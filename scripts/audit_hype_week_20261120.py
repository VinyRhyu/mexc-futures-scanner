"""HYPE_USDT Nov16-20 2026: frozen F causal, closed-candle paper trade-by-trade report.

Standalone research only. NO strategy modification, trading, Telegram, or main.
Clock cutoff recorded 2026-11-20 19:10 BRT (22:10 UTC).
"""
from __future__ import annotations
import bisect
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from scripts.audit_confluence_extended import candles, select_portfolio
from scripts.audit_confluence_v3 import (
    FIVE_MS, HOUR_MS, candidate_f, execute, iso, replay_structural,
)
from scripts.audit_confluence_pilot import Parameters

BRT = ZoneInfo("America/Sao_Paulo")
START = "2026-11-16T03:00:00+00:00"  # Mon 00:00 BRT
END = "2026-11-20T22:10:00+00:00"    # Fri 19:10 BRT; last fully closed M5
SYMBOL = "HYPE_USDT"


def brt(utc):
    return datetime.fromisoformat(utc).astimezone(BRT).strftime("%d/%m/%Y %H:%M")


def report_trade(five,hourly,t):
    at={iso(int(c[0])+FIVE_MS):i for i,c in enumerate(five)}
    i=at[t["signal_at"]]
    s=candidate_f(five,hourly,i)
    if s is None:
        raise AssertionError(f"F setup not reproducible {t['signal_at']}")
    end_ms=int(datetime.fromisoformat(t["exit_at"]).timestamp()*1000)
    end_i=bisect.bisect_left([int(c[0]) for c in five],end_ms)
    if end_i <= i:
        raise AssertionError("Exit must be after signal")
    path=five[i+1:end_i+1]
    entry=float(t["entry"])
    minimum=min(float(c[3]) for c in path)
    maximum=max(float(c[2]) for c in path)
    exit_px=(float(t["target"]) if t["result"]=="TP"
             else float(t["stop"]) if t["result"]=="SL"
             else float(five[end_i][4]) if t["result"]=="TIME" else None)
    return {
        "signal_brt":brt(t["signal_at"]),
        "entry_brt":brt(t["entry_at"]),
        "exit_candle_start_brt":brt(t["exit_at"]),
        "exit_candle_end_brt":brt(iso(end_ms+FIVE_MS)),
        "side":"SHORT",
        "result":t["result"],
        "signal_close":float(five[i][4]),
        "resistance_prior_2h":round(float(s["level"]),8),
        "volume_x":round(float(s["volume_ratio"]),3),
        "atr14":round(float(s["atr"]),8),
        "entry":entry,
        "tp":float(t["target"]),
        "sl":float(t["stop"]),
        "exit_price":exit_px,
        "gross_move_pct":round(100*(entry-exit_px)/entry,4) if exit_px is not None else None,
        "net_r":float(t["net_r"]) if t["net_r"] is not None else -1.0,
        "max_favorable_pct":round(100*(entry-minimum)/entry,4),
        "max_adverse_pct":round(100*(maximum-entry)/entry,4),
        "min_low_after_entry":minimum,
        "max_high_after_entry":maximum,
        "bars_open":end_i-i,
        "net_rr_at_entry":float(t["net_rr_ex_ante"]),
        "exit_time_not_exact":"TP/SL detected from 5m OHLC, shown candle is a 5-minute interval",
    }


def run():
    start=int(datetime.fromisoformat(START).timestamp())
    end=int(datetime.fromisoformat(END).timestamp())
    end_hour=end-end%3600
    if end_hour != end-600:
        raise RuntimeError("Cutoff changed; verify end_hour without using an open H1 candle")
    print("HYPE_WEEK_SOURCE "+json.dumps({
        "symbol":SYMBOL,"start_utc":START,"end_exclusive_utc":END,
        "start_brt":brt(START),"end_brt":brt(END),
        "H1_last_close_utc":iso(end_hour*1000),
        "strategy":"F_sweep_rejection (no modifications)",
        "taker_per_side":Parameters().taker_fee_each,
        "slippage_per_side":Parameters().slippage_each,
        "maker_orders":False, "hold_bars":24, "target_gross_R":1.8,
    }),flush=True)
    h=candles(SYMBOL,"Min60",start-160*3600,end_hour)
    five=candles(SYMBOL,"Min5",start-55*300,end)
    trades=replay_structural(five,h,"F_sweep_rejection")
    eligible=[t for t in trades if START<=t["signal_at"]<END]
    detailed=[report_trade(five,h,t) for t in eligible]
    total=select_portfolio([{**t,"symbol":SYMBOL} for t in eligible])
    direct,rr_rejected,potential=[],[],[]
    next_allowed=25
    for i in range(25,len(five)):
        event_at=iso(int(five[i][0])+FIVE_MS)
        if not START<=event_at<END:
            continue
        s=candidate_f(five,h,i)
        if s is None:
            continue
        direct.append(s)
        if i+1>=len(five):
            potential.append({"signal_brt":brt(event_at),"status":"SIGNAL_AT_LAST_CLOSED_BAR_NO_NEXT_OPEN",
                            "volume_x":round(s["volume_ratio"],3)})
            continue
        entry=float(five[i+1][1]);stop=float(s["stop_raw"]);risk=stop-entry
        if risk<=0:
            rr_rejected.append({"signal_brt":brt(event_at),"reason":"nonpositive_risk"})
            continue
        cost=2*entry*(Parameters().taker_fee_each+Parameters().slippage_each)
        rr=(1.8*risk-cost)/(risk+cost)
        if rr<1.2:
            rr_rejected.append({"signal_brt":brt(event_at),"reason":"net_rr_lt_1_2",
                                "entry":entry,"sl":round(stop,8),"rr_net":round(rr,3)})
            continue
        if i+24>=len(five):
            end_idx=len(five)-1
            visited=five[i+1:end_idx+1]
            if not visited:continue
            state="PENDING"
            first_trigger=None
            for k in range(i+1,end_idx+1):
                bar=five[k]
                if float(bar[2])>=stop or float(bar[3])<=entry-1.8*risk:
                    state="INTRAWINDOW_EXIT"
                    first_trigger=k
                    break
            if first_trigger is None:
                potential.append({"signal_brt":brt(event_at),"entry_brt":brt(iso(int(five[i+1][0]))),
                                  "entry":entry,"tp":round(entry-1.8*risk,8),
                                  "sl":round(stop,8),"state":"OPEN_UNTIL_CUTOFF",
                                  "observed_bars":len(visited)})
            else:
                potential.append({"signal_brt":brt(event_at),"entry_brt":brt(iso(int(five[i+1][0]))),
                                  "entry":entry,"tp":round(entry-1.8*risk,8),
                                  "sl":round(stop,8),"state":"EXIT_WITHIN_LAST_2H_NOT_IN_ORIGINAL_REPLAY",
                                  "exit_candle_brt":brt(iso(int(five[first_trigger][0]))),
                                  "which":"SL" if float(five[first_trigger][2])>=stop else "TP"})
    close_rows=[c for c in five if start*1000<=int(c[0])<end*1000]
    by_day={}
    for bar in close_rows:
        day=datetime.fromtimestamp(int(bar[0])/1000,BRT).strftime("%d/%m")
        item=by_day.setdefault(day,{"open":float(bar[1]),"high":-float("inf"),"low":float("inf"),"close":float(bar[4]),"M5":0})
        item["high"]=max(item["high"],float(bar[2]))
        item["low"]=min(item["low"],float(bar[3]))
        item["close"]=float(bar[4])
        item["M5"]+=1
    for v in by_day.values():
        v["movement_open_to_close_pct"]=round(100*(v["close"]/v["open"]-1),3)
    print("HYPE_WEEK_REPORT "+json.dumps({
        "source":{"M5":len(five),"H1":len(h),"week_M5":len(close_rows),
                  "M5_last_closed_utc":iso(int(five[-1][0])+FIVE_MS),
                  "H1_last_closed_utc":iso(int(h[-1][0])+HOUR_MS)},
        "daily_prices_brt":by_day,
        "eligible_complete_trades":len(eligible),
        "portfolio_one_position_only":total,
        "candidate_f_raw_signals":len(direct),
        "rejected_after_next_open":rr_rejected,
        "pending_or_recent":potential,
        "trades":detailed,
        "warnings":[
          "No orders were placed: OHLC MEXC public futures historical paper simulation.",
          "Time of TP/SL means the 5min OHLC candle, not exact tick.",
          "No funding, spread/book liquidity, contract minimum, liquidation, or actual fills.",
          "Original F replay ends 24 M5 bars before dataset end to avoid incomplete outcomes.",
          "If zero selected setups, do not invent a trade.",
        ],
    },sort_keys=True),flush=True)

if __name__=="__main__":
    run()
