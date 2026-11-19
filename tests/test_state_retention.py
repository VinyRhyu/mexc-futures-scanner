"""Retention safety: historical paper messages/plans may be removed from hot state only."""
import unittest

from mexc_scanner.config import Config
from mexc_scanner.state import initial_state
from scripts.state_branch import prune_expired_state_records, RETENTION_SECONDS


class StateRetentionTests(unittest.TestCase):
    def setUp(self):
        self.now = 1_800_000_000
        self.state = initial_state(Config())
        self.state["last_success"] = self.now
        self.old = self.now - RETENTION_SECONDS - 3600
        self.recent = self.now - 3600

    @staticmethod
    def plan(status, when):
        return {"status": status, "expires_at": when, "formed_at": when - 1800}

    @staticmethod
    def msg(status, when, **extra):
        return {"status": status, "created_at": when, "expires_at": when + 1800,
                "sent_at": when + 60, **extra}

    def test_removes_expired_history_but_preserves_live_and_referenced_records(self):
        s = self.state
        s["plans"] = {
            "old": self.plan("EXPIRADO", self.old),
            "recent": self.plan("INVALIDADO", self.recent),
            "live": self.plan("ATIVO", self.old),
            "position": self.plan("EVENTO_PASSADO", self.old),
            "journal": self.plan("EXPIRADO", self.old),
            "pending": self.plan("EXPIRADO", self.old),
        }
        s["wallet"]["position"] = {"plan_id": "position"}
        s["journal"].append({"plan_id": "journal"})
        s["outbox"] = {
            "sent-old": self.msg("SENT", self.old),
            "sent-new": self.msg("SENT", self.recent),
            "expired-old": self.msg("EXPIRED", self.old),
            "waiting": self.msg("PENDING", self.old, plan_id="pending"),
        }
        removed = prune_expired_state_records(s)
        self.assertEqual(removed, {"plans": 1, "outbox": 2})
        self.assertEqual(set(s["plans"]), {"recent", "live", "position", "journal", "pending"})
        self.assertEqual(set(s["outbox"]), {"sent-new", "waiting"})
        self.assertEqual(s["wallet"]["position"], {"plan_id": "position"})
        self.assertEqual(s["journal"], [{"plan_id": "journal"}])
        self.assertEqual(prune_expired_state_records(s), {"plans": 0, "outbox": 0})

    def test_preserves_active_pending_plan_list_and_unsettled_delivery(self):
        s = self.state
        s["plans"] = {"p1": self.plan("EXPIRADO", self.old),
                      "p2": self.plan("EXPIRADO", self.old)}
        s["wallet"]["pending"] = {"plan_id": "p1"}
        s["outbox"]["inflight"] = self.msg("PENDING", self.old, plan_ids=["p2"])
        prune_expired_state_records(s)
        self.assertEqual(set(s["plans"]), {"p1", "p2"})
        self.assertIn("inflight", s["outbox"])

    def test_does_not_prune_real_or_uninitialized_state(self):
        s = self.state
        s["plans"] = {"old": self.plan("EXPIRADO", self.old)}
        s["outbox"] = {"old": self.msg("SENT", self.old)}
        s["mode"] = "real"
        self.assertEqual(prune_expired_state_records(s), {"plans": 0, "outbox": 0})
        self.assertIn("old", s["plans"])
        s["mode"] = "paper"
        s["last_success"] = 0
        self.assertEqual(prune_expired_state_records(s), {"plans": 0, "outbox": 0})
        self.assertIn("old", s["outbox"])


if __name__ == "__main__":
    unittest.main()
