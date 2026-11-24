import unittest
import numpy as np
from scripts.research_event_predictability import event,context,metrics,day_gain,CLASSES,CONTEXT_NAMES,align_probabilities
from mexc_scanner.models import Candle,D

def candle(t,op=100,hi=101,lo=99,cl=100):
    return Candle(t,60,D(op),D(hi),D(lo),D(cl),D(1))

class EventTests(unittest.TestCase):
    def test_no_move(self):
        b={t:candle(t) for t in range(0,14400,60)}
        self.assertEqual(event(b,0,D(100),D(1)),("NONE",14400))
    def test_first_excursion(self):
        b={0:candle(0,100,104,99,103),60:candle(60,103,104,96,97)}
        self.assertEqual(event(b,0,D(100),D(1)),("UP",60))
    def test_ambiguous_and_gap(self):
        self.assertEqual(event({0:candle(0,100,104,96,100)},0,D(100),D(1)),("AMBIGUOUS",60))
        self.assertEqual(event({0:candle(0,96,104,95,100)},0,D(100),D(1)),("DOWN",0))
    def test_context_causal(self):
        t=86460
        b={j:candle(j) for j in range(0,t,60)}
        x=context(b,b,t)
        b[t]=candle(t,200,201,199,200)
        np.testing.assert_allclose(x,context(b,b,t),equal_nan=True)
        self.assertEqual(len(x),len(CONTEXT_NAMES))
    def test_metrics_and_paired_baseline(self):
        y=np.array(CLASSES)
        p=np.full((4,4),.25)
        self.assertAlmostEqual(metrics(y,p)["event_auc"],.5)
        self.assertEqual(day_gain(y,p,p,["a","a","b","b"])["ci95"],[0.,0.])

    def test_optional_class_absent(self):
        p=align_probabilities([[.2,.5,.3]],["DOWN","NONE","UP"])
        np.testing.assert_allclose(p,[[0,.2,.5,.3]])
        q=metrics(np.array(["AMBIGUOUS"]),p)
        self.assertTrue(np.isfinite(q["log_loss"]))
        self.assertEqual(q["class_counts"],{"AMBIGUOUS":1})
    def test_alignment_rejects_invalid_distribution(self):
        with self.assertRaises(ValueError):
            align_probabilities([[.2,.3]],["UP","DOWN"])
