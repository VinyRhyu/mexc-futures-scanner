import unittest
from unittest.mock import patch
from mexc_scanner.config import Config
from mexc_scanner.models import Candle, Contract, D
from scripts.audit_portfolio import simulate,time_exit
from scripts.audit_pullback import iso
from scripts.audit_sustained_trigger import MODE

T=1793502000

def row(offset=0,symbol='TEST_USDT'):
    return {'id':str(offset)+symbol,'symbol':symbol,'side':'LONG','formed_at':iso(T),
        'level':'101','lower':'99','upper':'101','atr':'2',
        'M1':{'signal':T+60,'reference':'101.3','entry_low':'101.21','entry_high':'101.8',
              'stop':'100','target':'103','target_origin':'TEST'},MODE:{'signal':T+120+offset}}

class PortfolioTests(unittest.TestCase):
    def setUp(self):
        c=Contract('TEST_USDT',D('.001'),D(1),D(1),D('.01'),20,D('.005'),D('.0004'))
        m={T+i*60:Candle(T+i*60,60,D('101.3'),D('101.4'),D('101.2'),D('101.3')) for i in range(400)}
        self.data={'TEST_USDT':{'contract':c,'minute_map':m}}

    def test_no_overlap_and_balance_is_reinvested_only_after_exit(self):
        balances=[]
        def quote(p,v,c,price,now,cfg):
            balances.append(D(cfg.initial_balance))
            return {'status':'VIAVEL_SIMULADO','base_quantity':'1','loss_usdt':'5',
                    'contracts':'1','leverage':2,'margin_usdt':'10'}
        outcomes=[{'outcome':'ALVO','net_usdt':'5','exited_at':iso(T+420)},
                  {'outcome':'STOP','net_usdt':'-5.5','exited_at':iso(T+900)}]
        with patch('scripts.audit_portfolio.paper_quote',side_effect=quote),patch('scripts.audit_portfolio.close_outcome',side_effect=outcomes):
            r=simulate([row(600),row(60),row()],self.data,Config())
        self.assertEqual(balances,[D(50),D(55)])
        self.assertEqual(r['final_balance'],'49.5')
        self.assertEqual(r['skips']['POSICAO_EM_ABERTO'],1)
        self.assertEqual(r['maximum_realized_drawdown_percent'],'10.0')

    def test_financially_blocked_candidates_are_not_forced_into_trades(self):
        with patch('scripts.audit_portfolio.paper_quote',return_value={'status':'BLOQUEADA','reasons':['MARGEM']}):
            r=simulate([row()],self.data,Config())
        self.assertEqual(r['entries'],0)
        self.assertEqual(r['final_balance'],'50')

    def test_tracing_does_not_change_wallet_and_records_each_candidate(self):
        decisions=[]
        blocked={'status':'BLOQUEADA','reasons':['MARGEM']}
        with patch('scripts.audit_portfolio.paper_quote',return_value=blocked):
            plain=simulate([row(),row()],self.data,Config())
            traced=simulate([row(),row()],self.data,Config(),decisions=decisions)
        self.assertEqual(plain,traced)
        self.assertEqual([e['status'] for e in decisions],['BLOQUEADA_FINANCEIRO','DUPLICATA'])
        self.assertEqual(decisions[1]['duplicate_of'],decisions[0]['id'])

    def test_time_exit_includes_both_fees_and_slippage(self):
        cfg=Config()
        self.assertLess(time_exit(D(100),D(100),D(1),D('.01'),cfg,'LONG'),0)
        self.assertLess(time_exit(D(100),D(100),D(1),D('.01'),cfg,'SHORT'),0)
        q={'status':'VIAVEL_SIMULADO','base_quantity':'1','loss_usdt':'5','contracts':'1','leverage':2,'margin_usdt':'10'}
        with patch('scripts.audit_portfolio.paper_quote',return_value=q),patch('scripts.audit_portfolio.close_outcome',return_value={'outcome':'ABERTO'}):
            r=simulate([row()],self.data,cfg)
        self.assertEqual(r['outcomes'],{'ENCERRAMENTO_4H':1})
        self.assertLess(D(r['final_balance']),50)

if __name__=='__main__':
    unittest.main()
