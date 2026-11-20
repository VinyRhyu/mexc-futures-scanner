"""Unit guards for three HYPE causal hypothesis families."""
import copy
import unittest
from scripts.audit_hype_three_regimes import ema, context, maybe_setup
from scripts.audit_confluence_v3 import FIVE_MS, HOUR_MS


class ThreeRegimesTests(unittest.TestCase):
    def setUp(self):
        self.m=[[i*FIVE_MS,100,100.1,99.9,100,1,100] for i in range(130)]
        self.h=[[(-140+i)*HOUR_MS,100+i*.1,101+i*.1,99+i*.1,
                 100+i*.1,1,100] for i in range(140)]
        self.i=90

    def test_ema_sma_seed_uses_only_closed_values(self):
        self.assertEqual(ema([1,2,3,4],3),[None,None,2,3])
        self.assertEqual(ema([2]*100,20)[-1],2)
        self.assertEqual(ema([2]*100,50)[-1],2)

    def test_impulse_long_trigger_is_causal(self):
        self.m[self.i]=[self.i*FIVE_MS,100,101.2,99.9,101,1,600]
        state=context(self.m,self.h)
        found=maybe_setup(self.m,self.h,self.i,"IMPULSE",state,"LONG")
        self.assertIsNotNone(found)
        self.assertEqual(found["side"],"LONG")
        self.assertIsNone(maybe_setup(self.m,self.h,self.i-1,"IMPULSE",state,"LONG"))
        changed=copy.deepcopy(self.m)
        for b in changed[self.i+1:]:
            b[1],b[2],b[3],b[4],b[6]=200,300,50,220,999999
        partial=context(self.m[:self.i+1],self.h)
        self.assertEqual(found,maybe_setup(self.m[:self.i+1],self.h,self.i,"IMPULSE",partial,"LONG"))
        self.assertEqual(found,maybe_setup(changed,self.h,self.i,"IMPULSE",context(changed,self.h),"LONG"))

    def test_opposite_h1_rejects_impulse(self):
        self.m[self.i]=[self.i*FIVE_MS,100,101.2,99.9,101,1,600]
        h=copy.deepcopy(self.h)
        # H1 chronologically falling, opposite to LONG
        for k,b in enumerate(h):
            b[4]=150-.1*k
        self.assertIsNone(maybe_setup(self.m,h,self.i,"IMPULSE",context(self.m,h),"LONG"))

    def test_reversal_has_to_reclaim_swept_level(self):
        h=copy.deepcopy(self.h)
        for k,b in enumerate(h):
            b[4]=150-.1*k
        j=self.i-1
        self.m[j]=[j*FIVE_MS,100,100.2,98.0,100.05,1,400]
        self.m[self.i]=[self.i*FIVE_MS,100.0,100.7,99.95,100.6,1,100]
        state=context(self.m,h)
        cand=maybe_setup(self.m,h,self.i,"REVERSAL",state,"LONG")
        self.assertIsNotNone(cand)
        self.assertLess(cand["stop_raw"],98)
        changed=copy.deepcopy(self.m)
        changed[j][4]=98.5
        self.assertIsNone(maybe_setup(changed,h,self.i,"REVERSAL",context(changed,h),"LONG"))

    def test_no_h1_future_used(self):
        self.m[self.i]=[self.i*FIVE_MS,100,101.2,99.9,101,1,600]
        s=context(self.m,self.h)
        base=maybe_setup(self.m,self.h,self.i,"IMPULSE",s,"LONG")
        future=copy.deepcopy(self.h)
        future.append([20*HOUR_MS,10,11,9,10,1,100])
        self.assertEqual(base,maybe_setup(self.m,future,self.i,"IMPULSE",context(self.m,future),"LONG"))


if __name__=="__main__":
    unittest.main()
