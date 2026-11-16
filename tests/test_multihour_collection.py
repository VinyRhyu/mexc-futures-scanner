import unittest
import gzip
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from mexc_scanner.models import D
from mexc_scanner.demo import DemoClient
from scripts.collect_multihour_source import parse_window,run
from scripts.audit_multihour import iso
from tests.test_multihour import T,HOUR


class PublicCollectionTests(unittest.TestCase):
    def payload(self):
        return dict(time=[T,T+HOUR],open=['100','101'],high=['102','103'],
            low=['99','100'],close=['101','102'],vol=['50','60'])

    def test_exact_complete_window_and_fair_without_volume(self):
        p=self.payload();bars=parse_window(p,T,T+2*HOUR)
        self.assertEqual(len(bars),2)
        self.assertEqual(bars[0].volume,D(50))
        del p['vol'];fair=parse_window(p,T,T+2*HOUR,fair=True)
        self.assertEqual(fair[0].volume,D(0))

    def test_gap_is_rejected_instead_of_silently_shortening_sample(self):
        with self.assertRaises(ValueError):parse_window(self.payload(),T,T+3*HOUR)

    def test_conflicting_duplicates_are_rejected(self):
        p=self.payload();p['time'][1]=T
        with self.assertRaises(ValueError):parse_window(p,T,T+2*HOUR)

    def test_unequal_arrays_fail(self):
        p=self.payload();p['close'].pop()
        with self.assertRaises(ValueError):parse_window(p,T,T+2*HOUR)

    def client(self,broken=False):
        payload=self.payload();contract=DemoClient(T).contracts()[0]
        class PublicFake:
            def server_time(self):return T+2*HOUR+10
            def contracts(self):return [contract]
            def _symbol(self,symbol):return symbol
            def _get(self,path,params):
                if 'funding_rate/history' in path:
                    return dict(totalPage=1,resultList=[dict(symbol=contract['symbol'],
                        settleTime=t*1000,fundingRate='.0001',collectCycle=8)
                        for t in [T-8*HOUR,T,T+8*HOUR]])
                if broken:return {'time':[]}
                return payload
        return PublicFake(),contract['symbol']

    def test_complete_public_collection_round_trip(self):
        client,symbol=self.client()
        with TemporaryDirectory() as td:
            p=Path(td)/'protocol.json';out=Path(td)/'out'
            p.write_text(json.dumps(dict(symbols=[symbol],collect_start_utc=iso(T),
                collect_end_utc=iso(T+2*HOUR))))
            result=run(p,out,client)
            self.assertFalse(result['errors'])
            data=json.loads(gzip.decompress((out/(symbol+'.json.gz')).read_bytes()))
            self.assertEqual(len(data['hourly']),2)
            self.assertEqual(len(data['fair']),2)
            self.assertTrue((out/'manifest.json').exists())

    def test_failed_symbol_is_recorded_and_batch_fails(self):
        client,symbol=self.client(broken=True)
        with TemporaryDirectory() as td:
            p=Path(td)/'protocol.json';out=Path(td)/'out'
            p.write_text(json.dumps(dict(symbols=[symbol],collect_start_utc=iso(T),
                collect_end_utc=iso(T+2*HOUR))))
            with self.assertRaises(ValueError):run(p,out,client)
            result=json.loads((out/'manifest.json').read_text())
            self.assertIn(symbol,result['errors'])
            self.assertFalse(result['ok'])

    def test_unavailable_server_leaves_an_explicit_error_artifact(self):
        class Unavailable:
            def server_time(self):raise ValueError('Public API unavailable')
        with TemporaryDirectory() as td:
            p=Path(td)/'protocol.json';out=Path(td)/'out'
            p.write_text(json.dumps(dict(symbols=['A'],collect_start_utc=iso(T),
                collect_end_utc=iso(T+2*HOUR))))
            with self.assertRaises(ValueError):run(p,out,Unavailable())
            self.assertEqual(json.loads((out/'collection_error.json').read_text())['status'],
                'FAILED_BEFORE_COLLECTION')
