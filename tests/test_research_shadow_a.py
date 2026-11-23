"""Regression tests: production state is never changed and no future candles leak."""
from copy import deepcopy
from datetime import datetime,timezone
import unittest

from mexc_scanner.minute_breakout import MODEL,STRATEGY
from mexc_scanner.models import Candle, DataError, D
from scripts.research_shadow_a import candidates_from_state, run, touch_path, unique_events, MAX_STATE_AGE


END=1795392000  # aligned UTC hour, synthetic clock base
CLOCK=END+20


def candle(ts,tf,op="100",hi="100",lo="100",cl="100"):
    return Candle(ts,tf,D(op),D(hi),D(lo),D(cl),D(1))


def fake_state(signal=END,mode=MODEL,status="EVENTO_PASSADO"):
    return {
        "active_signal_model":mode,
        "last_success":CLOCK-30,
        "wallet":{"private_balance":"DO_NOT_EXPORT"},
        "plans":{
            "existing": {
                "id":"existing","symbol":"TEST_USDT","strategy":STRATEGY,
                "side":"LONG","status":status,
                "variants":{"CONFIRMADA":{
                    "triggered_at":signal,"entry_low":"99","entry_high":"110",
                    "stop":"95","target":"120","status":"ENCERRADA"}}
            },
            "other": {
                "id":"other","symbol":"BAD_USDT","strategy":"CONTINUACAO",
                "side":"LONG","variants":{"CONFIRMADA":{"triggered_at":signal}}
            }
        }
    }


class FakePublicClient:
    def __init__(self):
        self.calls=[]
        self.m=[candle(END-60*(1100-i),60) for i in range(1100)]
        last=self.m[-1]
        self.m[-1]=candle(last.ts,60,op="100",hi="105",lo="100",cl="105")
        self.q=[candle(END-900*(560-i),900) for i in range(560)]
        last=self.q[-1]
        self.q[-1]=candle(last.ts,900,op="100",hi="105",lo="100",cl="105")
        self.h=[candle(END-3600*(260-i),3600) for i in range(260)]
        last=self.h[-1]
        self.h[-1]=candle(last.ts,3600,op="100",hi="105",lo="100",cl="105")

    def candles(self,symbol,interval,count,now):
        self.calls.append((symbol,interval,count,now))
        vals={"Min1":self.m, "Min15":self.q,"Min60":self.h}[interval]
        if count!=len(vals):
            raise AssertionError("unexpected synthetic count")
        return {key: [c.ts if key=="time" else
                      str(c.open if key=="open" else c.high if key=="high" else
                          c.low if key=="low" else c.close if key=="close" else c.volume)
                      for c in vals] for key in
                ("time","open","high","low","close","vol")}


class ShadowATests(unittest.TestCase):
    def test_recovers_closed_confirmations_even_if_later_expired(self):
        s=fake_state()
        rows=candidates_from_state(s,CLOCK)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["symbol"],"TEST_USDT")
        self.assertEqual(rows[0]["snapshot_status"],"EVENTO_PASSADO")
        self.assertNotIn("wallet",rows[0])

    def test_stale_state_fails_closed(self):
        s=fake_state()
        s["last_success"]=CLOCK-MAX_STATE_AGE-1
        with self.assertRaisesRegex(DataError,"stale"):
            candidates_from_state(s,CLOCK)

    def test_other_model_fails_closed(self):
        with self.assertRaisesRegex(DataError,"not running"):
            candidates_from_state(fake_state(mode="legacy"),CLOCK)

    def test_no_signals_is_valid_no_evidence(self):
        state=fake_state(signal=END-13*3600)
        client=FakePublicClient()
        result=run(state,client,CLOCK)
        self.assertEqual(result["signals_found"],0)
        self.assertEqual(result["classification_status"],"NO_SIGNALS_IN_LOOKBACK")
        self.assertEqual(client.calls,[])

    def test_public_causal_filter_and_no_mutation(self):
        state=fake_state()
        orig=deepcopy(state)
        client=FakePublicClient()
        result=run(state,client,CLOCK)
        self.assertEqual(state,orig)
        self.assertEqual(result["classification_status"],"COMPLETE")
        self.assertEqual(result["signals_found"],1)
        self.assertEqual(result["shadow_rejected"],1)
        self.assertFalse(result["fresh_prospective_sample"])
        self.assertEqual(result["signals"][0]["shadow"]["verdict_A"],"POSSIVEL_ENTRADA_TARDIA")
        self.assertEqual(len(client.calls),3)
        rendered=str(result)
        self.assertNotIn("private_balance",rendered)
        self.assertNotIn("DO_NOT_EXPORT",rendered)
        self.assertNotIn("net_usdt",rendered)

    def test_unique_market_events_keep_distinct_plan_levels(self):
        base={"symbol":"AVAX_USDT","side":"SHORT","signal_at":END,
              "stop":"7.00","target":"6.70","shadow":{"verdict_A":"POSSIVEL_ENTRADA_TARDIA",
              "path_status":"TOCOU_TP"}}
        duplicate=deepcopy(base)
        duplicate["stop"]="7.02"
        duplicate["shadow"]["path_status"]="TOCOU_SL"
        other=deepcopy(base)
        other["symbol"]="ARB_USDT"
        other["shadow"]["verdict_A"]="SEM_VETO_A"
        events=unique_events([base,duplicate,other])
        self.assertEqual(len(events),2)
        avax=next(x for x in events if x["symbol"]=="AVAX_USDT")
        self.assertEqual(avax["plan_count"],2)
        self.assertTrue(avax["different_stops_or_targets"])
        self.assertEqual(avax["price_path_by_plan"],{"TOCOU_TP":1,"TOCOU_SL":1})
        self.assertTrue(avax["not_a_financial_trade"])

    def test_unique_market_events_reject_conflicting_filter_decisions(self):
        a={"symbol":"TEST_USDT","side":"LONG","signal_at":END,
           "stop":"90","target":"120","shadow":{"verdict_A":"SEM_VETO_A",
           "path_status":"TOCOU_TP"}}
        b=deepcopy(a)
        b["shadow"]["verdict_A"]="POSSIVEL_ENTRADA_TARDIA"
        with self.assertRaisesRegex(DataError,"inconsistent"):
            unique_events([a,b])

    def test_path_observation_is_not_profit_claim(self):
        a=candle(END-3600,60)
        b=candle(END-3540,60,op="100",hi="121",lo="94",cl="110")
        result=touch_path([a,b],0,"LONG","95","120",CLOCK)
        self.assertEqual(result["path_status"],"AMBIGUO_STOP_PRIMEIRO")
        self.assertNotIn("net_r",result)
        self.assertFalse(result["window_complete"])


if __name__=="__main__":
    unittest.main()
