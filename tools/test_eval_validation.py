"""Testy narzędzia ewaluacji walidacyjnej (tools/eval_validation.py)."""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from eval_validation import NO_BASIS, agreement, main, run, wilson


def label(mid, lab, campaign=None, module="M1", kind="expert", **extra):
    return {"materialId": mid, "module": module, "campaignId": campaign or f"c-{mid}",
            "label": lab, "referenceKind": kind, **extra}


def pred(mid, score, state=None):
    row = {"materialId": mid, "score": score}
    if state:
        row["state"] = state
    return row


class WilsonTest(unittest.TestCase):
    def test_known_values(self):
        self.assertEqual(wilson(20, 20), [0.8389, 1.0])
        self.assertEqual(wilson(0, 10), [0.0, 0.2775])
        low, high = wilson(9, 10)
        self.assertAlmostEqual(low, 0.5958, places=4)
        self.assertAlmostEqual(high, 0.9821, places=4)

    def test_empty_denominator(self):
        self.assertIsNone(wilson(0, 0))


class ConfusionTest(unittest.TestCase):
    def setUp(self):
        self.labels = [
            label("a", "skieruj", "k1"), label("b", "skieruj", "k1"),
            label("c", "skieruj", "k2", module="M2"),
            label("d", "rejestr", "k3"), label("e", "bez_sygnalu", "k4", module="M3"),
            label("f", "nieustalone", "k5"),
        ]
        self.preds = [pred("a", 90), pred("b", 50), pred("c", None, "insufficient"),
                      pred("d", 70), pred("e", 10), pred("f", 99)]

    def test_counts_cost_and_withheld(self):
        report = run(self.labels, self.preds, [60, 80])
        at60, at80 = report["overall"]
        self.assertEqual((at60["tp"], at60["fp"], at60["tn"], at60["fn"]), (1, 1, 1, 2))
        self.assertEqual(at60["cost"], 2 * 2 + 1)
        self.assertEqual(at60["undetermined"], 1)
        self.assertEqual(at60["evaluated"], 5)
        self.assertEqual(at60["withheld"], 1)
        self.assertEqual(at60["withheldRate"], 0.2)
        self.assertEqual(at60["precision"], 0.5)
        self.assertEqual(at60["registryNegatives"], 1)
        self.assertEqual(at60["registryInQueue"], 1)
        self.assertEqual((at80["tp"], at80["fp"], at80["fn"]), (1, 0, 2))
        self.assertEqual(at80["cost"], 4)

    def test_campaign_grouping(self):
        at60 = run(self.labels, self.preds, [60, 80])["overall"][0]
        self.assertEqual(at60["referredCampaigns"], 2)  # k1 i k3
        self.assertEqual(at60["truePositiveCampaigns"], 1)
        self.assertEqual(at60["independentCampaigns"], 4)  # k5 nieustalone poza macierzą
        self.assertEqual(at60["campaignLevel"], {"tp": 1, "fp": 1, "tn": 1, "fn": 1})

    def test_per_module(self):
        report = run(self.labels, self.preds, [60, 80])
        self.assertEqual(set(report["byModule"]), {"M1", "M2", "M3"})
        m2 = report["byModule"]["M2"][0]
        self.assertEqual(m2["precision"], NO_BASIS)
        self.assertEqual(m2["precisionCI95"], NO_BASIS)
        self.assertEqual(m2["recall"], 0.0)

    def test_missing_prediction_counts_as_not_referred(self):
        report = run([label("x", "skieruj")], [], [30, 60])
        r = report["overall"][0]
        self.assertEqual((r["fn"], r["missingPredictions"], r["withheld"]), (1, 1, 1))


class EmptyAndGateTest(unittest.TestCase):
    def test_empty_labels(self):
        report = run([], [], [30, 60])
        r = report["overall"][0]
        self.assertEqual(r["precision"], NO_BASIS)
        self.assertEqual(r["recall"], NO_BASIS)
        self.assertEqual(r["withheldRate"], NO_BASIS)
        self.assertEqual(report["referenceKind"], NO_BASIS)

    def test_agent_labels_never_pass_gate(self):
        labels = [label(f"m{i}", "skieruj", kind="agent", split="test") for i in range(25)]
        preds = [pred(f"m{i}", 95) for i in range(25)]
        report = run(labels, preds, [60, 80], 60, "test")
        self.assertTrue(report["gate"]["status"].startswith("nie dotyczy"))
        self.assertIn("nie są niezależnym wzorcem", report["referenceNote"])

    def test_gate_requires_twenty_distinct_campaigns(self):
        labels = [label(f"m{i}", "skieruj", campaign="jedna", split="test") for i in range(30)]
        preds = [pred(f"m{i}", 95) for i in range(30)]
        report = run(labels, preds, [60, 80], 60, "test")
        self.assertEqual(report["gate"]["status"], "brak podstaw do oceny")

    def test_gate_pass_and_fail(self):
        labels = [label(f"p{i}", "skieruj", split="test") for i in range(20)]
        labels += [label("n0", "rejestr", split="test"), label("n1", "bez_sygnalu", split="test"),
                   label("n2", "rejestr", split="test")]
        preds = [pred(r["materialId"], 90) for r in labels]
        fail = run(labels, preds, [60, 80], 60, "test")["gate"]
        self.assertEqual(fail["status"], "niezaliczona")  # 20/23 < 0.90
        preds[-2:] = [pred("n1", 10), pred("n2", 10)]
        ok = run(labels, preds, [60, 80], 60, "test")["gate"]
        self.assertEqual(ok["status"], "zaliczona")  # 20/21
        self.assertEqual(ok["referredCampaigns"], 21)

    def test_gate_only_on_test_split(self):
        labels = [label(f"m{i}", "skieruj", split="tuning") for i in range(25)]
        report = run(labels, [pred(f"m{i}", 95) for i in range(25)], [60, 80], 60, "tuning")
        self.assertIn("zamkniętym teście", report["gate"]["status"])


class InputRulesTest(unittest.TestCase):
    def test_mixed_reference_requires_choice(self):
        labels = [label("a", "skieruj"), label("b", "rejestr", kind="agent")]
        with self.assertRaises(ValueError):
            run(labels, [], [30, 60])
        report = run(labels, [], [30, 60], reference="agent")
        self.assertEqual(report["excludedOtherReference"], 1)
        self.assertEqual(report["overall"][0]["evaluated"], 1)

    def test_synthetic_excluded(self):
        report = run([label("s", "skieruj", synthetic=True), label("r", "rejestr")],
                     [pred("s", 99), pred("r", 1)], [30, 60])
        self.assertEqual(report["excludedSynthetic"], 1)
        self.assertEqual(report["overall"][0]["evaluated"], 1)

    def test_invalid_inputs(self):
        for bad in ([label("a", "tak")], [label("a", "skieruj", module="M9")],
                    [label("a", "skieruj"), label("a", "rejestr")],
                    [{"materialId": "a", "module": "M1", "label": "skieruj", "referenceKind": "expert"}]):
            with self.assertRaises(ValueError):
                run(bad, [], [30, 60])
        with self.assertRaises(ValueError):
            run([label("a", "skieruj")], [pred("a", "90")], [30, 60])
        with self.assertRaises(ValueError):
            run([label("a", "skieruj")], [], [60])

    def test_weighted_real_prevalence(self):
        labels = [label("a1", "skieruj", stratum="alarm"), label("a2", "rejestr", stratum="alarm"),
                  label("r1", "bez_sygnalu", stratum="losowa"), label("r2", "skieruj", stratum="losowa")]
        preds = [pred("a1", 90), pred("a2", 90), pred("r1", 5), pred("r2", 5)]
        est = run(labels, preds, [30, 60], populations={"alarm": 2, "losowa": 100})["realPrevalenceEstimate"]
        e = est["60.0"] if "60.0" in est else est["60"]
        self.assertEqual(e["weighted"], {"tp": 1.0, "fp": 1.0, "tn": 50.0, "fn": 50.0})
        self.assertEqual(e["recall"], round(1 / 51, 4))
        missing = run(labels, preds, [30, 60], populations={"alarm": 2})["realPrevalenceEstimate"]
        self.assertEqual(next(iter(missing.values()))["status"], NO_BASIS)


class AgreementTest(unittest.TestCase):
    def test_kappa(self):
        ratings = []
        for mid, a, b in (("1", "skieruj", "skieruj"), ("2", "rejestr", "rejestr"),
                          ("3", "skieruj", "rejestr"), ("4", "bez_sygnalu", "bez_sygnalu")):
            ratings += [{"materialId": mid, "raterId": "r1", "label": a},
                        {"materialId": mid, "raterId": "r2", "label": b}]
        result = agreement(ratings)
        self.assertEqual(result["pairs"], 4)
        self.assertEqual(result["observed"], 0.75)
        self.assertEqual(result["disagreements"], ["3"])
        self.assertAlmostEqual(result["kappa"], 0.6364, places=4)
        self.assertEqual(agreement([])["kappa"], NO_BASIS)


class RunMetadataAndCompareTest(unittest.TestCase):
    LABELS = [label("a", "skieruj"), label("b", "rejestr"), label("c", "bez_sygnalu"),
              label("d", "nieustalone")]

    def test_run_metadata_and_missing_fields(self):
        preds = [{"type": "run", "variant": "rules", "rulesVersion": "investwatch-rules-pl-1.2"},
                 pred("a", 90), pred("b", 10)]
        report = run(self.LABELS, preds, [30, 60])
        self.assertEqual(report["run"]["variant"], "rules")
        self.assertIn("weightsDigest", report["runMetadataMissing"])
        self.assertEqual(report["overall"][0]["tp"], 1)
        with self.assertRaises(ValueError):
            run(self.LABELS, [{"type": "run"}, {"type": "run"}], [30, 60])

    def test_decision_field_ignores_threshold(self):
        preds = [{"materialId": "a", "score": None, "decision": "refer"},
                 {"materialId": "b", "score": None, "decision": "withheld"},
                 {"materialId": "c", "score": 99, "decision": "no_refer"}]
        for r in run(self.LABELS, preds, [30, 90])["overall"]:
            self.assertEqual((r["tp"], r["fp"], r["tn"], r["withheld"]), (1, 0, 2, 1))
        with self.assertRaises(ValueError):
            run(self.LABELS, [{"materialId": "a", "score": 1, "decision": "tak"}], [30, 60])

    def test_route_gates_score_and_counts_withheld(self):
        # a: refer z wynikiem progowanym; b: bramka mowy (complete) mimo 94 pkt; c: no_signal mimo 94 pkt
        preds = [{"materialId": "a", "score": 70, "route": "refer"},
                 {"materialId": "b", "score": 94, "route": "complete"},
                 {"materialId": "c", "score": 94, "route": "no_signal"}]
        at30, at80 = run(self.LABELS, preds, [30, 80])["overall"]
        self.assertEqual((at30["tp"], at30["fp"], at30["withheld"]), (1, 0, 1))
        self.assertEqual((at80["tp"], at80["fn"], at80["withheld"]), (0, 1, 1))
        with self.assertRaises(ValueError):
            run(self.LABELS, [{"materialId": "a", "score": 1, "route": "skieruj"}], [30, 60])

    def test_model_output_cannot_carry_labels(self):
        with self.assertRaises(ValueError):
            run(self.LABELS, [{"materialId": "a", "score": 90, "label": "skieruj"}], [30, 60])

    def test_compare_two_runs(self):
        a = [{"type": "run", "variant": "rules+qwen", "quantization": "Q4_K_M"},
             pred("a", 90), pred("b", 70), pred("c", 10)]
        b = [{"type": "run", "variant": "rules+qwen", "quantization": "Q8_0"},
             pred("a", 85), pred("b", 40), {"materialId": "c", "score": None, "state": "insufficient"}]
        report = run(self.LABELS, a, [60, 80], compare=b)
        c = report["comparison"]
        self.assertEqual(c["runB"]["quantization"], "Q8_0")
        self.assertEqual(c["byThreshold"]["60"]["disagreements"], 2)  # b: 70→40, c: wstrzymane
        self.assertEqual({r["materialId"] for r in c["byThreshold"]["60"]["materials"]}, {"b", "c"})
        self.assertEqual(c["byThreshold"]["80"]["disagreements"], 1)  # tylko c
        self.assertEqual(c["maxScoreDifference"], 30)
        self.assertEqual(c["overallB"][0]["fp"], 0)
        self.assertEqual(report["overall"][0]["fp"], 1)


class CliTest(unittest.TestCase):
    def write(self, directory, name, rows):
        path = Path(directory) / name
        path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        return str(path)

    def test_cli_text_and_json(self):
        with tempfile.TemporaryDirectory() as d:
            labels = self.write(d, "l.jsonl", [label("a", "skieruj", discoveryChannel="youtube-search")])
            preds = self.write(d, "p.jsonl", [pred("a", 75)])
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(main(["--labels", labels, "--predictions", preds]), 0)
            self.assertIn("TP=1", out.getvalue())
            self.assertIn("youtube-search", out.getvalue())
            out = io.StringIO()
            with redirect_stdout(out):
                main(["--labels", labels, "--predictions", preds, "--json", "--thresholds", "50,90"])
            data = json.loads(out.getvalue())
            self.assertEqual([r["tp"] for r in data["overall"]], [1, 0])

    def test_cli_reports_bad_json(self):
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d) / "l.jsonl"
            bad.write_text("{nie json\n", encoding="utf-8")
            preds = self.write(d, "p.jsonl", [])
            err = io.StringIO()
            with redirect_stderr(err):
                self.assertEqual(main(["--labels", str(bad), "--predictions", preds]), 2)
            self.assertIn("l.jsonl:1", err.getvalue())


if __name__ == "__main__":
    unittest.main()
