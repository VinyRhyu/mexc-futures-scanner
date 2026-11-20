"""Causal marker tests for HYPE event diagnosis (not trading validation)."""
import copy
import unittest

from scripts.audit_hype_eight_moves_20261120 import raw_momentum, checkpoint, ms, EVENTS
from scripts.audit_confluence_v3 import FIVE_MS, HOUR_MS


class HypeEightMovesTests(unittest.TestCase):
    def setUp(self):
        self.m=[[i*FIVE_MS, 100,100.1,99.9,100,1,100] for i in range(110)]
        self.h=[[(i-125)*HOUR_MS, 120-i*.1,121-i*.1,119-i*.1,
                 120-i*.1,1,100] for i in range(125)]
        self.i=45
        self.m[self.i]=[self.i*FIVE_MS,100,101,99.9,100.8,100,400]
        self.e_m=[int(c[0])+FIVE_MS for c in self.m]
        self.e_h=[int(c[0])+HOUR_MS for c in self.h]

    def test_all_user_windows_valid_nonoverlapping(self):
        self.assertEqual(len(EVENTS),8)
        slots=[]
        for name,sd,sh,sm,ed,eh,em,side in EVENTS:
            a,b=ms(sd,sh,sm),ms(ed,eh,em)
            self.assertLess(a,b)
            self.assertIn(side,("SHORT","LONG"))
            slots.append((a,b))
        slots.sort()
        self.assertTrue(all(x[1]<=y[0] for x,y in zip(slots,slots[1:])))

    def test_marker_uses_only_closed_bar_and_previous(self):
        expected=raw_momentum(self.m,self.i)
        self.assertIsNotNone(expected)
        self.assertEqual(expected["side"],"LONG")
        changed=copy.deepcopy(self.m)
        for c in changed[self.i+1:]:
            c[1],c[2],c[3],c[4],c[6]=300,400,50,350,99999
        self.assertEqual(expected,raw_momentum(changed,self.i))
        self.assertEqual(expected,raw_momentum(self.m[:self.i+1],self.i))

    def test_thresholds_are_not_guaranteed_on_every_bar(self):
        self.assertIsNone(raw_momentum(self.m,self.i-1))
        modified=copy.deepcopy(self.m)
        modified[self.i][6]=100
        self.assertIsNone(raw_momentum(modified,self.i))

    def test_checkpoint_does_not_use_future_hourly_m5(self):
        at=self.e_m[self.i]
        original=checkpoint(self.m,self.h,self.e_m,self.e_h,at)
        altered=copy.deepcopy(self.m)
        for c in altered[self.i+1:]:
            c[4]=12345
        appended=copy.deepcopy(self.h)
        appended.append([HOUR_MS, 1,2,0,999,4,3])
        self.assertEqual(original,checkpoint(altered,appended,self.e_m,
                         self.e_h+[2*HOUR_MS],at))


if __name__=="__main__":
    unittest.main()
