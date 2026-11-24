"""Only financially confirmed entries are eligible for Telegram delivery.

The technical first-M1 movement is still computed internally by the scanner.
There must be no unsolicited Telegram notification before full confirmation.
"""
from copy import deepcopy
import unittest

from mexc_scanner.config import Config
from mexc_scanner.engine import _queue_transitions, run_scan
from mexc_scanner.finance import evaluate
from mexc_scanner.mexc import SourceError
from mexc_scanner.minute_breakout import MODEL
from mexc_scanner.models import D, jsonable, stable_id
from mexc_scanner.state import initial_state, queue_message
from mexc_scanner.telegram import allowed_scanner_alert, drain_outbox
from mexc_scanner.watch_notifications import STRATEGY
from tests.test_finance import NOW, context


def candidate(side="LONG", symbol="TEST_USDT", phase="waiting"):
    p,v,c,t,b,f=context(side)
    p.id=symbol+"-"+side
    p.symbol,p.strategy,p.status=symbol,STRATEGY,"POSSIVEL"
    p.level=p.upper if side=="LONG" else p.lower
    if phase=="waiting":
        v.status="AGUARDANDO_CONFIRMACAO"
        v.triggered_at=NOW-5
        p.entry_started_at=NOW-5
        p.variants[v.kind]=v
    if phase in ("blocked","ready"):
        p.status,v.kind="ATIVO","CONFIRMADA"
        v.financial=(evaluate(p,v,c,D(1),t,b,f,NOW,Config()) if phase=="ready"
                     else {"status":"BLOQUEADA","reasons":["PRECO_FORA_DO_PLANO"]})
        p.variants[v.kind]=v
    return p


class WatchNotificationsTests(unittest.TestCase):
    def state(self,*plans):
        state=initial_state(Config())
        state["plans"]={p.id:jsonable(p) for p in plans}
        return state

    def pending(self,state,category=None):
        return [m for m in state["outbox"].values()
                if m["status"]=="PENDING" and
                   (category is None or m["category"]==category)]

    def test_untriggered_pattern_does_not_queue_telegram(self):
        s=self.state(candidate(phase="possible"))
        before=deepcopy(s["plans"])
        _queue_transitions(s,{},Config(),NOW)
        self.assertEqual(self.pending(s),[])
        self.assertEqual(before,s["plans"])

    def test_first_m1_unconfirmed_never_queues_telegram(self):
        for side in ("LONG","SHORT"):
            s=self.state(candidate(side))
            before=deepcopy(s["plans"])
            _queue_transitions(s,{},Config(),NOW)
            self.assertEqual(self.pending(s),[])
            self.assertEqual(before,s["plans"])

    def test_first_m1_does_not_notify_on_repeated_scans(self):
        s=self.state(candidate())
        _queue_transitions(s,{},Config(),NOW)
        _queue_transitions(s,deepcopy(s["plans"]),Config(),NOW+1)
        self.assertEqual(s["outbox"],{})

    def test_blocked_confirmation_does_not_notify(self):
        s=self.state(candidate(phase="blocked"))
        _queue_transitions(s,{},Config(),NOW)
        self.assertEqual(self.pending(s),[])

    def test_only_validated_confirmation_queues_exact_entry(self):
        p=candidate(phase="ready")
        s=self.state(p,candidate("SHORT"))
        _queue_transitions(s,{},Config(),NOW)
        notices=self.pending(s)
        self.assertEqual(len(notices),1)
        m=notices[0]
        self.assertEqual(m["category"],"ENTRY")
        self.assertEqual(m["notification_format"],"entry_only_v2")
        self.assertEqual(m["id"],stable_id(p.id,"CONFIRMADA","GATILHO","paper"))
        self.assertEqual(len(m["text"].splitlines()),10)
        self.assertIn("🟢 SINAL DE ENTRADA • SIMULAÇÃO",m["text"])
        self.assertNotIn("MOVIMENTO DETECTADO",m["text"])
        self.assertTrue(allowed_scanner_alert(m))

    def test_existing_legacy_movement_pending_suppressed_even_with_valid_schema(self):
        s=self.state(candidate())
        mtext="\\n".join([
            "🟡 MOVIMENTO DETECTADO • POSSÍVEL ENTRADA",
            "MOEDA: TEST/USDT",
            "MOVIMENTO: 📈 LONG (ALTA)",
            "STATUS: aguardando segundo fechamento M1 e avaliação financeira.",
        ])
        queue_message(s,"old-first-m1",mtext,NOW,NOW+60)
        old=s["outbox"]["old-first-m1"]
        old.update(notification_format="movement_only_v2",watch_stage=1,
                   movement_at=NOW,watch_symbol="TEST_USDT")
        self.assertFalse(allowed_scanner_alert(old))
        _queue_transitions(s,{},Config(),NOW)
        result=drain_outbox(s,NOW,"token","chat",
                            transport=lambda p:self.fail("No movement alerts"))
        self.assertEqual(result["sent"],0)
        self.assertEqual(result["suppressed"],1)
        self.assertEqual(old["status"],"EXPIRED")
        self.assertEqual(old["attempts"],0)

    def test_pending_first_m1_is_suppressed_but_validated_entry_delivers(self):
        p=candidate(phase="ready")
        s=self.state(p)
        queue_message(s,"old-first-m1","🟡 MOVIMENTO DETECTADO",NOW,NOW+60)
        s["outbox"]["old-first-m1"].update(
            notification_format="movement_only_v2",watch_stage=1,
            movement_at=NOW,watch_symbol="TEST_USDT")
        _queue_transitions(s,{},Config(),NOW)
        sent=[]
        def send(payload):
            sent.append(payload["text"])
            return {"ok":True,"result":{"message_id":len(sent)}}
        result=drain_outbox(s,NOW,"token","chat",transport=send)
        self.assertEqual(len(sent),1)
        self.assertEqual(sent[0].splitlines()[0],"🟢 SINAL DE ENTRADA • SIMULAÇÃO")
        self.assertEqual(result["suppressed"],1)
        self.assertEqual(result["sent"],1)

    def test_source_failure_stays_internal_without_entry_or_watch(self):
        s=self.state(candidate())
        s["active_signal_model"]=MODEL
        class Failure:
            def server_time(self):
                raise SourceError("Synthetic source failure")
        report,_=run_scan(Failure(),Config(),s,{"TEST"},now=NOW,signal_model=MODEL)
        self.assertEqual(report["source_status"],"FALHA")
        self.assertEqual(self.pending(s),[])

    def test_closed_or_expired_plan_does_not_notify(self):
        s=self.state(candidate(phase="ready"))
        for plan in s["plans"].values():
            plan["status"]="EXPIRADO"
            plan["reason"]="PRAZO_ENCERRADO"
        _queue_transitions(s,{},Config(),NOW)
        self.assertEqual(self.pending(s),[])

    def test_old_non_entry_notifications_stay_suppressed_and_sent_history_remains(self):
        s=self.state(candidate())
        for key in ("summary","preparation","source-error","plan-update","blocked"):
            queue_message(s,key,"diagnostic "+key,NOW,NOW+100)
        s["outbox"]["plan-update"]["status"]="SENT"
        _queue_transitions(s,{},Config(),NOW)
        result=drain_outbox(s,NOW,"token","chat",
                            transport=lambda p:self.fail("No unsolicited diagnostics"))
        self.assertEqual(result["sent"],0)
        self.assertEqual(result["suppressed"],4)
        self.assertEqual(s["outbox"]["plan-update"]["status"],"SENT")


if __name__=="__main__":
    unittest.main()
