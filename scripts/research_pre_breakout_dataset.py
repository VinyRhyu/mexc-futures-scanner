"""E2: offline, causal snapshots and separate diagnostic barrier labels."""
from __future__ import annotations
import argparse
from collections import Counter
import csv
from decimal import Decimal
import gzip
import hashlib
import json
import math
from pathlib import Path
from statistics import median, pstdev
from mexc_scanner.models import Candle, D, DataError
from mexc_scanner.market import atr

HORIZONS = (15,30,60)
STEP = 300
WARM = 48 * 900


def load_raw(path, expected_hash):
    bars, digest = {}, hashlib.sha256()
    with gzip.open(path, "rb") as source:
        for line in source:
            digest.update(line)
            c = Candle.from_dict(json.loads(line))
            c.validate()
            if c.tf != 60 or c.ts in bars:
                raise DataError("invalid M1 key")
            bars[c.ts] = c
    if digest.hexdigest() != expected_hash:
        raise DataError("raw digest mismatch")
    return bars


def contiguous(bars, left, right):
    if left % 60 or right % 60 or right <= left:
        raise ValueError("invalid M1 range")
    try:
        return [bars[t] for t in range(left,right,60)]
    except KeyError:
        return None


def aggregate15(bars):
    out = []
    for i in range(0,len(bars),15):
        g = bars[i:i+15]
        if len(g)!=15 or g[0].ts%900 or any(a.end!=b.ts for a,b in zip(g,g[1:])):
            raise DataError("M15 aggregation requires aligned complete M1")
        out.append(Candle(g[0].ts,900,g[0].open,max(x.high for x in g),
                          min(x.low for x in g),g[-1].close,sum(x.volume for x in g)))
    return out


def features(bars, btc, t):
    # All input candles end <= t. ATR is 48-bar Wilder warmup, finite and fixed.
    qend = t//900*900
    hist = contiguous(bars,qend-WARM,qend)
    m = contiguous(bars,t-61*60,t)
    b = contiguous(btc,t-61*60,t)
    if hist is None or m is None or b is None:
        return None
    a = atr(aggregate15(hist),14)[-1]
    if a is None or a<=0:
        return None
    closes = [float(x.close) for x in m]
    bc = [float(x.close) for x in b]
    r = [math.log(y/x) for x,y in zip(closes,closes[1:])]
    lo,hi = min(x.low for x in m[:-1]),max(x.high for x in m[:-1])
    last = m[-1]
    med = median(x.volume for x in m[:-1])
    rv60 = pstdev(r)
    row = {"atr15":str(a),"inside_prior_range":int(lo<last.close<hi),
           "range_atr":float((hi-lo)/a),
           "range_position":float((last.close-lo)/(hi-lo)) if hi>lo else None,
           "rv15":pstdev(r[-15:]),"rv60":rv60,
           "rv_ratio":pstdev(r[-15:])/rv60 if rv60 else None,
           "relative_volume":float(last.volume/med) if med else None,
           "body_atr":float((last.close-last.open)/a),
           "upper_wick_atr":float((last.high-max(last.open,last.close))/a),
           "lower_wick_atr":float((min(last.open,last.close)-last.low)/a)}
    for n in (1,5,15,30,60):
        row[f"ret_{n}"] = closes[-1]/closes[-1-n]-1
        row[f"btc_ret_{n}"] = bc[-1]/bc[-1-n]-1
        row[f"rel_btc_{n}"] = row[f"ret_{n}"]-row[f"btc_ret_{n}"]
    return row


def label(bars,t,a,side,horizon,end):
    # Delay by one full minute because the live collector requires closed-bar grace.
    entry_t = t+60
    finish = entry_t+horizon*60
    if finish>end:
        return {"outcome":"CENSORED"}
    seq = contiguous(bars,entry_t,finish)
    if seq is None:
        return {"outcome":"CENSORED"}
    sign = D(1) if side=="LONG" else D(-1)
    entry = seq[0].open
    stop,target = entry-sign*a,entry+sign*D("1.5")*a
    if min(stop,target)<=0:
        return {"outcome":"INVALID_GEOMETRY"}
    outcome,exit_price,exit_end = "TIMEOUT",seq[-1].close,seq[-1].end
    mfe,mae = D(0),D(0)
    for c in seq:
        # At open a barrier crossing is observable before intrabar extremes.
        open_r = sign*(c.open-entry)/a
        if open_r<=-1:
            outcome,exit_price,exit_end = "SL",c.open,c.ts
            break
        if open_r>=D("1.5"):
            outcome,exit_price,exit_end = "TP",target,c.ts
            break
        fav = sign*((c.high if sign>0 else c.low)-entry)/a
        adv = sign*((c.low if sign>0 else c.high)-entry)/a
        # Conservative SL-first when both intrabar barriers touched.
        if adv<=-1:
            outcome,exit_price,exit_end = "SL",stop,c.end
            break
        if fav>=D("1.5"):
            outcome,exit_price,exit_end = "TP",target,c.end
            break
        mfe,mae = max(mfe,fav),min(mae,adv)
    return {"outcome":outcome,"entry_ts":entry_t,"exit_ts":exit_end,
            "entry":str(entry),"stop":str(stop),"target":str(target),"exit":str(exit_price),
            "gross_r":str(sign*(exit_price-entry)/a),
            "mfe_before_exit_bar_r":str(mfe),"mae_before_exit_bar_r":str(mae)}


LABEL_FIELDS = ["symbol","asof_utc","side","horizon","outcome","entry_ts","exit_ts",
                "entry","stop","target","exit","gross_r","mfe_before_exit_bar_r","mae_before_exit_bar_r"]


def run(source,output):
    audit = json.loads((source/"coverage.json").read_text())
    output.mkdir(parents=True,exist_ok=True)
    start,end = audit["start"],audit["end_exclusive"]
    btc_meta = audit["symbols"]["BTC_USDT"]
    btc = load_raw(source/btc_meta["raw_file"],btc_meta["sha256_uncompressed"])
    summary = {"source_run":45432136926,"start":start,"end_exclusive":end,
               "primary_horizon":30,"symbols":{},
               "limitations":["Fixed six-symbol pilot, historical universe not reconstructed.",
                              "Inside-range is geometric proxy only; PRD confirmation state not replayed.",
                              "Gross barriers only, continuous prices, no historical tick/fees/funding or portfolio.",
                              "One-minute entry delay; OHLC SL-first; MFE/MAE exclude exit bar.",
                              "No model training or profitability inference."]}
    with gzip.open(output/"features.csv.gz","wt",newline="") as ff, gzip.open(output/"labels.csv.gz","wt",newline="") as lf:
        fw = None
        lw = csv.DictWriter(lf,fieldnames=LABEL_FIELDS)
        lw.writeheader()
        for s,meta in audit["symbols"].items():
            bars = btc if s=="BTC_USDT" else load_raw(source/meta["raw_file"],meta["sha256_uncompressed"])
            counts = Counter()
            observed = sorted(t for t in bars if start<=t<end)
            gaps = sum(b-a!=60 for a,b in zip(observed,observed[1:]))
            # All scheduled snapshots, even when data absent or outside range.
            for t in range(start,end,STEP):
                f = features(bars,btc,t)
                if f is None:
                    counts["missing_features"]+=1
                    continue
                counts["snapshots"]+=1
                counts["inside_prior_range"]+=f["inside_prior_range"]
                row = {"symbol":s,"asof_utc":t,**f}
                if fw is None:
                    fw = csv.DictWriter(ff,fieldnames=list(row))
                    fw.writeheader()
                fw.writerow(row)
                for h in HORIZONS:
                    for side in ("LONG","SHORT"):
                        v=label(bars,t,D(f["atr15"]),side,h,end)
                        counts[f"{side}_{h}_{v['outcome']}"]+=1
                        lw.writerow({"symbol":s,"asof_utc":t,"side":side,"horizon":h,**v})
            summary["symbols"][s]={"first_ts":min(observed,default=None),
                                   "last_ts":max(observed,default=None),
                                   "internal_gaps":gaps,"counts":dict(counts)}
            print(json.dumps({"symbol":s,**summary["symbols"][s]}),flush=True)
    (output/"summary.json").write_text(json.dumps(summary,indent=2))
    if not sum(x["counts"].get("snapshots",0) for x in summary["symbols"].values()):
        raise SystemExit("No causal snapshots")
    return summary


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--input",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    args=p.parse_args()
    run(args.input,args.output)
