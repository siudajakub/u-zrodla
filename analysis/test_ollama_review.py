from contextlib import redirect_stdout
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from analysis import ollama_review as review


class OllamaReviewTests(unittest.TestCase):
    CAPTURE = {
        "id": "m3:123",
        "module": "M3",
        "url": "https://example.com/oferta",
        "description": "Nasi eksperci przygotują rekomendacje według Twojego indywidualnego profilu ryzyka.",
    }

    def run_cli(self, path, *extra_args):
        output = StringIO()
        with redirect_stdout(output):
            status = review.main([str(path), *extra_args])
        return status, json.loads(output.getvalue())

    def mock_response(self, connection_class, content, *, status=200, finish_reason="stop"):
        connection = connection_class.return_value
        response = connection.getresponse.return_value
        response.status = status
        response.read.return_value = json.dumps({
            "model": "qwen3.5:9b",
            "choices": [{"message": {"content": content}, "finish_reason": finish_reason}],
        }).encode()
        return connection

    @patch.object(review, "HTTPConnection")
    def test_collection_selection_uses_shared_prompt_and_validates_evidence(self, connection_class):
        fragments = review.capture_fragments(self.CAPTURE)
        fragment_id = next(iter(fragments))
        quote = "według Twojego indywidualnego profilu ryzyka"
        connection = self.mock_response(connection_class, json.dumps({
            "signal": "personalized_recommendation_offer", "fragmentId": fragment_id, "quote": quote,
        }, ensure_ascii=False))
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "capture.json"
            path.write_text(json.dumps({"captures": [self.CAPTURE]}), encoding="utf-8")
            status, result = self.run_cli(path, "--capture-id", self.CAPTURE["id"])

        self.assertEqual(status, 0, result)
        self.assertEqual(result["backend"], "ollama")
        self.assertEqual(result["requestedModel"], "qwen3.5:9b")
        self.assertEqual(result["reportedModel"], "qwen3.5:9b")
        self.assertEqual(result["captureId"], self.CAPTURE["id"])
        self.assertEqual(result["method"], review.METHOD)
        self.assertEqual(result["status"], "review")
        self.assertEqual(result["evidence"]["text"], quote)
        expected_messages = review.review_messages("M3", fragments)
        source = json.dumps(expected_messages, ensure_ascii=False, sort_keys=True).encode()
        self.assertEqual(result["sourceSha256"], sha256(source).hexdigest())
        connection_class.assert_called_once_with("127.0.0.1", 11434, timeout=review.TIMEOUT_SECONDS)
        method, path, body, headers = connection.request.call_args.args
        self.assertEqual((method, path), ("POST", "/v1/chat/completions"))
        self.assertEqual(headers, {"Content-Type": "application/json"})
        request = json.loads(body)
        self.assertEqual(request["model"], "qwen3.5:9b")
        self.assertEqual(request["messages"], expected_messages)
        self.assertEqual(request["response_format"]["json_schema"]["schema"], review.response_schema("M3"))
        connection.close.assert_called_once_with()

    @patch.object(review, "HTTPConnection")
    def test_invalid_input_fails_without_calling_ollama(self, connection_class):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "broken.json"
            path.write_text("broken", encoding="utf-8")
            status, result = self.run_cli(path)
        self.assertEqual(status, 2)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "invalid_capture")
        connection_class.assert_not_called()

    @patch.object(review, "HTTPConnection")
    def test_truncated_completion_and_missing_model_fail_closed(self, connection_class):
        for status, finish_reason, code in (
            (200, "length", "incomplete_response"),
            (404, "stop", "ollama_model_unavailable"),
            (307, "stop", "ollama_http_error"),
        ):
            with self.subTest(status=status, finish_reason=finish_reason):
                connection_class.reset_mock()
                connection = self.mock_response(connection_class, "{}", status=status,
                                                finish_reason=finish_reason)
                with self.assertRaises(review.ReviewError) as raised:
                    review.request_review([], {})
                self.assertEqual(raised.exception.code, code)
                connection.request.assert_called_once()
                connection.close.assert_called_once_with()

    @patch.object(review, "HTTPConnection")
    def test_invalid_quote_returns_error(self, connection_class):
        fragment_id = next(iter(review.capture_fragments(self.CAPTURE)))
        self.mock_response(connection_class, json.dumps({
            "signal": "personalized_recommendation_offer",
            "fragmentId": fragment_id, "quote": "Zmyślony cytat",
        }))
        with self.assertRaises(review.ReviewError) as raised:
            review.review_capture(self.CAPTURE)
        self.assertEqual(raised.exception.code, "ungrounded_response")

    @patch.object(review, "HTTPConnection")
    def test_declared_partnership_remains_a_control_after_quote_validation(self, connection_class):
        quote = "Materiał powstał we współpracy z Aurorą."
        capture = {"id": "m1:partnership", "module": "M1", "description": quote}
        self.mock_response(connection_class, json.dumps({
            "signal": "declared_partnership", "fragmentId": "description", "quote": quote,
            "charStart": 0, "charEnd": len(quote), "disclosureQuote": quote,
        }))

        result = review.review_capture(capture)

        self.assertEqual(result["status"], "control")
        self.assertEqual(result["evidence"]["text"], quote)
        self.assertEqual(result["evidence"]["match"], "verbatim")
        self.assertEqual(result["disclosure"]["fragmentId"], "description")

    @patch.object(review, "HTTPConnection")
    def test_shared_parameters_env_model_and_raw_response_on_rejection(self, connection_class):
        connection = self.mock_response(connection_class, json.dumps({
            "signal": "personalized_recommendation_offer", "fragmentId": "description", "quote": "Zmyślony cytat",
        }, ensure_ascii=False))
        with patch.dict("os.environ", {"INVESTWATCH_REVIEW_MODEL": "qwen3.5:9b-q4_K_M", "OLLAMA_HOST": "10.0.0.5:11500"}):
            with self.assertRaises(review.ReviewError) as raised:
                review.review_capture(self.CAPTURE)
        connection_class.assert_called_once_with("10.0.0.5", 11500, timeout=review.TIMEOUT_SECONDS)
        request = json.loads(connection.request.call_args.args[2])
        self.assertEqual(request["model"], "qwen3.5:9b-q4_K_M")
        self.assertEqual((request["temperature"], request["max_tokens"], request["seed"], request["reasoning_effort"]),
                         (0, review.MAX_TOKENS, review.SEED, "none"))
        details = raised.exception.details
        self.assertIn("Zmyślony cytat", details["rawResponse"])
        self.assertEqual(details["modelMismatch"], {"requested": "qwen3.5:9b-q4_K_M", "reported": "qwen3.5:9b"})
        self.assertEqual(details["reason"], "quote_not_in_fragment")


if __name__ == "__main__":
    unittest.main()
