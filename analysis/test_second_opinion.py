"""Offline tests of the second opinion: validation, window coverage, aggregation and the route guarantee.

The Ollama service is replaced by a fake ``inference._http``; nothing here opens a connection.
"""
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from analysis import inference, second_opinion as so

MODEL = "fake:test"
CAPTURE = {
    "title": "Mój portfel dywidendowy",
    "description": "Konto maklerskie (XTB) z kodem WYPRAWA: https://link-pso.xtb.com/pso/abc\nOpis odcinka.",
    "segments": [{"start": i * 3.0, "text": f"zdanie numer {i} o rynku akcji."} for i in range(400)]
    + [{"start": 1300.0, "text": "a konto otworzycie u partnera tego odcinka XTB."}],
}


def answer(verdict, line_id="", quote="", confidence="wysoka", explanation="Jedno zdanie."):
    return json.dumps({"verdict": verdict, "lineId": line_id, "quote": quote, "confidence": confidence,
                       "explanation": explanation}, ensure_ascii=False)


class FakeOllama:
    """Replaces inference._http; `reply(body)` returns the model content for one /api/chat request."""

    def __init__(self, reply, model=MODEL):
        self.reply, self.chats = reply, []
        self.model = model

    def __call__(self, method, path, body=None, timeout=None):
        if path == "/api/tags":
            return {"models": [{"name": self.model, "digest": "sha256:fake", "size": 1,
                                "details": {"quantization_level": "Q4_K_M", "parameter_size": "27B"}}]}
        self.chats.append(body)
        return {"message": {"role": "assistant", "content": self.reply(body)}, "done": True, "done_reason": "stop",
                "prompt_eval_count": 100, "eval_count": 20}


def lines_of(body):
    return json.loads(body["messages"][1]["content"])["linie"]


class Base(unittest.TestCase):
    def setUp(self):
        so._cache.clear()
        inference._digests.clear()
        inference.use_remote(None, None)
        self.env = patch.dict(os.environ, {"INVESTWATCH_SECOND_OPINION_MODEL": MODEL, "INVESTWATCH_LLM_BACKEND": "ollama"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        inference.use_remote(None, None)


class Validation(Base):
    LINES = {"T0": "[0:00] dzisiaj partnerem tego odcinka jest", "T1": "[0:05] XTB i to wszystko", "T2": "[0:09] koniec"}

    def test_accepts_verbatim_quote_and_typographic_variants(self):
        result = so.validate("m1_disclosure", answer("ujawnione", "T0", "partnerem tego odcinka"), self.LINES)
        self.assertEqual(result["quote"], "partnerem tego odcinka")
        spanning = so.validate("m1_disclosure", answer("ujawnione", "T0", "odcinka jest [0:05] XTB"), self.LINES)
        self.assertEqual(spanning["lineId"], "T0")
        quoted = so.validate("m2_k09", answer("zrozumiale", "W0", "„Inwestowanie” jest ryzykowne"),
                             {"W0": '"Inwestowanie" jest ryzykowne.'})
        self.assertEqual(quoted["verdict"], "zrozumiale")

    def test_rejections(self):
        cases = [
            (answer("ujawnione", "T2", "partnerem tego odcinka"), "rejected:quote_not_in_line"),
            (answer("ujawnione", "T9", "partnerem"), "rejected:line_missing"),
            (answer("ujawnione", "T0", "Partnerem tego odcinka jest"), None),  # case differs -> next assertion
            (answer("ujawnione", "", ""), "rejected:quote_missing"),
            (answer("inne", "T0", "partnerem"), "rejected:verdict"),
            (answer("ujawnione", "T0", "partnerem", confidence="pewna"), "rejected:confidence"),
            ("nie json", "rejected:not_json"),
            (json.dumps({"verdict": "ujawnione"}), "rejected:schema"),
        ]
        for content, code in cases:
            if code is None:
                with self.assertRaises(inference.InferenceError) as raised:
                    so.validate("m1_disclosure", content, self.LINES)
                self.assertEqual(raised.exception.code, "rejected:quote_not_in_line")
                continue
            with self.assertRaises(inference.InferenceError, msg=content) as raised:
                so.validate("m1_disclosure", content, self.LINES)
            self.assertEqual(raised.exception.code, code)

    def test_absence_and_abstain_need_no_quote(self):
        self.assertEqual(so.validate("m1_disclosure", answer("brak_ujawnienia"), self.LINES)["quote"], None)
        self.assertEqual(so.validate("m1_disclosure", answer("nieustalone"), self.LINES)["verdict"], "nieustalone")
        with self.assertRaises(inference.InferenceError):  # an optional quote is still validated
            so.validate("m3_offer", answer("informacja_edukacja", "P0L1", "nie ma tego"), {"P0L1": "Artykuł o rynku"})


class Inputs(unittest.TestCase):
    def test_windows_cover_every_segment_and_keep_time(self):
        windows = so.m1_windows(CAPTURE)
        self.assertEqual(windows[0]["kind"], "opis")
        self.assertGreater(len(windows), 2)
        text = " ".join(line for w in windows[1:] for line in w["lines"].values())
        for segment in CAPTURE["segments"]:
            self.assertIn(segment["text"], text)
        for window in windows:
            self.assertLessEqual(sum(len(v) for v in window["lines"].values()), so.WINDOW_CHARS + so.LINE_CHARS * 2)
        last = windows[-1]
        key = next(k for k, v in last["lines"].items() if "partnera tego odcinka" in v)
        self.assertGreaterEqual(last["times"][key], 1200)

    def test_m2_neighbourhood_keeps_sticky_and_drops_nav_hidden_far(self):
        view = {"blocks": [
            {"t": "Zarabiaj na dywidendach", "bbox": [0, 1000, 10, 10], "role": "body"},
            {"t": "Inwestowanie wiąże się z ryzykiem utraty kapitału.", "bbox": [0, 1100, 10, 10], "role": "body"},
            {"t": "Menu akcje", "bbox": [0, 1000, 10, 10], "role": "nav"},
            {"t": "Ukryte ostrzeżenie", "bbox": [0, 1000, 10, 10], "role": "body", "hid": "display:none"},
            {"t": "Stopka daleko", "bbox": [0, 5000, 10, 10], "role": "footer"},
            {"t": "76% rachunków CFD traci pieniądze", "bbox": [0, 0, 10, 10], "role": "header", "fix": "fixed"},
        ]}
        lines = so.m2_claim_lines(view, 0)
        joined = " ".join(lines.values())
        self.assertIn("ryzykiem utraty", joined)
        self.assertIn("przyklejony", joined)
        for absent in ("Menu akcje", "Ukryte", "Stopka daleko"):
            self.assertNotIn(absent, joined)

    def test_m3_lines_keep_rule_evidence_in_long_pages(self):
        text = "\n".join(f"linia {i} o niczym szczególnym, wypełnienie tekstu strony" for i in range(2000))
        text += "\nOferujemy indywidualne doradztwo inwestycyjne w zakresie akcji."
        lines = so.m3_lines([{"url": "https://a.pl/", "text": text}], {"https://a.pl/": {2001}}, limit=6000)
        self.assertIn("P0L2001", lines)
        self.assertLessEqual(sum(len(v) for v in lines.values()), 6000)


class Reviews(Base):
    def test_disabled_by_default(self):
        with patch.dict(os.environ, {"INVESTWATCH_SECOND_OPINION": ""}):
            self.assertFalse(so.enabled())
        self.assertEqual(so.disabled("m1_disclosure")["status"], "disabled")

    def test_m1_absence_only_after_every_window(self):
        fake = FakeOllama(lambda body: answer("brak_ujawnienia"))
        with patch.object(inference, "_http", fake):
            result = so.review_m1({**CAPTURE, "segments": CAPTURE["segments"][:400]}, "XTB", ["link-pso"], "ujawnione")
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["verdict"], "brak_ujawnienia")
        self.assertEqual(len(fake.chats), result["windows"])
        self.assertTrue(result["needsReview"])
        self.assertEqual(result["reviewLabel"], so.REVIEW_LABEL)
        self.assertFalse(result["affectsRoute"])

    def test_m1_disclosure_in_transcript_gives_time(self):
        def reply(body):
            for key, value in lines_of(body).items():
                if "partnera tego odcinka" in value:
                    return answer("ujawnione", key, "u partnera tego odcinka XTB")
            return answer("brak_ujawnienia")
        with patch.object(inference, "_http", FakeOllama(reply)):
            result = so.review_m1(CAPTURE, "XTB", ["link-pso"], "ujawnione")
        self.assertEqual(result["verdict"], "ujawnione")
        self.assertEqual(result["locator"]["field"], "transcript")
        self.assertGreaterEqual(result["locator"]["seconds"], 1200)
        self.assertIs(result["agreement"], True)
        self.assertFalse(result["needsReview"])

    def test_m1_rejected_window_blocks_absence(self):
        calls = {"n": 0}

        def reply(body):
            calls["n"] += 1
            return answer("ujawnione", "T0", "zmyślony cytat") if calls["n"] == 2 else answer("brak_ujawnienia")
        with patch.object(inference, "_http", FakeOllama(reply)):
            result = so.review_m1({**CAPTURE, "segments": CAPTURE["segments"][:400]}, "XTB", [], "brak_ujawnienia")
        self.assertEqual(result["status"], "rejected")
        self.assertIsNone(result["verdict"])
        self.assertFalse(result["needsReview"])

    def test_m2_and_m3_envelopes(self):
        view = {"blocks": [{"t": "Zarabiaj na dywidendach", "bbox": [0, 100, 1, 1], "role": "body"},
                           {"t": "Akcje to ryzyko utraty kapitału.", "bbox": [0, 150, 1, 1], "role": "body"}]}

        def reply(body):
            task = body["format"]["properties"]["verdict"]["enum"][0]
            if task == "ostrzezenie_obok":
                return answer("ostrzezenie_obok", "B1", "ryzyko utraty kapitału")
            if task == "zrozumiale":
                return answer("niezrozumiale", "W0", "Instrumenty pochodne")
            return answer("oferta_rekomendacji", "P0L2", "doradztwo inwestycyjne")
        with patch.object(inference, "_http", FakeOllama(reply)):
            k03 = so.review_m2_k03(view, "Zarabiaj na dywidendach", 0, ["akcje"], "brak_ostrzezenia", viewport="desktop")
            k09 = so.review_m2_k09("Instrumenty pochodne są złożone.", "zrozumiale")
            m3 = so.review_m3([{"url": "https://a.pl/", "text": "Start\nOferujemy doradztwo inwestycyjne"}], [], "informacja_edukacja")
        self.assertEqual((k03["verdict"], k03["needsReview"], k03["locator"]["block"]), ("ostrzezenie_obok", True, "B1"))
        self.assertEqual((k09["verdict"], k09["agreement"]), ("niezrozumiale", False))
        self.assertEqual(m3["locator"], {"url": "https://a.pl/", "line": 2})
        self.assertTrue(m3["needsReview"])

    def test_attach_keeps_route_score_and_queue(self):
        finding = {"id": "x", "score": 90, "reviewDecision": {"route": "refer"}, "reviewScore": {"value": 90}}
        second = {"task": "m1_disclosure", "status": "ready", "verdict": "ujawnione", "needsReview": True, "affectsRoute": False}
        out = so.attach(finding, second)
        self.assertEqual(out["reviewDecision"], finding["reviewDecision"])
        self.assertEqual(out["score"], 90)
        self.assertEqual(out["secondOpinion"], second)
        self.assertNotIn("secondOpinion", finding)

    def test_openrouter_backend_refused_without_measurement_transport(self):
        with patch.dict(os.environ, {"INVESTWATCH_LLM_BACKEND": "openrouter"}):
            result = so.review_m2_k09("Inwestowanie jest ryzykowne.", "zrozumiale")
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["errorCode"], "backend_forbidden")

    def test_unavailable_service_is_not_a_verdict(self):
        def down(*args, **kwargs):
            raise inference.InferenceError("unavailable", "brak usługi")
        with patch.object(inference, "_http", down):
            result = so.review_m2_k09("Inwestowanie jest ryzykowne.", "zrozumiale")
        self.assertEqual((result["status"], result["verdict"], result["needsReview"]), ("unavailable", None, False))

    def test_product_file_never_reads_a_key_or_opens_a_remote_connection(self):
        source = Path(so.__file__).read_text(encoding="utf-8")
        for forbidden in ("OPENROUTER_API_KEY", ".env.openrouter", "openrouter.ai", "urllib", "Authorization"):
            self.assertNotIn(forbidden, source)


class LocalDefault(Base):
    def test_default_is_local_without_api_credentials(self):
        with (patch.dict(os.environ, {}, clear=True),
              patch.object(inference, "_http", FakeOllama(
                  lambda body: answer("zrozumiale", "W0", "Instrumenty pochodne"), inference.DEFAULT_MODEL))):
            self.assertTrue(so.enabled())
            self.assertEqual(so.configured_model(), inference.DEFAULT_MODEL)
            self.assertFalse(so.recorded_enabled())
            result = so.review_m2_k09("Instrumenty pochodne są złożone.", "zrozumiale")
        self.assertEqual((result["runtime"], result["engine"], result["verdict"]),
                         ("local", "ollama", "zrozumiale"))

    def test_legacy_api_demo_flag_still_uses_local_model(self):
        with (patch.dict(os.environ, {"INVESTWATCH_LLM_DEMO_API": "1", "INVESTWATCH_LLM_DEMO_MODEL": "remote"}),
              patch.object(inference, "_http", FakeOllama(
                  lambda body: answer("zrozumiale", "W0", "Instrumenty pochodne")))):
            result = so.review_m2_k09("Instrumenty pochodne są złożone.", "zrozumiale")
        self.assertEqual((result["runtime"], result["modelId"]), ("local", MODEL))


if __name__ == "__main__":
    unittest.main()
