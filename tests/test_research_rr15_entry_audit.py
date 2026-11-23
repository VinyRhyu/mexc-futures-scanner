"""Tests for 12-trade ex-ante diagnostic, without network or hidden outcomes."""
import unittest
from decimal import Decimal
from copy import deepcopy
from datetime import datetime,timezone

from mexc_scanner.models import Candle,DataError,D
from scripts.research_rr15_entry_audit import (
    pre_entry_features,audit_selection,audit_summary,as_brt,
)


def candle(ts,tf,op,hi,lo,cl,vol):
    return Candle(ts,tf,D(op),D(hi),D(lo),D(cl),D(vol))


def fixture():
    start=1800000
    m=[candle(start+60*i,60,"100","101","99","100",10) for i in range(242)]
    last=m[240]
    m[240]=candle(last.ts,60,"100","102","99","101",20)
    anchor=(m[240].end//900)*900
    q=[candle(anchor-900*(14-i),900,"100","102","99","100",100)
       for i in range(14)]
    ctx={"m15_atr":"3","m1_signed_4h_extension_atr":"0.4",
         "h1_structure":"INDEFINIDA","A_late":False,"B_against_h1":False}
    return m,q,ctx


def sample(name,symbol,when,rr="1.6",result="-1",end=None):
    exit_at=end or "2026-11-14T01:10:00+00:00"
    return {"plan_id":name,"symbol":symbol,"side":"LONG",
            "signal_at":when,"historical_group":"core_liquidity",
            "stop":"99","target":"103","turnover24":"12000000",
            "exante_features":{"asof_utc":when,
                "M1_volume_vs_prev20":"2.0","M1_body_fraction_of_range":"0.5",
                "M1_close_near_side_fraction":"0.7","M1_range_over_M15_ATR":"0.8",
                "signed_1h_M1_extension_ATR":"0.2","signed_4h_M1_extension_ATR":"1.0",
                "signed_2h_M15_extension_ATR":"0.3","H1_structure":"INDEFINIDA",
                "A_late":False,"B_against_H1":False},
            "wallet_1usdt":{"status":"FILLED_SIMULATED","net_rr":rr,
                             "entry_at":when,"exit_at":exit_at,
                             "entry_fill_estimate":"100","outcome":"STOP" if D(result)<0 else "ALVO",
                             "net_r":result,"net_usdt":str(D(result)/10)}}


class RR15AuditTests(unittest.TestCase):
    def test_no_future_m1_affects_entry_features(self):
        m,q,c=fixture()
        x=pre_entry_features(m,240,q,c,"LONG")
        self.assertEqual(D(x["M1_volume_vs_prev20"]),D(2))
        y=m.copy()
        y[241]=candle(y[241].ts,60,"100","400","1","400",999999)
        self.assertEqual(x,pre_entry_features(y,240,q,c,"LONG"))
        self.assertLessEqual(datetime.fromisoformat(x["asof_utc"]).timestamp(),
                             m[240].end)

    def test_unclosed_quarter_is_rejected(self):
        m,q,c=fixture()
        q.append(candle(m[240].end,900,"100","104","99","102",10))
        with self.assertRaisesRegex(DataError,"future"):
            pre_entry_features(m,240,q,c,"LONG")

    def test_exact_1usdt_rr_filter_precedes_results_and_reallocates(self):
        a=sample("a","BTC_USDT","2026-11-14T01:00:00+00:00",rr="1.2")
        b=sample("b","ETH_USDT","2026-11-14T01:01:00+00:00",rr="1.7")
        c=sample("c","SOL_USDT","2026-11-14T01:20:00+00:00",rr="1.9",
                 end="2026-11-14T01:35:00+00:00")
        a["wallet_1usdt"]["exit_at"]="2026-11-14T01:10:00+00:00"
        b["wallet_1usdt"]["exit_at"]="2026-11-14T01:15:00+00:00"
        ledger,unique,dupes=audit_selection([a,b,c],"H5")
        self.assertEqual((unique,dupes),(3,0))
        self.assertEqual([x["symbol"] for x in ledger],["ETH_USDT","SOL_USDT"])
        b["wallet_1usdt"]["net_r"]="10"
        c["wallet_1usdt"]["net_r"]="10"
        ledger2,_,_=audit_selection([a,b,c],"H5")
        self.assertEqual([x["symbol"] for x in ledger2],["ETH_USDT","SOL_USDT"])

    def test_duplicate_plan_does_not_use_future_winning_outcome(self):
        one=sample("a","BTC_USDT","2026-11-14T01:00:00+00:00",
                   rr="1.6",result="-1")
        two=sample("z","BTC_USDT","2026-11-14T01:00:00+00:00",
                   rr="1.9",result="2.4")
        rows,unique,dupes=audit_selection([two,one],"H5")
        self.assertEqual((len(rows),unique,dupes),(1,1,1))
        self.assertEqual(rows[0]["plan_id"],"a")
        self.assertEqual(rows[0]["net_R"],"-1")

    def test_summary_groups_use_outcome_only_after_selection(self):
        a=sample("a","BTC_USDT","2026-11-14T01:00:00+00:00",
                 result="-1")
        b=sample("b","ETH_USDT","2026-11-14T01:20:00+00:00",
                 result="2",end="2026-11-14T01:40:00+00:00")
        rows,_,_=audit_selection([a,b],"H5")
        out=audit_summary(rows)
        self.assertEqual(out["total"]["wins"],1)
        self.assertEqual(out["winners"]["trades"],1)
        self.assertEqual(out["nonwinners"]["trades"],1)
        self.assertEqual(D(out["total"]["total_net_R"]),D(1))

if __name__=="__main__":
    unittest.main()
