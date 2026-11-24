"""V6a: public MEXC source coverage pilot, no orders or signals."""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
import time
from decimal import Decimal
from pathlib import Path
from mexc_scanner.mexc import MexcClient
from mexc_scanner.models import D,seconds
from scripts.research_pre_breakout_coverage import SYMBOLS,utc_date

START=utc_date("2026-09-25")
END=utc_date("2026-11-24")
MATCH_START=1792864860
STEP=300
MATCH_LEFT=((MATCH_START+STEP-1)//STEP)*STEP
MAX_PAGES=10
PREFIX="/api/v1/contract/"

def safe(call):
    try:
        return {"ok":True,"data":call()}
    except Exception as e:
        return {"ok":False,"error":type(e).__name__+": "+str(e)[:200]}

def save(path,value):
    data=json.dumps(value,default=str,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
    path.write_bytes(gzip.compress(data,mtime=0))
    return {"file":path.name,"sha256_uncompressed":hashlib.sha256(data).hexdigest()}

def price_rows(payload,left,right):
    keys=("time","open","high","low","close")
    if not isinstance(payload,dict) or any(k not in payload for k in keys) or len({len(payload[k]) for k in keys})!=1:
        raise ValueError("bad kline arrays")
    rows={}
    for ts,o,h,l,c in zip(*(payload[k] for k in keys)):
        t=seconds(ts)
        if not left<=t<right:
            continue
        vals=[D(v) for v in (o,h,l,c)]
        if t%STEP or not all(v.is_finite() and v>0 for v in vals) or vals[2]>min(vals[0],vals[3]) or vals[1]<max(vals[0],vals[3]):
            raise ValueError("invalid candle")
        v=[str(x) for x in vals]
        if t in rows and rows[t]!=v:
            raise ValueError("conflicting candle")
        rows[t]=v
    return rows

def coverage(ts,left,right):
    expected=set(range(left,right,STEP))
    found=expected & set(ts)
    missing=sorted(expected-found)
    return {"expected":len(expected),"observed":len(found),"pct":100*len(found)/len(expected),
            "first":min(found,default=None),"last":max(found,default=None),"missing":len(missing)}

def history_prices(client,symbol,kind):
    rows={}
    errors=[]
    for left in range(START,END,1800*STEP):
        right=min(END,left+1800*STEP)
        try:
            raw=client._get(PREFIX+"kline/"+kind+"/"+client._symbol(symbol),
                            {"interval":"Min5","start":left,"end":right-1})
            rows.update(price_rows(raw,left,right))
        except Exception as exc:
            errors.append({"left":left,"right":right,"error":str(exc)[:200]})
    return rows,{"requested":coverage(rows,START,END),"matched":coverage(rows,MATCH_LEFT,END),"errors":errors}

def funding_history(client,symbol,now):
    rows={}
    pages=[]
    errors=[]
    last_min=None
    stop="page_cap"
    for page in range(1,MAX_PAGES+1):
        try:
            p=client._get(PREFIX+"funding_rate/history",{"symbol":symbol,"page_num":page,"page_size":1000})
            batch=p["resultList"]
            if not isinstance(batch,list):
                raise ValueError("bad resultList")
            batch_times=[]
            staged={}
            for x in batch:
                if x["symbol"]!=symbol:
                    raise ValueError("symbol mismatch")
                t=seconds(x["settleTime"])
                rate=D(x["fundingRate"])
                cycle=int(x["collectCycle"]) if x.get("collectCycle") is not None else None
                if t>now or not rate.is_finite() or (cycle is not None and cycle<=0):
                    raise ValueError("invalid settled funding")
                row={"rate":str(rate),"cycle_hours":cycle}
                if (t in staged and staged[t]!=row) or (t in rows and rows[t]!=row):
                    raise ValueError("conflicting settlement")
                staged[t]=row
                batch_times.append(t)
            if batch_times!=sorted(batch_times,reverse=True) or (last_min is not None and batch_times and max(batch_times)>last_min):
                raise ValueError("nonchronological pagination")
            rows.update(staged)
            pages.append({"page":page,"n":len(batch),"total_pages":p.get("totalPage")})
            if not batch_times:
                stop="empty_page";break
            last_min=min(batch_times)
            if last_min<START:
                stop="prior_settlement_reached";break
            if page>=int(p["totalPage"]):
                stop="last_page";break
        except Exception as e:
            errors.append({"page":page,"error":str(e)[:200]})
            stop="error";break
    times=sorted(rows)
    inside=[t for t in times if MATCH_LEFT<=t<END]
    prior=[t for t in times if t<MATCH_LEFT]
    gaps=[]
    # Compare consecutive settled timestamps to cycle recorded at later settlement;
    # a mismatch is flagged, not automatically filled or called a missing settlement.
    relevant=[t for t in times if MATCH_LEFT<=t<END]
    if prior:
        relevant=[prior[-1]]+relevant
    for a,b in zip(relevant,relevant[1:]):
        cycle=rows[b]["cycle_hours"]
        if cycle is None or b-a!=cycle*3600:
            gaps.append({"previous":a,"current":b,"observed_seconds":b-a,"cycle_hours":cycle})
    return rows,{"pages":pages,"stop":stop,"errors":errors,"records":len(rows),
                 "first":min(times,default=None),"last":max(times,default=None),
                 "matched_settlements":len(inside),"prior_settlement":max(prior,default=None),
                 "last_matched_settlement":max(inside,default=None),"cycle_mismatches":gaps}

def recent_summary(payload):
    if not isinstance(payload,list):
        raise ValueError("expected deal list")
    ts=[seconds(x["t"]) for x in payload]
    return {"count":len(ts),"span_seconds":max(ts)-min(ts) if ts else None,
            "side_field_present":all(x.get("T") in (1,2) for x in payload),
            "unique_tuple_count":len({json.dumps(x,default=str,sort_keys=True) for x in payload}),
            "complete_history":False}

def run(client,output):
    output.mkdir(parents=True,exist_ok=True)
    now=client.server_time()
    if now<END:
        raise ValueError("unclosed target dates")
    report={"type":"V6A_PUBLIC_SOURCE_COVERAGE","server_time":now,"requested":[START,END],
            "matched_min5":[MATCH_LEFT,END],"symbols":{},
            "limitations":["Fixed six-symbol pilot, not 52-symbol validation.",
            "Min5 historical fair/index coverage, not yet joined to trade candle dataset.",
            "Settled funding only known after settlement; not future predicted funding.",
            "Recent trade/depth samples and current OI are not historical series.",
            "No documented long-window public OI or liquidation archive established by this audit.",
            "No continuous WebSocket collector, signals, orders, credentials or PRD changes."]}
    for symbol in SYMBOLS:
        a={}
        price_sets={}
        for kind in ("index_price","fair_price"):
            rows,summary=history_prices(client,symbol,kind)
            price_sets[kind]=set(rows)
            a[kind]={**summary,**save(output/(symbol+"-"+kind+".json.gz"),rows)}
        a["joint_matched"]=coverage(price_sets["index_price"] & price_sets["fair_price"],MATCH_LEFT,END)
        rows,summary=funding_history(client,symbol,now)
        a["funding"]={**summary,**save(output/(symbol+"-funding.json.gz"),rows)}
        for name,call in (("ticker",lambda:client.ticker(symbol)),
                          ("recent_deals",lambda:client._get(PREFIX+"deals/"+client._symbol(symbol),{"limit":100})),
                          ("depth",lambda:client.depth(symbol)),
                          ("depth_commits",lambda:client._get(PREFIX+"depth_commits/"+client._symbol(symbol)+"/20"))):
            begin=time.time_ns()//1000000
            r=safe(call)
            received=time.time_ns()//1000000
            if r["ok"]:
                d=r["data"]
                summary=safe(lambda:recent_summary(d)) if name=="recent_deals" else {}
                r={"ok":True,"summary":summary,"fields":sorted(d) if isinstance(d,dict) else None,
                   "rows":len(d) if isinstance(d,list) else None,
                   **save(output/(symbol+"-"+name+".json.gz"),{"request_ms":begin,"received_ms":received,"data":d})}
                if name=="ticker":
                    r["oi_present"]=d.get("holdVol") is not None
                    r["exchange_timestamp"]=d.get("timestamp")
            a[name]={**r,"request_ms":begin,"received_ms":received}
        report["symbols"][symbol]=a
        print(json.dumps({"symbol":symbol,"joint_matched":a["joint_matched"],"funding_records":a["funding"]["matched_settlements"]}),flush=True)
    (output/"summary.json").write_text(json.dumps(report,indent=2,default=str,allow_nan=False))
    print(json.dumps(report,indent=2,default=str,allow_nan=False),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    run(MexcClient(),a.output)
