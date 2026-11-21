"""No-lookahead common stop/TP tests for frozen HYPE WATCH execution study."""
import copy
import unittest
from scripts.audit_confluence_v3 import FIVE_MS
from scripts.audit_hype_m1_trend import ONE_MS
from scripts.audit_hype_m1_fixed_watch_risk import (
    frozen_watch_levels, fixed_execute, portfolio,
)

class HypeFixedWatchRiskTest(unittest.TestCase):
    def setUp(self):
        self.m5=[[i*FIVE_MS,100.0,100.3,99.7,100.0,1.0,100]
                 for i in range(100)]
        self.w={"i":50,"side":"LONG","at_ms":51*FIVE_MS,"family":"BREAK"}
        self.m1=[[i*ONE_MS,100.,100.1,99.9,100.,1,100]
                 for i in range(440)]
        # close time 52*FIVE_MS = 260 min for synthetic confirm
        self.sig={"signal_index":260,"signal_at":"1970-01-01T04:20:00+00:00",
                  "side":"LONG"}
        self.state={"m1e":[int(c[0])+ONE_MS for c in self.m1]}
        self.w["at_ms"]=50*FIVE_MS

    def test_anchor_stop_target_causal(self):
        a=frozen_watch_levels(self.m5,self.w)
        m=copy.deepcopy(self.m5)
        for candle in m[51:]:
            candle[2],candle[3],candle[4]=999,1,800
        self.assertEqual(a,frozen_watch_levels(m,self.w))
        self.assertEqual(a,frozen_watch_levels(self.m5[:51],self.w))
        self.assertLess(a["stop"],a["reference"])
        self.assertGreater(a["target"],a["reference"])

    def test_common_levels_ignore_entry_prices(self):
        a=frozen_watch_levels(self.m5,self.w)
        t1,reason=fixed_execute(self.m1,self.state,self.sig,"M1_FIXED",a)
        self.assertIsNotNone(t1,reason)
        updated=copy.deepcopy(self.m1)
        updated[260][1]=99.98
        s2={"m1e":[int(x[0])+ONE_MS for x in updated]}
        t2,reason=fixed_execute(updated,s2,self.sig,"M5_FIXED",a)
        self.assertIsNotNone(t2,reason)
        self.assertEqual(t1["sl"],t2["sl"])
        self.assertEqual(t1["tp"],t2["tp"])
        self.assertNotEqual(t1["entry"],t2["entry"])

    def test_entry_gate_rejects_nonviable_price(self):
        a=frozen_watch_levels(self.m5,self.w)
        m=copy.deepcopy(self.m1)
        m[260][1]=a["target"]+1
        s={"m1e":[int(x[0])+ONE_MS for x in m]}
        trade,reason=fixed_execute(m,s,self.sig,"M1_FIXED",a)
        self.assertIsNone(trade)
        self.assertEqual(reason,"INVALID_ENTRY_RELATIVE_TO_FIXED_LEVELS")

    def test_selector_waits_through_actual_one_minute_exit(self):
        a={"signal_ms":100000,"entry_ms":100000,"exit_end_ms":160000,
           "net_r":1.,"rr_net_at_fill":1.3,"watch_key":"a","result":"TP"}
        b={**a,"signal_ms":130000,"entry_ms":130000,"watch_key":"b"}
        c={**a,"signal_ms":160000,"entry_ms":160000,"watch_key":"c"}
        selected,p=portfolio([a,b,c])
        self.assertEqual(len(selected),2)
        self.assertEqual([x["watch_key"] for x in selected],["a","c"])

if __name__=="__main__":
    unittest.main()
