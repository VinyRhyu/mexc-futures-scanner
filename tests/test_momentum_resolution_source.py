import gzip,hashlib,json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from mexc_scanner.models import Candle,D,jsonable
from scripts.audit_momentum_intrahour import attach_resolution
from tests.test_multihour import market,T


class ResolutionSourceTests(unittest.TestCase):
    def source(self,root,wrong=False):
        bars=[Candle(T+i*300,300,D(100),D(102) if wrong else D(101),D(99),D(100),D(1)) for i in range(12)]
        row=jsonable(dict(symbol='A',start=T,end=T+3600,timeframe_seconds=300,last=bars,fair=bars))
        raw=json.dumps(row).encode();key='A-'+str(T)
        (root/(key+'.json.gz')).write_bytes(gzip.compress(raw))
        summary=dict(protocol_sha256='frozen',selected=1,complete=1,errors={},datasets=[
            dict(key=key,sha256_uncompressed=hashlib.sha256(raw).hexdigest())])
        raw=json.dumps(summary).encode();(root/'summary.json').write_bytes(raw)
        return dict(intrahour_summary_sha256=hashlib.sha256(raw).hexdigest(),intrahour_protocol_sha256='frozen')

    def test_verified_resolution_is_attached_with_explicit_timeframe(self):
        with TemporaryDirectory() as td:
            root=Path(td);p=self.source(root);markets={'A':market()}
            attach_resolution(markets,root,p)
            self.assertEqual(markets['A']['minute_resolution'][T]['timeframe_seconds'],300)

    def test_inconsistent_intrahour_ohlc_cannot_improve_results(self):
        with TemporaryDirectory() as td:
            root=Path(td);p=self.source(root,True)
            with self.assertRaises(ValueError):attach_resolution({'A':market()},root,p)
