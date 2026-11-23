"""Regression: compact MEXC Telegram ENTRY is presentation-only, fail closed."""
from copy import deepcopy
import unittest

from mexc_scanner.config import Config
from mexc_scanner.demo import DemoClient
from mexc_scanner.engine import run_scan
from mexc_scanner.finance import evaluate
from mexc_scanner.models import D, jsonable
from mexc_scanner.reporting import entry_signal_message
from mexc_scanner.state import initial_state
from scripts.telegram_preview import preview_message
from tests.test_finance import NOW, context


class ProductionEntryLayoutTests(unittest.TestCase):
    def ready(self, side="LONG"):
        plan, variant, contract, ticker, book, funding = context(side)
        plan.status = "ATIVO"
        variant.financial = evaluate(
            plan, variant, contract, D("1"), ticker, book, funding, NOW, Config())
        self.assertEqual(variant.financial["status"], "VIAVEL_SIMULADO")
        plan.variants[variant.kind] = variant
        return plan, variant

    def test_requested_labels_appear_exactly_in_entry_order(self):
        p,v=self.ready()
        before=deepcopy(jsonable(p))
        text=entry_signal_message(p,"paper",NOW,v)
        positions=[text.index(x) for x in (
            "MOEDA:", "MOVIMENTO:", "ALAVANCAGEM:", "ENTRADA:",
            "TP1:", "TP2:", "SL:",
        )]
        self.assertEqual(positions,sorted(positions))
        self.assertIn("MOVIMENTO: 📈 LONG (ALTA)",text)
        self.assertIn("MOEDA: TEST/USDT",text)
        self.assertEqual(text.count("TP1:"),1)
        self.assertEqual(text.count("TP2:"),1)
        self.assertEqual(text.count("SL:"),1)
        self.assertIn("ROI líquido estimado sobre a margem",text)
        self.assertIn("TP2: não definido (modelo atual tem apenas um alvo técnico)",text)
        self.assertIn("nenhuma ordem automática",text)
        self.assertIn("Retorno/risco líquido:",text)
        self.assertIn("Taxa por execução: 0.06%",text)
        self.assertLess(len(text),3500)
        self.assertEqual(jsonable(p),before)
        self.assertNotIn("50x",text)

    def test_short_keeps_stop_above_entry_and_tp_below(self):
        p,v=self.ready("SHORT")
        text=entry_signal_message(p,"paper",NOW,v)
        f=v.financial
        self.assertIn("MOVIMENTO: 📉 SHORT (BAIXA)",text)
        self.assertIn("TP1: "+str(v.target.normalize()),text)
        self.assertIn("SL: "+str(v.stop.normalize()),text)
        self.assertGreater(v.stop,D(f["worst_entry"]))
        self.assertLess(v.target,D(f["worst_entry"]))
        self.assertEqual(text.count("TP2:"),1)

    def test_extreme_precision_prices_not_rounded_for_orders(self):
        p,v=self.ready()
        v.financial["entry_low"]=D("0.0000000123456789")
        before=deepcopy(jsonable(p))
        text=entry_signal_message(p,"paper",NOW,v)
        self.assertIn("ENTRADA: 0.0000000123456789",text)
        self.assertEqual(jsonable(p),before)

    def test_no_financial_authorization_is_not_presented_as_entry(self):
        p,v=self.ready()
        v.financial={"status":"BLOQUEADA","reasons":["PRECO_FORA_DO_PLANO"]}
        text=entry_signal_message(p,"paper",NOW,v)
        self.assertIn("ENTRADA BLOQUEADA",text)
        self.assertNotIn("SINAL DE ENTRADA",text)
        self.assertNotIn("ALAVANCAGEM:",text)

    def test_missing_margin_cannot_invent_roi_or_tp2(self):
        p,v=self.ready()
        v.financial.pop("margin_usdt")
        text=entry_signal_message(p,"paper",NOW,v)
        self.assertIn("APENAS ACOMPANHAMENTO",text)
        self.assertNotIn("SINAL DE ENTRADA",text)
        self.assertNotIn("TP1:",text)

    def test_existing_position_restriction_not_hidden(self):
        p,v=self.ready()
        v.financial["status"]="VIAVEL_REAL"
        text=entry_signal_message(p,"real",NOW,v,
            restriction="Já existe uma posição registrada.")
        self.assertIn("APENAS ACOMPANHAMENTO",text)
        self.assertIn("Já existe uma posição",text)
        self.assertNotIn("SINAL DE ENTRADA",text)

    def test_demo_preview_uses_production_layout_without_sending(self):
        text=preview_message(NOW)
        self.assertIn("EXEMPLO FICTÍCIO — NÃO OPERAR",text)
        for field in ("MOEDA:","MOVIMENTO:","ALAVANCAGEM:",
                      "ENTRADA:","TP1:","TP2:","SL:"):
            self.assertIn(field,text)
        self.assertIn("não definido",text)
        self.assertLess(len(text),3500)

    def test_real_engine_queues_same_layout_without_changing_finance(self):
        cfg=Config()
        state=initial_state(cfg)
        client=DemoClient(NOW)
        report,_=run_scan(client,cfg,state,{"DEMO"},now=client.now)
        self.assertEqual(report["source_status"],"OK")
        entries=[m for m in state["outbox"].values()
                 if m["category"]=="ENTRY" and m["status"]=="PENDING"]
        self.assertTrue(entries)
        for m in entries:
            self.assertIn("MOEDA:",m["text"])
            self.assertIn("MOVIMENTO:",m["text"])
            self.assertIn("ALAVANCAGEM:",m["text"])
            self.assertIn("TP1:",m["text"])
            self.assertIn("TP2: não definido",m["text"])
            self.assertIn("SL:",m["text"])
            self.assertEqual(m["attempts"],0)
        self.assertEqual(state["wallet"]["balance"],"1")
        self.assertIsNone(state["wallet"].get("position"))


if __name__=="__main__":
    unittest.main()
