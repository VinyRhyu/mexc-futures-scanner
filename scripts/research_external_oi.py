"""V6c: public Bybit OI coverage; no production use or orders."""
from __future__ import annotations
import argparse,json,time,urllib.request,urllib.parse,urllib.error
from pathlib import Path
from mexc_scanner.models import D,seconds
from scripts.research_microstructure_coverage import MATCH_LEFT,END,STEP,save,coverage
from scripts.research_pre_breakout_coverage import SYMBOLS

HOST="https://api.bybit.com"
LEFT=MATCH_LEFT-86400
WINDOW=180*STEP

def get(path,params):
    if path!="/v5/market/open-interest":
        raise ValueError("only public OI")
    url=HOST+path+"?"+urllib.parse.urlencode(params)
    time.sleep(.25)
    req=urllib.request.Request(url,headers={"Accept":"application/json","User-Agent":"scanner-research/0.1"},method="GET")
    with urllib.request.urlopen(req,timeout=15) as r:
        raw=r.read(2_000_001)
    if len(raw)>2_000_000:
        raise ValueError("response too large")
    p=json.loads(raw)
    if p.get("retCode")!=0:
        raise ValueError("Bybit "+str(p.get("retCode"))+" "+str(p.get("retMsg"))[:100])
    return p["result"]

def parse(payload,symbol,left,right):
    if payload.get("symbol")!=symbol or payload.get("category")!="linear":
        raise ValueError("instrument mismatch")
    rows={}
    for v in payload["list"]:
        t=seconds(v["timestamp"])
        if not left<=t<right:
            continue
        x=D(v["openInterest"])
        if t%STEP or not x.is_finite() or x<=0:
            raise ValueError("invalid OI row")
        row=str(x)
        if t in rows and rows[t]!=row:
            raise ValueError("conflicting OI duplicate")
        rows[t]=row
    return rows

def collect(fetch,symbol):
    rows={};errors=[];consecutive=0;requests=0
    for left in range(LEFT,END,WINDOW):
        right=min(END,left+WINDOW)
        try:
            p=fetch("/v5/market/open-interest",{"category":"linear","symbol":symbol,"intervalTime":"5min",
                     "startTime":left*1000,"endTime":right*1000-1,"limit":200})
            requests+=1
            b=parse(p,symbol,left,right)
            # 180 expected rows < limit; do not assume complete when pagination or gaps arise.
            rows.update(b);consecutive=0
        except Exception as e:
            errors.append({"left":left,"right":right,"error":type(e).__name__+": "+str(e)[:200]})
            consecutive+=1
            if isinstance(e,urllib.error.HTTPError) and e.code in (401,403,451):
                break
            if consecutive>=3:
                break
    return rows,{"requested":coverage(rows,LEFT,END),"matched":coverage(rows,MATCH_LEFT,END),
                 "successful_requests":requests,"errors":errors}

def run(output):
    output.mkdir(parents=True,exist_ok=True)
    report={"type":"V6C_BYBIT_OI_COVERAGE","source":HOST,"matched":[MATCH_LEFT,END],"symbols":{},
            "limitations":["Exact USDT linear symbol mappings only; listing/instrument identity and permissions must be verified before model use.",
                           "Open interest is Bybit-specific and not MEXC OI; raw absolute levels not comparable across exchanges.",
                           "Archive observation timestamps do not prove publication time; future use requires conservative lag and live latency audit.",
                           "No bypass of access restrictions, no keys, no trading, no PRD."]}
    for mexc in SYMBOLS:
        symbol=mexc.replace("_","")
        rows,meta=collect(get,symbol)
        report["symbols"][mexc]={"external_symbol":symbol,**meta,**save(output/(symbol+"-oi.json.gz"),rows)}
        print(json.dumps({"symbol":symbol,"matched":meta["matched"],"errors":meta["errors"][:2]}),flush=True)
    (output/"summary.json").write_text(json.dumps(report,indent=2,allow_nan=False))
    print(json.dumps(report,indent=2,allow_nan=False),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--output",type=Path,required=True)
    run(p.parse_args().output)
