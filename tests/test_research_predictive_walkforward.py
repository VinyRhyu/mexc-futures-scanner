"""Regression tests for the experimental causal TP-before-SL forecaster."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import csv
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.research_predictive_walkforward import (
    FEATURE_NAMES, FUTURE_ONLY, MIN_TRAIN, WINDOWS, VAL_START, TEST_START,
    fit_logistic, load_frozen_events, metrics, one_slot_paper,
    pretrade_features, probability, qualifies, run_experiment,
)


def example_raw(**updates):
    r={
        "period":"2026-10-26T00:00:00+00:00",
        "signal_utc":"2026-10-26T08:40:00+00:00",
        "exit_utc":"2026-10-26T08:51:00+00:00",
        "side":"LONG", "symbol":"BTC_USDT","plan_id":"a",
        "projected_net_RR":"1.80","entry_utc":"2026-10-26T08:41:00+00:00",
        "outcome":"ALVO","net_R":"1.5","net_USDT_fixed_paper":"0.1",
        "turnover24_USDT":"12000000",
        "M1_volume_vs_prev20":"1.4",
        "M1_body_fraction_of_range":"0.7",
        "M1_close_near_side_fraction":"0.8",
        "M1_range_over_M15_ATR":"0.3",
        "signed_1h_M1_extension_ATR":"0.2",
        "signed_4h_M1_extension_ATR":"0.4",
        "signed_2h_M15_extension_ATR":"0.6",
        "H1_alignment":"NO_CONFIRMED_H1_TREND",
    }
    r.update(updates)
    return r


def row_at(t, **kwargs):
    raw=example_raw(**kwargs)
    d=datetime.fromisoformat(t)
    rr=float(raw["projected_net_RR"])
    return {
        "symbol":raw["symbol"],"side":raw["side"],"plan_id":raw["plan_id"],
        "signal_utc":d.isoformat(),"signal_at":d,
        "exit_utc":(d+timedelta(minutes=10)).isoformat(),
        "exit_at":d+timedelta(minutes=10),
        "rr":rr,"features":pretrade_features(raw),
        "y":int(raw["outcome"]=="ALVO"),
        "outcome":raw["outcome"],
        "net_r":float(raw["net_R"]),
        "net_usdt_fixed_paper":float(raw["net_USDT_fixed_paper"]),
    }


class PredictiveResearchTests(unittest.TestCase):
    def test_fixed_feature_contract_never_includes_future_outcome(self):
        self.assertFalse(set(FEATURE_NAMES)&FUTURE_ONLY)
        raw=example_raw()
        before=pretrade_features(raw)
        mutated=deepcopy(raw)
        mutated.update(outcome="STOP",net_R="-1",
                       net_USDT_fixed_paper="-0.1",
                       exit_utc="2026-10-26T09:00:00+00:00")
        self.assertEqual(before,pretrade_features(mutated))

    def test_pretrade_features_change_with_momentum_not_with_future(self):
        a=example_raw()
        b=example_raw(M1_volume_vs_prev20="3.0",H1_alignment="WITH_H1")
        x,y=pretrade_features(a),pretrade_features(b)
        self.assertNotEqual(x,y)
        self.assertEqual(len(x),len(FEATURE_NAMES))

    def test_invalid_nonfinite_feature_cannot_silently_enter_model(self):
        for bad in ("NaN","Infinity","-Infinity","oops",""):
            with self.assertRaises(ValueError):
                pretrade_features(example_raw(M1_volume_vs_prev20=bad))
        with self.assertRaises(ValueError):
            pretrade_features(example_raw(H1_alignment="UNKNOWN_FROM_FUTURE"))

    def test_fit_uses_only_training_labels(self):
        start=datetime.fromisoformat("2026-10-26T00:00:00+00:00")
        train=[]
        for i in range(MIN_TRAIN+12):
            d=(start+timedelta(minutes=i*12)).isoformat()
            train.append(row_at(d,
                outcome="ALVO" if i%3==0 else "STOP",
                net_R="1.2" if i%3==0 else "-1",
                net_USDT_fixed_paper="0.1" if i%3==0 else "-0.1",
                M1_volume_vs_prev20=str(0.5+i/100),
                plan_id=str(i),symbol="T"+str(i)+"_USDT"))
        one=row_at("2026-11-15T21:00:00+00:00",symbol="TEST_USDT")
        other=deepcopy(one)
        other.update(y=0,outcome="STOP",net_r=-1,net_usdt_fixed_paper=-0.1)
        model=fit_logistic(train)
        self.assertEqual(probability(model,one),probability(model,other))
        self.assertGreater(probability(model,one),0)
        self.assertLess(probability(model,one),1)
        self.assertEqual(model["training_count"],len(train))

    def test_gate_uses_projected_rr_probability_not_future_label(self):
        row={"p":0.8,"rr":1.8,"outcome":"STOP","net_r":-1}
        self.assertTrue(qualifies(row,"PREDICTED_POSITIVE_EXPECTANCY"))
        row["outcome"]="ALVO"
        row["net_r"]=1.8
        self.assertTrue(qualifies(row,"PREDICTED_POSITIVE_EXPECTANCY"))
        row["p"]=0.1
        self.assertFalse(qualifies(row,"PREDICTED_POSITIVE_EXPECTANCY"))

    def test_one_position_slot_prevents_overlapping_events(self):
        a=row_at("2026-11-15T22:00:00+00:00",plan_id="a",symbol="A_USDT")
        b=row_at("2026-11-15T22:01:00+00:00",plan_id="b",symbol="B_USDT")
        c=row_at("2026-11-15T22:11:00+00:00",plan_id="c",symbol="C_USDT")
        for r in (a,b,c):
            r["p"]=0.95
        result=one_slot_paper([a,b,c],"CONFIRMED_ALL")
        self.assertEqual(result["selected"],2)
        self.assertEqual([x["symbol"] for x in result["trade_events"]],["A_USDT","C_USDT"])

    def test_chronological_ordering_is_independent_of_source_file_names(self):
        with TemporaryDirectory() as td:
            root=Path(td)
            for i,(period,_) in enumerate(WINDOWS.items()):
                folder=root/f"shuffled-{4-i}"
                folder.mkdir()
                day=datetime.fromisoformat(period)+timedelta(hours=8)
                with (folder/"one_usdt_viable_unique_events.csv").open(
                        "w",newline="",encoding="utf-8") as out:
                    writer=csv.DictWriter(out,fieldnames=list(example_raw()))
                    writer.writeheader()
                    for j in range(20 if i<3 else 8):
                        ts=day+timedelta(minutes=12*j)
                        r=example_raw(
                            period=period,signal_utc=ts.isoformat(),
                            exit_utc=(ts+timedelta(minutes=10)).isoformat(),
                            side="LONG" if j%2 else "SHORT",
                            symbol=f"COIN{i}_{j}_USDT",plan_id=f"{i}-{j}",
                            outcome="ALVO" if j%3==0 else "STOP",
                            net_R="1.8" if j%3==0 else "-1",
                            net_USDT_fixed_paper="0.12" if j%3==0 else "-0.08")
                        writer.writerow(r)
            rows,counts=load_frozen_events(root)
            self.assertEqual(len(rows),76)
            self.assertEqual(len(counts),5)
            report,ledger=run_experiment(rows,counts)
            self.assertEqual(report["counts"]["training_purged"],60)
            self.assertEqual(report["counts"]["validation"],8)
            self.assertEqual(report["counts"]["test"],8)
            self.assertEqual(len(ledger["TEST"]),4)
            self.assertEqual(set(report["reports"]),{"VALIDATION","TEST"})

    def test_duplicate_market_event_rejected_even_if_from_different_plan(self):
        with TemporaryDirectory() as td:
            # Data contract insists on all five windows, but duplicate is rejected
            # before any research score is trained.
            root=Path(td)
            for period in WINDOWS:
                folder=root/period[:10]
                folder.mkdir(exist_ok=True)
                r=example_raw(period=period,signal_utc=(
                    datetime.fromisoformat(period)+timedelta(hours=1)).isoformat(),
                    exit_utc=(datetime.fromisoformat(period)+
                              timedelta(hours=1,minutes=10)).isoformat())
                with (folder/"one_usdt_viable_unique_events.csv").open(
                        "w",newline="",encoding="utf-8") as out:
                    writer=csv.DictWriter(out,fieldnames=list(r))
                    writer.writeheader()
                    writer.writerow(r)
                    if period == "2026-10-26T00:00:00+00:00":
                        writer.writerow({**r,"plan_id":"different_plan"})
            with self.assertRaisesRegex(ValueError,"duplicate market event"):
                load_frozen_events(root)

    def test_brier_benchmark_uses_prior_from_train_only(self):
        samples=[{"p":0.8,"y":1},{"p":0.6,"y":0}]
        score=metrics(samples,0.25)
        self.assertAlmostEqual(score["target_rate"],0.5)
        self.assertAlmostEqual(score["prior_brier"],0.3125)
        self.assertAlmostEqual(score["brier"],0.2)


if __name__=="__main__":
    unittest.main()
