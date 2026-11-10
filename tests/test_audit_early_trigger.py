from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mexc_scanner.config import Config
from mexc_scanner.models import Candle, Contract, D, Plan
from scripts.audit_early_trigger import (check_ohlc, collect_minutes, evaluate_formation,
                                         evaluate_trigger, formations, summarize, trigger, write_gzip)


START=1793502000


def candle(ts,tf=60,op='100',hi='101',lo='99',cl='100'):
    return Candle(ts,tf,*map(D,(op,hi,lo,cl)))


def plan(side='LONG'):
    return Plan('p','TEST_USDT','ROMPIMENTO',side,START,START,START+1800,
                D(2),D(101) if side=='LONG' else D(99),D(99),D(101),D(100),'p')


class EarlyTriggerTests(unittest.TestCase):
    def setUp(self):
        self.contract=Contract('TEST_USDT',D('.001'),D(1),D(1),D('.01'),20,D('.005'),D('.0004'))
        self.h=[candle(START-(240-i)*3600,3600) for i in range(240)]

    def test_formations_exist_without_future_breakout_and_use_only_closed_history(self):
        q=[candle(START-(480-i)*900,900) for i in range(480)]
        q.append(candle(START,900))
        before=formations('TEST_USDT',q,D('.01'),START,START+900)
        self.assertEqual({p.side for p in before},{'LONG','SHORT'})
        altered=deepcopy(q)
        altered[-1]=candle(START,900,'100','500','1','400')
        after=formations('TEST_USDT',altered,D('.01'),START,START+900)
        self.assertEqual(before,after)
        self.assertEqual(before[0].formed_at,START)
        self.assertEqual(before[0].atr,D(2))

    def test_first_closed_minute_not_first_wick(self):
        p=plan()
        bars=[candle(START,hi='105',cl='101'),candle(START+60,hi='102',cl='101.3'),
              candle(START+120,hi='103',cl='102')]
        self.assertEqual(trigger(p,bars),bars[1])
        self.assertIsNone(trigger(p,[replace(bars[1],ts=START+1800)]))
        self.assertIsNone(trigger(p,[replace(bars[1],ts=START-60)]))

    def test_trigger_is_symmetric_and_deadline_is_inclusive(self):
        b=candle(START+1740,hi='102',cl='101.3')
        m=replace(b,open=200-b.open,high=200-b.low,low=200-b.high,close=200-b.close)
        self.assertEqual(trigger(plan(),[b]).end,START+1800)
        self.assertEqual(trigger(plan('SHORT'),[m]).end,START+1800)

    def test_signal_bar_extremes_do_not_count_as_post_entry_profit(self):
        p=plan()
        b=candle(START,hi='150',cl='101.3')
        mm={START+(i+1)*60:candle(START+(i+1)*60,op='101.3',hi='101.4',lo='101.2',cl='101.3') for i in range(240)}
        with patch('scripts.audit_early_trigger.paper_quote',return_value={'status':'BLOQUEADA','reasons':['RETORNO_RISCO_INSUFICIENTE']}):
            r=evaluate_trigger(p,b,mm,self.h,self.contract,Config())
        self.assertEqual(r['trajectory']['outcome'],'ABERTO')
        self.assertEqual(r['signal'],START+60)
        self.assertEqual(r['entry_mid'],'101.3')

    def test_future_hourly_bars_cannot_select_targets(self):
        p=plan()
        b=candle(START,hi='102',cl='101.3')
        mm={START+(i+1)*60:candle(START+(i+1)*60) for i in range(240)}
        future=[candle(START+i*3600,3600,hi=str(110+i)) for i in range(6)]
        from mexc_scanner.strategies import make_variant
        def checked(p,kind,c,h,tick):
            self.assertEqual(len(h),240)
            self.assertTrue(all(x.end<=c.end for x in h))
            return make_variant(p,kind,c,h,tick)
        with patch('scripts.audit_early_trigger.make_variant',side_effect=checked),patch('scripts.audit_early_trigger.paper_quote',return_value={'status':'BLOQUEADA','reasons':['X']}):
            r=evaluate_trigger(p,b,mm,self.h+future,self.contract,Config())
        self.assertEqual(r['target'],'103')
        self.assertEqual(r['stop'],'100')

    def test_intrabar_false_breakout_is_included_even_without_15m_trigger(self):
        p=plan()
        mm={START+i*60:candle(START+i*60) for i in range(270)}
        mm[START]=candle(START,hi='102',cl='101.3')
        qm={START:candle(START,900,hi='102'),START+900:candle(START+900,900)}
        with patch('scripts.audit_early_trigger.paper_quote',return_value={'status':'BLOQUEADA','reasons':['X']}):
            r=evaluate_formation(p,qm,mm,self.h,self.contract,Config())
        self.assertEqual(r['M15']['outcome'],'SEM_GATILHO')
        self.assertEqual(r['M1']['signal'],START+60)
        self.assertTrue(r['m1_not_sustained_at_15m_close'])
        self.assertTrue(r['returned_inside_before_15m_close'])
        self.assertEqual(summarize([r])['paired']['m1_only_triggers'],1)

    def test_missing_minutes_or_inconsistent_ohlc_are_rejected(self):
        q=[candle(START,900)]
        m={START+i*60:candle(START+i*60) for i in range(15)}
        check_ohlc(q,m,START,START+900)
        m[START]=candle(START,hi='102')
        with self.assertRaisesRegex(ValueError,'does not match'):
            check_ohlc(q,m,START,START+900)
        del m[START+60]
        with self.assertRaises(KeyError):
            check_ohlc(q,m,START,START+900)

    def test_collect_rejects_gaps_between_request_chunks(self):
        from mexc_scanner.mexc import MexcClient
        client=MexcClient()
        # Each chunk could be valid independently, but the join must be checked.
        def fake(data,tf,now,count):
            right=now-10
            offset=-60 if count<1800 else 0
            return [candle(right-count*60+i*60+offset) for i in range(count)]
        with patch.object(client,'candles',return_value={}),patch('scripts.audit_early_trigger.parse_candles',side_effect=fake):
            with self.assertRaisesRegex(ValueError,'boundaries'):
                collect_minutes(client,'TEST_USDT',START,START+1860*60)

    def test_summary_does_not_treat_blocked_trajectory_as_released_trade(self):
        r={'symbol':'TEST_USDT','side':'LONG','M15':{'outcome':'SEM_GATILHO'},
           'M1':{'signal':START,'outcome':'BLOQUEADA','reasons':['X'],'trajectory':{'outcome':'ALVO','net_r':'2'}}}
        s=summarize([r])
        self.assertEqual(s['M1']['entries'],0)
        self.assertEqual(s['M1']['targets'],0)
        self.assertEqual(s['M1']['trajectory_blocked'],{'ALVO':1})

    def test_saved_history_has_reproducible_hash_and_gzip(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'history.json.gz'
            one=write_gzip(p,{'price':D('1.2')})
            first=p.read_bytes()
            two=write_gzip(p,{'price':D('1.2')})
            self.assertEqual(one,two)
            self.assertEqual(first,p.read_bytes())


if __name__=='__main__':
    unittest.main()
