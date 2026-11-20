"""BCM-1: frozen compression breakout momentum in LONG and SHORT, research only.

Rules registered BEFORE historical runs in
docs/compression-momentum-preregistered-2026-11-20.md.
Causal signal: M5 current and prior closed candles + last CLOSED H1 only.
Returns paper trades; never posts Telegram messages or orders.
"""
from __future__ import annotations
import argparse
import bisect
import json
from collections import Counter
from datetime import datetime, timezone
from statistics import median

from scripts.audit_confluence_extended import candles
from scripts.audit_confluence_v3 import FIVE_MS, HOUR_MS, SYMBOLS, atr_before, iso, replay_structural, true_range
from scripts.audit_confluence_pilot import Parameters
from scripts.audit_smc_liquidity_fvg import h1_states, portfolio_metrics


WINDOWS = {
    "S": ("2026-04-24T11:00:00+00:00", "2026-06-05T11:00:00+00:00"),
    "T": ("2026-06-05T11:00:00+00:00", "2026-07-17T11:00:00+00:00"),
    "U": ("2026-07-17T11:00:00+00:00", "2026-08-28T11:00:00+00:00"),
    "V": ("2026-08-28T11:00:00+00:00", "2026-10-09T11:00:00+00:00"),
    "W": ("2026-10-09T11:00:00+00:00", "2026-11-20T11:00:00+00:00"),
}


def detect_breakout(five, hourly, index, states=None):
    """Inspect NO candle after index. Return LONG or SHORT only after M5 close."""
    if index < 50 or index >= len(five):
        return None
    # H1 EMA20 is built using only completed H1. The state at decision is
    # chosen by bisect-right over H1 close timestamps, not current H1 open.
    ends, down = states if states is not None else h1_states(hourly)
    decision = int(five[index][0]) + FIVE_MS
    hpos = bisect.bisect_right(ends, decision) - 1
    if hpos < 19:
        return None

    atr = atr_before(five, index)
    if atr <= 0:
        return None
    consolidation = five[index - 12:index]
    baseline = five[index - 48:index - 12]
    def avg_tr(candles_subset, previous_index):
        n = len(candles_subset)
        return sum(true_range(five[j], float(five[j-1][4]))
                   for j in range(previous_index, previous_index+n)) / n
    # Previous 36 M5 immediately before consolidation (no overlap).
    base_mean = avg_tr(baseline, index-48)
    recent_mean = avg_tr(consolidation, index-12)
    if base_mean <= 0 or recent_mean > 0.85*base_mean:
        return None
    ceiling = max(float(r[2]) for r in consolidation)
    floor = min(float(r[3]) for r in consolidation)
    if ceiling - floor > 4*atr:
        return None

    bar = five[index]
    op,high,low,close = (float(bar[k]) for k in (1,2,3,4))
    width=high-low
    candle_tr=true_range(bar, float(five[index-1][4]))
    if (width <= 0 or abs(close-op)/width < 0.60
            or not atr <= candle_tr <= 3*atr):
        return None
    relative_amount=float(bar[6])/max(1e-12,
                   median(float(r[6]) for r in consolidation))
    if relative_amount < 1.5:
        return None

    if not down[hpos] and close > ceiling + 0.10*atr and close > op:
        direction="LONG"
        stop=low-0.1*atr
    elif down[hpos] and close < floor-0.10*atr and close < op:
        direction="SHORT"
        stop=high+0.1*atr
    else:
        return None
    return {
        "signal_at":iso(decision), "signal_ms":decision,
        "signal_index":index, "direction":direction,
        "box_high":ceiling,"box_low":floor,"atr":atr,
        "relative_quote_volume":relative_amount,
        "stop_raw":stop,
        "compression_ratio":recent_mean/base_mean,
        "body_fraction":abs(close-op)/width,
    }


def simulate_trade(five, signal, params=Parameters(), *, hold_bars=24):
    """Next M5 OPEN fill assumption; intrabar ambiguous is conservative loss."""
    i=signal["signal_index"]
    if i+hold_bars>=len(five):
        return None
    entry=float(five[i+1][1])
    stop=float(signal["stop_raw"])
    direction=signal["direction"]
    risk=(entry-stop) if direction=="LONG" else (stop-entry)
    if entry<=0 or stop<=0 or risk<=0:
        return None
    target=entry+(1.8*risk if direction=="LONG" else -1.8*risk)
    if target<=0:
        return None
    cost=2*entry*(params.taker_fee_each+params.slippage_each)
    rr_net=(1.8*risk-cost)/(risk+cost)
    if rr_net<1.2:
        return None
    outcome="TIME"
    endidx=i+hold_bars
    exitpx=float(five[endidx][4])
    for k in range(i+1,i+hold_bars+1):
        c=five[k]
        if direction=="LONG":
            sl=float(c[3])<=stop
            tp=float(c[2])>=target
        else:
            sl=float(c[2])>=stop
            tp=float(c[3])<=target
        if sl or tp:
            outcome=("AMBIGUOUS" if sl and tp else "SL" if sl else "TP")
            exitpx=None if sl and tp else stop if sl else target
            endidx=k
            break
    netr=None if exitpx is None else (
        (exitpx-entry-cost)/(risk+cost) if direction=="LONG"
        else (entry-exitpx-cost)/(risk+cost)
    )
    return {
        "signal_at":signal["signal_at"],
        "direction":direction,
        "entry_at":iso(int(five[i+1][0])),
        "exit_at":iso(int(five[endidx][0])),
        "entry":round(entry,9), "stop":round(stop,9), "target":round(target,9),
        "result":outcome, "net_r":round(netr,5) if netr is not None else None,
        "relative_quote_volume":round(signal["relative_quote_volume"],5),
        "net_rr_ex_ante":round(rr_net,4),
        "box_high":round(signal["box_high"],9),
        "box_low":round(signal["box_low"],9),
        "compression_ratio":round(signal["compression_ratio"],4),
    }


def replay_bcm(five, hourly):
    """One position per symbol at a time, regardless of LONG/SHORT direction."""
    ends_flags=h1_states(hourly)
    starts=[int(r[0]) for r in five]
    allowed=50
    diagnostics=Counter()
    trades=[]
    for i in range(50,len(five)-25):
        if i<allowed:
            continue
        setup=detect_breakout(five,hourly,i,ends_flags)
        if setup is None:
            continue
        diagnostics["compression_breakout_formed"]+=1
        diagnostics["setups_"+setup["direction"]]+=1
        trade=simulate_trade(five,setup)
        if trade is None:
            diagnostics["risk_reward_reject"]+=1
            continue
        diagnostics["paper_"+setup["direction"]]+=1
        trades.append(trade)
        exit_ms=int(datetime.fromisoformat(trade["exit_at"]).timestamp()*1000)
        allowed=bisect.bisect_right(starts,exit_ms)
    return trades,dict(diagnostics)


def run(window):
    start_iso,end_iso=WINDOWS[window]
    start=int(datetime.fromisoformat(start_iso).timestamp())
    end=int(datetime.fromisoformat(end_iso).timestamp())
    mid=iso((start+21*86400)*1000)
    print("BCM_WINDOW "+json.dumps({
        "window":window,"first":start_iso,"mid":mid,"last":end_iso,
        "assets":SYMBOLS,"frozen":"docs/compression-momentum-preregistered-2026-11-20.md",
        "no_orders":True,
    },sort_keys=True),flush=True)
    variants={"F_baseline_SHORT":[],"BCM_BOTH":[],"BCM_LONG":[],"BCM_SHORT":[]}
    failures=[]
    totals={}
    for symbol in SYMBOLS:
        ticker=symbol+"_USDT"
        try:
            hourly=candles(ticker,"Min60",start-80*3600,end)
            five=candles(ticker,"Min5",start-80*300,end)
            controls=replay_structural(five,hourly,"F_sweep_rejection")
            runtrades,diag=replay_bcm(five,hourly)
            controls=[{**t,"symbol":ticker} for t in controls
                      if start_iso<=t["signal_at"]<end_iso]
            runtrades=[{**t,"symbol":ticker} for t in runtrades
                       if start_iso<=t["signal_at"]<end_iso]
            variants["F_baseline_SHORT"].extend(controls)
            variants["BCM_BOTH"].extend(runtrades)
            variants["BCM_LONG"].extend(t for t in runtrades if t["direction"]=="LONG")
            variants["BCM_SHORT"].extend(t for t in runtrades if t["direction"]=="SHORT")
            totals[ticker]=diag
            print("BCM_ASSET "+json.dumps({
                "window":window,"symbol":ticker,"M5":len(five),"H1":len(hourly),
                "baseline_F":len(controls),
                "BCM_LONG":sum(t["direction"]=="LONG" for t in runtrades),
                "BCM_SHORT":sum(t["direction"]=="SHORT" for t in runtrades),
                "diagnostics":diag,
            },sort_keys=True),flush=True)
        except Exception as e:
            failures.append({"symbol":ticker,"error":f"{type(e).__name__}: {str(e)[:180]}"})
            print("BCM_DATA_FAIL "+json.dumps({"window":window,**failures[-1]}),flush=True)
    if failures:
        print("BCM_WINDOW_INCOMPLETE "+json.dumps({"window":window,"errors":failures}),flush=True)
        raise RuntimeError(f"Refusing partial historical window {window}: {len(failures)} missing assets")
    for label,ts in variants.items():
        result={
            "early21":portfolio_metrics(ts,start_iso,mid),
            "late21":portfolio_metrics(ts,mid,end_iso),
            "full42":portfolio_metrics(ts,start_iso,end_iso),
        }
        print("BCM_VARIANT "+json.dumps({
            "window":window,"model":label,"results":result,
            "per_symbol_candidates":dict(Counter(t["symbol"] for t in ts)),
            "assumed_taker_fee_side":Parameters().taker_fee_each,
            "assumed_slippage_side":Parameters().slippage_each,
            "retrospective_only":True,
        },sort_keys=True),flush=True)
    print("BCM_DONE "+json.dumps({"window":window,"data_complete":True,
          "symbols":len(SYMBOLS),"diagnostics":totals},sort_keys=True),flush=True)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--window",required=True,choices=tuple(WINDOWS))
    args=p.parse_args()
    run(args.window)


if __name__=="__main__":
    main()
