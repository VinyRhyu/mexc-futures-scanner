"""Meta-label trip-barrier, no-lookahead, training-only scaling guards."""
import copy
import unittest

from scripts.audit_confluence_v3 import FIVE_MS,HOUR_MS
from scripts.audit_hype_meta_label_walkforward import (
    triple_barrier,watch_features,FEATURES,fit_standardizer,train_logit,
    probability,percentile80,BASELINE_GUARD
)
from scripts.audit_hype_three_regimes import ema


class HypeMetaLabelTests(unittest.TestCase):
    def setUp(self):
        self.m=[[i*FIVE_MS,100,100.2,99.8,100,1,100]
                for i in range(150)]
        self.h=[[(i-200)*HOUR_MS,100+i*.1,101+i*.1,
                 99+i*.1,100+i*.1,1,100] for i in range(200)]

    def test_future_triple_barrier_first_hit_and_tie(self):
        # LONG label: 1.25pct TP before .75pct adverse.
        self.m[101][2]=101.6
        self.assertEqual(triple_barrier(self.m,100,"LONG")[0],1)
        self.assertEqual(triple_barrier(self.m,100,"LONG")[2],"FAVORABLE")
        self.m[101][3]=99.0
        self.assertEqual(triple_barrier(self.m,100,"LONG")[0],0)
        self.assertEqual(triple_barrier(self.m,100,"LONG")[2],"ADVERSE")

    def test_watch_features_no_future_M5(self):
        i=110
        # align synthetic H1 timeline: last completion before t = H1 index <= 8
        # 110 M5 = 9h10m, still enough H1 warmup -> use longer index.
        self.m.extend([[n*FIVE_MS,100,100.2,99.8,100,1,100]
                       for n in range(150,500)])
        i=450  # t=37h35m, H1 latest index=36; warmed up
        w={"i":i,"at_ms":(i+1)*FIVE_MS,"side":"LONG",
           "family":"BREAK","volume_x":1.3}
        st=lambda m,h:{"he":[int(x[0])+HOUR_MS for x in h],
           "h20":ema([float(x[4]) for x in h],20),
           "m9":ema([float(x[4]) for x in m],9),
           "m21":ema([float(x[4]) for x in m],21)}
        original=watch_features(self.m,self.h,i,w,st(self.m,self.h))
        self.assertEqual(len(original),len(FEATURES))
        altered=copy.deepcopy(self.m)
        for row in altered[i+1:]:
            row[1],row[2],row[3],row[4],row[6]=300,500,1,400,99999
        self.assertEqual(original,watch_features(altered,self.h,i,w,st(altered,self.h)))
        self.assertEqual(original,watch_features(self.m[:i+1],self.h,i,w,st(self.m[:i+1],self.h)))

    def test_train_only_normalization_and_percentile(self):
        rows=[{"features":tuple(float(j+i/10) for j in range(len(FEATURES))),
               "label":int(i%3==0)} for i in range(120)]
        mu,sd=fit_standardizer(rows)
        model=train_logit(rows)
        p=probability(model,rows[0])
        self.assertTrue(0<p<1)
        self.assertEqual(len(model["coef"]),len(FEATURES))
        self.assertEqual(len(mu),len(sd))
        self.assertEqual(percentile80([1,2,3,4,5]),4)
        corrupt=copy.deepcopy(rows)
        corrupt[100]["features"]=tuple(10000. for _ in FEATURES)
        model_original=train_logit(rows[:100])
        model_changed=train_logit(corrupt[:100])
        self.assertEqual(model_original,model_changed)
        self.assertTrue(all(k in BASELINE_GUARD for k in ("U","V","W0")))

if __name__=="__main__":
    unittest.main()
