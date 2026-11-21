import contextlib
import io
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from analysis import openrouter_review as review


DESCRIPTION = "Oferujemy portfel dopasowany do sytuacji i celów inwestycyjnych klienta."
CAPTURE = {
    "id": "www:example.org/oferta",
    "module": "M3",
    "title": "Oferta domu maklerskiego",
    "description": DESCRIPTION,
    "url": "https://example.org/oferta",
    "segments": [{"start": 24, "end": 36, "text": DESCRIPTION}],
    "registry": {"note": "registry-only"},
    "mediaUrl": "https://example.org/source.mp4",
    "internalNotes": "internal-only",
}
RESULT = {
    "signal": "personalized_recommendation_offer",
    "fragmentId": "transcript:0",
    "quote": "portfel dopasowany do sytuacji i celów inwestycyjnych klienta",
}


FREE_PRICES = [{"provider": "Free", "tag": "free", "quantization": "bf16", "prompt": review._price("0"),
                "completion": review._price("0"), "request": review._price("0"),
                "supported": set(review.REQUIRED_PARAMETERS)}]
PAID_PRICES = [{**FREE_PRICES[0], "prompt": review._price("0.0000001"), "completion": review._price("0.00000015")}]


def completion(model_result, finish_reason="stop"):
    return {
        "model": review.DEFAULT_MODEL,
        "choices": [{"message": {"content": json.dumps(model_result)}, "finish_reason": finish_reason}],
    }


class OpenRouterReviewTests(unittest.TestCase):
    def setUp(self):
        pricing = patch.object(review, "fetch_endpoint_prices", return_value=FREE_PRICES)
        self.prices = pricing.start()
        self.addCleanup(pricing.stop)

    def test_capture_selection_requires_single_match(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "captures.json"
            other_capture = {**CAPTURE, "id": "two"}
            path.write_text(json.dumps({"captures": [CAPTURE, other_capture]}), encoding="utf-8")
            self.assertEqual(review.load_capture(path, "two"), other_capture)
            with self.assertRaises(review.ReviewError):
                review.load_capture(path, None)
            with self.assertRaises(review.ReviewError):
                review.load_capture(path, "missing")
            path.write_text(json.dumps({"capture": CAPTURE, "source": {"url": "discovery"}}), encoding="utf-8")
            self.assertEqual(review.load_capture(path, None), CAPTURE)
            path.write_text(json.dumps([CAPTURE, CAPTURE]), encoding="utf-8")
            with self.assertRaises(review.ReviewError):
                review.load_capture(path, CAPTURE["id"])

    def test_free_request_exposes_only_selected_content_and_preserves_provenance(self):
        with (patch.dict(os.environ, {"OPENROUTER_API_KEY": "unit-test-key"}),
              patch.object(review, "_post", return_value=completion(RESULT)) as post):
            outcome = review.assess(CAPTURE, review.DEFAULT_MODEL)
        post.assert_called_once()
        body, key = post.call_args.args
        self.assertEqual(key, "unit-test-key")
        self.assertEqual(body["model"], "qwen/qwen3.5-9b")
        self.assertEqual(body["provider"], {
            "allow_fallbacks": False,
            "require_parameters": True,
            "data_collection": "deny",
            "max_price": {"prompt": "0", "completion": "0", "request": "0"},
        })
        self.assertEqual((body["temperature"], body["max_tokens"], body["seed"]),
                         (0, review.MAX_TOKENS, review.SEED))
        self.assertEqual(body["reasoning"], {"enabled": False})
        response_format = body["response_format"]["json_schema"]
        self.assertTrue(response_format["strict"])
        self.assertIn(RESULT["signal"], response_format["schema"]["properties"]["signal"]["enum"])
        self.assertEqual(json.loads(body["messages"][1]["content"]), {
            "title": CAPTURE["title"], "description": DESCRIPTION, "transcript:0": DESCRIPTION,
        })
        for value in ("unit-test-key", "registry-only", "internal-only", CAPTURE["url"], CAPTURE["mediaUrl"], CAPTURE["id"]):
            self.assertNotIn(value, json.dumps(body))
        self.assertEqual(outcome["billing"], "free-only")
        self.assertEqual(outcome["status"], "review")
        self.assertEqual(outcome["evidence"]["url"], CAPTURE["url"])
        self.assertEqual(outcome["evidence"]["start"], 24)
        self.assertEqual(outcome["evidence"]["end"], 36)
        start, end = (outcome["evidence"][key] for key in ("charStart", "charEnd"))
        self.assertEqual(DESCRIPTION[start:end], RESULT["quote"])
        self.assertEqual(len(outcome["sourceSha256"]), 64)

    def test_paid_model_override_with_opt_in_keeps_no_fallback(self):
        self.prices.return_value = PAID_PRICES
        with (patch.dict(os.environ, {"OPENROUTER_API_KEY": "unit-test-key"}),
              patch.object(review, "_post", return_value=completion(RESULT)) as post):
            outcome = review.assess(CAPTURE, "example/model", allow_paid=True, max_price_per_mtok=0.5)
        body, _ = post.call_args.args
        self.assertEqual(outcome["requestedModel"], "example/model")
        self.assertEqual(outcome["billing"], "paid≤0.5USD/Mtok")
        self.assertEqual(body["provider"]["max_price"], {"prompt": 0.5, "completion": 0.5, "request": 0})
        self.assertFalse(body["provider"]["allow_fallbacks"])
        self.assertEqual(outcome["modelMismatch"], {"requested": "example/model", "reported": review.DEFAULT_MODEL})

    def test_paid_model_without_opt_in_is_refused_before_request(self):
        self.prices.return_value = PAID_PRICES
        with (patch.dict(os.environ, {"OPENROUTER_API_KEY": "unit-test-key"}),
              patch.object(review, "_post") as post):
            with self.assertRaises(review.ReviewError) as raised:
                review.assess(CAPTURE, review.DEFAULT_MODEL)
        self.assertEqual(raised.exception.code, "paid_model_requires_opt_in")
        post.assert_not_called()

    def test_public_confirmation_and_selected_capture_validation_precede_request(self):
        with (TemporaryDirectory() as directory,
              patch.object(review, "_post") as post,
              contextlib.redirect_stderr(io.StringIO())):
            path = Path(directory) / "capture.json"
            path.write_text(json.dumps(CAPTURE), encoding="utf-8")
            with self.assertRaises(SystemExit) as raised:
                review.main([str(path)])
            self.assertEqual(raised.exception.code, 2)
            for changes in (
                {"synthetic": True}, {"visibility": "private"}, {"url": "/media/local.mp4"},
                {"url": "http://127.0.0.1/offers"}, {"url": "https://shop.internal/offers"},
                {"url": "https://secret@example.org/offers"},
            ):
                with self.subTest(changes=changes), self.assertRaises(review.ReviewError) as invalid:
                    review.assess({**CAPTURE, **changes}, review.DEFAULT_MODEL)
                self.assertEqual(invalid.exception.code, "non_public_capture")
            post.assert_not_called()

    def test_no_key_oversized_or_empty_capture_stops_before_request(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(review, "_post") as post:
            for capture, code in (
                (CAPTURE, "missing_api_key"),
                ({**CAPTURE, "description": "x" * review.MAX_SOURCE_CHARS}, "capture_too_large"),
                ({**CAPTURE, "title": "", "description": "\n", "segments": []}, "empty_capture"),
            ):
                with self.subTest(code=code), self.assertRaises(review.ReviewError) as raised:
                    review.assess(capture, review.DEFAULT_MODEL)
                self.assertEqual(raised.exception.code, code)
            post.assert_not_called()

    def test_negative_m2_control_and_abstention(self):
        cap = {**CAPTURE, "module": "M2", "description": "Inwestuj w ETF z prowizją 0%.", "segments": []}
        fragments = review.capture_fragments(cap)
        control = {"signal": "fee_only", "fragmentId": "description", "quote": cap["description"]}
        answer = review.validate_recommendation(json.dumps(control), "M2", fragments)
        self.assertEqual(answer["status"], "control")
        abstained = {"signal": "ambiguous_context", "fragmentId": "", "quote": ""}
        answer = review.validate_recommendation(json.dumps(abstained), "M2", fragments)
        self.assertEqual(answer, {"status": "abstained", "signal": "ambiguous_context", "evidence": None})

    def test_m1_partnership_and_affiliation_are_controls(self):
        examples = {
            "declared_partnership": "Partnerem tej publikacji jest firma oferująca fundusze ETF.",
            "affiliate_promotion": "Materiał reklamowy: otwórz konto do zakupu ETF z kodem partnerskim ZACZNIJ.",
        }
        for signal, quote in examples.items():
            with self.subTest(signal=signal):
                fragments = review.capture_fragments({"description": quote})
                candidate = {"signal": signal, "fragmentId": "description", "quote": quote,
                             "disclosureQuote": quote if signal == "declared_partnership" else None}
                result = review.validate_recommendation(json.dumps(candidate), "M1", fragments)
                self.assertEqual(result["status"], "control")
                candidate["signal"] = review.GUARANTEED_RETURN
                with self.assertRaises(review.ReviewError) as raised:
                    review.validate_recommendation(json.dumps(candidate), "M1", fragments)
                self.assertEqual(raised.exception.code, "ungrounded_response")

    def test_guarantee_needs_evidence_beyond_a_potential_return(self):
        possible = "Inwestując w akcje, możesz osiągnąć zysk."
        negation = "Inwestując w ETF, nie gwarantujemy zysku."
        unqualified = "Kup nasze ETF, gwarantujemy bezwarunkowy zysk."
        only_guarantee = "Zapewniamy zysk bez ryzyka."
        guaranteed = {"signal": review.GUARANTEED_RETURN, "fragmentId": "description"}
        for module in ("M1", "M2"):
            for quote in (possible, negation, unqualified, only_guarantee):
                with self.subTest(module=module, quote=quote):
                    extra = {"disclosureQuote": None} if module == "M1" else {}
                    candidate = json.dumps({**guaranteed, "quote": quote, **extra})
                    fragments = review.capture_fragments({"description": quote})
                    if quote == unqualified:
                        result = review.validate_recommendation(candidate, module, fragments)
                        self.assertEqual(result["status"], "review")
                    else:
                        with self.assertRaises(review.ReviewError) as raised:
                            review.validate_recommendation(candidate, module, fragments)
                        self.assertEqual(raised.exception.code, "ungrounded_response")
        candidate = {**guaranteed, "quote": possible, "signal": "potential_return_claim"}
        fragments = review.capture_fragments({"description": possible})
        result = review.validate_recommendation(json.dumps(candidate), "M2", fragments)
        self.assertEqual(result["status"], "control")

    def test_rejects_fabricated_ambiguous_and_cross_module_evidence(self):
        fragments = review.capture_fragments({**CAPTURE, "title": "Fragment. Fragment."})
        for alternate, code in (
            ({"quote": "Fałszywy cytat"}, "ungrounded_response"),
            ({"fragmentId": "missing"}, "ungrounded_response"),
            ({"fragmentId": "title", "quote": "Brak takiego"}, "ungrounded_response"),
            ({"signal": "fee_only"}, "invalid_response"),
            ({"signal": "insufficient_evidence"}, "invalid_response"),
            ({"legalStatus": "illegal"}, "invalid_response"),
        ):
            with self.subTest(alternate=alternate), self.assertRaises(review.ReviewError) as raised:
                review.validate_recommendation(json.dumps({**RESULT, **alternate}), "M3", fragments)
            self.assertEqual(raised.exception.code, code)
        repeated = review.validate_recommendation(
            json.dumps({**RESULT, "fragmentId": "title", "quote": "Fragment."}), "M3", fragments)
        self.assertEqual((repeated["evidence"]["charStart"], repeated["evidence"]["match"]), (0, "relocated"))
        self.assertEqual(repeated["evidence"]["occurrences"], 2)
        positioned = review.validate_recommendation(
            json.dumps({**RESULT, "fragmentId": "title", "quote": "Fragment.", "charStart": 10, "charEnd": 19}),
            "M3", fragments)
        self.assertEqual((positioned["evidence"]["charStart"], positioned["evidence"]["match"]), (10, "verbatim"))
        duplicate = '{"signal": "fee_only", ' + json.dumps(RESULT)[1:]
        with self.assertRaises(review.ReviewError) as invalid:
            review.validate_recommendation(duplicate, "M3", fragments)
        self.assertEqual(invalid.exception.code, "invalid_response")

    def test_partial_provider_completion_is_never_accepted(self):
        with (patch.dict(os.environ, {"OPENROUTER_API_KEY": "unit-test-key"}),
              patch.object(review, "_post", return_value=completion(RESULT, finish_reason="length"))):
            with self.assertRaises(review.ReviewError) as raised:
                review.assess(CAPTURE, review.DEFAULT_MODEL)
        self.assertEqual(raised.exception.code, "incomplete_response")
        self.assertEqual(raised.exception.details["finishReason"], "length")
        self.assertIn("personalized_recommendation_offer", raised.exception.details["rawResponse"])

    def test_m1_undisclosed_partnership_against_d_rules(self):
        link = "https://link-pso.xtb.com/pso/GFTfa"
        description = f"Sprawdź XTB\n{link}\nKod „COMPARIC” przy rejestracji = darmowy kurs."
        answer = {"signal": review.UNDISCLOSED, "fragmentId": "description", "quote": link,
                  "charStart": None, "charEnd": None, "disclosureQuote": None}
        fragments = review.capture_fragments({"description": description})
        result = review.validate_recommendation(json.dumps(answer), "M1", fragments)
        self.assertEqual(result["status"], "review")
        self.assertEqual(result["rulesCheck"]["rulesVersion"], "investwatch-m1-qual-1.0")
        disclosed = review.capture_fragments({"description": description + "\n#reklama"})
        result = review.validate_recommendation(json.dumps(answer), "M1", disclosed)
        self.assertEqual(result["status"], "hold")
        self.assertEqual(result["rulesCheck"]["disclosures"][0]["text"], "#reklama")
        with self.assertRaises(review.ReviewError) as raised:  # M1 requires disclosureQuote
            review.validate_recommendation(json.dumps({k: v for k, v in answer.items() if k != "disclosureQuote"}),
                                           "M1", fragments)
        self.assertEqual(raised.exception.code, "invalid_response")

    def test_m1_schema_and_prompt_v2(self):
        self.assertEqual(review.METHOD, "investwatch-text-review-v2")
        schema = review.response_schema("M1")
        self.assertIn(review.UNDISCLOSED, schema["properties"]["signal"]["enum"])
        self.assertEqual(schema["properties"]["disclosureQuote"]["type"], ["string", "null"])
        self.assertNotIn("disclosureQuote", review.response_schema("M3")["properties"])
        system = review.review_messages("M1", review.capture_fragments({"description": "Opis testowy."}))[0]["content"]
        self.assertIn("Brak w wejściu: tytuł; transkrypcja mowy; kadry", system)

    def test_post_uses_fixed_endpoint_and_redirect_is_refused(self):
        mocked_response = MagicMock()
        mocked_response.__enter__.return_value.read.return_value = json.dumps(completion(RESULT)).encode()
        with patch.object(review, "build_opener") as build:
            build.return_value.open.return_value = mocked_response
            output = review._post({"model": review.DEFAULT_MODEL}, "unit-test-key")
        redirect = build.call_args.args[0]
        request = build.return_value.open.call_args.args[0]
        self.assertEqual(request.full_url, review.ENDPOINT)
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.headers["Authorization"], "Bearer unit-test-key")
        self.assertIsNone(redirect.redirect_request(request, None, 302, "", {}, "https://example.org"))
        self.assertEqual(output["model"], review.DEFAULT_MODEL)

    def test_network_failures_are_safe_and_do_not_retry(self):
        for error, code in (
            (TimeoutError("provider contained unit-test-key"), "provider_unavailable"),
            (URLError("provider contained unit-test-key"), "provider_unavailable"),
            (HTTPError(review.ENDPOINT, 401, "provider contained unit-test-key", {}, None), "provider_http"),
        ):
            with self.subTest(code=code), patch.object(review, "build_opener") as build:
                build.return_value.open.side_effect = error
                with self.assertRaises(review.ReviewError) as raised:
                    review._post({}, "unit-test-key")
                self.assertEqual(raised.exception.code, code)
                self.assertNotIn("unit-test-key", str(raised.exception))
                build.return_value.open.assert_called_once()


if __name__ == "__main__":
    unittest.main()
