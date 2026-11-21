"""Produce localized screening findings from observed captures; no legal verdicts."""
from collections import Counter
from functools import lru_cache
import hashlib
import json
import re

from .checks import marketing, excerpt, OBS, UNKNOWN
from .transcribe import MEDIA, ROOT, replay_file

SNAPSHOTS = ROOT / "data" / "probe-snapshots"
FIXTURES = ROOT / "fixtures" / "labeled"
RULESET = "investwatch-rules-pl-1.0"
PARTNER = (r"\bpartner(?:em)? (?:tego |naszego )?(?:programu|odcinka|materiału|kanału|filmu)\b"
           r"|\b(?:we współpracy z|płatna współpraca|współpraca reklamowa|materiał sponsorowany|"
           r"film sponsoruje|sponsorem (?:jest|odcinka)|naszym partnerem jest|reklama)\b")
REFERRAL = r"\bkod(?:em|u)? (?:rabatow\w*|polecaj\w*|promocyjn\w*)|link\w* (?:afiliacyjn\w*|partnersk\w*)"
BRANDS = r"\b(?:XTB|Aurora|eToro|Trading 212|BDM|DM BOŚ)\b"
DENIAL = r"\b(?:nie jest|nie była|bez|żadnej|brak) (?:to |żadnej )?(?:reklam\w*|współprac\w*|partner\w*|sponsor\w*)|\bnie (?:reklamuję|współpracuję)"
ADVICE = (r"portfel rekomendowany|rekomendacj\w* (?:dla ciebie|dla klienta|dopasowan\w*)|"
          r"dobior\w* (?:ci |dla ciebie |Państwu )?(?:konkretn\w* )?(?:akcj\w*|portfel|instrument\w*)|"
          r"politykę inwestycyjną zgodną z twoimi potrzebami")
NO_ADVICE = r"\bnie (?:dob(?:ier|ior)\w*|rekomenduj\w*|oferuj\w* rekomendacj\w*|udziel\w* (?:porad|rekomendacji))"


@lru_cache(maxsize=16)
def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def dom_views(url):
    archive = read_json(SNAPSHOTS / "2026-11-21-browser-files.json")
    return [view for view in archive["views"] if view["url"] == url]


def registry_snapshot(stem, ids):
    rows = read_json(SNAPSHOTS / "knf" / (stem + ".json"))
    entries = []
    for row in rows:
        if row["id"] not in ids:
            continue
        entry = {"id": row["id"], "name": row["name"], "category": row["subcategoryName"]}
        for field in row.get("attributes", []):
            if "na rzecz której działa agent" in field["name"]:
                entry["principal"] = field.get("value")
        entries.append(entry)
    category = 6 if stem == "knf_agenci_prawne" else 19
    return {"entries": entries, "checkedAt": "2026-11-21",
            "url": f"https://www.knf.gov.pl/api/podmioty-children?parentId={category}&type=COMPANY&pageSize=100",
            "status": "do wyjaśnienia", "sourceFile": f"data/probe-snapshots/knf/{stem}.json"}


def demo_captures():
    report = replay_file(MEDIA / "studio.mp4")
    captures = [dict(item) for item in read_json(FIXTURES / "showcase.json")]
    film = captures[0]
    film.update(segments=report["segments"], mediaSha256=report["sha256"], asrModel=report["model"])
    for cap in captures:
        if "registrySnapshot" in cap:
            cap["registry"] = registry_snapshot(cap.pop("registrySnapshot"), cap.pop("registryIds"))
        if cap.pop("archivedDom", False):
            cap["views"] = dom_views(cap["url"])
    return captures


def clause_relation(text):
    if re.search(DENIAL, text, re.I):
        return 12, "Autor zaprzecza współpracy", excerpt(text, DENIAL)
    for score, desc, pattern in [
        (94, "Deklaracja reklamy lub partnerstwa", PARTNER),
        (66, "Kod lub link polecający", REFERRAL),
        (24, "Wzmianka o marce", BRANDS),
    ]:
        quote = excerpt(text, pattern)
        if quote:
            return score, desc, quote
    return (12, "Brak jednoznacznego sygnału współpracy", text[:150]) if text else (0, "Brak treści do oceny", "")


def relation(text):
    clauses = re.split(r"(?<=[!?])\s+|(?<=\.)\s+(?=[A-ZĄĆĘŁŃÓŚŹŻ])|\n+|\bale\b", text)
    return max((clause_relation(clause) for clause in clauses), key=lambda result: result[0])


def m1(cap):
    text = cap.get("description") or ""
    ds, reason, quote = relation(text)
    evidence = []
    best = ds
    segments = cap.get("segments") or []
    audio_scores = [(seg, *relation(seg["text"])[:2]) for seg in segments]
    strong = [s for s in audio_scores if s[1] >= 60]
    displayed = strong or sorted(audio_scores, key=lambda s: s[1], reverse=True)[:1]
    for seg, score, label in displayed:
        start, end = seg["start"], seg["end"]
        ev = {"kind": "audio", "text": seg["text"], "start": start, "end": end}
        if cap.get("mediaUrl"):
            ev["url"] = f"{cap['mediaUrl']}#t={start},{end}"
        if "confidence" in seg:
            ev["confidence"] = seg["confidence"]
        evidence.append(ev)
        if score > best:
            best, reason = score, label
    if text:
        evidence.append({"kind": "description", "text": quote or text[:180], "url": cap.get("url")})
    audio_only = bool(text.strip() and strong and ds < 60 <= best)
    if audio_only:
        reason += " w nagraniu. Opis nie ujawnia tego sygnału."
    elif best >= 60:
        reason += ". Ustal warunki współpracy z firmą."
    else:
        reason += " w zbadanym zakresie."
    extra = {"descriptionScore": ds, "speechOnlySignal": audio_only}
    if segments:
        extra["modalityComparison"] = {"descriptionOnly": ds, "withAudio": best, "delta": best - ds}
    if not cap.get("brand"):
        source_quote = " ".join(e["text"] for e in evidence)
        match = re.search(BRANDS, source_quote, re.I)
        if match:
            extra["brand"] = match.group()
    return best, reason, evidence, extra


def m2(cap):
    checks = marketing(cap)
    counts = Counter(r["state"] for r in checks)
    severe = any(r["id"] in {"17", "18"} and r["state"] == OBS for r in checks)
    score = 88 if severe else min(80, 42 + 9 * counts[OBS]) if counts[OBS] else 20
    evidence = [{"kind": "description", "text": cap["description"][:220], "url": cap.get("url")}] if cap.get("description") else []
    for view in cap.get("views", []):
        evidence.append({"kind": "screenshot", "text": f"Pierwszy widok strony · {view['width']} × {view['height']} px",
                         "url": "/evidence/" + view["screenshotFile"], "sha256": view["screenshotHash"],
                         "domUrl": "/evidence/" + view["domExtractFile"]})
    return score, f"Katalog 19 kontroli. Obserwacje do przeglądu: {counts[OBS]}. Brak danych: {counts[UNKNOWN]}.", evidence, {"checks": checks, "checkCounts": dict(counts)}


def m3(cap):
    text = cap.get("description") or ""
    quote = excerpt(text, ADVICE)
    registry = cap.get("registry", {})
    evidence = [{"kind": "description", "text": quote or text[:220], "url": cap.get("url")}] if text else []
    for entry in registry.get("entries", []):
        evidence.append({"kind": "registry", "text": entry["name"] + " · ID " + str(entry["id"]) +
                         (" · " + entry["principal"] if entry.get("principal") else ""),
                         "url": registry["url"], "observedAt": registry["checkedAt"]})
    if len(registry.get("entries", [])) > 1:
        return 52, "Dwa podmioty o podobnej nazwie. Ustal operatora i zakres czynności agenta.", evidence, {"registry": registry}
    affirmative = any(re.search(ADVICE, clause, re.I) and not re.search(NO_ADVICE, clause, re.I)
                      for clause in re.split(r"[.!?\n]|\bale\b", text))
    if re.search(NO_ADVICE, text, re.I) and not affirmative:
        return 15, "Autor wyłącza indywidualne rekomendacje. Zachowaj zakres cytatu.", evidence, {}
    if quote:
        if registry.get("entries"):
            return 58, "Oferta spersonalizowana. Potwierdzono tożsamość w wykazie, zakres usługi wymaga weryfikacji.", evidence, {"registry": registry}
        return 83, "Oferta dopasowania portfela. Ustal podmiot i sprawdź zakres zezwolenia.", evidence, {"registryStatus": "do wyjaśnienia"}
    return 18 if text else 0, "W dostępnym fragmencie brak jednoznacznej oferty indywidualnego doboru instrumentów.", evidence, {}


def analyze(capture):
    module = capture.get("module", "M1")
    score, summary, evidence, extra = {"M1": m1, "M2": m2, "M3": m3}[module](capture)
    finding = {k: capture[k] for k in (
        "id", "title", "module", "platform", "creatorId", "creatorName", "url", "brand", "provenance",
        "publishedAt", "observedAt", "mediaUrl", "contractDemo", "asrModel", "mediaSha256", "mode",
        "sourceId", "campaignId", "version", "description", "segments", "registry", "synthetic",
    ) if k in capture}
    finding.update({"module": module, "score": score, "summary": summary, "evidence": evidence,
                    "rulesVersion": RULESET, **extra})
    return finding


def calibration(threshold=60):
    if not 0 <= threshold <= 100:
        raise ValueError("Próg musi mieścić się w zakresie 0–100.")
    dataset = read_json(FIXTURES / "calibration.json")
    counts = dict.fromkeys(("tp", "fp", "tn", "fn"), 0)
    examples = []
    cases = {cap["id"]: cap for cap in demo_captures()}
    for row in dataset:
        cap = dict(row["capture"])
        if "registryExample" in cap:
            cap["registry"] = cases[cap["registryExample"]]["registry"]
        if cap.get("savedDom"):
            cap["views"] = dom_views(cap["url"])
        score = analyze(cap)["score"]
        predicted, expected = score >= threshold, row["expected"]
        outcome = ("t" if predicted == expected else "f") + ("p" if predicted else "n")
        counts[outcome] += 1
        examples.append({"id": cap["id"], "title": cap["title"], "module": cap["module"], "score": score,
                         "expected": expected, "outcome": outcome, "origin": row["origin"], "url": cap.get("url"),
                         "text": cap["description"]})
    real = sum(row["origin"] == "publiczny" for row in dataset)
    dataset_id = hashlib.sha256((FIXTURES / "calibration.json").read_bytes()).hexdigest()[:12]
    return {"datasetId": dataset_id, "threshold": threshold, **counts, "n": len(dataset),
            "publicExamples": real, "syntheticExamples": len(dataset)-real,
            "cost": counts["fp"] + 2*counts["fn"], "examples": examples,
            "errors": [e for e in examples if e["outcome"].startswith("f")],
            "description": "Próba ilustracyjna. Etykiety robocze autora reguł; brak niezależnej walidacji na przyszłym ruchu."}
