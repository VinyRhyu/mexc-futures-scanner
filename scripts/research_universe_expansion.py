"""V3g expansion coverage audit only: fixed additional assets, same frozen BTC dates."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from scripts.research_pre_breakout_coverage import collect,save_raw,SYMBOLS
from scripts.research_pre_breakout_dataset import load_raw
from mexc_scanner.mexc import MexcClient

TIER1=("XRP_USDT","ADA_USDT","DOGE_USDT","AVAX_USDT","SUI_USDT","BNB_USDT")
TIER2=("LTC_USDT","BCH_USDT","DOT_USDT","APT_USDT","UNI_USDT","NEAR_USDT")

def alignment(bars,reference):
    observed=set(bars)
    expected=set(reference)
    common=observed&expected
    missing=sorted(expected-common)
    return {"expected":len(expected),"observed_aligned":len(common),"missing":len(missing),
            "coverage_pct":100*len(common)/len(expected) if expected else None,
            "first_missing":missing[0] if missing else None,
            "last_missing":missing[-1] if missing else None,
            "unexpected":len(observed-expected)}

def run(client,raw,output):
    meta=json.loads((raw/"coverage.json").read_text())
    b=meta["symbols"]["BTC_USDT"]
    btc=load_raw(raw/b["raw_file"],b["sha256_uncompressed"])
    start,end=min(btc),max(btc)+60
    if set(btc)!=set(range(start,end,60)):
        raise ValueError("frozen BTC not contiguous")
    if client.server_time()<end+10:
        raise ValueError("reference data not closed")
    output.mkdir(parents=True,exist_ok=True)
    try:
        catalog={c.get("symbol"):c for c in client.contracts()}
        catalog_status="available"
    except Exception as e:
        catalog={}
        catalog_status=type(e).__name__
    results={}
    for tier,universe in (("tier1",TIER1),("tier2",TIER2)):
        for s in universe:
            bars,fail,duplicates=collect(client,s,start,end)
            info=alignment(bars,btc)
            qualified=not fail and info["missing"]==0 and info["unexpected"]==0
            info.update({"tier":tier,"qualified_coverage_only":qualified,"failed_chunks":fail,
                         "duplicates":duplicates,"catalog_present_at_collection":s in catalog,
                         "raw_file":s+".jsonl.gz",
                         "sha256_uncompressed":save_raw(output/(s+".jsonl.gz"),bars)})
            results[s]=info
            print(json.dumps({"symbol":s,**{k:info[k] for k in ("tier","observed_aligned","missing","coverage_pct","qualified_coverage_only")}}),flush=True)
    report={"type":"V3G_EXPANSION_COVERAGE","source_run":45432136926,
            "start":start,"end_exclusive":end,"reference_btc_sha256":b["sha256_uncompressed"],
            "original_symbols":SYMBOLS,"candidate_tiers":{"tier1":TIER1,"tier2":TIER2},
            "catalog_status":catalog_status,"symbols":results,
            "qualified_extra":[s for s,r in results.items() if r["qualified_coverage_only"]],
            "limitations":["Fixed candidate basket selected by researcher before expansion results, not a point-in-time liquidity universe.",
                "Only data coverage tested, not financial performance or eligibility for trading.",
                "New data collected separately; reference BTC dates fixed; no gap filling.",
                "Current contract catalog is not historical eligibility; no fees, spread, liquidity or funding verified.",
                "No V3e model, gate, universe or prospective window changes; no PRD changes."]}
    (output/"coverage.json").write_text(json.dumps(report,indent=2,allow_nan=False))
    print(json.dumps(report,indent=2,allow_nan=False),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--raw",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    run(MexcClient(),a.raw,a.output)
