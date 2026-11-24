"""V3j: matched historical transfer of frozen V3e to nested asset universes."""
from __future__ import annotations
import argparse
import json
from collections import Counter
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from scripts.research_pre_breakout_dataset import load_raw,features
from scripts.research_pre_breakout_coverage import SYMBOLS
from scripts.research_universe_expansion import TIER1,TIER2
from scripts.research_v3e_prospective import load_model,score,HASH
from scripts.research_amplitude_240 import inputs,split,MAX_LABEL,CUT1,CUT2
from scripts.research_amplitude_geometry import barrier,funding_charge
from scripts.research_amplitude_frequency import select_daily,local_day
from scripts.research_expected_net_return import portfolio_stats,utc_day,COSTS
from scripts.research_pre_breakout_model import net_r
from mexc_scanner.models import D

LOCAL=ZoneInfo("America/Sao_Paulo")
BANDS={"5m_plus":.0024,"2.5m_to_5m":.0035,"1m_to_2.5m":.005}
SIDES=("LONG","SHORT")

def sources(raw,g,h,i):
    metas=[json.loads((p/"coverage.json").read_text()) for p in (raw,g,h,i)]
    a,b,c,d=metas
    btc=a["symbols"]["BTC_USDT"]
    refhash=btc["sha256_uncompressed"]
    if any(x["reference_btc_sha256"]!=refhash for x in (b,c,d)):
        raise ValueError("BTC reference digest mismatch")
    if len({(x["start"],x["end_exclusive"]) for x in (b,c,d)})!=1:
        raise ValueError("reference dates mismatch")
    if tuple(b["qualified_extra"])!=(*TIER1,*TIER2):
        raise ValueError("unexpected V3g coverage")
    orig=list(SYMBOLS)
    g1=orig+list(TIER1)
    g2=g1+list(TIER2)
    g3=g2+c["qualified_extra"]
    g4=g3+d["qualified_extra"]
    if len(set(g4))!=52 or [len(x) for x in (orig,g1,g2,g3,g4)]!=[6,12,18,31,52]:
        raise ValueError("unexpected nested universe")
    if set(d["reference"])!=set(g3):
        raise ValueError("V3i reference mismatch")
    loc={s:(raw,a["symbols"][s]) for s in orig}
    for p,m in ((g,b),(h,c),(i,d)):
        for s in m["qualified_extra"]:
            loc[s]=(p,m["symbols"][s])
    bands={s:d["symbols"][s]["liquidity_band"] for s in d["qualified_extra"]}
    return loc,{"6":orig,"12":g1,"18":g2,"31":g3,"52":g4},bands,b["start"],b["end_exclusive"]

def stress_cost(band):
    return BANDS[band] if band is not None else .0024

def frequency(actual,eligible,times):
    first,last=min(times),max(times)
    d=datetime.fromtimestamp(first,LOCAL).date()
    final=datetime.fromtimestamp(last,LOCAL).date()
    counts=Counter(local_day(r["t"]) for r in actual)
    candidates=Counter(local_day(r["t"]) for r in eligible)
    slots=Counter(local_day(t) for t in {r["t"] for r in eligible})
    rows=[]
    while d<=final:
        k=d.isoformat()
        left=int(datetime.combine(d,datetime.min.time(),LOCAL).timestamp())
        right=int(datetime.combine(d+timedelta(days=1),datetime.min.time(),LOCAL).timestamp())
        rows.append({"date":k,"complete":first<=left and last>=right-300,
                     "executed":counts[k],"eligible_directional":candidates[k],"eligible_slots":slots[k]})
        d+=timedelta(days=1)
    full=[r["executed"] for r in rows if r["complete"]]
    return {"daily":rows,"full_days":len(full),"days_ge2":sum(n>=2 for n in full),
            "days_zero":sum(n==0 for n in full),"days_1":sum(n==1 for n in full),
            "days_2_to_4":sum(2<=n<=4 for n in full),"mean_full":sum(full)/len(full) if full else None}

def evaluate(candidates,times,cap):
    actual=select_daily(candidates,cap)
    days=sorted({utc_day(t) for t in times})
    stats,verified=portfolio_stats(actual,days)
    if len(verified)!=len(actual):
        raise ValueError("overlap in selection")
    common=[{**r,"y":[r["y"][0],r["y"][1]-r["funding"]]} for r in actual]
    tier=[{**r,"y":[r["y"][0],r["tier_net"]]} for r in actual]
    cs,_=portfolio_stats(common,days)
    ts,_=portfolio_stats(tier,days)
    return {"eligible_directional":len(candidates),"finance":stats,
            "common_adverse_funding":cs["0.0024"],"tier_adverse_funding":ts["0.0024"],
            "frequency":frequency(actual,candidates,times),
            "outcomes":dict(Counter(r["label"]["outcome"] for r in actual)),
            "symbols":dict(Counter(r["symbol"] for r in actual)),
            "gross_r":sum(float(r["label"]["gross_r"]) for r in actual)}

def run(raw,g,h,i,output):
    model=load_model()
    loc,groups,bands,start,end=sources(raw,g,h,i)
    output.mkdir(parents=True,exist_ok=True)
    p,m=loc["BTC_USDT"]
    btc=load_raw(p/m["raw_file"],m["sha256_uncompressed"])
    # Same partition policy and full 240m outcome tail as V3c-e.
    times={part:[t for t in range((start+299)//300*300,end,300)
                  if split(t)==part and t+MAX_LABEL<=end] for part in ("validation","test")}
    all_candidates={p:[] for p in times}
    coverage={}
    for symbol,(p,m) in loc.items():
        bars=btc if symbol=="BTC_USDT" else load_raw(p/m["raw_file"],m["sha256_uncompressed"])
        if any(t not in bars for t in range(start,end,60)):
            raise ValueError("missing reference candles "+symbol)
        counts=Counter()
        for part,tt in times.items():
            for t in tt:
                f=features(bars,btc,t)
                if f is None:
                    raise ValueError("missing causal features "+symbol)
                if not f["inside_prior_range"]:
                    continue
                x,notional=inputs(f,bars[t-60].close)
                a=D(f["atr15"])
                for side in SIDES:
                    counts[part+"_geometric"]+=1
                    pred=score(x,notional,side,model)
                    if min(pred)<=0:
                        continue
                    l=barrier(bars,t,a,side,"3",end)
                    if l["outcome"]=="INVALID_GEOMETRY":
                        counts[part+"_invalid_geometry"]+=1
                        continue
                    if l["outcome"] not in ("TP","SL","TIMEOUT"):
                        raise ValueError("unexpected censored candidate")
                    funding=funding_charge(l,float(a),.0005)
                    all_candidates[part].append({"t":t,"symbol":symbol,"side":side,"rank":pred[1],
                        "label":l,"y":[net_r(l,float(a),c) for c in COSTS],"funding":funding,
                        "tier_net":net_r(l,float(a),stress_cost(bands.get(symbol)))-funding})
                    counts[part+"_eligible"]+=1
        coverage[symbol]=dict(counts)
        print(json.dumps({"symbol":symbol,"counts":dict(counts)}),flush=True)
    report={"type":"V3J_MATCHED_UNIVERSE_TRANSFER","model_sha256":HASH,
            "start":start,"end_exclusive":end,"cutoffs":[CUT1,CUT2],
            "universes":groups,"coverage":coverage,"lower_liquidity_bands":bands,
            "tier_costs":BANDS,"results":{},
            "limitations":["Retrospective dates already inspected; transfer to unseen symbols is not independent temporal validation.",
             "Current turnover selection is not historical liquidity or point-in-time universe.",
             "Band costs only applied to newly added V3i assets; reference 31 use common stress, regardless of current turnover.",
             "Stress funding hypothetical, no actual fills, tick/lot, spread, funding or liquidation.",
             "Caps chronological, not ex-post top daily signals; same gate/rank in all cost scenarios.",
             "One position and 60s cooldown; no enforced minimum. No PRD or frozen strategy changes."]}
    for part,tt in times.items():
        report["results"][part]={}
        for name,universe in groups.items():
            universe=set(universe)
            candidates=[r for r in all_candidates[part] if r["symbol"] in universe]
            report["results"][part][name]={"uncapped":evaluate(candidates,tt,None),
                                           "cap3":evaluate(candidates,tt,3)}
        # Exact previously published reference benchmark, fail closed if cohort differs.
        expected=(18,.6562278018556729,12,1.6526712730962987) if part=="validation" else (39,5.899315915626597,16,4.756236536451358)
        for variant,n,r in (("uncapped",expected[0],expected[1]),("cap3",expected[2],expected[3])):
            q=report["results"][part]["6"][variant]["finance"]
            if q["trades"]!=n or abs(q["0.0016"]["total_net_r"]-r)>1e-8:
                raise ValueError("six-symbol V3f benchmark differs: "+part+" "+variant+" "+str(q))
    (output/"summary.json").write_text(json.dumps(report,indent=2,allow_nan=False))
    print(json.dumps(report,indent=2,allow_nan=False),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for k in ("raw","g","h","i","output"):
        p.add_argument("--"+k,type=Path,required=True)
    a=p.parse_args()
    run(a.raw,a.g,a.h,a.i,a.output)
