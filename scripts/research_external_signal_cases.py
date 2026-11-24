"""External Telegram signal case study; diagnostic only, not a trained strategy."""
from __future__ import annotations
import argparse,json,math
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from statistics import median
from mexc_scanner.mexc import MexcClient
from mexc_scanner.models import D
from scripts.research_pre_breakout_coverage import collect,save_raw
from scripts.research_pre_breakout_dataset import load_raw,features,contiguous
from scripts.research_universe_transfer import sources
from scripts.research_outcome_patterns import pattern_features
from scripts.research_amplitude_240 import inputs

LOCAL=ZoneInfo("America/Sao_Paulo")
DAY=86400
CASES=(
 ("KERNEL","2026-11-20 10:02","SHORT",25,("0.05113","0.05008","0.04904","0.04800"),"0.05920",("KERNEL_USDT",)),
 ("ORCA","2026-11-22 10:44","LONG",30,("1.2005","1.2241","1.2476","1.2712"),"1.164",("ORCA_USDT",)),
 ("QNT","2026-11-21 10:02","LONG",20,("136.87","139.56","142.24","144.93"),"134.19",("QNT_USDT",)),
 ("PUMPFUN","2026-11-18 22:27","LONG",30,("0.002618","0.002670","0.002721","0.002772"),"0.002551",("PUMPFUN_USDT","PUMP_USDT")),
)
NEW_CASES=(
 ("WLFI","2026-11-24 10:05","LONG",30,("0.04169","0.04250","0.04332","0.04414"),None,("WLFI_USDT",)),
 ("VVV","2026-11-23 21:57","SHORT",25,("24.176","23.682","23.189","22.695"),None,("VVV_USDT",)),
 ("THETA","2026-11-22 13:12","LONG",30,("0.1289","0.1315","0.1340","0.1365"),None,("THETA_USDT",)),
 ("NAORIS","2026-11-19 12:52","LONG",30,("0.03365","0.03431","0.03497","0.03563"),None,("NAORIS_USDT",)),
 ("NEAR","2026-11-16 10:21","LONG",30,("3.1936","3.2562","3.3189","3.3815"),None,("NEAR_USDT",)),
 ("EVAA","2026-11-15 17:42","LONG",10,("2.7518","2.8057","2.8597"),None,("EVAA_USDT",)),
 ("STRK","2026-11-13 09:40","LONG",30,("0.0373","0.0381","0.0388","0.0395"),None,("STRK_USDT",)),
 ("INJ","2026-11-12 11:43","LONG",25,("7.5674","7.7158","7.8641","8.0125"),None,("INJ_USDT",)),
)
def epoch(x):
    return int(datetime.strptime(x,"%Y-%m-%d %H:%M").replace(tzinfo=LOCAL).timestamp())

def inferred_reference(targets,side):
    sign=D(1) if side=="LONG" else D(-1)
    return [D(v)/(1+sign*D(".02")*(i+1)) for i,v in enumerate(targets)]

def snapshot(bars,btc,t,side):
    # Extra one-minute publication buffer: at signal t, use only bars ending <=t-60.
    k=t-60
    f=features(bars,btc,k)
    if f is None or contiguous(bars,k-7200,k) is None:
        return None
    a=D(f["atr15"]);c=bars[k-60].close
    s=1 if side=="LONG" else -1
    p=pattern_features(bars,k,a)
    out={"atr_pct":100*float(a/c),"range_position_directional":float(f["range_position"]) if s==1 else 1-float(f["range_position"]),
         "rv_ratio":f["rv_ratio"],"range_atr":f["range_atr"],"inside_prior_range":f["inside_prior_range"]}
    for n in (1,5,15,30,60):
        out["signed_ret_"+str(n)]=100*s*f["ret_"+str(n)]
        out["signed_relative_btc_"+str(n)]=100*s*f["rel_btc_"+str(n)]
        out["signed_btc_"+str(n)]=100*s*f["btc_ret_"+str(n)]
    for j,n in enumerate((5,15,30,60)):
        out["volume_ratio_"+str(n)]=p[5*j]
        out["range_atr_"+str(n)]=p[5*j+1]
        out["signed_body_volume_proxy_"+str(n)]=s*p[5*j+3]
        out["signed_body_efficiency_"+str(n)]=s*p[5*j+4]
    return {k:float(v) if v is not None and math.isfinite(float(v)) else None for k,v in out.items()}

def outcome(bars,t,side,horizon=240):
    seq=contiguous(bars,t+60,t+60+horizon*60)
    if seq is None:
        return None
    s=D(1) if side=="LONG" else D(-1);e=seq[0].open
    stop=e*(1-s*D(".01"));tp=e*(1+s*D(".02"))
    status="TIMEOUT";exit_price=seq[-1].close;exit_t=seq[-1].end
    for c in seq:
        if s*(c.open-stop)<=0:
            status="SL";exit_price=c.open;exit_t=c.ts;break
        if s*(c.open-tp)>=0:
            status="TP";exit_price=tp;exit_t=c.ts;break
        adv=c.low if s>0 else c.high
        fav=c.high if s>0 else c.low
        if s*(adv-stop)<=0:
            status="SL";exit_price=stop;exit_t=c.end;break
        if s*(fav-tp)>=0:
            status="TP";exit_price=tp;exit_t=c.end;break
    fav=max(s*((c.high if s>0 else c.low)/e-1) for c in seq)
    adv=min(s*((c.low if s>0 else c.high)/e-1) for c in seq)
    return {"entry":str(e),"status":status,"exit_ts":exit_t,"gross_pct":100*float(s*(exit_price/e-1)),
            "mfe_pct":100*float(max(D(0),fav)),"mae_pct":100*float(min(D(0),adv))}

def touches(bars,t,side,targets,hours):
    seq=contiguous(bars,t+60,t+60+hours*3600)
    if seq is None:
        return None
    s=D(1) if side=="LONG" else D(-1)
    return [next((c.end for c in seq if s*((c.high if s>0 else c.low)-D(v))>=0),None) for v in targets]

def compare(case,controls):
    out={}
    for k,v in case.items():
        allv=[f[k] for f,o in controls if f[k] is not None]
        win=[f[k] for f,o in controls if o["status"]=="TP" and f[k] is not None]
        lose=[f[k] for f,o in controls if o["status"]!="TP" and f[k] is not None]
        out[k]={"signal":v,"control_median":median(allv) if allv else None,
                "tp_median":median(win) if win else None,"non_tp_median":median(lose) if lose else None,
                "percentile":100*(sum(a<v for a in allv)+.5*sum(a==v for a in allv))/len(allv) if v is not None and allv else None}
    return out

def passes(f):
    return all(f.get(k) is not None for k in ("rv_ratio","signed_ret_1","signed_ret_60")) and f["rv_ratio"]<=.75 and f["signed_ret_1"]<0 and f["signed_ret_60"]<0

def extend(client,bars,symbol,left,right,output):
    if right<=left:
        return {"requested":0,"observed":0,"failures":[]}
    fresh,fail,dupes=collect(client,symbol,left,right)
    if any(t in bars and bars[t]!=c for t,c in fresh.items()):
        raise ValueError("frozen/live candle conflict "+symbol)
    bars.update(fresh)
    return {"requested":(right-left)//60,"observed":len(fresh),"failures":fail,
            "duplicates":dupes,"sha256_uncompressed":save_raw(output/(symbol+"-extension.jsonl.gz"),fresh)}

def run(raw,g,h,i,output):
    loc,groups,bands,start,end=sources(raw,g,h,i)
    p,m=loc["BTC_USDT"];btc=load_raw(p/m["raw_file"],m["sha256_uncompressed"])
    client=MexcClient();output.mkdir(parents=True,exist_ok=True)
    closed=(client.server_time()-10)//60*60
    report={"type":"EXTERNAL_SIGNAL_CASE_AUDIT_V2","cases":{},"closed_end":closed,
            "hypothesis":{"rv_ratio_max":.75,"signed_ret_1_negative":True,"signed_ret_60_negative":True},
            "btc_extension":extend(client,btc,"BTC_USDT",end,min(closed,max(epoch(c[1]) for c in NEW_CASES)+DAY+60),output),
            "limitations":["Dates assumed November 2026 Sao Paulo; source exchange and precise entry time unknown.",
               "Twelve profit-selected examples (four discovery, eight new checks); controls are earlier same-symbol same-side decision times, not the signal provider's losing signals.",
               "Screenshot entries separate from inferred target reference; screenshot mark and unrealized PNL do not prove realized profit or signal match.",
               "MEXC candidate PUMP mapping unverified; no automatic alias selection.",
               "Signal features use closed candles ending <= signal minus 1 minute. Simulated entry signal plus 1 minute.",
               "Hypothetical 2% TP/1% SL for diagnostic controls only, no known actual stop; SL first on ambiguous minute, no fees/funding/leverage.",
               "Touch timestamps use minute close, not tick order; targets may already be crossed at simulated entry. No fitting or PRD change."]}
    try:
        catalog={r["symbol"]:r for r in client.contracts()}
    except Exception as e:
        catalog={};report["catalog_error"]=str(e)[:200]
    for name,stamp,side,lev,targets,shot,aliases in (*CASES,*NEW_CASES):
        t=epoch(stamp);refs=inferred_reference(targets,side)
        entry=median(refs)
        c={"local":stamp,"utc":datetime.fromtimestamp(t,ZoneInfo("UTC")).isoformat(),"side":side,"leverage":lev,
           "targets":targets,"reference_by_target":[str(x) for x in refs],"inferred_reference":str(entry),
           "screenshot_entry":shot,"screenshot_entry_vs_reference_pct":100*float(D(shot)/entry-1) if shot is not None else None,
           "group":"discovery" if name in {r[0] for r in CASES} else "new_check","candidates":{}}
        for symbol in aliases:
            if symbol in loc:
                p,m=loc[symbol];bars=load_raw(p/m["raw_file"],m["sha256_uncompressed"]);meta={"source":"frozen_mexc"}
                if t+60+DAY>end:
                    meta["extension"]=extend(client,bars,symbol,end,min(closed,t+60+DAY),output)
            elif symbol in catalog:
                left=t-8*DAY;right=min(closed,t+60+DAY)
                bars,fail,dupes=collect(client,symbol,left,right)
                meta={"source":"live_mexc_historical","requested_minutes":(right-left)//60,"observed":len(bars),
                      "failed_chunks":fail,"duplicates":dupes}
                meta["sha256_uncompressed"]=save_raw(output/(symbol+".jsonl.gz"),bars)
            else:
                c["candidates"][symbol]={"status":"not_in_frozen_universe_or_current_catalog"};continue
            f=snapshot(bars,btc,t,side)
            q={**meta,"catalog_present":symbol in catalog,"status":"ok" if f is not None else "missing_feature_history"}
            if f is None:
                c["candidates"][symbol]=q;continue
            o=outcome(bars,t,side);o24=outcome(bars,t,side,1440)
            controls=[]
            for u in range(t-7*DAY,t-60-240*60+1,900):
                ff=snapshot(bars,btc,u,side);oo=outcome(bars,u,side)
                if ff is not None and oo is not None:
                    controls.append((ff,oo))
            matched=[(ff,oo) for ff,oo in controls if passes(ff)]
            q.update({"hypothesis_pass":passes(f),"matched_control_n":len(matched),"matched_control_tp":sum(oo["status"]=="TP" for _,oo in matched),
                      "atr_above_control_median":f["atr_pct"]>median([ff["atr_pct"] for ff,oo in controls]) if controls else None,
                      "last_known_close":str(bars[t-120].close),"signal_minute_open":str(bars[t].open) if t in bars else None,
                      "reference_vs_last_known_pct":100*float(entry/bars[t-120].close-1),
                      "path_4h":o,"path_24h":o24,"target_touches_4h":touches(bars,t,side,targets,4),
                      "target_touches_24h":touches(bars,t,side,targets,24),
                      "control_n":len(controls),"control_tp":sum(o["status"]=="TP" for _,o in controls),
                      "features":compare(f,controls)})
            c["candidates"][symbol]=q
        report["cases"][name]=c
        print(json.dumps({"case":name,"candidates":{s:{k:v for k,v in q.items() if k!="features"} for s,q in c["candidates"].items()}}),flush=True)
    report["hypothesis_summary"]={}
    for group in ("discovery","new_check"):
        qs=[q for c in report["cases"].values() if c["group"]==group for q in c["candidates"].values() if q["status"]=="ok"]
        report["hypothesis_summary"][group]={"available":len(qs),"pass":sum(q["hypothesis_pass"] for q in qs),
            "controls":sum(q["control_n"] for q in qs),"controls_tp":sum(q["control_tp"] for q in qs),
            "matched_controls":sum(q["matched_control_n"] for q in qs),"matched_controls_tp":sum(q["matched_control_tp"] for q in qs)}
    (output/"summary.json").write_text(json.dumps(report,indent=2,allow_nan=False))
    print(json.dumps(report,indent=2,allow_nan=False),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for k in ("raw","g","h","i","output"):
        p.add_argument("--"+k,type=Path,required=True)
    a=p.parse_args();run(a.raw,a.g,a.h,a.i,a.output)
