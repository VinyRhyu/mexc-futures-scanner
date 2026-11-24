"""V3h: expand research universe to 50 via existing public catalog liquidity rules."""
from __future__ import annotations
import argparse
import json
import tomllib
from pathlib import Path
from scripts.research_universe_expansion import TIER1,TIER2,alignment
from scripts.research_pre_breakout_coverage import collect,save_raw,SYMBOLS
from scripts.research_pre_breakout_dataset import load_raw
from mexc_scanner.mexc import MexcClient
from mexc_scanner.market import select_universe
from mexc_scanner.models import D,jsonable

FIXED=(*SYMBOLS,*TIER1,*TIER2)
LIMIT=50

def choose(eligible,limit=LIMIT):
    # Preserve diagnostic cohorts and append ranked eligible contracts.
    seen=set(FIXED)
    extra=[]
    for c in eligible:
        s=str(c["symbol"])
        if s not in seen:
            if len(seen)>=limit:
                break
            extra.append(s)
            seen.add(s)
    return extra

def run(client,raw,output):
    meta=json.loads((raw/"coverage.json").read_text())
    b=meta["symbols"]["BTC_USDT"]
    btc=load_raw(raw/b["raw_file"],b["sha256_uncompressed"])
    start,end=min(btc),max(btc)+60
    if set(btc)!=set(range(start,end,60)):
        raise ValueError("frozen BTC not contiguous")
    now=client.server_time()
    if now<end+10:
        raise ValueError("reference not closed")
    cfg=tomllib.loads(Path("config/default.toml").read_text())
    allowed=set(json.loads(Path("config/crypto-assets.json").read_text())["assets"])
    catalog=client.contracts()
    quotes=client.tickers()
    minimum=D(cfg["minimum_turnover"])
    eligible,excluded=select_universe(catalog,quotes,allowed,minimum,len(catalog))
    extra=choose(eligible)
    q={str(x["symbol"]):x for x in quotes}
    output.mkdir(parents=True,exist_ok=True)
    snapshot={"server_time":now,"minimum_turnover":str(minimum),
              "eligible_ranked":[str(c["symbol"]) for c in eligible],
              "excluded":excluded,"contracts":catalog,"tickers":quotes,
              "fixed_reference":FIXED,"additional":extra}
    (output/"selection.json").write_text(json.dumps(jsonable(snapshot),indent=2,allow_nan=False))
    results={}
    for s in extra:
        bars,fail,dupes=collect(client,s,start,end)
        r=alignment(bars,btc)
        r.update({"qualified_coverage_only":not fail and r["missing"]==0 and r["unexpected"]==0,
                  "failed_chunks":fail,"duplicates":dupes,
                  "current_turnover_24h":str(q[s]["amount24"]),
                  "raw_file":s+".jsonl.gz","sha256_uncompressed":save_raw(output/(s+".jsonl.gz"),bars)})
        results[s]=r
        print(json.dumps({"symbol":s,"coverage_pct":r["coverage_pct"],
                          "qualified_coverage_only":r["qualified_coverage_only"]}),flush=True)
    report={"type":"V3H_UNIVERSE_50_COVERAGE","start":start,"end_exclusive":end,
            "reference_btc_sha256":b["sha256_uncompressed"],"selection_time":now,
            "fixed_reference_count":len(FIXED),"fixed_reference":FIXED,"fixed_currently_eligible":[s for s in FIXED if s in {c["symbol"] for c in eligible}],
            "additional_candidates":extra,"total_candidates":len(FIXED)+len(extra),
            "minimum_current_turnover":str(minimum),"symbols":results,
            "qualified_extra":[s for s,r in results.items() if r["qualified_coverage_only"]],
            "limitations":["Current turnover and contract catalog used for diagnostic selection only, not historical eligibility.",
                "Fixed 18 reference candidates retained regardless of current liquidity; qualification not guaranteed.",
                "Additional assets ranked before candle collection; no replacement for failed historical coverage.",
                "Exact frozen BTC dates; API rolling retention can prevent full alignment; no imputation.",
                "No financial evaluation, model changes, PRD or order execution."]}
    (output/"coverage.json").write_text(json.dumps(report,indent=2,allow_nan=False))
    print(json.dumps(report,indent=2,allow_nan=False),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--raw",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    run(MexcClient(),a.raw,a.output)
