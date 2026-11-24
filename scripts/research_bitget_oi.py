"""V6e: Bitget public OI endpoint coverage, independent source."""
from __future__ import annotations
import argparse,json,time,urllib.request,urllib.parse,urllib.error
from pathlib import Path
from mexc_scanner.models import D,seconds
from scripts.research_microstructure_coverage import MATCH_LEFT,END,save
from scripts.research_pre_breakout_coverage import SYMBOLS

HOST="https://api.bitget.com"
PATH="/api/v3/market/open-interest-history"
PERIODS={"5m":300,"1h":3600}

def get(symbol,period):
    url=HOST+PATH+"?"+urllib.parse.urlencode({"symbol":symbol,"period":period})
    time.sleep(.25)
    req=urllib.request.Request(url,headers={"Accept":"application/json","User-Agent":"scanner-research/0.1"},method="GET")
    with urllib.request.urlopen(req,timeout=20) as r:
        raw=r.read(5_000_001)
    if len(raw)>5_000_000:
        raise ValueError("response too large")
    p=json.loads(raw)
    if p.get("code")!="00000":
        raise ValueError("Bitget "+str(p.get("code"))+" "+str(p.get("msg"))[:100])
    return p

def parse(p,symbol,period):
    step=PERIODS[period]
    rows={}
    for r in p["data"]["list"]:
        if r["symbol"]!=symbol:
            raise ValueError("symbol mismatch")
        ts=seconds(r["timestamp"])
        v=D(r["openInterest"])
        if ts%step or not v.is_finite() or v<=0:
            raise ValueError("invalid OI")
        row={"open_interest_base":str(v)}
        for name in ("oneSideOpenInterest","openInterestValue"):
            if name in r:
                x=D(r[name])
                if not x.is_finite() or x<0:
                    raise ValueError("invalid optional OI")
                row[name]=str(x)
        if ts in rows and rows[ts]!=row:
            raise ValueError("conflicting duplicate")
        rows[ts]=row
    return rows

def coverage(rows,step,left=MATCH_LEFT,right=END):
    # End timestamps; exclude settlement/observation at right boundary.
    left=(left+step-1)//step*step
    expected=set(range(left,right,step))
    got=expected & set(rows)
    return {"expected":len(expected),"matched":len(got),"pct":100*len(got)/len(expected),
            "first_matched":min(got,default=None),"last_matched":max(got,default=None),
            "returned":len(rows),"first_returned":min(rows,default=None),"last_returned":max(rows,default=None)}

def run(output):
    output.mkdir(parents=True,exist_ok=True)
    report={"type":"V6E_BITGET_OI_COVERAGE","source":HOST+PATH,"matched":[MATCH_LEFT,END],
            "symbols":{},"limitations":["Only documented symbol/period parameters; no unsupported historical pagination.",
            "Timestamp is interval end per documentation. Archive publication latency not verified.",
            "OI base coin, exchange-specific; contract identity and permitted use must be verified before integration.",
            "No API keys, no bypass of blocks, no trading or PRD."]}
    for mexc in SYMBOLS:
        symbol=mexc.replace("_","")
        result={}
        for period,step in PERIODS.items():
            start=time.time_ns()//1000000
            try:
                payload=get(symbol,period)
                rows=parse(payload,symbol,period)
                result[period]={"ok":True,"coverage":coverage(rows,step),
                    "request_time":payload.get("requestTime"),**save(output/(symbol+"-"+period+".json.gz"),rows)}
            except Exception as e:
                result[period]={"ok":False,"error":type(e).__name__+": "+str(e)[:200]}
            result[period].update({"request_ms":start,"received_ms":time.time_ns()//1000000})
        report["symbols"][mexc]=result
        print(json.dumps({"symbol":mexc,"result":result}),flush=True)
    (output/"summary.json").write_text(json.dumps(report,indent=2,allow_nan=False))
    print(json.dumps(report,indent=2,allow_nan=False),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--output",type=Path,required=True)
    run(p.parse_args().output)
