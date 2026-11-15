from copy import deepcopy
import unittest

from mexc_scanner.models import Candle,D
from scripts.audit_momentum_long_context import ema_context,allow_long
from scripts.audit_momentum_week10x import simulate_week
from tests.test_relative_momentum_daily import market,DAY,HOUR


class LongContextTests(unittest.TestCase):
    def test_ema_cannot_read_current_open_or_future_bars(self):
        m=market();decision=20*DAY
        before=ema_context(m,decision);changed=deepcopy(m)
        for ts in changed['hourly']:
            if ts>=decision:changed['hourly'][ts]=Candle(ts,HOUR,D(1),D(1),D(1),D(1),D(1))
        self.assertEqual(before,ema_context(changed,decision))
        self.assertEqual(before['last_bar_end'],decision)

    def test_gate_only_restricts_longs_below_ema(self):
        data={'UP_USDT':market('UP_USDT'),'DOWN_USDT':market('DOWN_USDT',False)}
        self.assertTrue(allow_long(dict(symbol='UP_USDT',sign=1),data,20*DAY))
        self.assertFalse(allow_long(dict(symbol='DOWN_USDT',sign=1),data,20*DAY))
        self.assertTrue(allow_long(dict(symbol='DOWN_USDT',sign=-1),data,20*DAY))
        self.assertTrue(allow_long(dict(symbol='UP_USDT',sign=-1),data,20*DAY))

    def test_blocked_budget_is_not_redistributed_to_shorts(self):
        data={'UP_USDT':market('UP_USDT'),'DOWN_USDT':market('DOWN_USDT',False)}
        for m in data.values():m['fair']=dict(m['hourly'])
        p=dict(reference_equity_usdt=100,evaluation_start_utc=20*DAY,evaluation_end_utc=21*DAY,
               portfolio_risk_fraction='.02',liquidation_stop_buffer='1.6')
        a=simulate_week(data,p,10)
        b=simulate_week(data,p,10,lambda t,m,day:t['sign']<0)
        shorts_a=[t for t in a['trades'] if t['sign']<0]
        self.assertEqual(len(shorts_a),1);self.assertEqual(len(b['trades']),1)
        self.assertEqual(shorts_a[0]['quantity'],b['trades'][0]['quantity'])
        self.assertEqual(shorts_a[0]['stop'],b['trades'][0]['stop'])
        self.assertEqual(b['skips']['LONG_CONTEXT'],1)


if __name__=='__main__':unittest.main()
