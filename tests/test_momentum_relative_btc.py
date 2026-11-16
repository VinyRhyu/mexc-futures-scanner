from copy import deepcopy
import unittest
from unittest.mock import patch

from mexc_scanner.demo import DemoClient
from mexc_scanner.models import Candle,Contract,D
from scripts.audit_multihour import HOUR,DAY,iso,simulate
from scripts.audit_momentum_relative_btc import relative_btc_score,selection_diagnostics

T=1790812800
COSTS=dict(fee='.0006',spread='.0002',slippage='.0002')


def bar(at,price):
    p=D(price)
    return Candle(at,HOUR,p,p,p,p,D(1000000))


def market(current='100'):
    bars={t:bar(t,'100') for t in range(T-300*HOUR,T+30*HOUR,HOUR)}
    for t in range(T-2*HOUR,T+30*HOUR,HOUR):bars[t]=bar(t,current)
    return dict(hourly=bars,fair=deepcopy(bars),contract=Contract.from_api(DemoClient(T).contracts()[0]),
        funding=[dict(ts=T-HOUR,rate=D(0),cycle=8)],funding_by_time={})


def signal(symbol='A',sign=1,atr='6'):
    return dict(symbol=symbol,sign=sign,signal_at=T-HOUR,atr=D(atr),score=D(10),
        stop=D('95'),turnover=D(10000000))


class RelativeBtcTests(unittest.TestCase):
    def test_long_uses_asset_minus_btc_normalized_by_daily_atr(self):
        markets={'A':market('120'),'BTC_USDT':market('110')}
        self.assertEqual(relative_btc_score(markets,signal()),D(2))

    def test_short_ranks_underperformance_in_own_direction(self):
        markets={'A':market('80'),'BTC_USDT':market('90')}
        self.assertEqual(relative_btc_score(markets,signal(sign=-1,atr='4')),D(2))

    def test_negative_relative_return_remains_a_finite_rank(self):
        markets={'A':market('105'),'BTC_USDT':market('110')}
        self.assertEqual(relative_btc_score(markets,signal(atr='5.25')),D(-1))

    def test_btc_itself_remains_eligible_with_zero_relative_score(self):
        self.assertEqual(relative_btc_score({'BTC_USDT':market('110')},signal('BTC_USDT')),D(0))

    def test_delay_and_future_bars_cannot_change_score(self):
        markets={'A':market('120'),'BTC_USDT':market('110')};s=signal();boundary=s['signal_at']
        original=relative_btc_score(markets,s)
        prefix={name:dict(m,hourly={t:b for t,b in m['hourly'].items() if b.end<=boundary}) for name,m in markets.items()}
        self.assertEqual(original,relative_btc_score(prefix,s))
        for name,m in markets.items():
            m['hourly'][boundary]=bar(boundary,'0.1' if name=='A' else '10000')
            m['hourly'][boundary+HOUR]=bar(boundary+HOUR,'10000' if name=='A' else '0.1')
        self.assertEqual(original,relative_btc_score(markets,s))

    def test_uses_exact_seven_day_closed_boundary(self):
        markets={'A':market('120'),'BTC_USDT':market('110')};s=signal()
        markets['A']['hourly'][s['signal_at']-7*DAY-HOUR]=bar(s['signal_at']-7*DAY-HOUR,'80')
        self.assertEqual(relative_btc_score(markets,s),D(8))

    def test_price_and_atr_rescaling_does_not_change_rank(self):
        markets={'A':market('120'),'BTC_USDT':market('110')};s=signal();old=relative_btc_score(markets,s)
        markets['A']['hourly']={t:bar(t,b.close*1000) for t,b in markets['A']['hourly'].items()}
        s['atr']*=1000
        self.assertEqual(old,relative_btc_score(markets,s))

    def test_zero_atr_fails_instead_of_silently_changing_formula(self):
        with self.assertRaises(ValueError):relative_btc_score({'A':market(),'BTC_USDT':market()},signal(atr='0'))

    def simulate(self,ranker=None):
        markets={'A':market(),'B':market()}
        signals={'A':signal('A'),'B':dict(signal('B'),score=D(1))}
        def entry(symbol,*args):return {T:[signals[symbol]]},{}
        p=dict(initial_equity='100',leverage=10,risk_fraction='.01',minimum_turnover='0',
            min_liquidation_buffer='1.5',signal_delay_seconds=HOUR)
        v=dict(name='TEST',kind='MOMENTUM',max_hold_hours=24,trail_atr=2)
        block=dict(start=iso(T),end=iso(T+12*HOUR),validation_start=iso(T+6*HOUR))
        with patch('scripts.audit_multihour.events',side_effect=entry):
            return simulate(markets,v,block,p,COSTS,entry_ranker=ranker)

    def test_optional_ordering_changes_selection_without_changing_risk_or_exit(self):
        baseline=self.simulate();candidate=self.simulate(lambda markets,s: -s['score'])
        a=baseline['trades'][0];b=candidate['trades'][0]
        self.assertEqual(a['symbol'],'A');self.assertEqual(b['symbol'],'B')
        self.assertEqual(a['quantity'],b['quantity']);self.assertEqual(a['stop'],b['stop'])
        self.assertEqual(a['exit_at'],b['exit_at']);self.assertEqual(a['net'],b['net'])
        self.assertNotIn('original_score',a)
        self.assertEqual(b['original_score'],D(1));self.assertEqual(b['score'],D(-1))
        self.assertLessEqual(b['planned_risk'],D(1))

    def test_equal_scores_keep_original_deterministic_tiebreak(self):
        self.assertEqual(self.simulate(lambda markets,s:D(0))['trades'][0]['symbol'],'A')

    def test_selection_diagnostic_pairs_entries_instead_of_future_profit(self):
        a=self.simulate();b=self.simulate(lambda markets,s:-s['score'])
        d=selection_diagnostics(a,b)
        self.assertEqual(d['changed_symbols_or_sides'],1);self.assertEqual(d['same_entries'],0)
        self.assertEqual(d['rows'][0]['control_symbol'],'A')
        self.assertEqual(d['rows'][0]['candidate_symbol'],'B')
