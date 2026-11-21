#!/usr/bin/env python3
"""Zmierz model otwartych wag na zbiorze odłożonym „typ materiału” przez OpenRouter.

Wyłącznie pomiar wyboru modelu. Produkt działa lokalnie (Ollama); worker nigdy nie czyta klucza
OpenRouter. Narzędzie rejestruje transport w analysis.inference (use_remote), więc prompt, schemat JSON,
temperatura 0, walidator cytatów i format wyniku są takie same jak dla Ollamy.

Twarde limity: lokalna kontrola cennika przed pierwszym żądaniem, --max-price-per-mtok (domyślnie 3),
koszt jednego modelu (0,30 USD) i łączny (1,50 USD, rejestr .runtime/openrouter-ledger.json) wg
usage.cost, jedno żądanie naraz. Klucz: OPENROUTER_API_KEY z środowiska albo z pliku .env.openrouter
(Git go ignoruje); jego wartość nie trafia do wyjścia ani plików.

  .runtime/venv/bin/python -B tools/measure_llm_openrouter.py --model qwen/qwen3.5-9b --public-source
"""
import argparse
from decimal import Decimal
import json
import os
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis import inference, openrouter_review as orr  # noqa: E402
from analysis.material_classifier import CLASSES, confusion, labeled_examples  # noqa: E402

LEDGER = ROOT / ".runtime" / "openrouter-ledger.json"
E5_RESULT = ROOT / "fixtures" / "labeled" / "ai-material-type-result-e5.json"
OUT_DIR = ROOT / "fixtures" / "labeled"
REQUIRED = ("max_tokens", "temperature", "seed", "response_format", "structured_outputs")
MAX_MODEL_COST, MAX_TOTAL_COST, MAX_PRICE = 0.30, 1.50, 3.0
MAX_CONSECUTIVE_ERRORS = 3


class Stop(Exception):
    """The run must end now (budget, key, repeated provider errors)."""


def load_key():
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    path = ROOT / ".env.openrouter"
    if not key and path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            name, _, value = line.partition("=")
            if name.strip() in ("OPENROUTER_API_KEY", "export OPENROUTER_API_KEY"):
                key = value.strip().strip("'\"")
    if not key:
        raise SystemExit("Brak OPENROUTER_API_KEY (środowisko albo .env.openrouter).")
    return key


def redact(text, key):
    return str(text).replace(key, "[klucz]") if key else str(text)


def choose_endpoint(prices, max_price, provider=None):
    """Cheapest endpoint that supports structured outputs and the fixed generation parameters, within the cap."""
    cap = Decimal(str(max_price)) / 1_000_000
    fit = [p for p in prices if all(name in p["supported"] for name in REQUIRED) and p["request"] == 0
           and p["prompt"] <= cap and p["completion"] <= cap
           and (provider is None or (p["provider"] or "").lower() == provider.lower())]
    if not fit:
        raise SystemExit("Żaden endpoint nie spełnia wymagań (structured outputs, parametry, limit ceny); nic nie wysłano.")
    return min(fit, key=lambda p: (p["prompt"] + p["completion"], p["provider"] or ""))


def read_ledger():
    try:
        return json.loads(LEDGER.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def write_ledger(ledger):
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(ledger, indent=1), encoding="utf-8")


class Meter:
    """Runs the requests one at a time and counts usage.cost; raises Stop before a limit is exceeded."""

    def __init__(self, model, endpoint, key, max_price, model_limit, total_limit, ledger, sleep=time.sleep):
        self.model, self.endpoint, self.key = model, endpoint, key
        self.max_price, self.model_limit, self.total_limit = max_price, model_limit, total_limit
        self.ledger, self.spent_before = ledger, sum(v for k, v in ledger.items() if k != model)
        self.cost = 0.0
        self.last = {}
        self.errors_in_row = 0
        self.sleep = sleep
        self.post = orr._post

    @property
    def total(self):
        return self.spent_before + self.cost

    def body(self, body):
        provider = {"allow_fallbacks": False, "require_parameters": True, "data_collection": "deny",
                    "only": [self.endpoint["provider"]],
                    "max_price": {"prompt": self.max_price, "completion": self.max_price, "request": 0}}
        extra = {"reasoning": orr.OPENROUTER_REASONING} if "reasoning" in self.endpoint["supported"] else {}
        return {**body, **extra, "usage": {"include": True}, "provider": provider}

    def chat(self, body):
        if self.cost >= self.model_limit:
            raise Stop(f"limit kosztu modelu {self.model_limit} USD osiągnięty ({self.cost:.4f})")
        if self.total >= self.total_limit:
            raise Stop(f"limit łączny {self.total_limit} USD osiągnięty ({self.total:.4f})")
        started = time.monotonic()
        self.last = {}
        try:
            response = self.post(self.body(body), self.key)
        except orr.ReviewError as error:
            self.errors_in_row += 1
            message = redact(error.message, self.key)
            self.last = {"error": error.code, "errorMessage": message}
            if "HTTP 401" in message or "HTTP 402" in message or self.errors_in_row >= MAX_CONSECUTIVE_ERRORS:
                raise Stop(f"przerwano po błędzie dostawcy: {message}") from error
            raise inference.InferenceError("unavailable", message) from error
        self.errors_in_row = 0
        meta = orr.response_meta(response, self.model)
        cost = (meta.get("usage") or {}).get("cost")
        self.cost += float(cost) if cost is not None else 0.0
        self.ledger[self.model] = round(self.cost, 6)
        write_ledger(self.ledger)
        self.last = {"wallMs": round((time.monotonic() - started) * 1000, 1), **meta,
                     "rawResponse": redact(meta.get("rawResponse") or "", self.key)}
        return response

    def meta(self):
        return {"digest": f"openrouter:{self.model}:{self.endpoint['provider']}", "sizeBytes": None,
                "quantization": self.endpoint["quantization"], "parameterSize": None}


def raw_label(content):
    try:
        label = json.loads(content).get("label")
    except (ValueError, AttributeError):
        return None
    return label if label in CLASSES or label == inference.ABSTAIN else None


def e5_predictions(rows):
    """E5 labels on the held-out set: correct unless listed among the errors of the stored result."""
    stored = json.loads(E5_RESULT.read_text(encoding="utf-8"))
    wrong = {e["id"]: e["predicted"] for e in stored["errors"]}
    return {r["id"]: wrong.get(r["id"], r["label"]) for r in rows}, stored["model"]["correct"]


def run(model, endpoint, args, key, sleep=time.sleep):
    labels, rows = labeled_examples()
    rows = [r for r in rows if args.split == "all" or r["split"] == args.split][:args.limit]
    e5, e5_correct = e5_predictions(rows)
    ledger = read_ledger()
    meter = Meter(model, endpoint, key, args.max_price_per_mtok, args.max_model_cost, args.max_total_cost, ledger, sleep)
    os.environ.update({"INVESTWATCH_LLM": "1", "INVESTWATCH_LLM_BACKEND": "openrouter",
                       "INVESTWATCH_LLM_MODEL": model})
    inference._cache.clear()
    inference.use_remote(meter.chat, meter.meta)
    items, stopped = [], None
    try:
        for row in rows:
            try:
                result = inference.classify(row["capture"])
            except Stop as error:
                stopped = str(error)
                break
            last = meter.last
            items.append({
                "id": row["id"], "expected": row["label"], "e5": e5[row["id"]],
                "status": result["status"], "label": result.get("label"),
                "rawLabel": raw_label(last.get("rawResponse", "")),
                "quote": result.get("quote"), "lineId": (result.get("evidence") or {}).get("lineId"),
                "errorCode": result.get("errorCode"), "reason": result.get("reason"),
                "latencyMs": result.get("latencyMs"), "wallMs": last.get("wallMs"),
                "cost": (last.get("usage") or {}).get("cost"), "usage": last.get("usage"),
                "provider": last.get("provider"), "reportedModel": last.get("reportedModel"),
                "rawResponse": last.get("rawResponse") if result["status"] != "ready" else None,
            })
            print(f"[{len(items)}/{len(rows)}] {row['label']:>10} -> {str(result.get('label')):>10} "
                  f"{result['status']:<9} {result.get('errorCode') or ''} cost {meter.cost:.4f}", flush=True)
    finally:
        inference.use_remote(None, None)
    return rows, items, meter, stopped, e5_correct


def summarize(model, endpoint, args, rows, items, meter, stopped, e5_correct):
    n = len(items)
    expected = [i["expected"] for i in items]
    predicted = [i["label"] if i["status"] == "ready" else inference.ABSTAIN for i in items]
    metrics = confusion(expected, predicted) if n else None
    rejected = [i for i in items if i["status"] == "rejected"]
    unavailable = [i for i in items if i["status"] == "unavailable"]
    reasons = {}
    for item in rejected + unavailable:
        reasons[item["errorCode"]] = reasons.get(item["errorCode"], 0) + 1
    answered = [i for i in items if i["status"] == "ready"]
    latencies = sorted(i["wallMs"] for i in items if i["wallMs"] is not None)
    providers = sorted({i["provider"] for i in items if i["provider"]})
    return {
        "backend": "openrouter", "measurementOnly": True, "split": args.split, "model": model,
        "modelsReportedBy": sorted({i["reportedModel"] for i in items if i["reportedModel"]}),
        "provider": providers, "endpointProvider": endpoint["provider"], "endpointTag": endpoint["tag"],
        "quantization": endpoint["quantization"],
        "pricePerMtok": {"prompt": float(endpoint["prompt"] * 1_000_000),
                         "completion": float(endpoint["completion"] * 1_000_000)},
        "promptVersion": inference.PROMPT_VERSION,
        "parameters": {"temperature": 0, "seed": inference.SEED, "max_tokens": inference.MAX_TOKENS,
                       "structuredOutput": "json_schema strict", "reasoning": "disabled" if "reasoning" in endpoint["supported"] else "n/a"},
        "measuredOn": time.strftime("%Y-%m-%d", time.gmtime()),
        "completed": n, "planned": len(rows), "stopped": stopped,
        "statuses": {s: sum(i["status"] == s for i in items) for s in sorted({i["status"] for i in items})},
        "rejectedShare": len(rejected) / n if n else None,
        "unavailableShare": len(unavailable) / n if n else None,
        "rejectionReasons": reasons,
        "rawLabelAccuracy": (sum(i["rawLabel"] == i["expected"] for i in items) / n) if n else None,
        "metrics": metrics,
        "e5": {"correct": e5_correct, "n": len(rows)},
        "agreementWithE5": {"answered": len(answered),
                            "same": sum(i["label"] == i["e5"] for i in answered),
                            "share": (sum(i["label"] == i["e5"] for i in answered) / len(answered)) if answered else None},
        "costUsd": round(meter.cost, 6),
        "wallMs": {"median": latencies[len(latencies) // 2] if latencies else None, "max": latencies[-1] if latencies else None},
        "tokens": {"prompt": sum((i["usage"] or {}).get("prompt_tokens", 0) for i in items),
                   "completion": sum((i["usage"] or {}).get("completion_tokens", 0) for i in items)},
        "acceptance": None if not n or stopped else {
            "threshold": "trafność >= 30/57 i odrzucenia walidatora <= 10%",
            "passed": metrics["correct"] >= 30 and len(rejected) / n <= 0.10},
        "items": items,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", required=True, help="identyfikator OpenRouter, np. qwen/qwen3.5-9b")
    parser.add_argument("--public-source", required=True, action="store_true",
                        help="potwierdź wysłanie tytułów i opisów publicznych materiałów YouTube do OpenRouter")
    parser.add_argument("--provider", help="tylko ten dostawca (domyślnie najtańszy endpoint ze structured outputs)")
    parser.add_argument("--split", default="heldout", choices=("heldout", "tuning", "all"))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--max-price-per-mtok", type=float, default=MAX_PRICE)
    parser.add_argument("--max-model-cost", type=float, default=MAX_MODEL_COST)
    parser.add_argument("--max-total-cost", type=float, default=MAX_TOTAL_COST)
    parser.add_argument("--out", type=Path, help="plik wyniku (domyślnie fixtures/labeled/ai-material-type-result-<model>.json)")
    parser.add_argument("--dry-run", action="store_true", help="tylko lokalna kontrola cennika, bez żądań")
    args = parser.parse_args(argv)
    if not orr._valid_model(args.model):
        raise SystemExit("Nieprawidłowy identyfikator modelu.")
    if not 0 < args.max_price_per_mtok <= MAX_PRICE:
        raise SystemExit(f"--max-price-per-mtok musi mieścić się w (0, {MAX_PRICE}].")
    if args.provider is not None and not re.fullmatch(r"[A-Za-z0-9 ._-]{1,60}", args.provider):
        raise SystemExit("Nieprawidłowa nazwa dostawcy.")
    try:
        prices = orr.fetch_endpoint_prices(args.model)
    except orr.ReviewError as error:
        raise SystemExit(error.message)
    endpoint = choose_endpoint(prices, args.max_price_per_mtok, args.provider)
    print(f"Endpoint: {endpoint['provider']} {endpoint['quantization']} "
          f"{float(endpoint['prompt'] * 10**6):.3f}/{float(endpoint['completion'] * 10**6):.3f} USD/Mtok", flush=True)
    if args.dry_run:
        return 0
    key = load_key()
    rows, items, meter, stopped, e5_correct = run(args.model, endpoint, args, key)
    summary = summarize(args.model, endpoint, args, rows, items, meter, stopped, e5_correct)
    out = args.out or OUT_DIR / f"ai-material-type-result-{re.sub(r'[^A-Za-z0-9.]+', '-', args.model.split('/')[-1])}.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    m = summary["metrics"]
    if m:
        print(f"{args.model} [{endpoint['provider']} {endpoint['quantization']}]: trafność {m['correct']}/{m['n']}, "
              f"macro-F1 {m['macroF1']:.3f}, odrzucone {summary['rejectedShare']:.1%}, koszt {meter.cost:.4f} USD")
    if stopped:
        print(f"PRZERWANO: {stopped}")
    print(f"Zapisano {out}")
    return 3 if stopped else 0


if __name__ == "__main__":
    raise SystemExit(main())
