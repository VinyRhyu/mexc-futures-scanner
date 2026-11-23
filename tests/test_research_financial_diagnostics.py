"""Offline tests proving financial research cannot cherry-pick winners."""
import unittest
from decimal import Decimal

from scripts.research_financial_diagnostics import (
    analyze_financial_robustness, dedupe_scenario, paired_repricing,
    select_at_quote, summarize_selected, SCENARIOS,
)


def trade(name, symbol, signal, rr, result, entry, exit_time, viable=True, late=False):
    outcome="ALVO" if Decimal(result)>0 else "STOP"
    values={}
    for _,(key,balance,slip) in SCENARIOS.items():
        values[key]=(
            {"status":"FILLED_SIMULATED","entry_at":entry,"exit_at":exit_time,
             "outcome":outcome,"net_r":result,"net_usdt":str(Decimal(result)/10),
             "net_rr":rr}
            if viable else {"status":"FINANCIAL_BLOCK","reasons":["CUSTO_RELATIVO_ELEVADO"]})
    return {
        "plan_id":name,"symbol":symbol,"side":"LONG","signal_at":signal,
        "historical_group":"core_liquidity",
        "causal_context":{"A_late":late,"B_against_h1":False,"A_or_B":late},
        **values,
    }


class FinancialEdgeTests(unittest.TestCase):
    def setUp(self):
        t1="2026-11-08T12:00:00+00:00"
        t2="2026-11-08T12:03:00+00:00"
        self.a=trade("a","BTC_USDT",t1,"1.2","-1",t1,
                     "2026-11-08T12:15:00+00:00",late=False)
        self.b=trade("b","ETH_USDT",t2,"1.8","1.3",t2,
                     "2026-11-08T12:10:00+00:00",late=False)
        self.c=trade("c","SOL_USDT","2026-11-08T12:16:00+00:00","2.1","-1",
                     "2026-11-08T12:16:00+00:00","2026-11-08T13:00:00+00:00",
                     late=True)

    def test_threshold_decision_only_uses_pre_entry_net_rr(self):
        first=select_at_quote([self.a,self.b,self.c],"cost_base",Decimal("1.5"))
        self.assertEqual([x["plan_id"] for x in first],["b","c"])
        self.a["cost_base"]["net_r"]="100"
        self.b["cost_base"]["net_r"]="-100"
        again=select_at_quote([self.a,self.b,self.c],"cost_base",Decimal("1.5"))
        self.assertEqual([x["plan_id"] for x in again],["b","c"])

    def test_portfolio_reallocation_does_not_just_remove_baseline_losers(self):
        base=select_at_quote([self.a,self.b,self.c],"cost_base")
        filtered=select_at_quote([self.a,self.b,self.c],"cost_base",D("1.5"))
        self.assertEqual([x["plan_id"] for x in base],["a","c"])
        self.assertEqual([x["plan_id"] for x in filtered],["b","c"])

    def test_dedupe_preserves_a_losing_plan_id_even_if_alternative_wins(self):
        copy=trade("a-2","BTC_USDT",self.a["signal_at"],"2.5","3.5",
                   self.a["cost_base"]["entry_at"],self.a["cost_base"]["exit_at"])
        rows, dupes=dedupe_scenario([copy,self.a],"cost_base")
        self.assertEqual(dupes,1)
        self.assertEqual(rows[0]["plan_id"],"a")
        self.assertEqual(rows[0]["cost_base"]["net_r"],"-1")

    def test_partial_cost_stress_has_no_fake_negative_trade(self):
        self.a["cost_mid"]={"status":"FINANCIAL_BLOCK","reasons":["PRECO_FORA_DO_PLANO"]}
        stats=paired_repricing([self.a,self.b],"cost_mid")
        self.assertEqual(stats["base_selected"],2)
        self.assertEqual(stats["still_simulated_filled"],1)
        self.assertEqual(stats["not_filled_under_compare"],1)
        self.assertEqual(stats["block_reasons"]["PRECO_FORA_DO_PLANO"],1)
        self.assertEqual(Decimal(stats["on_shared_fills_base_net_r"]),Decimal("1.3"))

    def test_full_comparison_reports_both_wallets_all_costs(self):
        self.a["wallet_1usdt"]={"status":"FINANCIAL_BLOCK",
                                 "reasons":["LOTE_MINIMO_OU_META_EXCEDE_RISCO"]}
        result=analyze_financial_robustness([self.a,self.b,self.c])
        self.assertEqual(len(result["scenarios"]),6)
        self.assertEqual(result["scenarios"]["1usd_base"]["portfolio_BASE"]["trades"],2)
        self.assertEqual(result["scenarios"]["50usd_base"]["portfolio_BASE"]["trades"],2)
        self.assertEqual(result["historical_5m_confirmations"],3)
        self.assertEqual(len(result["exploratory_minimum_projected_RR"]["50usd_base"]),4)
        self.assertEqual(len(result["exploratory_minimum_projected_RR"]),6)
        self.assertEqual(len(result["exploratory_minimum_projected_RR"]["1usd_stress"]),4)
        self.assertEqual(result["scenarios"]["1usd_base"]["blocking_reasons_by_plan"]
                         ["LOTE_MINIMO_OU_META_EXCEDE_RISCO"],1)

    def test_missing_net_rr_on_filled_does_not_silently_drop_trade(self):
        self.b["cost_base"].pop("net_rr")
        with self.assertRaisesRegex(ValueError,"missing pre-entry"):
            select_at_quote([self.b],"cost_base",D("1.5"))

    def test_missing_wallet_cost_scenario_fails_closed(self):
        self.a.pop("wallet_1usdt_stress")
        with self.assertRaisesRegex(ValueError,"all six"):
            analyze_financial_robustness([self.a])


def D(x):
    return Decimal(x)


if __name__=="__main__":
    unittest.main()
