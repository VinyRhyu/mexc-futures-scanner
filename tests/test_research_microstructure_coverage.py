import unittest
from scripts.research_microstructure_coverage import price_rows,coverage,recent_summary,funding_history,START,STEP

class CoverageTests(unittest.TestCase):
    def test_price_filter(self):
        p={"time":[START-STEP,START,START+STEP],"open":[1,1,1],"high":[2,2,2],"low":[1,1,1],"close":[2,2,2]}
        r=price_rows(p,START,START+STEP)
        self.assertEqual(set(r),{START})
        self.assertEqual(coverage(r,START,START+2*STEP)["observed"],1)
    def test_conflicting_duplicate(self):
        p={"time":[START,START],"open":[1,1],"high":[2,3],"low":[1,1],"close":[2,3]}
        with self.assertRaises(ValueError):
            price_rows(p,START,START+STEP)
    def test_recent_not_complete(self):
        r=recent_summary([{"t":START*1000,"T":1},{"t":(START+2)*1000,"T":2}])
        self.assertEqual(r["span_seconds"],2)
        self.assertFalse(r["complete_history"])
    def test_funding_pagination(self):
        class Fake:
            def _get(self,path,params):
                page=params["page_num"]
                t=START+3600 if page==1 else START-7*3600
                return {"totalPage":2,"resultList":[{"symbol":"BTC_USDT","settleTime":t*1000,"fundingRate":"0.0001","collectCycle":8}]}
        rows,s=funding_history(Fake(),"BTC_USDT",START+7200)
        self.assertEqual(len(rows),2)
        self.assertEqual(s["stop"],"prior_settlement_reached")
