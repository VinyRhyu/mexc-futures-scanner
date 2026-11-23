"""PRD ENTRY layout: no new target, leverage or signal decision is introduced."""
from copy import deepcopy
import unittest

from mexc_scanner.config import Config, load_config
from mexc_scanner.finance import evaluate
from mexc_scanner.models import D, jsonable
from mexc_scanner.reporting import plan_message, number
from scripts.telegram_preview import preview_message
from tests.test_finance import NOW, context


class ProductionEntryLayoutTests(unittest.TestCase):
    def approved(self, side="LONG"):
        p,v,c,t,b,f=context(side)
        p.status="ATIVO"
        v.financial=evaluate(p,v,c,D("1"),t,b,f,NOW,Config())
        self.assertEqual(v.financial["status"],"VIAVEL_SIMULADO")
        p.variants[v.kind]=v
        return p,v

    def test_seven_fields_top_to_bottom_with_real_approved_levels_for_both_directions(self):
        for side in ("LONG","SHORT"):
            with self.subTest(side=side):
                p,v=self.approved(side)
                state=deepcopy(jsonable(p))
                message=plan_message(p,"paper",NOW,v)
                lines=message.splitlines()
                expected=[
                    "MOEDA: "+p.symbol.replace("_","/"),
                    "MOVIMENTO: "+("ALTA (LONG)" if side=="LONG" else "BAIXA (SHORT)"),
                    "ALAVANCAGEM: "+str(v.financial["leverage"])+"x",
                    "ENTRADA: "+number(v.financial["entry_low"])+" a "+number(v.financial["entry_high"]),
                    "TP1: "+number(v.target)+" (",
                    "TP2: não definido (sem segundo alvo técnico validado)",
                    "SL: "+number(v.stop)+" (",
                ]
                indices=[next(i for i,l in enumerate(lines) if l.startswith(prefix)) for prefix in expected]
                self.assertEqual(indices,sorted(indices))
                self.assertEqual(indices[0],1)
                self.assertEqual(message.count("TP1:"),1)
                self.assertEqual(message.count("TP2:"),1)
                self.assertEqual(message.count("SL:"),1)
                self.assertIn("líquido sobre a margem)",message)
                self.assertIn("Margem isolada estimada:",message)
                self.assertIn("Taxa por execução:",message)
                self.assertLess(len(message),3500)
                self.assertEqual(state,jsonable(p))

    def test_production_preview_contains_exact_fields_and_explicitly_no_tp2(self):
        example=preview_message(NOW)
        for label in ("MOEDA:","MOVIMENTO:","ALAVANCAGEM:","ENTRADA:","TP1:","TP2:","SL:"):
            self.assertIn(label,example)
        self.assertIn("não definido",example)
        self.assertTrue(example.startswith("EXEMPLO FICTÍCIO — NÃO OPERAR"))

    def test_blocked_technical_plan_never_masquerades_as_entry(self):
        p,v=self.approved()
        v.financial={"status":"BLOQUEADA","reasons":["PRECO_FORA_DO_PLANO"]}
        message=plan_message(p,"paper",NOW,v)
        self.assertIn("ENTRADA BLOQUEADA",message)
        self.assertIn("Faixa do plano",message)
        self.assertNotIn("ALAVANCAGEM:",message)
        self.assertNotIn("TP2:",message)

    def test_restricted_watch_never_masquerades_as_actionable_entry(self):
        p,v=self.approved()
        message=plan_message(p,"paper",NOW,v,restriction="Há posição pendente.")
        self.assertIn("APENAS ACOMPANHAMENTO",message)
        self.assertNotIn("MOEDA:",message)
        self.assertNotIn("TP2:",message)

    def test_real_mode_header_uses_only_real_viability_flag(self):
        p,v=self.approved()
        v.financial=dict(v.financial,status="VIAVEL_REAL")
        message=plan_message(p,"real",NOW,v)
        self.assertIn("ENTRADA VALIDADA",message)
        self.assertIn("MOEDA:",message)
        self.assertIn("TP2: não definido",message)
        # A paper approval alone is not a real viable order.
        v.financial["status"]="VIAVEL_SIMULADO"
        blocked=plan_message(p,"real",NOW,v)
        self.assertIn("ENTRADA BLOQUEADA",blocked)
        self.assertNotIn("TP2:",blocked)

    def test_leverage_policy_not_changed_by_notification_format(self):
        cfg=load_config("config/default.toml")
        self.assertEqual((cfg.minimum_leverage,cfg.max_leverage),(10,20))
        self.assertEqual(cfg.mode,"paper")


if __name__=="__main__":
    unittest.main()
