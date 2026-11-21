"""Live public-MEXC sweep/rejection research. Read-only, no Telegram or trades.

The F SHORT rule is experimental and had negative historical expectancy.
Current signals are observational only and are NEVER a recommendation to enter.
"""
from __future__ import annotations

import argparse
import json
import math
import time
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal

from mexc_scanner.mexc import MexcClient
from scripts.audit_confluence_extended import candles
from scripts.audit_confluence_v3 import (
    FIVE_MS, HOUR_MS, atr_before, candidate_f, h1_bias_below_ema_at, iso,
)

FIVE_SECONDS=300
HOUR_SECONDS=3600
SKIP_BASE={"BTC", "USDC", "USDT", "DAI", "FDUSD", "TUSD", "USDD", "PYUSD", "USDE", "USD1", "EUR", "EURC", "USTC", "XAU", "XAUT", "SILVER", "GOLD", "XAG", "PAXG", "USOIL", "UKOIL", "XPT", "XPD", "ALUMINUM", "ZINC", "COPPER", "WTI", "BRENT", "PLATINUM", "PALLADIUM"}


def now_iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


def filter_universe(contracts, tickers, minimum_turnover):
    quotes={q.get("symbol"):q for q in tickers if isinstance(q,dict)}
    eligible=[]
    reasons=Counter()
    for c in contracts:
        symbol=str(c.get("symbol",""))
        asset=str(c.get("baseCoin",""))
        try:
            active=int(c.get("state",-1))==0
            regular=(c.get("settleCoin")=="USDT" and c.get("quoteCoin")=="USDT"
                     and int(c.get("futureType",1))==1
                     and not c.get("preMarket",False)
                     and int(c.get("typeLabel",0) or 0) not in (1,2))
            turnover=float(quotes.get(symbol,{}).get("amount24") or 0)
        except (TypeError, ValueError):
            reasons["METADATA_INVALID"]+=1;continue
        if not active or not regular or not symbol.endswith("_USDT"):
            reasons["NON_USDT_PERP_OR_INACTIVE"]+=1
        elif asset.upper() in SKIP_BASE or not asset:
            reasons["BTC_STABLE_FIAT_EXCLUDED"]+=1
        elif symbol not in quotes:
            reasons["NO_TICKER"]+=1
        elif not math.isfinite(turnover) or turnover < minimum_turnover:
            reasons["LOW_24H_TURNOVER"]+=1
        else:
            eligible.append({"symbol":symbol,"turnover_24h":turnover,
                             "price":quotes[symbol].get("lastPrice"),
                             "ticker_time":quotes[symbol].get("timestamp")})
    eligible.sort(key=lambda x:(-x["turnover_24h"],x["symbol"]))
    return eligible,dict(reasons)


def check_symbol(meta, latest_m5_end, latest_h1_end):
    symbol=meta["symbol"]
    # Strict 80 closed H1 / 120 closed M5 candles. No unknown gaps accepted.
    hourly=candles(symbol,"Min60",latest_h1_end-80*3600,latest_h1_end)
    five=candles(symbol,"Min5",latest_m5_end-120*300,latest_m5_end)
    i=len(five)-1
    last=five[-1]
    decision_ms=last[0]+FIVE_MS
    if decision_ms != latest_m5_end*1000:
        raise ValueError("stale latest M5 candle")
    last_ema_down=h1_bias_below_ema_at(hourly,decision_ms)
    atr=atr_before(five,i)
    previous20=five[i-24:i]
    ceiling=max(c[2] for c in previous20)
    nearby_max=max(c[2] for c in five[i-6:i])
    relative=last[6]/max(1e-12,sorted(c[6] for c in five[i-12:i])[6])
    # Median of 12 points is mean of indices 5 and 6, as elsewhere.
    vols=sorted(c[6] for c in five[i-12:i])
    relative=last[6]/max(1e-12,(vols[5]+vols[6])/2)
    upper=last[2]-max(last[1],last[4])
    wick_ratio=upper/max(1e-12,last[2]-last[3])
    close_below_ceiling=last[4]<ceiling
    # Near a recent 2h resistance is an observational watchlist only.
    near=(last_ema_down and atr>0 and
          nearby_max >= ceiling-0.5*atr and
          close_below_ceiling and
          (ceiling-last[4]) <= max(1.2*atr, 0.003*ceiling))
    latest=candidate_f(five,hourly,i)
    recent=[]
    for k in range(max(25,i-5),i):
        signal=candidate_f(five,hourly,k)
        if signal:
            recent.append({"at":signal["signal_at"],"price_close":five[k][4],
                           "high":five[k][2],"relative_volume":round(signal["volume_ratio"],3),
                           "stop_if_entered_immediately":round(signal["stop_raw"],8),
                           "elapsed_minutes":int((decision_ms-signal["signal_ms"])/60000)})
    if latest:
        status="REJECTION_M5_CLOSED"
    elif recent:
        status="REJECTION_OLDER_NO_ENTRY"
    elif near:
        status="WATCH_RESISTANCE"
    else:
        status="NO_SETUP"
    reason=(
        "H1_NOT_BEARISH" if not last_ema_down else
        "NOT_NEAR_RESISTANCE" if not near else
        "REJECTION_OR_VOLUME_NOT_CONFIRMED"
    )
    return {
        "symbol":symbol,"status":status,"reason":reason,
        "turnover_24h":round(meta["turnover_24h"],2),
        "last_m5_at":iso(last[0]),"last_close":last[4],
        "reference_resistance":round(ceiling,8),
        "atr14_m5":round(atr,8),"relative_quote_volume":round(relative,3),
        "last_m5_upper_wick_fraction":round(wick_ratio,3),
        "h1_below_ema20":last_ema_down,
        "current_candle_F":({ "signal_at":latest["signal_at"],
              "stop_structural":round(latest["stop_raw"],8),
              "no_live_entry_price_guaranteed":True } if latest else None),
        "recent_F":recent,
        "no_live_execution":True
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--minimum-turnover",type=float,default=2_000_000)
    ap.add_argument("--limit",type=int,default=0,
                    help="0 = all eligible liquid contracts; nonzero is explicit limit")
    args=ap.parse_args()
    client=MexcClient()
    fetched=int(time.time())
    server_time=client.server_time()
    contracts=client.contracts()
    tickers=client.tickers()
    universe, exclusions=filter_universe(contracts,tickers,args.minimum_turnover)
    total_eligible=len(universe)
    if args.limit:
        universe=universe[:args.limit]
    # Completed, server-time confirmed M5; allow up to 60 seconds exchange propagation.
    latest_m5_end=((server_time-60)//FIVE_SECONDS)*FIVE_SECONDS
    latest_h1_end=(latest_m5_end//HOUR_SECONDS)*HOUR_SECONDS
    print("LIVE_F_UNIVERSE "+json.dumps({
        "server_utc":now_iso(server_time),
        "sample_collected_utc":now_iso(fetched),
        "m5_latest_closed_until":now_iso(latest_m5_end),
        "h1_latest_closed_until":now_iso(latest_h1_end),
        "contracts":len(contracts),"tickers":len(tickers),
        "eligible_all":total_eligible,"selected":len(universe),
        "minimum_turnover_usdt":args.minimum_turnover,
        "exclusion_counts":exclusions,
        "experimental_short_only":True},sort_keys=True),flush=True)
    selected=[]; errors=[]; counts=Counter()
    started=time.monotonic()
    for n,meta in enumerate(universe,1):
        try:
            row=check_symbol(meta,latest_m5_end,latest_h1_end)
            selected.append(row);counts[row["status"]]+=1
            if row["status"]!="NO_SETUP":
                print("LIVE_F_CANDIDATE "+json.dumps(row,sort_keys=True),flush=True)
        except Exception as exc:
            errors.append({"symbol":meta["symbol"],
                           "reason":f"{type(exc).__name__}: {str(exc)[:180]}"})
        if n%20==0 or n==len(universe):
            print(f"LIVE_F_PROGRESS {n}/{len(universe)} valid={len(selected)} "
                  f"failures={len(errors)} elapsed={time.monotonic()-started:.1f}s",
                  flush=True)
    if not selected:
        raise RuntimeError("Zero symbols with complete verified candles")
    report={
        "venue":"MEXC futures",
        "timestamp_utc":now_iso(server_time),
        "last_m5_close_utc":now_iso(latest_m5_end),
        "last_h1_close_utc":now_iso(latest_h1_end),
        "all_eligible_altcoins":total_eligible,
        "selected_altcoins":len(universe),
        "evaluated_valid":len(selected),
        "failed_data":len(errors),
        "failed_examples":errors[:25],
        "minimum_24h_turnover_usdt":args.minimum_turnover,
        "status_counts":dict(counts),
        "current_F": [r for r in selected if r["status"]=="REJECTION_M5_CLOSED"],
        "recent_F":[r for r in selected if r["status"]=="REJECTION_OLDER_NO_ENTRY"],
        "watch_resistance":sorted((r for r in selected if r["status"]=="WATCH_RESISTANCE"),
                       key=lambda r:(-r["turnover_24h"],r["symbol"]))[:45],
        "excluded_by_liquidity_or_contract_metadata":exclusions,
        "model":"F, SHORT false breakout 5m + bearish H1; negative ROI historical",
        "restriction":"Observational research only; no live trading signals or execution",
        "all_valid_symbols": [r["symbol"] for r in selected]
    }
    print("LIVE_F_RESULTS "+json.dumps(report,sort_keys=True),flush=True)
    if len(selected) < .9*len(universe):
        raise RuntimeError("Coverage less than 90%; no full universe claim")


if __name__=="__main__":
    main()
