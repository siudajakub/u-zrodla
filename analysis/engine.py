"""Produce localized screening findings from observed captures; no legal verdicts."""
from collections import Counter
from functools import lru_cache
import hashlib
import json
import os
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


INSTRUMENT_WORDS = re.compile(
    r"(?i)\b(pieniąd\w*|akcj\w*|etf\w*|obligacj\w*|fundusz\w*|cfd\w*|forex|fx|kryptowalut\w*|krypto|bitcoin\w*|inwest\w*|giełd\w*|maklersk\w*|"
    r"indeks\w*|surowc\w*|złot\w*|dywidend\w*|portfel\w*|lokat\w*|oszczędz\w*|zysk\w*|stop\w* zwrotu|rachunk\w* (?:inwestycyjn|maklersk)\w*|"
    r"trading\w*|handel\w*|dźwigni\w*|kapita\w*|emerytur\w*|ike|ikze|ppk|walut\w*|instrument\w*|papier\w* wartościow\w*)\b")


def m2_scope(cap):
    """Membership of a social post or ad of M2 in the Polish queues (decision of 21 XI): the author is a firm of the
    register (a), the text is Polish (b, the language heuristic of the YouTube adapter) and it concerns an instrument or
    a service of the offer, or carries a claim of benefit or a risk warning (c). Anything else is `no_signal`, only in `all`."""
    text = " ".join(str(cap.get(k) or "") for k in ("title", "description", "adBody"))
    signals = cap.get("textSignals") if isinstance(cap.get("textSignals"), dict) else {}
    if not (cap.get("firmRelation") or cap.get("firmMentions")):
        return {"belongs": False, "code": "no_registry_firm", "label": "autor spoza rejestru firm"}
    from collectors.youtube import detect_language
    language, _ = detect_language([], cap.get("title"), cap.get("description") or cap.get("adBody"))
    if language == "other":
        return {"belongs": False, "code": "other_market", "label": "inny rynek lub język: poza kolejkami PL", "language": language}
    if not (INSTRUMENT_WORDS.search(text) or signals.get("benefitClaim") or signals.get("riskWarningInText")):
        return {"belongs": False, "code": "not_investment", "label": "post firmy bez treści o instrumentach lub usłudze inwestycyjnej",
                "language": language}
    return {"belongs": True, "code": "in_scope", "label": "polski materiał firmy z rejestru o instrumencie lub usłudze", "language": language}


def m2(cap):
    if cap.get("m2Market"):  # a rendered market page (lane E): 19 criteria, card, reasons and screenshots
        from .m2_card import card
        score, summary, evidence, extra = card(cap)
        # Code that predates the card counts "obserwacja"; a premise is the same kind of observation.
        extra["checkCounts"] = {**extra["checkCounts"], OBS: extra["checkCounts"].get("przesłanka", 0)}
        return score, summary, evidence, extra
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
    if cap.get("adId") or (cap["provenance"].get("scope") if isinstance(cap.get("provenance"), dict) else None) == "meta_ad_library_text":
        # An ad of the Meta Ad Library is read as text: no render, no geometry, no image or video.
        extra["coverage"] = {"scope": "ad_text", "state": "partial", "modalities": {"adText": {"state": "full"},
                             "render": {"state": "not_collected"}, "media": {"state": "not_collected"}},
                             "gaps": [{"modality": "render", "code": "not_collected", "reason": "obrazu, wideo i układu reklamy nie analizowano"}],
                             "blocksConclusion": False, "label": "Zbadano: tylko tekst reklamy, bez renderu"}
    if cap.get("platform") not in (None, "web"):
        scope = m2_scope(cap)
        extra["m2Scope"] = scope
        if not scope["belongs"]:
            extra["reviewSuggestion"] = {"source": "rules", "criterionId": None, "state": "no_signal", "reason": scope["label"].capitalize() + "."}
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


# --- M3: advisory offers (lane F). One decision per firm, taken in one place: analysis.offers.analyze_entity ---------
M3_STRONG = {"present", "catalog", "poland"}
M3_PARTIAL = {"service_only", "weak", "generic"}
M3_AXES = (("action", "Czynność"), ("personalisation", "Personalizacja"), ("instrument", "Instrument"), ("market", "Rynek"))
M3_ROUTE_STATE = {"refer": "review", "complete": "uncertain", "no_signal": "no_signal"}
M3_LICENSED = {"authorized_advice": "podmiot uprawniony", "investment_firm_agent": "agent firmy inwestycyjnej"}
M3_MEANING = "Siła sygnału reguł M3 w skali 0–100: ile przesłanek do sprawdzenia widać w tekście. Nie jest oceną prawną."


def m3_rules():
    from . import offers
    return offers.RULES_VERSION


@lru_cache(maxsize=1)
def _offer_index():
    from . import offers
    return offers.load_registers()


def m3_entity(cap):
    """The firm behind a M3 capture: all saved pages (m3Pages) or, for a single-page capture, that page."""
    prov = cap.get("provenance") if isinstance(cap.get("provenance"), dict) else {}
    url = cap.get("url") or ""
    domain = (cap.get("m3Entity") or "").removeprefix("m3:") or re.sub(r"^www\.", "", urlsplit(url).hostname or "")
    if cap.get("m3Pages"):
        pages = [{"url": p["url"], "observedAt": p.get("observedAt"), "sha256": p.get("sha256"), "text": p.get("text") or "",
                  "textSha256": p.get("textSha256"), "identityText": p.get("identityText") or "", "role": p.get("role")}
                 for p in cap["m3Pages"]]
    else:
        ident = cap.get("identityEvidence") if isinstance(cap.get("identityEvidence"), dict) else {}
        footer = " ".join(str(ident[k]) for k in ("name", "krs", "nip") if ident.get(k))
        text = cap.get("description") or ""
        pages = [{"url": url, "observedAt": cap.get("observedAt"), "sha256": prov.get("responseSha256"), "text": text,
                  "textSha256": hashlib.sha256(text.encode()).hexdigest(), "identityText": footer, "role": "offer"}]
    return {"id": cap.get("id") or url, "domain": domain, "label": cap.get("brand") or cap.get("title"),
            "discoveredVia": prov.get("discoveredFrom") or cap.get("discoveredVia"), "pages": pages}


def _loc(item, page_urls):
    loc = item.get("locator") or {}
    return {"field": "pageText", **{k: loc.get(k) for k in ("url", "line", "start", "end", "textSha256")}}


def _offer_evidence(case_id, analysis):
    """Evidence items with role (claim/context/counter), one per quote, each with the locator and the URL of its own page."""
    items, moments = [], []
    for key, label in M3_AXES:
        axis = analysis["axes"][key]
        strong = axis["status"] in M3_STRONG
        for number, quote in enumerate(axis["evidence"][:2 if key != "market" else 1], 1):
            loc = _loc(quote, None)
            item = {"id": f"m3:{case_id}:{key}:{number}", "kind": "page", "role": "claim" if strong else "context",
                    "modality": "page", "method": "html-text", "match": "verbatim", "text": quote["quote"],
                    "textSha256": hashlib.sha256(quote["quote"].encode()).hexdigest(), "url": loc["url"], "sourceUrlAtTime": loc["url"],
                    "locator": loc, "criterionId": key, "label": label, "observedAt": None, "available": bool(loc["url"])}
            items.append(item)
            if strong and number == 1:
                moments.append({"start": None, "end": None, "label": f"{label}: {_q(quote['quote'], 70)}", "deepLink": loc["url"],
                                "evidenceId": item["id"], "locator": loc, "kind": "text", "url": loc["url"], "quote": quote["quote"]})
    counters = []
    for number, quote in enumerate(analysis.get("counterEvidence") or [], 1):
        loc = _loc(quote, None)
        counter = {"id": f"m3:{case_id}:counter:{number}", "kind": "page", "role": "counter", "modality": "page",
                   "method": "html-text", "match": "verbatim", "text": quote["quote"], "counterKind": quote.get("kind"),
                   "textSha256": hashlib.sha256(quote["quote"].encode()).hexdigest(), "url": loc["url"], "sourceUrlAtTime": loc["url"],
                   "locator": loc, "available": bool(loc["url"])}
        counters.append(counter)
    return items, counters, moments


def _q(text, limit):
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"


def _offer_checks(analysis):
    rows = []
    for key, label in M3_AXES:
        axis = analysis["axes"][key]
        status = axis["status"]
        state = ("przesłanka" if status in M3_STRONG else "częściowo" if status in M3_PARTIAL
                 else "poza katalogiem" if status == "outside_only" else "brak danych")
        quote = axis["evidence"][0] if axis["evidence"] else None
        rows.append({"id": key, "label": label, "state": state, "axisStatus": status,
                     "evidence": quote["quote"] if quote else "Brak jednoznacznego fragmentu w dostępnym tekście.",
                     "url": _loc(quote, None)["url"] if quote else None, "locator": _loc(quote, None) if quote else None,
                     "counter": [c["quote"] for c in axis.get("counter") or []][:2]})
    return rows


def _offer_complete_reason(analysis):
    state = analysis["identity"]["state"]
    if state in ("name_collision", "registry_error", "no_identity") and any("tożsamo" in m or "operator" in m
                                                                             for m in analysis["missing"] + [analysis["summary"]]):
        return "identity_unresolved"
    return "market_unknown" if analysis["axes"]["market"]["status"] != "poland" else "axes_incomplete"


def _offers_view(capture, finding):
    """Add the v2 fields to a M3 finding: the same shape as M1 (reviewDecision with reasons, moments and missing,
    reviewScore, axes table, identity, counterEvidence, coverage)."""
    from . import offers
    entity = m3_entity(capture)
    analysis = offers.analyze_entity(entity, _offer_index())
    case_id = capture.get("id") or entity["id"]
    evidence, counters, moments = _offer_evidence(case_id, analysis)
    identity = analysis["identity"]
    state = identity["state"]
    badge = M3_LICENSED.get(state)
    route = analysis["route"]
    cues = {"currency": "waluta PLN", "poland": "odniesienie do Polski", "pl_domain": "domena .pl", "polish_text": "tekst po polsku"}
    reasons = [re.sub(r"\b(currency|poland|pl_domain|polish_text)\b", lambda m: cues[m.group(1)], r)
               for r in analysis["reasons"]] or [analysis["summary"]]
    pages = analysis["pages"]
    read = len(pages)
    knf_warning = {"state": "found" if identity["warning"] else "none", "entries": identity["warning"],
                   "checkedAt": identity["checkedAt"]}
    missing = list(analysis["missing"])
    decision = {"route": route, "reason": analysis["summary"][:160], "reasons": reasons[:5],
                "moments": moments if route in ("refer", "complete") else [],
                "completeReason": _offer_complete_reason(analysis) if route == "complete" else None,
                "requirement": None, "claim": None, "alternative": None, "missing": missing,
                "decidedBy": "rules", "version": offers.RULES_VERSION, "queueEligible": route == "refer",
                "wording": analysis["wording"]}
    value = analysis["signalPoints"]
    score = {"state": "computed", "value": value, "scale": "0-100",
             "band": "strong" if value >= 75 else "moderate" if value >= 60 else "weak", "meaning": M3_MEANING,
             "notComputableReason": None, "rulesVersion": offers.RULES_VERSION, "modelVersion": None, "components": []}
    gaps = [{"modality": "render", "code": "not_collected", "reason": "strony odczytano jako tekst HTML; układu i obrazów nie badano"}]
    if read < 2:
        gaps.append({"modality": "pages", "code": "one_page", "reason": "odczytano jedną podstronę"})
    coverage = {"scope": "public_html_text", "state": "partial",
                "modalities": {"pageText": {"state": "full", "pages": read}, "render": {"state": "not_collected"},
                               "media": {"state": "not_collected"},
                               "registers": {"state": "checked" if not identity["registerFailures"] else "partial",
                                             "reviewed": identity["reviewedRegisters"], "checkedAt": identity["checkedAt"]}},
                "gaps": gaps, "blocksConclusion": False,
                "label": f"Zbadano: tekst {read} {'podstrony' if read in (2, 3, 4) else 'podstron' if read != 1 else 'podstrony'} firmy "
                         f"i {len(identity['reviewedRegisters'])} wykazów KNF z {identity['checkedAt']}; bez renderu i multimediów"}
    offer = {"entityId": analysis["entityId"], "name": analysis["name"], "domain": analysis["domain"], "pages": pages,
             "paidOffer": analysis["paidOffer"], "formAndInitiative": analysis["formAndInitiative"],
             "rulesVersion": offers.RULES_VERSION, "wording": analysis["wording"]}
    suggestion = {"source": "rules", "version": offers.RULES_VERSION, "state": M3_ROUTE_STATE[route], "reason": analysis["summary"]}
    lead = next((e for e in evidence if e["role"] == "claim"), None)
    if lead and route == "refer":
        suggestion["evidence"] = {"kind": "description", "text": lead["text"], "url": lead["url"]}
    if not capture.get("m3Pages"):
        # A single-page capture of the earlier demo (bossa.pl, FinanceWell, the study room): its v1 score, summary,
        # checks and review hint stay as they were (the T21 queue golden); it only gains the v2 fields below.
        keep = {k: finding[k] for k in ("score", "summary", "rulesVersion", "checks") if k in finding}
        keep["registryStatus"] = finding.get("registryStatus")
    else:
        keep = {"score": value, "summary": analysis["summary"], "rulesVersion": offers.RULES_VERSION, "reviewSuggestion": suggestion,
                "checks": _offer_checks(analysis)}
    finding.update({
        **keep, "axes": analysis["axes"], "offer": offer, "offerChecks": _offer_checks(analysis),
        "identity": {**identity, "licensed": badge is not None, "badge": badge, "knfWarning": knf_warning},
        "reviewDecision": decision, "reviewScore": score, "counterEvidence": counters, "coverage": coverage,
        "evidence": [*finding["evidence"], *evidence, *counters],
    })


# Fields of the D qualification. In shadow mode (step S5) they are computed and stored beside the
# case, while the queue, `score`, `reviewSuggestion` and `high_risk` keep following rules_1_2.
SHADOW_KEYS = ("reviewDecision", "reviewScore", "adRelationship", "relationships", "adRegistry", "premises",
               "counterEvidence", "coverage", "variants", "analysisVersion", "priority")
ANALYSIS_SCHEMA = 2
ACTIVE_VARIANT = "rules_1_2"  # set by the worker from the qualification settings before it analyses
DEFAULT_THRESHOLD = 60  # N2: the API applies the threshold, qualify only says refer or not
ROUTE_OF_SUGGESTION = {"review": "refer", "uncertain": "complete", "no_signal": "no_signal", "unavailable": "insufficient"}


# --- Speech gate (decision of the product owner) -------------------------------------------------
# A video reaches "Co wymaga sprawdzenia" only after the description AND the speech were examined and the
# collaboration label was not found, or when the transcript can permanently not be obtained. A suspicion
# from the description alone, while the transcript is still to be fetched, waits in `incomplete`.
PERMANENT_GAP = re.compile(r"^\s*(?:private|unavailable|age_restricted|members_only|no_captions)\b|brak napis", re.I)
SPEECH_PENDING_REASON = "Podejrzenie z opisu; mowy jeszcze nie zbadano (transkrypcja czeka na pobranie)."


def is_video(capture):
    return capture.get("module", "M1") == "M1" and str(capture.get("id", "")).startswith("youtube:")


def permanent_gap(reason):
    """True for a transcript that can not be obtained at all (no captions, private, removed); false for a retry."""
    return bool(PERMANENT_GAP.search(str(reason or "")))


def transcript_phase(capture):
    """{state: full|partial|pending|unavailable, reason} of the speech of a YouTube video, None for other material."""
    if not is_video(capture):
        return None
    media = capture.get("mediaCoverage") if isinstance(capture.get("mediaCoverage"), dict) else {}
    transcript = media.get("transcript") if isinstance(media.get("transcript"), dict) else {}
    segments = [s for s in capture.get("segments") or [] if isinstance(s, dict) and str(s.get("text", "")).strip()]
    state, reason = transcript.get("state"), transcript.get("reason")
    if state in ("full", "partial", "pending"):
        return {"state": state, "reason": reason}
    if state == "unavailable":
        return {"state": "unavailable" if permanent_gap(reason) else "pending", "reason": reason}
    if segments:
        return {"state": "partial", "reason": None}  # extent unknown without a coverage record
    return {"state": "pending", "reason": "transkrypcja jeszcze niepobrana"}


def _with_phase(capture, phase):
    """The capture as the qualification must see it: a transcript still to fetch is `pending`, not `unavailable`."""
    if phase is None or phase["state"] != "pending":
        return capture
    media = dict(capture.get("mediaCoverage") or {})
    transcript = dict(media.get("transcript") or {})
    transcript.update(state="pending", source=transcript.get("source") or "none", windows=transcript.get("windows") or [],
                      reason=phase.get("reason") or "transkrypcja jeszcze niepobrana")
    media["transcript"] = transcript
    return {**capture, "mediaCoverage": media}


def _gate(decision, phase):
    """Apply the speech gate to a qualification decision in place; returns the gate code or None."""
    if phase is None or decision.get("route") != "refer":
        return None
    if phase["state"] in ("pending", "partial"):
        code = "transcript_pending" if phase["state"] == "pending" else "other_gap"
        decision.update(route="complete", completeReason=code, gatedFrom="refer", queueEligible=False,
                        reason=SPEECH_PENDING_REASON if code == "transcript_pending" else
                        "Podejrzenie z opisu; mowę zbadano tylko częściowo.",
                        missing=list(dict.fromkeys([*(decision.get("missing") or []), "transkrypcja mowy"])))
        return code
    if phase["state"] == "unavailable":
        why = str(phase.get("reason") or "brak napisów").strip()[:120]
        sentence = f"Transkrypcji nie da się uzyskać ({why}); oceniono wyłącznie opis, mowy nie zbadano."
        reasons = list(decision.get("reasons") or [])
        reasons.insert(min(1, len(reasons)), sentence)
        decision["reasons"] = reasons[:5]
        decision["speechBasis"] = "unavailable"
    else:
        decision["speechBasis"] = "examined"
    return None


FRAME_NOTE = "kadry pobrane, tekst z obrazu nieodczytany automatycznie"


def _clock(seconds):
    seconds = int(seconds or 0)
    return f"{seconds // 60}:{seconds % 60:02d}"


def _frame_evidence(capture, result):
    """Frames carry no OCR: each is evidence for the analyst (kind=frame), listed beside the moments of the card."""
    frames = [f for f in capture.get("frames") or [] if isinstance(f, dict) and f.get("time", f.get("t")) is not None]
    if not frames:
        return
    evidence = result.setdefault("evidence", [])
    have = {(e.get("modality"), e.get("start")) for e in evidence if isinstance(e, dict)}
    decision = result.get("reviewDecision") or {}
    added = []
    for number, frame in enumerate(frames, 1):
        t = frame.get("time", frame.get("t"))
        if ("frame", t) in have:
            continue
        link = frame.get("sourceUrlAtTime") or frame.get("deepLink") or frame.get("url") or capture.get("url")
        item = {"id": frame.get("id") or f"frame-{number}", "kind": "frame", "role": "context", "modality": "frame",
                "method": frame.get("method"), "start": t, "end": t,
                "text": f"Kadr z {_clock(t)}; tekst z obrazu nieodczytany automatycznie.",
                "url": frame.get("url") or capture.get("url"), "sourceUrlAtTime": link,
                "frameSha256": frame.get("sha256") or frame.get("frameSha256"), "framePath": frame.get("path"),
                "observedAt": frame.get("observedAt") or capture.get("observedAt"), "available": bool(link)}
        evidence.append(item)
        added.append(item)
    if added and decision.get("route") == "refer" and isinstance(decision.get("moments"), list):
        for item in added:
            decision["moments"].append({"start": item["start"], "end": item["end"], "label": "Kadr z momentu dowodu",
                                        "deepLink": item["sourceUrlAtTime"], "evidenceId": item["id"]})
    cov = result.get("coverage")
    if isinstance(cov, dict) and isinstance(cov.get("modalities"), dict):
        frames_cov = cov["modalities"].setdefault("frames", {})
        frames_cov["reason"] = FRAME_NOTE
        if isinstance(cov.get("label"), str):
            cov["label"] = re.sub(r"kadry \([^)]*\)", f"kadry ({FRAME_NOTE})", cov["label"])


def _qualification_failed(exc):
    reason = f"Kwalifikacja nie powiodła się: {type(exc).__name__}"
    return {"reviewDecision": {"route": "insufficient", "reason": reason[:160], "reasons": [], "moments": [],
                               "completeReason": None, "requirement": None, "claim": None, "alternative": None,
                               "missing": [], "decidedBy": "rules", "version": None, "queueEligible": None},
            "reviewScore": {"state": "withheld", "value": None, "scale": "0-100", "band": None, "meaning": None,
                            "notComputableReason": reason, "rulesVersion": None, "modelVersion": None, "components": []},
            "adRelationship": {"status": "unknown"}, "relationships": [], "adRegistry": {"state": "none"},
            "premises": [], "evidence": [], "counterEvidence": [], "coverage": None}


# --- Instagram and Facebook posts read as text (lane K sample, manual import) -------------------------------------
CAPTION_ONLY = re.compile(r"obrazu i wideo nie analizowano|obrazu, wideo i układu", re.I)
STRONG_RELATION = {"tracking_link", "creator_code"}
PLATFORM_FLAG_TEXT = {"instagram": "Instagram oznacza post jako płatne partnerstwo",
                      "facebook": "Facebook oznacza wpis jako płatne partnerstwo"}


def _social_platform(capture):
    return str(capture.get("platform") or "").split(":")[0]


def _with_platform_flag(capture):
    """The platform's paid-partnership flag of an Instagram or Facebook post is a disclosure at platform level, as
    paidPromotionFlag is on YouTube. Only True counts; False proves nothing about a label inside the picture."""
    flag = capture.get("isPaidPartnership")
    if _social_platform(capture) not in PLATFORM_FLAG_TEXT or not isinstance(flag, bool) or isinstance(capture.get("youtube"), dict):
        return capture
    return {**capture, "youtube": {"paidPromotionFlag": flag, "observedAt": capture.get("observedAt"), "synthetic": "platform-flag"}}


def _name_the_platform(capture, result):
    """The shared qualification words the flag as YouTube's: say which platform really reported it."""
    text = PLATFORM_FLAG_TEXT.get(_social_platform(capture))
    if text is None or not isinstance(capture.get("isPaidPartnership"), bool):
        return
    for item in result.get("evidence", []):
        if isinstance(item, dict) and item.get("field") == "youtube.paidPromotionFlag":
            stamp = item["text"].partition(" (")[2]
            item.update(text=text + (f" ({stamp}" if stamp else ""), field="platform.paidPartnership", method="vendor_api")
            disclosure = (result.get("adRelationship") or {}).get("disclosure")
            if isinstance(disclosure, dict) and disclosure.get("evidenceId") == item["id"]:
                disclosure["text"] = item["text"]
    platform = ((result.get("coverage") or {}).get("modalities") or {}).get("platformFlags")
    if isinstance(platform, dict):
        platform["label"] = text.split(" oznacza")[0] + ": flaga płatnego partnerstwa"


def _platform_register(capture, result):
    """A post flagged by the platform as a paid partnership is an advertising relation declared at platform level even when
    the caption names no firm: it enters the register with the firm unresolved (the platform does not name the partner)."""
    flagged = capture.get("isPaidPartnership") is True and _social_platform(capture) in PLATFORM_FLAG_TEXT
    if not flagged or (result.get("adRegistry") or {}).get("state") != "none":
        return
    item = next((e for e in result.get("evidence", []) if isinstance(e, dict) and e.get("field") == "platform.paidPartnership"), None)
    if item is None:
        return
    sentence = f"{PLATFORM_FLAG_TEXT[_social_platform(capture)]}; w podpisie nie wskazano firmy."
    relation = dict(result.get("adRelationship") or {})
    relation.update(status="declared", basis="flaga płatnego partnerstwa platformy", firm=None,
                    disclosure={"state": "platform_flag", "where": "platform", "text": item["text"], "evidenceId": item["id"],
                                "checked": ["platformFlags"], "notChecked": ["frames", "transcript"], "kind": "platform_flag",
                                "kinds": ["platform_flag"], "summary": sentence})
    result["adRelationship"] = relation
    result["adRegistry"] = {"state": "included", "campaignKey": f"{capture.get('creatorId')}|platform_flag",
                            "firstObservedAt": capture.get("observedAt"), "identityStatus": "unresolved", "entityType": "unresolved",
                            "disclosureKind": "platform_flag", "summary": sentence}


def _caption_only(capture):
    media = capture.get("mediaCoverage") if isinstance(capture.get("mediaCoverage"), dict) else {}
    reason = str((media.get("transcript") or {}).get("reason") or "")
    return (capture.get("module", "M1") == "M1" and _social_platform(capture) in PLATFORM_FLAG_TEXT
            and not capture.get("segments") and bool(CAPTION_ONLY.search(reason)))


def _caption_gate(capture, result, decision):
    """Only the caption was read. A label may sit in the picture or the video, so a missing label is not a finding by
    itself: the route becomes `complete: check the material`. It stays `refer` only when the proof of the relation is
    strong (a firm's tracking link or a code) AND the platform returned the paid-partnership flag as false."""
    if decision.get("route") != "refer":
        return None
    kinds = {r.get("kind") for p in result.get("premises") or [] for r in p.get("relationEvidence") or []}
    flag = capture.get("isPaidPartnership")
    scope = "Zbadano tylko podpis posta; obrazu i wideo nie oglądano."
    if kinds & STRONG_RELATION and flag is False:
        sentence = f"{scope} Platforma zwróciła flagę płatnego partnerstwa: nie. Dowód relacji z firmą jest mocny (link śledzący lub kod)."
        reasons = list(decision.get("reasons") or [])
        decision["reasons"] = [*reasons[:4], sentence]
        decision["captionBasis"] = "caption_only_strong"
        return None
    decision.update(route="complete", completeReason="visual_unexamined", gatedFrom="refer", queueEligible=False,
                    reason="Uzupełnij: sprawdź materiał wideo lub grafikę; w podpisie nie ma oznaczenia, ale mogło być w obrazie.",
                    missing=list(dict.fromkeys([*(decision.get("missing") or []), "obraz i wideo posta"])))
    decision["reasons"] = [*(decision.get("reasons") or [])[:4], scope + " Brak oznaczenia w podpisie nie wyklucza oznaczenia w obrazie."]
    return "visual_unexamined"


BRACKET_TAG_START = re.compile(r"\s*\[\s*współprac\w*\s+z\s+", re.I)
BRACKET_COLLABORATION = r"|\[\s*współprac\w*\s+z\s+(?:firmą\s+)?(?P<name_tag>[^\]\n]{2,60})\]"


def _caption_vocabulary(qualification):
    """Short-form captions (TikTok) label a paid collaboration as "[współpraca z XTB]". Teach the qualification's
    named-disclosure pattern that bracket form, once, without changing any quoted text. The qualification module
    belongs to lane D: when its own pattern already reads the form, nothing is changed."""
    pattern = qualification.NAMED_DECLARATION
    if not pattern.search("[współpraca z XTB] Złoto"):
        qualification.NAMED_DECLARATION = re.compile(pattern.pattern + BRACKET_COLLABORATION, pattern.flags)
    skip = qualification._skip_clause
    if not getattr(skip, "bracket_aware", False):
        def bracket_aware(text):
            # A caption that opens with the label is not a question to skip, even if its first sentence ends with "?".
            return False if BRACKET_TAG_START.match(text) else skip(text)
        bracket_aware.bracket_aware = True
        qualification._skip_clause = bracket_aware


def _shadow(capture, finding, semantic, variant=None):
    """Single call site of qualify (contract R5). Adds the v2 fields to an M1 finding."""
    from . import qualification
    _caption_vocabulary(qualification)
    from .semantic import review_suggestion
    phase = transcript_phase(capture)
    try:
        result = qualification.qualify(_with_platform_flag(_with_phase(capture, phase)), finding, semantic)
        _name_the_platform(capture, result)
        _platform_register(capture, result)
    except Exception as exc:  # a failing rule must never stop a scan
        result = _qualification_failed(exc)
    suggestion = review_suggestion(capture, semantic or {}, finding)
    decision = result["reviewDecision"]
    score = result["reviewScore"]
    gate = _gate(decision, phase)
    if gate is None and _caption_only(capture):
        gate = _caption_gate(capture, result, decision)
    if capture.get("frames"):
        _frame_evidence(capture, result)
    decision["queueEligible"] = bool(decision["route"] == "refer" and score.get("value") is not None
                                     and score["value"] >= DEFAULT_THRESHOLD)
    rules_route = ROUTE_OF_SUGGESTION.get(suggestion["state"], "insufficient")
    rules_gate = None
    if phase is not None and rules_route == "refer" and phase["state"] in ("pending", "partial"):
        rules_route, rules_gate = "complete", "transcript_pending" if phase["state"] == "pending" else "other_gap"
    finding.update({key: result[key] for key in SHADOW_KEYS if key in result})
    finding["evidence"] = [*finding["evidence"], *result["evidence"]]
    finding["variants"] = {
        "rules_1_2": {"route": rules_route,
                      "reviewScore": {"state": "computed", "value": finding["score"], "scale": "0-100"},
                      "decidedBy": "rules", "variantUsed": "rules_1_2", "fallback": None,
                      "reason": suggestion.get("reason"), "gated": rules_gate},
        "qual_d": {"route": decision["route"], "reviewScore": {k: score.get(k) for k in ("state", "value", "scale", "band")},
                   "decidedBy": decision.get("decidedBy"), "variantUsed": "qual_d", "fallback": None,
                   "queueEligible": decision["queueEligible"], "gated": gate}}
    if variant == "qual_d_model":
        # No local model can run yet (N3): the answer is qual_d, with the reason recorded. No key is read.
        finding["variants"]["qual_d_model"] = {**finding["variants"]["qual_d"], "variantUsed": "qual_d",
                                               "fallback": {"from": "qual_d_model", "reason": "model lokalny niedostępny"}}
    finding["analysisVersion"] = {"rules": RULESET, "model": None, "schema": ANALYSIS_SCHEMA, "variant": variant or ACTIVE_VARIANT,
                                  "shadowVariant": "qual_d", "qualification": decision.get("version")}
    order = qualification.priority(capture.get("reach"), result.get("adRelationship"))
    finding["priority"] = {**(capture.get("priority") if isinstance(capture.get("priority"), dict) else {}),
                           "review": order["review"], "basis": order["basis"], "affectsDecision": False}


def _annotate_on():
    return os.getenv("INVESTWATCH_MODEL_ANNOTATE", "").strip().lower() in {"1", "on", "true"}


def _annotation_wanted(finding):
    """Only material of a human queue costs CPU: review (refer + eligible), ad register, M2 and M3 offers.
    The test mirrors api.store.queues_of; a replay of thousands of other findings stays free."""
    decision = finding.get("reviewDecision") if isinstance(finding.get("reviewDecision"), dict) else {}
    return bool(finding.get("module") in ("M2", "M3")
                or (finding.get("adRegistry") or {}).get("state") in ("included", "candidate")
                or (decision.get("route") == "refer" and decision.get("queueEligible")))


MODEL_UNAVAILABLE = {"task": "material_type", "engine": None, "status": "unavailable", "label": None, "confidence": None,
                     "quote": None, "modelId": None, "version": None, "digest": None, "promptVersion": None,
                     "latencyMs": None, "affectsDecision": False,
                     "meaning": "Typ materiału opisuje treść dla analityka; nie zmienia skierowania ani punktów."}


def _annotate(finding, capture):
    """INVESTWATCH_MODEL_ANNOTATE=1: add the descriptive `model` field (affectsDecision=false) and its version to
    analysisVersion.model. Route, score and queues stay as the rules set them; a failure is a status, never a scan error."""
    try:
        from .inference import annotate
        annotated = annotate(finding, capture)
        model = annotated["model"]
        second = model.get("secondOpinion") or {}
        version = {"materialType": model.get("version"),
                   "secondOpinion": second.get("modelId") if second.get("status") not in ("disabled", None) else None}
        model["affectsDecision"] = False
    except Exception as exc:  # no weights, no service, a bug: "model niedostępny"
        model = {**MODEL_UNAVAILABLE, "reason": f"model niedostępny ({type(exc).__name__})"}
        annotated, version = dict(finding), None
    result = {**finding, "model": model}
    if isinstance(result.get("analysisVersion"), dict):
        result["analysisVersion"] = {**result["analysisVersion"], "model": version}
    return result


M2_RULES = "investwatch-m2-rendered-1"


def module_rules():
    """Rule version(s) a stored finding of each module is current with."""
    from .m2_rules import RULES_VERSION as card_rules
    return {"M1": RULESET, "M2": (M2_RULES, card_rules), "M3": m3_rules()}


def _stamp(finding, module):
    """analysisVersion of M2 and M3 (M1 gets it from the qualification): the module's rules and the analysis schema."""
    rules = module_rules()["M3"] if module == "M3" else finding.get("rulesVersion") or module_rules()[module][0]
    finding["analysisVersion"] = {"rules": rules, "model": None, "schema": ANALYSIS_SCHEMA, "variant": module.lower() + "_rules",
                                  "module": module}


def analyze(capture, *, semantic=None, variant=None, offers=True):
    module = capture.get("module", "M1")
    score, summary, evidence, extra = {"M1": m1, "M2": m2, "M3": m3}[module](capture)
    finding = {k: capture[k] for k in (
        "id", "title", "module", "platform", "creatorId", "creatorName", "url", "brand", "provenance",
        "publishedAt", "observedAt", "mediaUrl", "contractDemo", "asrModel", "mediaSha256", "mode",
        "sourceId", "campaignId", "version", "description", "segments", "registry", "synthetic",
    ) if k in capture}
    finding.update({"module": module, "score": score, "summary": summary, "evidence": evidence,
                    "rulesVersion": RULESET, **extra})
    if module == "M1":
        _shadow(capture, finding, semantic, variant)
    elif module == "M3" and offers:
        try:
            _offers_view(capture, finding)
        except Exception as exc:  # a failing rule must never stop a scan
            finding["reviewDecision"] = _qualification_failed(exc)["reviewDecision"]
            finding["reviewScore"] = _qualification_failed(exc)["reviewScore"]
    if module in ("M2", "M3"):
        _stamp(finding, module)
    if _annotate_on() and _annotation_wanted(finding):
        finding = _annotate(finding, capture)
    return finding


def calibration(threshold=60, variant="rules_1_2"):
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
        found = analyze(cap, offers=False)
        score = found["score"]
        if variant == "rules_1_2" or "reviewScore" not in found:
            predicted = score >= threshold
        else:  # the qualification variants: refer, with a score at or above the threshold
            value = (found["reviewScore"] or {}).get("value")
            predicted = found["reviewDecision"]["route"] == "refer" and value is not None and value >= threshold
        expected = row["expected"]
        outcome = ("t" if predicted == expected else "f") + ("p" if predicted else "n")
        counts[outcome] += 1
        examples.append({"id": cap["id"], "title": cap["title"], "module": cap["module"], "score": score,
                         "expected": expected, "outcome": outcome, "origin": row["origin"], "url": cap.get("url"),
                         "text": cap["description"],
                         # Active variant rules_1_2 decides today; qual_d is the shadow reading.
                         "route": "refer" if predicted else "no_signal", "variant": variant,
                         **({"variants": found["variants"]} if "variants" in found else {})})
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
