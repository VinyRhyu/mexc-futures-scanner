import unittest
from scripts.research_external_signal_cases import inferred_reference,epoch,outcome,touches,passes,NEW_CASES
from mexc_scanner.models import Candle,D

class ExternalCasesTests(unittest.TestCase):
    def test_reference(self):
        self.assertEqual(inferred_reference(("102","104","106","108"),"LONG"),[D(100)]*4)
        self.assertEqual(inferred_reference(("98","96","94","92"),"SHORT"),[D(100)]*4)
    def test_ambiguous_bar(self):
        t=0;bars={60:Candle(60,60,D(100),D(103),D(98),D(101),D(1))}
        self.assertEqual(outcome(bars,t,"LONG",1)["status"],"SL")
    def test_timezone(self):
        self.assertEqual(epoch("2026-11-22 10:44")%86400,13*3600+44*60)

    def test_frozen_hypothesis(self):
        self.assertEqual(len(NEW_CASES),8)
        self.assertTrue(passes({"rv_ratio":.75,"signed_ret_1":-.1,"signed_ret_60":-.1}))
        self.assertFalse(passes({"rv_ratio":.76,"signed_ret_1":-.1,"signed_ret_60":-.1}))
        self.assertFalse(passes({"rv_ratio":.5,"signed_ret_1":0,"signed_ret_60":-.1}))
