"""Causal M1 TP/SL audit, avoids labeling queued/unfilled alerts as profits."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from scripts.verify_recent_confirmed_tp import read_delivered,outcome


def evt(**changes):
    d={"event_id":"sig1","symbol":"XLM_USDT","side":"LONG",
       "sent_at":1800000010,"expires_at":1800000150,
       "entry_low":"100","entry_high":"101","target":"105","stop":"98",
       "signal_at":1800000000,"quote_at":1800000009,"plan_id":"p1"}
    d.update(changes)
    return d


def candle(ts,lo,hi):
    from decimal import Decimal
    d=lambda x:Decimal(str(x))
    return {"ts":ts,"open":d(lo),"low":d(lo),"high":d(hi),"close":d(hi)}


class CausalTPTests(unittest.TestCase):
    def test_only_delivered_confirmed_signals_and_no_duplicate(self):
        with TemporaryDirectory() as d:
            file=Path(d)/"decisions-2027-01-15.jsonl"
            records=[
                {"event":"entry_queued","event_id":"a","variant":"CONFIRMADA",
                 "variant_status":"VALIDA","strategy":"ROMPIMENTO_M1_VOLUME",
                 "financial":{"status":"VIAVEL_SIMULADO"},"plan_id":"p1",
                 "symbol":"BTC_USDT","side":"LONG","target":"105","stop":"98",
                 "entry_low":"100","entry_high":"101","quote_at":1800000000,
                 "expires_at":1800000150,"signal_at":1800000000},
                {"event":"entry_queued","event_id":"b","variant":"CONFIRMADA",
                 "variant_status":"VALIDA","strategy":"ROMPIMENTO_M1_VOLUME",
                 "financial":{"status":"VIAVEL_SIMULADO"}},
                {"event":"delivery_sent","event_id":"a","status":"SENT",
                 "sent_at":1800000010},
            ]
            file.write_text("\n".join(json.dumps(x) for x in records)+"\n")
            x=read_delivered(Path(d),1800000050,lookback_hours=1)
            self.assertEqual(len(x),1)
            self.assertEqual(x[0]["event_id"],"a")

    def test_no_candle_prior_to_delivery_is_counted(self):
        e=evt()
        # 1800000000 starts *before* 1800000010 delivery; this TP is unknowable
        x=outcome(e,{1800000000:candle(1800000000,100,120)},1800000050)
        self.assertFalse(x["tp_touched_after_delivery"])
        self.assertEqual(x["conservative_4h_outcome"],"AWAITING_CLOSED_M1")

    def test_valid_entry_then_target_is_a_price_touch_not_real_fill(self):
        e=evt()
        c={1800000060:candle(1800000060,99,101),
           1800000120:candle(1800000120,102,106)}
        x=outcome(e,c,1800000180)
        self.assertTrue(x["entry_touched_before_expiry"])
        self.assertTrue(x["tp_touched_after_delivery"])
        self.assertFalse(x["sl_touched_after_delivery"])
        self.assertEqual(x["conservative_4h_outcome"],"TP_FIRST")

    def test_stop_before_tp_is_loss_first_even_if_later_tp_touched(self):
        e=evt()
        c={1800000060:candle(1800000060,99,101),
           1800000120:candle(1800000120,97,100),
           1800000180:candle(1800000180,101,106)}
        x=outcome(e,c,1800000240)
        self.assertEqual(x["conservative_4h_outcome"],"SL_FIRST")
        self.assertTrue(x["sl_touched_after_delivery"])
        # The first-hit settlement deliberately halts after stop;
        # no later price movement is claimed to rescue a stopped position.

    def test_tp_and_entry_in_same_candle_is_ambiguous(self):
        e=evt()
        x=outcome(e,{1800000060:candle(1800000060,99,106)},1800000120)
        self.assertTrue(x["tp_touched_after_delivery"])
        self.assertEqual(x["conservative_4h_outcome"],"AMBIGUOUS_ENTRY_MINUTE")

    def test_stop_and_tp_same_candle_after_entry_is_ambiguous(self):
        e=evt()
        c={1800000060:candle(1800000060,99,101),
           1800000120:candle(1800000120,97,106)}
        x=outcome(e,c,1800000180)
        self.assertEqual(x["conservative_4h_outcome"],"AMBIGUOUS_TP_AND_SL_SAME_M1")

    def test_short_has_mirrored_levels_and_target_first(self):
        e=evt(side="SHORT",entry_low="99",entry_high="100",target="95",stop="102")
        c={1800000060:candle(1800000060,99,101),
           1800000120:candle(1800000120,94,98)}
        x=outcome(e,c,1800000180)
        self.assertTrue(x["tp_touched_after_delivery"])
        self.assertEqual(x["conservative_4h_outcome"],"TP_FIRST")

    def test_entry_touched_only_after_signal_expires_not_a_trade(self):
        e=evt(expires_at=1800000120)
        c={1800000060:candle(1800000060,102,103),
           1800000120:candle(1800000120,100,101),
           1800000180:candle(1800000180,101,106)}
        x=outcome(e,c,1800000240)
        self.assertFalse(x["entry_touched_before_expiry"])
        self.assertTrue(x["tp_touched_after_delivery"])
        self.assertEqual(x["conservative_4h_outcome"],"NO_ENTRY_ZONE_TOUCH_BEFORE_EXPIRY")

    def test_missing_one_minute_means_no_conclusion(self):
        e=evt()
        c={1800000060:candle(1800000060,99,101),
           1800000180:candle(1800000180,99,106)}
        x=outcome(e,c,1800000240)
        self.assertEqual(x["conservative_4h_outcome"],"HISTORY_INCOMPLETE")
        self.assertEqual(x["missing_minutes"],1)

    def test_no_complete_candle_yet_is_awaiting(self):
        e=evt(sent_at=1800000018)
        x=outcome(e,{},1800000070)
        self.assertEqual(x["conservative_4h_outcome"],"AWAITING_CLOSED_M1")


if __name__=="__main__":
    unittest.main()
