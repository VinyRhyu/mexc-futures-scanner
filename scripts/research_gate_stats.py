"""V6f: public Gate perpetual statistics coverage, not trading."""
from __future__ import annotations
import argparse,json,time,urllib.request,urllib.parse,urllib.error
from collections import Counter
from pathlib import Path
from mexc_scanner.models import D,seconds
from scripts.research_microstructure_coverage import MATCH_LEFT,END,STEP,save
from scripts.research_pre_breakout_coverage import SYMBOLS

HOST="https://api.gateio.ws"
PREFIX="/api/v4/futures/usdt/"
LEFT=MATCH_LEFT-86400
LIMIT=100
FIELDS=("open_interest","open_interest_usd","lsr_taker","lsr_account","top_lsr_size",
        "top_lsr_account","long_liq_size","short_liq_size","long_liq_usd","short_liq_usd",
        "long_liq_usd_new","short_liq_usd_new","long_taker_size","short_taker_size","mark_price")

def get(path,params):
    if path not in ("contract_stats","contracts"):
        raise ValueError("public endpoint only")
    url=HOST+PREFIX+path+"?"+urllib.parse.urlencode(params)
    time.sleep(.25)
    req=urllib.request.Request(url,headers={"Accept":"application/json","User-Agent":"scanner-research/0.1"},method="GET")
    with urllib.request.urlopen(req,timeout=15) as r:
        raw=r.read(5_000_001)
    if len(raw)>5_000_000:
        raise ValueError("response too large")
    return json.loads(raw)

def parse(payload):
    if not isinstance(payload,list):
        raise ValueError("expected stats list")
    rows={}
    for x in payload:
        ts=seconds(x["time"])
        if ts%STEP:
            raise ValueError("off-grid timestamp")
        row={}
        for k in FIELDS:
            if x.get(k) is None or x.get(k)=="":
                continue
            v=D(x[k])
            if not v.is_finite() or v<0:
                raise ValueError("invalid "+k)
            row[k]=str(v)
        if ts in rows and rows[ts]!=row:
            raise ValueError("conflicting duplicate")
        rows[ts]=row
    return rows

def coverage(rows,left,right):
    expected=set(range(left,right,STEP))
    got=expected & set(rows)
    counts={k:sum(k in rows[t] for t in got) for k in FIELDS}
    return {"expected":len(expected),"observed":len(got),"pct":100*len(got)/len(expected),
            "first":min(got,default=None),"last":max(got,default=None),
            "fields_present":counts,"positive_oi":sum("open_interest" in rows[t] and D(rows[t]["open_interest"])>0 for t in got)}

def collect(fetch,symbol,left=LEFT,right=END):
    rows={};errors=[];requests=0;probes=[];conflicts=0
    # Probe whether documented from selects forward rows; retain only timestamped actual observations.
    # If response is backward-looking, use the last timestamp of each requested chunk.
    def request(start):
        nonlocal requests
        requests+=1
        p=parse(fetch("contract_stats",{"contract":symbol,"from":start,"interval":"5m","limit":LIMIT}))
        probes.append({"from":start,"count":len(p),"first":min(p,default=None),"last":max(p,default=None)})
        return p
    def merge(p):
        nonlocal conflicts
        for t,v in p.items():
            if left<=t<right:
                if t in rows and rows[t]!=v:
                    conflicts+=1
                    raise ValueError("conflicting stats across requests")
                rows[t]=v
    try:
        p=request(left);merge(p)
        if not p or max(p)<left or min(p)>=right:
            # Check last historical chunk; a zero first response may reflect retention.
            q=request(right-STEP);merge(q)
            if not rows:
                return rows,{"requests":requests,"errors":errors,"probes":probes,"conflicts":conflicts,"mode":"no_matched_history"}
            mode="backward" if q and max(q)<=right-STEP else "forward"
        else:
            mode="backward" if max(p)<=left and min(p)<left else "forward"
        for a in range(left,right,LIMIT*STEP):
            b=min(right,a+LIMIT*STEP)
            key=b-STEP if mode=="backward" else a
            if all(t in rows for t in range(a,b,STEP)):
                continue
            q=request(key);merge(q)
    except Exception as e:
        errors.append(type(e).__name__+": "+str(e)[:200])
        mode="error"
    return rows,{"requests":requests,"errors":errors,"probes":probes,"conflicts":conflicts,"mode":mode}

def run(output):
    output.mkdir(parents=True,exist_ok=True)
    report={"type":"V6F_GATE_STATS_COVERAGE","matched":[MATCH_LEFT,END],"source":HOST+PREFIX,
            "symbols":{},"limitations":["Gate-specific public statistics, not MEXC positions or trade flow.",
                "No claim of interval start/end semantics or historical publication latency; verify before any model join.",
                "Fields absent remain missing; ratios and liquidation totals are not CVD or raw trade history.",
                "No automatic bypass/retry of forbidden access; no keys, orders, or PRD changes."]}
    try:
        catalog=get("contracts",{})
        names={r["name"]:r for r in catalog}
    except Exception as e:
        report["catalog_error"]=type(e).__name__+": "+str(e)[:200]
        names={}
    for symbol in SYMBOLS:
        rows,a=collect(get,symbol)
        c=names.get(symbol,{})
        result={"requested":coverage(rows,LEFT,END),"matched":coverage(rows,MATCH_LEFT,END),
                "catalog_present":bool(c),"catalog_fields":{k:c[k] for k in ("name","type","quanto_multiplier","in_delisting") if k in c},
                **a,**save(output/(symbol+"-stats.json.gz"),rows)}
        report["symbols"][symbol]=result
        print(json.dumps({"symbol":symbol,"matched":result["matched"],"errors":a["errors"],"mode":a["mode"]}),flush=True)
    (output/"summary.json").write_text(json.dumps(report,indent=2,allow_nan=False))
    compact={**report,"symbols":{s:{**a,"probes":a["probes"][:3]+a["probes"][-1:]} for s,a in report["symbols"].items()}}
    print(json.dumps(compact,indent=2,allow_nan=False),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--output",type=Path,required=True)
    run(p.parse_args().output)
