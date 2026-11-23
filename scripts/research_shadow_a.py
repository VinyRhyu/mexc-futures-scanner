"""Read-only shadow check of frozen filter A against recorded production M1 signals.

No state writes, Telegram, orders, wallet, P&L simulation, or secrets.
Reads an existing state.json snapshot and public MEXC closed candles.
The first retrospective bootstrap is NOT prospective evidence.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from bisect import bisect_left, bisect_right
import argparse
import json

from mexc_scanner.market import parse_candles
from mexc_scanner.mexc import MexcClient
from mexc_scanner.minute_breakout import MODEL, STRATEGY, validate_minute_ohlc
from mexc_scanner.models import D, DataError
from scripts.research_entry_context import entry_context

MAX_STATE_AGE = 30 * 60
LOOKBACK_HOURS = 12


def iso(ts):
    return datetime.fromtimestamp(int(ts), timezone.utc).isoformat()


def candidates_from_state(state, observed_at, since_seconds=LOOKBACK_HOURS*3600):
    """Selection uses historical technical triggers only, not hindsight status/PnL."""
    if state.get("active_signal_model") != MODEL:
        raise DataError("Scanner state is not running intended production model")
    last_success = state.get("last_success")
    if type(last_success) is not int or last_success <= 0:
        raise DataError("Missing scanner checkpoint")
    if not -300 <= observed_at-last_success <= MAX_STATE_AGE:
        raise DataError("Scanner state missing or stale")
    if not 60 <= since_seconds <= LOOKBACK_HOURS*3600:
        raise DataError("Invalid observation lookback")
    plans = state.get("plans")
    if not isinstance(plans, dict):
        raise DataError("Scanner plans absent or invalid")
    seen, rows = set(), []
    for p in plans.values():
        if not isinstance(p, dict) or p.get("strategy") != STRATEGY:
            continue
        v = p.get("variants", {}).get("CONFIRMADA")
        if not isinstance(v, dict):
            continue
        t = v.get("triggered_at")
        if type(t) is not int or not observed_at-since_seconds <= t <= observed_at:
            continue
        key = (p["id"], t)
        if key in seen:
            continue
        seen.add(key)
        symbol, side = p["symbol"],p["side"]
        if side not in ("LONG","SHORT"):
            raise DataError("Invalid saved direction")
        rows.append({
            "plan_id":p["id"], "symbol":symbol, "side":side,
            "signal_at":t, "signal_iso":iso(t),
            "stop":str(v["stop"]), "target":str(v["target"]),
            "entry_low":str(v["entry_low"]), "entry_high":str(v["entry_high"]),
            "snapshot_status":p.get("status"),
        })
    return sorted(rows,key=lambda r:(r["signal_at"],r["symbol"],r["plan_id"]))


def touch_path(minute, at_index, side, stop, target, now):
    """Describes prices after signal, not real entry or financial trade outcome."""
    signal = minute[at_index]
    until=signal.end+4*3600
    later=[c for c in minute[at_index+1:] if c.ts < until]
    complete=now>=until+10 and len(later)==240
    sign=1 if side=="LONG" else -1
    if not later:
        return {"path_status":"SEM_M1_POSTERIOR","window_complete":False}
    for c in later:
        bad=(c.low <= D(stop) if sign==1 else c.high >= D(stop))
        good=(c.high >= D(target) if sign==1 else c.low <= D(target))
        if bad or good:
            return {"path_status":("AMBIGUO_STOP_PRIMEIRO" if bad and good
                                   else "TOCOU_SL" if bad else "TOCOU_TP"),
                    "observed_at":iso(c.end),
                    "window_complete":complete}
    return {"path_status":"NENHUM_TOQUE_4H" if complete else "OBSERVACAO_PARCIAL",
            "window_complete":complete}


def analyze_symbol(client, symbol, signals, clock):
    # Need 240 M1 + up to 12h of signal age, plus buffer and 4h exit observation.
    minute = parse_candles(client.candles(symbol,"Min1",1100,clock),60,clock,1100)
    quarter = parse_candles(client.candles(symbol,"Min15",560,clock),900,clock,560)
    hourly = parse_candles(client.candles(symbol,"Min60",260,clock),3600,clock,260)
    validate_minute_ohlc(quarter, minute)
    m_ends=[c.end for c in minute]
    q_ends=[c.end for c in quarter]
    h_ends=[c.end for c in hourly]
    result=[]
    for row in signals:
        t=row["signal_at"]
        pos=bisect_left(m_ends,t)
        if pos>=len(m_ends) or m_ends[pos]!=t:
            raise DataError("Signal minute unavailable or unclosed")
        qpos=bisect_right(q_ends,t)
        hpos=bisect_right(h_ends,t)
        q=quarter[:qpos][-480:]
        h=hourly[:hpos][-240:]
        if len(q)<480 or len(h)<240:
            raise DataError("Missing complete historical warmup as of signal")
        context=entry_context(q,h,minute,pos,row["side"])
        if context["asof"]!=t:
            raise DataError("Causal timestamp mismatch")
        audit={"verdict_A":"POSSIVEL_ENTRADA_TARDIA" if context["A_late"]
                           else "SEM_VETO_A",
               "signed_4h_atr":context["m1_signed_4h_extension_atr"],
               "threshold_atr":context["A_threshold_atr"],
               "h1_structure_diagnostic":context["h1_structure"],
               "diagnostic_only":True,
               "not_a_fill":True}
        audit.update(touch_path(minute,pos,row["side"],row["stop"],row["target"],clock))
        result.append(dict(row,shadow=audit))
    return result


def run(state, client, clock, lookback_hours=LOOKBACK_HOURS):
    signals=candidates_from_state(state,clock,int(lookback_hours*3600))
    by_symbol=defaultdict(list)
    for row in signals:
        by_symbol[row["symbol"]].append(row)
    classified, errors=[], {}
    for symbol in sorted(by_symbol):
        try:
            classified+=analyze_symbol(client,symbol,by_symbol[symbol],clock)
        except (DataError,ValueError,KeyError,TypeError) as exc:
            errors[symbol]=type(exc).__name__+": "+str(exc)[:160]
    result={
        "kind":"SHADOW_A_READONLY_BOOTSTRAP",
        "created_at_utc":iso(clock),
        "baseline_model":MODEL,
        "filter":"A: 4h directional M1 close displacement >= 2 M15 ATR(14)",
        "lookback_hours":lookback_hours,
        "fresh_prospective_sample":False,
        "reason_not_prospective":"Prior state signals are observed retrospectively at bootstrap",
        "signals_found":len(signals),
        "signals_classified":len(classified),
        "symbols_with_errors":errors,
        "shadow_rejected":sum(x["shadow"]["verdict_A"]=="POSSIVEL_ENTRADA_TARDIA" for x in classified),
        "shadow_allowed":sum(x["shadow"]["verdict_A"]=="SEM_VETO_A" for x in classified),
        "path_observations":dict(Counter(x["shadow"]["path_status"] for x in classified)),
        "assumptions":[
            "Technical confirmations already recorded in scanner-state, not reconstructed financial fills",
            "Signals may have expired before the current snapshot; original status is not used to select winners",
            "Causal computation uses only M1/M15/H1 candles closed by original confirmation",
            "No historical quote, order book, personal funding, or actual entry feasibility checks",
            "SL/TP path is descriptive only; no historical execution/PnL or win-rate claim",
            "No state writes, outbox access, Telegram or trading endpoints",
            "Bootstrap is retrospective; recurrent captures must be timestamped independently to validate prospectively",
        ],
        "signals":classified,
    }
    if len(classified)+len(errors)==0:
        result["classification_status"]="NO_SIGNALS_IN_LOOKBACK"
    elif errors:
        result["classification_status"]="PARTIAL"
    else:
        result["classification_status"]="COMPLETE"
    return result


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--state",type=Path,default=Path("shadow-source/state.json"))
    ap.add_argument("--output",type=Path,default=Path("reports/shadow-a"))
    ap.add_argument("--lookback-hours",type=int,default=LOOKBACK_HOURS)
    args=ap.parse_args()
    if not args.state.is_file():
        raise SystemExit("Read-only state source unavailable")
    # Never copy sensitive source state into artifacts or logs.
    state=json.loads(args.state.read_text(encoding="utf-8"))
    client=MexcClient()
    now=client.server_time()
    out=run(state,client,now,args.lookback_hours)
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/"shadow-result.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    summary={key:out[key] for key in ("created_at_utc","classification_status","signals_found",
                                      "signals_classified","shadow_rejected","shadow_allowed",
                                      "path_observations","symbols_with_errors")}
    print("SHADOW_A_SUMMARY="+json.dumps(summary,ensure_ascii=False),flush=True)
    if out["symbols_with_errors"]:
        raise SystemExit("Partial shadow coverage; do not treat incomplete samples as success")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
