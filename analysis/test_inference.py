"""Offline tests of the inference client against a fake Ollama HTTP server, and of preprocessing."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
import threading
import time
import unittest
from unittest.mock import patch

from analysis import inference, material_classifier as mc

CAPTURE = {"id": "youtube:x", "module": "M1", "title": "Jak zacząć inwestować w ETF?",
           "description": "W tym filmie wyjaśniam krok po kroku, czym jest ETF.\nhttps://example.org/link\n"
                          "00:00 Wstęp\nW tym filmie wyjaśniam krok po kroku, czym jest ETF."}
FINDING = {"id": "youtube:x", "module": "M1", "score": 24, "summary": "Wzmianka", "evidence": [{"text": "a"}],
           "reviewDecision": {"route": "no_signal"}, "reviewScore": {"value": 12}}


class Fake(BaseHTTPRequestHandler):
    answer = None
    delay = 0.0
    chats = []

    def log_message(self, *args):
        pass

    def _send(self, body, status=200):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/api/tags":
            self._send({"models": [{"name": "qwen3.5:4b-q4_K_M", "digest": "sha256:abc", "size": 3300000000,
                                    "details": {"quantization_level": "Q4_K_M", "parameter_size": "4B"}}]})
        else:
            self._send({}, 404)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).chats.append(body)
        time.sleep(type(self).delay)
        self._send({"message": {"role": "assistant", "content": json.dumps(type(self).answer, ensure_ascii=False)},
                    "done": True, "done_reason": "stop", "eval_count": 20, "prompt_eval_count": 300})


class TestInferenceClient(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Fake)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.env = {"OLLAMA_HOST": f"127.0.0.1:{cls.server.server_port}", "INVESTWATCH_LLM": "1",
                   "INVESTWATCH_LLM_MODEL": "qwen3.5:4b-q4_K_M"}

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        inference._cache.clear()
        inference._digests.clear()
        Fake.chats, Fake.delay = [], 0.0
        Fake.answer = {"label": "edukacja", "lineId": "L1", "quote": "wyjaśniam krok po kroku, czym jest ETF"}

    def test_ready_label_has_validated_quote_digest_and_cache(self):
        with patch.dict(os.environ, self.env):
            first = inference.classify(CAPTURE)
            second = inference.classify(CAPTURE)
        self.assertEqual((first["status"], first["label"], first["digest"]), ("ready", "edukacja", "sha256:abc"))
        self.assertEqual(first["evidence"]["text"], "wyjaśniam krok po kroku, czym jest ETF")
        self.assertEqual(first["promptVersion"], inference.PROMPT_VERSION)
        self.assertFalse(first["affectsDecision"])
        self.assertTrue(second["cached"])
        self.assertEqual(len(Fake.chats), 1)
        request = Fake.chats[0]
        self.assertEqual((request["options"]["temperature"], request["think"], request["stream"]), (0, False, False))
        self.assertEqual(request["format"], inference.SCHEMA)
        self.assertNotIn("https://", request["messages"][1]["content"])  # preprocessing removed URLs

    def test_ungrounded_quote_is_rejected_not_labelled(self):
        Fake.answer = {"label": "promocja", "lineId": "L1", "quote": "Załóż konto z moim kodem"}
        with patch.dict(os.environ, self.env):
            result = inference.classify(CAPTURE)
        self.assertEqual((result["status"], result["label"], result["errorCode"]),
                         ("rejected", None, "rejected:quote_not_in_line"))

    def test_abstention_and_line_outside_input(self):
        Fake.answer = {"label": "nieustalone", "lineId": "", "quote": ""}
        with patch.dict(os.environ, self.env):
            self.assertEqual(inference.classify(CAPTURE)["status"], "abstained")
        inference._cache.clear()
        Fake.answer = {"label": "opinia", "lineId": "L9", "quote": "czym jest ETF"}
        with patch.dict(os.environ, self.env):
            self.assertEqual(inference.classify(CAPTURE)["errorCode"], "rejected:line_missing")

    def test_disabled_unavailable_busy_and_timeout(self):
        with patch.dict(os.environ, {**self.env, "INVESTWATCH_LLM": ""}):
            self.assertEqual(inference.classify(CAPTURE)["status"], "disabled")
        with patch.dict(os.environ, {**self.env, "OLLAMA_HOST": "127.0.0.1:9"}):
            self.assertEqual(inference.classify(CAPTURE)["status"], "unavailable")
        with patch.dict(os.environ, self.env), patch.object(inference, "QUEUE_SECONDS", 0.05):
            inference._slot.acquire()
            try:
                self.assertEqual(inference.classify(CAPTURE)["status"], "busy")
            finally:
                inference._slot.release()
        Fake.delay = 0.5
        with patch.dict(os.environ, self.env), patch.object(inference, "TIMEOUT_SECONDS", 0.1):
            result = inference.classify(CAPTURE)
        self.assertEqual((result["status"], result["errorCode"]), ("unavailable", "timeout"))

    def test_missing_model_is_unavailable(self):
        with patch.dict(os.environ, {**self.env, "INVESTWATCH_LLM_MODEL": "gemma4:e2b"}):
            result = inference.classify(CAPTURE)
        self.assertEqual((result["status"], result["errorCode"]), ("unavailable", "model_missing"))

    def test_annotate_never_changes_decision_fields(self):
        with patch.dict(os.environ, self.env), patch.object(mc, "WEIGHTS", mc.ROOT / "no-such-weights.json"):
            annotated = inference.annotate(FINDING, CAPTURE)
        self.assertEqual({k: v for k, v in annotated.items() if k != "model"}, FINDING)
        self.assertNotIn("model", FINDING)
        model = annotated["model"]
        self.assertEqual(model["status"], "unavailable")  # no weights: the E5 feature degrades, scan goes on
        self.assertEqual(model["secondOpinion"]["status"], "ready")
        self.assertIsNone(model["agreement"])
        self.assertFalse(model["affectsDecision"])


class TestPreprocessing(unittest.TestCase):
    def test_clean_text_removes_markup_urls_timestamps_and_repeats(self):
        raw = ("<p>Inwestuj&nbsp;mądrze</p>\n12:05 Rozdział drugi\nhttps://x.pl/a?b=1\n-----\n"
               "Kontakt: biuro@firma.pl\nInwestuj mądrze\nＥＴＦ")
        self.assertEqual(mc.clean_text(raw), "Inwestuj mądrze\nRozdział drugi\nKontakt\nETF")

    def test_dedupe_keeps_first_identical_material(self):
        a = {"id": "1", "title": "Tytuł", "description": "Opis https://a.pl"}
        b = {"id": "2", "title": "tytuł", "description": "Opis https://b.pl"}
        c = {"id": "3", "title": "Inny", "description": "Opis"}
        self.assertEqual([x["id"] for x in mc.dedupe([a, b, c])], ["1", "3"])

    def test_split_is_by_creator_and_labels_match_replay_text(self):
        labels, rows = mc.labeled_examples()
        tuning = {r["creatorId"] for r in rows if r["split"] == "tuning"}
        heldout = {r["creatorId"] for r in rows if r["split"] == "heldout"}
        self.assertFalse(tuning & heldout)
        self.assertEqual(len(rows), 160)
        self.assertTrue(all(r["split"] == mc.creator_split(r["creatorId"]) for r in rows))

    def test_classifier_without_weights_reports_unavailable(self):
        with patch.object(mc, "WEIGHTS", mc.ROOT / "no-such-weights.json"):
            self.assertEqual(mc.classify(CAPTURE)["status"], "unavailable")

    def test_weights_file_is_versioned(self):
        weights = mc.load_weights()
        self.assertEqual(weights["classes"], list(mc.CLASSES))
        self.assertTrue(weights["version"].startswith("mt-e5lr-1-"))
        self.assertEqual((len(weights["weights"]), len(weights["weights"][0])), (384, 4))
        self.assertEqual(weights["trainedOn"]["split"], "tuning")

    @unittest.skipUnless(importlib.util.find_spec("numpy"), "numpy niedostępny")
    def test_softmax_and_confusion(self):
        import numpy as np
        probabilities = mc.softmax(np, np.array([[0.0, 0.0, 0.0, 10.0]]))
        self.assertGreater(probabilities[0, 3], 0.99)
        report = mc.confusion(["opinia", "edukacja"], ["opinia", "nieustalone"])
        self.assertEqual((report["correct"], report["answered"], report["abstained"]), (1, 1, 1))


if __name__ == "__main__":
    unittest.main()
