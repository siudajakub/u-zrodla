"""M3: read a public advisory offer on four axes and match its operator to dated KNF lists.

Usage:
  python -m analysis.offers registers --out DIR   # one-off refresh of the KNF lists (network)
  python -m analysis.offers analyze RAW_DIR        # offline analysis of a saved discovery run

The four axes follow Temat 3 (art. 76 and art. 2-3 of the Act on trading in financial instruments):
action (buy / sell / hold or an equivalent act), personalisation (the client's situation), instrument
(the statutory catalogue versus products outside it) and market (an offer addressed to clients in
Poland). Every axis carries a verbatim quote with a locator and the counter-evidence found on the same
pages. The route says what the analyst should do next. It never states a violation: a missing register
entry is not proof of a missing authorisation, so the wording is "uprawnienia do ustalenia".
"""

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
import time
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
KNF = ROOT / "data" / "probe-snapshots" / "knf"
M3_REGISTERS = ROOT / "fixtures" / "raw" / "discovery" / "m3-2026-11-21" / "registers"
RULES_VERSION = "m3-offers-1"

# --- Axis patterns ---------------------------------------------------------------------------------
# Patterns are matched clause by clause on the saved page text. Each label is plain Polish for the desk.

ACTION = [
    ("hold", "rekomendacja „trzymaj”",
     r"\b(?:(?:trzym|utrzym)\w* (?:\w+ ){0,2}(?:akcj|spółk|pozycj|walor|obligac|ETF|fundusz|jednost|certyfikat|instrument|papier)\w*|"
     r"kup\w*\s*[/,]\s*(?:sprzedaj\w*\s*[/,]\s*)?trzymaj|rekomendacj\w*\W{1,3}(?:„|\")?trzymaj|pozostać w (?:spółce|pozycji|akcjach)|nie sprzedawać)\b"),
    ("buy_sell", "rekomendacja kupna lub sprzedaży",
     r"\b(?:co (?:kupić|sprzedać)|kiedy (?:kupić|sprzedać|kupować|sprzedawać)|sygnał\w* (?:kupna|sprzedaży|transakcyjn|wejści|wyjści)\w*|"
     r"(?:kupuj|sprzedaj|sprzedawaj)\b|rekomendacj\w* (?:kupna|sprzedaży|zakupu|inwestycyjn\w*)|rekomendujemy (?:zakup|kupno|sprzedaż|akcj|spółk|fundusz|ETF|obligac)\w*|polecamy (?:zakup|sprzedaż|kupno) (?:akcj|spółk|ETF|obligac|jednost|instrument|fundusz)\w*|"
     r"podpowiad\w* (?:co|jakie|które)|wskaż\w* (?:konkretne |jakie )?(?:spółki|akcje|fundusze|instrumenty|ETF)|"
     r"alert\w* (?:kupna|sprzedaży|transakcyjn)\w*|powiadomieni\w* o (?:transakcj|zakup|sprzedaż)\w*|"
     r"(?:otwarcie|zamknięcie) pozycji|(?:typy|typujemy) (?:spółek|akcji))"),
    ("equivalent", "czynność o równoważnych skutkach",
     r"\b(?:subskrybuj\w* (?:jednostk|certyfikat|obligac)\w*|zapis\w* na (?:akcje|obligacje|certyfikaty)|(?:obejm|obj[ąę]|obejmow)\w* (?:akcj|obligac|certyfikat)\w*|"
     r"zamian\w* (?:jednostek|funduszu|funduszy)|konwersj\w* (?:jednostek|funduszu|funduszy|między)|przenie\w* (?:środk\w* )?(?:do|między) (?:fundusz|subfundusz)\w*|"
     r"wykup\w* (?:jednostek|certyfikat|obligac)\w*|odkup\w* (?:jednostek|certyfikat)\w*|rebalansowani\w*|przebudow\w* portfel\w*|"
     r"(?:skład|struktur\w*|alokacj\w*) portfel\w* (?:dla (?:ciebie|klienta|pana|pani|państwa)|dopasowan)\w*|portfel\w* (?:modelow|rekomendowan|wzorcow)\w*|"
     r"kopiow\w* transakcj\w*|copy ?trading|subskryb\w* (?:i kopiow\w* )?(?:sygnał|transakcj)\w*|sygnał\w* handlow\w*|zmian\w* (?:w )?(?:składzie |alokacji )?portfel\w*|realokacj\w*|dob(?:ór|ierzemy|ierzem|iera\w*|ranie|rać) (?:\w+ ){0,2}(?:fundusz|instrument|akcj|obligacj|ETF|spółk|aktyw|produkt\w* inwestycyjn)\w*)"),
    ("advice_service", "usługa doradztwa lub zarządzania portfelem",
     r"\b(?:doradztw\w* inwestycyjn\w*|doradc\w* inwestycyjn\w*|zarządzani\w* (?:portfel\w*|majątkiem|aktywami|kapitałem)|opiek\w* nad (?:portfelem|inwestycjami|majątkiem)|"
     r"wealth management|investment advi[cs]\w*|portfolio manag\w*|family office|rekomendacj\w*)\b"),
]
STRONG_ACTION = {"hold", "buy_sell", "equivalent"}

PERSONAL = [
    ("situation", "odniesienie do sytuacji, celów lub profilu klienta",
     r"\b(?:twoj\w* (?:cel\w*|potrzeb\w*|sytuacj\w*|profil\w*|horyzont\w*|oczekiwa\w*|majątk\w*|finans\w*|możliwości|preferencj\w*|toleranc\w*|budżet\w*)|"
     r"(?:cel\w*|potrzeb\w*|sytuacj\w*|profil\w*|toleranc\w*|oczekiwa\w*|horyzont\w*) (?:inwestycyjn\w* |finansow\w* |ryzyka )?(?:klient\w*|inwestor\w*|pana|pani|państwa)|"
     r"profil\w* (?:ryzyka|inwestycyjn\w*|inwestora|klienta)|ankiet\w* (?:mifid|inwestycyjn|adekwatności|odpowiedniości)\w*|test\w* (?:adekwatności|odpowiedniości)|"
     r"(?:analiz\w*|diagnoz\w*|audyt\w*) (?:twojej |twoich |Pana |Pani )?(?:sytuacji|portfel\w*|finansów|potrzeb|majątku)|"
     r"toleranc\w* (?:na )?ryzyk\w*|apetyt\w* na ryzyko)"),
    ("tailored", "usługa dobierana indywidualnie",
     r"\b(?:indywidualn\w*|spersonalizowan\w*|personalizowan\w*|szyt\w* na miarę|na miarę (?:twoich|pana|pani|potrzeb|klienta)|dopasowan\w*|dostosowan\w*|"
     r"dla (?:ciebie|klienta|pana|pani|każdego klienta)|one[- ]to[- ]one|1\s*(?:na|:)\s*1)\b"),
]

INSTRUMENT = [
    ("shares", "akcje i prawa z nimi związane (art. 3 lit. a)", r"\b(?:akcj[aeiąę]\w*|spółk\w* (?:giełdow|z GPW|notowan)\w*|prawa? poboru|prawa? do akcji|warrant\w* subskrypcyjn\w*|kwit\w* depozytow\w*|dywidend\w*|GPW|NewConnect|stocks?|equit(?:y|ies))\b"),
    ("bonds", "obligacje i listy zastawne (art. 3 lit. a)", r"\b(?:obligac\w*|list\w* zastawn\w*|bon\w* skarbow\w*|papier\w* dłużn\w*|bonds?)\b"),
    ("funds", "tytuły uczestnictwa: fundusze, ETF, certyfikaty (art. 2 pkt 2 lit. a)", r"\b(?:fundusz\w* (?:inwestycyjn|otwart|zamknięt|akcyjn|obligacyjn|ETF|indeksow)\w*|subfundusz\w*|jednost\w* uczestnictwa|certyfikat\w* inwestycyjn\w*|ETF\w*|TFI|tytuł\w* uczestnictwa)\b"),
    ("money_market", "instrumenty rynku pieniężnego (lit. b)", r"\b(?:instrument\w* rynku pieniężnego|bon\w* (?:skarbow|pieniężn)\w*|papier\w* komercyjn\w*)\b"),
    ("derivatives", "instrumenty pochodne: opcje, kontrakty terminowe, swapy (lit. c–g, i)", r"\b(?:instrument\w* pochodn\w*|derywat\w*|opcj[aeiąę] (?:na|kupna|sprzedaży|walutow)\w*|opcj\w* binarn\w*|kontrakt\w* terminow\w*|futures|swap\w*|forward\w*|FRA)\b"),
    ("cfd", "kontrakty na różnicę, CFD i forex z dźwignią (lit. h)", r"\b(?:CFD|kontrakt\w* na różnic\w*|forex|FX|dźwigni\w* finansow\w*|par\w* walutow\w*)\b"),
    ("emission_allowances", "uprawnienia do emisji (lit. j)", r"\b(?:uprawnie\w* do emisji|EUA|CO2 allowances?|carbon (?:credits|allowances)|EU ETS)\b"),
    ("structured", "produkty strukturyzowane i inne papiery wartościowe", r"\b(?:produkt\w* strukturyzowan\w*|certyfikat\w* strukturyzowan\w*|papier\w* wartościow\w*|instrument\w* finansow\w*|rynk\w* (?:publiczn|kapitałow)\w*|portfel\w* inwestycyjn\w*)\b"),
]
OUT_OF_CATALOG = [
    ("real_estate", "nieruchomości", r"\b(?:nieruchomoś\w*|mieszka\w* pod wynajem|grunt\w*|flipp\w*|condo|apartament\w* inwestycyjn\w*)\b"),
    ("physical_gold", "złoto fizyczne i kruszce", r"\b(?:złot\w* (?:fizyczn|inwestycyjn)\w*|sztab\w*|monet\w* (?:bulionow|inwestycyjn|złot)\w*|kruszc\w*|srebr\w* inwestycyjn\w*)\b"),
    ("deposits", "lokaty i konta oszczędnościowe", r"\b(?:lokat\w*|kont\w* oszczędnościow\w*|rachun\w* oszczędnościow\w*)\b"),
    ("insurance", "ubezpieczenia i polisy", r"\b(?:ubezpiecze\w*|polis\w*|IKZE ubezpieczeniow\w*|ochron\w* (?:na życie|życia))\b"),
    ("crypto", "kryptoaktywa (osobny reżim; sama nazwa nie przesądza)", r"\b(?:kryptowalut\w*|kryptoaktyw\w*|bitcoin\w*|BTC|ethereum|altcoin\w*|token\w*|NFT|DeFi|krypto)\b"),
    ("credit", "kredyty i finansowanie", r"\b(?:kredyt\w*|pożycz\w*|hipote\w*|leasing\w*|faktoring\w*)\b"),
    ("alternatives", "aktywa alternatywne: wino, sztuka, diamenty", r"\b(?:win\w* inwestycyjn\w*|whisky|dzieł\w* sztuki|diament\w*|kamieni\w* szlachetn\w*|zegark\w* inwestycyjn\w*)\b"),
    ("legal_tax", "usługi prawne, podatkowe i sukcesyjne", r"\b(?:sukcesj\w*|fundacj\w* rodzinn\w*|optymalizacj\w* podatkow\w*|testament\w*|prawn\w* i podatkow\w*|podatkow\w*)\b"),
]

COUNTER = [
    ("disclaimer", "zastrzeżenie, że treść nie jest rekomendacją",
     r"\b(?:nie stanowi\w* (?:\w+ ){0,3}(?:rekomendacj|porad|doradztw|oferty)\w*|nie jest (?:to )?(?:\w+ ){0,2}(?:rekomendacj|porad|doradztw)\w*|"
     r"nie (?:świadczy\w*|prowadzi\w*|udziela\w*) (?:\w+ ){0,2}(?:doradztw|rekomendacj|porad)\w*|(?:wyłącznie|jedynie|tylko) (?:cel\w* |charakter\w* )?(?:edukacyjn|informacyjn|poglądow)\w*|"
     r"charakter\w* (?:wyłącznie )?(?:edukacyjn|informacyjn)\w*|not (?:investment|financial) advice|nie jest doradc\w* inwestycyjn\w*|"
     r"decyzj\w* (?:inwestycyjn\w* )?(?:podejmujesz|należ\w*|podejmuje) (?:samodzielnie|wyłącznie|do ciebie|ty)|na własn\w* (?:odpowiedzialność|ryzyko))"),
    ("education", "oferta edukacyjna (kurs, szkolenie, webinar)",
     r"\b(?:kurs\w*|szkoleni\w*|webinar\w*|warsztat\w*|edukac\w*|akademi\w*|lekcj\w*|e-book\w*|ebook\w*|nauczysz się|mentoring\w*|wykład\w*|poradnik\w*)\b"),
    ("licensed_partner", "współpraca z licencjonowanym podmiotem lub działanie jako agent",
     r"\b(?:agent\w* (?:firmy|domu|biura) (?:inwestycyjn|maklersk)\w*|na rzecz (?:domu|biura) maklersk\w*|"
     r"(?:we )?współprac\w* z (?:licencjonowan|autoryzowan|nadzorowan|uprawnion)\w*|licencjonowan\w* partner\w*|"
     r"nadz(?:ór|orem|orowan)\w* (?:przez )?(?:komisj\w* nadzoru finansowego|KNF)|zezwoleni\w* (?:komisji nadzoru finansowego|KNF)|"
     r"dystrybutor\w* (?:jednostek|funduszy)|pośredni\w* (?:w sprzedaży )?(?:jednostek|funduszy)|(?:wpisan\w*|wpis) do rejestru (?:agentów|KNF))"),
    ("general_info", "informacja ogólna o rynku lub narzędziu",
     r"\b(?:narzędzi\w* (?:do analizy|analityczn)\w*|screener\w*|notowani\w* (?:giełdow\w* |online|na żywo)\w*|kalkulator\w*|wiadomości (?:giełdow|rynkow)\w*|serwis\w* informacyjn\w*|"
     r"platform\w* (?:informacyjn|edukacyjn)\w*|portal\w*|redakcj\w*|policz swoje zyski|załóż portfel|bez reklam)\b"),
]

FORM = [
    ("electronic", r"\b(?:e-?mail\w*|newsletter\w*|aplikacj\w*|SMS\w*|telegram\w*|discord\w*|whats ?app|signal\b|platform\w* online|panel\w* klienta|powiadomie\w* push|online)\b"),
    ("oral", r"\b(?:spotkani\w*|rozmow\w*|konsultac\w*|telefon\w*|wideokonferencj\w*|zoom|teams|osobiście)\b"),
    ("written", r"\b(?:raport\w*|plan\w* finansow\w*|opracowani\w*|pisemn\w*|PDF|rekomendacj\w* na piśmie)\b"),
]
INITIATIVE = [
    ("firm", r"\b(?:wysyłamy|powiadomimy|powiadamiamy|alert\w*|na bieżąco informujemy|otrzymasz (?:sygnał|alert|powiadomieni|rekomendacj)\w*|z naszej inicjatywy)\b"),
    ("client", r"\b(?:na (?:twoją |państwa )?(?:prośbę|życzenie|wniosek)|zadaj pytanie|umów (?:się|konsultację|spotkanie)|zapytaj)\b"),
]
PAID = r"\b(?:\d[\d\s]*(?:,\d{2})?\s?(?:zł|PLN)\b|abonament\w*|subskrypcj\w*|cennik\w*|opłat\w*|wynagrodzeni\w*|premium|pakiet\w*|% (?:rocznie|od (?:wartości|aktywów)))"

POLISH_WORDS = re.compile(r"\b(?:i|w|na|z|się|że|nie|do|jest|dla|oraz|jak|Twoich|Twój|Państwa|inwestycj\w*)\b", re.I)
PL_MARKET = [
    ("currency", r"\b(?:zł|PLN|złotych)\b"),
    ("postal_code", r"\b\d{2}-\d{3}\s+[A-ZŁŚŻŹĆ][a-ząćęłńóśźż]+"),
    ("phone", r"(?:\+48|\(48\))[\s-]?\d{2,3}"),
    ("poland", r"\b(?:w Polsce|polskich (?:inwestorów|klientów)|polski\w* rynk\w*|na GPW|Warszaw\w*|Krak\w*|Wrocław\w*|Poznań|Poznaniu|Gdańsk\w*|Gdyni\w*|Łódź|Łodzi|Katowic\w*)\b"),
    ("tax_ids", r"\b(?:NIP|KRS|REGON)\b"),
]

LEGAL_FORMS = (r"(?:ltd\.?|limited|gmbh|plc|sp\.?\s?z\s?o\.?\s?o\.?|spółka z ograniczoną odpowiedzialnością|s\.\s?a\.|spółka akcyjna|sp\.\s?k\.?|spółka komandytowa|"
               r"sp\.\s?j\.?|spółka jawna|s\.\s?c\.?|spółka cywilna|p\.?s\.?a\.?|prosta spółka akcyjna|sp\.\s?k\.\s?a\.?)")
COMPANY = re.compile(r"((?:[A-ZĄĆĘŁŃÓŚŹŻ0-9(][\w&.\-–'’()]*\s){1,6}" + LEGAL_FORMS + r")(?=[\s,;)]|$)", re.I)
NIP = re.compile(r"\bNIP\b[:\s.]*(?:PL)?\s*((?:\d[\s-]?){9}\d)\b", re.I)
KRS = re.compile(r"\bKRS\b[^\d\n]{0,25}(\d{10})\b", re.I)
REGON = re.compile(r"\bREGON\b[:\s.]*(\d{9}(?:\d{5})?)\b", re.I)
PERSON = re.compile(r"\b([A-ZŁŚŻŹĆ][a-ząćęłńóśźż]{2,})\s+([A-ZŁŚŻŹĆ][a-ząćęłńóśźż]{2,}(?:-[A-ZŁŚŻŹĆ][a-ząćęłńóśźż]{2,})?)\b")
OPERATOR_CUE = re.compile(r"©|copyright|wszelkie prawa|all rights|\bNIP\b|\bKRS\b|\bREGON\b|administrator\w* (?:danych|serwisu|strony|portalu)|"
                          r"właściciel\w* (?:serwisu|strony|portalu)|sąd rejonow|kapitał zakładow|przedtem|dawniej|nr spółki|zarejestrowan\w* adres|registered", re.I)
THIRD_PARTY = re.compile(r"dostarcza|dostawc|partner\w*|we współpracy|współprac\w* z|na rzecz|agentem|w imieniu|"
                         r"projekt\w*|wykona\w*|realizacj\w*|powered|technologi\w*|zawarli|plasuje", re.I)
ADVISER_NO = re.compile(r"(?:doradc\w* inwestycyjn\w*|licencj\w* (?:nr|numer)?\s*doradcy)[^\n\d]{0,40}?(?:(?:nr|numer|nr wpisu)\.?\s*|\(\s*)(\d{1,4})\b", re.I)


def _casefold(text):
    return unicodedata.normalize("NFC", text).casefold()


def name_key(name):
    """Normalise a legal or person name so that a site and a register can be compared."""
    text = _casefold(re.sub(r"<[^>]+>", " ", name or ""))
    text = re.sub(r"spółka z ograniczoną odpowiedzialnością|sp\.?\s?z\s?o\.?\s?o\.?", " spzoo ", text)
    text = re.sub(r"spółka akcyjna|\bs\.\s?a\.?(?=\s|$)|\bsa\b", " sa ", text)
    text = re.sub(r"spółka komandytowa|\bsp\.\s?k\.?(?=\s|$)", " spk ", text)
    text = re.sub(r"\blimited\b", " ltd ", text)
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def hashed(name):
    return sha256(name_key(name).encode()).hexdigest()


def valid_nip(digits):
    if len(digits) != 10 or not digits.isdigit():
        return False
    weights = (6, 5, 7, 2, 3, 4, 5, 6, 7)
    return sum(int(d) * w for d, w in zip(digits, weights)) % 11 == int(digits[9])


# --- Text helpers ----------------------------------------------------------------------------------

def clauses(page):
    """Yield (line number, start, end, clause) for each sentence-like clause of a saved page text."""
    offset = 0
    for number, line in enumerate(page["text"].split("\n"), 1):
        for match in re.finditer(r"[^.!?;]+[.!?;]?", line):
            clause = match.group(0).strip()
            if len(clause) >= 3 and not NOISE.search(clause):
                yield number, offset + match.start(), offset + match.end(), clause
        offset += len(line) + 1


def _quote(clause, match, width=260):
    if len(clause) <= width:
        return clause
    start = max(0, match.start() - width // 2)
    return ("…" if start else "") + clause[start:start + width].strip() + ("…" if start + width < len(clause) else "")


# Cookie banners and privacy notices address the reader too ("twoje preferencje") but say nothing of the service.
NOISE = re.compile(r"cookie|ciasteczk|plik\w* cookie|RODO|dan\w* osobow|polityk\w* prywatności", re.I)
SIGNAL_SERVICE = re.compile(r"sygnał\w*|alert\w* (?:kupna|sprzedaży|transakcyjn)\w*|powiadomieni\w* o transakcj\w*|portfel\w* modelow\w*|kopiow\w* transakcj\w*|naśladować nasze ruchy", re.I)
NEGATED = re.compile(r"\b(?:nie|bez|żadn\w*|nigdy)\b(?:\W+\w+){0,3}\W*$", re.I)


def find(pages, patterns, *, skip_negated=True, limit=3):
    """Return evidence for each pattern id: verbatim quotes with page URL, line and character range."""
    found = {}
    for page in pages:
        for line, start, end, clause in clauses(page):
            for key, *rest in patterns:
                pattern = rest[-1]
                if len(found.get(key, [])) >= limit:
                    continue
                match = re.search(pattern, clause, re.I)
                if not match:
                    continue
                if skip_negated and NEGATED.search(clause[:match.start()]):
                    continue
                found.setdefault(key, []).append({
                    "quote": _quote(clause, match), "match": match.group(0),
                    "locator": {"url": page["url"], "line": line, "start": start, "end": end,
                                "textSha256": page.get("textSha256")},
                })
    return found


def _labels(patterns):
    return {key: rest[0] for key, *rest in patterns if len(rest) == 2}


# --- Axes ------------------------------------------------------------------------------------------

def axis_action(pages, counter):
    hits = find(pages, ACTION)
    strong = {k: v for k, v in hits.items() if k in STRONG_ACTION}
    status = "present" if strong else ("service_only" if hits.get("advice_service") else "absent")
    return {"axis": "action", "status": status, "kinds": sorted(hits), "labels": _labels(ACTION),
            "evidence": [e for key in ("hold", "buy_sell", "equivalent", "advice_service") for e in hits.get(key, [])[:2]],
            "counter": counter.get("disclaimer", [])[:2]}


def axis_personal(pages, counter):
    hits = find(pages, PERSONAL)
    status = "present" if hits.get("situation") else ("weak" if hits.get("tailored") else "absent")
    return {"axis": "personalisation", "status": status, "kinds": sorted(hits), "labels": _labels(PERSONAL),
            "evidence": hits.get("situation", [])[:2] + hits.get("tailored", [])[:2],
            "counter": (counter.get("education", []) + counter.get("disclaimer", []))[:2]}


def axis_instrument(pages):
    inside = find(pages, INSTRUMENT, limit=2)
    outside = find(pages, OUT_OF_CATALOG, limit=2)
    # A bare "instrument finansowy" or "papier wartościowy" names the catalogue but no class.
    classes = sorted(k for k in inside if k != "structured")
    status = "catalog" if classes else ("generic" if inside else ("outside_only" if outside else "absent"))
    return {"axis": "instrument", "status": status, "classes": classes, "outside": sorted(outside),
            "labels": {**_labels(INSTRUMENT), **_labels(OUT_OF_CATALOG)},
            "evidence": [e for k in classes + (["structured"] if "structured" in inside else []) for e in inside[k][:1]],
            "counter": [e for k in sorted(outside) for e in outside[k][:1]]}


def axis_market(pages, domain):
    text = "\n".join(page["text"] for page in pages)
    words = len(re.findall(r"\w+", text)) or 1
    polish_ratio = round(len(POLISH_WORDS.findall(text)) / words, 3)
    diacritics = len(re.findall(r"[ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]", text))
    markers = find(pages, PL_MARKET, skip_negated=False, limit=1)
    cues = sorted(markers) + (["pl_domain"] if (domain or "").endswith(".pl") else []) + (["polish_text"] if polish_ratio >= 0.05 and diacritics >= 20 else [])
    status = "poland" if "polish_text" in cues and len(cues) >= 3 else ("unclear" if cues else "absent")
    # Phone numbers and addresses stay out of the evidence; the quote is the marker word only.
    evidence = [{**e, "quote": e["match"]} if k in ("phone", "postal_code") else e for k, v in markers.items() for e in v]
    return {"axis": "market", "status": status, "cues": cues, "polishWordRatio": polish_ratio, "evidence": evidence[:4],
            "counter": []}


def form_and_initiative(pages):
    form = find(pages, FORM, limit=1)
    initiative = find(pages, INITIATIVE, limit=1)
    return {"forms": sorted(form), "initiative": sorted(initiative),
            "evidence": [e for v in list(form.values()) + list(initiative.values()) for e in v][:4]}


# --- Identity --------------------------------------------------------------------------------------

def extract_identity(pages, domain):
    """Read the operator statement of the site: legal names, NIP (checksum), KRS, REGON, adviser number."""
    names, mentioned, nips, krs, regon, adviser, people = {}, {}, set(), set(), set(), set(), set()
    for page in pages:
        footer = page.get("identityText") or ""
        text = footer + "\n" + page["text"] if footer else page["text"]
        footer_lines = set(footer.split("\n"))
        for line in text.split("\n"):
            for match in COMPANY.finditer(line):
                name = " ".join(match.group(1).split())
                # Drop sentence starts that the pattern swept in before the trading name.
                name = re.sub(r"^(?:(?:przez|oraz|firma|firmy|spółka|spółki|administrator\w*|operator\w*|właściciel\w*|serwis\w*|jest|to|i|z|w|©|copyright|"
                              r"przedtem|dawniej|dawny|dawna|agent\w*|firmy|inwestycyjnej|domu|maklerskiego|banku|\d{4})\s+)+", "", name, flags=re.I)
                # Cut a sentence start that ends with a verb or cue ("… dostarcza Dom Maklerski X S.A.").
                name = re.sub(r"^.*\b(?:dostarcza\w*|przez|wykonał\w*|oferowan\w*|przedtem|dawniej|jest|są)\s+", "", name, flags=re.I)
                name = re.sub(r"^(?:[a-ząćęłńóśźż][a-ząćęłńóśźż.,]*\s+)+", "", name)
                if len(name_key(name).split()) < 2:
                    continue
                # Only the operator statement identifies the site; a partner or data supplier is a mention.
                third = THIRD_PARTY.search(line)
                operator = OPERATOR_CUE.search(line) or (line in footer_lines and len(name) >= 0.6 * len(line.strip()))
                (names if operator and not third else mentioned).setdefault(name_key(name), name)
        for match in NIP.finditer(text):
            digits = re.sub(r"\D", "", match.group(1))
            if valid_nip(digits):
                nips.add(digits)
        krs.update(KRS.findall(text))
        regon.update(REGON.findall(text))
        adviser.update(ADVISER_NO.findall(text))
        for line in text.split("\n"):
            if re.search(r"doradc\w* inwestycyjn|licencj\w*|makler\w*", line, re.I):
                for first, last in PERSON.findall(line):
                    people.update({hashed(f"{last} {first}"), hashed(f"{first} {last}")})
    # Person names leave this function only as hashes; they are compared with the hashed KNF person lists.
    return {"domain": domain, "names": list(names.values())[:6], "mentioned": list(mentioned.values())[:6], "nip": sorted(nips), "krs": sorted(krs),
            "regon": sorted(regon), "adviserNumbers": sorted(adviser), "personKeys": sorted(people)}


def _attr(row, *names):
    for attribute in row.get("attributes") or []:
        if attribute.get("name") in names and attribute.get("value"):
            return re.sub(r"<[^>]+>", " ", attribute["value"]).strip()
    return None


def _codes(value):
    return {c for c in re.findall(r"\d+", value or "")}


def load_registers(knf_dir=KNF, m3_dir=M3_REGISTERS):
    """Index the dated KNF lists. A list that cannot be read is reported, never treated as empty."""
    registers, failures, entries = [], [], []

    def add(file, label, kind, scope_fn, name_attrs=("Nazwa", "Nazwa podmiotu")):
        path = Path(file)
        try:
            raw = path.read_bytes()
            rows = json.loads(raw)
        except (OSError, ValueError) as error:
            failures.append({"file": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path), "name": label, "error": type(error).__name__})
            return
        registers.append({"file": str(path.relative_to(ROOT)), "name": label, "rows": len(rows), "sha256": sha256(raw).hexdigest()})
        for row in rows:
            name = _attr(row, *name_attrs) or row.get("name") or ""
            entries.append({"kind": kind, "register": label, "id": row.get("id"), "name": " ".join(name.split()),
                            "key": name_key(name), "file": str(path.relative_to(ROOT)), **scope_fn(row)})

    domestic = lambda row: {"scopeCodes": sorted(_codes(_attr(row, "Zakres działalności")), key=int),
                            "advice": "5" in _codes(_attr(row, "Zakres działalności")),
                            "portfolio": "4" in _codes(_attr(row, "Zakres działalności"))}
    foreign = lambda row: {"scopeCodes": sorted(_codes(_attr(row, "Usługi inwestycyjne (A)", "A - Usługi inwestycyjne i działalność inwestycyjna z sekcji A załącznika I Dyrektywy 2014/65/UE")), key=int),
                           "advice": "5" in _codes(_attr(row, "Usługi inwestycyjne (A)", "A - Usługi inwestycyjne i działalność inwestycyjna z sekcji A załącznika I Dyrektywy 2014/65/UE")),
                           "portfolio": "4" in _codes(_attr(row, "Usługi inwestycyjne (A)", "A - Usługi inwestycyjne i działalność inwestycyjna z sekcji A załącznika I Dyrektywy 2014/65/UE"))}
    add(knf_dir / "knf_domy_maklerskie.json", "domy maklerskie", "investment_firm", domestic)
    add(knf_dir / "knf_banki_maklerskie.json", "banki prowadzące działalność maklerską", "investment_firm", domestic)
    add(knf_dir / "knf_oddzialy_zagr_FI.json", "oddziały zagranicznych firm inwestycyjnych", "investment_firm", foreign)
    add(knf_dir / "knf_notyfikacje_zagr_FI.json", "notyfikacje zagranicznych firm inwestycyjnych", "investment_firm", foreign)
    add(knf_dir / "knf_banki_art70.json", "banki działające na podstawie art. 70 ust. 2", "bank_art70", domestic)
    add(knf_dir / "knf_TFI.json", "towarzystwa funduszy inwestycyjnych", "tfi", lambda row: {"scopeCodes": [], "advice": None, "portfolio": None})
    add(knf_dir / "knf_agenci_prawne.json", "agenci firm inwestycyjnych (osoby prawne)", "agent",
        lambda row: {"principal": _attr(row, "Nazwa firmy inwestycyjnej na rzecz której działa agent")})
    add(knf_dir / "knf_cofniete_zezwolenie.json", "firmy, którym cofnięto zezwolenie", "revoked", lambda row: {})
    # Person lists and the public warnings are stored as derived keys (hashes of normalised names).
    derived = {"knf_doradcy_inwestycyjni.json": "doradcy inwestycyjni (osoby)", "knf_maklerzy_doradztwo.json": "maklerzy z uprawnieniem do doradztwa (osoby)",
               "knf_agenci_osoby.json": "agenci firm inwestycyjnych (osoby fizyczne)", "knf_ostrzezenia.json": "lista ostrzeżeń publicznych KNF"}
    persons, warnings = [], []
    for file, label in derived.items():
        path = m3_dir / file
        try:
            data = json.loads(path.read_bytes())
        except (OSError, ValueError) as error:
            failures.append({"file": str(path.relative_to(ROOT)), "name": label, "error": type(error).__name__})
            continue
        registers.append({"file": str(path.relative_to(ROOT)), "name": label, "rows": len(data["rows"]), "sha256": data.get("responseSha256"),
                          "checkedAt": data.get("checkedAt"), "url": data.get("url")})
        (warnings if file == "knf_ostrzezenia.json" else persons).extend({**row, "register": label} for row in data["rows"])
    return {"registers": registers, "failures": failures, "entries": entries, "persons": persons, "warnings": warnings,
            "checkedAt": "2026-11-21"}


def _domain_root(domain):
    parts = (domain or "").lower().removeprefix("www.").split(".")
    return parts[-3] if len(parts) >= 3 and parts[-2] in ("com", "org", "net") else (parts[-2] if len(parts) >= 2 else "")


def match_identity(identity, index):
    """Map the operator statement to one identity state. Absence in the lists is only absence there."""
    reviewed = [r["name"] for r in index["registers"]]
    keys = {name_key(n) for n in identity["names"]}
    name_hashes = {hashed(n) for n in identity["names"]}
    warnings = [w for w in index["warnings"]
                if name_hashes & set(w.get("nameKeys", []))
                or set(identity["krs"]) & set(w.get("krs", [])) or set(identity["nip"]) & set(w.get("nip", []))
                or (identity["domain"] and identity["domain"].removeprefix("www.") in w.get("domains", []))]
    warning = [{"id": w["id"], "section": w.get("section"), "matchedOn": "domena/KRS/NIP/nazwa", "url": w.get("url")} for w in warnings]
    base = {"reviewedRegisters": reviewed, "checkedAt": index["checkedAt"], "warning": warning,
            "registerFailures": index["failures"], "operator": identity}
    # A register row often joins the current and former names; the site name must be its whole first name
    # or a bounded part of it that carries a legal form.
    forms = r"\b(?:sa|spzoo|spk|ltd|gmbh|ag|plc)\b"

    def same(key, entry):
        if entry["key"] == key:
            return True
        first = re.match(r".*?" + forms, entry["key"])
        # The site sentence may precede the legal name ("Produkty oferowane przez X Ltd").
        if first and len(first.group(0).split()) >= 2 and (key == first.group(0) or key.endswith(" " + first.group(0))):
            return True
        return bool(re.search(forms, key) and re.search(r"(?:^| )" + re.escape(key) + r"(?: |$)", entry["key"]))
    exact = [e for e in index["entries"] if e["key"] and any(same(k, e) for k in keys)]
    # Brand-level collision: the distinctive word of the domain appears in register rows.
    root = _domain_root(identity["domain"])
    loose = []
    if not exact and len(root) >= 6:
        loose = [e for e in index["entries"] if root in e["key"].replace(" ", "")]
    person_hits = [p for p in index["persons"]
                   if p.get("nameSha256") in name_hashes | set(identity.get("personKeys", [])) or (p.get("number") and p["number"] in identity["adviserNumbers"] and "doradcy" in p["register"])]
    if not (identity["names"] or identity["nip"] or identity["krs"] or person_hits or loose):
        state = "registry_error" if index["failures"] and not index["entries"] else "no_identity"
        return {**base, "state": state, "label": "brak danych podmiotu na stronie" if state == "no_identity" else "awaria rejestru",
                "matches": []}
    matches = exact or loose
    summary = [{"register": e["register"], "id": e["id"], "name": e["name"], "scopeCodes": e.get("scopeCodes"),
                "principal": e.get("principal"), "file": e["file"]} for e in matches[:5]]
    if index["failures"] and not matches:
        return {**base, "state": "registry_error", "label": "awaria rejestru: " + ", ".join(f["name"] for f in index["failures"]),
                "matches": []}
    advice = [e for e in exact if e["kind"] in ("investment_firm", "bank_art70") and e.get("advice")]
    if advice:
        summary = [s for s in summary if s["id"] in {e["id"] for e in advice}] or summary
        return {**base, "state": "authorized_advice", "label": "uprawniony: zakres obejmuje doradztwo inwestycyjne (kod 5 / A5) według nazwy podanej na stronie",
                "matches": summary}
    if len({(e["kind"], e["id"]) for e in matches}) > 1 and (loose or len({e["kind"] for e in matches}) > 1 or all(e["kind"] == "agent" for e in matches)):
        return {**base, "state": "name_collision", "label": "kolizja nazw: kilka wpisów pasuje do nazwy lub domeny", "matches": summary}
    if matches:
        entry = matches[0]
        if entry["kind"] == "agent":
            return {**base, "state": "investment_firm_agent", "label": f"agent firmy inwestycyjnej ({entry.get('principal')})", "matches": summary}
        if entry["kind"] in ("investment_firm", "bank_art70") and entry.get("advice"):
            return {**base, "state": "authorized_advice", "label": "uprawniony: zakres obejmuje doradztwo inwestycyjne (kod 5 / A5)", "matches": summary}
        if entry["kind"] == "revoked":
            return {**base, "state": "authorized_other_scope", "label": "wpis o cofniętym zezwoleniu", "matches": summary, "scopeKnown": True}
        known = entry["kind"] in ("investment_firm", "bank_art70")
        return {**base, "state": "authorized_other_scope", "scopeKnown": known,
                "label": "uprawniony w innym zakresie (bez kodu doradztwa w kopii)" if known else "podmiot nadzorowany; zakres doradztwa nieustalony w kopii wykazu",
                "matches": summary}
    if person_hits:
        return {**base, "state": "authorized_advice", "label": "osoba z listy doradców lub maklerów z uprawnieniem do doradztwa (dopasowanie po nazwisku lub numerze wpisu)",
                "matches": [{"register": p["register"], "number": p.get("number")} for p in person_hits[:3]]}
    return {**base, "state": "not_found", "label": "brak wpisu w przejrzanych wykazach – uprawnienia do ustalenia", "matches": []}


# --- Route -----------------------------------------------------------------------------------------

def _plain(evidence):
    return evidence[0]["quote"] if evidence else ""


def route(axes, identity, form, paid):
    action, personal, instrument, market = (axes[k] for k in ("action", "personalisation", "instrument", "market"))
    points, reasons, missing = 0, [], []
    counters = [c for key, axis in axes.items() if not key.startswith("_") for c in axis.get("counter", [])]
    if action["status"] == "present":
        points += 30
        kinds = ", ".join(action["labels"][k] for k in action["kinds"] if k in STRONG_ACTION)
        reasons.append(f"Strona opisuje czynność: {kinds} – „{_plain(action['evidence'])}”.")
    elif action["status"] == "service_only":
        points += 12
        missing.append("opisu czynności: czy klient dostaje rekomendację kup / sprzedaj / trzymaj albo czynność równoważną")
    else:
        missing.append("czynności doradczej (rekomendacji dotyczącej instrumentu)")
    if personal["status"] == "present":
        points += 25
        reasons.append(f"Oferta odnosi się do sytuacji klienta – „{_plain(personal['evidence'])}”.")
    elif personal["status"] == "weak":
        points += 10
        missing.append("odniesienia do sytuacji lub profilu klienta (samo „indywidualnie” nie wystarcza)")
    else:
        missing.append("personalizacji (rekomendacji opartej na sytuacji klienta)")
    if instrument["status"] == "catalog":
        points += 20 + (5 if set(instrument["classes"]) & {"derivatives", "cfd", "emission_allowances"} else 0)
        names = ", ".join(instrument["labels"][k].split(" (")[0] for k in instrument["classes"][:3])
        reasons.append(f"Wymienione instrumenty należą do katalogu ustawy: {names} – „{_plain(instrument['evidence'])}”.")
    elif instrument["status"] == "generic":
        points += 8
        missing.append("klasy instrumentu (strona mówi ogólnie o instrumentach finansowych)")
    else:
        missing.append("instrumentu finansowego z katalogu ustawy")
    if market["status"] == "poland":
        points += 10
        reasons.append("Oferta jest kierowana do klientów w Polsce: " + ", ".join(market["cues"]) + ".")
    elif market["status"] != "poland":
        missing.append("wskazania, że oferta jest kierowana do klientów w Polsce")
    if paid:
        points += 5
    kinds = {c.get("kind") for c in counters}
    points -= 15 * len({k for k in ("disclaimer", "education", "licensed_partner") if axes["_counter"].get(k)})
    state = identity["state"]
    if identity["warning"]:
        points += 20
        reasons.append("Nazwa, domena lub numer występuje na liście ostrzeżeń publicznych KNF (sygnał osobny, do potwierdzenia tożsamości).")
    if state == "not_found":
        points += 10
        reasons.append(f"Operatora ({', '.join(identity['operator']['names'][:1] or identity['operator']['nip'][:1] or identity['operator']['krs'][:1])}) nie znaleziono w {len(identity['reviewedRegisters'])} przejrzanych wykazach KNF z {identity['checkedAt']} – uprawnienia do ustalenia.")
    points = max(0, min(100, points))
    outside_only = instrument["status"] == "outside_only"
    # Education or an information tool without a signal service and without the client's situation is general content.
    informative = bool(axes["_counter"].get("education") or axes["_counter"].get("general_info"))
    education = informative and personal["status"] != "present" and not axes.get("_signals")
    core = action["status"] == "present" and personal["status"] == "present" and instrument["status"] == "catalog"
    if state == "authorized_advice":
        decision, why = "no_signal", "Podmiot ma w datowanym wykazie zakres obejmujący doradztwo – kontrola ujemna."
    elif state == "investment_firm_agent":
        decision, why = "no_signal", "Podmiot figuruje jako agent firmy inwestycyjnej – działa w imieniu firmy uprawnionej; zakres umowy agencyjnej do potwierdzenia przy wątpliwości."
    elif outside_only:
        decision, why = "no_signal", "Oferta dotyczy produktów spoza katalogu instrumentów finansowych (" + ", ".join(instrument["labels"][k] for k in instrument["outside"][:3]) + ")."
    elif education and not core:
        decision, why = "no_signal", "Treść ma charakter edukacyjny lub informacyjny, bez rekomendacji dla konkretnego klienta."
    elif core and market["status"] == "poland" and state in ("not_found", "authorized_other_scope", "no_identity"):
        if state == "authorized_other_scope" and not identity.get("scopeKnown"):
            decision, why = "complete", "Podmiot nadzorowany, ale kopia wykazu nie podaje zakresu – ustalić, czy zezwolenie obejmuje doradztwo."
        elif state == "no_identity":
            decision, why = "refer", "Przesłanka do sprawdzenia: spersonalizowana rekomendacja dotycząca instrumentu finansowego, a strona nie podaje nazwy, NIP ani KRS – operator i uprawnienia do ustalenia."
            points += 5
            reasons.append(f"Strona nie podaje nazwy, NIP ani KRS operatora; domena {identity['operator']['domain']} – operator i uprawnienia do ustalenia.")
        else:
            decision, why = "refer", "Przesłanka do sprawdzenia: spersonalizowana rekomendacja dotycząca instrumentu finansowego, a w przejrzanych wykazach brak wpisu z zakresem doradztwa."
    elif core and market["status"] != "poland" and state not in ("name_collision", "registry_error"):
        decision, why = "complete", "Treść wskazuje na doradztwo, brakuje wskazania, że oferta jest kierowana do klientów w Polsce."
    elif state in ("name_collision", "registry_error") and (core or action["status"] == "present"):
        need = {"name_collision": "rozstrzygnąć kolizję nazw (ustalić, który wpis dotyczy operatora strony)",
                "registry_error": "powtórzyć odczyt wykazu, który się nie wczytał",
                "no_identity": "ustalić operatora domeny (strona nie podaje nazwy, NIP ani KRS)"}[state]
        decision, why = "complete", "Treść wskazuje na doradztwo, brakuje tożsamości: " + need + "."
        missing.insert(0, need)
    elif action["status"] in ("present", "service_only") and not core:
        decision, why = "complete", "Do uzupełnienia: " + "; ".join(missing[:2]) + "."
    else:
        decision, why = "no_signal", "Brak opisu usługi doradczej dotyczącej instrumentów finansowych."
    points = max(0, min(100, points))
    if decision != "refer":
        points = min(points, 59 if decision == "complete" else 30)
    reasons = reasons[:5]
    for c in counters[:2]:
        if len(reasons) < 5 and decision == "refer":
            reasons.append(f"Kontrargument do oceny: „{c['quote']}”.")
    return {"route": decision, "summary": why, "signalPoints": points, "reasons": reasons,
            "missing": missing if decision == "complete" else [], "wording": "przesłanka do sprawdzenia; uprawnienia do ustalenia"}


def analyze_entity(entity, index):
    pages = [p for p in entity.get("pages", []) if p.get("text")]
    domain = entity.get("domain")
    counter_hits = find(pages, COUNTER, limit=2)
    counter = {k: [{**e, "kind": k} for e in v] for k, v in counter_hits.items()}
    axes = {"action": axis_action(pages, counter), "personalisation": axis_personal(pages, counter),
            "instrument": axis_instrument(pages), "market": axis_market(pages, domain), "_counter": counter,
            "_signals": any(SIGNAL_SERVICE.search(p["text"]) for p in pages)}
    axes["action"]["counter"] = counter.get("disclaimer", [])[:2] + counter.get("licensed_partner", [])[:1]
    identity = match_identity(extract_identity(pages, domain), index)
    form = form_and_initiative(pages)
    paid = any(re.search(PAID, p["text"], re.I) for p in pages)
    decision = route(axes, identity, form, paid)
    offer_pages = [{"url": p["url"], "observedAt": p.get("observedAt"), "sha256": p.get("sha256"), "chars": len(p["text"])} for p in pages]
    return {"entityId": entity.get("id") or domain, "name": (identity["operator"]["names"] or [entity.get("label") or domain])[0],
            "domain": domain, "discoveredVia": entity.get("discoveredVia"), "pages": offer_pages,
            "axes": {k: v for k, v in axes.items() if not k.startswith("_")},
            "counterEvidence": [e for v in counter.values() for e in v][:6], "formAndInitiative": form, "paidOffer": paid,
            "identity": identity, **decision, "rulesVersion": RULES_VERSION}


# --- Register refresh (network, one-off) -----------------------------------------------------------

KNF_API = "https://www.knf.gov.pl/api/podmioty-children"
WARNINGS_URL = "https://www.knf.gov.pl/dla_konsumenta/ostrzezenia_publiczne"
PERSON_LISTS = {"knf_doradcy_inwestycyjni.json": 1384614, "knf_maklerzy_doradztwo.json": 1384613, "knf_agenci_osoby.json": 5}


def _get(url, counter, delay=3.0):
    from urllib.request import Request, urlopen
    time.sleep(delay)
    counter.append(url)
    with urlopen(Request(url, headers={"User-Agent": "InvestWatch-SourceMonitor/1.0"}), timeout=40) as response:
        return response.read()


def parse_warnings(html):
    """Read the warning rows embedded in the KNF page (Next.js flight data) without personal fields."""
    parts = re.findall(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)', html, flags=re.S)
    flight = "".join(json.loads(p) for p in parts)
    rows = []
    decoder = json.JSONDecoder()
    for match in re.finditer(r'\{"id":\d+,"title":', flight):
        try:
            row, _ = decoder.raw_decode(flight, match.start())
        except ValueError:
            continue
        title = row.get("title") or ""
        ident = re.sub(r"<[^>]+>", " ", row.get("numerIdentyfikacyjny") or "")
        names = [re.split(r"\s+z siedzibą|,|\(", re.sub(r"^\s*\d+\.\s*", "", line))[0].strip(" „”\"") for line in title.split("\n")]
        rows.append({"id": row["id"], "nameKeys": sorted({hashed(n) for n in names if len(name_key(n)) > 3}),
                     "krs": sorted(set(re.findall(r"\b\d{10}\b", re.sub(r"(?i)nip\D{0,5}\d{10}", "", ident)))),
                     "nip": sorted(set(re.sub(r"\D", "", m) for m in re.findall(r"NIP\D{0,5}([\d-]{10,13})", ident, re.I))),
                     "domains": sorted({d.lower().removeprefix("www.") for d in re.findall(r"\b(?:https?://)?((?:www\.)?[a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]+)*\.[a-z]{2,})\b", title, re.I)
                                        if not re.fullmatch(r"(?:sp|s\.a|o\.o)", d, re.I)}),
                     "section": row.get("istotneInformacje", "")[:160]})
    return {row["id"]: row for row in rows}


def refresh_registers(out, raw_dir):
    out.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    requests, checked = [], datetime.now(timezone.utc).isoformat(timespec="seconds")
    for file, parent in PERSON_LISTS.items():
        items, page, hashes = [], 0, []
        while page < 20:
            url = f"{KNF_API}?parentId={parent}&page={page}&pageSize=100&type=COMPANY"
            body = _get(url, requests)
            hashes.append(sha256(body).hexdigest())
            (raw_dir / f"{file[:-5]}-{page}.json").write_bytes(body)
            batch = json.loads(body).get("items", [])
            items += batch
            if len(batch) < 100:
                break
            page += 1
        rows = [{"nameSha256": hashed(item.get("name", "")),
                 "number": _attr(item, "Nr wpisu doradcy inwestycyjnego", "Nr licencji", "Numer licencji", "Nr wpisu")}
                for item in items]
        (out / file).write_text(json.dumps({"url": f"{KNF_API}?parentId={parent}&type=COMPANY", "checkedAt": checked,
                                            "responseSha256": hashes, "note": "Nazwiska zapisano wyłącznie jako SHA-256 znormalizowanej nazwy.",
                                            "rows": rows}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    body = _get(WARNINGS_URL, requests)
    (raw_dir / "knf_ostrzezenia.html").write_bytes(body)
    warnings = parse_warnings(body.decode("utf-8"))
    (out / "knf_ostrzezenia.json").write_text(json.dumps({"url": WARNINGS_URL, "checkedAt": checked, "responseSha256": sha256(body).hexdigest(),
                                                         "note": "Tytuły wpisów zapisano jako SHA-256 znormalizowanych nazw; KRS, NIP i domeny dosłownie.",
                                                         "rows": list(warnings.values())}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return requests


CONTROL_CAPTURES = (ROOT / "fixtures" / "validation" / "bossa-discovery-2026-11-21.json",
                    ROOT / "fixtures" / "validation" / "bossa-education-2026-11-21.json")


def entity_from_capture(capture):
    """Adapt a shared Capture (collectors.sites.read_site, module M3) to the entity read by analyze_entity."""
    url = capture.get("url") or ""
    domain = re.sub(r"^www\.", "", re.sub(r"^https?://([^/]+).*$", r"\1", url))
    ident = capture.get("identityEvidence") or {}
    footer = " ".join(str(ident[k]) for k in ("name", "krs", "nip") if ident.get(k))
    prov = capture.get("provenance") or {}
    text = capture.get("description") or ""
    return {"id": capture.get("id") or url, "domain": domain, "label": capture.get("brand") or capture.get("title"),
            "discoveredVia": prov.get("discoveredFrom"),
            "pages": [{"url": url, "observedAt": capture.get("observedAt"), "sha256": prov.get("responseSha256"),
                       "text": text, "textSha256": sha256(text.encode()).hexdigest(), "identityText": footer, "role": "offer"}]}


def analyze_run(raw_dir, index=None, controls=CONTROL_CAPTURES):
    index = index or load_registers()
    entities = json.loads((Path(raw_dir) / "entities.json").read_text(encoding="utf-8"))["entities"]
    for path in controls:
        if Path(path).exists():
            control = entity_from_capture(json.loads(Path(path).read_text(encoding="utf-8"))["capture"])
            entities.append({**control, "id": "control:" + control["id"], "discoveredVia": "Zapis kontrolny (replay) " + Path(path).name})
    return [analyze_entity(entity, index) for entity in entities]


def evaluate(results, labels):
    """Compare routes with labels on the material that was read. Two views: refer only, and refer or complete."""
    label = {row["entityId"]: row["label"] for row in labels}
    rows = [(r["entityId"], r["route"], label[r["entityId"]]) for r in results if r["entityId"] in label and r["pages"]]
    out = {"n": len(rows), "missingLabels": sorted(r["entityId"] for r in results if r["entityId"] not in label and r["pages"])}
    for view, positive in (("refer", {"refer"}), ("refer_or_complete", {"refer", "complete"})):
        tp = sum(1 for _, p, l in rows if p in positive and l in positive)
        fp = sum(1 for _, p, l in rows if p in positive and l not in positive)
        fn = sum(1 for _, p, l in rows if p not in positive and l in positive)
        tn = len(rows) - tp - fp - fn
        out[view] = {"TP": tp, "FP": fp, "TN": tn, "FN": fn, "cost_2FN_plus_FP": 2 * fn + fp,
                     "errors": [{"entityId": e, "route": p, "label": l} for e, p, l in rows if (p in positive) != (l in positive)]}
    out["agreementExactRoute"] = sum(1 for _, p, l in rows if p == l)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    reg = sub.add_parser("registers")
    reg.add_argument("--out", type=Path, default=M3_REGISTERS)
    reg.add_argument("--raw", type=Path, default=ROOT / ".runtime" / "m3-registers")
    ev = sub.add_parser("evaluate")
    ev.add_argument("results", type=Path)
    ev.add_argument("labels", type=Path)
    run = sub.add_parser("analyze")
    run.add_argument("raw_dir", type=Path)
    run.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    if args.command == "registers":
        requests = refresh_registers(args.out, args.raw)
        print(f"Zapisano wykazy M3 ({len(requests)} żądań).")
        return 0
    if args.command == "evaluate":
        results = json.loads(args.results.read_text(encoding="utf-8"))["results"]
        labels = [json.loads(line) for line in args.labels.read_text(encoding="utf-8").splitlines() if line.strip()]
        print(json.dumps(evaluate(results, labels), ensure_ascii=False, indent=1))
        return 0
    results = analyze_run(args.raw_dir)
    text = json.dumps({"rulesVersion": RULES_VERSION, "results": results}, ensure_ascii=False, indent=1) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    counts = {}
    for item in results:
        counts[item["route"]] = counts.get(item["route"], 0) + 1
    print(json.dumps(counts, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
