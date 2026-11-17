from dataclasses import replace
import unittest

from mexc_scanner.config import Config
from mexc_scanner.finance import evaluate
from mexc_scanner.models import Contract, D, Plan, Variant


NOW = 1794177030


def context(side="LONG"):
    plan = Plan("p", "TEST_USDT", "CONTINUACAO", side, NOW - 60, NOW, NOW + 1800,
                D(1), D(100), D(99), D(101), D(98 if side == "LONG" else 102), "family")
    v = Variant("ANTECIPADA", NOW - 60, D(100), D("99.95"), D("100.05"),
                D(98 if side == "LONG" else 102), D(106 if side == "LONG" else 94), "SYNTHETIC")
    contract = Contract("TEST_USDT", D("0.001"), D(1), D(1), D("0.001"), 20, D("0.005"), D("0.0004"))
    ticker = {"bid1": "99.99", "ask1": "100.01", "timestamp": NOW * 1000}
    depth = {"asks": [["100.01", "1000000", 1]], "bids": [["99.99", "1000000", 1]], "timestamp": NOW * 1000}
    funding = {"fundingRate": "0", "collectCycle": 8, "nextSettleTime": (NOW + 8 * 3600) * 1000}
    return plan, v, contract, ticker, depth, funding


class FinanceTests(unittest.TestCase):
    def calculate(self, side="LONG", config=None, contract_override=None, **kw):
        p, v, c, t, b, f = context(side)
        return evaluate(p, v, contract_override or c, D(1), t, b, f, NOW, config or Config())

    def test_one_dollar_synthetic_trade_can_fit(self):
        result = self.calculate()
        self.assertEqual(result["status"], "VIAVEL_SIMULADO")
        self.assertGreaterEqual(result["net_rr"], 2)
        self.assertLess(result["gain_usdt"], D("0.60"))
        self.assertFalse(result["daily_goal_reachable_in_one_trade"])
        self.assertLessEqual(result["loss_usdt"], D("0.10"))
        self.assertLessEqual(result["margin_usdt"] + result["costs_usdt"], 1)
        self.assertLessEqual(result["leverage"], 20)

    def test_short_has_symmetric_budget(self):
        result = self.calculate("SHORT")
        self.assertEqual(result["status"], "VIAVEL_SIMULADO")
        self.assertGreaterEqual(result["net_rr"], 2)
        self.assertLess(result["gain_fraction"], D("0.60"))
        self.assertLessEqual(result["loss_fraction"], D("0.10"))

    def test_large_upside_can_reach_daily_goal_without_extra_risk(self):
        p, v, c, t, b, f = context()
        v.target = D(120)
        result = evaluate(p, v, c, D(1), t, b, f, NOW, Config())
        self.assertEqual(result["status"], "VIAVEL_SIMULADO")
        self.assertTrue(result["daily_goal_reachable_in_one_trade"])
        self.assertGreaterEqual(result["gain_fraction"], D("0.60"))
        self.assertLessEqual(result["loss_fraction"], D("0.10"))

    def test_large_minimum_is_not_silently_rounded_down(self):
        c = replace(context()[2], min_volume=D(1000000))
        result = self.calculate(contract_override=c)
        self.assertEqual(result["status"], "BLOQUEADA")
        self.assertIn("LOTE_MINIMO_OU_META_EXCEDE_RISCO", result["reasons"])

    def test_leverage_limit_not_increased_to_fit(self):
        c = replace(context()[2], max_leverage=1)
        result = self.calculate(contract_override=c)
        self.assertIn("MARGEM_OU_TETO_DE_ALAVANCAGEM", result["reasons"])

    def test_worst_price_rr_narrows_band_without_moving_stop(self):
        p, v, c, t, b, f = context()
        v.stop, v.target = D(99), D(104)
        v.entry_low, v.entry_high = D("99.8"), D("101.5")
        result = evaluate(p, v, c, D(1), t, b, f, NOW, replace(Config(), taker_fee="0.0004"))
        self.assertEqual(result["status"], "VIAVEL_SIMULADO")
        self.assertLess(result["entry_high"], D("101.5"))
        self.assertGreaterEqual(result["net_rr"], 2)
        self.assertEqual((v.stop, v.target), (D(99), D(104)))

    def test_stale_quote_blocks_execution(self):
        p, v, c, t, b, f = context()
        t["timestamp"] = (NOW - 500) * 1000
        result = evaluate(p, v, c, D(1), t, b, f, NOW, Config())
        self.assertIn("DADOS_NAO_VERIFICADOS", result["reasons"])

    def test_insufficient_book_is_not_assumed_liquid(self):
        p, v, c, t, b, f = context()
        b["asks"] = [["100.01", "1", 1]]
        result = evaluate(p, v, c, D(1), t, b, f, NOW, Config())
        self.assertIn("PROFUNDIDADE_INSUFICIENTE", result["reasons"])

    def test_unverified_fees_cannot_release_real(self):
        result = self.calculate(config=replace(Config(), mode="real"))
        self.assertEqual(result["status"], "BLOQUEADA")
        self.assertIn("TAXA_PESSOAL_NAO_VERIFICADA", result["real_gates"])

    def test_receiving_funding_is_not_guaranteed_profit(self):
        p, v, c, t, b, f = context("SHORT")
        f.update({"fundingRate": "0.001", "nextSettleTime": (NOW + 3600) * 1000})
        result = evaluate(p, v, c, D(1), t, b, f, NOW, Config())
        self.assertEqual(result["funding_cost_rate"], 0)

    def test_quantity_uses_contract_increment(self):
        c = replace(context()[2], volume_step=D(3), min_volume=D(3))
        result = self.calculate(contract_override=c)
        self.assertEqual(result["contracts"] % 3, 0)

    def band_cost_case(self, side='LONG'):
        p, v, c, t, b, f = context(side)
        v.stop, v.target = (D(99), D(104)) if side == 'LONG' else (D(101), D(96))
        v.entry_low, v.entry_high = ((D('99.05'), D('100.05')) if side == 'LONG' else
                                   (D('99.95'), D('100.95')))
        t.update(bid1='100', ask1='100')
        b.update(bids=[['100', '1000000', 1]], asks=[['100', '1000000', 1]])
        return p, v, c, t, b, f

    def test_cost_at_best_endpoint_cannot_reject_viable_current_price(self):
        for side in ('LONG', 'SHORT'):
            with self.subTest(side=side):
                p, v, c, t, b, f = self.band_cost_case(side)
                old_low, old_high, old_stop, old_target = v.entry_low, v.entry_high, v.stop, v.target
                r = evaluate(p, v, c, D(1), t, b, f, NOW, Config())
                self.assertEqual(r['status'], 'VIAVEL_SIMULADO')
                self.assertEqual((r['entry_low'], r['entry_high']), (D(100), D(100)))
                self.assertGreaterEqual(r['net_rr'], 2)
                self.assertLessEqual(r['loss_usdt'], D('0.10'))
                self.assertLessEqual(r['costs_usdt'], D('0.03'))
                self.assertLessEqual(r['leverage'], 20)
                self.assertEqual((v.entry_low, v.entry_high, v.stop, v.target),
                                 (old_low, old_high, old_stop, old_target))

    def test_retry_cannot_expand_original_entry_band(self):
        p, v, c, t, b, f = self.band_cost_case()
        t.update(bid1='100.5', ask1='100.5')
        b.update(asks=[['100.5', '1000000', 1]])
        r = evaluate(p, v, c, D(1), t, b, f, NOW, Config())
        self.assertEqual(r['status'], 'BLOQUEADA')

    def test_retry_keeps_rr_depth_and_real_verification_gates(self):
        for failure in ('rr', 'depth', 'real', 'margin'):
            with self.subTest(failure=failure):
                p, v, c, t, b, f = self.band_cost_case()
                cfg = Config()
                if failure == 'rr':
                    v.target = D('100.2')
                elif failure == 'depth':
                    b['asks'] = [['100', '1', 1]]
                elif failure == 'real':
                    cfg = replace(cfg, mode='real')
                elif failure == 'margin':
                    c = replace(c, max_leverage=1)
                r = evaluate(p, v, c, D(1), t, b, f, NOW, cfg)
                self.assertEqual(r['status'], 'BLOQUEADA')
