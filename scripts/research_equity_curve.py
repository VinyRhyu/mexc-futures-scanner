"""Offline research: compound a 1-USDT PAPER wallet by re-quoting EACH entry.

Every candidate comes from an earlier fully causal OHLC replay. At its
historical signal instant we re-run production finance.evaluate with the
CURRENT simulated wallet equity, using the recorded historical candle opening
and frozen symbol contract metadata. Exit information, computed from the next
240 historical M1 candles, is consulted ONLY AFTER an entry is selected.

No authenticated exchange endpoints, real orders, live notifications or writes.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
import csv
import json
from pathlib import Path

from mexc_scanner.config import load_config
from mexc_scanner.models import Contract, D, Plan, Variant, jsonable, seconds
from scripts.audit_pullback import paper_quote

INITIAL_BALANCE=D("1")
RR_FLOOR=D("1.5")
SLIPS=(D("0.0002"),D("0.0005"),D("0.0010"))
ALLOWED_RULES=("BASE","RR15")


def describe_future_exit(candles,side,stop,target):
    """Precompute outcome for research replay; do NOT gate on this future data."""
    if len(candles)!=240:
        raise ValueError("need all 240 future closed M1 candles")
    sign=1 if side=="LONG" else -1 if side=="SHORT" else None
    if sign is None:
        raise ValueError("invalid direction")
    for bar in candles:
        bad=bar.low<=stop if sign==1 else bar.high>=stop
        good=bar.high>=target if sign==1 else bar.low<=target
        if bad or good:
            outcome="STOP_AMBIGUO" if bad and good else "STOP" if bad else "ALVO"
            reference=min(stop,bar.open) if sign==1 else max(stop,bar.open)
            if not bad:
                reference=target
            return {
                "outcome":outcome,"exit_reference":str(reference),
                "exit_at":datetime.fromtimestamp(bar.end,timezone.utc).isoformat(),
            }
    end=candles[-1]
    return {
        "outcome":"TIME_4H","exit_reference":str(end.close),
        "exit_at":datetime.fromtimestamp(end.end,timezone.utc).isoformat(),
    }


def pack_equity_candidate(plan,variant,contract_row,next_open,future,turnover,signal_at):
    if not future or len(future)!=240:
        raise ValueError("cannot export an incomplete horizon")
    if next_open!=future[0].open:
        raise ValueError("next opening price mismatch")
    if D(turnover)<D("5000000"):
        raise ValueError("less than historical five million turnover")
    if plan.symbol!=contract_row["symbol"] or variant.triggered_at!=int(datetime.fromisoformat(signal_at).timestamp()):
        raise ValueError("plan identity or as-of mismatch")
    return {
        "symbol":plan.symbol, "side":plan.side, "plan_id":plan.id,
        "signal_at":datetime.fromtimestamp(variant.triggered_at,timezone.utc).isoformat(),
        "turnover24_USDT":str(turnover),
        "plan":jsonable(plan),"variant":jsonable(variant),
        "contract_row":jsonable(contract_row),
        "next_open":str(next_open),
        "future_exit":describe_future_exit(future,plan.side,variant.stop,variant.target),
    }


def parse_candidate(raw):
    required=("symbol","side","plan_id","signal_at","turnover24_USDT",
              "plan","variant","contract_row","next_open","future_exit")
    if any(k not in raw for k in required):
        raise ValueError("missing essential equity replay candidate field")
    p=Plan.from_dict(raw["plan"])
    v=Variant.from_dict(raw["variant"])
    c=Contract.from_api(raw["contract_row"])
    if not (p.id==raw["plan_id"] and p.symbol==c.symbol==raw["symbol"]
            and p.side==raw["side"] and v.triggered_at==int(datetime.fromisoformat(raw["signal_at"]).timestamp())):
        raise ValueError("candidate contains cross-signal contract or plan data")
    if D(raw["turnover24_USDT"])<D("5000000"):
        raise ValueError("historical turnover gate violated")
    if v.entry_low>v.entry_high or v.status!="VALIDA":
        raise ValueError("recorded variant invalid")
    if D(raw["next_open"])<=0:
        raise ValueError("nonpositive opening")
    future=raw["future_exit"]
    if future["outcome"] not in ("STOP","STOP_AMBIGUO","ALVO","TIME_4H"):
        raise ValueError("invalid future outcome")
    exit_time=datetime.fromisoformat(future["exit_at"])
    entry_time=datetime.fromisoformat(raw["signal_at"])
    if not entry_time.tzinfo or not exit_time.tzinfo:
        raise ValueError("timezone-free timestamps")
    dt=(exit_time-entry_time).total_seconds()
    if not 0<dt<=4*3600:
        raise ValueError("exit must occur within 4h after entry")
    return p,v,c


def reprice_candidate(row,balance,cfg,slip,rr_floor):
    """Viability based ONLY on current balance and entry quote; outcome ignored."""
    p,v,c=parse_candidate(row)
    dynamic=replace(cfg,initial_balance=str(balance),slippage_rate=str(slip))
    quote=paper_quote(p,v,c,D(row["next_open"]),v.triggered_at+1,dynamic)
    if quote["status"]!="VIAVEL_SIMULADO":
        return None,quote.get("reasons",["BLOCK_UNKNOWN"])
    sign=D(1 if row["side"]=="LONG" else -1)
    open_mid=D(row["next_open"])
    entry_unadjusted=open_mid*(D(1)+sign*D("0.0001"))
    entry_slip=max(D(2)*c.tick,entry_unadjusted*D(slip))
    entry_band=entry_unadjusted+sign*entry_slip
    if not D(quote["entry_low"])<=entry_band<=D(quote["entry_high"]):
        return None,["NO_FILL_BAND"]
    if rr_floor is not None and D(quote["net_rr"])<D(rr_floor):
        return None,["PROJECTED_NET_RR_BELOW_FROZEN_FLOOR"]
    if D(quote["margin_usdt"])+D(quote["costs_usdt"])>balance:
        # The core validator also reserves costs and checks margin, but this
        # strict additional check guarantees the paper wallet does not
        # silently borrow above its own equity.
        return None,["MARGIN_PLUS_RESERVED_COSTS_EXCEED_EQUITY"]
    if D(quote["contracts"])<c.min_volume or D(quote["contracts"])>c.max_volume:
        raise ValueError("out-of-range contract volume")
    return {
        "quote":quote,"entry":entry_unadjusted,"entry_slip":entry_slip,
        "mid":open_mid,"contract":c,"config":dynamic,
    },[]


def settle_candidate(row,entry_snapshot,balance_before):
    """Use precomputed next-4h OHLC exit ONLY AFTER selecting the trade."""
    f=entry_snapshot["quote"]
    c=entry_snapshot["contract"]
    cfg=entry_snapshot["config"]
    fee,slip=D(cfg.taker_fee),D(cfg.slippage_rate)
    sign=D(1 if row["side"]=="LONG" else -1)
    mid=entry_snapshot["mid"]
    entry=entry_snapshot["entry"]
    entry_slip=entry_snapshot["entry_slip"]
    exit_data=row["future_exit"]
    ref=D(exit_data["exit_reference"])
    stop=D(row["variant"]["stop"])
    exit_slip=max(D(2)*c.tick,ref*slip)
    quantity=D(f["base_quantity"])
    if exit_data["outcome"]=="TIME_4H":
        effective_entry=entry+sign*entry_slip
        net=quantity*(sign*(ref-effective_entry)-exit_slip-
                      fee*(effective_entry+ref))
        risk=quantity*(sign*(effective_entry-stop)+entry_slip+
                       max(D(2)*c.tick,stop*slip)+fee*(effective_entry+stop))
    else:
        net=quantity*(sign*(ref-entry)-entry_slip-exit_slip-
                      fee*(entry+ref))
        risk=quantity*(sign*(entry-stop)+entry_slip+
                       max(D(2)*c.tick,stop*slip)+fee*(entry+stop))
    if risk<=0:
        raise ValueError("nonpositive realized R denominator")
    if D(f["loss_usdt"])>balance_before*D("0.1000000001"):
        raise ValueError("quote exceeded 10pct individual loss budget")
    if D(f["margin_usdt"])>balance_before:
        raise ValueError("quote margin exceeds balance")
    return {
        "net_usdt":net,"net_r":net/risk,
        "risk_usdt":risk,"contracts":D(f["contracts"]),
        "notional_usdt":quantity*D(f["worst_entry"]),
        "margin_usdt":D(f["margin_usdt"]),
        "cost_reserve_usdt":D(f["costs_usdt"]),
        "leverage":f["leverage"],
        "net_rr_projected":D(f["net_rr"]),
        "outcome":exit_data["outcome"],
        "exit_at":exit_data["exit_at"],
    }


def run_wallet(rows, *, rule="BASE", slip="0.0002", initial_balance=INITIAL_BALANCE):
    if rule not in ALLOWED_RULES:
        raise ValueError("unknown frozen entry criterion")
    if D(initial_balance)!=INITIAL_BALANCE:
        raise ValueError("research comparison uses exactly 1 USDT initial balance")
    slip=D(slip)
    if slip not in SLIPS:
        raise ValueError("slippage not preregistered")
    cfg=load_config("config/default.toml")
    if cfg.mode!="paper" or D(cfg.minimum_turnover)!=D("5000000"):
        raise ValueError("production paper assumptions changed")
    # Group by minute and market event; quote all alternative technical plans,
    # then deterministic minimum plan ID among *viable* plans.
    groups=defaultdict(lambda:defaultdict(list))
    seen=set()
    for r in rows:
        parse_candidate(r)
        identity=(r["symbol"],r["side"],r["signal_at"],r["plan_id"])
        if identity in seen:
            # One period includes the boundary minute of the next; remove it
            # rather than double count the candidate (the snapshots must match).
            continue
        seen.add(identity)
        groups[r["signal_at"]][(r["symbol"],r["side"])].append(r)
    start_equity=equity=INITIAL_BALANCE
    peak=equity
    max_drawdown=D(0)
    next_available=""
    journal=[]
    skip=Counter()
    seen_events=0
    winning_streak=losing_streak=max_losing_streak=0
    daily_breakdown=defaultdict(lambda:{"ops":0,"net":D(0)})
    for timestamp in sorted(groups):
        markets=groups[timestamp]
        seen_events+=len(markets)
        if timestamp<next_available:
            skip["IN_EXISTING_POSITION"]+=len(markets)
            continue
        if equity<=0:
            skip["BANKRUPT_OR_EXHAUSTED"]+=len(markets)
            continue
        # Lexicographic same-minute/symbol ordering matches the frozen replay.
        eligible=[]
        for market in sorted(markets):
            viables=[]
            for row in sorted(markets[market],key=lambda r:r["plan_id"]):
                quote,reasons=reprice_candidate(
                    row,equity,cfg,slip,None)
                if quote is not None:
                    viables.append((row,quote))
                else:
                    for reason in reasons:
                        skip[reason]+=1
            if not viables:
                continue
            first,quoted=viables[0]
            if rule=="RR15" and D(quoted["quote"]["net_rr"])<RR_FLOOR:
                skip["RR15_FROZEN_VETO"]+=1
                continue
            eligible.append((first,quoted))
        if not eligible:
            continue
        selected,quote=min(eligible,key=lambda x:(x[0]["symbol"],x[0]["plan_id"]))
        balance_before=equity
        trade=settle_candidate(selected,quote,balance_before)
        equity+=trade["net_usdt"]
        peak=max(peak,equity)
        drawdown=peak-equity
        max_drawdown=max(max_drawdown,drawdown)
        if equity<0:
            raise ValueError("modeled net PnL exceeded wallet and went negative")
        pnl=trade["net_usdt"]
        if pnl>0:
            winning_streak+=1
            losing_streak=0
        else:
            winning_streak=0
            losing_streak+=1
            max_losing_streak=max(max_losing_streak,losing_streak)
        next_available=trade["exit_at"]
        daily_breakdown[selected["signal_at"][:10]]["ops"]+=1
        daily_breakdown[selected["signal_at"][:10]]["net"]+=pnl
        journal.append({
            "signal_at":selected["signal_at"],"exit_at":trade["exit_at"],
            "symbol":selected["symbol"],"side":selected["side"],
            "plan_id":selected["plan_id"],"outcome":trade["outcome"],
            "balance_before":str(balance_before),
            "balance_after":str(equity),
            **{k:str(v) if isinstance(v,Decimal) else v for k,v in trade.items()},
        })
    return {
        "name":rule,"slippage_per_side":str(slip),
        "initial_usdt":str(start_equity),"ending_usdt":str(equity),
        "net_usdt":str(equity-start_equity),
        "net_pct_of_initial":str((equity/start_equity-D(1))*100),
        "trades":len(journal),"wins":sum(D(x["net_usdt"])>0 for x in journal),
        "total_net_R":str(sum((D(x["net_r"]) for x in journal),D(0))),
        "max_realized_drawdown_usdt":str(max_drawdown),
        "max_realized_drawdown_pct_of_initial":str(max_drawdown/start_equity*100),
        "max_losing_streak":max_losing_streak,
        "total_market_events_considered":seen_events,
        "unique_plan_candidates":len(seen),
        "skipped_or_blocked_counts":dict(skip),
        "daily_ledger":{day:{"trades":x["ops"],"net_usdt":str(x["net"])}
                        for day,x in sorted(daily_breakdown.items())},
        "trades_detail":journal,
        "exclusions":(
            "MEXC historical rank top50, historical depth, real fills, "
            "actual funding, personalized fees and historical contract spec unavailable"
        ),
    }


def combine_replay_inputs(files):
    all_cases=[]
    source_windows=[]
    for source in files:
        payload=json.loads(Path(source).read_text(encoding="utf8"))
        if payload.get("schema")!=1 or payload.get("snapshot_sha256")!=(
               "edf08de9b2c1027c7631069a9b86baa73febd799c56fc8c2edf2274bc82601a1"):
            raise ValueError("incorrect or modified historical research cohort")
        if payload["completed_symbols"]!=24 or payload["incomplete_symbols"]:
            raise ValueError("incomplete source historical universe")
        for row in payload["candidates"]:
            parse_candidate(row)
        all_cases.extend(payload["candidates"])
        source_windows.append((payload["start_utc"],payload["end_utc_exclusive"]))
    source_windows.sort()
    if len(source_windows)!=5 or [x[0] for x in source_windows[1:]] != [
            x[1] for x in source_windows[:-1]]:
        raise ValueError("expected exact five continuous, non-overlapping source windows")
    if source_windows[0][0]!="2026-10-26T00:00:00+00:00" or (
          source_windows[-1][1]!="2026-11-22T20:00:00+00:00"):
        raise ValueError("source timeline differs from registered study")
    return all_cases,source_windows


def save_replay(replays,out_dir,windows):
    out_dir=Path(out_dir)
    out_dir.mkdir(parents=True,exist_ok=True)
    summaries=[]
    all_trade_rows=[]
    for r in replays:
        summaries.append({k:v for k,v in r.items() if k!="trades_detail"})
        for trade in r["trades_detail"]:
            all_trade_rows.append({"rule":r["name"],"slippage":r["slippage_per_side"],**trade})
    (out_dir/"equity_report.json").write_text(
        json.dumps({"windows":windows,"cases":summaries,
                    "warning":"simulated ledger from 1-USDT paper quote, not live executable trading"},
                   indent=2,ensure_ascii=False)+"\n")
    keys=["rule","slippage","signal_at","exit_at","symbol","side","plan_id",
          "outcome","balance_before","net_usdt","balance_after","net_r",
          "risk_usdt","contracts","notional_usdt","margin_usdt",
          "cost_reserve_usdt","leverage","net_rr_projected"]
    with (out_dir/"compounded_1usdt_paper_ledger.csv").open(
        "w",newline="",encoding="utf-8-sig") as f:
        writer=csv.DictWriter(f,fieldnames=keys,extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_trade_rows)
    return summaries


def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--inputs",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    files=sorted(args.inputs.glob("**/equity_candidates_*.json"))
    if len(files)!=5:
        raise ValueError("expected five exact source reports, not partial subset")
    rows,windows=combine_replay_inputs(files)
    results=[]
    for slip in SLIPS:
        for rule in ALLOWED_RULES:
            results.append(run_wallet(rows,rule=rule,slip=slip))
    outputs=save_replay(results,args.output,windows)
    for r in outputs:
        print("WALLET_1USDT_COMPOUNDED="+json.dumps({
            k:r[k] for k in ("name","slippage_per_side","initial_usdt",
                             "ending_usdt","net_usdt","trades","wins",
                             "max_realized_drawdown_usdt","max_losing_streak")
        },ensure_ascii=False),flush=True)


if __name__=="__main__":
    main()
