"""Produce localized screening findings from observed captures; no legal verdicts."""
from collections import Counter
from functools import lru_cache
import hashlib
import json
import re
from urllib.parse import urlsplit

from .checks import marketing, excerpt, OBS, UNKNOWN
from .transcribe import MEDIA, ROOT, replay_file

SNAPSHOTS = ROOT / "data" / "probe-snapshots"
FIXTURES = ROOT / "fixtures" / "labeled"
RULESET = "investwatch-rules-pl-1.2"
PARTNER = (
    r"\b(?:partnerem (?:(?:tego|naszego) )?(?:programu|odcinka|materiału|kanału|filmu) (?:jest|został\w*)"
    r"|film sponsoruje|sponsorem (?:jest|odcinka jest)|naszym partnerem jest)\b"
    r"|\b(?:powstał\w*|przygotowano|zrealizowano|nagrano) we współpracy z\b"
    r"|^\s*we współpracy z\b"
    r"|^\s*(?:partner|sponsor) (?:odcinka|programu|materiału|filmu)\s*:\s*(?=[\w„])"
)
DISCLOSURE_LABEL = (
    r"(?<![\w/])#(?:reklama|wsp[oó][łl]praca(?:reklamowa)?|płatnawspółpraca|materiałreklamowy|ad|sponsored)\b"
    r"|^\s*[\[(]?\s*(?:(?:to (?:jest )?|niniejszy )?materiał (?:reklamowy|sponsorowany)"
    r"|płatna współpraca|współpraca reklamowa|to (?:jest )?reklama)\b"
    r"|^\s*[\[(]?\s*reklama\s*(?:$|[\]).:–-])"
)
REFERRAL = r"\bkod(?:em|u)? (?:rabatow\w*|polecaj\w*|promocyjn\w*)|link\w* (?:afiliacyjn\w*|partnersk\w*)"
BRANDS = r"\b(?:XTB|Aurora|eToro|Trading 212|BDM|DM BOŚ)\b"
CTA = (r"\b(?:pobierz (?:aplikację|program)|otwórz (?:konto|rachunek)|załóż (?:konto|rachunek)"
       r"|zarejestruj się|wybierz ofertę|kup teraz|odbierz bonus|skorzystaj z oferty)\b")
SIGNALS = {94: "declaration", 74: "brand_cta", 66: "affiliate_code", 24: "neutral_mention"}
CLAUSE_SPLIT = re.compile(r"(?<=[.!?])\s+|[\r\n]+|\b(?:ale|jednak|natomiast)\b", re.I)
DENIAL = re.compile(
    r"\b(?:nie jest|nie była|bez|żadnej|brak) (?:to |żadnej )?"
    r"(?:reklam\w*|współprac\w*|partner\w*|sponsor\w*|materiał\w* (?:reklamow\w*|sponsorowan\w*))"
    r"|\bnie (?:reklamuję|współpracuję)\b"
    r"|\b(?:materiał|odcinek|film) nie (?:powstał\w*|został\w*) we współpracy\b",
    re.I,
)
ACTION_DENIAL = re.compile(
    r"\bnie (?:klikaj\w*|korzystaj\w*|używaj\w*|użyj|pobieraj\w*|otwieraj\w*|zakładaj\w*|rejestruj się|polecam)\b",
    re.I,
)
FRAUD_CONTEXT = re.compile(
    r"\b(?:podszywa\w*|oszust\w*|wyłudz\w*|scam\w*|"
    r"fałszyw\w*\s+(?:reklam\w*|ofert\w*|link\w*))\b",
    re.I,
)
FRAUD_REFERENCE = re.compile(
    r"^\s*(?:to (?:jest )?(?:oszustwo|próba wyłudzenia)|(?:ta oferta|ta reklama|ten link) (?:jest )?fałszyw\w*)\b",
    re.I,
)
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
            if field["name"] == "Data zezwolenia":
                entry["authorizationDate"] = field.get("value")
            if field["name"] == "Zakres działalności":
                entry["scopeCodes"] = field.get("value")
                entry["scopeLegend"] = field.get("legend_name")
                if stem == "knf_domy_maklerskie" and "5" in (field.get("value") or "").replace(" ", "").split(","):
                    entry["scopeCode5"] = {"text": "doradztwo inwestycyjne", "checkedAt": "2026-11-21",
                        "url": "https://www.knf.gov.pl/knf/pl/komponenty/img/zakres_dzialalnosci.pdf"}
        entries.append(entry)
    category = 6 if stem == "knf_agenci_prawne" else 19
    return {"entries": entries, "checkedAt": "2026-11-21",
            "url": f"https://www.knf.gov.pl/api/podmioty-children?parentId={category}&type=COMPANY&pageSize=100",
            "status": "do wyjaśnienia", "sourceFile": f"data/probe-snapshots/knf/{stem}.json"}


def demo_captures():
    captures = [dict(item) for item in read_json(FIXTURES / "showcase.json")]
    for cap in captures:
        if "sampleFile" in cap:
            report = replay_file(MEDIA / cap.pop("sampleFile"))
            cap.update(segments=report["segments"], mediaSha256=report["sha256"], asrModel=report["model"])
        if "registrySnapshot" in cap:
            cap["registry"] = registry_snapshot(cap.pop("registrySnapshot"), cap.pop("registryIds"))
        if cap.pop("archivedDom", False):
            cap["views"] = dom_views(cap["url"])
    return captures


def promotion_clauses(text):
    clauses = [part.strip() for part in CLAUSE_SPLIT.split(text) if part.strip()]
    for index, clause in enumerate(clauses):
        next_clause = clauses[index + 1] if index + 1 < len(clauses) else ""
        warning = FRAUD_CONTEXT.search(clause) or FRAUD_REFERENCE.search(next_clause)
        denial = DENIAL.search(clause)
        yield clause, denial, bool(warning or ACTION_DENIAL.search(clause) or clause.endswith("?"))


def brand_pattern(brand):
    if isinstance(brand, str) and brand:
        return BRANDS + r"|(?<!\w)" + re.escape(brand) + r"(?!\w)"
    return BRANDS


def clause_relation(text, brands, denial, blocked):
    if denial:
        return 12, "Autor zaprzecza współpracy", excerpt(text, DENIAL.pattern)
    mentions = list(re.finditer(brands, text, re.I))
    if not blocked:
        sponsor = excerpt(text, PARTNER)
        if sponsor:
            return 94, "Deklaracja współpracy lub partnerstwa", sponsor
        for cta in re.finditer(CTA, text, re.I):
            for mention in mentions:
                if abs(mention.start() - cta.start()) <= 90:
                    start = min(mention.start(), cta.start())
                    end = max(mention.end(), cta.end())
                    return 74, "Zachęta do działania przy wzmiance o marce", text[max(0, start - 15):end + 60]
        code = excerpt(text, REFERRAL)
        if code:
            return 66, "Kod lub link polecający", code
    if mentions:
        return 24, "Wzmianka o marce", excerpt(text, brands)
    return 12, "Brak jednoznacznego sygnału współpracy", text[:150]


def relation(text, brand=None):
    brands = brand_pattern(brand)
    return max(
        (clause_relation(clause, brands, denial, blocked) for clause, denial, blocked in promotion_clauses(text)),
        key=lambda result: result[0],
        default=(0, "Brak treści do oceny", ""),
    )


def find_disclosure(text, brand):
    brands = brand_pattern(brand)
    label = None
    for clause, denial, blocked in promotion_clauses(text):
        if denial or blocked:
            continue
        declaration = re.search(PARTNER, clause, re.I)
        if declaration:
            named = re.match(
                rf'\s*[:„"«]?\s*(?:(?:firma|marka|dom maklerski)\s+)?(?P<name>{brands})',
                clause[declaration.end():], re.I,
            )
            return "declaration", excerpt(clause, PARTNER), named["name"] if named else None
        if label is None:
            label = excerpt(clause, DISCLOSURE_LABEL)
    return ("label", label, None) if label else (None, None, None)


def m1(cap):
    text = cap.get("description") or ""
    ds, reason, quote = relation(text, cap.get("brand"))
    evidence = []
    best = ds
    segments = cap.get("segments") or []
    audio_scores = [(seg, *relation(seg["text"], cap.get("brand"))[:2]) for seg in segments]
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
    if text.strip():
        evidence.append({"kind": "description", "text": quote or text[:180], "url": cap.get("url")})
    disclosure, disclosure_quote, disclosed_brand = find_disclosure(text, cap.get("brand"))
    if disclosure_quote and (not quote or disclosure_quote not in quote):
        evidence.append({"kind": "description", "text": disclosure_quote, "url": cap.get("url")})
    audio_only = bool(text.strip() and strong and ds < 60 <= best)
    if audio_only:
        reason += " w nagraniu. Opis nie ujawnia tego sygnału."
    elif best >= 60:
        reason += ". Ustal warunki współpracy z firmą."
    else:
        reason += " w zbadanym zakresie."
    extra = {"descriptionScore": ds, "speechOnlySignal": audio_only}
    extra["signalType"] = SIGNALS.get(best, "none")
    extra["descriptionDisclosureStatus"] = "unavailable" if not text.strip() else "observed" if disclosure else "not_found"
    if disclosure:
        extra["descriptionDisclosureType"] = disclosure
    if disclosed_brand:
        extra["descriptionDisclosedBrand"] = disclosed_brand
    if disclosure == "label":
        if best < 60:
            extra["signalType"] = "disclosure_label"
            reason = "W zbadanym opisie występuje etykieta reklamowa. Ustal charakter powiązania."
        else:
            reason += " W opisie występuje etykieta reklamowa."
    extra["possibleUndisclosedPromotion"] = best in (74, 66) and extra["descriptionDisclosureStatus"] == "not_found"
    if extra["possibleUndisclosedPromotion"]:
        reason = ("Zachęta do działania przy wzmiance o marce" if best == 74 else "Kod lub link polecający")
        reason += " w nagraniu." if audio_only else "."
        reason += " W zbadanym opisie nie wykryto oznaczenia. Sprawdź charakter relacji."
    if segments:
        extra["modalityComparison"] = {"descriptionOnly": ds, "withAudio": best, "delta": best - ds}
    if not cap.get("brand"):
        inferred_brand = disclosed_brand
        if not inferred_brand and best == 94:
            for seg, score, _ in displayed:
                if score == 94:
                    _, _, inferred_brand = find_disclosure(seg["text"], None)
                    if inferred_brand:
                        break
        elif not inferred_brand:
            source_quote = " ".join(e["text"] for e in evidence)
            match = re.search(BRANDS, source_quote, re.I)
            inferred_brand = match.group() if match else None
        if inferred_brand:
            extra["brand"] = inferred_brand
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
    for view in cap.get("m2Views", []):
        if view["state"] != "initial":
            continue
        evidence.append({"kind": "screenshot", "text": f"Pierwszy widok strony · {view['width']} × {view['height']} px",
                         "url": view["url"], "sha256": view["screenshotHash"], "domUrl": view["domUrl"],
                         "domSha256": view["domHash"], "contentHash": cap["m2EvidenceRevision"]})
    from .m2_evidence import marketing_review_suggestion
    extra = {
        "checks": checks, "checkCounts": dict(counts), "rulesVersion": "investwatch-m2-rendered-1",
        "reviewSuggestion": marketing_review_suggestion(checks),
    }
    return score, f"Katalog 19 kontroli. Obserwacje do przeglądu: {counts[OBS]}. Brak danych: {counts[UNKNOWN]}.", evidence, extra


def m3(cap):
    text = cap.get("description") or ""
    quote = excerpt(text, ADVICE)
    registry = cap.get("registry", {})
    identity = cap.get("identityEvidence", {})
    prov = cap.get("provenance") or {}
    if not isinstance(prov, dict):
        prov = {}
    source = cap.get("url") or ""
    try:
        host = urlsplit(source).hostname
    except ValueError:
        host = None
    # Only join the named KNF row when this exact acquired page carries the
    # matching operator and identifiers, with no conflicting KRS on the page.
    candidates = identity.get("krsCandidates") or []
    verified_identity = bool(
        cap.get("materialType") == "public_html_text" and host == "bossa.pl"
        and prov.get("sourceUrl") == source and prov.get("discoveredFrom") == "https://bossa.pl/"
        and prov.get("responseSha256") and identity.get("url") == source
        and identity.get("observedAt") == cap.get("observedAt")
        and identity.get("name", "").casefold() == "dom maklerski banku ochrony środowiska spółka akcyjna".casefold()
        and re.sub(r"\D", "", identity.get("krs", "")) == "0000048901"
        and re.sub(r"\D", "", identity.get("nip", "")) == "5261026828"
        and candidates and set(candidates) == {"0000048901"}
    )
    if verified_identity:
        registry = registry_snapshot("knf_domy_maklerskie", [8353437])
        registry["identityStatus"] = "zgodność identyfikatorów w źródłach"
        registry["scopeStatus"] = "kod 5: doradztwo inwestycyjne w stanie wykazu z 2026-11-21"
    evidence = [{"kind": "description", "text": quote or text[:220], "url": cap.get("url")}] if text else []
    # These are independent cues, not a legal conclusion or a claim that the
    # service and registry entry belong to the same legal person.
    cues = [
        ("personalizacja", r"profil\w* inwestycyjn\w* klient\w*|dla (?:ciebie|klienta|Państwa)|dopasowan\w*|zgodn\w* z twoimi potrzebami"),
        ("instrument", r"\b(?:papier\w* wartościow\w*|akcj\w*|obligacj\w*|instrument\w*|fundusz\w*)\b"),
        ("czynność", r"portfel\w* rekomendowan\w*|rekomendacj\w*|dob(?:ier|ior)\w*|wyselekcjonowan\w* list\w*"),
    ]
    checks = []
    for label, pattern in cues:
        affirmative_parts = [clause for clause in re.split(r"[.!?\n]|\bale\b", text, flags=re.I)
                             if not re.search(NO_ADVICE, clause, re.I)]
        cue = next((excerpt(clause, pattern) for clause in affirmative_parts if re.search(pattern, clause, re.I)), "")
        checks.append({"id": label, "label": label.capitalize(), "state": OBS if cue else UNKNOWN,
                       "evidence": cue or "Brak jednoznacznego fragmentu w dostępnym tekście.", "url": cap.get("url")})
        if cue and not any(item["text"] == cue for item in evidence):
            evidence.append({"kind": "description", "text": cue, "url": cap.get("url")})
    if identity.get("text"):
        evidence.append({"kind": "identity", **identity})
    elif verified_identity:
        for key in ("name", "krs", "nip"):
            evidence.append({"kind": "identity", "text": identity[key], "url": source,
                             "observedAt": identity["observedAt"]})
        evidence.append({"kind": "identity", "text": "Domu Maklerskiego Banku Ochrony Środowiska SA z siedzibą w Warszawie – nr KRS 0000048901", "observedAt": "2024-03-13",
                         "url": "https://www.knf.gov.pl/?articleId=88304&p_id=18"})
    for entry in registry.get("entries", []):
        evidence.append({"kind": "registry", "text": entry["name"] + " · ID " + str(entry["id"]) +
                         (" · " + entry["principal"] if entry.get("principal") else "") +
                         (" · data zezwolenia: " + entry["authorizationDate"] if entry.get("authorizationDate") else "") +
                         (" · kody zakresu: " + entry["scopeCodes"] if entry.get("scopeCodes") else ""),
                         "url": registry["url"], "observedAt": registry["checkedAt"]})
        if entry.get("scopeCode5"):
            code = entry["scopeCode5"]
            evidence.append({"kind": "registry", "text": "Legenda KNF, pozycja 5: " + code["text"],
                             "url": code["url"], "observedAt": code["checkedAt"]})
    extra = {"checks": checks, "registryStatus": "zgodność w stanie archiwalnym" if verified_identity else "do wyjaśnienia"}
    if registry:
        extra["registry"] = registry
    if len(registry.get("entries", [])) > 1:
        return 52, "Podmioty o podobnej nazwie. Ustal operatora i zakres czynności agenta.", evidence, extra
    affirmative = any(re.search(ADVICE, clause, re.I) and not re.search(NO_ADVICE, clause, re.I)
                      for clause in re.split(r"[.!?\n]|\bale\b", text))
    if re.search(NO_ADVICE, text, re.I) and not affirmative:
        return 15, "Autor wyłącza indywidualne rekomendacje. Zachowaj zakres cytatu.", evidence, extra
    if quote:
        if verified_identity:
            return 58, "Sygnał oferty spersonalizowanej. Identyfikatory zgodne; kod 5 w datowanym wykazie oznacza doradztwo inwestycyjne. Zweryfikuj aktualny stan.", evidence, extra
        if registry.get("entries"):
            return 58, "Sygnał oferty spersonalizowanej. Wpis w wykazie jest kandydatem; potwierdź tożsamość i zakres zezwolenia.", evidence, extra
        return 83, "Sygnał oferty dopasowania portfela. Ustal podmiot i sprawdź zakres zezwolenia.", evidence, extra
    return 18 if text else 0, "W dostępnym fragmencie brak jednoznacznej oferty indywidualnego doboru instrumentów.", evidence, extra


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
    modules = {}
    for module in ("M1", "M2", "M3"):
        selected = [row for row in examples if row["module"] == module]
        per_counts = {key: sum(row["outcome"] == key for row in selected) for key in counts}
        modules[module] = {"n": len(selected), **per_counts,
                           "publicExamples": sum(row["origin"] == "publiczny" for row in selected),
                           "syntheticExamples": sum(row["origin"] == "syntetyczny" for row in selected),
                           "cost": per_counts["fp"] + 2 * per_counts["fn"]}
    return {"datasetId": dataset_id, "threshold": threshold, **counts, "n": len(dataset),
            "publicExamples": real, "syntheticExamples": len(dataset)-real,
            "cost": counts["fp"] + 2*counts["fn"], "examples": examples,
            "modules": modules, "labelSource": "Robocze etykiety autora reguł; brak niezależnego oznaczania.",
            "evaluationStatus": "illustrative_not_held_out",
            "errors": [e for e in examples if e["outcome"].startswith("f")],
            "description": "Próba ilustracyjna. Etykiety robocze autora reguł; brak niezależnej walidacji na przyszłym ruchu."}
