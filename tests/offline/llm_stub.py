"""Atrapa API Ollamy (bez modelu) do sprawdzenia okablowania serwisu inference: DNS, sieć wewnętrzna, OLLAMA_HOST.

Odpowiada na GET /api/version i /api/tags (jeden fikcyjny model z digestem); inne ścieżki: 404.
Użycie: nakładka tests/offline/compose.llm-stub.yaml, potem z workera:
  python -c "from analysis import inference; print(inference.model_digest())"
"""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os

MODEL = os.environ.get("INVESTWATCH_LLM_MODEL") or "qwen3.5:4b-q4_K_M"
TAGS = {"models": [{"name": MODEL, "model": MODEL, "size": 1, "digest": "stub-" + "0" * 59,
                    "details": {"quantization_level": "STUB", "parameter_size": "0"}}]}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = {"/api/version": {"version": "stub"}, "/api/tags": TAGS}.get(self.path)
        data = json.dumps(body).encode()
        self.send_response(200 if body else 404)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 11434), Handler).serve_forever()
