"""One-off MEXC Futures USDT-altcoin census with frozen F sweep-rejection SHORT.

Research-only. Never executes orders, sends Telegram or modifies scanner state.
For reproducibility ALL symbols are analyzed at the same CLOSED M5/H1 UTC cutoff.
Rates, spread, funding and fills must be checked again before any real order.
"""
from __future__ import annotations
import argparse
import concurrent.futures
import json
import math
import time
from collections import Counter
from datetime import datetime,timezone
from statistics import median
from urllib.request import Request,urlopen

from scripts.audit_confluence_extended import candles
from scripts.audit_confluence_v3 import (
    candidate_f, atr_before, h1_bias_below_ema_at, iso, FIVE_MS, HOUR_MS
)
from scripts.audit_confluence_pilot import Parameters

BASE = "https://api.mexc.com"
STABLE = {"USDC","USDT","DAI","FDUSD","TUSD","USDE","USD1","PYUSD","USDD"}
QUOTE = "_USDT"


def get_json(path):
    req = Request(BASE+path,headers={"User-Agent":"AltcoinResearchCensus/1.0"})
    last=None
    for j in range(3):
        try:
            with urlopen(req,timeout=22) as resp:
                doc=json.load(resp)
            if not isinstance(doc,dict) or not doc.get("success") or int(doc.get("code",-1))!=0:
                raise RuntimeError(f"API returned non-success {str(doc)[:120]}")
            return doc.get("data")
        except Exception as exc:
            last=exc
            if j<2:
                time.sleep(0.5*(j+1))
    raise last


def universe():
    details = get_json("/api/v1/contract/detail")
    tickers = get_json("/api/v1/contract/ticker")
    if not isinstance(details,list):
        raise ValueError("Contract list is not a list")
    tmap = {x["symbol"]: x for x in tickers if isinstance(x,dict) and x.get("symbol")} \
        if isinstance(tickers,list) else {}
    eligible=[]
    discarded=Counter()
    for item in details:
        s=item.get("symbol")
        if not s or not s.endswith(QUOTE):
            discarded["not_usdt"]+=1
            continue
        base = s[:-len(QUOTE)]
        if base=="BTC" or base in STABLE:
            discarded["bitcoin_or_stable"]+=1
            continue
        if int(item.get("state",-1))!=0:
            discarded["not_enabled"]+=1
            continue
        eligible.append((s,item,tmap.get(s,{})))
    return eligible,discarded,len(details)


def safe_float(v):
    try:
        n=float(v)
        return n if math.isfinite(n) else None
    except (TypeError,ValueError):
        return None


def evaluate_one(task,anchor):
    symbol,contract,ticker=task
    end_m5=anchor
    end_h1=anchor-anchor%3600
    try:
        # All candle close times <= frozen, shared anchor; no current M5/H1.
        m=candles(symbol,"Min5",end_m5-52*300,end_m5)
        h=candles(symbol,"Min60",end_h1-50*3600,end_h1)
        idx=len(m)-1
        f=candidate_f(m,h,idx)
        close=float(m[-1][4])
        a=atr_before(m,idx)
        if a<=0 or close<=0:
            raise ValueError("invalid close or ATR")
        prior_high=max(float(x[2]) for x in m[idx-24:idx])
        rel_vol=float(m[-1][6])/max(1e-12,median(float(x[6]) for x in m[-13:-1]))
        h1_down=h1_bias_below_ema_at(h,anchor*1000)
        turnover=safe_float(ticker.get("amount24"))
        bid=safe_float(ticker.get("bid1"))
        ask=safe_float(ticker.get("ask1"))
        spread=(ask-bid)/((ask+bid)/2)*100 if bid and ask and ask>=bid else None
        state="NONE";reason="NO_SWEEP_REJECTION";setup=None
        if f:
            # Entry next candle has not executed. Use signal CLOSE ONLY as a
            # theoretical reference. Never claim a realized or fillable price.
            stop=f["stop_raw"]
            risk=stop-close
            cost=2*close*(Parameters().taker_fee_each+Parameters().slippage_each)
            net_rr=(1.8*risk-cost)/(risk+cost) if risk>0 else -1
            if risk>0 and net_rr>=1.2:
                state="SIGNAL_M5"
                setup={
                    "signal_at_utc":iso(anchor*1000),
                    "close_reference":round(close,10),
                    "stop_reference":round(stop,10),
                    "target_reference":round(close-1.8*risk,10),
                    "estimated_net_rr":round(net_rr,3),
                    "entry_note":"Not a fill. Next-M5 open/market execution not observed.",
                    "sweep_level":round(f["level"],10),
                    "vol_ratio":round(f["volume_ratio"],3),
                }
                reason="M5_SWEEP_REJECTION_CAUSAL"
            else:
                state="FILTERED";reason="EX_ANTE_NET_RR_BELOW_1_2"
        if state=="NONE" and h1_down:
            # Observation only: price in resistance zone with low bounce,
            # no valid trigger. Do not label entry permitted.
            # Near top if a prior M5 in last 6 bars reached nearby resistance
            # and last close is within two ATR of level.
            six_hi=max(float(x[2]) for x in m[-7:-1])
            dist_atr=(prior_high-close)/a
            if six_hi>=prior_high-0.25*a and -0.5<=dist_atr<=2:
                state="WATCH"
                reason="H1_BEARISH_NEAR_M5_RESISTANCE_NO_CONFIRMED_REJECTION"
                setup={"prior_resistance":round(prior_high,10),
                       "last_m5_close":round(close,10),
                       "distance_from_resistance_atr":round(dist_atr,3),
                       "relative_quote_volume":round(rel_vol,3)}
        if state=="NONE":
            reason=("H1_NOT_BEARISH" if not h1_down else "NO_CONFIRMED_SWEEP")
        # Also record STRICT F signals in last six closed 5m bars; these are
        # historical observations, NEVER current entry recommendations.
        history=[]
        for i in range(max(25,len(m)-7),len(m)-1):
            v=candidate_f(m,h,i)
            if v:
                history.append({"at_utc":v["signal_at"],"sweep_level":round(v["level"],9)})
        liquidity="UNKNOWN"
        if turnover is not None:
            liquidity="HIGH" if turnover>=5_000_000 else "MEDIUM" if turnover>=2_000_000 else "LOW"
        return {
            "symbol":symbol,"state":state,"reason":reason,
            "closed_m5_utc":iso(anchor*1000),
            "closed_m5_price":round(close,10),
            "h1_down":h1_down,
            "turnover24_usdt":round(turnover,0) if turnover is not None else None,
            "liquidity":liquidity,"spread_pct":round(spread,4) if spread is not None else None,
            "rel_volume_last_m5":round(rel_vol,3),
            "setup":setup,"recent_f_history":history,
        }
    except Exception as e:
        return {"symbol":symbol,"state":"DATA_ERROR","reason":f"{type(e).__name__}: {str(e)[:180]}"}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--workers",type=int,default=7)
    parser.add_argument("--max-symbols",type=int,default=0,
                        help="0 means ALL active USDT altcoins, no artificial cap")
    args=parser.parse_args()
    if not 1<=args.workers<=9:
        parser.error("workers must be 1..9 to respect public API rate limits")
    # Allow 12s for recent completed candle to propagate.
    now=int(datetime.now(timezone.utc).timestamp())
    anchor=((now-12)//300)*300
    collected_start=iso(now*1000)
    print("CENSUS_BEGIN "+json.dumps({
        "collection_started_utc":collected_start,
        "frozen_m5_close_utc":iso(anchor*1000),
        "frozen_last_h1_close_utc":iso((anchor-anchor%3600)*1000),
        "model":"F_sweep_rejection_UNCHANGED",
        "mode":"PAPER_ONLY_NO_ORDERS",
    }),flush=True)
    eligible,discarded,total=universe()
    eligible.sort(key=lambda t:t[0])
    if args.max_symbols:
        eligible=eligible[:args.max_symbols]
    print("CENSUS_UNIVERSE "+json.dumps({"contracts_total":total,
          "altcoin_usdt_active":len(eligible),"excluded":dict(discarded),
          "max_symbols":args.max_symbols}),flush=True)
    out=[]
    start=time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures=[pool.submit(evaluate_one,t,anchor) for t in eligible]
        for j,f in enumerate(concurrent.futures.as_completed(futures),1):
            out.append(f.result())
            if j%75==0:
                print("CENSUS_PROGRESS "+json.dumps({"processed":j,"total":len(eligible)}),flush=True)
    out.sort(key=lambda x:x["symbol"])
    status=Counter(x["state"] for x in out)
    sig=sorted([x for x in out if x["state"]=="SIGNAL_M5"],
               key=lambda x: (-(x.get("turnover24_usdt") or 0),-x["rel_volume_last_m5"]))
    watch=sorted([x for x in out if x["state"]=="WATCH"],
                 key=lambda x: (x["setup"]["distance_from_resistance_atr"],
                                -(x.get("turnover24_usdt") or 0)))
    recent=sorted([x for x in out if x.get("recent_f_history")],
                  key=lambda x: x["recent_f_history"][-1]["at_utc"],reverse=True)
    finished=int(datetime.now(timezone.utc).timestamp())
    result={
        "model":"F_sweep_rejection_UNCHANGED",
        "methodology":"H1 last closed below EMA20; M5 sweep high24 by .1ATR, close below resistance/open, wick >=40%, TR .8-3ATR, quote volume >=1.5x12 median, SL high+.1ATR, TP1.8R",
        "m5_candle_close_utc":iso(anchor*1000),
        "h1_last_close_utc":iso((anchor-anchor%3600)*1000),
        "start_utc":collected_start,"complete_utc":iso(finished*1000),
        "age_seconds_at_completion":finished-anchor,
        "elapsed_seconds":round(time.monotonic()-start,1),
        "total_contracts":total,"active_altcoin_usdt_contracts":len(eligible),
        "exclusions":dict(discarded),
        "counts":dict(status),
        "confirmed_last_closed_m5_all":sig,
        "watch_near_resistance_count":len(watch),
        "watch_top30":watch[:30],
        "recent_30m_F_signal_count":len(recent),
        "recent_30m_F_signal_top30":recent[:30],
        "data_errors":out and [x for x in out if x["state"]=="DATA_ERROR"][:30],
        "data_error_count":status["DATA_ERROR"],
        "risk":"These are research signals not execution offers. Funding, tick, minVol, margin, spread, slippage, orderbook and freshness remain unverified.",
        "fee_slippage_assumed_each_side":.0008,
        "historical_F_ROI_126d_at_1pct_risk_pct":-5.109,
        "execution_note":"At completion, if age_seconds_at_completion exceeds 300, this frozen cutoff is not current. Never use it as a live entry.",
    }
    print("CENSUS_RESULT "+json.dumps(result,ensure_ascii=False,sort_keys=True),flush=True)


if __name__=="__main__":
    main()
