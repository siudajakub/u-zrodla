"""One M2 card per material: 19 rows, a rule score, three plain-language reasons and the Finding fields.

``card(capture)`` returns the same 4-tuple as ``analysis.engine.m2`` (score, summary, evidence, extra),
so the engine can route market captures here with a two-line change (see the lane record).
"""
from collections import Counter
from hashlib import sha256

from .m2_rules import NA, OK, ORDER, PREMISE, RULES_VERSION, UNKNOWN, evaluate

# Weight of a premise in the rule score (pre-registered before the agent's labels were compared).
WEIGHTS = {"3": 35, "18": 30, "17": 25, "14": 20, "7": 15, "10": 15, "15": 15, "16": 15, "1": 15,
           "4": 10, "5": 10, "6": 10, "11": 10, "12a": 10, "12b": 10, "13": 10, "8": 5, "9": 5, "2": 5}
THRESHOLD = 30          # refer at or above (sensitive variant)
STRICT_THRESHOLD = 50   # second variant compared in the evaluation
VIEW_LABEL = {"desktop": "komputer", "phone": "telefon"}


def _q(text, limit=110):
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"


def reason_for(row):
    """A sentence for a person: no criterion numbers, no field names, never 'naruszenie'."""
    q = _q(row.get("quote"))
    quote = f" („{q}”)" if q else ""
    lead = "Przesłanka do sprawdzenia: "
    texts = {
        "1": "na stronie nie znaleziono pełnej nazwy firmy z rejestru KNF.",
        "2": "strona zachęca do skorzystania z oferty, ale nie oznaczono jej jako reklamy.",
        "3": f"obietnica zysku{quote} nie ma obok siebie informacji o ryzyku tego samego produktu.",
        "4": "informacja o ryzyku jest pisana wyraźnie mniejszą czcionką niż reszta strony.",
        "5": "informację o ryzyku słabo widać: jest blada, zasłonięta albo pojawia się dopiero po przewinięciu, gdy korzyść widać od razu.",
        "6": "informacja o ryzyku jest schowana w stopce, przypisie albo na samym dole strony.",
        "7": "informację o ryzyku widać dopiero po rozwinięciu elementu albo kliknięciu odsyłacza.",
        "8": "na telefonie informacja o ryzyku jest ucięta, zbyt drobna albo niewidoczna.",
        "9": "ostrzeżenie jest napisane trudnym językiem: długie zdania i terminy fachowe.",
        "10": "ostrzeżenie jest w innym języku niż główny przekaz.",
        "11": f"strona porównuje się z innymi{quote}, ale nie podaje źródła ani założeń.",
        "12a": f"wyniki z przeszłości{quote} pokazano bez pełnych pięciu lat, okresu albo źródła.",
        "12b": "przy wynikach z przeszłości nie wyjaśniono wpływu kosztów albo kursu walut.",
        "13": f"wyniki z przeszłości{quote} są najbardziej widocznym elementem strony.",
        "14": f"wyniki z przeszłości{quote} pokazano bez zastrzeżenia, że nie przesądzają o przyszłych.",
        "15": f"strona podaje prognozę{quote} bez zastrzeżenia, że nie jest ona pewnym wskaźnikiem.",
        "16": f"wzmianka o podatkach{quote} nie mówi, że korzyść zależy od sytuacji klienta i przepisy mogą się zmienić.",
        "17": f"odwołanie do organu nadzoru{quote} może brzmieć jak jego poparcie dla oferty.",
        "18": f"bezpieczeństwo oferty uzasadniono nadzorem{quote}.",
    }
    return lead + texts[row["id"]]


def _evidence_id(case_id, row_id):
    return f"m2:{case_id}:{row_id}"


def build(capture, rows, threshold=THRESHOLD):
    market = capture.get("m2Market") or {}
    views = market.get("views") or {}
    counts = Counter(row["state"] for row in rows)
    premises = [row for row in rows if row["state"] == PREMISE]
    components = [{"id": row["id"], "label": row["label"], "points": WEIGHTS[row["id"]]} for row in premises]
    score = min(100, sum(c["points"] for c in components))
    route = "refer" if premises and score >= threshold else "no_signal"
    if counts[UNKNOWN] >= 15:
        route = "insufficient"
    ranked = sorted(premises, key=lambda row: (-WEIGHTS[row["id"]], ORDER.index(row["id"])))
    reasons = [reason_for(row) for row in ranked[:3]]
    if len(reasons) < 3:
        reasons.append(f"Pozostałe kryteria: spełnione {counts[OK]}, nie dotyczy {counts[NA]}, bez danych {counts[UNKNOWN]}; przy nich nie znaleziono przesłanek.")
    if len(reasons) < 3:
        seen = ", ".join(f"{VIEW_LABEL.get(name, name)} {v.get('width')}×{v.get('height')}" for name, v in views.items())
        reasons.append(f"Stronę odczytano w przeglądarce na ekranach: {seen or 'brak'}; tekst ukryty w zwiniętych elementach też sprawdzono.")
    if len(reasons) < 3:
        reasons.append("Wynik pochodzi z reguł; przy każdym kryterium jest cytat i zrzut ekranu do samodzielnej oceny analityka.")
    case_id = capture.get("id", "")
    first_view = views.get("phone") or views.get("desktop") or {}
    evidence = []
    for row in rows:
        if not row.get("quote"):
            continue
        measurement = next(iter(row.get("measurements") or []), {})
        evidence.append({
            "id": _evidence_id(case_id, row["id"]), "kind": "screenshot" if measurement.get("screenshot") else "page",
            "role": "claim" if row["state"] == PREMISE else "context", "modality": "page", "method": "chromium-dom-block",
            "match": "verbatim", "text": row["quote"][:400], "textSha256": sha256(row["quote"].encode()).hexdigest(),
            "url": measurement.get("screenshot") or capture.get("url"), "domUrl": measurement.get("dom"),
            "sourceUrlAtTime": capture.get("url"), "bbox": measurement.get("bbox"), "viewport": measurement.get("viewport"),
            "criterionId": row["id"], "sourceVersion": market.get("manifestSha256"), "observedAt": capture.get("observedAt"),
            "available": True,
        })
    lead = next((e for e in evidence if e["criterionId"] == (ranked[0]["id"] if ranked else None)), None)
    gaps = [{"modality": name, "code": "blocks_truncated", "reason": "Strona ma więcej bloków tekstu niż limit pomiaru."}
            for name, v in views.items() if v.get("truncatedBlocks")]
    missing = [name for name in ("desktop", "phone") if name not in views]
    gaps += [{"modality": name, "code": "not_rendered", "reason": "Brak widoku."} for name in missing]
    coverage = {
        "scope": "page_dom", "state": "full" if not gaps else "partial" if views else "none",
        "modalities": {**{name: {"state": "observed", "blocks": len(v.get("blocks") or []), "width": v.get("width")} for name, v in views.items()},
                       "html": {"state": "hash_only", "sha256": market.get("htmlSha256")}},
        "gaps": gaps, "blocksConclusion": not views,
        "label": "Render strony na komputerze i telefonie, z tekstem zwiniętych elementów" if views else "Brak renderu",
    }
    firm = market.get("firm") or {}
    table = [{"id": row["id"], "label": row["label"], "state": row["state"], "evidence": row["evidence"], "basis": row["basis"],
              **({"applicability": row["applicability"]} if row.get("applicability") else {})} for row in rows]
    m2card = {
        "firm": {"name": firm.get("name"), "brand": firm.get("brand"), "registryId": firm.get("registryId"),
                 "entityType": firm.get("entityType"), "entityLabel": firm.get("entityLabel"), "category": firm.get("category"),
                 "sourceFile": firm.get("sourceFile")},
        "url": capture.get("url"), "observedAt": capture.get("observedAt"), "kind": market.get("kind"),
        "viewports": [f"{VIEW_LABEL.get(name, name)} {v.get('width')}×{v.get('height')}" for name, v in views.items()],
        "rows": table, "counts": dict(counts), "score": score, "threshold": threshold, "route": route, "reasons": reasons[:3],
        "rulesVersion": RULES_VERSION,
    }
    short = reasons[0] if route == "refer" else "W zbadanym zakresie nie ma przesłanek, które łącznie przekraczają próg skierowania."
    decision = {
        "route": route, "reason": short[:160], "reasons": reasons[:3],
        "moments": [{"start": None, "end": None, "label": f"{lead['viewport']}: {_q(lead['text'], 60)}", "deepLink": capture.get("url"),
                     "evidenceId": lead["id"]}] if lead else [],
        "requirement": {"module": "M2", "id": ranked[0]["id"], "label": ranked[0]["label"], "scope": "page_dom"} if ranked else None,
        "claim": {"text": lead["text"], "evidenceId": lead["id"]} if lead else None,
        "decidedBy": "rules", "version": RULES_VERSION, "queueEligible": route == "refer", "missing": [g["code"] for g in gaps],
    }
    suggestion = {"source": "rules", "criterionId": ranked[0]["id"] if ranked else None,
                  "state": {"refer": "review", "no_signal": "no_signal", "insufficient": "unavailable"}[route], "reason": short}
    if lead and route == "refer":
        suggestion["evidence"] = {"kind": lead["kind"], "text": lead["text"], "url": lead["url"], "domUrl": lead.get("domUrl")}
    for name in ("desktop", "phone"):
        v = views.get(name)
        if v:
            evidence.append({"id": f"m2:{case_id}:screen-{name}", "kind": "screenshot", "role": "context", "modality": "page",
                             "method": "chromium-first-screen", "text": f"Pierwszy ekran · {VIEW_LABEL[name]} {v['width']}×{v['height']}",
                             "url": v.get("screenshotUrl"), "sha256": v.get("screenshotSha256"), "domUrl": v.get("domUrl"),
                             "sourceUrlAtTime": capture.get("url"), "observedAt": capture.get("observedAt"), "available": True})
    summary = (f"Karta M2 · 19 kryteriów: przesłanki {counts[PREMISE]}, spełnione {counts[OK]}, nie dotyczy {counts[NA]}, "
               f"brak danych {counts[UNKNOWN]}. Wynik reguł {score}/100.")
    extra = {
        "checks": rows, "checkCounts": dict(counts), "rulesVersion": RULES_VERSION, "reviewSuggestion": suggestion,
        "reviewDecision": decision, "reviewScore": {"state": "computed", "value": score, "scale": "0-100",
                                                    "band": "strong" if score >= 60 else "moderate" if score >= THRESHOLD else "weak",
                                                    "meaning": "Suma wag przesłanek M2 (reguły, nie ocena prawna)",
                                                    "rulesVersion": RULES_VERSION, "modelVersion": None, "components": components},
        "coverage": coverage, "m2Card": m2card,
    }
    return score, summary, evidence, extra


def card(capture, threshold=THRESHOLD):
    from collectors.m2_market import material
    return build(capture, evaluate(material(capture)), threshold)
