"""MEXC public futures M1 60-day availability PILOT, not a full 24-symbol dataset.

The exchange documents <=2,000 bars per request but not a guarantee of
continuous full 60-day history. Anchor windows and optional BTC full sweep are
strict and read-only; never replace absent candles with synthetic data.
"""
from __future__ import annotations

from datetime import datetime,timezone
from pathlib import Path
import json

from scripts.research_liquidity_cohort import fetch_range,iso
from scripts.research_production_universe import ResearchMexcClient

START=datetime(2026,9,24,tzinfo=timezone.utc).timestamp()
END=datetime(2026,11,23,tzinfo=timezone.utc).timestamp()
SYMBOLS=("BTC_USDT","ETH_USDT","SOL_USDT")
ANCHORS=("2026-09-24T00:00:00+00:00","2026-10-01T00:00:00+00:00",
         "2026-10-11T00:00:00+00:00","2026-10-21T00:00:00+00:00",
         "2026-10-31T00:00:00+00:00","2026-11-10T00:00:00+00:00",
         "2026-11-22T00:00:00+00:00")


def probe(client,full_btc_if_possible=True):
    report={
        "schema":1,"period_start":iso(int(START)),"period_end_exclusive":iso(int(END)),
        "days_requested":60,"endpoint":"GET /api/v1/contract/kline/{symbol} Min1",
        "source":"MEXC public historical OHLC, strictly validated",
        "symbols":{},"full_60_days_BTC_verified":False,
        "full_60_days_all_24_verified":False,
        "historical_top50_membership_verified":False,
        "conclusion":"UNVERIFIED",
    }
    all_anchors=True
    for symbol in SYMBOLS:
        sample=[]
        for at in ANCHORS:
            a=int(datetime.fromisoformat(at).timestamp())
            item={"symbol":symbol,"start":at,"expected_bars":240}
            try:
                m,amounts=fetch_range(client,symbol,60,a,a+240*60)
                if len(m)!=240 or len(amounts)!=240:
                    raise ValueError("sample range not continuous")
                item.update(status="COMPLETE",received_bars=len(m),
                            any_turnover=any(x>0 for x in amounts))
            except (ValueError,KeyError,TimeoutError,OSError,RuntimeError) as exc:
                item.update(status="INCOMPLETE",received_bars=None,
                            reason=type(exc).__name__+": "+str(exc)[:160])
                all_anchors=False
            sample.append(item)
        report["symbols"][symbol]=sample
    if full_btc_if_possible and all_anchors:
        try:
            m,amounts=fetch_range(client,"BTC_USDT",60,int(START),int(END))
            report["full_60_days_BTC_verified"]=len(m)==86400 and len(amounts)==86400
            report["btc_full_count"]=len(m)
        except (ValueError,KeyError,TimeoutError,OSError,RuntimeError) as exc:
            report["btc_full_error"]=type(exc).__name__+": "+str(exc)[:160]
    report["anchor_passed"]=sum(
        x["status"]=="COMPLETE" for values in report["symbols"].values() for x in values)
    report["anchor_total"]=len(SYMBOLS)*len(ANCHORS)
    report["conclusion"]=(
        "PILOT_BTC_FULL_ONLY_NOT_FULL_UNIVERSE" if report["full_60_days_BTC_verified"]
        else "60_DAY_FULL_HISTORY_NOT_VERIFIED")
    return report


def main():
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",type=Path,default=Path("reports/history_60d_probe.json"))
    args=ap.parse_args()
    result=probe(ResearchMexcClient())
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print("HISTORY_60D_PILOT="+json.dumps({
        "anchors_complete":result["anchor_passed"],"anchors_total":result["anchor_total"],
        "btc_full":result["full_60_days_BTC_verified"],
        "conclusion":result["conclusion"]
    },ensure_ascii=False),flush=True)
    # A gap is a RESEARCH RESULT, not a successful 60-day validation.


if __name__=="__main__":
    main()
