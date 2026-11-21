#!/usr/bin/env python3
"""Zmierz drugi głos LLM (analysis/second_opinion.py) na zbiorach M1, M2 i M3 przez OpenRouter.

Wyłącznie pomiar wyboru modelu: produkt działa lokalnie (Ollama), worker nigdy nie czyta klucza. Narzędzie
rejestruje transport w analysis.inference (use_remote), więc prompt, schemat JSON, temperatura 0 i walidator
cytatów są takie same jak dla Ollamy. Wejścia są budowane raz i zapisywane w .runtime/second-opinion/cases-*.json
(skrót wejścia w każdym wyniku), więc wszystkie modele dostają identyczne dane.

Zabezpieczenia jak w tools/measure_llm_openrouter.py: lokalna kontrola cennika i wybór endpointu ze
structured outputs przed pierwszym żądaniem, --max-price-per-mtok (domyślnie 3), limit na model i łączny limit
tej serii wg usage.cost (osobny rejestr .runtime/second-opinion/ledger/, sumowany przy każdym żądaniu, także
między równoległymi procesami), jedno żądanie naraz w procesie, data_collection: deny, klucz z
OPENROUTER_API_KEY albo .env.openrouter, redagowany w każdym zapisie.

  .runtime/venv/bin/python -B tools/measure_second_opinion.py cases            # zbuduj wejścia (bez sieci)
  .runtime/venv/bin/python -B tools/measure_second_opinion.py run --model qwen/qwen3.5-27b --module all \\
      --split all --public-source
  .runtime/venv/bin/python -B tools/measure_second_opinion.py report           # tabela i podsumowanie
"""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis import inference, second_opinion as so, openrouter_review as orr  # noqa: E402
from tools import measure_llm_openrouter as mlo  # noqa: E402

WORK = ROOT / ".runtime" / "second-opinion"
LEDGER_DIR = WORK / "ledger"
OUT_DIR = ROOT / "fixtures" / "labeled"
SUMMARY = OUT_DIR / "ai-second-opinion-summary.json"
MODULES = ("m1", "m2k03", "m2k09", "m3")
MAX_MODEL_COST, MAX_TOTAL_COST = 0.60, 2.40
REGISTRY_STATES = ("authorized_advice", "investment_firm_agent")
RATE_LIMIT_BACKOFF = (5, 15, 30, 60, None)  # seconds before the next try; None = give up
Q_V2 = ROOT / "fixtures" / "validation" / "q-v2"
M3_DIR = ROOT / "fixtures" / "raw" / "discovery" / "m3-2026-11-21"


def slug(model):
    return re.sub(r"[^A-Za-z0-9.]+", "-", model.split("/")[-1])


def split_of(group, salt=""):
    """Deterministic split by independent unit (campaign, firm, domain): even hash byte = tuning. The M3 salt
    was chosen before any model run so that both parts hold 3 positives (unsalted: 5 and 1)."""
    return "tuning" if sha256((salt + group).encode()).digest()[0] % 2 == 0 else "heldout"


def digest(obj):
    return sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]


# --- Cases (built once, offline) ----------------------------------------------------------------

def build_m1():
    import importlib.util
    spec = importlib.util.spec_from_file_location("uruchom_warianty", Q_V2 / "uruchom_warianty.py")
    uw = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(uw)
    from analysis import qualification
    labels = [json.loads(l) for l in (Q_V2 / "etykiety-agentow.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    preds = {}
    for variant in ("qual_d", "rules_1_2"):
        for line in (Q_V2 / f"predykcje-{variant}-pelne.jsonl").read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if "materialId" in row:
                preds.setdefault(row["materialId"], {})[variant] = row["route"]
    replay = {c["id"]: c for c in uw.load_json(uw.API_DIR / "replay.json.gz")["captures"]}
    flags = uw.api_flags()
    cases = []
    for label in labels:
        if label.get("sourceSet") != "media-2026-11-21":
            continue  # q-v1 text-only items: no relation found by the rules, nothing to verify
        vid = label["materialId"].split(":", 1)[1]
        full = uw.media_capture(vid, replay, flags, True)
        q = qualification.qualify(full)
        rel = q["adRelationship"]
        ev = {e["id"]: e for e in q.get("evidence") or []}
        quotes = []
        for ref in rel.get("evidenceRefs") or []:
            item = ev.get(ref) or {}
            if (item.get("modality") == "description" and item.get("role") != "disclosure" and item.get("text")
                    and item["text"] not in quotes):
                quotes.append(item["text"])
        capture = {"title": full.get("title"), "description": full.get("description"),
                   "segments": [{"start": s["start"], "text": s["text"]} for s in full.get("segments") or []]}
        firm = (rel.get("firm") or {}).get("mention") or label.get("advertiser")
        rules = {v: ("brak_ujawnienia" if preds[label["materialId"]][v] == "refer" else "ujawnione") for v in preds[label["materialId"]]}
        cases.append({"id": label["materialId"], "group": label["campaignId"], "split": split_of(label["campaignId"]),
                      "truthPositive": label["label"] == "skieruj", "truthLabel": label["label"],
                      "rulesVerdict": rules["qual_d"], "rulesVerdictAlt": {"rules_1_2": rules["rules_1_2"]},
                      "relationStatus": rel.get("status"), "input": {"capture": capture, "firm": firm, "relationQuotes": quotes[:3]}})
    return cases


def _m2_pages():
    from analysis.m2_rules import PREMISE, evaluate
    from collectors.m2_market import market_captures, material
    labels = {json.loads(l)["id"]: json.loads(l) for l in (OUT_DIR / "m2-agent-labels.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}
    captures, _, _ = market_captures()
    for cap in captures:
        pid = cap["m2Market"]["manifest"]
        mat = material(cap)
        rows = {r["id"]: r for r in evaluate(mat)}
        premises = [k for k, r in rows.items() if r["state"] == PREMISE]
        yield pid, cap, mat, rows, premises, labels[pid]


def build_m2():
    from analysis.m2_card import WEIGHTS, THRESHOLD
    from analysis.m2_rules import OK, PREMISE

    def flagged(premises):
        return bool(premises) and min(100, sum(WEIGHTS[p] for p in premises)) >= THRESHOLD
    k03, k09 = [], []
    for pid, cap, mat, rows, premises, label in _m2_pages():
        firm = cap["m2Market"]["firm"]["brand"]
        page = {"pageLabel": label["label"], "rulesFlag": flagged(premises),
                "flagIfPremise": {k: flagged(sorted(set(premises) | {k})) for k in ("3", "9")},
                "flagIfCleared": {k: flagged(sorted(set(premises) - {k})) for k in ("3", "9")}}
        row = rows["3"]
        if row["state"] in (PREMISE, OK):
            claims = [m for m in row.get("measurements") or [] if m.get("focus") == "claim"]
            pick = next((m for m in claims if m.get("quote") == row.get("quote")), claims[0] if claims else None)
            if pick:
                viewport = "phone" if str(pick.get("viewport", "")).startswith("phone") else "desktop"
                view = mat["views"][viewport]
                lines = so.m2_claim_lines(view, pick.get("blockIndex"), pick.get("quote"))
                k03.append({"id": pid, "group": firm, "split": split_of(firm), "truthPositive": "3" in label["criteria"],
                            "rulesVerdict": "brak_ostrzezenia" if row["state"] == PREMISE else "ostrzezenie_obok", **page,
                            "input": {"claim": pick.get("quote"), "products": pick.get("products") or [], "viewport": viewport,
                                      "lines": lines}})
        row = rows["9"]
        if row["state"] in (PREMISE, OK) and row.get("quote"):
            k09.append({"id": pid, "group": firm, "split": split_of(firm), "truthPositive": "9" in label["criteria"],
                        "rulesVerdict": "niezrozumiale" if row["state"] == PREMISE else "zrozumiale", **page,
                        "input": {"warning": row["quote"]}})
    return k03, k09


def build_m3():
    labels = {json.loads(l)["entityId"]: json.loads(l) for l in (OUT_DIR / "m3-agent-labels.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}
    entities = {e["id"]: e for e in json.loads((M3_DIR / "entities.json").read_text(encoding="utf-8"))["entities"]}
    results = json.loads((M3_DIR / "results.json").read_text(encoding="utf-8"))["results"]
    cases = []
    for result in results:
        eid = result["entityId"]
        if eid not in labels or eid not in entities or not any(p.get("text") for p in entities[eid].get("pages") or []):
            continue
        evidence = []
        for axis in ("action", "personalisation"):
            evidence += (result["axes"].get(axis) or {}).get("evidence") or []
        pages = [{"url": p["url"], "text": p["text"]} for p in entities[eid]["pages"] if p.get("text")]
        marks = {}
        for item in evidence:
            loc = item.get("locator") or {}
            if loc.get("url") and loc.get("line"):
                marks.setdefault(loc["url"], set()).add(int(loc["line"]))
        cases.append({"id": eid, "group": result["domain"], "split": split_of(result["domain"], "m3-1"),
                      "truthPositive": labels[eid]["label"] in ("complete", "refer"), "truthLabel": labels[eid]["label"],
                      "rulesRoute": result["route"], "identityState": (result.get("identity") or {}).get("state"),
                      "rulesVerdict": "oferta_rekomendacji" if result["route"] in ("complete", "refer") else "informacja_edukacja",
                      "input": {"lines": so.m3_lines(pages, marks), "evidence": [{"quote": e.get("quote")} for e in evidence[:6]]}})
    return cases


def cases_path(module):
    return WORK / f"cases-{module}.json"


def build_cases():
    WORK.mkdir(parents=True, exist_ok=True)
    k03, k09 = build_m2()
    built = {"m1": build_m1(), "m2k03": k03, "m2k09": k09, "m3": build_m3()}
    for module, cases in built.items():
        for case in cases:
            case["inputSha"] = digest(case["input"])
        cases_path(module).write_text(json.dumps(cases, ensure_ascii=False, indent=1), encoding="utf-8")
        pos = sum(c["truthPositive"] for c in cases)
        print(f"{module}: {len(cases)} przypadków ({pos} pozytywnych), strojenie {sum(c['split'] == 'tuning' for c in cases)} "
              f"(poz. {sum(c['truthPositive'] for c in cases if c['split'] == 'tuning')}), odłożone "
              f"{sum(c['split'] == 'heldout' for c in cases)} (poz. {sum(c['truthPositive'] for c in cases if c['split'] == 'heldout')})")
    return built


def load_cases(module):
    return json.loads(cases_path(module).read_text(encoding="utf-8"))


# --- Metered transport --------------------------------------------------------------------------

def spent_total():
    total = 0.0
    for path in LEDGER_DIR.glob("*.json"):
        try:
            total += float(json.loads(path.read_text(encoding="utf-8")).get("cost", 0))
        except (OSError, ValueError, TypeError):
            continue
    return total


class SeriesMeter(mlo.Meter):
    """mlo.Meter with a separate per-process ledger file; the series limit sums every file in LEDGER_DIR."""

    def __init__(self, model, endpoint, key, max_price, model_limit, total_limit):
        super().__init__(model, endpoint, key, max_price, model_limit, total_limit, {})
        LEDGER_DIR.mkdir(parents=True, exist_ok=True)
        self.ledger_path = LEDGER_DIR / f"{slug(model)}-{os.getpid()}-{int(time.time())}.json"

    def _post_with_backoff(self, body):
        """HTTP 429 (rate limit of the provider) is retried with backoff; nothing was billed for it."""
        for wait in RATE_LIMIT_BACKOFF:
            try:
                return self.post(self.body(body), self.key)
            except orr.ReviewError as error:
                if "HTTP 429" not in error.message or wait is None:
                    raise
                self.sleep(wait)

    def chat(self, body):
        if self.cost >= self.model_limit:
            raise mlo.Stop(f"limit kosztu modelu {self.model_limit} USD osiągnięty ({self.cost:.4f})")
        if spent_total() >= self.total_limit:
            raise mlo.Stop(f"limit serii {self.total_limit} USD osiągnięty ({spent_total():.4f})")
        started = time.monotonic()
        self.last = {}
        try:
            response = self._post_with_backoff(body)
        except orr.ReviewError as error:
            self.errors_in_row += 1
            message = mlo.redact(error.message, self.key)
            self.last = {"error": error.code, "errorMessage": message}
            if "HTTP 401" in message or "HTTP 402" in message or self.errors_in_row >= mlo.MAX_CONSECUTIVE_ERRORS:
                raise mlo.Stop(f"przerwano po błędzie dostawcy: {message}") from error
            raise inference.InferenceError("unavailable", message) from error
        self.errors_in_row = 0
        meta = orr.response_meta(response, self.model)
        cost = (meta.get("usage") or {}).get("cost")
        self.cost += float(cost) if cost is not None else 0.0
        self.ledger_path.write_text(json.dumps({"model": self.model, "cost": round(self.cost, 6)}), encoding="utf-8")
        self.last = {"wallMs": round((time.monotonic() - started) * 1000, 1), **meta,
                     "rawResponse": mlo.redact(meta.get("rawResponse") or "", self.key)}
        return response


# --- Running one module --------------------------------------------------------------------------

def ask_case(module, case, model):
    data = case["input"]
    if module == "m1":
        return so.review_m1(data["capture"], data["firm"], data["relationQuotes"], case["rulesVerdict"], model)
    if module == "m2k03":
        context = {"twierdzenie": str(data["claim"] or "")[:300], "produkty": sorted(data["products"]), "ekran": data["viewport"]}
        answer = so.ask("m2_k03", context, data["lines"], model)
        return so._envelope("m2_k03", case["rulesVerdict"], model, answer, {"viewport": data["viewport"], "block": answer.get("lineId")})
    if module == "m2k09":
        return so.review_m2_k09(data["warning"], case["rulesVerdict"], model)
    answer = so.ask("m3_offer", {"dowodyRegul": [str(e["quote"])[:300] for e in data["evidence"]]}, data["lines"], model)
    return so._envelope("m3_offer", case["rulesVerdict"], model, answer, {"lineId": answer.get("lineId")})


TASK_OF = {"m1": "m1_disclosure", "m2k03": "m2_k03", "m2k09": "m2_k09", "m3": "m3_offer"}


def run_module(module, model, meter, split, limit=None):
    cases = [c for c in load_cases(module) if split == "all" or c["split"] == split][:limit]
    items, stopped = [], None
    for case in cases:
        before, raw = meter.cost, []
        original = meter.chat

        def chat(body, _orig=original):
            try:
                return _orig(body)
            finally:
                if meter.last.get("rawResponse") is not None or meter.last.get("errorMessage"):
                    raw.append(meter.last.get("rawResponse") or meter.last.get("errorMessage"))
        inference.use_remote(chat, meter.meta)
        try:
            result = ask_case(module, case, model)
        except mlo.Stop as error:
            stopped = str(error)
            break
        finally:
            inference.use_remote(None, None)
        positive = None if result["status"] != "ready" else result["verdict"] == so.POSITIVE[TASK_OF[module]]
        items.append({"id": case["id"], "group": case["group"], "split": case["split"], "inputSha": case["inputSha"],
                      "truthPositive": case["truthPositive"], "rulesPositive": case["rulesVerdict"] == so.POSITIVE[TASK_OF[module]],
                      "status": result["status"], "verdict": result["verdict"], "modelPositive": positive,
                      "quote": result.get("quote"), "locator": result.get("locator"), "confidence": result.get("confidence"),
                      "explanation": result.get("explanation"), "errorCode": result.get("errorCode"),
                      "calls": len(result.get("calls") or []) or 1, "callStatuses": [c["status"] for c in result.get("calls") or []],
                      "cost": round(meter.cost - before, 6), "latencyMs": result.get("latencyMs"),
                      "rawRejected": [r[:600] for r in raw] if result["status"] not in ("ready",) else None})
        print(f"  [{module} {len(items)}/{len(cases)}] {case['id'][:40]:40} truth={int(case['truthPositive'])} "
              f"rules={int(items[-1]['rulesPositive'])} -> {result['status']:<9} {result['verdict'] or result.get('errorCode') or ''} "
              f"cost {meter.cost:.4f}", flush=True)
    return cases, items, stopped


def result_path(module, model):
    return OUT_DIR / f"ai-second-opinion-{module}-{slug(model)}.json"


def save_run(module, model, endpoint, split, cases, items, stopped, meter_cost):
    path = result_path(module, model)
    document = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {
        "measurementOnly": True, "backend": "openrouter", "module": module, "task": TASK_OF[module], "model": model,
        "labels": "etykiety agentów (Claude), nie ekspertów", "runs": []}
    run = {"promptVersion": so.PROMPT_VERSION, "split": split, "measuredOn": time.strftime("%Y-%m-%d", time.gmtime()),
           "endpointProvider": endpoint["provider"], "quantization": endpoint["quantization"],
           "pricePerMtok": {"prompt": float(endpoint["prompt"] * 1_000_000), "completion": float(endpoint["completion"] * 1_000_000)},
           "parameters": {"temperature": 0, "seed": inference.SEED, "max_tokens": so.MAX_TOKENS, "structuredOutput": "json_schema strict",
                          "reasoning": "disabled" if "reasoning" in endpoint["supported"] else "n/a"},
           "planned": len(cases), "completed": len(items), "stopped": stopped, "costUsd": round(meter_cost, 6), "items": items}
    document["runs"] = [r for r in document["runs"] if (r["promptVersion"], r["split"]) != (so.PROMPT_VERSION, split)] + [run]
    path.write_text(json.dumps(document, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return path


# --- Metrics ---------------------------------------------------------------------------------------

def cost_2fn_fp(truth, predicted):
    fn = sum(t and not p for t, p in zip(truth, predicted))
    fp = sum(p and not t for t, p in zip(truth, predicted))
    return {"FN": fn, "FP": fp, "cost": 2 * fn + fp}


def metrics(module, items, cases):
    by_id = {c["id"]: c for c in cases}
    n = len(items)
    ready = [i for i in items if i["status"] == "ready"]
    registry = []
    if module == "m3":  # registry-decided entities: the label follows the register, not the content question
        registry = [i["id"] for i in ready if by_id[i["id"]]["identityState"] in REGISTRY_STATES]
        ready = [i for i in ready if i["id"] not in registry]
    fixes = [i["id"] for i in ready if i["rulesPositive"] != i["truthPositive"] and i["modelPositive"] == i["truthPositive"]]
    breaks = [i["id"] for i in ready if i["rulesPositive"] == i["truthPositive"] and i["modelPositive"] != i["truthPositive"]]
    rejected = [i for i in items if i["status"] == "rejected"]
    calls = sum(i["calls"] for i in items)
    rejected_calls = sum(s == "rejected" for i in items for s in i["callStatuses"]) if module == "m1" else len(rejected)
    truth = [i["truthPositive"] for i in items]
    rules = [i["rulesPositive"] for i in items]
    veto = [r and not (i["status"] == "ready" and i["modelPositive"] is False) for r, i in zip(rules, items)]
    escalate = [r or (i["status"] == "ready" and i["modelPositive"] is True) for r, i in zip(rules, items)]
    if module == "m3":  # registry decisions are not content questions; the model never escalates them
        escalate = [r or (i["status"] == "ready" and i["modelPositive"] is True
                          and by_id[i["id"]]["identityState"] not in REGISTRY_STATES)
                    for r, i in zip(rules, items)]
    out = {"n": n, "ready": len(ready), "abstained": sum(i["status"] == "abstained" for i in items),
           "rejected": len(rejected), "unavailable": sum(i["status"] == "unavailable" for i in items),
           "calls": calls, "rejectedCalls": rejected_calls, "rejectedCallShare": rejected_calls / calls if calls else None,
           "modelCorrect": sum(i["modelPositive"] == i["truthPositive"] for i in ready),
           "agreementWithRules": sum(i["modelPositive"] == i["rulesPositive"] for i in ready),
           "rulesErrors": sum(r != t for r, t in zip(rules, truth)),
           "registryDecidedExcluded": registry,
           "fixed": len(fixes), "broken": len(breaks), "fixedIds": fixes, "brokenIds": breaks,
           "policy": {"rules": cost_2fn_fp(truth, rules), "veto": cost_2fn_fp(truth, veto), "escalation": cost_2fn_fp(truth, escalate)},
           "costUsd": round(sum(i["cost"] for i in items), 6),
           "latencyMsMedianPerItem": sorted(i["latencyMs"] for i in items if i["latencyMs"] is not None)[len(items) // 2] if items else None}
    if module == "m1":
        alt = [by_id[i["id"]]["rulesVerdictAlt"]["rules_1_2"] == "brak_ujawnienia" for i in items]
        fix_alt = [i["id"] for i, a in zip(items, alt) if i["status"] == "ready" and a != i["truthPositive"] and i["modelPositive"] == i["truthPositive"]]
        break_alt = [i["id"] for i, a in zip(items, alt) if i["status"] == "ready" and a == i["truthPositive"] and i["modelPositive"] != i["truthPositive"]]
        out["vsRules12"] = {"rulesErrors": sum(a != t for a, t in zip(alt, truth)), "fixed": len(fix_alt), "broken": len(break_alt),
                            "policy": {"rules": cost_2fn_fp(truth, alt),
                                       "veto": cost_2fn_fp(truth, [a and not (i["status"] == "ready" and i["modelPositive"] is False) for a, i in zip(alt, items)]),
                                       "escalation": cost_2fn_fp(truth, [a or (i["status"] == "ready" and i["modelPositive"] is True) for a, i in zip(alt, items)])}}
    if module in ("m2k03", "m2k09"):
        key = "3" if module == "m2k03" else "9"
        page_truth = [by_id[i["id"]]["pageLabel"] for i in items]
        page_rules = [by_id[i["id"]]["rulesFlag"] for i in items]
        page_veto = [by_id[i["id"]]["flagIfCleared"][key] if (i["rulesPositive"] and i["status"] == "ready" and i["modelPositive"] is False)
                     else by_id[i["id"]]["rulesFlag"] for i in items]
        page_esc = [by_id[i["id"]]["rulesFlag"] or (i["status"] == "ready" and i["modelPositive"] is True
                                                     and by_id[i["id"]]["flagIfPremise"][key]) for i in items]
        out["pageLevel"] = {"note": "tylko strony, na których drugi głos miał o co zapytać",
                            "rules": cost_2fn_fp(page_truth, page_rules), "veto": cost_2fn_fp(page_truth, page_veto),
                            "escalation": cost_2fn_fp(page_truth, page_esc)}
    return out


# --- Commands ----------------------------------------------------------------------------------------

def command_run(args):
    if not orr._valid_model(args.model):
        raise SystemExit("Nieprawidłowy identyfikator modelu.")
    if not 0 < args.max_price_per_mtok <= mlo.MAX_PRICE:
        raise SystemExit(f"--max-price-per-mtok musi mieścić się w (0, {mlo.MAX_PRICE}].")
    if args.provider is not None and not re.fullmatch(r"[A-Za-z0-9 ._-]{1,60}", args.provider):
        raise SystemExit("Nieprawidłowa nazwa dostawcy.")
    if args.max_total_cost > MAX_TOTAL_COST:
        raise SystemExit(f"--max-total-cost nie może przekroczyć {MAX_TOTAL_COST} USD (limit tej serii).")
    try:
        prices = orr.fetch_endpoint_prices(args.model)
    except orr.ReviewError as error:
        raise SystemExit(error.message)
    endpoint = mlo.choose_endpoint(prices, args.max_price_per_mtok, args.provider)
    print(f"Endpoint: {endpoint['provider']} {endpoint['quantization']} {float(endpoint['prompt'] * 10**6):.3f}/"
          f"{float(endpoint['completion'] * 10**6):.3f} USD/Mtok; wydano w serii {spent_total():.4f} USD", flush=True)
    if args.dry_run:
        return 0
    key = mlo.load_key()
    meter = SeriesMeter(args.model, endpoint, key, args.max_price_per_mtok, args.max_model_cost, args.max_total_cost)
    os.environ.update({"INVESTWATCH_LLM_BACKEND": "openrouter", "INVESTWATCH_SECOND_OPINION": "1",
                       "INVESTWATCH_SECOND_OPINION_MODEL": args.model})
    so._cache.clear()
    inference._digests.clear()
    modules = MODULES if args.module == "all" else tuple(args.module.split(","))
    code = 0
    for module in modules:
        before = meter.cost
        cases, items, stopped = run_module(module, args.model, meter, args.split, args.limit)
        path = save_run(module, args.model, endpoint, args.split, cases, items, stopped, meter.cost - before)
        summary = metrics(module, items, load_cases(module))
        print(f"{module} {args.model}: naprawione {summary['fixed']}, zepsute {summary['broken']}, odrzucone {summary['rejected']}/"
              f"{summary['n']}, zgodność {summary['agreementWithRules']}/{summary['ready']}, koszt {summary['costUsd']:.4f} USD -> {path.name}",
              flush=True)
        if stopped:
            print(f"PRZERWANO: {stopped}")
            code = 3
            break
    print(f"Koszt modelu {meter.cost:.4f} USD; seria łącznie {spent_total():.4f} USD")
    return code


def held_extra(h):
    extra = h.get("vsRules12") or h.get("pageLevel") or {}
    p = extra.get("policy", extra)
    if not p:
        return ""
    fixed = f"naprawione {extra['fixed']}, zepsute {extra['broken']}, " if "fixed" in extra else ""
    return f"; odłożone (n={h['n']}): {fixed}2FN+FP {p['rules']['cost']}/{p['veto']['cost']}/{p['escalation']['cost']}"


def command_report(args):
    cases = {m: load_cases(m) for m in MODULES}
    report = {"promptVersion": args.prompt_version, "labels": "etykiety agentów (Claude), nie ekspertów", "modules": {}}
    for path in sorted(OUT_DIR.glob("ai-second-opinion-m*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        runs = [r for r in document["runs"] if r["promptVersion"] == args.prompt_version]
        items = {}
        for run in runs:
            for item in run["items"]:
                items[item["id"]] = item
        if not items:
            continue
        module = document["module"]
        all_items = list(items.values())
        entry = {"provider": sorted({r["endpointProvider"] for r in runs}), "quantization": sorted({str(r["quantization"]) for r in runs}),
                 "complete": len(all_items) == len(cases[module]),
                 "all": metrics(module, all_items, cases[module]),
                 "tuning": metrics(module, [i for i in all_items if i["split"] == "tuning"], cases[module]),
                 "heldout": metrics(module, [i for i in all_items if i["split"] == "heldout"], cases[module])}
        report["modules"].setdefault(module, {})[document["model"]] = entry
    SUMMARY.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for module, models in report["modules"].items():
        print(f"\n## {module} (n={len(cases[module])}, poz. {sum(c['truthPositive'] for c in cases[module])})")
        print("| Model | n | Trafne | Naprawione | Zepsute | Odrzucone (odp./wywołania) | Zgodność z regułami | 2FN+FP reguły / weto / eskalacja | Koszt USD | Mediana ms |")
        print("|---|---|---|---|---|---|---|---|---|---|")
        for model, entry in sorted(models.items()):
            m = entry["all"]
            p = m["policy"]
            print(f"| {model}{'' if entry['complete'] else ' (niepełny)'} | {m['n']} | {m['modelCorrect']}/{m['ready']} | {m['fixed']} | {m['broken']} | "
                  f"{m['rejected']} / {m['rejectedCalls']} z {m['calls']} | {m['agreementWithRules']}/{m['ready']} | "
                  f"{p['rules']['cost']} / {p['veto']['cost']} / {p['escalation']['cost']} | {m['costUsd']:.4f} | {m['latencyMsMedianPerItem']} |")
        for model, entry in sorted(models.items()):
            m = entry["all"]
            extra = m.get("vsRules12") or m.get("pageLevel")
            if extra:
                p = extra["policy"] if "policy" in extra else extra
                label = (f"względem rules_1_2: błędy reguł {extra['rulesErrors']}, naprawione {extra['fixed']}, zepsute {extra['broken']}; "
                         if "rulesErrors" in extra else "poziom strony: ")
                print(f"- {model}: {label}2FN+FP reguły/weto/eskalacja {p['rules']['cost']}/{p['veto']['cost']}/{p['escalation']['cost']}"
                      + held_extra(entry["heldout"]))
            else:
                h = entry["heldout"]
                print(f"- {model}: odłożone (n={h['n']}): naprawione {h['fixed']}, zepsute {h['broken']}, "
                      f"2FN+FP {h['policy']['rules']['cost']}/{h['policy']['veto']['cost']}/{h['policy']['escalation']['cost']}")
    print(f"\nSeria łącznie: {spent_total():.4f} USD. Zapisano {SUMMARY}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("cases", help="Zbuduj identyczne wejścia dla wszystkich modeli (bez sieci).")
    run = sub.add_parser("run", help="Uruchom model przez OpenRouter.")
    run.add_argument("--model", required=True)
    run.add_argument("--public-source", required=True, action="store_true",
                     help="potwierdź wysłanie publicznych opisów, transkrypcji i stron WWW do OpenRouter")
    run.add_argument("--module", default="all", help="all albo lista: m1,m2k03,m2k09,m3")
    run.add_argument("--split", default="all", choices=("tuning", "heldout", "all"))
    run.add_argument("--provider")
    run.add_argument("--limit", type=int)
    run.add_argument("--max-price-per-mtok", type=float, default=mlo.MAX_PRICE)
    run.add_argument("--max-model-cost", type=float, default=MAX_MODEL_COST)
    run.add_argument("--max-total-cost", type=float, default=MAX_TOTAL_COST)
    run.add_argument("--dry-run", action="store_true")
    rep = sub.add_parser("report", help="Policz metryki z zapisanych wyników.")
    rep.add_argument("--prompt-version", default=so.PROMPT_VERSION)
    args = parser.parse_args(argv)
    if args.command == "cases":
        build_cases()
        return 0
    return command_run(args) if args.command == "run" else command_report(args)


if __name__ == "__main__":
    raise SystemExit(main())
