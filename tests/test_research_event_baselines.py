import unittest
import numpy as np
from scripts.research_event_baselines import binary_metrics,binary_gain,symbol_prior

class BaselineTests(unittest.TestCase):
    def test_constant_auc(self):
        self.assertEqual(binary_metrics([0,1],[.5,.5])["auc"],.5)
    def test_single_class(self):
        self.assertIsNone(binary_metrics([1,1],[.7,.8])["auc"])
    def test_paired_gain(self):
        self.assertEqual(binary_gain([0,1],[.4,.7],[.4,.7],["a","b"])["ci95"],[0.,0.])
    def test_symbol_prior(self):
        self.assertEqual(symbol_prior(np.array([0,1,1]),np.array(["A","A","B"])),{"A":.5,"B":1.})
