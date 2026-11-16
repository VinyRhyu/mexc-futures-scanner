from copy import deepcopy
import unittest

from mexc_scanner.models import Candle, D, jsonable
from scripts.audit_failure_reversal import first_failure
from tests.test_wallet_entry_research import signal, bar, T


class FailureReversalResearchTests(unittest.TestCase):
    def case(self):
        original=signal()
        prices={t:bar(t) for t in range(T-120,T+600,60)}
        prices[T+60]=bar(T+60,hi='101.1',lo='99.5',close='99.8')
        return original,prices

    def test_first_inside_close_produces_opposite_side_using_known_levels(self):
        original,prices=self.case()
        reverse,reason=first_failure(original,prices)
        self.assertIsNone(reason)
        self.assertEqual(reverse['side'],'SHORT')
        self.assertEqual(reverse['signal'],T+120)
        self.assertEqual(reverse['target'],D(99))
        self.assertEqual(reverse['stop'],D('101.3'))
        self.assertLessEqual(reverse['variant'].entry_high,D('99.999'))

    def test_signal_is_identical_when_every_future_bar_is_removed(self):
        original,prices=self.case()
        reverse,_=first_failure(original,prices)
        prefix={t:c for t,c in prices.items() if c.end<=reverse['signal']}
        causal,_=first_failure(original,prefix)
        self.assertEqual(jsonable(reverse),jsonable(causal))

    def test_original_stop_already_touched_prevents_hindsight_reversal(self):
        original,prices=self.case();prices[T+60]=bar(T+60,hi='101.1',lo='97.5',close='99.8')
        reverse,reason=first_failure(original,prices)
        self.assertIsNone(reverse)
        self.assertEqual(reason,'ORIGINAL_SL_TP_ANTES_DA_FALHA')

    def test_midpoint_touched_before_signal_is_not_a_profit_opportunity(self):
        original,prices=self.case();prices[T+60]=bar(T+60,hi='101.1',lo='98.5',close='99.8')
        reverse,reason=first_failure(original,prices)
        self.assertIsNone(reverse)
        self.assertEqual(reason,'MEIO_DA_FAIXA_JA_TOCADO')

    def test_future_terminal_status_is_not_copied_into_new_signal(self):
        original,prices=self.case()
        original['plan'].status='INVALIDADO';original['plan'].reason='FUTURE_STOP_NOT_KNOWN'
        original['plan'].last_bar=T+600
        reverse,_=first_failure(original,prices)
        self.assertEqual(reverse['plan'].status,'ATIVO')
        self.assertEqual(reverse['plan'].last_bar,T+120)
        self.assertNotIn('FUTURE_STOP_NOT_KNOWN',str(jsonable(reverse)))

    def test_mirrored_failed_short_produces_long(self):
        original,prices=self.case()
        original['side']='SHORT';original['plan'].side='SHORT'
        original['plan'].lower=D(100);original['plan'].upper=D(102)
        original['stop']=D(102);original['target']=D(94)
        prices={t:Candle(c.ts,c.tf,200-c.open,200-c.low,200-c.high,200-c.close,c.volume)
                for t,c in prices.items()}
        reverse,reason=first_failure(original,prices)
        self.assertIsNone(reason)
        self.assertEqual(reverse['side'],'LONG')
        self.assertEqual(reverse['target'],D(101))
        self.assertLess(reverse['stop'],D(100))

    def test_no_failure_within_five_minutes_does_not_search_later(self):
        original,prices=self.case();prices[T+60]=bar(T+60)
        prices[T+300]=bar(T+300,lo='99.5',close='99.8')
        reverse,reason=first_failure(original,prices)
        self.assertIsNone(reverse)
        self.assertEqual(reason,'NAO_RETORNOU_PARA_FAIXA_EM_5M')
