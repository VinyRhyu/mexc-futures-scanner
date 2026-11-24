"""V3i: expand historical coverage up to 100 candidates in separate liquidity bands."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from scripts.research_universe_expansion import alignment
from scripts.research_pre_breakout_coverage import collect,save_raw
from scripts.research_pre_breakout_dataset import load_raw
from mexc_scanner.mexc import MexcClient
from mexc_scanner.market import select_universe
from mexc_scanner.models import D,jsonable

LIMIT=100
MIN_TURNOVER=D("1000000")

def liquidity_band(amount):
    a=D(amount)
    if a>=D("5000000"):
        return "5m_plus"
    if a>=D("2500000"):
        return "2.5m_to_5m"
    if a>=MIN_TURNOVER:
        return "1m_to_2.5m"
    return "below_1m"

def choose(eligible,reference,limit=LIMIT):
    seen=set(reference)
    if len(seen)>limit:
        raise ValueError("reference exceeds limit")
    extra=[]
    for c in eligible:
        s=str(c["symbol"])
        if s in seen:
            continue
        if len(seen)>=limit:
            break
        extra.append(s)
        seen.add(s)
    return extra

def run(client,raw,previous,output):
    meta=json.loads((raw/"coverage.json").read_text())
    prior=json.loads((previous/"coverage.json").read_text())
    if prior["type"]!="V3H_UNIVERSE_50_COVERAGE":
        raise ValueError("unexpected source")
    b=meta["symbols"]["BTC_USDT"]
    btc=load_raw(raw/b["raw_file"],b["sha256_uncompressed"])
    start,end=min(btc),max(btc)+60
    if (set(btc)!=set(range(start,end,60)) or prior["start"]!=start
        or prior["end_exclusive"]!=end or prior["reference_btc_sha256"]!=b["sha256_uncompressed"]):
        raise ValueError("reference mismatch")
    reference=[*prior["fixed_reference"],*prior["qualified_extra"]]
    if len(reference)!=31 or len(set(reference))!=31:
        raise ValueError("unexpected prior universe")
    now=client.server_time()
    if now<end+10:
        raise ValueError("reference not closed")
    allowed=set(json.loads(Path("config/crypto-assets.json").read_text())["assets"])
    catalog=client.contracts()
    quotes=client.tickers()
    eligible,excluded=select_universe(catalog,quotes,allowed,MIN_TURNOVER,len(catalog))
    q={str(x["symbol"]):x for x in quotes}
    eligible_set={str(c["symbol"]) for c in eligible}
    extra=choose(eligible,reference)
    bands={s:liquidity_band(q[s]["amount24"]) for s in extra}
    output.mkdir(parents=True,exist_ok=True)
    snapshot={"server_time":now,"minimum_turnover":str(MIN_TURNOVER),"reference":reference,
              "eligible_ranked":[str(c["symbol"]) for c in eligible],"excluded":excluded,
              "additional":extra,"additional_bands":bands,"contracts":catalog,"tickers":quotes}
    (output/"selection.json").write_text(json.dumps(jsonable(snapshot),indent=2,allow_nan=False))
    results={}
    for s in extra:
        bars,fail,dupes=collect(client,s,start,end)
        r=alignment(bars,btc)
        r.update({"qualified_coverage_only":not fail and r["missing"]==0 and r["unexpected"]==0,
                  "failed_chunks":fail,"duplicates":dupes,"liquidity_band":bands[s],
                  "current_turnover_24h":str(q[s]["amount24"]),
                  "raw_file":s+".jsonl.gz","sha256_uncompressed":save_raw(output/(s+".jsonl.gz"),bars)})
        results[s]=r
        print(json.dumps({"symbol":s,"band":bands[s],"coverage_pct":r["coverage_pct"],
                          "qualified_coverage_only":r["qualified_coverage_only"]}),flush=True)
    report={"type":"V3I_UNIVERSE_100_COVERAGE","source_run":45449303295,
            "start":start,"end_exclusive":end,"reference_btc_sha256":b["sha256_uncompressed"],
            "selection_time":now,"reference":reference,"reference_currently_eligible":[s for s in reference if s in eligible_set],
            "additional_candidates":extra,"total_candidates":len(reference)+len(extra),
            "minimum_current_turnover":str(MIN_TURNOVER),"symbols":results,
            "qualified_extra":[s for s,r in results.items() if r["qualified_coverage_only"]],
            "bands":{band:{"candidates":sum(v==band for v in bands.values()),
                           "qualified":sum(r["liquidity_band"]==band and r["qualified_coverage_only"] for r in results.values())}
                      for band in ("5m_plus","2.5m_to_5m","1m_to_2.5m")},
            "limitations":["Research-only lower current turnover floor; not a change to production rules.",
                "Current turnover is not historical liquidity and does not measure actual spread, depth or slippage.",
                "31 reference symbols retained regardless of current eligibility; no duplicate collection.",
                "Selection frozen before candle access; no performance-based replacement or missing data imputation.",
                "Coverage alone does not qualify trades. Lower liquidity requires separate cost stress and independent validation."]}
    (output/"coverage.json").write_text(json.dumps(report,indent=2,allow_nan=False))
    print(json.dumps(report,indent=2,allow_nan=False),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for name in ("raw","previous","output"):
        p.add_argument("--"+name,type=Path,required=True)
    a=p.parse_args()
    run(MexcClient(),a.raw,a.previous,a.output)
