import unittest
from mexc_scanner.models import Candle,D
from scripts.research_pre_breakout_dataset import features,label

def bar(t,op=100,hi=101,lo=99,cl=100):
    return Candle(t,60,D(op),D(hi),D(lo),D(cl),D(5))

class DatasetTests(unittest.TestCase):
    def test_features_invariant_to_future(self):
        t=43200
        data={x:bar(x) for x in range(0,t+60,60)}
        before=features(data,data,t)
        self.assertIsNotNone(before)
        data[t]=bar(t,100,300,90,200)
        self.assertEqual(before,features(data,data,t))

    def test_gap_rejects_features(self):
        t=43200
        data={x:bar(x) for x in range(0,t,60)}
        del data[60]
        self.assertIsNone(features(data,data,t))

    def test_same_bar_stop_first_and_delayed_entry(self):
        data={60:bar(60,100,104,97,100)}
        result=label(data,0,D(2),"LONG",1,120)
        self.assertEqual(result["outcome"],"SL")
        self.assertEqual(result["entry_ts"],60)
        self.assertEqual(D(result["gross_r"]),D(-1))

    def test_tp_short(self):
        data={60:bar(60,100,101,96,100)}
        self.assertEqual(label(data,0,D(2),"SHORT",1,120)["outcome"],"TP")

    def test_gap_stop(self):
        data={60:bar(60),120:bar(120,95,96,94,95)}
        result=label(data,0,D(2),"LONG",2,180)
        self.assertEqual(D(result["gross_r"]),D("-2.5"))

    def test_timeout_and_censor(self):
        data={60:bar(60)}
        self.assertEqual(label(data,0,D(2),"LONG",1,120)["outcome"],"TIMEOUT")
        self.assertEqual(label(data,0,D(2),"LONG",2,180)["outcome"],"CENSORED")

if __name__=="__main__":
    unittest.main()
