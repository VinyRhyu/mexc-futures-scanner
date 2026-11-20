"""BRK-T research: causal M5 compression breakout with H1 trend LONG/SHORT.

Frozen rules: docs/brk-t-preregistered-2026-11-20.md. No live orders or Telegram.
"""
from __future__ import annotations
import argparse
import bisect
import json
from collections import Counter
from datetime import datetime, timezone
from statistics import median

from scripts.audit_confluence_extended import candles, select_portfolio
from scripts.audit_confluence_v3 import FIVE_MS, HOUR_MS, SYMBOLS, atr_before, iso, replay_structural
from scripts.audit_confluence_pilot import Parameters
from scripts.audit_smc_liquidity_fvg import WINDOWS, portfolio_metrics


def trend_states(hourly):
    """EMA20/EMA50 seeded at 20th/50th H1 close, indexed by H1 END."""
    ends = [int(h[0]) + HOUR_MS for h in hourly]
    if any(a >= b for a,b in zip(ends,ends[1:])):
        raise ValueError("H1 must be strictly ordered")
    closes = [float(h[4]) for h in hourly]
    ema20 = ema50 = None
    states = []
    for i, close in enumerate(closes):
        if i == 19:
            ema20 = sum(closes[:20])/20
        elif i > 19:
            ema20 = close*(2/21) + ema20*(19/21)
        if i == 49:
            ema50 = sum(closes[:50])/50
        elif i > 49:
            ema50 = close*(2/51) + ema50*(49/51)
        if i < 49:
            states.append(None)
        else:
            states.append("LONG" if close > ema20 > ema50 else
                          "SHORT" if close < ema20 < ema50 else None)
    return ends, states


def signal_at(five, hourly, index, precomputed=None):
    """Signal at CLOSE of index, no future M5/H1 used to decide."""
    if index < 38 or index >= len(five):
        return None
    ends, states = precomputed if precomputed is not None else trend_states(hourly)
    at = int(five[index][0]) + FIVE_MS
    h = bisect.bisect_right(ends, at) - 1
    if h < 49 or states[h] is None:
        return None
    side = states[h]
    atr = atr_before(five,index)
    if atr <= 0:
        return None
    prior = five[index-12:index]
    hi = max(float(c[2]) for c in prior)
    lo = min(float(c[3]) for c in prior)
    if hi-lo > 3.0*atr:
        return None
    bar = five[index]
    op, high, low, close = map(float,(bar[1],bar[2],bar[3],bar[4]))
    span = high-low
    body = close-op if side=="LONG" else op-close
    rv = float(bar[6]) / max(1e-12,median(float(c[6]) for c in prior))
    if (span<=0 or span>3.0*atr or body<0.6*atr or rv<1.5):
        return None
    if side=="LONG" and close<hi+0.1*atr:
        return None
    if side=="SHORT" and close>lo-0.1*atr:
        return None
    return {"signal_index":index,"signal_at":iso(at),"side":side,
            "stop_raw":(lo-0.1*atr if side=="LONG" else hi+0.1*atr),
            "relative_quote_volume":rv,"atr":atr,
            "range_high":hi,"range_low":lo}


def execute(five, setup, params=Parameters(), hold_bars=24):
    i=setup["signal_index"]
    if i+hold_bars>=len(five):
        return None
    side=setup["side"]
    entry=float(five[i+1][1])
    stop=setup["stop_raw"]
    risk=(entry-stop if side=="LONG" else stop-entry)
    if risk<=0:
        return None
    target=(entry+1.8*risk if side=="LONG" else entry-1.8*risk)
    cost=2*entry*(params.taker_fee_each+params.slippage_each)
    net_rr=(1.8*risk-cost)/(risk+cost)
    if net_rr<1.2:
        return None
    state="TIME"
    exit_price=float(five[i+hold_bars][4])
    end_i=i+hold_bars
    for k in range(i+1,i+hold_bars+1):
        bar=five[k]
        high,low=float(bar[2]),float(bar[3])
        bad=(low<=stop if side=="LONG" else high>=stop)
        good=(high>=target if side=="LONG" else low<=target)
        if bad or good:
            state="AMBIGUOUS" if bad and good else "SL" if bad else "TP"
            exit_price=None if bad and good else stop if bad else target
            end_i=k
            break
    profit=((exit_price-entry if side=="LONG" else entry-exit_price)-cost
            if exit_price is not None else None)
    net_r=(profit/(risk+cost) if profit is not None else None)
    return {"signal_at":setup["signal_at"],"entry_at":iso(int(five[i+1][0])),
            "exit_at":iso(int(five[end_i][0])),"result":state,"side":side,
            "entry":round(entry,8),"stop":round(stop,8),"target":round(target,8),
            "net_r":round(net_r,5) if net_r is not None else None,
            "relative_quote_volume":round(setup["relative_quote_volume"],5),
            "net_rr_ex_ante":round(net_rr,5)}


def replay(five,hourly):
    state=trend_states(hourly)
    starts=[int(c[0]) for c in five]
    next_index=38
    trades=[]
    diagnostics=Counter()
    for i in range(38,len(five)-25):
        if i<next_index:
            continue
        setup=signal_at(five,hourly,i,state)
        if setup is None:
            continue
        diagnostics["signals"]+=1
        trade=execute(five,setup)
        if trade is None:
            diagnostics["rejected_rr"]+=1
            continue
        trades.append(trade)
        diagnostics[setup["side"]]+=1
        end_ms=int(datetime.fromisoformat(trade["exit_at"]).timestamp()*1000)
        next_index=bisect.bisect_right(starts,end_ms)
    return trades,dict(diagnostics)


def run(window):
    first,last=WINDOWS[window]
    start=int(datetime.fromisoformat(first).timestamp())
    end=int(datetime.fromisoformat(last).timestamp())
    mid=iso((start+21*86400)*1000)
    print("BRKT_START "+json.dumps({"window":window,"dates":[first,mid,last],
         "symbols":SYMBOLS,"frozen_doc":"docs/brk-t-preregistered-2026-11-20.md"}),flush=True)
    pool={"F_original":[],"BRKT_LONG":[],"BRKT_SHORT":[],"BRKT_COMBINED":[]}
    errors=[]
    for symbol in SYMBOLS:
        sym=symbol+"_USDT"
        try:
            h=candles(sym,"Min60",start-100*3600,end)
            m=candles(sym,"Min5",start-52*300,end)
            base=replay_structural(m,h,"F_sweep_rejection")
            challenger,diag=replay(m,h)
            for t in base:
                if first<=t["signal_at"]<last:
                    pool["F_original"].append({**t,"symbol":sym})
            for t in challenger:
                if first<=t["signal_at"]<last:
                    row={**t,"symbol":sym}
                    pool["BRKT_"+t["side"]].append(row)
                    pool["BRKT_COMBINED"].append(row)
            print("BRKT_ASSET "+json.dumps({"window":window,"symbol":sym,
                  "M5":len(m),"H1":len(h),"F":len(base),
                  "BRKT":len(challenger),"diagnostics":diag}),flush=True)
        except Exception as exc:
            errors.append({"symbol":sym,"error":f"{type(exc).__name__}: {str(exc)[:180]}"})
            print("BRKT_SOURCE_ERROR "+json.dumps({"window":window,**errors[-1]}),flush=True)
    if errors:
        raise RuntimeError(f"Refusing partial {window}: {errors}")
    for name,trades in pool.items():
        report={"early21":portfolio_metrics(trades,first,mid),
                "late21":portfolio_metrics(trades,mid,last),
                "full42":portfolio_metrics(trades,first,last)}
        print("BRKT_VARIANT "+json.dumps({"window":window,"model":name,
              "results":report,"historical_not_prospective":True},sort_keys=True),flush=True)
    print("BRKT_DONE "+json.dumps({"window":window,"complete_symbols":len(SYMBOLS)}),flush=True)


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--window",required=True,choices=tuple(WINDOWS))
    run(p.parse_args().window)
