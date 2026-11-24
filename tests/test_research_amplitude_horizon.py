import unittest
from mexc_scanner.models import D,Candle
from scripts.research_amplitude_horizon import partition,outcome,CUT1,CUT2,MAX_LABEL_TIME,EMBARGO

def bar(t,o=100,h=101,l=99,c=100):
    return Candle(t,60,D(o),D(h),D(l),D(c),D(5))

class AmplitudeTests(unittest.TestCase):
    def test_purge_max_horizon(self):
        self.assertEqual(partition(CUT1-MAX_LABEL_TIME),"train")
        self.assertIsNone(partition(CUT1-MAX_LABEL_TIME+60))
        self.assertIsNone(partition(CUT1+EMBARGO-60))
        self.assertEqual(partition(CUT1+EMBARGO),"validation")
        self.assertIsNone(partition(CUT2+EMBARGO-60))
        self.assertEqual(partition(CUT2+EMBARGO),"test")
    def test_wider_stop_preserves_rr_and_changes_outcome(self):
        bars={60:bar(60,100,101,97,100)}
        r={"a":D(2),"t":0,"symbol":"X","x":[]}
        narrow=outcome(bars,r,"LONG",1,1,120)
        wide=outcome(bars,r,"LONG",1,2,120)
        self.assertEqual(narrow["label"]["outcome"],"SL")
        self.assertEqual(wide["label"]["outcome"],"TIMEOUT")
        self.assertEqual(D(wide["label"]["target"])-D(wide["label"]["entry"]),D(6))
        self.assertEqual(wide["atr"],4.)
    def test_longer_horizon_can_change_timeout(self):
        bars={60:bar(60),120:bar(120,100,104,99,103)}
        r={"a":D(2),"t":0,"symbol":"X","x":[]}
        self.assertEqual(outcome(bars,r,"LONG",1,1,180)["label"]["outcome"],"TIMEOUT")
        self.assertEqual(outcome(bars,r,"LONG",2,1,180)["label"]["outcome"],"TP")
