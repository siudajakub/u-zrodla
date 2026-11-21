"""M1 qualification: ad relationship, review premises, evidence strength and coverage.

Pure function, no network, no model. The result is a screening recommendation
for an analyst ("przesłanka do kontroli"), never a legal finding. The threshold
is applied by the API, not here. Reach is not an input (see ``priority``).
Field names follow docs/lanes/2026-11-21-fable-h-kontrakt.md §3.3.
"""
from datetime import datetime
from functools import lru_cache
from hashlib import sha256
import json
import math
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit

from .engine import ADVICE, CTA, FRAUD_CONTEXT, FRAUD_REFERENCE, NO_ADVICE

RULES_VERSION = "investwatch-m1-qual-1.0"
INDEX_PATH = Path(__file__).resolve().with_name("firm-index.json")
SCALE_MEANING = ("Punkty siły przesłanki do kontroli 0–100: suma jawnych składników reguł. "
                 "Nie jest prawdopodobieństwem ani oceną prawną; próg stosuje API.")

# --- Disclosure, relation and claim vocabulary -------------------------------------------
URL = re.compile(r"https?://[^\s<>\"')\]]+")
REKLAMA_TAG = re.compile(r"\[\s*reklama(?:[_\s]+(?P<name>[^\]]+?))?\s*\]", re.I)
NAMED_DECLARATION = re.compile(
    r"\b(?:partnerem|sponsorem)\s+(?:(?:tego|naszego|dzisiejszego)\s+)?"
    r"(?:programu|odcinka|materiału|kanału|filmu|publikacji|wpisu|nagrania|podcastu|rankingu|audycji)\s+"
    r"(?:jest|został\w*)\s+(?:firma\s+|marka\s+|dom maklerski\s+)?(?P<name>[^.,;:!?\n]{2,60})"
    r"|\bnaszym partnerem jest\s+(?P<name2>[^.,;:!?\n]{2,60})"
    r"|\b(?:film|odcinek|materiał)\s+sponsoruje\s+(?P<name3>[^.,;:!?\n]{2,60})"
    r"|\bwe współpracy z\s+(?:firmą\s+)?(?P<name4>[^.,;:!?\n]{2,60})"
    r"|\b(?:płatn\w*\s+współprac\w*|współprac\w*\s+(?:reklamow|marketingow)\w*)\s+z\s+(?:firmą\s+)?(?P<name5>[^.,;:!?\n]{2,60})"
    r"|\blink\s+(?P<name6>\w[\w ]{0,20}?)\s+wstawiamy\s+w\s+ramach\s+płatnej\s+współpracy",
    re.I,
)
GENERIC_LABEL = re.compile(
    r"(?<![\w/])#(?:reklama|wsp[oó][łl]praca(?:reklamowa)?|p[łl]atnawsp[oó][łl]praca|materia[łl]reklamowy|ad|sponsored|sponsorowane)\b"
    r"|\bp[łl]atn\w*\s+wsp[oó][łl]prac\w*"
    r"|\bwsp[oó][łl]prac\w*\s+(?:reklamow|marketingow)\w*"
    r"|\bmateria[łl]\w*\s+(?:reklamow|sponsorowan|promocyjn)\w*"
    r"|\b(?:odcinek|film|wpis|post)\s+sponsorowan\w*"
    r"|\blink\w*\s+(?:partnersk|afiliacyjn|polecając)\w*"
    r"|^\s*[\[(]?\s*reklama\s*(?:$|[\]).:–-])"
    r"|\bto\s+(?:jest\s+)?reklama\b",
    re.I | re.M,
)
CONTACT_LINE = re.compile(r"wsp[oó][łl]prac\w*\s*[:\-–]\s*(?:\S+@\S+|kontakt|napisz|zapraszam)", re.I)
DENIAL = re.compile(
    r"\b(?:nie jest|nie była|bez|żadnej|brak) (?:to |żadnej )?"
    r"(?:reklam\w*|współprac\w*|partner\w*|sponsor\w*|materiał\w* (?:reklamow\w*|sponsorowan\w*))"
    r"|\bnie (?:reklamuję|współpracuję|mam (?:z nią|z nim|z nimi) umowy)\b|\bnie (?:finansowała|finansował|zapłacił\w*)\b"
    r"|\b(?:materiał|odcinek|film) nie (?:powstał\w*|został\w*) we współpracy\b",
    re.I,
)
CODE = re.compile(r"(?i:\b(?:promo)?kod(?:em|u)?(?:\s+(?:rabatow|polecaj|promocyjn|partnersk)\w*)?)\s*[:„\"«'“]?\s*"
                  r"(?P<code>[A-Z0-9][A-Z0-9_-]{3,})\b")
CODE_CONTEXT = re.compile(r"rejestr|konto|kont[ao]|rachun|otw[oó]rz|za[łl][oó][żz]|aplikacj|zapis", re.I)
COMPENSATION = re.compile(
    r"\b(?:dostaj\w*|otrzymuj\w*|zarabiam)\b[^.\n]{0,40}\b(?:prowizj\w*|wynagrodzeni\w*|pieniądz\w*|przelew\w*|zapłat\w*)"
    r"|\bprzelew\w*\s+od\s+(?:domu maklerskiego|brokera|firmy inwestycyjnej)"
    r"|\bza każd\w*\s+(?:now\w*\s+)?(?:rachun|kont|klient)\w*[^.\n]{0,40}\b(?:dostaj|otrzymuj|płac)\w*"
    r"|\b(?:dostaj|otrzymuj)\w*\s+[^.\n]{0,30}\bza każd\w*\s+(?:now\w*\s+)?(?:rachun|kont|klient)\w*",
    re.I,
)
CTA_EXTRA = re.compile(r"\b(?:sprawdź|zacznij|inwestuj|odbierz|otwórz|załóż|pobierz|zarejestruj|wybierz)\b", re.I)
GENERIC_FIRM = re.compile(r"\b(?:dom\w* maklersk\w*|broker\w*|firm\w* inwestycyjn\w*)\b", re.I)
INVESTMENT_CONTEXT = re.compile(
    r"\b(?:akcj\w*|ETF\w*|inwest\w*|makler\w*|CFD|forex|broker\w*|kryptowalut\w*|IKE|IKZE|obligacj\w*|fundusz\w*|giełd\w*)\b",
    re.I,
)
TRACK_SUBDOMAINS = {"link-pso", "geolink", "c", "go", "track", "trk", "partners", "partner", "affiliate", "aff", "invite", "r"}
TRACK_QUERY = {"a", "ref", "ref1", "aff", "affid", "aff_id", "partner", "pid", "referral", "invite"}
TRACK_PATH = re.compile(r"/(?:pso|campaigns?|invite|ref|referral|aff|partners?)(?:/|$)", re.I)
NUMBER = (r"(?:\d+(?:[.,]\d+)?|jed\w+|dw\w+|trz\w+|czter\w+|pięć\w*|sześć\w*|siedem\w*|osiem\w*|dziewięć\w*"
          r"|dziesięć\w*|\w+naście|\w+dzieści\w*|\w+set|sto)")
PROFIT = re.compile(
    rf"\b(?:zarobi\w*|zarabia\w*|zysk\w*|zwrot\w*|stop\w* zwrotu|dochod\w*|zrobi\w*)\b[^.!?\n]{{0,40}}?\b{NUMBER}\s*(?:%|procent\w*)"
    rf"|\b{NUMBER}\s*(?:%|procent\w*)\s+(?:rocznie|w skali roku|zysku|zwrotu|miesięcznie)",
    re.I,
)
# "w tej aplikacji", "u partnera": a claim about the promoted product without repeating the brand.
PRODUCT_ANAPHORA = re.compile(r"\b(?:t(?:ej|ym|en|a|ą)\s+(?:aplikacj\w*|platform\w*|broker\w*|kon\w*|rachunk\w*|ofer\w*)"
                              r"|u\s+partnera|partner\w*\s+(?:tego\s+)?(?:odcinka|kanału))\b", re.I)
GUARANTEE = re.compile(
    r"\b(?:pewn\w*|gwarantowan\w*|bezwarunkow\w*)\s+(?:zysk|zwrot|zarob)\w*"
    r"|\b(?:gwarantuj\w*|zapewniamy)\b[^.!?\n]{0,55}\b(?:zysk|zwrot)\w*"
    r"|\b(?:zysk|zwrot|zarob)\w*\b[^.!?\n]{0,55}\bbez (?:żadnego )?ryzyka\b"
    r"|\bna pewno (?:zarobi\w*|wzrośnie|zyska\w*)",
    re.I,
)
GUARANTEE_DENIAL = re.compile(r"\bnie (?:gwarant\w*|zapewnia\w*|jest (?:pewn\w*|gwarantowan\w*))|\b(?:brak|bez) gwarancji"
                              r"|nie stanowi\w* gwarancji", re.I)
SUPERVISION = re.compile(
    r"\b(?:KNF|Komisj\w* Nadzoru Finansowego|nadz[oó]r\w*)\b[^.\n]{0,20}\b(?:poleca|zatwierdzi\w*|zatwierdza|rekomenduje|aprobuje|gwarantuje)\b"
    r"|\bbezpiecz\w*[^.\n]{0,32}\b(?:dzięki|bo|ponieważ)\b[^.\n]{0,25}\b(?:KNF|nadzor\w*)",
    re.I,
)
RISK_WARNING = re.compile(r"\bryzyk\w*|\bryzykown\w*|\bstrat\w*|\butrat\w*|inwestuj odpowiedzialnie"
                          r"|nie (?:gwarantuj\w*|są wiarygodnym)", re.I)

BASIS = {
    "U1": {"source": "Brief §2 M1, §3 Korzyści; KRYTERIA-M2 ID 2", "provision": "art. 24 ust. 3 MiFID II (materiał firmy)",
           "basisScope": "pakiet UKNF", "transfer": "dowód relacji handlowej z firmą z wykazu; oznaczenie szukane w opisie, mowie i kadrach"},
    "U3": {"source": "Brief §2 M1; Temat 1", "provision": "definicje firmy inwestycyjnej i wskazane wykazy",
           "basisScope": "pakiet UKNF", "transfer": "brak wpisu w jednym wykazie nie dowodzi braku uprawnień"},
    "U4": {"source": "KRYTERIA-M2 ID 3", "provision": "art. 44 ust. 2 lit. b rozporządzenia (UE) 2017/565",
           "basisScope": "pakiet UKNF, materiały firmy", "transfer": "warunkowy: relacja zadeklarowana lub udokumentowana i ten sam produkt"},
    "U5": {"source": "KRYTERIA-M2 ID 15, 14", "provision": "art. 44 ust. 6 i ust. 4 lit. d rozporządzenia (UE) 2017/565",
           "basisScope": "pakiet UKNF, materiały firmy", "transfer": "warunkowy: relacja zadeklarowana lub udokumentowana i ten sam produkt"},
    "U6": {"source": "KRYTERIA-M2 ID 17, 18", "provision": "art. 44 ust. 8 rozporządzenia (UE) 2017/565",
           "basisScope": "pakiet UKNF, materiały firmy", "transfer": "warunkowy: relacja zadeklarowana lub udokumentowana"},
    "U7": {"source": "Brief §2 M3", "provision": "odesłanie do modułu M3", "basisScope": "pakiet UKNF", "transfer": "nie dotyczy M1"},
}
LABELS = {
    "U1": "Nieoznaczona współpraca z firmą inwestycyjną",
    "U3": "Promowany podmiot bez wpisu w przejrzanych wykazach",
    "U4": "Twierdzenie o zysku bez informacji o ryzyku",
    "U5": "Obietnica pewnego zysku lub prognoza",
    "U6": "Sugestia aprobaty organu nadzoru",
    "U7": "Sygnał indywidualnej rekomendacji (M3)",
}
EXPLANATIONS = {
    "U1": ["oznaczenie reklamy mogło paść w miejscu, którego nie zbadano, albo być wyrażone inaczej, niż szukano",
           "link może być zwykłym poleceniem, bez wynagrodzenia dla twórcy"],
    "U3": ["kopia wykazu może być niepełna albo firma działa pod inną nazwą prawną"],
    "U4": ["wypowiedź może opisywać osobisty wynik twórcy, a nie obietnicę firmy",
           "ostrzeżenie o ryzyku mogło paść w miejscu, którego nie zbadano"],
    "U5": ["to może być ironia, cytat cudzej obietnicy albo przykład hipotetyczny"],
    "U6": ["neutralna informacja o nadzorze nie jest jeszcze sugestią, że organ coś zaaprobował"],
    "U7": ["to może być materiał edukacyjny albo zaprzeczenie, że udziela się doradztwa"],
}
BASE_LABELS = {"U1": "podstawa: relacja z firmą bez oznaczenia reklamy", "U3": "podstawa: brak wpisu firmy w wykazie",
               "U4": "podstawa: twierdzenie o zysku", "U5": "podstawa: obietnica pewnego zysku",
               "U6": "podstawa: sugestia aprobaty nadzoru"}
RELATION_NAMES = {"declared": "zadeklarowana", "documented": "udokumentowana", "probable": "prawdopodobna"}
KIND_NAMES = {"tracking_link": "link polecający", "short_link": "skrócony link przy nazwie firmy", "creator_code": "kod twórcy",
              "compensation": "wzmianka o wynagrodzeniu", "affiliate_label": "oznaczenie linku partnerskiego"}
CATEGORY_NAMES = {"Firmy inwestycyjne - Domy maklerskie": "dom maklerski",
                  "Firmy inwestycyjne - Banki prowadzące działalność maklerską": "bank prowadzący działalność maklerską",
                  "Notyfikacje zagranicznych firm inwestycyjnych na terytorium RP": "notyfikacja"}
DISCLOSURE_KIND_NAMES = {"explicit_ad": "oznaczenie reklamy lub współpracy", "platform_flag": "oznaczenie płatnej promocji przez YouTube",
                         "affiliate_link_mention": "wzmianka o linku partnerskim", "partner_mention": "wzmianka o partnerze materiału"}


def _clock(seconds):
    """Seconds as m:ss (h:mm:ss from one hour)."""
    if not isinstance(seconds, (int, float)):
        return "czas nieznany"
    total = int(math.floor(seconds))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def _quote(text, limit=120):
    text = " ".join((text or "").split())
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0].rstrip(" ,;:.") + "…"
    return f"„{text}”"


def _stamp(value):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return str(value)


def _join(items):
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " i " + items[-1]


def _upper(text):
    return text[:1].upper() + text[1:]
BASE_POINTS = {"U1": 45, "U3": 30, "U4": 40, "U5": 50, "U6": 50}
CONDITIONAL_CAP = 55


@lru_cache(maxsize=1)
def _default_index():
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


def _compiled(index):
    firms = [(f, re.compile(f["pattern"], re.I)) for f in index["firms"]]
    outside = [(f, re.compile(f["pattern"], re.I)) for f in index["outOfScope"]]
    return firms, outside


# --- Units and evidence --------------------------------------------------------------------
def _description_units(text):
    """Lines with absolute offsets and paragraph ids."""
    units, offset, paragraph = [], 0, 0
    for line in text.split("\n"):
        if not line.strip():
            paragraph += 1
        else:
            units.append({"modality": "description", "text": line, "offset": offset, "paragraph": paragraph})
        offset += len(line) + 1
    return units


def _speech_units(capture):
    units = []
    for index, seg in enumerate(capture.get("segments") or []):
        if not isinstance(seg, dict) or not isinstance(seg.get("text"), str) or not seg["text"].strip():
            continue
        method = seg.get("method") or "asr"
        units.append({"modality": "transcript", "text": seg["text"], "start": seg.get("start"), "end": seg.get("end"),
                      "method": method, "confidence": seg.get("confidence"), "windowId": seg.get("windowId"),
                      "segment": index, "paragraph": f"t{index}"})
    return units


QUOTED = re.compile(r"„([^”]{2,120})”")


def _frame_units(capture):
    """Contract shape {t, text, method:"ocr"} or agent C shape {time, observation, sha256}.

    For C records the on-screen text is taken from the quoted fragments of the observation
    („…”), one unit per fragment; the observation is a description of the frame, not OCR."""
    units = []
    for i, frame in enumerate(capture.get("frames") or []):
        if not isinstance(frame, dict):
            continue
        t = frame.get("t", frame.get("time"))
        if isinstance(frame.get("text"), str):
            texts, method = [frame["text"]], frame.get("method", "ocr")
        elif isinstance(frame.get("observation"), str):
            texts, method = QUOTED.findall(frame["observation"]), (frame.get("method") or "frame") + "+observation"
        else:
            continue
        for j, text in enumerate(texts):
            units.append({"modality": "frame", "text": text, "start": t, "end": t, "method": method,
                          "frameSha256": frame.get("frameSha256") or frame.get("sha256"), "paragraph": f"f{i}.{j}",
                          "observation": frame.get("observation")})
    return units


def _time_link(url, start):
    if not isinstance(url, str) or start is None:
        return None
    seconds = int(math.floor(start))
    try:
        host = urlsplit(url).hostname or ""
    except ValueError:
        return None
    if host.endswith("youtube.com") or host.endswith("youtu.be"):
        return f"{url}{'&' if '?' in url else '?'}t={seconds}s"
    return f"{url}#t={seconds}"


class Evidence:
    def __init__(self, capture):
        self.capture = capture
        self.items = []
        self.description = capture.get("description") or ""

    def add(self, unit, start, end, role):
        quote = unit["text"][start:end].strip()
        lead = len(unit["text"][start:end]) - len(unit["text"][start:end].lstrip())
        start += lead
        url = self.capture.get("url")
        item = {"id": f"ev-{len(self.items) + 1}", "kind": "audio" if unit["modality"] == "transcript" else unit["modality"],
                "role": role, "modality": unit["modality"], "text": quote, "match": "verbatim",
                "textSha256": sha256(quote.encode()).hexdigest(), "url": url,
                "sourceVersion": self.capture.get("mediaVersion") if unit["modality"] != "description" else self.capture.get("contentHash"),
                "observedAt": self.capture.get("observedAt"), "available": bool(url)}
        if unit["modality"] == "description":
            absolute = unit["offset"] + start
            item["locator"] = {"field": "description", "charStart": absolute, "charEnd": absolute + len(quote),
                               "occurrences": self.description.count(quote)}
            item["sourceUrlAtTime"] = url
        else:
            item.update(start=unit.get("start"), end=unit.get("end"), method=unit.get("method"))
            item["sourceUrlAtTime"] = _time_link(url, unit.get("start"))
            if unit.get("confidence") is not None:
                item["confidence"] = unit["confidence"]
            if unit.get("windowId") is not None:
                item["windowId"] = unit["windowId"]
            if unit.get("joinedSegments"):
                item["joinedSegments"] = unit["joinedSegments"]
            if unit.get("frameSha256"):
                item["frameSha256"] = unit["frameSha256"]
            if unit.get("observation"):
                item["match"] = "approximate"
                item["observation"] = unit["observation"]
            if unit.get("method") == "auto_captions":
                item["caveat"] = "auto-napisy: nazwy własne i liczby mogą być zniekształcone"
            if self.capture.get("mediaSha256"):
                item["mediaSha256"] = self.capture["mediaSha256"]
        for existing in self.items:
            if existing["text"] == quote and existing.get("locator") == item.get("locator") and existing.get("start") == item.get("start"):
                return existing["id"]
        self.items.append(item)
        return item["id"]

    def get(self, evidence_id):
        return next(item for item in self.items if item["id"] == evidence_id)


# --- Coverage ------------------------------------------------------------------------------
def coverage(capture):
    description = capture.get("description") or ""
    prov = capture.get("provenance") if isinstance(capture.get("provenance"), dict) else {}
    fragment = bool(prov.get("truncated") or prov.get("sampled") or capture.get("contentCompleteness") == "partial"
                    or (prov.get("originalTextSha256") and capture.get("contentHash")
                        and prov["originalTextSha256"] != capture["contentHash"]))
    desc = {"state": "empty" if not description.strip() else "fragment" if fragment else "full", "chars": len(description)}
    if prov.get("originalTextSha256"):
        desc["originalTextSha256"] = prov["originalTextSha256"]
    media = capture.get("mediaCoverage") if isinstance(capture.get("mediaCoverage"), dict) else {}
    tmedia = media.get("transcript") if isinstance(media.get("transcript"), dict) else {}
    segments = [s for s in capture.get("segments") or [] if isinstance(s, dict) and str(s.get("text", "")).strip()]
    windows = [{"start": s.get("start"), "end": s.get("end")} for s in segments if s.get("start") is not None]
    if tmedia.get("state"):
        tstate = tmedia["state"]
    elif segments:
        tstate = "partial"  # extent unknown without mediaCoverage (e.g. first 45 s of a podcast)
    else:
        tstate = "unavailable"
    transcript = {"state": tstate, "source": tmedia.get("source") or (segments[0].get("method") if segments else "none"),
                  "windows": tmedia.get("windows") or windows, "durationSec": tmedia.get("durationSec"),
                  "reason": tmedia.get("reason") or (None if segments else "nie pobrano transkrypcji")}
    fmedia = media.get("frames") if isinstance(media.get("frames"), dict) else {}
    frames_list = capture.get("frames") or []
    if frames_list:  # frames actually present win over a stale media summary
        fstate = fmedia.get("state") if fmedia.get("state") in ("selected_moments", "full") else "selected_moments"
    else:
        fstate = fmedia.get("state") or "not_collected"
    frames = {"state": fstate, "moments": [f.get("t", f.get("time")) for f in frames_list if isinstance(f, dict)] or fmedia.get("moments") or [],
              "reason": None if fstate != "not_collected" else "kadrów nie pobrano"}
    flag = (capture.get("youtube") or {}).get("paidPromotionFlag") if isinstance(capture.get("youtube"), dict) else None
    platform = {"state": "observed" if flag is not None else "unavailable", "paidPromotion": flag}
    title = {"state": "full" if (capture.get("title") or "").strip() else "empty"}
    gaps = []
    if desc["state"] != "full":
        gaps.append({"modality": "description", "code": desc["state"],
                     "reason": "zbadano tylko fragment opisu" if desc["state"] == "fragment" else "brak opisu"})
    if tstate != "full":
        gaps.append({"modality": "transcript", "code": tstate,
                     "reason": "mowę zbadano częściowo" if tstate == "partial" else "mowy nie zbadano"})
    if fstate == "not_collected":
        gaps.append({"modality": "frames", "code": "not_collected", "reason": "kadrów nie zbadano (krok opcjonalny)"})
    if platform["state"] == "unavailable":
        gaps.append({"modality": "platformFlags", "code": "unavailable", "reason": "flaga płatnej promocji niesprawdzona"})
    if desc["state"] == "full" and tstate == "full":
        state = "full"
    elif desc["state"] == "full" or tstate in ("full", "partial"):
        state = "partial"
    elif desc["state"] == "fragment":
        state = "minimal"
    else:
        state = "none"
    names = {"full": "pełny", "fragment": "fragment", "empty": "brak", "unavailable": "niedostępny",
             "partial": "częściowo", "pending": "w kolejce"}
    frame_names = {"selected_moments": "wybrane momenty", "full": "pełne"}
    label = (f"Zbadano: opis ({names.get(desc['state'], desc['state'])}), "
             f"mowa ({'niezbadana' if tstate in ('unavailable', 'pending') else names.get(tstate, tstate)}), "
             f"kadry ({'niezbadane' if fstate == 'not_collected' else frame_names.get(fstate, fstate)})")
    return {"scope": "description+transcript", "state": state,
            "modalities": {"title": title, "description": desc, "transcript": transcript, "frames": frames,
                           "platformFlags": platform},
            "gaps": gaps, "blocksConclusion": state != "full", "label": label}


# --- Firm detection ------------------------------------------------------------------------
def _url_firm(url, firms):
    try:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
    except ValueError:
        return None, False
    for firm, _ in firms:
        for domain in firm["domains"]:
            if host == domain or host.endswith("." + domain):
                sub = host[: -len(domain)].rstrip(".").split(".")[-1] if host != domain else ""
                query = {k.lower() for k in parse_qs(parts.query)}
                tracking = sub in TRACK_SUBDOMAINS or bool(query & TRACK_QUERY) or bool(TRACK_PATH.search(parts.path))
                return firm, tracking
    return None, False


def _resolve_name(name, firms, outside):
    for firm, pattern in firms:
        if pattern.search(name):
            return ("firm", firm)
    for firm, pattern in outside:
        if pattern.search(name):
            return ("outside", firm)
    return ("unknown", name.strip(" „\"”«»'"))


class Firms:
    """Per-firm accumulation of relation signals."""

    def __init__(self):
        self.data = {}

    def entry(self, key, kind, ref):
        return self.data.setdefault(key, {"kind": kind, "ref": ref, "mentions": [], "disclosures": [], "commercial": [],
                                          "cta": [], "legalHits": set()})


SKIP_EFFECT = {"denial": "Autor zaprzecza współpracy, więc to zdanie nie liczy się jako ślad relacji z firmą.",
               "fraud_warning": "To ostrzeżenie przed oszustwami, więc to zdanie nie liczy się jako ślad relacji z firmą.",
               "neutral_context": "To pytanie lub neutralna wzmianka, więc to zdanie nie liczy się jako ślad relacji z firmą."}
SPEECH_PARTNER = re.compile(
    r"\bpartner\w*\s+(?:(?:tego|naszego|mojego|mego|dzisiejszego|niniejszego)\s+)?"
    r"(?:odcinka|kanału|programu|materiału|filmu|podcastu|nagrania|publikacji)\b"
    r"|\b(?:odcinek|materiał|film|wideo|nagranie)\s+(?:powstał\w*\s+)?(?:we współpracy|sponsorowan\w*)\b"
    r"|\bsponsorowan\w*\s+przez\b|\bto (?:jest )?reklama\b",
    re.I,
)
AFFILIATE_MENTION = re.compile(r"\blink\w*\s+(?:partnersk|afiliacyjn|polecając)\w*|\bprogram\w*\s+partnersk\w*", re.I)
EXPLICIT_AD = re.compile(r"reklam|sponsor|wsp[oó][łl]prac|#ad\b|materia[łl]\w*\s+promocyjn", re.I)
LINK_CALL = re.compile(r"\blink\w*\b[^.?!]{0,60}?\bw\s+(?:pierwszej\s+lini\w*\s+)?opisie\b|\bw\s+opisie\b[^.?!]{0,40}?\blink\w*", re.I)
SHORTENERS = {"bit.ly", "tinyurl.com", "rb.gy", "t.ly", "cutt.ly", "is.gd", "ow.ly", "goo.gl", "shorturl.at",
              "tiny.cc", "rebrand.ly", "bl.ink", "s.id", "buff.ly", "lnk.to", "linktr.ee"}
SPEECH_WINDOW = 5          # segments joined before matching, so boundaries of auto-captions do not matter
SPEECH_WINDOW_GAP = 10.0   # seconds; a larger gap (e.g. between transcript windows) ends a join


def disclosure_kind(text, modality=None):
    """Strength of a disclosure: platform flag, explicit ad label, affiliate link mention, partner mention."""
    if modality == "platform":
        return "platform_flag"
    if EXPLICIT_AD.search(text or ""):
        return "explicit_ad"
    if AFFILIATE_MENTION.search(text or "") or re.search(r"afiliac", text or "", re.I):
        return "affiliate_link_mention"
    return "partner_mention"


def _speech_joins(speech):
    """For each segment i: the join of segments i..i+4 (contiguous in time) and their units."""
    for i, unit in enumerate(speech):
        group = [unit]
        for nxt in speech[i + 1:i + SPEECH_WINDOW]:
            prev = group[-1]
            if (nxt.get("windowId") != prev.get("windowId")
                    or not isinstance(nxt.get("start"), (int, float)) or not isinstance(prev.get("end"), (int, float))
                    or nxt["start"] - prev["end"] > SPEECH_WINDOW_GAP):
                break
            group.append(nxt)
        yield i, group, " ".join(u["text"] for u in group)


def _joined_unit(group, start, end):
    """Unit made of the consecutive segments that a match [start, end) of the join touches."""
    used, offset = [], 0
    for unit in group:
        a, b = offset, offset + len(unit["text"])
        if a < end and b > start:
            used.append(unit)
        offset = b + 1
    if len(used) == 1:
        return used[0]
    return {**used[0], "text": " ".join(u["text"] for u in used), "end": used[-1].get("end"),
            "joinedSegments": [u["segment"] for u in used]}
SPOKEN_CODE = re.compile(r"(?i)\bkod\w*\s+(\w{4,})")


def _similar_code(token, code):
    """Auto-captions distort proper names (e.g. "Komparik" for COMPARIC)."""
    from difflib import SequenceMatcher
    norm = lambda s: s.lower().replace("k", "c").replace("w", "v")
    return SequenceMatcher(None, norm(token), norm(code)).ratio() >= 0.75


CLAUSE_SEPARATOR = re.compile(r"(?<=[.!?])\s+|\s*\b(?:ale|jednak|natomiast)\b\s*", re.I)


def _clauses(unit):
    """Split a line or segment into clauses, keeping absolute offsets and timing."""
    text, pieces, start = unit["text"], [], 0
    for sep in CLAUSE_SEPARATOR.finditer(text):
        if sep.start() > start:
            pieces.append((start, sep.start()))
        start = sep.end()
    if start < len(text):
        pieces.append((start, len(text)))
    for a, b in pieces or [(0, len(text))]:
        if text[a:b].strip():
            clause = {**unit, "text": text[a:b]}
            if "offset" in unit:
                clause["offset"] = unit["offset"] + a
            yield clause


def _skip_clause(text):
    stripped = text.strip()
    return bool(DENIAL.search(text) or FRAUD_CONTEXT.search(text) or FRAUD_REFERENCE.search(text) or stripped.endswith("?"))


def _scan_relations(units, firms, outside, ev, counter):
    acc = Firms()
    generic_disclosures = []
    paragraphs = {}
    for unit in units:
        paragraphs.setdefault(unit["paragraph"], []).append(unit)

    def para_firms(unit):
        found = []
        for other in paragraphs[unit["paragraph"]]:
            for firm, pattern in firms:
                if pattern.search(other["text"]) and firm not in found:
                    found.append(firm)
            for url in URL.findall(other["text"]):
                firm, _ = _url_firm(url, firms)
                if firm and firm not in found:
                    found.append(firm)
        return found

    speech = [u for u in units if u["modality"] == "transcript"]
    material_firms = []
    for firm, pattern in firms:
        if any(pattern.search(u["text"]) for u in units) or any(
                _url_firm(url, firms)[0] is firm for u in units for url in URL.findall(u["text"])):
            material_firms.append(firm)
    seen_speech = set()
    for position, group, joined in _speech_joins(speech):
        # Spoken disclosure in a sliding join of segments: "partnerem mojego kanału jest X",
        # "X, partnera tego odcinka", "materiał sponsorowany przez X", "z mojego linku partnerskiego".
        first_len = len(group[0]["text"])
        for pattern in (SPEECH_PARTNER, AFFILIATE_MENTION):
            for match in pattern.finditer(joined):
                if match.start() >= first_len:
                    continue  # counted from the segment where it starts
                near = joined[max(0, match.start() - 80):match.end() + 40]
                if DENIAL.search(near) or FRAUD_CONTEXT.search(near) or FRAUD_REFERENCE.search(near):
                    continue
                context_units = speech[max(0, position - 1):position] + group
                context = " ".join(u["text"] for u in context_units)
                offset = sum(len(u["text"]) + 1 for u in speech[max(0, position - 1):position])
                span = context[max(0, offset + match.start() - 60):offset + match.end() + 80]
                named_firms = [firm for firm, fpattern in firms if fpattern.search(span)]
                if not named_firms and NAMED_DECLARATION.search(span):
                    continue  # a disclosure naming another sponsor does not cover these firms; the main pass records it
                unit = _joined_unit(group, match.start(), match.end())
                key = (unit.get("segment"), pattern.pattern)
                if key in seen_speech:
                    continue
                seen_speech.add(key)
                evidence_id = ev.add(unit, 0, len(unit["text"]), "disclosure")
                affiliate = pattern is AFFILIATE_MENTION
                if not named_firms and affiliate:
                    if len(material_firms) == 1:  # "z mojego linku partnerskiego" in a film about exactly one firm
                        firm = material_firms[0]
                        entry = acc.entry(firm["key"], "firm", firm)
                        entry["disclosures"].append({"evidenceId": evidence_id, "modality": "transcript", "named": False})
                        entry["commercial"].append({"evidenceId": evidence_id, "kind": "affiliate_label", "modality": "transcript",
                                                    "detail": "link partnerski w mowie; jedyna firma w materiale"})
                        continue
                for firm in named_firms:
                    entry = acc.entry(firm["key"], "firm", firm)
                    entry["disclosures"].append({"evidenceId": evidence_id, "modality": "transcript", "named": True})
                    if affiliate:
                        entry["commercial"].append({"evidenceId": evidence_id, "kind": "affiliate_label", "modality": "transcript"})
                if not named_firms:
                    generic_disclosures.append({"evidenceId": evidence_id, "modality": "transcript", "paragraph": unit["paragraph"]})

    description_codes = {}
    for unit in (clause for line in units for clause in _clauses(line)):
        text = unit["text"]
        if unit["modality"] == "transcript":
            for spoken in SPOKEN_CODE.finditer(text):
                token = spoken.group(1)
                for code, firm in description_codes.items():
                    if _similar_code(token, code):
                        acc.entry(firm["key"], "firm", firm)["commercial"].append(
                            {"evidenceId": ev.add(unit, 0, len(text), "claim"), "kind": "creator_code", "modality": "transcript",
                             "detail": f"{token} ≈ {code}", "match": "approximate"})
        if _skip_clause(text):
            kind = "denial" if DENIAL.search(text) else "fraud_warning" if (FRAUD_CONTEXT.search(text) or FRAUD_REFERENCE.search(text)) else "neutral_context"
            counter.append({**ev.get(ev.add(unit, 0, len(text), "context")), "effect": SKIP_EFFECT[kind], "counterKind": kind})
            continue
        contact = bool(CONTACT_LINE.search(text))
        # Named disclosures: [reklama_X], "Partnerem odcinka jest X", "Link X wstawiamy w ramach płatnej współpracy".
        named = False
        for match in REKLAMA_TAG.finditer(text):
            name = (match.group("name") or "").replace("_", " ").strip()
            evidence_id = ev.add(unit, match.start(), len(text) if len(text) - match.start() < 200 else match.end(), "disclosure")
            if name:
                kind, ref = _resolve_name(name, firms, outside)
                key = ref["key"] if kind != "unknown" else "unknown:" + ref.lower()
                acc.entry(key, kind, ref)["disclosures"].append({"evidenceId": evidence_id, "modality": unit["modality"], "named": True})
                named = True
            else:
                generic_disclosures.append({"evidenceId": evidence_id, "modality": unit["modality"], "paragraph": unit["paragraph"]})
        for match in NAMED_DECLARATION.finditer(text):
            raw = next(g for g in match.groups() if g)
            kind, ref = _resolve_name(raw, firms, outside)
            if kind == "unknown":
                raw = re.sub(r"^\s*(?:broker\w*|firm\w*|mark\w*|platform\w*|dom maklerski)\s+", "", raw, flags=re.I)
                words = re.match(r"\s*((?:[A-ZŁŚŻŹĆŃÓĘĄ0-9][\w&.-]*\s?){1,4})", raw)
                if not words:
                    continue
                ref = words.group(1).strip()
            key = ref["key"] if kind != "unknown" else "unknown:" + ref.lower()
            evidence_id = ev.add(unit, match.start(), match.end(), "disclosure")
            acc.entry(key, kind, ref)["disclosures"].append({"evidenceId": evidence_id, "modality": unit["modality"], "named": True})
            named = True
        if not contact:
            for match in GENERIC_LABEL.finditer(text):
                if named and re.search(r"płatn|współprac|wstawiamy", match.group(), re.I):
                    continue
                attached = para_firms(unit) if re.search(r"link\w*\s+(?:partnersk|afiliacyjn|polecając)", match.group(), re.I) \
                    or any(p.search(text) for _, p in firms) else []
                evidence_id = ev.add(unit, match.start(), match.end(), "disclosure")
                if attached:
                    for firm in attached:
                        acc.entry(firm["key"], "firm", firm)["disclosures"].append(
                            {"evidenceId": evidence_id, "modality": unit["modality"], "named": False})
                else:
                    generic_disclosures.append({"evidenceId": evidence_id, "modality": unit["modality"], "paragraph": unit["paragraph"]})
                if re.search(r"link\w*\s+(?:partnersk|afiliacyjn)", match.group(), re.I):
                    for firm in attached:
                        acc.entry(firm["key"], "firm", firm)["commercial"].append(
                            {"evidenceId": evidence_id, "kind": "affiliate_label", "modality": unit["modality"]})
        # Mentions and legal-name hints.
        for firm, pattern in firms:
            match = pattern.search(text)
            if match:
                entry = acc.entry(firm["key"], "firm", firm)
                entry["mentions"].append(ev.add(unit, max(0, match.start() - 40), min(len(text), match.end() + 80), "context")
                                         if not entry["mentions"] else entry["mentions"][0])
                for legal, registry_id in firm.get("legal", {}).items():
                    if re.search(legal, text, re.I):
                        entry["legalHits"].add(registry_id)
            for cta in list(re.finditer(CTA, text, re.I)) + list(CTA_EXTRA.finditer(text)):
                mention = pattern.search(text)
                if mention and abs(mention.start() - cta.start()) <= 90:
                    entry = acc.entry(firm["key"], "firm", firm)
                    entry["cta"].append(ev.add(unit, min(mention.start(), cta.start()), min(len(text), max(mention.end(), cta.end()) + 40), "claim"))
                    break
        for firm, pattern in outside:
            match = pattern.search(text)
            if match:
                acc.entry(firm["key"], "outside", firm)["mentions"].append(ev.add(unit, match.start(), match.end(), "context"))
        # Commercial evidence: tracking links, creator codes, compensation statements.
        for match in URL.finditer(text):
            firm, tracking = _url_firm(match.group(), firms)
            if firm and tracking:
                acc.entry(firm["key"], "firm", firm)["commercial"].append(
                    {"evidenceId": ev.add(unit, match.start(), match.end(), "claim"), "kind": "tracking_link",
                     "modality": unit["modality"], "detail": urlsplit(match.group()).hostname})
            elif not firm:
                # Shortened link next to a firm name ("XTB: https://bit.ly/...") or naming it in the path.
                try:
                    host = (urlsplit(match.group()).hostname or "").lower()
                except ValueError:
                    host = ""
                if host.removeprefix("www.") in SHORTENERS:
                    before = text[max(0, match.start() - 80):match.start()]
                    for firm_, pattern in firms:
                        if pattern.search(before) or pattern.search(match.group()) or re.search(
                                re.escape(firm_["key"]), match.group(), re.I):
                            acc.entry(firm_["key"], "firm", firm_)["commercial"].append(
                                {"evidenceId": ev.add(unit, match.start(), match.end(), "claim"), "kind": "short_link",
                                 "modality": unit["modality"], "detail": host})
                            break
        line_firms = [f for f, p in firms if p.search(text)]
        for match in CODE.finditer(text):
            if not (CODE_CONTEXT.search(text) or unit["modality"] != "description" or line_firms):
                continue
            for firm in (para_firms(unit) if CODE_CONTEXT.search(text) else line_firms) if unit["modality"] == "description" \
                    else [f for f, p in firms if p.search(text)]:
                if unit["modality"] == "description":
                    description_codes[match.group("code")] = firm
                acc.entry(firm["key"], "firm", firm)["commercial"].append(
                    {"evidenceId": ev.add(unit, 0, len(text), "claim"), "kind": "creator_code",
                     "modality": unit["modality"], "detail": match.group("code")})
        for match in COMPENSATION.finditer(text):
            attached = para_firms(unit)
            evidence_id = ev.add(unit, 0, len(text), "claim")
            if attached:
                for firm in attached:
                    acc.entry(firm["key"], "firm", firm)["commercial"].append(
                        {"evidenceId": evidence_id, "kind": "compensation", "modality": unit["modality"]})
            elif GENERIC_FIRM.search(text):
                acc.entry("unknown:firma inwestycyjna", "generic", "firma inwestycyjna (nieustalona)")["commercial"].append(
                    {"evidenceId": evidence_id, "kind": "compensation", "modality": unit["modality"]})
    return acc, generic_disclosures


# --- Main function -------------------------------------------------------------------------
def _kind_names(commercial):
    return ", ".join(sorted({KIND_NAMES[c["kind"]] for c in commercial}))


def _searched(cov):
    """Where the material was searched, as readable phrases."""
    description, transcript = cov["modalities"]["description"], cov["modalities"]["transcript"]
    frames = cov["modalities"]["frames"]
    found = []
    if description["state"] != "empty":
        found.append("opis" + (" (tylko fragment)" if description["state"] == "fragment" else ""))
    if transcript["state"] not in ("unavailable", "pending"):
        found.append("mowa (" + ("cała transkrypcja" if transcript["state"] == "full" else "część transkrypcji") + ")")
    if frames["state"] != "not_collected":
        count = len(frames.get("moments") or [])
        found.append("kadry (" + (f"{count} wybranych momentów" if count else "wybrane momenty") + ")")
    return found


def _firm_block(entry):
    if entry["kind"] == "firm":
        firm = entry["ref"]
        candidates = [{k: c[k] for k in ("registryId", "name", "category", "sourceFile", "checkedAt")} for c in firm["candidates"]]
        if entry["legalHits"]:
            narrowed = [c for c in candidates if c["registryId"] in entry["legalHits"]]
            candidates = narrowed or candidates
        cross = {c["registryId"]: c["crossBorder"] for c in firm["candidates"]}
        if not candidates:
            status, reason = "no_registry_entry", "Brak wpisu w przejrzanych kopiach wykazów KNF (stan z 21.11.2026)."
        elif len(candidates) == 1:
            status, reason = "established", "Jeden pasujący wpis w wykazie KNF." if not entry["legalHits"] else "Nazwa prawna z materiału wskazuje jeden wpis w wykazie KNF."
        else:
            status, reason = "candidates", "Nazwa marki pasuje do kilku wpisów w wykazie KNF; materiał nie rozstrzyga, który podmiot ją prowadzi."
        flags = {cross[c["registryId"]] for c in candidates}
        return {"mention": firm["label"], "identityStatus": status, "candidates": candidates,
                "crossBorder": flags.pop() if len(flags) == 1 else "unresolved", "reason": reason, "inScope": True}
    if entry["kind"] == "outside":
        return {"mention": entry["ref"]["label"], "identityStatus": "unresolved", "candidates": [], "crossBorder": "unresolved",
                "reason": "Podmiot spoza zakresu M1: " + entry["ref"]["reason"] + ".", "inScope": False,
                "outOfScopeReason": entry["ref"]["reason"]}
    name = entry["ref"] if isinstance(entry["ref"], str) else str(entry["ref"])
    return {"mention": name, "identityStatus": "unresolved", "candidates": [], "crossBorder": "unresolved",
            "reason": "Nazwy nie dopasowano do żadnej firmy z używanego zestawu.", "inScope": None}


def _point_components(premise_type, unit_modality, method, confidence, cov, extras):
    components = [[BASE_LABELS[premise_type], BASE_POINTS[premise_type]], ["cytat dosłowny z miejscem w materiale", 5]]
    if unit_modality == "description":
        components.append(["opis autora", 10 if premise_type != "U1" else 5])
    elif method == "author_captions":
        components.append(["napisy autora", 10])
    elif confidence is None or confidence >= 0.8:
        components.append(["transkrypcja", 5])
    components.extend(extras)
    if cov["modalities"]["transcript"]["state"] == "full":
        components.append(["przeszukano pełną transkrypcję", 10])
    if cov["modalities"]["frames"]["state"] in ("selected_moments", "full"):
        components.append(["przeszukano kadry", 5])
    return components


def qualify(capture, finding=None, semantic=None, context=None):
    """Return M1 qualification fields. ``finding`` and ``semantic`` are accepted for the
    H call signature but do not change the result; E5 never adds points."""
    context = context or {}
    index = context.get("firmIndex") or _default_index()
    firms, outside = _compiled(index)
    cov = coverage(capture)
    ev = Evidence(capture)
    counter = []
    description = capture.get("description") or ""
    dunits = _description_units(description)
    sunits = _speech_units(capture)
    funits = _frame_units(capture)
    base = {"rulesVersion": RULES_VERSION, "coverage": cov}

    if not dunits and not sunits and not funits and not (capture.get("title") or "").strip():
        return {**base, "adRelationship": _relationship_none(capture, "unknown"), "adRegistry": {"state": "none"},
                "premises": [], "evidence": [], "counterEvidence": [],
                "reviewDecision": _decision("insufficient", "Materiał nie ma tytułu, opisu ani transkrypcji, więc nie ma czego oceniać.", missing=["opis lub transkrypcja"]),
                "reviewScore": _score(None, "brak treści do oceny")}

    acc, generic = _scan_relations(dunits + sunits + funits, firms, outside, ev, counter)
    platform = _platform_disclosure(capture, ev)
    if platform:
        generic.append(platform)

    # Relation status per firm.
    relations = []
    for key, entry in acc.data.items():
        named = [d for d in entry["disclosures"]]
        firm_block = _firm_block(entry) if entry["kind"] != "generic" else {
            "mention": entry["ref"], "identityStatus": "unresolved", "candidates": [], "crossBorder": "unresolved",
            "reason": "Materiał wskazuje firmę inwestycyjną bez podania nazwy.", "inScope": True}
        if entry["kind"] == "unknown":
            texts = " ".join(ev.get(d["evidenceId"])["text"] for d in entry["disclosures"])
            if INVESTMENT_CONTEXT.search(texts):
                firm_block.update(identityStatus="no_registry_entry", inScope=True,
                                  reason="Nazwy nie ma w używanym zestawie firm, a kontekst dotyczy usług inwestycyjnych; brak wpisu w przejrzanych wykazach KNF.")
            else:
                firm_block.update(inScope=False, outOfScopeReason="nierozpoznany reklamodawca bez kontekstu inwestycyjnego",
                                  reason="Podmiot spoza zakresu M1: nierozpoznany reklamodawca bez kontekstu inwestycyjnego.")
        if named:
            status, basis = "declared", "oznaczenie z nazwą firmy lub przy jej marce"
        elif platform and (entry["commercial"] or entry["cta"]):
            status, basis = "declared", "flaga płatnej promocji YouTube"
        elif entry["commercial"] and generic:
            status, basis = "declared", "oznaczenie ogólne przy dowodzie relacji handlowej"
        elif any(c["kind"] in ("compensation", "affiliate_label") for c in entry["commercial"]):
            status, basis = "documented", _kind_names(entry["commercial"])
        elif entry["commercial"]:
            # Contract v2 R3: a link or creator code alone is "probable" (register candidate); U1 still applies (J5).
            status, basis = "probable", _kind_names(entry["commercial"])
        elif entry["cta"]:
            status, basis = "probable", "zachęta do skorzystania przy nazwie firmy"
        else:
            status, basis = "none", "samo wymienienie marki"
        relations.append({"key": key, "entry": entry, "status": status, "basis": basis, "firm": firm_block})
    order = {"declared": 0, "documented": 1, "probable": 2, "none": 3}
    relations.sort(key=lambda r: (r["firm"].get("inScope") is False, order[r["status"]],
                                  -len(r["entry"]["commercial"])))

    all_disclosures = generic + [d for r in relations for d in r["entry"]["disclosures"]]
    premises = []

    # U1: documented commercial relation without any disclosure in the examined scope.
    for rel in relations:
        entry, firm = rel["entry"], rel["firm"]
        if not entry["commercial"] or firm.get("inScope") is False:
            continue
        own = entry["disclosures"]
        found = own + generic
        primary = max(entry["commercial"], key=lambda c: {"tracking_link": 3, "compensation": 2, "short_link": 2,
                                                          "creator_code": 1, "affiliate_label": 0}[c["kind"]])
        quote_item = ev.get(primary["evidenceId"])
        searched = _searched(cov)
        if found:
            if any(d["modality"] == "description" for d in found):
                continue  # disclosed in the description: register only, no premise
            status = "refuted"
        else:
            status = "documented"
        extras = []
        kinds = {c["kind"] for c in entry["commercial"]}
        if "tracking_link" in kinds:
            extras.append(["link polecający w domenie firmy", 15])
        if "creator_code" in kinds:
            extras.append(["kod twórcy przy rejestracji", 10])
        if "short_link" in kinds:
            extras.append(["skrócony link przy nazwie firmy", 10])
        if "compensation" in kinds:
            extras.append(["deklaracja wynagrodzenia", 15])
        if cov["modalities"]["description"]["state"] == "full":
            extras.append(["pełny opis bez oznaczenia", 5])
        components = _point_components("U1", quote_item["modality"], quote_item.get("method"), quote_item.get("confidence"), cov, extras)
        points = 0 if status == "refuted" else min(100, sum(p for _, p in components))
        premises.append(_premise(
            "U1", f"Są ślady relacji handlowej z {firm['mention']} ({rel['basis']}), a w zbadanym zakresie nie znaleziono oznaczenia reklamy.",
            quote_item, status, components, points,
            requires=["ślad relacji handlowej (link polecający, kod twórcy lub wynagrodzenie)", "brak oznaczenia reklamy w opisie, w mowie i w kadrach"],
            satisfied=status == "documented", searched=searched,
            found=[ev.get(d["evidenceId"])["text"] for d in found], firm=firm, commercial=entry["commercial"]))

    # U3: in-scope relation with a firm missing from the reviewed registers.
    for rel in relations:
        firm = rel["firm"]
        if rel["status"] in ("declared", "documented", "probable") and firm.get("inScope") \
                and firm.get("identityStatus") == "no_registry_entry":
            named_first = sorted(rel["entry"]["disclosures"], key=lambda d: not d["named"])
            refs = named_first or rel["entry"]["commercial"] or [{"evidenceId": e} for e in rel["entry"]["cta"]]
            if not refs:
                continue
            item = ev.get(refs[0]["evidenceId"])
            components = [[BASE_LABELS["U3"], BASE_POINTS["U3"]], ["cytat dosłowny z miejscem w materiale", 5]]
            premises.append(_premise(
                "U3", f"Promowany podmiot {firm['mention']} bez wpisu w przejrzanych kopiach wykazów.", item, "conditional",
                components, min(CONDITIONAL_CAP, sum(p for _, p in components)),
                requires=["sprawdzenie aktualnych wykazów KNF i ESMA dla tej nazwy prawnej"], satisfied=False,
                searched=["wykazy KNF: domy maklerskie, banki prowadzące działalność maklerską, notyfikacje zagranicznych firm, "
                          "oddziały zagranicznych firm (kopie z " + _stamp(index.get("checkedAt", "")).split(" ")[0] + ")"],
                found=[], firm=firm))

    # U4–U6: claims about the product of a firm with a declared/documented relation.
    related = {r["entry"]["ref"]["key"]: r for r in relations
               if r["entry"]["kind"] == "firm" and r["status"] in ("declared", "documented") and r["firm"].get("inScope")}
    mentioned = {r["entry"]["ref"]["key"]: r for r in relations if r["entry"]["kind"] == "firm"}
    for unit in dunits + sunits:
        text = unit["text"]
        if _skip_clause(text):
            continue
        claims = []
        g = GUARANTEE.search(text)
        if g and not GUARANTEE_DENIAL.search(text):
            claims.append(("U5", g))
        s = SUPERVISION.search(text)
        if s:
            claims.append(("U6", s))
        p = PROFIT.search(text)
        if p and not g:
            claims.append(("U4", p))
        for premise_type, match in claims:
            firm_keys = [k for k, (f, pat) in ((f["key"], (f, pat)) for f, pat in firms) if pat.search(text)]
            in_related = [k for k in firm_keys if k in related]
            if not firm_keys and len(related) == 1 and PRODUCT_ANAPHORA.search(text):
                firm_keys = in_related = list(related)
            evidence_id = ev.add(unit, 0, len(text), "claim")
            item = ev.get(evidence_id)
            if not firm_keys:
                continue  # general statement, not about a promoted product
            if not in_related:
                premises.append(_premise(premise_type, "Twierdzenie o firmie bez ustalonej relacji reklamowej (opinia twórcy).",
                                         item, "out_of_scope_m1", [], 0, requires=["relacja zadeklarowana lub udokumentowana"],
                                         satisfied=False, searched=[], found=[], firm=mentioned[firm_keys[0]]["firm"]))
                continue
            rel = related[in_related[0]]
            warnings = _nearby_warnings(unit, dunits, sunits, ev) if premise_type == "U4" else []
            transcript_full = cov["modalities"]["transcript"]["state"] == "full"
            if warnings:
                status = "refuted"
            elif transcript_full:
                status = "documented"
            else:
                status = "conditional"
            components = _point_components(premise_type, unit["modality"], unit.get("method"), unit.get("confidence"), cov,
                                           [["relacja z firmą: " + RELATION_NAMES.get(rel["status"], rel["status"]), 5]])
            points = sum(p for _, p in components)
            if status == "conditional":
                points = min(points, CONDITIONAL_CAP)
            if status == "refuted":
                points = 0
            for w in warnings:
                counter.append({**ev.get(w), "effect": "Obok twierdzenia jest ostrzeżenie o ryzyku, więc nie ma przesłanki do kontroli.", "counterKind": "risk_warning"})
            premises.append(_premise(premise_type, LABELS[premise_type] + f" ({rel['firm']['mention']}).", item, status, components,
                                     points, requires=BASIS[premise_type]["transfer"].split("; "), satisfied=status == "documented",
                                     searched=[cov["label"]], found=[ev.get(w)["text"] for w in warnings], firm=rel["firm"]))

    # U7: personalised advice cue, handed to M3.
    for unit in dunits + sunits:
        if re.search(ADVICE, unit["text"], re.I) and not re.search(NO_ADVICE, unit["text"], re.I):
            m = re.search(ADVICE, unit["text"], re.I)
            item = ev.get(ev.add(unit, m.start(), m.end(), "context"))
            premise = _premise("U7", "Sygnał oferty indywidualnej rekomendacji; do oceny w M3.", item, "out_of_scope_m1", [], 0,
                               requires=["ocena w module M3"], satisfied=False, searched=[], found=[], firm=None)
            premise["handoff"] = "M3"
            premises.append(premise)

    for d in all_disclosures:
        counter.append({**ev.get(d["evidenceId"]), "effect": "Materiał jest oznaczony jako reklama lub współpraca w zbadanym zakresie.", "counterKind": "disclosure_present"})

    primary = relations[0] if relations else None
    relationship = _relationship(capture, primary, cov, all_disclosures, ev) if primary else _relationship_none(capture, "none")
    registry = _registry(capture, primary, ev, all_disclosures)
    decision, score = _route(capture, cov, primary, relations, premises, ev, all_disclosures)
    extra_relations = [{"status": r["status"], "basis": r["basis"], "firm": r["firm"],
                        "adRegistry": _registry(capture, r, ev, all_disclosures)["state"]} for r in relations[1:]]
    return {**base, "adRelationship": relationship, "relationships": extra_relations, "adRegistry": registry,
            "premises": premises, "evidence": ev.items, "counterEvidence": counter,
            "reviewDecision": decision, "reviewScore": score}


WARNING_WINDOW_SECONDS = 60  # team method for "bezpośrednio towarzyszy" in speech


def _nearby_warnings(unit, dunits, sunits, ev):
    """Risk information in the same description paragraph or within ±60 s of speech."""
    if unit["modality"] == "description":
        pool = [u for u in dunits if u["paragraph"] == unit["paragraph"]]
    else:
        pool = [u for u in sunits if u.get("start") is not None and unit.get("start") is not None
                and abs(u["start"] - unit["start"]) <= WARNING_WINDOW_SECONDS]
    found = []
    for other in pool:
        match = RISK_WARNING.search(other["text"])
        if match:
            found.append(ev.add(other, 0, len(other["text"]), "context"))
    return found


def _premise(ptype, claim, item, status, components, points, *, requires, satisfied, searched, found, firm, commercial=None):
    premise = {"id": f"pr-{ptype}-{item['id']}", "type": ptype, "claim": claim, "quote": item["text"], "evidenceRef": item["id"],
               "basis": BASIS[ptype], "scope": {"requires": requires, "satisfied": satisfied},
               "counterEvidence": {"searched": searched, "found": found, "possibleExplanations": EXPLANATIONS[ptype]},
               "status": status, "strength": {"points": points, "components": components}, "legalStatus": "review_premise"}
    if firm:
        premise["firm"] = {"mention": firm["mention"], "identityStatus": firm["identityStatus"],
                           "candidates": [c["registryId"] for c in firm["candidates"]]}
    if commercial:
        premise["relationEvidence"] = [{"kind": c["kind"], "evidenceId": c["evidenceId"], "modality": c.get("modality"),
                                        "match": c.get("match", "verbatim"),
                                        **({"detail": c["detail"]} if c.get("detail") else {})} for c in commercial]
    return premise


def _platform_disclosure(capture, ev):
    """YouTube paid-promotion flag = disclosure at platform level. Only ``True`` counts:
    ``False`` or ``None`` (not collected) proves nothing."""
    youtube = capture.get("youtube") if isinstance(capture.get("youtube"), dict) else {}
    if youtube.get("paidPromotionFlag") is not True:
        return None
    read_at = youtube.get("observedAt") or youtube.get("readAt") or capture.get("observedAt")
    text = "YouTube oznacza film jako płatną promocję" + (f" (odczyt z {_stamp(read_at)})" if read_at else "")
    evidence_id = ev.add({"modality": "platform", "text": text, "paragraph": "platform", "method": "youtube_api"},
                         0, len(text), "disclosure")
    item = ev.get(evidence_id)
    item.update(kind="platform", match="verbatim", field="youtube.paidPromotionFlag", readAt=read_at)
    return {"evidenceId": evidence_id, "modality": "platform", "paragraph": "platform"}


def _relationship_none(capture, status):
    return {"status": status, "basis": None, "signalScore": 0,
            "advertiser": {"creatorId": capture.get("creatorId"), "handle": capture.get("creatorName")},
            "firm": None, "disclosure": {"state": "not_checked", "where": None, "text": None, "evidenceId": None,
                                         "checked": [], "notChecked": [],
                                         "summary": "Nie ustalono relacji z firmą, więc nie szukano oznaczenia."},
            "language": _language(capture), "evidenceRefs": []}


def _language(capture):
    lang = capture.get("language") if isinstance(capture.get("language"), dict) else {}
    value = lang.get("detected") or lang.get("declared")
    if value:
        return {"value": value, "method": lang.get("method", "źródło")}
    text = " ".join(filter(None, [capture.get("title"), capture.get("description")]))
    polish = len(re.findall(r"[ąćęłńóśźż]", text, re.I)) + \
        len(re.findall(r"\b(?:jest|się|nie|oraz|że|jak|dla|odcinka|przez|akcje|inwestuj\w*)\b", text, re.I))
    return {"value": "pl" if polish >= 3 else None,
            "method": "heurystyka: polskie znaki i słowa funkcyjne w tytule i opisie"}


def _relationship(capture, rel, cov, disclosures, ev):
    modalities = {"description": "in_description", "transcript": "in_speech", "frame": "in_frame", "platform": "platform_flag"}
    own = rel["entry"]["disclosures"] or disclosures
    checked = [m for m, key in (("description", "description"), ("transcript", "transcript"), ("frames", "frames"))
               if cov["modalities"][key]["state"] not in ("unavailable", "pending", "not_collected", "empty")]
    not_checked = [m for m in ("description", "transcript", "frames", "platformFlags") if m not in checked
                   and not (m == "platformFlags" and cov["modalities"]["platformFlags"]["state"] == "observed")]
    if own:
        rank = {"description": 0, "transcript": 1, "frame": 2}
        first = ev.get(min(own, key=lambda d: rank.get(d["modality"], 3))["evidenceId"])
        disclosure = {"state": modalities[first["modality"]], "where": first["modality"], "text": first["text"],
                      "evidenceId": first["id"], "checked": checked, "notChecked": not_checked,
                      "kind": disclosure_kind(first["text"], first["modality"]),
                      "kinds": sorted({disclosure_kind(ev.get(d["evidenceId"])["text"], d["modality"]) for d in own})}
        disclosure["summary"] = _disclosure_sentence(first, disclosure["kind"])
    else:
        disclosure = {"state": "not_found_in_scope" if checked else "not_checked", "where": None, "text": None,
                      "evidenceId": None, "checked": checked, "notChecked": not_checked,
                      "summary": "Nie znaleziono oznaczenia reklamy w zbadanym zakresie." if checked
                      else "Nie sprawdzono, czy materiał jest oznaczony jako reklama."}
    signal = {"declared": 94, "documented": 80, "probable": 60, "none": 20}[rel["status"]]
    refs = [d["evidenceId"] for d in rel["entry"]["disclosures"]] + [c["evidenceId"] for c in rel["entry"]["commercial"]] \
        + rel["entry"]["cta"] + rel["entry"]["mentions"][:1]
    status = rel["status"] if rel["firm"].get("inScope") is not False else "none" if rel["status"] == "none" else rel["status"]
    return {"status": status, "basis": rel["basis"], "signalScore": signal,
            "advertiser": {"creatorId": capture.get("creatorId"), "handle": capture.get("creatorName")},
            "firm": rel["firm"], "disclosure": disclosure, "language": _language(capture), "evidenceRefs": list(dict.fromkeys(refs))}


def _registry(capture, rel, ev=None, disclosures=()):
    if not rel or rel["firm"].get("inScope") is False:
        return {"state": "none"}
    state = {"declared": "included", "documented": "included", "probable": "candidate"}.get(rel["status"], "none")
    if state == "none":
        return {"state": "none"}
    registry = {"state": state, "campaignKey": f"{capture.get('creatorId')}|{rel['firm']['mention']}",
                "firstObservedAt": capture.get("observedAt")}
    own = rel["entry"]["disclosures"] or list(disclosures)
    if ev is not None and own:
        kinds = [disclosure_kind(ev.get(d["evidenceId"])["text"], d["modality"]) for d in own]
        order = ["explicit_ad", "platform_flag", "affiliate_link_mention", "partner_mention"]
        registry["disclosureKind"] = min(kinds, key=order.index)
        first = ev.get(own[0]["evidenceId"])
        registry["summary"] = _disclosure_sentence(first, registry["disclosureKind"])
    elif state == "candidate":
        registry["summary"] = (f"Prawdopodobna relacja z {rel['firm']['mention']}, do potwierdzenia ({rel['basis']}); "
                               "oznaczenia nie znaleziono.")
    else:
        registry["summary"] = (f"Udokumentowana relacja z {rel['firm']['mention']} ({rel['basis']}) "
                               "bez oznaczenia w zbadanym zakresie.")
    return registry


def _score(value, reason=None, components=None):
    band = None if value is None else "strong" if value >= 75 else "moderate" if value >= 60 else "weak"
    return {"state": "computed" if value is not None else "withheld", "value": value, "scale": "0-100", "band": band,
            "meaning": SCALE_MEANING, "notComputableReason": reason, "rulesVersion": RULES_VERSION, "modelVersion": None,
            "components": components or []}


def _decision(route, reason, *, reasons=None, moments=None, complete_reason=None, requirement=None, claim=None,
              alternative=None, missing=None):
    return {"route": route, "reason": reason[:160], "reasons": reasons or [], "moments": moments or [],
            "completeReason": complete_reason, "requirement": requirement, "claim": claim, "alternative": alternative,
            "missing": missing or [], "decidedBy": "rules", "version": RULES_VERSION, "queueEligible": None}


def _moment(item, label):
    moment = {"start": item.get("start"), "end": item.get("end"), "label": label,
              "deepLink": item.get("sourceUrlAtTime") or item.get("url"), "evidenceId": item["id"],
              **({"locator": item["locator"]} if item.get("locator") else {})}
    # A description quote has no time: it is a text moment located by the description locator.
    moment["kind"] = "text" if item.get("locator") else "time" if item.get("start") is not None else "platform"
    return moment


def _link_call(capture, ev):
    """First spoken call to the description links ("linki ... w opisie"), as a time moment."""
    speech = _speech_units(capture)
    for _, group, joined in _speech_joins(speech):
        match = LINK_CALL.search(joined)
        if match and match.start() < len(group[0]["text"]):
            unit = _joined_unit(group, match.start(), match.end())
            return ev.get(ev.add(unit, 0, len(unit["text"]), "context"))
    return None


def _not_found_sentence(cov):
    description, transcript = cov["modalities"]["description"], cov["modalities"]["transcript"]
    frames, platform = cov["modalities"]["frames"], cov["modalities"]["platformFlags"]
    places = []
    if description["state"] == "full":
        places.append("w opisie")
    elif description["state"] == "fragment":
        places.append("w zbadanym fragmencie opisu")
    if transcript["state"] == "full":
        windows = [w for w in transcript.get("windows") or [] if isinstance(w, dict)]
        starts = [w["start"] for w in windows if isinstance(w.get("start"), (int, float))]
        ends = [w["end"] for w in windows if isinstance(w.get("end"), (int, float))]
        span = f" ({_clock(math.floor(min(starts)))}–{_clock(math.ceil(max(ends)))})" if starts and ends else \
            f" (0:00–{_clock(transcript['durationSec'])})" if transcript.get("durationSec") else ""
        places.append("w całej transkrypcji" + span)
    elif transcript["state"] == "partial":
        places.append("w zbadanej części transkrypcji")
    count = len(frames.get("moments") or [])
    if count:
        places.append(f"w {count} sprawdzon" + ("ym kadrze" if count == 1 else "ych kadrach"))
    where = places[0] if len(places) == 1 else ", ".join(places[:-1]) + " ani " + places[-1] if places else "w zbadanym zakresie"
    sentence = f"Nie znaleziono oznaczenia reklamy ani współpracy: {where}."
    if platform["state"] == "observed":
        sentence += " YouTube nie oznacza filmu jako płatnej promocji."
    return sentence


def _where(item):
    if item["modality"] == "description":
        return "w opisie"
    if item["modality"] == "frame":
        return f"w kadrze ({_clock(item.get('start'))})"
    if item["modality"] == "platform":
        return "w danych YouTube"
    return f"w mowie ({_clock(item.get('start'))})"


def _relation_sentence(lead, ev):
    """What points to a relation with the firm, grouped by place (description, speech, frame)."""
    mention = (lead.get("firm") or {}).get("mention")
    groups = {}
    for rel_ev in lead.get("relationEvidence", []):
        item = ev.get(rel_ev["evidenceId"])
        if rel_ev["kind"] == "tracking_link":
            phrase = f"link polecający {mention}"
        elif rel_ev["kind"] == "short_link":
            phrase = f"skrócony link przy nazwie {mention}"
        elif rel_ev["kind"] == "creator_code":
            code = str(rel_ev.get("detail") or "").split("≈")[-1].strip()
            phrase = f"kod twórcy „{code}”" if code else "kod twórcy"
        else:
            phrase = KIND_NAMES[rel_ev["kind"]]
        group = groups.setdefault(item["modality"], {"phrases": [], "start": item.get("start")})
        if phrase not in group["phrases"]:
            group["phrases"].append(phrase)
    sentences = []
    for modality, group in groups.items():
        listed = _join(group["phrases"][:4])
        if modality == "description":
            sentences.append(f"W opisie filmu jest {listed}.")
        elif modality == "frame":
            sentences.append(f"W kadrze ({_clock(group['start'])}) widać: {listed}.")
        else:
            sentences.append(f"W mowie ({_clock(group['start'])}) słychać: {listed}.")
    return " ".join(sentences) or f"Materiał wskazuje relację handlową z {mention}."


def _firm_sentence(firm, relation_kinds):
    mention = firm.get("mention")
    status, candidates = firm.get("identityStatus"), firm.get("candidates") or []
    names = [f"{c['name']} ({CATEGORY_NAMES.get(c['category'], c['category'])})" for c in candidates]
    if status == "established" and names:
        return f"{mention} — w wykazie KNF jest jeden pasujący podmiot: {names[0]}."
    if status == "candidates" and names:
        subject = "link" if relation_kinds & {"tracking_link", "short_link"} else "materiał"
        count = ({2: "dwa", 3: "trzy", 4: "cztery"}.get(len(names)), len(names))
        head = f"są {count[0]} pasujące podmioty" if count[0] else f"jest {count[1]} pasujących podmiotów"
        return f"{mention} — w wykazie KNF {head}: {_join(names)}; nie ustalono, którego dotyczy {subject}."
    if status == "no_registry_entry":
        return f"{mention} — nie znaleziono pasującego wpisu w przejrzanych wykazach KNF; to nie dowodzi, że firma działa bez uprawnień."
    return f"{mention} — nie ustalono, o jaki podmiot z wykazu chodzi."


def _not_examined_sentence(cov):
    clauses = []
    for gap in cov["gaps"]:
        code, modality = gap["code"], gap["modality"]
        if modality == "description" and code == "fragment":
            clauses.append("opis zbadano tylko we fragmencie")
        elif modality == "transcript":
            clauses.append("mowę zbadano tylko częściowo" if code == "partial" else "treści mowy nie zbadano")
        elif modality == "frames":
            clauses.append("kadrów nie sprawdzono (krok opcjonalny)")
        elif modality == "platformFlags":
            clauses.append("nie sprawdzono, czy YouTube oznacza film jako płatną promocję")
    if not clauses:
        return None
    return _upper(_join(clauses)) + "; oznaczenie mogło paść w którymś z tych miejsc."


def _disclosure_sentence(item, kind):
    """Register wording: how the cooperation was disclosed and where."""
    if item["modality"] == "platform":
        return "YouTube oznacza film jako płatną promocję."
    quote, where = _quote(item["text"]), _where(item)
    lead = {"explicit_ad": "Reklama lub współpraca oznaczona", "affiliate_link_mention": "Link partnerski ujawniony"}.get(
        kind, "Współpraca ujawniona")
    return f"{lead} {where}: {quote}."


def _route(capture, cov, primary, relations, premises, ev, disclosures):
    documented = [p for p in premises if p["status"] == "documented"]
    conditional = [p for p in premises if p["status"] == "conditional"]
    refuted = [p for p in premises if p["status"] == "refuted"]
    transcript = cov["modalities"]["transcript"]["state"]
    if documented:
        documented.sort(key=lambda p: p["strength"]["points"], reverse=True)
        lead = documented[0]
        item = ev.get(lead["evidenceRef"])
        value = min(100, lead["strength"]["points"] + 5 * (len(documented) - 1))
        moments = [_moment(item, LABELS[lead["type"]])]
        rel = next((r for r in relations if r["firm"]["mention"] == (lead.get("firm") or {}).get("mention")), None)
        firm = rel["firm"] if rel else lead.get("firm") or {}
        if lead["type"] == "U1":
            reasons = [_relation_sentence(lead, ev)]
            for rel_ev in lead.get("relationEvidence", [])[1:3]:
                other = ev.get(rel_ev["evidenceId"])
                if other["id"] != item["id"]:
                    moments.append(_moment(other, "Dowód relacji handlowej"))
            reasons.append(_not_found_sentence(cov))
            if all(m["start"] is None for m in moments):
                call = _link_call(capture, ev)
                if call is not None:
                    moments.append(_moment(call, "Wezwanie w mowie do linku w opisie"))
            reasons.append(_firm_sentence(firm, {c["kind"] for c in lead.get("relationEvidence", [])}))
        else:
            status = RELATION_NAMES.get(rel["status"]) if rel else None
            reasons = [f"{LABELS[lead['type']]}: {_quote(item['text'])} ({_where(item)}).",
                       f"Twórca ma relację reklamową z firmą {firm.get('mention')}" + (f" ({status})" if status else "")
                       + ", a twierdzenie dotyczy jej produktu.",
                       "Obok twierdzenia nie znaleziono ostrzeżenia o ryzyku: ani w tym samym akapicie opisu, ani w mowie w odstępie do minuty."
                       if lead["type"] == "U4" else "W zbadanym zakresie nie znaleziono zastrzeżenia, które łagodziłoby tę wypowiedź."]
        examined = _not_examined_sentence(cov)
        if examined:
            reasons.append(examined)
        reasons.append("Możliwe niewinne wyjaśnienie: " + "; ".join(lead["counterEvidence"]["possibleExplanations"]) + ".")
        reasons = reasons[:5]
        if len(reasons) < 3 or not moments:
            return (_decision("insufficient", "Przesłanka nie ma wymaganego uzasadnienia lub wskazanego momentu dowodu.",
                              missing=["reasons", "moments"]), _score(None, "brak uzasadnienia skierowania"))
        missing = []
        if transcript != "full":
            missing.append("transkrypcja mowy")
        if cov["modalities"]["frames"]["state"] == "not_collected":
            missing.append("kadry z momentów dowodu (opcjonalnie)")
        decision = _decision(
            "refer", f"{LABELS[lead['type']]}: przesłanka do kontroli przez analityka.",
            reasons=reasons, moments=moments,
            requirement={"module": "M1", "id": lead["type"], "label": LABELS[lead["type"]], "scope": lead["basis"]["transfer"]},
            claim={"text": item["text"], "evidenceId": item["id"]}, alternative=_upper("; ".join(lead["counterEvidence"]["possibleExplanations"])) + ".",
            missing=missing)
        return decision, _score(value, components=lead["strength"]["components"])
    if not primary:
        if transcript == "full" and cov["modalities"]["description"]["state"] in ("full", "empty"):
            return _decision("no_signal", "Nie znaleziono relacji reklamowej z firmą inwestycyjną w opisie i mowie."), _score(0)
        return (_decision("no_signal", "Nie znaleziono relacji reklamowej z firmą inwestycyjną w zbadanym zakresie.",
                          missing=["transkrypcja mowy"] if transcript != "full" else []),
                _score(None, "wniosek o braku sygnału wymaga opisu i pełnej transkrypcji"))
    firm = primary["firm"]
    if firm.get("inScope") is False and not any(r["firm"].get("inScope") for r in relations):
        return _decision("no_signal", "Reklamowany podmiot spoza zakresu M1: " + firm.get("outOfScopeReason", "") + "."), _score(0)
    in_scope = [r for r in relations if r["firm"].get("inScope") is not False and r["status"] != "none"]
    if conditional:
        lead = max(conditional, key=lambda p: p["strength"]["points"])
        reason_code = "identity_unresolved" if lead["type"] == "U3" else (
            "transcript_pending" if transcript == "pending" else "transcript_unavailable" if transcript == "unavailable" else "other_gap")
        missing = ["aktualny wpis w wykazie dla " + lead["firm"]["mention"]] if lead["type"] == "U3" else ["pełna transkrypcja mowy"]
        return (_decision("complete", f"{LABELS[lead['type']]}: trzeba uzupełnić dane przed oceną.", complete_reason=reason_code,
                          missing=missing, claim={"text": lead["quote"], "evidenceId": lead["evidenceRef"]}),
                _score(lead["strength"]["points"], components=lead["strength"]["components"]))
    if in_scope and cov["state"] != "full" and not refuted:
        state = in_scope[0]["status"]
        gap = "treści mowy nie zbadano, więc nie wiadomo, czy materiał budzi zastrzeżenia" if transcript != "full" else "zbadano tylko fragment opisu"
        missing = (["pełna transkrypcja mowy"] if transcript != "full" else []) + \
                  (["pełny opis"] if cov["modalities"]["description"]["state"] == "fragment" else [])
        return (_decision("complete", f"Jest relacja reklamowa ({RELATION_NAMES.get(state, state)}) z {in_scope[0]['firm']['mention']}, ale {gap}.",
                          complete_reason="transcript_pending" if transcript == "pending" else
                          "transcript_unavailable" if transcript == "unavailable" else "other_gap",
                          missing=missing),
                _score(None, "wniosek o braku przesłanki wymaga pełnego opisu i pełnej transkrypcji"))
    if refuted and any(p["type"] == "U1" for p in refuted):
        return _decision("no_signal", "Współpraca jest oznaczona w mowie, w kadrze lub w danych YouTube, więc nie ma przesłanki do kontroli; film trafia tylko do rejestru reklam."), _score(0)
    if in_scope:
        return _decision("no_signal", "Jest relacja reklamowa, ale w opisie i mowie nie znaleziono przesłanki do kontroli; film trafia tylko do rejestru reklam."), _score(0)
    return (_decision("no_signal", "Firma jest tylko wymieniona, bez śladów relacji reklamowej; materiał nie trafia do kolejki M1."),
            _score(0 if transcript == "full" else None, None if transcript == "full" else "mowy nie zbadano w pełnym zakresie"))


def priority(reach, relation=None):
    """Order of acquisition and review. Never changes route, score or queues (contract R4)."""
    metrics = (reach or {}).get("metrics") or {}
    views = (metrics.get("viewCount") or {}).get("value")
    if not isinstance(views, (int, float)) or views < 0:
        return {"review": {"rank": None}, "basis": "reach", "affectsDecision": False}
    return {"review": {"rank": round(math.log10(views + 1), 3)}, "basis": "reach", "affectsDecision": False}
