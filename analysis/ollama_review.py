"""Run the evidence-review prompt through an installed local Ollama model."""
import argparse
from contextlib import closing
from http.client import HTTPConnection, HTTPException
import json
import os
from pathlib import Path
import time
from urllib.parse import urlsplit

from analysis.openrouter_review import (
    MAX_TOKENS,
    METHOD,
    OLLAMA_REASONING_EFFORT,
    ReviewError,
    SEED,
    SIGNALS,
    TEMPERATURE,
    capture_fragments,
    compare_recommendations,
    finish_review,
    load_capture,
    prompt_sha256,
    response_meta,
    response_schema,
    review_messages,
    source_version,
)

MODEL = "qwen3.5:9b"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 11434
MAX_RESPONSE_BYTES = 256 * 1024
TIMEOUT_SECONDS = 180

__all__ = ["compare_recommendations", "request_review", "review_capture", "main"]


def configured_model():
    model = os.getenv("INVESTWATCH_REVIEW_MODEL", "").strip()
    return model or MODEL


def configured_host():
    """OLLAMA_HOST like Ollama itself: host, host:port or http://host:port. Plain HTTP only."""
    value = os.getenv("OLLAMA_HOST", "").strip()
    if not value:
        return DEFAULT_HOST, DEFAULT_PORT
    parsed = urlsplit(value if "://" in value else f"http://{value}")
    try:
        host, port = parsed.hostname, parsed.port or DEFAULT_PORT
    except ValueError as exc:
        raise ReviewError("ollama_host_invalid", "OLLAMA_HOST ma nieprawidłowy port.") from exc
    if parsed.scheme != "http" or not host or parsed.username or parsed.password or parsed.path not in ("", "/"):
        raise ReviewError("ollama_host_invalid", "OLLAMA_HOST musi mieć postać host[:port] albo http://host[:port].")
    if host == "0.0.0.0":
        host = DEFAULT_HOST  # bind address used by `ollama serve`, reachable locally as loopback
    return host, port


def request_review(messages, schema):
    """Connect directly to Ollama without proxies, redirects or API keys. Returns (content, payload)."""
    model = configured_model()
    host, port = configured_host()
    body = json.dumps({
        "model": model,
        "messages": messages,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "evidence_review", "schema": schema, "strict": True},
        },
        "stream": False,
        "reasoning_effort": OLLAMA_REASONING_EFFORT,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
        "seed": SEED,
    }, ensure_ascii=False).encode("utf-8")
    try:
        with closing(HTTPConnection(host, port, timeout=TIMEOUT_SECONDS)) as connection:
            connection.request("POST", "/v1/chat/completions", body,
                               {"Content-Type": "application/json"})
            response = connection.getresponse()
            if response.status == 404:
                raise ReviewError("ollama_model_unavailable", f"Ollama nie udostępnia modelu {model}.")
            if response.status != 200:
                raise ReviewError("ollama_http_error", f"Ollama zwróciła HTTP {response.status}.")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except TimeoutError as exc:
        raise ReviewError("ollama_timeout", "Upłynął limit czasu odpowiedzi Ollama.") from exc
    except (OSError, HTTPException) as exc:
        raise ReviewError("ollama_unavailable", f"Nie udało się połączyć z Ollama na {host}:{port}.") from exc

    if len(raw) > MAX_RESPONSE_BYTES:
        raise ReviewError("invalid_response", "Odpowiedź Ollama przekroczyła limit rozmiaru.")
    try:
        payload = json.loads(raw)
        (choice,) = payload["choices"]
        content = choice["message"]["content"]
        finish_reason = choice["finish_reason"]
    except (ValueError, KeyError, TypeError, RecursionError) as exc:
        raise ReviewError("invalid_response", "Nieprawidłowa odpowiedź Ollama.") from exc
    if (payload.get("error") or choice.get("error") or finish_reason != "stop"
            or choice["message"].get("refusal") or not isinstance(content, str)):
        raise ReviewError("incomplete_response", "Ollama nie zwróciła kompletnego zalecenia.",
                          details=response_meta(payload, model))
    return content, payload


def review_capture(capture):
    module = capture.get("module")
    if not isinstance(module, str) or module not in SIGNALS:
        raise ReviewError("invalid_capture", "Materiał musi mieć moduł M1, M2 albo M3.")
    fragments = capture_fragments(capture)
    messages = review_messages(module, fragments, capture)
    model = configured_model()
    host, port = configured_host()
    url = capture.get("url")
    if not isinstance(url, str):
        url = None
    base = {
        "backend": "ollama",
        "method": METHOD,
        "captureId": capture["id"],
        "module": module,
        "requestedModel": model,
        "provider": f"ollama@{host}:{port}",
        "sourceUrl": url,
        "source": source_version(capture),
        "sourceSha256": prompt_sha256(messages),
        "parameters": {"temperature": TEMPERATURE, "max_tokens": MAX_TOKENS, "seed": SEED,
                       "reasoning_effort": OLLAMA_REASONING_EFFORT},
    }
    started = time.monotonic()
    try:
        content, payload = request_review(messages, response_schema(module))
    except ReviewError as exc:
        exc.details = {**base, "wallSeconds": round(time.monotonic() - started, 3), **exc.details}
        raise
    meta = {**base, "wallSeconds": round(time.monotonic() - started, 3), **response_meta(payload, model)}
    meta["provider"] = base["provider"]
    recommendation = finish_review(content, module, fragments, meta)
    if recommendation["evidence"] and url:
        recommendation["evidence"]["url"] = url
    return recommendation


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Plik JSON z obserwacją lub listą obserwacji.")
    parser.add_argument("--capture-id", help="ID obserwacji w zbiorze.")
    args = parser.parse_args(argv)
    result = {"backend": "ollama", "requestedModel": configured_model()}
    exit_status = 0
    try:
        capture = load_capture(args.path, args.capture_id)
        result.update(review_capture(capture))
    except ReviewError as exc:
        result.update(exc.details)
        result.update(status="error", error={"code": exc.code, "message": exc.message, "reason": exc.reason})
        exit_status = 2
    print(json.dumps(result, ensure_ascii=False))
    return exit_status


if __name__ == "__main__":
    raise SystemExit(main())
