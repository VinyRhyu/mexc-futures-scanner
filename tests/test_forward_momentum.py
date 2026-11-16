from copy import deepcopy
import gzip,json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from mexc_scanner.demo import DemoClient
from mexc_scanner.models import D,jsonable
from scripts.audit_multihour import HOUR,DAY,iso,simulate,events
from scripts.forward_momentum import (run,read_json,merge_observation,freeze_day,record_missing_days,
    frozen_timeline,initialize,verify_state,quote_capture)
from tests.test_multihour import T,market,bar,VARIANT,PROTOCOL


def protocol():
    p=read_json('config/momentum-forward-v1-2026-11-16.json')
    p.update(symbols=['BTC_USDT'],minimum_turnover='0',frozen_at_utc=iso(T-DAY),
        decision_start_utc=iso(T),decision_end_exclusive_utc=iso(T+30*DAY),
        history_start_utc=iso(T-17*DAY),evaluation_end_utc=iso(T+30*DAY+2*HOUR))
    return p


class PublicForwardFake:
    def __init__(self,now):
        self.now=now;self.calls=0
        self.contract={**DemoClient(T).contracts()[0],'symbol':'BTC_USDT','contractSize':'.001'}
    def server_time(self):return self.now
    def contracts(self):return [self.contract]
    def _symbol(self,symbol):return symbol
    def price(self,t):return D(100)+D(t-(T-17*DAY))/D(HOUR)/1000
    def _get(self,path,params):
        self.calls+=1
        if 'funding_rate/history' in path:
            times=list(range(T-18*DAY,self.now+1,8*HOUR))[::-1]
            page=params['page_num'];rows=times[(page-1)*100:page*100]
            return dict(totalPage=(len(times)+99)//100,resultList=[dict(symbol='BTC_USDT',settleTime=t*1000,
                fundingRate='0',collectCycle=8) for t in rows])
        times=list(range(params['start'],params['end']+1,HOUR))
        return dict(time=times,open=[str(self.price(t)) for t in times],high=[str(self.price(t)+1) for t in times],
            low=[str(self.price(t)-1) for t in times],close=[str(self.price(t)) for t in times],vol=['1000000']*len(times))
    def tickers(self):
        return [dict(symbol='BTC_USDT',bid1=str(self.price(self.now)-D('.01')),ask1=str(self.price(self.now)+D('.01')),
            lastPrice=str(self.price(self.now)),timestamp=self.now*1000)]
    def depth(self,symbol):return dict(bids=[['100','10000']],asks=[['101','10000']],timestamp=self.now*1000)


class ForwardMomentumTests(unittest.TestCase):
    def setup(self,td,now=T-HOUR+30):
        root=Path(td);p=root/'protocol.json';p.write_text(json.dumps(protocol()))
        return p,root/'state',PublicForwardFake(now)

    def test_bootstrap_has_zero_trades_and_no_success_claim(self):
        with TemporaryDirectory() as td:
            p,root,c=self.setup(td);s=run(p,root,c)
            self.assertEqual(s['phase'],'WARMUP');self.assertEqual(s['frozen_days'],0)
            for model in s['models'].values():
                self.assertFalse(model['research_screen_passed'])
                for w in model['wallets'].values():
                    self.assertEqual(w['marked_equity'],D(100));self.assertEqual(w['summary']['positions'],0)

    def test_signal_is_frozen_before_quote_and_open_positions_stay_open(self):
        with TemporaryDirectory() as td:
            p,root,c=self.setup(td);run(p,root,c)
            c.now=T+30;run(p,root,c)
            frozen=(root/'decisions'/f'{T}.json').read_bytes()
            d=json.loads(frozen);self.assertLess(d['frozen_at'],d['entry_at']);self.assertTrue(d['entries'])
            c.now=T+HOUR+30;s=run(p,root,c)
            self.assertEqual(s['observed_quote_windows'],1)
            c.now=T+2*HOUR+30;s=run(p,root,c)
            self.assertEqual((root/'decisions'/f'{T}.json').read_bytes(),frozen)
            for w in read_json(root/'wallets.json').values():
                self.assertIsNotNone(w['open_position']);self.assertEqual(w['summary']['positions'],0)

    def test_missed_day_is_never_backfilled_from_future_data(self):
        with TemporaryDirectory() as td:
            p,root,c=self.setup(td);run(p,root,c)
            c.now=T+2*HOUR+30;s=run(p,root,c)
            d=read_json(root/'decisions'/f'{T}.json')
            self.assertEqual(d['status'],'MISSED_FREEZE_WINDOW');self.assertFalse(d['entries'])
            self.assertEqual(s['missed_days'],1)

    def test_late_quote_is_recorded_as_missed_not_as_historical_price(self):
        with TemporaryDirectory() as td:
            p,root,c=self.setup(td);run(p,root,c)
            c.now=T+30;run(p,root,c)
            c.now=T+HOUR+601;s=run(p,root,c)
            q=read_json(root/'quotes'/f'{T}.json')
            self.assertEqual(q['status'],'MISSED_QUOTE_WINDOW');self.assertFalse(q['quotes'])
            self.assertEqual(s['observed_quote_windows'],0)

    def test_repeated_hour_is_idempotent(self):
        with TemporaryDirectory() as td:
            p,root,c=self.setup(td);run(p,root,c);before=(root/'journal.jsonl').read_bytes();calls=c.calls
            run(p,root,c);self.assertEqual((root/'journal.jsonl').read_bytes(),before);self.assertEqual(c.calls,calls)

    def test_checkpoint_with_missing_days_does_not_pass(self):
        with TemporaryDirectory() as td:
            p,root,c=self.setup(td);run(p,root,c)
            c.now=T+30*DAY+2*HOUR+30;s=run(p,root,c)
            self.assertEqual(s['phase'],'COMPLETED_CHECKPOINT');self.assertEqual(s['missed_days'],30)
            self.assertTrue(all(not m['research_screen_passed'] for m in s['models'].values()))
            self.assertFalse(s['approved_for_production'])

    def test_price_or_protocol_tampering_is_rejected(self):
        with TemporaryDirectory() as td:
            p,root,c=self.setup(td);run(p,root,c)
            target=next((root/'prices').glob('*.gz'));target.write_bytes(b'changed')
            c.now+=HOUR
            with self.assertRaises(AssertionError):run(p,root,c)

    def test_initialization_cannot_silently_compare_different_entry_rules(self):
        with TemporaryDirectory() as td:
            p,root,c=self.setup(td);v=json.loads(p.read_text());v['variants'][1]['lookback_days']=3;p.write_text(json.dumps(v))
            with self.assertRaises(AssertionError):run(p,root,c)
        with TemporaryDirectory() as td:
            p,root,c=self.setup(td);run(p,root,c);v=json.loads(p.read_text());v['leverage']=20;p.write_text(json.dumps(v))
            c.now+=HOUR
            with self.assertRaises(AssertionError):run(p,root,c)

    def test_first_observed_source_is_retained_after_revision(self):
        days={};state={'source_revisions':{}};a=jsonable(bar(T));b=dict(a,high='102')
        merge_observation(days,state,'A','hourly',a,T+3601)
        merge_observation(days,state,'A','hourly',b,T+7201)
        stored=next(iter(days.values()))['A']['hourly'][str(T)]
        self.assertEqual(stored['high'],'101');self.assertEqual(len(state['source_revisions']),1)
        merge_observation(days,state,'A','hourly',b,T+8201)
        self.assertEqual(len(state['source_revisions']),1)

    def test_numeric_formatting_is_not_a_market_revision(self):
        days={};state={'source_revisions':{}};a=jsonable(bar(T));b=dict(a,open='100.000')
        merge_observation(days,state,'A','hourly',a,T+3601);merge_observation(days,state,'A','hourly',b,T+7201)
        self.assertFalse(state['source_revisions'])

    def test_closed_trade_prefix_is_stable_and_corruption_fails(self):
        with TemporaryDirectory() as td:
            p,root,c=self.setup(td);run(p,root,c)
            for now in [T+30,T+HOUR+30,T+2*HOUR+30,T+DAY+2*HOUR+30]:
                c.now=now;run(p,root,c)
            wallets=read_json(root/'wallets.json');self.assertTrue(all(w['trades'] for w in wallets.values()))
            old={k:w['trades'] for k,w in wallets.items()};c.now+=HOUR;run(p,root,c)
            self.assertEqual({k:w['trades'] for k,w in read_json(root/'wallets.json').items()},old)
            wallets=read_json(root/'wallets.json');next(iter(wallets.values()))['trades'][0]['net']='999'
            (root/'wallets.json').write_text(json.dumps(wallets));c.now+=HOUR
            with self.assertRaises(AssertionError):run(p,root,c)

    def test_frozen_gate_is_not_recomputed_using_later_market_state(self):
        m=market();m['hourly'][T-HOUR]=bar(T-HOUR,hi='104',cl='103');m['fair'][T-HOUR]=m['hourly'][T-HOUR]
        for t in range(T,T+24*HOUR,HOUR):m['hourly'][t]=bar(t,op='103',hi='104',lo='102',cl='103');m['fair'][t]=m['hourly'][t]
        variant=dict(VARIANT,market_gate='BTC7_SIGN');e,u=events('A',m,variant,T,T+24*HOUR)
        for rows in e.values():
            for s in rows:s['frozen_market_gate']=True
        block=dict(start=iso(T),end=iso(T+24*HOUR),validation_start=iso(T))
        result=simulate({'A':m},variant,block,PROTOCOL,{'fee':'.0006','spread':'.0002','slippage':'.0002'},
            frozen_events={'entries':e,'updates':{'A':u}},force_flat=False)
        self.assertIsNotNone(result['open_position'])
