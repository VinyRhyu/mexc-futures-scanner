"""V4c: attribute existing V4b forecasts to causal market regimes; no refit or selection."""
from __future__ import annotations
import argparse
import csv
import gzip
import json
import math
from pathlib import Path
from collections import defaultdict
from functools import lru_cache
from scripts.research_universe_transfer import sources
from scripts.research_pre_breakout_dataset import load_raw
from scripts.research_amplitude_frequency import local_day

def regime(z):
    return "UP" if z>=1 else "DOWN" if z<=-1 else "NEUTRAL"

def normalized_move(bars,t,minutes):
    # Last close ends at t; prior closes also strictly available at t.
    prices=[float(bars[u].close) for u in range(t-(minutes+1)*60,t,60)]
    moves=[math.log(b/a) for a,b in zip(prices,prices[1:])]
    denom=math.sqrt(sum(r*r for r in moves))
    return sum(moves)/denom if denom else 0.

def add(group,r):
    group["n"]+=1
    for k in ("audit_pred","gross","net_stress","funding"):
        group[k]+=float(r[k])
    group["sl"]+=r["outcome"]=="SL"
    group["tp"]+=r["outcome"]=="TP"

def finish(group):
    return {"n":int(group["n"]), "pred_mean":group["audit_pred"]/group["n"],
            "gross_mean":group["gross"]/group["n"],"stress_mean":group["net_stress"]/group["n"],
            "stress_total":group["net_stress"],"funding_mean":group["funding"]/group["n"],
            "sl_rate":group["sl"]/group["n"],"tp_rate":group["tp"]/group["n"]}

def leave_one(groups,total):
    return {k:total-v["net_stress"] for k,v in sorted(groups.items())}

def run(raw,g,h,i,predictions,output):
    loc,universes,bands,start,end=sources(raw,g,h,i)
    p,m=loc["BTC_USDT"]
    btc=load_raw(p/m["raw_file"],m["sha256_uncompressed"])
    @lru_cache(maxsize=None)
    def btc_regime(t):
        return regime(normalized_move(btc,t,240))
    report={"type":"V4C_CAUSAL_REGIME_AUDIT","source_run":45453071515,
            "definitions":{"btc_4h":"sum of last 240 closed M1 log returns / sqrt(sum of squared returns), +/-1",
                           "asset_1h":"same normalization over 60 closed M1 returns, +/-1",
                           "alignment":"LONG in UP or SHORT in DOWN; neutral separate"},
            "parts":{},"limitations":["Existing retrospective V4b predictions only; no training, tuning, or new trades.",
                "Causal bins fixed before computing grouped results; observational, not causal inference.",
                "Overlapping forecasts are not independent trades; selected portfolio tiny and dates already inspected.",
                "No inference that any particular regime or asset should be excluded from trading."]}
    for part,expected_n,expected_total in (("validation",155592,-5.590841192332695),("test",154672,4.140695988401875)):
        by_symbol=defaultdict(list)
        with gzip.open(predictions/(part+"-predictions.csv.gz"),"rt",newline="") as f:
            for r in csv.DictReader(f):
                by_symbol[r["symbol"]].append(r)
        if set(by_symbol)!=set(loc) or sum(map(len,by_symbol.values()))!=expected_n:
            raise ValueError("unexpected V4b cohort")
        stats={kind:defaultdict(lambda:defaultdict(float)) for kind in ("all","eligible","selected")}
        selected_days=defaultdict(lambda:defaultdict(float))
        selected_symbols=defaultdict(lambda:defaultdict(float))
        for symbol,rows in by_symbol.items():
            p,m=loc[symbol]
            bars=btc if symbol=="BTC_USDT" else load_raw(p/m["raw_file"],m["sha256_uncompressed"])
            @lru_cache(maxsize=None)
            def asset_regime(t):
                return regime(normalized_move(bars,t,60))
            for r in rows:
                t=int(r["t"])
                b=btc_regime(t)
                a=asset_regime(t)
                side=r["side"]
                aligned="NEUTRAL" if b=="NEUTRAL" else "ALIGNED" if (b=="UP")== (side=="LONG") else "OPPOSED"
                contexts=("TOTAL","BTC_"+b,"ASSET_"+a,"BTC_"+b+"_"+side,"ALIGN_"+aligned,
                          "BTC_"+b+"_ASSET_"+a+"_"+side,"DAY_"+local_day(t))
                kinds=["all"]
                # V4a base cost is <= tier cost, so a positive tier forecast is the exact gate.
                if float(r["audit_pred"])>0:
                    kinds.append("eligible")
                if r["selected_cap3"]=="1":
                    kinds.append("selected")
                    add(selected_days[local_day(t)],r)
                    add(selected_symbols[symbol],r)
                for kind in kinds:
                    for k in contexts:
                        add(stats[kind][k],r)
            asset_regime.cache_clear()
        sel=stats["selected"]["TOTAL"]
        if sel["n"]!=18 or abs(sel["net_stress"]-expected_total)>1e-8:
            raise ValueError("selected V4b portfolio mismatch")
        if stats["eligible"]["TOTAL"]["n"]!=(3912 if part=="validation" else 4766):
            raise ValueError("eligible V4b cohort mismatch")
        report["parts"][part]={"groups":{kind:{k:finish(v) for k,v in sorted(groups.items())} for kind,groups in stats.items()},
            "leave_one_day_out_stress_r":leave_one(selected_days,sel["net_stress"]),
            "leave_one_symbol_out_stress_r":leave_one(selected_symbols,sel["net_stress"])}
    output.mkdir(parents=True,exist_ok=True)
    (output/"summary.json").write_text(json.dumps(report,indent=2,allow_nan=False))
    print(json.dumps(report,indent=2,allow_nan=False),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for name in ("raw","g","h","i","predictions","output"):
        p.add_argument("--"+name,type=Path,required=True)
    a=p.parse_args()
    run(a.raw,a.g,a.h,a.i,a.predictions,a.output)
