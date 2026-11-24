"""V5e: fixed-path failure attribution of V5d; no alternate strategy."""
from __future__ import annotations
import argparse
import csv
import gzip
import json
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np
from scripts.research_delayed_first_passage import (
    confirmation,remaining,stats,bounded_barrier,DELAY,MOVE,GATE,HORIZON,
    event,align_probabilities,CLASSES,PARTS,LOOKBACK,pipeline,binary_metrics,
    sources,load_raw,features,inputs,split,MAX_LABEL,CUT1,CUT2,D,
    FEATURES,net_r,COSTS,funding_charge,evaluate,stress_cost,positive)
from scripts.research_amplitude_frequency import select_daily

EXPECTED={"validation":(707,18,6.659280535307438,-1.1257038866753266),
          "test":(1152,18,-2.930079061836024,-9.755948144420449)}

def path_trace(bars,trade,atr,expiry):
    """Full post-entry trajectory, including candles after actual simulated exit.
    Same-bar extrema cannot establish order. Only later full bars count as recovery.
    """
    l=trade["label"]
    entry=D(l["entry"])
    sign=D(1) if trade["side"]=="LONG" else D(-1)
    first_tp=None
    first_sl=None
    simulated=None
    favorable=D(0)
    adverse=D(0)
    pre_tp_lo=pre_tp_hi=None
    pre_sl_lo=pre_sl_hi=None
    stop_bar=None
    stop_bar_both=False
    later_tp=False
    later_max=D(0)
    later_tp_ts=None
    for ts in range(int(l["entry_ts"]),expiry,60):
        c=bars[ts]
        op=sign*(c.open-entry)/atr
        fav=sign*((c.high if sign>0 else c.low)-entry)/atr
        adv=-sign*((c.low if sign>0 else c.high)-entry)/atr
        if first_tp is None and (op>=3 or fav>=3):
            first_tp=ts if op>=3 else c.end
            pre_tp_lo=max(adverse,-op,D(0))
            pre_tp_hi=pre_tp_lo if op>=3 else max(pre_tp_lo,adv)
        if first_sl is None and (op<=-1 or adv>=1):
            first_sl=ts if op<=-1 else c.end
        if simulated is None:
            if op<=-1:
                simulated=("SL",ts)
            elif op>=3:
                simulated=("TP",ts)
            elif adv>=1:
                simulated=("SL",c.end)
            elif fav>=3:
                simulated=("TP",c.end)
            if simulated and simulated[0]=="SL":
                stop_bar=ts
                stop_bar_both=fav>=3
                pre_sl_lo=max(favorable,op,D(0))
                pre_sl_hi=pre_sl_lo if op<=-1 else max(pre_sl_lo,fav)
        if stop_bar is not None and ts>stop_bar:
            later_max=max(later_max,fav,D(0))
            if not later_tp and (op>=3 or fav>=3):
                later_tp=True
                later_tp_ts=ts if op>=3 else c.end
        favorable=max(favorable,fav)
        adverse=max(adverse,adv)
    if simulated is None:
        simulated=("TIMEOUT",expiry)
    if simulated!=(l["outcome"],int(l["exit_ts"])):
        raise ValueError("first passage mismatch")
    def val(x):
        return float(x) if x is not None else None
    start=int(l["entry_ts"])
    return {"outcome":l["outcome"],"duration_minutes":(int(l["exit_ts"])-start)/60,
            "full_mfe":float(favorable),"full_mae":float(adverse),
            "first_target_minutes":(first_tp-start)/60 if first_tp is not None else None,
            "first_stop_minutes":(first_sl-start)/60 if first_sl is not None else None,
            "pre_target_adverse_lower":val(pre_tp_lo),"pre_target_adverse_upper":val(pre_tp_hi),
            "pre_stop_favorable_lower":val(pre_sl_lo),"pre_stop_favorable_upper":val(pre_sl_hi),
            "stop_bar_also_target":stop_bar_both,"later_target_after_stop":later_tp,
            "later_max_favorable":float(later_max) if stop_bar is not None else None,
            "stop_to_later_target_minutes":(later_tp_ts-int(l["exit_ts"]))/60 if later_tp_ts is not None else None}

def qstats(values):
    vals=[v for v in values if v is not None]
    if not vals:
        return None
    return {"n":len(vals),"p25":float(np.quantile(vals,.25)),"median":float(np.median(vals)),
            "p75":float(np.quantile(vals,.75)),"p90":float(np.quantile(vals,.9))}

def describe(rows):
    n=len(rows)
    if not n:
        return {"n":0}
    stops=[r for r in rows if r["outcome"]=="SL"]
    later=[r for r in stops if r["later_target_after_stop"]]
    reached=[r for r in rows if r["first_target_minutes"] is not None]
    gross=sum(r["gross_r"] for r in rows)
    base=sum(r["base_net_r"] for r in rows)
    stress=sum(r["stress_net_r"] for r in rows)
    fund=sum(r["funding_r"] for r in rows)
    return {"n":n,"outcomes":dict(Counter(r["outcome"] for r in rows)),
            "gross_total_r":gross,"base_cost_total_r":gross-base,
            "tier_cost_total_r":gross-stress-fund,"funding_total_r":fund,
            "base_net_total_r":base,"stress_net_total_r":stress,
            "mean_gross_r":gross/n,"mean_base_net_r":base/n,"mean_stress_net_r":stress/n,
            "direction_matches_original_event":sum(r["direction_matches_event"] for r in rows),
            "stop_latency_minutes":qstats([r["duration_minutes"] for r in stops]),
            "stop_within_5_15_30_60_minutes":{str(m):sum(r["duration_minutes"]<=m for r in stops) for m in (5,15,30,60)},
            "stops_later_reach_original_trade_target":len(later),
            "stops_later_target_fraction":len(later)/len(stops) if stops else None,
            "stops_same_candle_also_target":sum(r["stop_bar_also_target"] for r in stops),
            "stops_without_later_target":len(stops)-len(later),
            "stop_to_later_target_minutes":qstats([r["stop_to_later_target_minutes"] for r in later]),
            "later_target_pre_target_adverse_lower":qstats([r["pre_target_adverse_lower"] for r in later]),
            "later_target_pre_target_adverse_upper":qstats([r["pre_target_adverse_upper"] for r in later]),
            "before_stop_favorable_lower":qstats([r["pre_stop_favorable_lower"] for r in stops]),
            "before_stop_favorable_upper":qstats([r["pre_stop_favorable_upper"] for r in stops]),
            "full_target_reached_count":len(reached),
            "target_pre_adverse_lower":qstats([r["pre_target_adverse_lower"] for r in reached]),
            "target_pre_adverse_upper":qstats([r["pre_target_adverse_upper"] for r in reached]),
            "full_mfe":qstats([r["full_mfe"] for r in rows]),
            "full_mae":qstats([r["full_mae"] for r in rows])}

def grouped(rows,key):
    groups=defaultdict(list)
    for r in rows:
        groups[key(r)].append(r)
    return {str(k):describe(v) for k,v in sorted(groups.items())}

def atr_band(v):
    return "lt_0.25pct" if v<.0025 else "0.25_to_0.5pct" if v<.005 else "0.5_to_1pct" if v<.01 else "ge_1pct"

def move_band(v):
    return "0.5_to_1atr" if v<1 else "1_to_2atr" if v<2 else "ge_2atr"

def trace_gate(rows,candidates,loc,btc,output,part):
    by_symbol=defaultdict(list)
    chosen={(r["t"],r["symbol"],r["side"]) for r in select_daily(candidates,3)}
    for r in rows:
        if r.get("vol_probability",0)>=GATE and "trade" in r:
            by_symbol[r["symbol"]].append(r)
    records=[]
    for symbol,rs in sorted(by_symbol.items()):
        p,m=loc[symbol]
        bars=btc if symbol=="BTC_USDT" else load_raw(p/m["raw_file"],m["sha256_uncompressed"])
        for r in rs:
            tr=r["trade"]
            a=D(r["audit_atr"])
            l=tr["label"]
            trace=path_trace(bars,tr,a,r["t"]+HORIZON)
            records.append({"symbol":symbol,"forecast_t":r["t"],"confirmation_t":tr["t"],
                            "side":tr["side"],"probability":r["vol_probability"],
                            "atr_over_confirmation_close":float(a/bars[tr["t"]-60].close),
                            "confirmation_move_atr":abs(r["move_atr"]),
                            "latency_drift_atr":float((D(l["entry"])-bars[tr["t"]-60].close)/a)*(1 if tr["side"]=="LONG" else -1),
                            "direction_matches_event":int(r["event"]==r["side"]),
                            "gross_r":float(l["gross_r"]),"base_net_r":tr["y"][0],
                            "stress_net_r":tr["tier_net"],"funding_r":tr["funding"],
                            "selected":int((tr["t"],symbol,tr["side"]) in chosen),**trace})
    executed=[r for r in records if r["selected"]]
    n,k,net,stress=EXPECTED[part]
    if len(records)!=n or len(executed)!=k or abs(sum(r["base_net_r"] for r in executed)-net)>1e-8 or abs(sum(r["stress_net_r"] for r in executed)-stress)>1e-8:
        raise ValueError("V5d reference portfolio differs")
    output.mkdir(parents=True,exist_ok=True)
    with gzip.open(output/(part+"-path-audit.csv.gz"),"wt",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]))
        w.writeheader()
        w.writerows(records)
    return {"all_overlapping":describe(records),"executed_cap3":describe(executed),
            "by_side":grouped(records,lambda r:r["side"]),
            "by_causal_atr_price_band":grouped(records,lambda r:atr_band(r["atr_over_confirmation_close"])),
            "by_confirmation_move_band":grouped(records,lambda r:move_band(r["confirmation_move_atr"])),
            "executed_by_symbol":grouped(executed,lambda r:r["symbol"]),
            "latency_drift_all":qstats([r["latency_drift_atr"] for r in records]),
            "latency_drift_executed":qstats([r["latency_drift_atr"] for r in executed])}

def run(raw,g,h,i,output):
    loc,groups,bands,start,end=sources(raw,g,h,i)
    p,m=loc["BTC_USDT"]
    btc=load_raw(p/m["raw_file"],m["sha256_uncompressed"])
    times={part:[t for t in range((start+LOOKBACK+60+299)//300*300,end,300)
                if split(t)==part and t+MAX_LABEL<=end and (part!="train" or t%900==0)] for part in PARTS}
    data={p:[] for p in PARTS}
    for symbol,(p,m) in loc.items():
        bars=btc if symbol=="BTC_USDT" else load_raw(p/m["raw_file"],m["sha256_uncompressed"])
        if any(t not in bars for t in range(start,end,60)):
            raise ValueError("missing candle "+symbol)
        counts=Counter()
        for part,tt in times.items():
            for t in tt:
                f=features(bars,btc,t)
                if f is None:
                    raise ValueError("missing features")
                if not f["inside_prior_range"]:
                    continue
                a=D(f["atr15"])
                anchor=bars[t-60].close
                x,_=inputs(f,anchor)
                y,_=event(bars,t,anchor,a)
                r={"x":x,"event":y,"symbol":symbol,"t":t}
                if part!="train":
                    conf=confirmation(bars,t,a,anchor)
                    r.update(conf)
                    if conf["status"]=="confirmed":
                        r.update(remaining(bars,t,a,anchor,conf))
                        side="LONG" if conf["side"]=="UP" else "SHORT"
                        l=bounded_barrier(bars,conf["confirmation_t"],a,side,end)
                        if l["outcome"]=="CENSORED":
                            raise ValueError("incomplete delayed outcome")
                        if l["outcome"]!="INVALID_GEOMETRY":
                            atr=float(a)
                            fund=funding_charge(l,atr,.0005)
                            r["audit_atr"]=str(a)
                            r["trade"]={"t":conf["confirmation_t"],"symbol":symbol,"side":side,
                                "label":l,"y":[net_r(l,atr,c) for c in COSTS],
                                "funding":fund,"tier_net":net_r(l,atr,stress_cost(bands.get(symbol)))-fund}
                data[part].append(r)
                counts[part]+=1
        print(json.dumps({"symbol":symbol,"counts":dict(counts)}),flush=True)
    if [len(data[p]) for p in PARTS]!=[79260,77796,77336]:
        raise ValueError("V5a cohort mismatch")
    model=pipeline()
    model.fit(np.asarray([r["x"] for r in data["train"]]),np.asarray([r["event"] for r in data["train"]]))
    names=[*FEATURES,"atr_over_last_closed_price"]
    vi=[names.index(k) for k in ("rv15","rv60","rv_ratio","range_atr","atr_over_last_closed_price")]
    vol=pipeline()
    vol.fit(np.asarray([r["x"] for r in data["train"]])[:,vi],
            np.asarray([r["event"]!="NONE" for r in data["train"]],dtype=int))
    report={"type":"V5E_PATH_FAILURE_ATTRIBUTION","cutoffs":[CUT1,CUT2],"delay_sec":DELAY,
            "confirmation_move_atr":str(MOVE),"event_gate":GATE,"horizon_sec":HORIZON,
            "results":{},"limitations":["Compare original V5a and V5b volatility probabilities, plus no gate with volatility ranking.",
                "Fixed researcher-chosen 15min and 0.5 ATR confirmation, event probability >=0.60, no parameter search.",
                "Overlapping candidate statistics separate from chronological single-position max3 portfolios.",
                "SL1 ATR TP3 ATR based on original causal ATR, expiry at original t+240m, entry at confirmation+60s. SL-first intrabar, gap-stop at open. Costs/funding hypothetical.",
                "Directional correctness conditional on ex-post observed directional events is descriptive only; unconditional also reported.",
                "No selection based on future latency crossings or future realized outcome; invalid nonpositive barrier geometry counted. No actual fills, liquidation or recommendations.",
                "Same examined dates, current asset-selection bias, no independent confirmation."]}
    for part in PARTS[1:]:
        rows=data[part]
        p=align_probabilities(model.predict_proba(np.asarray([r["x"] for r in rows])),list(model.classes_))
        prob=1-p[:,CLASSES.index("NONE")]
        met=binary_metrics([r["event"]!="NONE" for r in rows],prob)
        expected=.5870439166518046 if part=="validation" else .6005279571949154
        if abs(met["auc"]-expected)>1e-8:
            raise ValueError("V5a event AUC mismatch")
        for r,v in zip(rows,prob):
            r["event_probability"]=float(v)
        selected=[r for r in rows if r["event_probability"]>=GATE]
        vp=positive(vol,np.asarray([r["x"] for r in rows])[:,vi])
        vm=binary_metrics([r["event"]!="NONE" for r in rows],vp)
        expected_vol=.5923385341549485 if part=="validation" else .6094123723225107
        if abs(vm["auc"]-expected_vol)>1e-8:
            raise ValueError("V5b volatility AUC mismatch")
        expected_confirmed=(3650,1861) if part=="validation" else (3552,1901)
        if (len(selected),sum(r["status"]=="confirmed" for r in selected))!=expected_confirmed:
            raise ValueError("V5c cohort mismatch")
        variants={"no_gate_vol_rank":[],"original_gate":[],"volatility_gate":[]}
        invalid=0
        for r,v in zip(rows,vp):
            r["vol_probability"]=float(v)
            if r["status"]!="confirmed":
                continue
            if "trade" not in r:
                invalid+=1
                continue
            variants["no_gate_vol_rank"].append({**r["trade"],"rank":float(v)})
            if r["event_probability"]>=GATE:
                variants["original_gate"].append({**r["trade"],"rank":r["event_probability"]})
            if v>=GATE:
                variants["volatility_gate"].append({**r["trade"],"rank":float(v)})
        result={"original_occurrence":met,"volatility_occurrence":vm,"invalid_geometry":invalid,
                "v5c_reference":stats(selected),"variants":{}}
        for name,rs in variants.items():
            n=len(rs)
            result["variants"][name]={"overlapping":{"n":n,
                "outcomes":dict(Counter(r["label"]["outcome"] for r in rs)),
                "mean_gross_r":sum(float(r["label"]["gross_r"]) for r in rs)/n if n else None,
                "mean_tier_stress_r":sum(r["tier_net"] for r in rs)/n if n else None},
                "portfolio_cap3":evaluate(rs,[t+DELAY for t in times[part]],3)}
        result["path_audit"]=trace_gate(rows,variants["volatility_gate"],loc,btc,output,part)
        report["results"][part]=result
    report["limitations"].extend(["Post-stop trajectories are diagnostic counterfactual observations, not realized or achievable returns.",
        "Recovery requires a target touch in a later full candle; same-stop-candle target touches are separately counted, not asserted as recovery.",
        "Pre-target adverse excursion lower/upper bounds exclude/include uncertain same-candle adverse extrema; gap-open target has exact prior bound.",
        "ATR/price and confirmation magnitude bins are fixed descriptive groups, no threshold selection or stop widening.",
        "All candidate trajectories overlap, and the 18-trade selected portfolios are small. No independent holdout."])
    output.mkdir(parents=True,exist_ok=True)
    (output/"summary.json").write_text(json.dumps(report,indent=2,allow_nan=False))
    print(json.dumps(report,indent=2,allow_nan=False),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for name in ("raw","g","h","i","output"):
        p.add_argument("--"+name,type=Path,required=True)
    a=p.parse_args()
    run(a.raw,a.g,a.h,a.i,a.output)
