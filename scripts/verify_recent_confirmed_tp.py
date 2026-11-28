"""Read-only MEXC M1 audit of the last delivered, financially confirmed ENTRY signals.

No order placement, paper wallet edits, production imports or historical tuning.
Checks target/stop touches AFTER Telegram delivery, and models an entry only when
the entry interval was touched before the original authorization expired.
"""
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import time

from mexc_scanner.models import D

SOURCE="https://contract.mexc.com"
HORIZON_SECONDS=4*3600
MAX_REQUEST_BARS=1200


def iso(ts):
    return datetime.fromtimestamp(ts,timezone.utc).isoformat()


def read_delivered(audit_dir: Path, asof: int, lookback_hours=24, max_signals=20):
    since=asof-int(lookback_hours)*3600
    queued={}
    delivered={}
    for path in sorted(audit_dir.glob("decisions-*.jsonl")):
        # The only state data we need: an append-only evidence record. Never
        # infer delivery from an ENTRY proposal that was only queued.
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row=json.loads(line)
                event=row.get("event")
                key=row.get("event_id")
                if not key:
                    continue
                if event=="entry_queued" and row.get("strategy")=="ROMPIMENTO_M1_VOLUME":
                    queued[key]=row
                elif event=="delivery_sent" and row.get("status")=="SENT":
                    delivered[key]=row
    eligible=[]
    for event_id,sent in delivered.items():
        if event_id not in queued:
            continue
        q=queued[event_id]
        if not (since<=int(sent["sent_at"])<=asof):
            continue
        if (q.get("variant")!="CONFIRMADA" or
                q.get("variant_status")!="VALIDA" or
                q.get("financial",{}).get("status")!="VIAVEL_SIMULADO"):
            continue
        if not all(k in q for k in ("symbol","side","target","stop","entry_low",
                                    "entry_high","expires_at","signal_at")):
            continue
        eligible.append(dict(
            event_id=event_id,
            plan_id=q["plan_id"],
            symbol=q["symbol"],side=q["side"],
            sent_at=int(sent["sent_at"]),
            quote_at=int(q["quote_at"]),
            signal_at=int(q["signal_at"]),
            expires_at=int(q["expires_at"]),
            entry_low=str(q["entry_low"]),entry_high=str(q["entry_high"]),
            target=str(q["target"]),stop=str(q["stop"]),
            leverage=q["financial"].get("leverage"),
            source_run_id=q.get("run_id"),delivery_run_id=sent.get("run_id"),
        ))
    eligible.sort(key=lambda x:(-x["sent_at"],x["event_id"]))
    return eligible[:max_signals]


def fetch_m1(symbol: str, start: int, end: int):
    """GET only historical last-traded OHLC; no credentials and no write."""
    candles={}
    for begin in range(start,end+1,MAX_REQUEST_BARS*60):
        finish=min(end,begin+(MAX_REQUEST_BARS-1)*60)
        url=f"{SOURCE}/api/v1/contract/kline/{symbol}?"+urlencode({
            "interval":"Min1","start":begin,"end":finish})
        req=Request(url,headers={"User-Agent":"MEXCScannerReadOnlyTPAudit/1.0",
                                 "Accept":"application/json"})
        error=None
        for retry in range(3):
            try:
                with urlopen(req,timeout=25) as response:
                    body=json.load(response)
                error=None
                break
            except (OSError,ValueError) as exc:
                error=f"{type(exc).__name__}: {str(exc)[:120]}"
                if retry<2:
                    time.sleep(retry+1)
        if error:
            raise RuntimeError(f"MEXC_API_ERROR {symbol}: {error}")
        if not isinstance(body,dict) or not body.get("success",False):
            raise RuntimeError(f"MEXC_SOURCE_REJECTED {symbol}: code={body.get('code') if isinstance(body,dict) else '?'}")
        data=body.get("data")
        if not isinstance(data,dict):
            raise RuntimeError(f"MEXC_SOURCE_INVALID {symbol}: missing data")
        t=data.get("time",[])
        fields=["open","high","low","close"]
        if not isinstance(t,list) or any(
                not isinstance(data.get(k),list) or len(data[k])!=len(t) for k in fields):
            raise RuntimeError(f"MEXC_SOURCE_INVALID {symbol}: incomplete OHLC arrays")
        for i,ts in enumerate(t):
            ts=int(ts)
            if ts%60 or not start<=ts<=end:
                raise RuntimeError(f"MEXC_SOURCE_INVALID {symbol}: timestamp {ts}")
            o,h,l,c=(D(data[k][i]) for k in fields)
            if l<=0 or not l<=min(o,c)<=max(o,c)<=h:
                raise RuntimeError(f"MEXC_SOURCE_INVALID {symbol}: invalid OHLC {ts}")
            item={"ts":ts,"open":o,"high":h,"low":l,"close":c}
            if ts in candles and candles[ts]!=item:
                raise RuntimeError(f"MEXC_SOURCE_CONFLICT {symbol}: {ts}")
            candles[ts]=item
    return candles


def outcome(event:dict, candles:dict, asof:int):
    sent=event["sent_at"]
    start=((sent+59)//60)*60    # NEVER use any part of the delivery minute
    last_closed=(asof//60)*60-60
    max_until=min(sent+HORIZON_SECONDS,last_closed)
    until=(max_until//60)*60
    levels={k:D(event[k]) for k in ("entry_low","entry_high","target","stop")}
    side=event["side"]
    if (side not in ("LONG","SHORT") or
            not levels["entry_low"]<=levels["entry_high"] or
            min(levels.values())<=0):
        raise ValueError("Invalid signal geometry")
    if not (levels["stop"]<levels["entry_low"]<=levels["entry_high"]<levels["target"]
            if side=="LONG" else
            levels["target"]<levels["entry_low"]<=levels["entry_high"]<levels["stop"]):
        raise ValueError("Invalid directional signal geometry")

    base={**event,"first_eligible_m1_utc":iso(start),
          "evaluated_until_utc":iso(until) if until>=start else None,
          "horizon_complete":until>=((sent+HORIZON_SECONDS)//60)*60,
          "source":"MEXC public futures last-price Min1 OHLC; not mark/fair price",
          "entry_touched_before_expiry":False,
          "first_entry_touch_utc":None,
          "tp_touched_after_delivery":False,"first_tp_touch_utc":None,
          "sl_touched_after_delivery":False,"first_sl_touch_utc":None,
          "conservative_4h_outcome":"AWAITING_CLOSED_M1",
          "caveat":"No manual fill recorded, price path inside 1m candle unknown"}

    if until<start:
        return base
    expected=list(range(start,until+1,60))
    missing=[ts for ts in expected if ts not in candles]
    if missing:
        base["conservative_4h_outcome"]="HISTORY_INCOMPLETE"
        base["missing_minutes"]=len(missing)
        base["first_missing_utc"]=iso(missing[0])
        return base

    took_entry=False
    for ts in expected:
        c=candles[ts]
        touched_tp=c["high"]>=levels["target"] if side=="LONG" else c["low"]<=levels["target"]
        touched_sl=c["low"]<=levels["stop"] if side=="LONG" else c["high"]>=levels["stop"]
        if touched_tp and not base["tp_touched_after_delivery"]:
            base["tp_touched_after_delivery"]=True
            base["first_tp_touch_utc"]=iso(ts)
        if touched_sl and not base["sl_touched_after_delivery"]:
            base["sl_touched_after_delivery"]=True
            base["first_sl_touch_utc"]=iso(ts)

        if not took_entry and ts<int(event["expires_at"]):
            if c["low"]<=levels["entry_high"] and c["high"]>=levels["entry_low"]:
                took_entry=True
                base["entry_touched_before_expiry"]=True
                base["first_entry_touch_utc"]=iso(ts)
                # A same-minute entry and TP/SL cannot be causally sequenced.
                if touched_tp or touched_sl:
                    base["conservative_4h_outcome"]="AMBIGUOUS_ENTRY_MINUTE"
                    break
        if took_entry:
            if touched_tp and touched_sl:
                base["conservative_4h_outcome"]="AMBIGUOUS_TP_AND_SL_SAME_M1"
                break
            if touched_sl:
                base["conservative_4h_outcome"]="SL_FIRST"
                break
            if touched_tp:
                base["conservative_4h_outcome"]="TP_FIRST"
                break
    else:
        if not took_entry:
            base["conservative_4h_outcome"]="NO_ENTRY_ZONE_TOUCH_BEFORE_EXPIRY"
        elif base["horizon_complete"]:
            base["conservative_4h_outcome"]="NO_TP_OR_SL_WITHIN_4H"
        else:
            base["conservative_4h_outcome"]="OPEN_UNTIL_CUTOFF"

    return base


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--audit-dir",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--lookback-hours",type=int,default=24)
    p.add_argument("--max-signals",type=int,default=20)
    p.add_argument("--asof-utc",default=None)
    args=p.parse_args()
    asof=(int(datetime.fromisoformat(args.asof_utc.replace("Z","+00:00")).timestamp())
          if args.asof_utc else int(datetime.now(timezone.utc).timestamp()))
    events=read_delivered(args.audit_dir,asof,args.lookback_hours,args.max_signals)
    args.output.mkdir(parents=True,exist_ok=True)
    groups=defaultdict(list)
    for e in events:
        groups[e["symbol"]].append(e)
    by_symbol={}
    errors={}
    for symbol,items in groups.items():
        start=min(((e["sent_at"]+59)//60)*60 for e in items)
        end=max(min(e["sent_at"]+HORIZON_SECONDS,(asof//60)*60-60) for e in items)
        if end<start:
            by_symbol[symbol]={}
            continue
        try:
            by_symbol[symbol]=fetch_m1(symbol,start,(end//60)*60)
        except Exception as exc:
            # Do not silently convert missing historical data into a loss.
            errors[symbol]=f"{type(exc).__name__}: {str(exc)[:180]}"
            by_symbol[symbol]={}
    results=[]
    for e in events:
        try:
            result=outcome(e,by_symbol[e["symbol"]],asof)
            if e["symbol"] in errors:
                result["conservative_4h_outcome"]="SOURCE_ERROR"
                result["source_error"]=errors[e["symbol"]]
        except Exception as exc:
            result={**e,"conservative_4h_outcome":"INVALID_INPUT",
                    "error":f"{type(exc).__name__}: {str(exc)[:180]}"}
        results.append(result)
    counts={}
    for r in results:
        k=r["conservative_4h_outcome"]
        counts[k]=counts.get(k,0)+1
    report={
        "asof_utc":iso(asof),
        "lookback_hours":args.lookback_hours,
        "max_recent_delivered_signals":args.max_signals,
        "delivered_confirmed_signals":len(events),
        "distinct_symbols":len(groups),
        "outcomes":counts,
        "api_errors":errors,
        "conservatism":(
            "Delivery minute excluded; first full M1 after Telegram sent. "
            "Entry touched only when inside the original authorization expiry. "
            "If entry and TP or SL touch in the same M1, result is ambiguous. "
            "After entry, first TP or SL touch wins, both in same candle ambiguous. "
            "4h horizon; pending signals may be unfinished. "
            "M1 last-price touches do not prove real fills, actual account PnL, "
            "fair-price stops or manual order execution."
        ),
        "signals":results,
    }
    (args.output/"confirmed_tp_report.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    cols=["symbol","side","sent_at","entry_low","entry_high","target","stop",
          "leverage","entry_touched_before_expiry","first_entry_touch_utc",
          "tp_touched_after_delivery","first_tp_touch_utc",
          "sl_touched_after_delivery","first_sl_touch_utc",
          "conservative_4h_outcome","horizon_complete","plan_id","event_id"]
    with (args.output/"confirmed_tp_signals.csv").open(
            "w",encoding="utf-8-sig",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=cols,extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)
    print("CONFIRMED_TP_SUMMARY="+json.dumps({
        "asof":iso(asof),"count":len(events),"symbols":list(groups),
        "outcomes":counts,"api_errors":errors,
        "signals":[{k:r.get(k) for k in ("symbol","side","sent_at",
          "entry_low","entry_high","target","stop",
          "entry_touched_before_expiry","tp_touched_after_delivery",
          "first_tp_touch_utc","sl_touched_after_delivery","first_sl_touch_utc",
          "conservative_4h_outcome","horizon_complete")} for r in results]
    },ensure_ascii=False),flush=True)


if __name__=="__main__":
    main()
