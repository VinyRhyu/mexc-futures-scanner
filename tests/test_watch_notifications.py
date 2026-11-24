"""Only a fresh first-M1 watch and an independently validated ENTRY may notify."""
from copy import deepcopy
from dataclasses import replace
import unittest

from mexc_scanner.config import Config
from mexc_scanner.engine import _queue_transitions, run_scan
from mexc_scanner.finance import evaluate
from mexc_scanner.mexc import SourceError
from mexc_scanner.minute_breakout import MODEL
from mexc_scanner.models import D, jsonable, stable_id
from mexc_scanner.state import initial_state, queue_message
from mexc_scanner.telegram import drain_outbox
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

    def test_no_watch_when_pattern_only_exists_without_first_m1(self):
        s=self.state(candidate(phase="possible"),candidate("SHORT",phase="possible"))
        before=deepcopy(s["plans"])
        _queue_transitions(s,{},Config(),NOW)
        self.assertEqual(self.pending(s),[])
        self.assertEqual(before,s["plans"])

    def test_fresh_first_m1_only_has_short_meaningful_watch(self):
        s=self.state(candidate(),candidate("SHORT",phase="possible"))
        _queue_transitions(s,{},Config(),NOW)
        notices=self.pending(s)
        self.assertEqual(len(notices),1)
        m=notices[0]
        self.assertEqual(m["category"],"INFO")
        self.assertEqual(m["notification_format"],"movement_only_v2")
        self.assertEqual(m["watch_stage"],1)
        self.assertEqual(m["expires_at"],NOW+55)
        self.assertEqual(m["text"].splitlines(),[
            "🟡 MOVIMENTO DETECTADO • POSSÍVEL ENTRADA",
            "MOEDA: TEST/USDT",
            "MOVIMENTO: 📈 LONG (ALTA)",
            "STATUS: aguardando segundo fechamento M1 e avaliação financeira."])
        self.assertEqual(self.pending(s,"ENTRY"),[])

    def test_short_direction_was_observed_not_assumed(self):
        s=self.state(candidate("SHORT"))
        _queue_transitions(s,{},Config(),NOW)
        self.assertIn("MOVIMENTO: 📉 SHORT (BAIXA)",self.pending(s)[0]["text"])

    def test_old_stale_m1_is_not_notified(self):
        p=candidate()
        p.variants["ANTECIPADA"].triggered_at=NOW-65
        s=self.state(p)
        _queue_transitions(s,{},Config(),NOW)
        self.assertEqual(self.pending(s),[])

    def test_blocked_second_m1_never_emits_watch_or_entry(self):
        s=self.state(candidate(phase="blocked"))
        _queue_transitions(s,{},Config(),NOW)
        self.assertEqual(self.pending(s),[])

    def test_viable_entry_has_only_exact_ten_lines_and_original_event(self):
        p=candidate(phase="ready")
        s=self.state(p,candidate("SHORT"))
        _queue_transitions(s,{},Config(),NOW)
        notices=self.pending(s)
        self.assertEqual(len(notices),1)
        m=notices[0]
        self.assertEqual(m["category"],"ENTRY")
        self.assertEqual(m["notification_format"],"entry_only_v2")
        self.assertEqual(m["id"],stable_id(p.id,"CONFIRMADA","GATILHO","paper"))
        lines=m["text"].splitlines()
        self.assertEqual(len(lines),10)
        self.assertEqual(lines[0],"🟢 SINAL DE ENTRADA • SIMULAÇÃO")
        self.assertEqual(lines[4],"")
        self.assertEqual(lines[8],"")
        self.assertTrue(lines[9].startswith("SL: "))
        self.assertNotIn("Plano:",m["text"])
        self.assertNotIn("Taxa por execução:",m["text"])

    def test_unverified_asset_never_notifies_movement(self):
        s=self.state(candidate())
        _queue_transitions(s,{},Config(),NOW,watch_symbols=set())
        self.assertEqual(self.pending(s),[])

    def test_existing_recent_first_m1_can_notify_once(self):
        s=self.state(candidate())
        old=deepcopy(s["plans"])
        _queue_transitions(s,old,Config(),NOW)
        self.assertEqual(len(self.pending(s)),1)
        first=self.pending(s)[0]["id"]
        s["outbox"][first]["status"]="SENT"
        _queue_transitions(s,deepcopy(s["plans"]),Config(),NOW+1)
        self.assertEqual(self.pending(s),[])
        self.assertEqual(len(s["outbox"]),1)

    def test_prior_non_actionable_messages_expired_sent_history_preserved(self):
        s=self.state(candidate(phase="possible"))
        for key in ("preparation","blocked","summary","close","source-error","journal"):
            queue_message(s,key,"noise: "+key,NOW,NOW+300)
        s["outbox"]["close"]["status"]="SENT"
        _queue_transitions(s,{},Config(),NOW)
        sent=[]
        result=drain_outbox(s,NOW,"bot","chat",
            lambda payload:(sent.append(payload["text"]) or
                            {"ok":True,"result":{"message_id":len(sent)}}))
        self.assertEqual(sent,[])
        self.assertEqual(result["suppressed"],5)
        self.assertEqual(s["outbox"]["close"]["status"],"SENT")

    def test_existing_old_movement_stage_one_is_expired_not_sent(self):
        s=self.state(candidate())
        queue_message(s,"old","🟡 MOVIMENTO DETECTADO\nTEST",NOW,NOW+300)
        s["outbox"]["old"].update(watch_symbol="TEST_USDT",watch_stage=1)
        _queue_transitions(s,{},Config(),NOW)
        self.assertEqual(s["outbox"]["old"]["status"],"EXPIRED")
        self.assertEqual(len(self.pending(s)),1)
        self.assertIn("movement_only_v2",self.pending(s)[0]["notification_format"])

    def test_existing_old_stage_two_and_blocked_stage_zero_retired(self):
        s=self.state(candidate(phase="blocked"))
        for i,stage in enumerate((0,2)):
            queue_message(s,"watch-old-"+str(i),"Old watch",NOW,NOW+300)
            s["outbox"]["watch-old-"+str(i)].update(
                watch_symbol="TEST_USDT",watch_stage=stage)
        _queue_transitions(s,{},Config(),NOW)
        self.assertEqual(self.pending(s),[])

    def test_different_movement_watch_suppressed_if_entry_eligible(self):
        p=candidate(phase="ready")
        s=self.state(p)
        _queue_transitions(s,{},Config(),NOW)
        self.assertEqual(len(self.pending(s,"ENTRY")),1)
        self.assertEqual([m for m in self.pending(s) if m["category"]!="ENTRY"],[])

    def test_freshest_movement_once_without_modifying_plan(self):
        a,b=candidate(),candidate("SHORT")
        a.variants["ANTECIPADA"].triggered_at=NOW-50
        b.variants["ANTECIPADA"].triggered_at=NOW-10
        s=self.state(a,b)
        before=deepcopy(s["plans"])
        _queue_transitions(s,{},Config(),NOW)
        self.assertEqual(len(self.pending(s)),1)
        self.assertIn("SHORT (BAIXA)",self.pending(s)[0]["text"])
        self.assertEqual(before,s["plans"])

    def test_tied_contradictory_first_candles_do_not_choose_direction(self):
        s=self.state(candidate(),candidate("SHORT"))
        _queue_transitions(s,{},Config(),NOW)
        self.assertEqual(self.pending(s),[])

    def test_five_recent_m1_watches_respect_per_round_limit_without_repeats(self):
        s=self.state(*(candidate(symbol=f"COIN{i}_USDT") for i in range(5)))
        cfg=replace(Config(),max_alerts=2)
        totals=[]
        for _ in range(3):
            _queue_transitions(s,deepcopy(s["plans"]),cfg,NOW)
            totals.append(len(self.pending(s)))
            for m in self.pending(s):
                m["status"]="SENT"
        self.assertEqual(totals,[2,2,1])

    def test_movement_expires_when_source_fails(self):
        s=self.state(candidate())
        s["active_signal_model"]=MODEL
        _queue_transitions(s,{},Config(),NOW)
        item=self.pending(s)[0]
        class Failure:
            def server_time(self):
                raise SourceError("Synthetic source failure")
        report,_=run_scan(Failure(),Config(),s,{"TEST"},now=NOW,signal_model=MODEL)
        self.assertEqual(report["source_status"],"FALHA")
        self.assertEqual(s["outbox"][item["id"]]["status"],"EXPIRED")
        self.assertFalse(any("FALHA NA COLETA" in x["text"] for x in self.pending(s)))

    def test_closed_plan_has_no_telegram_notification(self):
        s=self.state(candidate())
        _queue_transitions(s,{},Config(),NOW)
        for m in self.pending(s):
            m["status"]="SENT"
        previous=deepcopy(s["plans"])
        for p in s["plans"].values():
            p["status"],p["reason"]="EXPIRADO","PRAZO_ENCERRADO"
        _queue_transitions(s,previous,Config(),NOW+1)
        self.assertEqual(self.pending(s),[])

    def test_outdated_first_m1_does_not_reappear_after_expiration(self):
        s=self.state(candidate())
        _queue_transitions(s,{},Config(),NOW)
        old=self.pending(s)[0]
        p=candidate(phase="blocked")
        s["plans"][p.id]=jsonable(p)
        _queue_transitions(s,{},Config(),NOW+1)
        self.assertEqual(s["outbox"][old["id"]]["status"],"EXPIRED")
        self.assertEqual(self.pending(s),[])


if __name__=="__main__":
    unittest.main()
