import json,tempfile,unittest
from pathlib import Path
from scripts.audit_m1_short_progress_validation import run


class ProgressSourceGuards(unittest.TestCase):
    def fixture(self,directory):
        p=dict(start_brt='2026-11-08T00:00:00-03:00',end_exclusive_brt='2026-11-15T00:00:00-03:00',
               symbols=['DASH_USDT','XMR_USDT']+[f'C{i}_USDT' for i in range(29)],
               partial_analysis_amendment_before_outcomes=dict(excluded_symbols=['DASH_USDT','XMR_USDT']))
        m=dict(kind='M1_PROGRESS_NEW_WEEK_SOURCE',start_brt=p['start_brt'],end_exclusive_brt=p['end_exclusive_brt'],
               selected_symbols=31,analyzed_symbols=29,errors={'DASH_USDT':'missing','XMR_USDT':'missing'},
               datasets=[dict(symbol=f'C{i}_USDT') for i in range(29)])
        root=Path(directory);proto=root/'protocol.json';proto.write_text(json.dumps(p))
        return root,proto,m

    def test_partial_source_is_rejected_without_explicit_flag(self):
        with tempfile.TemporaryDirectory() as d:
            root,p,m=self.fixture(d);(root/'summary.json').write_text(json.dumps(m))
            with self.assertRaises(AssertionError):run(root,p)

    def test_partial_flag_cannot_hide_an_additional_missing_symbol(self):
        with tempfile.TemporaryDirectory() as d:
            root,p,m=self.fixture(d);m['errors']['C0_USDT']='missing';m['datasets']=m['datasets'][1:];m['analyzed_symbols']=28
            (root/'summary.json').write_text(json.dumps(m))
            with self.assertRaises(AssertionError):run(root,p,True)

    def test_partial_flag_cannot_accept_a_different_period(self):
        with tempfile.TemporaryDirectory() as d:
            root,p,m=self.fixture(d);m['start_brt']='2026-10-25T00:00:00-03:00'
            (root/'summary.json').write_text(json.dumps(m))
            with self.assertRaises(AssertionError):run(root,p,True)


if __name__=='__main__':unittest.main()
