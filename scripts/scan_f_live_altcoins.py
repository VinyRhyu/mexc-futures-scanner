"""One-off MEXC futures altcoin market sweep using F (false resistance breakout).

Isolated research snapshot. Never places orders, touches Telegram, or mutates
the production scanner. Only CLOSED M5/H1 bars are used for decisions.
"""
from __future__ import annotations

import argparse
import json
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from statistics import median
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from scripts.audit_confluence_v3 import (
    candidate_f, atr_before, h1_bias_below_ema_at, FIVE_MS, HOUR_MS,
)
from scripts.audit_confluence_pilot import Parameters

BASE = "https://api.mexc.com"
MIN_USDT_VOLUME = 2_000_000
PRIORITY_USDT_VOLUME = 5_000_000
MAX_SPREAD_PCT = 0.25
THROTTLE_SEC = 0.23  # <= 5 public requests/sec, incl. retries
LOCK = threading.Lock()
LAST_START = [0.0]


def iso(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat()


def get_json(path, query=None):
    url = BASE + path + ("?" + urlencode(query) if query else "")
    exc = None
    for attempt in range(3):
        with LOCK:
            delta = time.monotonic() - LAST_START[0]
            if delta < THROTTLE_SEC:
                time.sleep(THROTTLE_SEC - delta)
            LAST_START[0] = time.monotonic()
        try:
            with urlopen(Request(url, headers={"User-Agent":"MEXC-Paper-Replay/1.0"}),
                         timeout=12) as resp:
                payload = json.load(resp)
            if isinstance(payload,dict) and payload.get("success") and payload.get("code")==0:
                return payload["data"]
            raise ValueError(f"Exchange response code={payload.get('code') if isinstance(payload,dict) else 'unknown'}")
        except Exception as e:
            exc=e
            time.sleep(0.35*(attempt+1))
    raise RuntimeError(f"{path}: {type(exc).__name__}: {str(exc)[:150]}")


def market():
    details = None
    errors = []
    for path in ("/api/v1/contract/detail/country", "/api/v1/contract/detail"):
        try:
            details = get_json(path)
            break
        except Exception as e:
            errors.append(str(e))
    if details is None:
        raise RuntimeError("Contracts endpoint unavailable: " + "; ".join(errors))
    if isinstance(details,dict):
        details = [details]
    tickers = get_json("/api/v1/contract/ticker")
    if isinstance(tickers,dict):
        tickers = [tickers]
    ticker_map = {x["symbol"]: x for x in tickers if isinstance(x,dict) and x.get("symbol")}
    contracts = {}
    ignored = {"BTC": "bitcoin", "USDC":"stablecoin", "USDT":"stablecoin",
               "FDUSD":"stablecoin", "USDE":"stablecoin", "DAI":"stablecoin",
               "TUSD":"stablecoin", "USDD":"stablecoin"}
    for x in details:
        sym=x.get("symbol","")
        if not sym.endswith("_USDT"):
            continue
        base=sym[:-5]
        if base in ignored:
            continue
        if x.get("state")!=0 or x.get("type",1)==2 or x.get("preMarket"):
            continue
        if x.get("quoteCoin","USDT")!="USDT":
            continue
        if x.get("futureType",1)!=1:
            continue
        contracts[sym]=x
    return contracts,ticker_map


def rows(symbol,interval,first,last):
    expected=list(range(first,last,300 if interval=="Min5" else 3600))
    payload=get_json("/api/v1/contract/kline/"+symbol,
                     {"interval":interval,"start":first,"end":last-(300 if interval=="Min5" else 3600)})
    keys=["time","open","high","low","close","vol","amount"]
    if not isinstance(payload,dict) or any(k not in payload for k in keys):
        raise ValueError("missing OHLCV fields")
    if len({len(payload[k]) for k in keys})!=1:
        raise ValueError("inconsistent OHLCV columns")
    out={}
    for vals in zip(*(payload[k] for k in keys)):
        stamp=int(vals[0])
        if stamp in out:
            raise ValueError("duplicate bars")
        if any(v is None for v in vals):
            raise ValueError("null candle")
        out[stamp]=[stamp*1000,*[float(v) for v in vals[1:]]]
    if sorted(out)!=expected:
        raise ValueError(f"historical gap: {len(out)}/{len(expected)} bars")
    data=[out[t] for t in expected]
    if any(r[2]<max(r[1],r[4]) or r[3]>min(r[1],r[4])
           or not all(math.isfinite(y) for y in r[1:]) for r in data):
        raise ValueError("invalid numeric OHLC")
    return data


def scan_contract(symbol, details, ticker, end_m5, end_h1, started_ms):
    amount=float(ticker.get("amount24") or 0)
    bid=float(ticker.get("bid1") or 0)
    ask=float(ticker.get("ask1") or 0)
    last=float(ticker.get("lastPrice") or 0)
    if last<=0 or bid<=0 or ask<=0 or ask<bid:
        raise ValueError("invalid bid/ask/last")
    spread=100*(ask-bid)/((ask+bid)/2)
    m5=rows(symbol,"Min5",end_m5-78*300,end_m5)
    h1=rows(symbol,"Min60",end_h1-48*3600,end_h1)
    i=len(m5)-1
    confirmed=[]
    current=candidate_f(m5,h1,i)
    # Also capture F triggers from the preceding 2 closed M5 bars,
    # but NEVER present them as tradeable right now.
    for j in (i-2,i-1,i):
        c=candidate_f(m5,h1,j)
        if not c:
            continue
        entry_reference=bid
        stop=c["stop_raw"]
        if stop<=entry_reference:
            status="INVALIDADO_PRECO"
            rr_net=None; tp=None
        else:
            risk=stop-entry_reference
            tp=entry_reference-1.8*risk
            cost=entry_reference*.0016
            rr_net=(1.8*risk-cost)/(risk+cost)
            status="GATILHO_RECENTE" if j==i else "HISTORICO_NAO_ENTRAR"
            if rr_net<1.2:
                status="RR_LIQ_INSUFICIENTE"
            if spread>MAX_SPREAD_PCT:
                status="SPREAD_ALTO"
        confirmed.append({
            "signal_at_utc":iso(c["signal_ms"]),
            "age_at_snapshot_sec":round((started_ms-c["signal_ms"])/1000),
            "status":status,
            "signal_candle_close":m5[j][4],
            "last_price":last,
            "bid1":bid,"ask1":ask,
            "entry_reference_not_fill":round(entry_reference,12),
            "stop":round(stop,12),"target_if_enter_now":round(tp,12) if tp else None,
            "rr_net_if_enter_now":round(rr_net,3) if rr_net is not None else None,
            "relative_volume":round(c["volume_ratio"],3),
            "spread_pct":round(spread,4),
            "volume_24h_usdt":round(amount),
            "note":"Model F signal uses closed M5. Entry/SL/TP at this moment not executed."
        })
    atr=atr_before(m5,i)
    resistance=max(float(x[2]) for x in m5[i-24:i])
    volume_base=median(float(x[6]) for x in m5[i-12:i])
    rel_vol=float(m5[i][6])/max(volume_base,1e-12)
    bias=h1_bias_below_ema_at(h1,m5[i][0]+FIVE_MS)
    distance_atr=(resistance-float(m5[i][4]))/atr if atr else None
    # Preparation is NOT a confirmed F signal. Need new sweep and rejection.
    preparing=(bias and current is None and atr>0 and
               -0.35 <= distance_atr <= 0.75 and spread <= MAX_SPREAD_PCT)
    return {
        "symbol":symbol,"market_state":"TECHNICAL_SCAN_OK",
        "24h_usdt":round(amount), "last_price":last,
        "spread_pct":round(spread,4),"H1_below_ema20":bias,
        "M5_closed_at_utc":iso(m5[i][0]+FIVE_MS),
        "resistance_prior_24xM5":round(resistance,12),
        "atr_14_M5":round(atr,12),"dist_to_resistance_atr":round(distance_atr,3),
        "last_M5_relative_volume":round(rel_vol,3),
        "preparation":preparing,"confirmed_F":confirmed,
        "min_qty_contracts":details.get("minVol"),
        "contract_size":details.get("contractSize"),
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--min-amount",type=float,default=MIN_USDT_VOLUME)
    p.add_argument("--max-workers",type=int,default=6)
    args=p.parse_args()
    if not 1<=args.max_workers<=8:
        p.error("workers 1..8")
    now=int(time.time())
    started_ms=now*1000
    end5=now//300*300
    end1=now//3600*3600
    print("LIVE_F_SNAPSHOT_CONFIG "+json.dumps({
        "snapshot_utc":iso(started_ms),
        "latest_closed_M5_utc":iso(end5*1000),
        "latest_closed_H1_utc":iso(end1*1000),
        "min_24h_USDT_volume":args.min_amount,
        "priority_24h_USDT_volume":PRIORITY_USDT_VOLUME,
        "max_spread_pct":MAX_SPREAD_PCT,
        "strategy":"F_sweep_rejection (SHORT only)",
        "paper_only":True,"source":"MEXC contract ticker/detail and 5m/1h klines"
    }),flush=True)
    info,tickers=market()
    eligible=[]
    counts={"listed_active_altcoin_usdt":len(info), "no_ticker":0,
            "below_min_turnover":0, "eligible":0}
    for sym,dt in info.items():
        t=tickers.get(sym)
        if not t:
            counts["no_ticker"]+=1
            continue
        amount=float(t.get("amount24") or 0)
        if amount<args.min_amount:
            counts["below_min_turnover"]+=1
            continue
        eligible.append((sym,dt,t))
    eligible.sort(key=lambda x:-float(x[2].get("amount24") or 0))
    counts["eligible"]=len(eligible)
    print("LIVE_F_UNIVERSE "+json.dumps({**counts,
       "definition":"Every active USDT perpetual altcoin (ex-BTC and major stablecoins) discovered, all with >= minimum turnover scanned; below-min reported as excluded",
       "sample_symbols":[x[0] for x in eligible[:15]]}),flush=True)
    scanned=[]; errors=[]
    with ThreadPoolExecutor(max_workers=args.max_workers) as ex:
        futures={ex.submit(scan_contract,sym,detail,t,end5,end1,started_ms):sym for sym,detail,t in eligible}
        for fut in as_completed(futures):
            sym=futures[fut]
            try:
                scanned.append(fut.result())
            except Exception as e:
                errors.append({"symbol":sym,"error":f"{type(e).__name__}: {str(e)[:145]}"})
    scan_end_ms=int(time.time()*1000)
    active=[]
    for x in scanned:
        for s in x["confirmed_F"]:
            active.append({"symbol":x["symbol"],**s})
    active.sort(key=lambda x:(x["status"]!="GATILHO_RECENTE",-x["relative_volume"]))
    preparing=[x for x in scanned if x["preparation"]]
    preparing.sort(key=lambda x:(abs(x["dist_to_resistance_atr"]),-x["24h_usdt"]))
    # At this point current "active" signal may have aged significantly.
    # Invalidate actionable classification if over 120s old.
    for s in active:
        s["age_at_report_sec"]=round((scan_end_ms-int(datetime.fromisoformat(
            s["signal_at_utc"]).timestamp()*1000))/1000)
        if s["status"]=="GATILHO_RECENTE" and s["age_at_report_sec"]>120:
            s["status"]="ATRASADO_NAO_ENTRAR"
    report={
      "asof_scan_start_utc":iso(started_ms), "finished_utc":iso(scan_end_ms),
      "M5_closed_snapshot_utc":iso(end5*1000),
      "universe":counts, "scanned_ok":len(scanned),
      "coverage_errors":len(errors), "errors":errors[:60],
      "confirmed_F_all_recent":active,
      "actionable_F_not_expired":[x for x in active if x["status"]=="GATILHO_RECENTE"],
      "preparing_count":len(preparing),
      "preparing_top20":preparing[:20],
      "liquid_scanned_top10":sorted(
          scanned,key=lambda x:-x["24h_usdt"])[:10],
      "note":"All signals/levels are analytical, not orders; no trade recommended. Scans are an as-of timestamp, not continuous live monitoring. Missing feeds not treated as no signals."
    }
    print("LIVE_F_SUMMARY "+json.dumps(report,ensure_ascii=False,separators=(",",":")),flush=True)


if __name__=="__main__":
    main()
