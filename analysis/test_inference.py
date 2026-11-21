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


def _load_tool():
    path = inference.Path(__file__).resolve().parent.parent / "tools" / "measure_llm_openrouter.py"
    spec = importlib.util.spec_from_file_location("measure_llm_openrouter", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _chat_response(content, cost=0.0001, finish="stop"):
    return {"model": "qwen/qwen3.5-9b", "provider": "DeepInfra",
            "choices": [{"finish_reason": finish, "message": {"role": "assistant", "content": json.dumps(content)}}],
            "usage": {"prompt_tokens": 300, "completion_tokens": 20, "cost": cost}}


class TestRemoteBackend(unittest.TestCase):
    """OpenAI-compatible backend: same prompt, schema and validator, reachable only through the tool's transport."""
    env = {"INVESTWATCH_LLM": "1", "INVESTWATCH_LLM_BACKEND": "openrouter", "INVESTWATCH_LLM_MODEL": "qwen/qwen3.5-9b"}
    answer = {"label": "edukacja", "lineId": "L1", "quote": "wyjaśniam krok po kroku, czym jest ETF"}

    def setUp(self):
        inference._cache.clear()
        inference._digests.clear()
        self.addCleanup(inference.use_remote, None, None)

    def register(self, response):
        seen = []

        def chat(body):
            seen.append(body)
            return response

        inference.use_remote(chat, lambda: {"digest": "openrouter:x", "quantization": "bf16"})
        return seen

    def test_default_backend_is_ollama_and_invalid_value_is_refused(self):
        with patch.dict(os.environ, {"INVESTWATCH_LLM_BACKEND": ""}):
            self.assertEqual(inference.backend(), "ollama")
        with patch.dict(os.environ, {"INVESTWATCH_LLM": "1", "INVESTWATCH_LLM_BACKEND": "gpt"}):
            result = inference.classify(CAPTURE)
        self.assertEqual((result["engine"], result["errorCode"]), ("ollama", "backend_invalid"))

    def test_product_cannot_use_openrouter_without_the_measurement_transport(self):
        with patch.dict(os.environ, self.env):
            result = inference.classify(CAPTURE)
        self.assertEqual((result["status"], result["errorCode"], result["engine"]),
                         ("unavailable", "backend_forbidden", "openrouter"))

    def test_inference_module_never_touches_the_openrouter_key_or_host(self):
        text = inference.Path(inference.__file__).read_text(encoding="utf-8")
        self.assertNotIn("OPENROUTER_API_KEY", text)
        self.assertNotIn("openrouter.ai", text)
        self.assertNotIn(".env.openrouter", text)

    def test_same_prompt_schema_temperature_and_validator(self):
        seen = self.register(_chat_response(self.answer))
        with patch.dict(os.environ, self.env):
            result = inference.classify(CAPTURE)
        self.assertEqual((result["status"], result["label"], result["engine"]), ("ready", "edukacja", "openrouter"))
        self.assertEqual((result["quantization"], result["promptTokens"], result["evalTokens"]), ("bf16", 300, 20))
        body = seen[0]
        self.assertEqual((body["temperature"], body["seed"]), (0, inference.SEED))
        self.assertEqual(body["messages"], inference.messages(inference.fragments(CAPTURE)))
        self.assertEqual(body["response_format"]["json_schema"]["schema"], inference.SCHEMA)
        self.assertTrue(body["response_format"]["json_schema"]["strict"])

    def test_ungrounded_quote_and_truncation_are_not_labels(self):
        self.register(_chat_response({**self.answer, "quote": "Załóż konto z moim kodem"}))
        with patch.dict(os.environ, self.env):
            self.assertEqual(inference.classify(CAPTURE)["errorCode"], "rejected:quote_not_in_line")
        inference._cache.clear()
        self.register(_chat_response(self.answer, finish="length"))
        with patch.dict(os.environ, self.env):
            self.assertEqual(inference.classify(CAPTURE)["errorCode"], "incomplete_response")


class TestMeasurementTool(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tool = _load_tool()
        cls.labels, cls.rows = mc.labeled_examples()

    def endpoint(self, **kw):
        from decimal import Decimal
        base = {"provider": "DeepInfra", "tag": "deepinfra/bf16", "quantization": "bf16", "prompt": Decimal("0.0000001"),
                "completion": Decimal("0.0000002"), "request": Decimal(0),
                "supported": {"max_tokens", "temperature", "seed", "response_format", "structured_outputs", "reasoning"}}
        return {**base, **kw}

    def test_endpoint_choice_needs_structured_outputs_and_price_cap(self):
        from decimal import Decimal
        no_schema = self.endpoint(provider="Alibaba", supported={"max_tokens", "temperature", "seed", "response_format"},
                                  prompt=Decimal("0.00000001"))
        dear = self.endpoint(provider="Dear", prompt=Decimal("0.000005"))
        chosen = self.tool.choose_endpoint([no_schema, dear, self.endpoint()], 3.0)
        self.assertEqual(chosen["provider"], "DeepInfra")
        with self.assertRaises(SystemExit):
            self.tool.choose_endpoint([no_schema, dear], 3.0)
        with self.assertRaises(SystemExit):
            self.tool.choose_endpoint([self.endpoint()], 3.0, provider="Other")

    def meter(self, post, model_limit=0.30, total_limit=1.50, ledger=None, **kw):
        meter = self.tool.Meter("qwen/qwen3.5-9b", self.endpoint(**kw), "secret-key", 3.0, model_limit, total_limit,
                                ledger if ledger is not None else {})
        meter.post = post
        return meter

    def test_request_body_pins_provider_price_and_privacy(self):
        seen = []
        meter = self.meter(lambda body, key: seen.append((body, key)) or _chat_response({}))
        with patch.object(self.tool, "write_ledger"):
            meter.chat({"model": "m", "messages": []})
        body, key = seen[0]
        self.assertEqual(body["provider"], {"allow_fallbacks": False, "require_parameters": True, "data_collection": "deny",
                                            "only": ["DeepInfra"], "max_price": {"prompt": 3.0, "completion": 3.0, "request": 0}})
        self.assertEqual((body["usage"], body["reasoning"], key), ({"include": True}, {"enabled": False}, "secret-key"))

    def test_cost_limits_stop_before_the_next_request(self):
        calls = []
        meter = self.meter(lambda body, key: calls.append(1) or _chat_response({}, cost=0.2), model_limit=0.30)
        with patch.object(self.tool, "write_ledger"):
            meter.chat({}), meter.chat({})
            with self.assertRaises(self.tool.Stop):
                meter.chat({})
        self.assertEqual(len(calls), 2)
        meter = self.meter(lambda body, key: _chat_response({}), total_limit=1.50, ledger={"other": 1.49, "qwen/qwen3.5-9b": 0})
        meter.cost = 0.02
        with self.assertRaises(self.tool.Stop):
            meter.chat({})

    def test_run_summary_has_metrics_agreement_cost_and_no_key(self):
        heldout = [r for r in self.rows if r["split"] == "heldout"]
        by_text = {}
        for r in heldout:
            by_text[inference.fragments(r["capture"]).get("L0")] = r

        def post(body, key):
            row = by_text[json.loads(body["messages"][1]["content"])["L0"]]
            fragments = json.loads(body["messages"][1]["content"])
            if row is heldout[0]:
                return _chat_response({"label": row["label"], "lineId": "L0", "quote": "nie ma tego w tekście"})
            return _chat_response({"label": row["label"], "lineId": "L0", "quote": fragments["L0"][:40]})

        args = type("A", (), {"split": "heldout", "limit": 5, "max_price_per_mtok": 3.0, "max_model_cost": 0.3,
                              "max_total_cost": 1.5})()
        endpoint = self.endpoint()
        with patch.object(self.tool.orr, "_post", post), patch.object(self.tool, "write_ledger"), \
                patch.object(self.tool, "read_ledger", return_value={}), patch.dict(os.environ, {}, clear=False):
            rows, items, meter, stopped, e5_correct = self.tool.run("qwen/qwen3.5-9b", endpoint, args, "secret-key")
            summary = self.tool.summarize("qwen/qwen3.5-9b", endpoint, args, rows, items, meter, stopped, e5_correct)
        self.assertIsNone(inference._remote)  # transport unregistered after the run
        self.assertEqual((summary["completed"], summary["statuses"]), (5, {"ready": 4, "rejected": 1}))
        self.assertEqual(summary["rejectionReasons"], {"rejected:quote_not_in_line": 1})
        self.assertAlmostEqual(summary["rejectedShare"], 0.2)
        self.assertAlmostEqual(summary["costUsd"], 0.0005)
        self.assertEqual(summary["metrics"]["correct"], 4)
        self.assertEqual(summary["rawLabelAccuracy"], 1.0)
        self.assertEqual(summary["agreementWithE5"]["answered"], 4)
        self.assertEqual((summary["endpointProvider"], summary["quantization"]), ("DeepInfra", "bf16"))
        self.assertNotIn("secret-key", json.dumps(summary))


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
