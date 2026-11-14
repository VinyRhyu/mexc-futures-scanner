from copy import deepcopy
import unittest

from mexc_scanner.models import Candle,Contract,D
from scripts.audit_relative_momentum_daily import (HOUR,DAY,daily_bars,select,prepare,
                                                  hour_funding,funding_coverage,close_position)


def market(symbol='TEST_USDT',rising=True):
    c=Contract(symbol,D('.01'),D(1),D(1),D('.01'),20,D('.005'),D('.0004'))
    bars={}
    for i in range(30*24):
        price=D(100)+D(i)*D('.01')*(1 if rising else -1)
        bars[i*HOUR]=Candle(i*HOUR,HOUR,price,price,price,price,D(1000000))
    return dict(contract=c,hourly=bars,daily=daily_bars(bars),funding={})


class RelativeMomentumAuditTests(unittest.TestCase):
    def test_ranking_and_atr_cannot_see_future_prices(self):
        data={'A_USDT':market('A_USDT'), 'B_USDT':market('B_USDT',False)}
        signal=20*DAY;before=select(data,signal);changed=deepcopy(data)
        for m in changed.values():
            for ts in list(m['hourly']):
                if ts>=signal:m['hourly'][ts]=Candle(ts,HOUR,D(1),D(1),D(1),D(1),D(0))
            m['daily']=daily_bars(m['hourly'])
        self.assertEqual(before,select(changed,signal))
        self.assertEqual({(s['symbol'],s['sign']) for s in before[0]}, {('A_USDT',1),('B_USDT',-1)})

    def test_portfolio_sizing_respects_joint_risk_and_dollar_lot_limits(self):
        data={f'C{i}_USDT':market(f'C{i}_USDT') for i in range(6)}
        signals=[dict(symbol=s,sign=1,weight=D('.2'),return7=D('.1'),atr14=D(2)) for s in data]
        positions,_,small,_=prepare(signals,data,20*DAY+HOUR,D(1000))
        self.assertTrue(positions)
        self.assertLessEqual(sum(p['planned_risk'] for p in positions),D(20))
        self.assertEqual(small['below_min_lot'],6)
        self.assertLessEqual(sum(p['initial_notional'] for p in positions),D(1000))

    def test_positive_funding_is_paid_by_long_received_by_short(self):
        b=Candle(0,HOUR,D(100),D(100),D(100),D(100))
        long=dict(sign=1,quantity=D(10),opened_at=-1)
        short=dict(long,sign=-1)
        rates={HOUR:D('.0001')}
        self.assertEqual(hour_funding(long,b,rates,False)[0],-D('.1'))
        self.assertEqual(hour_funding(short,b,rates,False)[0],D('.1'))
        self.assertEqual(hour_funding(dict(long,opened_at=HOUR),b,rates,False)[0],D(0))

    def test_stopped_trade_does_not_pay_a_later_settlement(self):
        b=Candle(0,HOUR,D(100),D(101),D(90),D(95))
        pos=dict(sign=1,quantity=D(10),opened_at=-1)
        self.assertEqual(hour_funding(pos,b,{HOUR:D('.001')},True)[0],D(0))
        self.assertFalse(funding_coverage([dict(ts=t) for t in [0,8*HOUR,24*HOUR]],HOUR,23*HOUR))

    def test_fees_and_execution_costs_are_not_hidden_at_flat_market_exit(self):
        c=market()['contract'];entry=D('100.03')
        pos=dict(symbol='TEST_USDT',sign=1,entry_fill=entry,entry_fee=entry*D('.0006'),
                 quantity=D(1),funding_cash=D(0))
        trade,_=close_position(pos,D(100),DAY,'TIME',c)
        self.assertLess(trade['net_pnl'],D(0))


if __name__=='__main__':unittest.main()
