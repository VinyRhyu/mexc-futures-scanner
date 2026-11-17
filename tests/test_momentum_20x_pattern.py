from copy import deepcopy
import unittest
from unittest.mock import patch

from mexc_scanner.models import D
from scripts.audit_multihour import DAY,HOUR,risk_budget,simulate,iso
from scripts.audit_momentum_20x_pattern import features,predict,PatternFilter,isolated_label,prefix
from tests.test_momentum_relative_btc import market,signal,bar,T,COSTS


def training(n=20,r='1',release=None):
    return [dict(symbol='A',sign=1,signal_at=T-(i+3)*DAY,release_at=release or T-(i+2)*DAY,
        features=(D(i),D(0)),r=D(r)) for i in range(n)]


class PatternTests(unittest.TestCase):
    def test_no_training_means_cash(self):
        self.assertEqual(predict([], 'A',1,T,(D(0),D(0)))['reason'],'PADRAO_AMOSTRA_INSUFICIENTE')

    def test_nineteen_mature_neighbors_are_insufficient(self):
        self.assertFalse(predict(training(19),'A',1,T,(D(0),D(0)))['accepted'])

    def test_positive_mean_of_twenty_passes(self):
        r=predict(training(),'A',1,T,(D(0),D(0)))
        self.assertTrue(r['accepted']);self.assertEqual(r['mean_r'],1);self.assertEqual(len(r['neighbors']),20)

    def test_nonpositive_means_reject_without_threshold_search(self):
        for mean in ('0','-1'):
            self.assertEqual(predict(training(r=mean),'A',1,T,(D(0),D(0)))['reason'],'PADRAO_MEDIA_NAO_POSITIVA')

    def test_future_perfect_labels_never_enter_neighbors(self):
        labels=training()+training(40,'100',T+HOUR)
        self.assertEqual(predict(labels,'A',1,T,(D(0),D(0))),predict(training(),'A',1,T,(D(0),D(0))))

    def test_release_boundary_is_inclusive_but_one_second_later_is_unavailable(self):
        self.assertTrue(predict(training(release=T),'A',1,T,(D(0),D(0)))['accepted'])
        self.assertFalse(predict(training(release=T+1),'A',1,T,(D(0),D(0)))['accepted'])

    def test_other_symbols_or_sides_are_not_pooled(self):
        for symbol,side in [('B',1),('A',-1)]:
            self.assertFalse(predict(training(),symbol,side,T,(D(0),D(0)))['accepted'])

    def test_exact_twenty_nearest_and_oldest_tiebreak(self):
        labels=training(21)
        labels[-1]['r']=D(1000)
        self.assertEqual(predict(labels,'A',1,T,(D(0),D(0)))['mean_r'],1)
        for row in labels:row['features']=(D(0),D(0))
        r=predict(labels,'A',1,T,(D(0),D(0)))
        self.assertNotIn(labels[0]['signal_at'],[n['signal_at'] for n in r['neighbors']])
        self.assertEqual(r['mean_r'],D(1019)/20)

    def test_feature_uses_only_closed_signal_data(self):
        markets={'A':market('120'),'BTC_USDT':market('110')};s=signal();before=features(markets,s)
        self.assertEqual(before[0],D(4))
        for m in markets.values():m['hourly'][s['signal_at']]=bar(s['signal_at'],'100000')
        self.assertEqual(before,features(markets,s))
        self.assertEqual(before,features(prefix(markets,s['signal_at']),s))

    def test_filter_retains_audit_neighbors_and_returns_rejection(self):
        filt=PatternFilter(training());s=signal();markets={'A':market(),'BTC_USDT':market()}
        self.assertIsNone(filt(markets,s));self.assertTrue(filt.rows[0]['accepted'])
        self.assertEqual(len(filt.rows[0]['neighbors']),20)

    def test_20x_rejects_stop_that_is_safe_at10x(self):
        m=market();s=signal();p=dict(leverage=10,risk_fraction='.01',minimum_turnover=0,min_liquidation_buffer='1.5')
        v=dict(max_hold_hours=24)
        a,_=risk_budget(s,m,T,D(100),p,v,COSTS)
        b,why=risk_budget(s,m,T,D(100),dict(p,leverage=20),v,COSTS)
        self.assertIsNotNone(a);self.assertIsNone(b);self.assertEqual(why,'STOP_PROXIMO_DA_LIQUIDACAO')

    def test20x_margin_halves_with_same_notional_and_risk(self):
        m=market();s=dict(signal(),stop=D(99));p=dict(leverage=10,risk_fraction='.01',minimum_turnover=0,min_liquidation_buffer='1.5')
        v=dict(max_hold_hours=24)
        a,_=risk_budget(s,m,T,D(100),p,v,COSTS)
        b,_=risk_budget(s,m,T,D(100),dict(p,leverage=20),v,COSTS)
        self.assertEqual(a['quantity'],b['quantity']);self.assertEqual(a['planned_risk'],b['planned_risk'])
        self.assertEqual(a['margin'],2*b['margin'])

    def test_early_stop_label_still_requires_full_horizon_plus_embargo(self):
        markets={'A':market(),'BTC_USDT':market('110')};s=dict(signal(),stop=D(99));m=markets['A']
        m['hourly'][T]=bar(T,'98');m['fair'][T]=bar(T,'98')
        p=dict(leverage=20,risk_fraction='.01',minimum_turnover=0,min_liquidation_buffer='1.5')
        row,why=isolated_label(markets,s,p,dict(max_hold_hours=24),COSTS,T+24*HOUR)
        self.assertIsNone(row);self.assertEqual(why,'IMMATURE')

    def test_optional_filter_prevents_entry_and_retains_skip_reason(self):
        markets={'A':market()};s=signal()
        p=dict(initial_equity='100',leverage=10,risk_fraction='.01',minimum_turnover=0,min_liquidation_buffer='1.5',signal_delay_seconds=HOUR)
        b=dict(start=iso(T),end=iso(T+2*HOUR),validation_start=iso(T+HOUR))
        with patch('scripts.audit_multihour.events',return_value=({T:[s]},{})):
            w=simulate(markets,dict(max_hold_hours=24),b,p,COSTS,entry_filter=lambda *args:'REJECT')
        self.assertEqual(w['summary']['positions'],0);self.assertEqual(w['summary']['skipped']['REJECT'],1)
        self.assertEqual(w['summary']['final'],100)
