"""Research-only pre-registered H1/M5 SHORT regime variants over 42 continuous days.

Never sends notifications/orders; never modifies scanner production state.
Hypotheses and thresholds are frozen in docs/confluence-v2-preregistered.md.
"""
from __future__ import annotations
import argparse
import json
import time
from collections import Counter
from datetime import datetime, timezone, timedelta
from scripts.audit_confluence_extended import candles, select_portfolio
from scripts.audit_confluence_pilot import Parameters, replay, scan_at, _ema_last

MS_HOUR = 3_600_000
MS_FOUR = 14_400_000
VARIANTS = ("A_baseline", "B_h4", "C_btc", "D_h4_btc", "E_volume")
SYMBOLS = ("TAO", "SOL", "AVAX", "ENA", "DOT", "ZEC", "HYPE", "AAVE", "BTC", "ETH")


def h4_bias_down(hourly: list, decision_ms: int) -> bool:
    """Only complete four-hour periods, including those known by decision time."""
    groups = {}
    for h in hourly:
        if h[0] + MS_HOUR > decision_ms:
            break
        start = h[0] // MS_FOUR * MS_FOUR
        if start + MS_FOUR > decision_ms:
            continue
        groups.setdefault(start, []).append(h)
    bars = []
    for start, hourset in sorted(groups.items()):
        if len(hourset) != 4:
            continue
        if [h[0] for h in hourset] != [start + x*MS_HOUR for x in range(4)]:
            continue
        bars.append(float(hourset[-1][4]))
    if len(bars) < 21:
        return False
    ema_now = _ema_last(bars, 20)
    ema_before = _ema_last(bars[:-1], 20)
    return bars[-1] < ema_now and ema_now < ema_before


def btc_bias_down(btc_h1: list, decision_ms: int) -> bool:
    known = [h for h in btc_h1 if h[0] + MS_HOUR <= decision_ms]
    if len(known) < 20:
        return False
    return float(known[-1][4]) < _ema_last([float(h[4]) for h in known], 20)


def gate_for(variant: str, btc_h1: list):
    def gate(check, five, hourly, i):
        if variant == "A_baseline":
            return True
        decision_ms = five[i][0] + 300_000
        if variant in ("B_h4", "D_h4_btc") and not h4_bias_down(hourly, decision_ms):
            return False
        if variant in ("C_btc", "D_h4_btc") and not btc_bias_down(btc_h1, decision_ms):
            return False
        if variant == "E_volume":
            if check["relative_quote_volume"] < 2.0:
                return False
            if check["range_to_prior_atr"] is None or check["range_to_prior_atr"] < .75:
                return False
        return True
    return gate


def select_summary(trades, start, end):
    chosen = select_portfolio(trades)
    counts = dict(Counter(t["result"] for t in trades))
    return {
        "n_candidates": len(trades), "outcomes": counts,
        "candidate_net_R_sum": round(sum(t["net_r"] if t["net_r"] is not None else -1 for t in trades), 3),
        "n_selected": chosen["n"], "portfolio_R": chosen["net_R_sum"],
        "portfolio_return_pct": chosen["return_pct_at_1pct_risk"],
        "max_drawdown_pct": chosen["max_drawdown_pct_at_1pct_risk"],
        "signals_per_calendar_day": round(chosen["n"] / ((end-start)/86400), 3),
    }


def run(end_iso="2026-11-20T11:00:00+00:00", days=42):
    end = int(datetime.fromisoformat(end_iso).timestamp())
    start = end-days*86400
    split = start + 21*86400
    start_s = datetime.fromtimestamp(start, timezone.utc).isoformat()
    split_s = datetime.fromtimestamp(split, timezone.utc).isoformat()
    end_s = datetime.fromtimestamp(end, timezone.utc).isoformat()

    print("PREFROZEN_REGIME_VARIANTS " + json.dumps({
        "names": VARIANTS, "assets": SYMBOLS, "start": start_s,
        "split": split_s, "end": end_s,
        "hypotheses_file": "docs/confluence-v2-preregistered.md",
    }), flush=True)

    store = {}
    for s in SYMBOLS:
        sym=s+"_USDT"
        t0=time.monotonic()
        try:
            # >20 full H4 bars for the very first evaluated M5 candle.
            h = candles(sym, "Min60", start-160*3600, end)
            m = candles(sym, "Min5", start-25*300, end)
            data = {"venue": "mexc_swap", "collected_utc": end_s,
                    "closed_candles_only": True, "symbol": sym,
                    "candles": {"5m": m, "1h": h}}
            checks = [scan_at(m,h,i) if i>=20 else {"prealert":False, "trigger":False}
                      for i in range(len(m))]
            store[sym] = {"data": data, "cache": checks}
            print(f"DATA {sym} M5={len(m)} H1={len(h)} "
                  f"triggers={sum(x.get('trigger',False) for x in checks)} "
                  f"fetch_sec={time.monotonic()-t0:.1f}", flush=True)
        except Exception as e:
            print(f"DATA_FAIL {sym} {type(e).__name__}: {str(e)[:220]}", flush=True)

    if len(store) != len(SYMBOLS):
        raise RuntimeError("Refusing partial evaluation: not all historical feeds available")
    btc_h1=store["BTC_USDT"]["data"]["candles"]["1h"]
    all_results={}
    for variant in VARIANTS:
        t0=time.monotonic()
        trades=[]
        per_asset=[]
        for sym,src in store.items():
            gate=gate_for(variant,btc_h1)
            result=replay(src["data"], Parameters(), gate=gate, analysis_cache=src["cache"])
            chosen=[dict(x, symbol=sym) for x in result["trades"]
                    if start_s <= x["signal_at"] < end_s]
            trades.extend(chosen)
            per_asset.append({"symbol":sym, "n":len(chosen),
                              "net_R":round(sum(t["net_r"] if t["net_r"] is not None else -1
                                                 for t in chosen), 3),
                              "TP":sum(t["result"]=="TP" for t in chosen),
                              "SL":sum(t["result"]=="SL" for t in chosen)})
        trials={}
        for name, low, high in (("early21", start_s, split_s),
                                ("late21", split_s, end_s),
                                ("full42",start_s,end_s)):
            selected=[t for t in trades if low <= t["signal_at"] < high]
            trials[name]=select_summary(selected,
                                        datetime.fromisoformat(low).timestamp(),
                                        datetime.fromisoformat(high).timestamp())
        taos=[t for t in trades if t["symbol"]=="TAO_USDT" and
              "2026-11-20T01:00:00" <= t["signal_at"] < "2026-11-20T02:10:00"]
        total=trials["full42"]
        meets=(all(trials[k]["portfolio_return_pct"]>0 for k in ("early21","late21"))
               and total["max_drawdown_pct"]<=10 and total["n_selected"]>=30
               and total["signals_per_calendar_day"]<=3
               and total["portfolio_return_pct"] > -21.156)
        all_results[variant]={"windows":trials,
                              "tao_event": [{"signal_at":t["signal_at"], "result":t["result"],
                                             "net_R":t["net_r"]} for t in taos],
                              "per_asset":per_asset, "pass_exploratory":meets}
        print("VARIANT_METRICS "+json.dumps({
            "variant":variant,"windows":trials,"tao_event":all_results[variant]["tao_event"],
            "pass_exploratory":meets, "per_asset":per_asset,
            "duration_sec":round(time.monotonic()-t0,1),
        },sort_keys=True),flush=True)

    print("ALL_VARIANTS_SUMMARY " + json.dumps({
        "periods": (start_s,split_s,end_s), "assets":len(store),
        "results":{name:{"windows":r["windows"],"tao_event":r["tao_event"],
                         "pass_exploratory":r["pass_exploratory"]}
                   for name,r in all_results.items()}
    },sort_keys=True),flush=True)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--end",default="2026-11-20T11:00:00+00:00")
    ap.add_argument("--days",type=int,default=42)
    args=ap.parse_args()
    if args.days != 42:
        ap.error("This pre-registered experiment is fixed to 42 days")
    run(args.end,args.days)


if __name__ == "__main__":
    main()
