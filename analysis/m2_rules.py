"""The 19 UKNF M2 criteria evaluated over rendered text blocks of a firm's own page.

Input: ``material`` = {"firm": {...register row...}, "url", "observedAt", "kind",
"views": {"desktop": view, "phone": view}} where a view is the block list produced by
``collectors/m2_capture.js`` (text, font size, document box, role, section, hidden reason,
contrast, first-screen share, truncation, language).

Every row has one state with an explicit applicability:
  spełnione · przesłanka (niespełnione, do sprawdzenia przez analityka) ·
  nie dotyczy (z powodem) · brak danych (z powodem)
plus a quote, measurements and the UKNF basis. No row claims a legal violation.
"""
from collections import Counter
from dataclasses import dataclass, field
import re

from . import m2_readability

OK, PREMISE, NA, UNKNOWN = "spełnione", "przesłanka", "nie dotyczy", "brak danych"
OBSERVATION = "obserwacja"  # visible in the card, 0 points, never changes the route (criterion 2, decision of 21 XI)
RULES_VERSION = "investwatch-m2-market-1"
ORDER = ("1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12a", "12b", "13", "14", "15", "16", "17", "18")
LABELS = {
    "1": "Identyfikacja firmy", "2": "Oznaczenie reklamy", "3": "Informacja o ryzyku przy zysku",
    "4": "Rozmiar czcionki ryzyka", "5": "Ekspozycja i kontrast ryzyka", "6": "Ukrywanie ryzyka",
    "7": "Dostępność bez kliknięcia", "8": "Responsywność", "9": "Zrozumiałość ostrzeżenia",
    "10": "Spójność językowa", "11": "Porównania produktów lub usług", "12a": "Wyniki historyczne: okres i zakres",
    "12b": "Wyniki historyczne: waluta i koszty", "13": "Dominacja wyników historycznych",
    "14": "Ostrzeżenie przy wynikach historycznych", "15": "Prognozy przyszłych wyników",
    "16": "Informacja podatkowa", "17": "Sugestia aprobaty organu nadzoru", "18": "Nadzór jako argument bezpieczeństwa",
}
BASIS = {
    "1": "Art. 44 ust. 2 lit. a rozporządzenia 2017/565", "2": "Art. 24 ust. 3 MiFID II",
    "3": "Art. 44 ust. 2 lit. b rozporządzenia 2017/565", "4": "Art. 44 ust. 2 lit. c rozporządzenia 2017/565",
    "5": "Art. 44 ust. 2 lit. c i e rozporządzenia 2017/565", "6": "Art. 44 ust. 2 lit. e rozporządzenia 2017/565",
    "7": "Art. 44 ust. 2 lit. b i e rozporządzenia 2017/565", "8": "Art. 44 ust. 2 lit. g rozporządzenia 2017/565",
    "9": "Art. 44 ust. 2 lit. d rozporządzenia 2017/565", "10": "Art. 44 ust. 2 lit. f rozporządzenia 2017/565",
    "11": "Art. 44 ust. 3 rozporządzenia 2017/565", "12a": "Art. 44 ust. 4 rozporządzenia 2017/565",
    "12b": "Art. 44 ust. 4 rozporządzenia 2017/565", "13": "Art. 44 ust. 4 lit. a rozporządzenia 2017/565",
    "14": "Art. 44 ust. 4 lit. d rozporządzenia 2017/565", "15": "Art. 44 ust. 6 rozporządzenia 2017/565",
    "16": "Art. 44 ust. 7 rozporządzenia 2017/565", "17": "Art. 44 ust. 8 rozporządzenia 2017/565",
    "18": "Art. 44 ust. 8 rozporządzenia 2017/565",
}
# Team thresholds (auxiliary, not UKNF values).
ACCOMPANY_SCREEN = 0.5      # a warning within half a screen of the claim accompanies it
SECTION_SCREEN = 1.0        # ... or within one screen inside the same page section
SIZE_RATIO = 0.85           # warning font below 85 % of the dominant body size is smaller
MIN_PX = 12                 # auxiliary legibility floor on a phone
MIN_CONTRAST = 4.5          # WCAG AA reference for normal text
LOW_POSITION = 0.85         # lower 15 % of the page counts as a low-visibility place

# ---------------------------------------------------------------- vocabularies
PRODUCTS = {
    "cfd": r"\bCFD\b|kontrakt\w* na różnic\w*|\bforex\b|\bFX\b|dźwigni\w*|\blewar\w*|par\w* walutow\w*",
    "etf": r"\bETF\w*",
    "akcje": r"\bakcj[aeiąę]\w*|\bakcji\b|\bspół(?:ek|ki|ka|kach)\b",
    "obligacje": r"\bobligacj\w*",
    "fundusze": r"\bfundusz\w*|\bTFI\b|jednost\w* uczestnictwa",
    "krypto": r"kryptowalut\w*|\bbitcoin\w*|\bBTC\b|\bkrypto\w*",
    "emerytalne": r"\bIKE\b|\bIKZE\b|\bOIPE\b|\bPPK\b|emerytaln\w*",
    "derywaty": r"kontrakt\w* terminow\w*|\bfutures\b|\bopcj[aeiąę]\w*|\bopcji\b|instrument\w* pochodn\w*",
    "surowce": r"\bsurowc\w*|\bzłot[oa]\b|\bropa\b|\bropy\b",
    "portfel": r"\bportfel\w*|\brobo\w*|zarządzani\w* aktywami",
    "rachunek": r"rachun\w* (?:inwestycyjn|maklersk)\w*|kont\w* maklersk\w*",
}
LEVERAGED = {"cfd", "krypto", "surowce", "derywaty"}  # where a CFD-style warning can be the right one
PROFIT = [
    r"(?:możliw\w*|potencjaln\w*|wysok\w*|atrakcyjn\w*|realn\w*|dodatkow\w*|regularn\w*|pasywn\w*|stał\w*|wyższ\w*)\s+"
    r"(?:zysk\w*|dochod\w*|dochód|zwrot\w*|przych\w*|zarobk\w*|odsetk\w*)",
    r"\b(?:zarabiaj|zarób|zarabiać|zarobisz|zarobić|zarabiasz|zarabiają|pomnażaj|pomnóż|pomnażać|pomnożyć|pomnożysz)\b",
    r"\bzysk(?:aj|asz|iwać|ujesz|uj|ać|ają)\b",
    r"źródł\w* (?:\w+ ){0,2}dochod\w*",
    r"(?:otrzymuj\w*|otrzymasz|otrzymać|wypłac\w*|zgarniaj|odbieraj)\s+(?:\w+\s+){0,3}(?:dywidend\w*|odset\w*|kupon\w*)",
    r"(?:dywidend\w*|odset\w*|kupon\w*)\s+(?:\w+\s+){0,3}(?:co (?:miesiąc|kwartał|rok)|regularn\w*|na (?:twoje|twój) (?:konto|rachunek))",
    r"(?:oprocentowani\w*|rentowno\w*|stop\w* zwrotu|zwrot\w*|kupon\w*|zysk\w*)\s+(?:\w+\s+){0,4}(?:do |nawet |aż )?\d+(?:[.,]\d+)?\s?%",
    r"(?:do|nawet|aż)\s+\d+(?:[.,]\d+)?\s?%\s+(?:rocznie|w skali roku|zysku|zwrotu|p\.a\.)",
    r"\d+(?:[.,]\d+)?\s?%\s+(?:w skali roku|rocznie|p\.a\.|średniorocznie|w skali rok)",
    r"(?:zarabia\w*|zysk\w*|korzyst\w*)\s+(?:\w+\s+){0,2}(?:na|z)\s+(?:wzrost\w*|spadk\w*|zmian\w* cen)",
    r"(?:potencja\w*|szans\w*)\s+(?:\w+\s+){0,2}(?:wzrost\w*|zysk\w*)",
    r"wzrost\w* wartości (?:\w+ ){0,3}(?:inwestycj|oszczędno|kapitał|portfel)\w*",
    r"(?:twoje|twoich) (?:pieniądze|oszczędności|środki) (?:\w+ ){0,2}(?:pracuj|rosn|zarabia)\w*",
]
NOT_PROFIT = r"\b(?:0\s?%|zero)\s+prowizj|bez prowizji|bez opłat|\b0\s?zł\b|darmow\w*|bezpłatn\w*|cashback|rabat"
WARNING = [
    r"wiąż\w* się z (?:\w+ ){0,3}ryzyk\w*", r"ryzyk\w* (?:\w+ ){0,3}(?:utrat\w*|straty|strat)", r"obarczon\w* (?:\w+ ){0,2}ryzyk\w*",
    r"(?:możesz|można|mogą|może|możliw\w*) (?:\w+ ){0,3}(?:stracić|utracić|ponieść strat\w*|utrat\w*|strat\w*)",
    r"(?:utrat\w*|strat\w*) (?:\w+ ){0,3}(?:części|całości|kapitału|środków|zainwestowan\w*|pieniędzy)",
    r"\bryzykown\w*", r"odnotowuj\w* strat\w*", r"nie (?:\w+ ){0,2}(?:gwarantuj\w*|daj\w* gwarancji|ma gwarancji|stanowi\w* gwarancji)",
    r"brak gwarancji|bez gwarancji (?:zysku|zwrotu|kapitału)", r"(?:wartość|cena|kurs|wycena)\w* (?:\w+ ){0,4}(?:może|mogą) (?:\w+ ){0,3}(?:spa\w*|male\w*|zmniejsz\w*|obniż\w*|zarówno|wahać)",
    r"nie (?:są|jest) (?:\w+ ){0,2}wiarygodn\w* wskaźnik\w*", r"inwestowani\w* (?:\w+ ){0,3}ryzyk\w*",
    r"wysoki\w* poziom\w* ryzyka|(?<!brak )(?<!bez )(?:wysokie|średnie|niskie|średnio niskie|średnio wysokie|bardzo wysokie) ryzyko\b",
    r"(?:poziom|stopień|klas\w*) ryzyka\s*:?\s*(?:niski|średni|wysoki|zmienia|\d)", r"\brisk of loss\b|\blose money\b|\bcapital (?:is )?at risk\b",
]
NOT_WARNING = r"zarządza\w* ryzyk\w*|ogranicz\w* (?:\w+ ){0,2}(?:ryzyk|strat)\w*|minimaliz\w*|kontrol\w* ryzyk\w*|stop loss|bez ryzyka|"\
              r"dywersyfik\w*|ochron\w* przed strat\w*|zabezpiecz\w* (?:się )?przed"
CTA = r"otwórz (?:darmowe |bezpłatne )?(?:konto|rachunek)|załóż (?:konto|rachunek|IKE|IKZE)|zacznij inwestować|zainwestuj|dołącz|zarejestruj|"\
      r"kup (?:teraz|obligacj|akcj|jednost)|zapisz się|otwórz IKE|otwórz IKZE|sprawdź ofertę|wypróbuj|rozpocznij"
AD_LABEL = r"\breklam[aąy]\b|materiał\w* (?:reklamow|marketingow|promocyjn)\w*|komunikat\w* (?:reklamow|marketingow)\w*|"\
           r"informacj\w* (?:reklamow|marketingow|promocyjn)\w*|charakter\w* (?:reklamow|marketingow|promocyjn)\w*|"\
           r"treś\w* (?:reklamow|marketingow)\w*|cel\w* (?:reklamow|marketingow|promocyjn)\w*|marketing communication|advertisement"
COMPARE = r"\bnajtańsz\w*|\bnajniższ\w* (?:prowizj|opłat|koszt|spread|cen)\w*|"\
          r"\bnajlepsz\w* (?:\w+ ){0,2}(?:broker\w*|platform\w*|dom\w*|ofert\w*|aplikacj\w*|warunk\w*|zesp\w*|analiz\w*|cen\w*|oprocentowani\w*|produkt\w*|rachun\w*|kont\w*)|"\
          r"\bnajwiększ\w* (?:wybór|dom|broker|platform)\w*|(?:\bnr|numer)\s?(?:1|jeden)\s+(?:w|na|wśród)\b|\blider\w* (?:rynku|branży|wśród)|tańsz\w* niż|lepsz\w* niż|korzystniejsz\w* niż|więcej niż (?:w|na) |"\
          r"(?:w porównaniu (?:z|do)|w przeciwieństwie do|\bvs\.?\s)(?=.*(?:tańsz|taniej|niższ|wyższ|lepsz|korzystn|koszt|opłat|prowizj|zysk|zwrot))|niż (?:na )?(?:lokat\w*|kont\w* oszczędnościow\w*|w banku|konkurencj\w*|inflacj\w*)|"\
          r"\d+\s?(?:x|razy) (?:więcej|taniej|niższ)"
SOURCE = r"źródło|według (?:danych|rankingu|raportu|badania|stanu)|wg\.? (?:danych|rankingu|raportu|stanu)|na podstawie (?:danych|rankingu|badania|raportu)|"\
         r"dane (?:z|za|wg)\b|stan na|ranking\w*|nagrod\w*|plebiscyt\w*|konkurs\w*|badani\w* (?:przeprowadzon|zrealizowan)|założen\w*|\bwedług\b"
HISTORY = r"wynik\w* historyczn\w*|stop\w* zwrotu (?:za|w|z) (?:lata|okres|rok\w*)|historyczn\w* (?:stop\w* zwrotu|wynik\w*|rentowno\w*|zwrot\w*)|stop\w* zwrotu (?:za|w|z) (?:ostatni\w*|20\d\d|rok)|"\
          r"w ciągu ostatnich \d+ lat|(?:zyskał|wzrósł|wzrosła|wzrosły|zarobił|przyniósł|przyniosła|przyniosły|osiągnął|osiągnęła|osiągnęły)\w* (?:\D{0,40})\d+(?:[.,]\d+)?\s?%|"\
          r"\d+(?:[.,]\d+)?\s?% (?:w|za) (?:20\d\d|ostatni\w*|rok\w* 20\d\d)|od początku roku|\bYTD\b|średnioroczn\w* (?:stop\w* zwrotu|zwrot\w*|wynik\w*)|"\
          r"stop\w* zwrotu (?:\w+ ){0,3}\d+(?:[.,]\d+)?\s?%"
HISTORY_WARNING = r"(?:wynik\w*|stop\w* zwrotu|rentowno\w*|zwrot\w*) (?:\w+ ){0,4}(?:historyczn\w*|z przeszłości|w przeszłości|osiągnięt\w*)\w* (?:\w+ ){0,5}nie "\
                  r"(?:\w+ ){0,3}(?:wiarygodn\w*|gwarancj\w*|gwarantuj\w*|przesądzaj\w*|oznacza\w*)|nie (?:są|jest|stanowi\w*) (?:\w+ ){0,2}(?:wiarygodn\w* wskaźnik\w*|gwarancj\w*) "\
                  r"(?:\w+ ){0,5}przyszł\w*|past performance"
FORECAST = r"\bprognoz\w*|przewidujemy|przewidywan\w* (?:zysk|wynik|stop|zwrot|wartoś)\w*|oczekiwan\w* (?:zysk|stop\w* zwrotu|zwrot|wynik)\w*|"\
           r"szacowan\w* (?:zysk|zwrot|dochód|wartoś)\w*|cen\w* docelow\w*|(?:po|za) \d+ lat\w* (?:\w+ ){0,2}(?:będziesz|możesz) (?:mieć|zgromadzić|uzbierać)|"\
           r"symulacj\w* (?:wyniku|zysku|oszczędno|kapitału)\w*|przy (?:\w+ ){0,2}oprocentowani\w* \d+(?:[.,]\d+)?\s?% (?:\w+ ){0,2}przez \d+ lat|"\
           r"kalkulator\w* (?:procentu składanego|zysk\w*|oszczędno\w*)|(?:możesz|mógłbyś|będziesz mógł) (?:zarobić|uzbierać|zgromadzić|odłożyć|zaoszczędzić) (?:\w+ ){0,4}\d"
FORECAST_WARNING = r"(?:prognoz|symulacj|przewidywan|szacun|kalkulac|wylicz)\w*.{0,90}nie (?:\w+ ){0,3}(?:wiarygodn\w*|gwarancj\w*|gwarantuj\w*|stanowi\w*)|"\
                   r"nie (?:\w+ ){0,3}wiarygodn\w* wskaźnik\w*.{0,40}przyszł\w*|nie stanowi\w* (?:\w+ ){0,2}gwarancji (?:\w+ ){0,3}(?:przyszł|osiągnięcia|uzyskania)\w*|"\
                   r"(?:ma|mają) charakter (?:wyłącznie )?(?:poglądow|szacunkow|ilustracyjn|informacyjn)\w*"
TAX = r"podatk\w* (?:Belki|od zysków kapitałowych)|zwolni\w* (?:z|od) (?:\w+ ){0,2}podatk\w*|bez (?:\w+ ){0,1}podatku|ulg\w* podatkow\w*|"\
      r"odlicz\w* (?:\w+ ){0,5}(?:od )?(?:podstawy opodatkowania|podatku|dochodu)|korzyś\w* podatkow\w*|oszczędz\w* (?:\w+ ){0,3}(?:na )?podat\w*|"\
      r"nie zapłacisz (?:\w+ ){0,2}podatku|zwrot\w* podatku|optymalizacj\w* podatkow\w*|preferencj\w* podatkow\w*|podatk\w* (?:\w+ ){0,2}zwolnion\w*"
TAX_PERSONAL = r"indywidualn\w* sytuacj\w*|sytuacj\w* (?:\w+ ){0,2}(?:klienta|inwestora|podatnika|osobist)\w*"
TAX_CHANGE = r"(?:może|mogą|mogłyby) (?:\w+ ){0,3}(?:ulec zmian\w*|się zmienić|zmienić)|zmian\w* (?:\w+ ){0,2}(?:przepisów|prawa|regulacji)|podlega\w* zmian\w*"
AUTHORITY = r"\bKNF\b|Komisj\w* Nadzoru Finansowego|\bESMA\b|\bBaFin\b|\bCySEC\b|\bFCA\b|Central Bank of Ireland|\bAFM\b|Národn\w* bank\w* Slovensk\w*|"\
            r"organ\w* nadzor\w*|instytucj\w* nadzor\w*|nadzor\w* (?:finansow|państwow)\w*|nadzorowan\w* przez|regulowan\w* przez|pod nadzorem"
APPROVAL = r"zatwierdz\w*|zaakceptowan\w*|aprob\w*|rekomend\w*|\bpoleca\w*|certyfik\w*|gwarantuj\w*|gwarancj\w*|pod (?:okiem|kontrolą|ochroną) (?:\w+ ){0,2}(?:KNF|Komisji|nadzor)|"\
           r"potwierdz\w*|autoryzowan\w* (?:produkt|instrument|ofert)"
APPROVAL_DISCLAIMER = r"nie (?:należy|można) (?:\w+ ){0,3}(?:rozumieć|traktować|uznawać) (?:\w+ ){0,3}(?:jako|za) (?:\w+ ){0,2}(?:poparci|rekomendac|gwarancj|zatwierdz)\w*|"\
                      r"nie oznacza (?:\w+ ){0,3}(?:poparcia|rekomendacji|gwarancji|aprobaty|zatwierdzenia)|nie (?:stanowi|jest) (?:\w+ ){0,2}(?:poparci|rekomendac|gwarancj)\w*"
SAFETY = r"bezpieczn\w*|bezpieczeństw\w*|\bpewn\w*|zaufan\w*|spokojn\w*|chronion\w*|ochron\w*|gwarant\w*|stabiln\w*"
NOT_SAFETY = r"logowani\w*|cyber\w*|w sieci|hasł\w*|phishing|oszust\w*|dane osobow\w*|SSL|szyfrow\w*|nie gwarantuj\w*|nie (?:jest|są) (?:\w+ ){0,2}gwarancj\w*|"\
             r"nie (?:należy|można) (?:\w+ ){0,3}(?:rozumieć|traktować)"
SENT = re.compile(r"(?<=[.!?])\s+(?=[A-ZĄĆĘŁŃÓŚŹŻ0-9„\"(])")
PL_WORDS = {"i", "w", "z", "na", "się", "nie", "do", "jest", "że", "to", "o", "od", "oraz", "lub", "dla", "są", "przez", "jak", "po", "może", "twoje", "ryzyko"}
EN_WORDS = {"the", "and", "of", "to", "in", "is", "are", "for", "with", "you", "your", "may", "can", "on", "or", "be", "risk", "money"}


def rx(patterns):
    return re.compile("|".join(f"(?:{p})" for p in patterns) if isinstance(patterns, list) else patterns, re.I)


R_PROFIT, R_NOT_PROFIT, R_WARNING, R_NOT_WARNING = rx(PROFIT), rx(NOT_PROFIT), rx(WARNING), rx(NOT_WARNING)
R = {name: rx(value) for name, value in {
    "cta": CTA, "ad": AD_LABEL, "compare": COMPARE, "source": SOURCE, "history": HISTORY, "historyWarning": HISTORY_WARNING,
    "forecast": FORECAST, "forecastWarning": FORECAST_WARNING, "tax": TAX, "taxPersonal": TAX_PERSONAL, "taxChange": TAX_CHANGE,
    "authority": AUTHORITY, "approval": APPROVAL, "approvalDisclaimer": APPROVAL_DISCLAIMER, "safety": SAFETY, "notSafety": NOT_SAFETY,
}.items()}
R_PRODUCTS = {key: rx(value) for key, value in PRODUCTS.items()}
RATE_TILE = re.compile(r"(?:do |nawet )?\d{1,2}(?:[.,]\d{1,2})?\s?%(?:\s*(?:rocznie|p\.\s?a\.|w skali roku))?", re.I)
R_RATE_LABEL = rx(r"oprocentowan\w*|rentown\w*|stop\w* zwrotu|\bzwrot\w*|\bzysk\w*|kupon\w*|odsetk\w*|dywidend\w*")


EDUCATION_PATH = r"/(?:edukac\w*|akadem\w*|poradnik\w*|baza-wiedzy|blog|artykul\w*|wiedza)(?:/|$)"
OWN_OFFER = r"\bz nami\b|\bu nas\b|w naszej ofercie|\botwórz (?:konto|rachunek)|\bnaszych klientów\b"

# ---------------------------------------------------------------- data model
@dataclass
class Block:
    index: int
    text: str
    px: float | None
    role: str
    section: int
    bbox: list | None
    first: float
    hidden: str | None
    fixed: str | None
    contrast: float | None
    contrast_reason: str | None
    heading: int | None
    tag: str
    truncated: str | None
    occluded: bool | None
    lang: str | None
    hints: list = field(default_factory=list)
    href: str | None = None

    @property
    def visible(self):
        return self.hidden is None and self.bbox is not None and self.role != "dialog"

    @property
    def top(self):
        return self.bbox[1] if self.bbox else None

    @property
    def bottom(self):
        return self.bbox[1] + self.bbox[3] if self.bbox else None


@dataclass
class View:
    name: str
    width: int
    height: int
    blocks: list
    doc_height: float
    scroll_width: float
    consent: dict
    risk_links: list
    screenshot: str | None = None
    dom: str | None = None
    layout_width: float | None = None


def load_view(name, dom, screenshot=None, dom_ref=None):
    blocks = [Block(i, b["t"], b.get("px"), b.get("role", "body"), b.get("sec", 0), b.get("bbox"), b.get("first", 0.0),
                    b.get("hid"), b.get("fix"), b.get("cr"), b.get("crw"), b.get("h"), b.get("tag", "div"), b.get("trunc"),
                    b.get("occ"), b.get("lang"), b.get("hint") or [], b.get("href"))
              for i, b in enumerate(dom.get("blocks", []))]
    layout = dom.get("layoutWidth") or dom.get("width", 0)
    # Geometry is in the page's layout pixels; a page that ignores the phone viewport is scaled down.
    height = dom.get("layoutHeight") or dom.get("height", 0)
    return View(name, dom.get("width", 0), height, blocks, dom.get("docHeight") or 1, dom.get("scrollWidth") or 0,
                dom.get("consent") or {}, dom.get("riskLinks") or [], screenshot, dom_ref, layout)


def sentences(text):
    return [s.strip() for s in SENT.split(text) if s.strip()]


def products_in(text):
    return {key for key, pattern in R_PRODUCTS.items() if pattern.search(text)}


@dataclass
class Hit:
    kind: str
    block: Block
    quote: str
    products: set
    scope: str = ""


STRONG_WARNING = re.compile(r"wiąż\w* się z|stracić|utracić|utrat\w*|strat\w*|ryzykown\w*|nie (?:\w+ ){0,2}gwarant\w*", re.I)
REFERENCE_ONLY = re.compile(r"deklaracj\w*|opis\w* ryzyka|dokument\w*|więcej informacji|zapoznaj się|regulamin\w*", re.I)


def is_warning(sentence):
    if not R_WARNING.search(sentence):
        return False
    if R_NOT_WARNING.search(sentence) and not re.search(r"utrat|stracić|strat\w* pieni", sentence, re.I):
        return False
    # A pointer to a risk document ("Deklaracja Świadomości Ryzyka Inwestycyjnego") is not itself a warning.
    return not (REFERENCE_ONLY.search(sentence) and not STRONG_WARNING.search(sentence))


def is_profit(sentence):
    if not R_PROFIT.search(sentence) or is_warning(sentence):
        return False
    if re.search(r"\bnie (?:\w+ ){0,2}(?:gwarantuj|zapewni|obiecuj)\w*", sentence, re.I):
        return False
    if NOT_INVESTMENT_GAIN.search(sentence) or sentence.rstrip().endswith("?"):
        return False
    if re.search(r"opłat|prowizj|koszt|marż", sentence, re.I) and not re.search(
            r"zysk|zarab|dochod|dochód|zwrot|rentown|oprocentow|dywidend|odsetk", sentence, re.I):
        return False
    stripped = R_NOT_PROFIT.sub("", sentence)
    return bool(R_PROFIT.search(stripped))


# Interest on uninvested cash and gains that are not money are not a potential profit of an investment.
NOT_INVESTMENT_GAIN = re.compile(
    r"(?:odset\w*|oprocentowani\w*) (?:\w+ ){0,2}(?:od |na )?(?:\w+ ){0,1}(?:wolnych|niezainwestowanych|nieulokowanych|wolne) środk\w*|"
    r"\bzysk(?:aj|asz|ać|ają|ujesz|uj)\w* (?:\w+ ){0,2}(?:dostęp\w*|narzędzi\w*|kontrol\w*|elastyczno\w*|wiedz\w*|czas\w*|wygod\w*|aplikacj\w*|możliwo\w*)", re.I)


def heading_products(view, block):
    """Products named by the nearest heading above the block in the same section."""
    best = None
    for other in view.blocks:
        if other.index >= block.index:
            break
        if other.heading and other.section == block.section and other.visible:
            best = other
    return products_in(best.text) if best else set()


def find(view, test, kind, *, visible=True, roles=None):
    hits = []
    for block in view.blocks:
        if visible and not block.visible:
            continue
        if not visible and block.visible:
            continue
        if roles and block.role not in roles:
            continue
        for sentence in sentences(block.text):
            if test(sentence):
                hits.append(Hit(kind, block, sentence[:400], products_in(sentence)))
    return hits


def warning_scope(hit):
    """'leveraged' for a CFD-style warning, a product set for a named product, else 'generic'."""
    if hit.products & {"cfd"} or re.search(r"dźwigni|\d+\s?% rachunków", hit.quote, re.I):
        return "leveraged"
    named = hit.products - {"rachunek"}
    return ",".join(sorted(named)) if named else "generic"


def compatible(warning, claim_products, claim_text=""):
    scope = warning.scope
    if scope == "generic":
        return True
    if scope == "leveraged":
        return bool(claim_products & LEVERAGED) or bool(re.search(r"\bCFD\b|dźwigni", claim_text, re.I))
    return bool(set(scope.split(",")) & claim_products)


def gap(a, b):
    """Vertical distance in CSS px between two boxes, 0 when they overlap vertically."""
    if a.bbox is None or b.bbox is None:
        return None
    return round(max(0.0, b.top - a.bottom, a.top - b.bottom), 1)


def accompanies(view, claim, warning):
    if warning.block.fixed and warning.block.first >= 0.5:
        return True, 0.0
    distance = gap(claim.block, warning.block)
    if distance is None:
        return False, None
    if distance <= ACCOMPANY_SCREEN * view.height:
        return True, distance
    same = claim.block.section and claim.block.section == warning.block.section
    return bool(same and distance <= SECTION_SCREEN * view.height), distance


def language(text):
    words = re.findall(r"[a-ząćęłńóśźż]+", text.lower())
    pl, en = sum(w in PL_WORDS for w in words), sum(w in EN_WORDS for w in words)
    if pl + en < 2:
        return None
    return "pl" if pl >= en else "en"


def dominant_px(view):
    counts = Counter()
    for block in view.blocks:
        if (block.visible and block.role in {"body"} and block.px and not block.heading and block.tag not in {"button", "a"}
                and not any(is_warning(s) for s in sentences(block.text))):
            counts[block.px] += len(block.text)
    return counts.most_common(1)[0][0] if counts else None


def legal_pattern(name):
    """Tolerant regex for the register name: legal forms with or without dots, flexible spacing."""
    name = re.sub(r"\s+", " ", name).strip()
    variants = [part.strip(" ()") for part in re.split(r"[()]", name) if len(part.strip(" ()")) > 3]
    out = []
    for variant in variants:
        variant = re.sub(r"\bS\.?\s?A\.?(?=\s|$)", " §SA§ ", variant)
        variant = re.sub(r"\bSp\.?\s?z\s?o\.?\s?o\.?", " §SPZOO§ ", variant, flags=re.I)
        tokens = [t for t in re.split(r"[\s,]+", variant) if t]
        parts = []
        for token in tokens:
            if token == "§SA§":
                parts.append(r"(?:S\.?\s?A\.?|Spółk\w* Akcyjn\w*)")
            elif token == "§SPZOO§":
                parts.append(r"(?:Sp\.?\s?z\s?o\.?\s?o\.?|Spółk\w* z ograniczoną odpowiedzialnością)")
            else:
                parts.append(re.escape(token.rstrip(".")) + (r"\.?" if token.endswith(".") else ""))
        out.append(r"[\s,]*".join(parts))
    return re.compile("|".join(f"(?:{p})" for p in out), re.I)


# ---------------------------------------------------------------- the checks
class Evaluation:
    def __init__(self, material):
        self.material = material
        views = material.get("views") or {}
        self.views = {name: view if isinstance(view, View) else
                      load_view(name, view, view.get("screenshotUrl"), view.get("domUrl"))
                      for name, view in views.items() if view is not None}
        self.desktop = self.views.get("desktop")
        self.phone = self.views.get("phone")
        self.main = self.desktop or self.phone
        self.rows = {}
        self.url = material.get("url")

    # ---- helpers
    def add(self, key, state, evidence, *, why=None, quote=None, measurements=None, mode="automatyczny", flags=None):
        row = {"id": key, "label": LABELS[key], "state": state, "mode": mode, "basis": BASIS[key],
               "evidence": evidence, "url": self.url}
        if why:
            row["applicability"] = why
        if quote:
            row["quote"] = quote
        if measurements:
            row["measurements"] = measurements
        if flags:
            row["flags"] = flags
        self.rows[key] = row

    def page_products(self):
        text = (self.url or "") + " " + (self.material.get("title") or "")
        heads = [b.text for b in self.main.blocks if b.heading == 1 and b.visible][:2]
        return products_in(" ".join([text] + heads).replace("-", " ").replace("/", " "))

    def claim_products(self, view, hit):
        return (hit.products | heading_products(view, hit.block)) or self.page_products()

    def measure(self, view, block, extra=None):
        data = {"viewport": f"{view.name} {view.width}×{view.height}", "bbox": block.bbox, "px": block.px,
                "role": block.role, "section": block.section, "firstScreen": block.first, "contrast": block.contrast,
                "fixed": block.fixed, "hidden": block.hidden, "screenshot": view.screenshot, "dom": view.dom,
                "blockIndex": block.index}
        if extra:
            data.update(extra)
        return data

    # ---- shared facts
    def collect(self):
        main = self.main
        self.claims = {name: [h for h in find(view, is_profit, "claim") if h.block.role not in {"nav", "footer"}] + self.rate_tiles(view)
                       for name, view in self.views.items()}
        # Interest with no investment product anywhere in sight (a savings account) is outside these criteria.
        self.claims = {name: [c for c in claims if self.claim_products(self.views[name], c)
                              or not re.search(r"oprocentowan|odsetk", c.quote, re.I)] for name, claims in self.claims.items()}
        # On an education page, sentences about profit are the topic of articles, not the firm's promise,
        # unless the sentence itself sells the firm's offer.
        self.education = bool(re.search(EDUCATION_PATH, self.url or "", re.I)) or self.material.get("kind") == "education"
        if self.education:
            self.claims = {name: [c for c in claims if re.search(OWN_OFFER, c.quote, re.I)] for name, claims in self.claims.items()}
        self.hidden_claims = find(main, is_profit, "claim", visible=False)
        self.warnings = {}
        for name, view in self.views.items():
            hits = [h for h in find(view, is_warning, "warning") if h.block.role != "nav"]
            for hit in hits:
                hit.scope = warning_scope(hit)
            self.warnings[name] = hits
        self.hidden_warnings = find(main, is_warning, "warning", visible=False)
        for hit in self.hidden_warnings:
            hit.scope = warning_scope(hit)
        self.cta = [h for h in find(main, lambda s: bool(R["cta"].search(s)), "cta") if h.block.role in {"body", "header"}]
        self.products = set().union(*(self.claim_products(main, h) for h in self.claims.get(main.name, []))) if self.claims.get(main.name) else self.page_products()
        self.promotional = bool(self.claims.get(main.name) or self.cta) and self.material.get("kind") != "education_only"
        self.relevant = {name: [w for w in self.warnings[name] if self.compatible_any(name, w)] for name in self.views}
        if self.education and not any(self.claims.values()):
            # Risk sentences inside article teasers are not the firm's warning for an offer.
            self.relevant = {name: [] for name in self.views}

    @staticmethod
    def rate_tiles(view):
        """A bare rate ("4,00%") shown as a tile next to a label about interest or return is a profit claim too."""
        hits = []
        visible = [b for b in view.blocks if b.visible and b.role in {"body", "header"}]
        for block in visible:
            if not RATE_TILE.fullmatch(block.text.strip()) or re.fullmatch(r"0(?:[.,]0+)?\s?%", block.text.strip()):
                continue
            label = next((b for b in visible if b is not block and R_RATE_LABEL.search(b.text) and len(b.text) < 160
                          and ((b.section and b.section == block.section) or (gap(b, block) is not None and gap(b, block) <= 150))), None)
            if label:
                hits.append(Hit("claim", block, f"{label.text.strip()[:120]}: {block.text.strip()}", products_in(label.text)))
        return hits

    def compatible_any(self, name, warning):
        claims = self.claims.get(name, [])
        if not claims:
            return compatible(warning, self.products)
        view = self.views[name]
        return any(compatible(warning, self.claim_products(view, c), c.quote) for c in claims)

    def primary_warning(self, name):
        """The warning the reader is meant to see: nearest to a claim, else the most prominent one."""
        view, warnings = self.views[name], self.relevant.get(name, [])
        if not warnings:
            return None
        claims = self.claims.get(name, [])
        if claims:
            def key(w):
                distances = [gap(c.block, w.block) for c in claims if compatible(w, self.claim_products(view, c), c.quote)]
                return (min([d for d in distances if d is not None], default=1e9), w.block.role in {"footer", "footnote"})
            return min(warnings, key=key)
        return sorted(warnings, key=lambda w: (w.block.role in {"footer", "footnote"}, w.block.top or 0))[0]

    def no_warning_state(self):
        """Applicability for rows 4–10 when no warning of the promoted product was found."""
        if not self.claims.get(self.main.name) and not self.promotional:
            return NA, "Materiał nie zawiera twierdzeń o zysku ani wezwania do zakupu; brak informacji o ryzyku do oceny."
        if not self.claims.get(self.main.name):
            return NA, "Brak twierdzenia o zysku i brak informacji o ryzyku dla promowanego produktu, więc nie ma czego mierzyć."
        return UNKNOWN, "Nie znaleziono informacji o ryzyku dotyczącej promowanego produktu (zob. kryterium 3), więc nie ma czego mierzyć."

    # ---- rows
    def check_1(self):
        firm = self.material.get("firm") or {}
        name = firm.get("name")
        if not name:
            return self.add("1", UNKNOWN, "Brak nazwy z rejestru KNF dla wydawcy.", why="Nie ustalono wpisu w rejestrze.", mode="ręczny")
        pattern = legal_pattern(name)
        visible = next((b for b in self.main.blocks if b.visible and pattern.search(b.text)), None)
        hidden = next((b for b in self.main.blocks if not b.visible and pattern.search(b.text)), None)
        if visible:
            quote = pattern.search(visible.text).group(0)
            where = {"footer": "stopce", "footnote": "przypisie", "header": "nagłówku"}.get(visible.role, "treści")
            return self.add("1", OK, f"Nazwa z rejestru KNF „{name}” występuje w {where} strony: „{quote}”.", quote=visible.text[:300],
                            measurements=[self.measure(self.main, visible)])
        if hidden:
            return self.add("1", PREMISE, f"Nazwa „{name}” jest tylko w elemencie ukrytym ({hidden.hidden}).", quote=hidden.text[:300],
                            measurements=[self.measure(self.main, hidden)])
        self.add("1", PREMISE, f"Na stronie (łącznie ze stopką) nie znaleziono oficjalnej nazwy z rejestru KNF: „{name}”.")

    def check_2(self):
        hits = find(self.main, lambda s: bool(R["ad"].search(s)) and not re.search(r"reklamacj", s, re.I), "ad")
        if not self.promotional:
            return self.add("2", NA, "Strona nie zawiera twierdzeń o zysku ani wezwania do zakupu; traktujemy ją jako informacyjną.",
                            why="Materiał informacyjny lub edukacyjny.")
        if hits:
            hit = sorted(hits, key=lambda h: h.block.role in {"footer", "footnote"})[0]
            note = " Oznaczenie jest tylko w stopce." if hit.block.role in {"footer", "footnote"} else ""
            return self.add("2", OK, f"Oznaczenie: „{hit.quote[:200]}”.{note}", quote=hit.quote,
                            measurements=[self.measure(self.main, hit.block)], mode="wspomagany" if note else "automatyczny")
        cta = self.cta[0].quote if self.cta else (self.claims[self.main.name][0].quote if self.claims.get(self.main.name) else "")
        self.add("2", OBSERVATION, f"Obserwacja bez wpływu na wynik: strona promuje usługę („{cta[:120]}”), a nigdzie nie oznaczono jej jako reklamy lub materiału marketingowego.",
                 quote=cta, mode="wspomagany")

    def check_3(self):
        claims_all = {name: claims for name, claims in self.claims.items() if claims}
        if not claims_all:
            note = " Korzyści cenowe (np. brak prowizji) nie są twierdzeniem o zysku." if self.promotional else ""
            if self.hidden_claims:
                note += f" Wzmianka o zysku tylko w zwiniętym elemencie: „{self.hidden_claims[0].quote[:120]}”."
            return self.add("3", NA, "Nie wykryto twierdzenia o potencjalnym zysku." + note, why="Brak twierdzenia o zysku.")
        failures, measurements, quote = [], [], None
        rejected = []
        for name, claims in claims_all.items():
            view = self.views[name]
            for claim in claims:
                products = self.claim_products(view, claim)
                matches = [w for w in self.warnings[name] if compatible(w, products, claim.quote)]
                rejected += [w for w in self.warnings[name] if w not in matches]
                results = [(accompanies(view, claim, w), w) for w in matches]
                if re.search(r"ryzyk\w*|strat\w*|utrat\w*", claim.quote, re.I):
                    # The claim itself names the risk ("wysoki zysk, przy wyższym ryzyku").
                    results.append(((True, 0.0), Hit("warning", claim.block, claim.quote, claim.products, "generic")))
                ok = [(d, w) for (good, d), w in results if good]
                best = min(results, key=lambda item: item[0][1] if item[0][1] is not None else 1e9) if results else None
                entry = self.measure(view, claim.block, {"focus": "claim", "quote": claim.quote, "products": sorted(products)})
                if best:
                    entry.update(warningQuote=best[1].quote, warningBbox=best[1].block.bbox, distancePx=best[0][1],
                                 warningScope=best[1].scope, warningFixed=best[1].block.fixed)
                measurements.append(entry)
                if not ok:
                    failures.append((name, claim, best, products))
                    quote = quote or claim.quote
        if not failures:
            first = measurements[0]
            return self.add("3", OK, f"Twierdzenie „{first['quote'][:160]}” ma w pobliżu informację o ryzyku: „{(first.get('warningQuote') or '')[:160]}” "
                            f"(odległość {first.get('distancePx')} px).", quote=first["quote"], measurements=measurements, mode="wspomagany")
        name, claim, best, products = failures[0]
        product_label = ", ".join(sorted(products)) or "promowany produkt"
        if best:
            text = (f"Twierdzenie o zysku „{claim.quote[:180]}” ({name}) nie ma bezpośrednio obok informacji o ryzyku. Najbliższe właściwe ostrzeżenie "
                    f"„{best[1].quote[:150]}” jest {best[0][1]} px dalej (próg: pół ekranu, {int(ACCOMPANY_SCREEN * self.views[name].height)} px).")
        else:
            text = (f"Twierdzenie o zysku „{claim.quote[:180]}” dotyczy: {product_label}. Na stronie nie ma informacji o ryzyku tego produktu.")
            other = next((w for w in rejected if w.scope == "leveraged"), None)
            if other:
                text += f" Jedyne ostrzeżenie dotyczy innego instrumentu (CFD): „{other.quote[:120]}”."
        if len({id(f[1]) for f in failures}) > 1:
            text += f" Takich twierdzeń: {len({f[1].quote for f in failures})}."
        self.add("3", PREMISE, text, quote=quote, measurements=measurements, mode="wspomagany")

    def check_4(self):
        rows = []
        for name, view in self.views.items():
            warning = self.primary_warning(name)
            dominant = dominant_px(view)
            if warning and warning.block.px and dominant:
                rows.append((name, view, warning, dominant))
        if not rows:
            state, why = self.no_warning_state()
            if self.relevant.get(self.main.name):
                state, why = UNKNOWN, "Nie ustalono dominującego rozmiaru tekstu strony."
            return self.add("4", state, why, why=why)
        smaller = [(n, v, w, d) for n, v, w, d in rows if w.block.px < SIZE_RATIO * d]
        text = " · ".join(f"{n}: ostrzeżenie {w.block.px:g} px, przeważający tekst {d:g} px" for n, v, w, d in rows)
        measurements = [self.measure(v, w.block, {"focus": "warning", "dominantPx": d, "ratio": round(w.block.px / d, 2)}) for n, v, w, d in rows]
        state = PREMISE if smaller else OK
        lead = "Informacja o ryzyku jest wyraźnie mniejsza od przeważającego tekstu. " if smaller else ""
        self.add("4", state, lead + text + f". Próg zespołu: {int(SIZE_RATIO * 100)}% przeważającego rozmiaru.", quote=rows[0][2].quote,
                 measurements=measurements)

    def check_5(self):
        problems, measurements = [], []
        for name, view in self.views.items():
            warning = self.primary_warning(name)
            if not warning:
                continue
            block = warning.block
            measurements.append(self.measure(view, block, {"focus": "warning", "quote": warning.quote}))
            if block.contrast is not None and block.contrast < MIN_CONTRAST:
                problems.append(f"{name}: kontrast {str(block.contrast).replace('.', ',')}:1 (poniżej {str(MIN_CONTRAST).replace('.', ',')}:1)")
            if block.occluded and not view.consent.get("overlayAfter"):
                problems.append(f"{name}: tekst przesłonięty innym elementem")
            claims = [c for c in self.claims.get(name, []) if c.block.first >= 0.5]
            if claims and block.first < 0.5 and not block.fixed:
                problems.append(f"{name}: korzyść widoczna od razu („{claims[0].quote[:80]}”), ostrzeżenie dopiero po przewinięciu (y={block.top:g} px)")
        if not measurements:
            state, why = self.no_warning_state()
            return self.add("5", state, why, why=why)
        contrasts = " · ".join(f"{m['viewport']}: kontrast {m['contrast'] if m['contrast'] is not None else 'nieustalony'}" for m in measurements)
        if problems:
            return self.add("5", PREMISE, "; ".join(problems) + ". " + contrasts + ".", quote=measurements[0]["quote"], measurements=measurements,
                            mode="wspomagany")
        unknown = [m for m in measurements if m["contrast"] is None]
        self.add("5", OK, ("Ostrzeżenie czytelne i nieprzesłonięte. " if not unknown else
                                                 "Brak przesłonięcia; kontrastu nie zmierzono przy złożonym tle. ") + contrasts + ".",
                 quote=measurements[0]["quote"], measurements=measurements, mode="automatyczny" if not unknown else "wspomagany")

    def check_6(self):
        warnings = self.relevant.get(self.main.name, [])
        if not warnings:
            state, why = self.no_warning_state()
            if [w for w in self.hidden_warnings if compatible(w, self.products)]:
                state, why = PREMISE, "Informacja o ryzyku istnieje tylko w elemencie ukrytym (zob. kryterium 7)."
            return self.add("6", state, why, why=why if state != PREMISE else None)
        prominent = [w for w in warnings if w.block.role in {"body", "header"} and "footnote" not in w.block.hints
                     and not {"legal", "disclaimer"} & set(w.block.hints)]
        claims = self.claims.get(self.main.name, [])
        low = [w for w in prominent if w.block.top and w.block.top > LOW_POSITION * self.main.doc_height and claims
               and all(c.block.top < LOW_POSITION * self.main.doc_height for c in claims)]
        if prominent and len(low) < len(prominent):
            best = next(w for w in prominent if w not in low)
            return self.add("6", OK, f"Informacja o ryzyku jest w treści strony, nie tylko w stopce lub przypisie: „{best.quote[:160]}”.",
                            quote=best.quote, measurements=[self.measure(self.main, best.block)])
        where = warnings[0]
        place = {"footer": "stopce", "footnote": "przypisie lub nocie prawnej"}.get(where.block.role, "dolnej części strony")
        self.add("6", PREMISE, f"Informacja o ryzyku jest tylko w {place} (y={where.block.top:g} z {self.main.doc_height:g} px): „{where.quote[:160]}”.",
                 quote=where.quote, measurements=[self.measure(self.main, where.block)], mode="wspomagany")

    def check_7(self):
        visible = self.relevant.get(self.main.name, [])
        hidden = [w for w in self.hidden_warnings if compatible(w, self.products)]
        links = [link for link in self.main.risk_links if re.search(r"ryzyk|strat|risk|ostrzeżeni\w* o ryzyku", link["t"], re.I)
                 and not re.search(r"wyłudz|phishing|oszust|bezpieczeństw\w* w sieci|poziom ryzyka", link["t"], re.I)]
        if visible:
            return self.add("7", OK, f"Informacja o ryzyku widoczna bez rozwijania ani klikania: „{visible[0].quote[:160]}”.", quote=visible[0].quote,
                            measurements=[self.measure(self.main, visible[0].block)])
        if hidden:
            h = hidden[0]
            return self.add("7", PREMISE, f"Informacja o ryzyku jest w elemencie zwiniętym ({h.block.hidden}); odbiorca musi go rozwinąć: „{h.quote[:160]}”.",
                            quote=h.quote, measurements=[self.measure(self.main, h.block)])
        if links and (self.claims.get(self.main.name) or self.promotional):
            return self.add("7", PREMISE, f"Informacja o ryzyku dostępna dopiero po kliknięciu odsyłacza „{links[0]['t'][:80]}” ({links[0]['href'][:120]}).",
                            quote=links[0]["t"], mode="wspomagany")
        state, why = self.no_warning_state()
        self.add("7", state, why, why=why)

    def check_8(self):
        if not (self.desktop and self.phone):
            return self.add("8", UNKNOWN, "Brak pomiaru na obu ekranach (komputer i telefon).", why="Brak jednego z widoków.")
        problems, measurements = [], []
        if self.phone.layout_width and self.phone.layout_width > 1.1 * self.phone.width:
            problems.append(f"strona nie dopasowuje się do telefonu: układ {self.phone.layout_width:g} px pomniejszony do ekranu {self.phone.width} px, "
                            f"więc tekst jest skalowany w dół")
        elif self.phone.scroll_width > max(self.phone.width, self.phone.layout_width or 0) + 4:
            problems.append(f"na telefonie strona jest szersza niż ekran ({self.phone.scroll_width:g} px przy {self.phone.width} px)")
        desk, mob = self.primary_warning("desktop"), self.primary_warning("phone")
        if desk and not mob:
            problems.append("ostrzeżenie widoczne na komputerze nie jest widoczne na telefonie")
        if mob:
            measurements.append(self.measure(self.phone, mob.block, {"focus": "warning"}))
            if mob.block.truncated:
                problems.append(f"tekst ostrzeżenia na telefonie jest ucięty ({mob.block.truncated})")
            if mob.block.px and mob.block.px < MIN_PX:
                problems.append(f"ostrzeżenie na telefonie ma {mob.block.px:g} px (próg pomocniczy {MIN_PX} px)")
        if desk:
            measurements.append(self.measure(self.desktop, desk.block, {"focus": "warning"}))
        if not desk and not mob and not problems:
            state, why = self.no_warning_state()
            return self.add("8", state, why + " Układ strony na telefonie mieści się w szerokości ekranu.", why=why)
        if problems:
            return self.add("8", PREMISE, "; ".join(problems).capitalize() + ".", quote=(mob or desk).quote if (mob or desk) else None,
                            measurements=measurements)
        sizes = " · ".join(f"{m['viewport']}: {m['px']:g} px" for m in measurements if m["px"])
        self.add("8", OK, f"Ostrzeżenie widoczne i nieucięte na komputerze i telefonie ({sizes}); brak poziomego przewijania.", quote=(mob or desk).quote,
                 measurements=measurements)

    def check_9(self):
        warning = self.primary_warning(self.main.name)
        if not warning:
            state, why = self.no_warning_state()
            return self.add("9", state, why, why=why)
        text = warning.block.text if len(warning.block.text) < 900 else warning.quote
        result = m2_readability.measure(text)
        audience = self.material.get("audience") or "klient detaliczny (strona publiczna)"
        detail = m2_readability.describe(result)
        if result and result["esmaStandard"]:
            return self.add("9", OK, f"Adresat: {audience}. Standardowa treść ostrzeżenia ESMA dla CFD; wskaźnik informacyjny: {detail}",
                            quote=text[:300], measurements=[{"readability": result}], mode="wspomagany")
        state = PREMISE if result and result["difficult"] else OK
        lead = "Ostrzeżenie może być trudne dla przeciętnego klienta detalicznego: " if state == PREMISE else "Język ostrzeżenia mieści się w progach pomocniczych: "
        self.add("9", state, f"Adresat: {audience}. {lead}{detail} Przekroczone: {', '.join(result['exceeded']) or 'żaden'} (wskaźnik pomocniczy, nie próg UKNF).",
                 quote=text[:300], measurements=[{"readability": result}], mode="wspomagany")

    def check_10(self):
        warning = self.primary_warning(self.main.name)
        if not warning:
            state, why = self.no_warning_state()
            return self.add("10", state, why, why=why)
        claims = self.claims.get(self.main.name) or []
        message = " ".join([c.quote for c in claims] + [b.text for b in self.main.blocks if b.heading and b.visible][:6])
        main_lang, warn_lang = language(message), language(warning.block.text)
        if not main_lang or not warn_lang:
            return self.add("10", UNKNOWN, "Za mało tekstu, by rozpoznać język przekazu i ostrzeżenia.", why="Za krótki tekst.")
        if main_lang != warn_lang:
            return self.add("10", PREMISE, f"Przekaz w języku {main_lang}, a informacja o ryzyku w języku {warn_lang}: „{warning.quote[:140]}”.",
                            quote=warning.quote)
        self.add("10", OK, f"Przekaz i informacja o ryzyku w tym samym języku ({main_lang}; słowa funkcyjne, nie atrybut lang).", quote=warning.quote)

    def check_11(self):
        hits = [h for h in find(self.main, lambda s: bool(R["compare"].search(s)) and not s.rstrip().endswith("?"), "compare")
                if h.block.role in {"body", "header"}]
        if not hits:
            return self.add("11", NA, "Nie wykryto porównania z innymi produktami lub usługami.", why="Brak porównania.")
        award_note = next((b for b in self.main.blocks if b.visible and re.match(r"^\s*(?:\d{1,2}|[¹²³⁴⁵*])\s*\S", b.text)
                           and re.search(r"nagrod|award|ranking|wyróżnien|plebiscyt|konkurs|według", b.text, re.I)), None)
        without = []
        for hit in hits:
            if award_note and re.search(r"najlepsz|nagrod|\bnr\s?1|numer jeden", hit.quote, re.I) and re.search(r"[¹²³⁴⁵*]|\d\s*$", hit.block.text):
                continue
            near = [b for b in self.main.blocks if b.section == hit.block.section and b.section] + [hit.block]
            footnote = "*" in hit.block.text or re.search(r"[¹²³]", hit.block.text)
            if not (R["source"].search(hit.quote) or any(R["source"].search(b.text) for b in near) or footnote):
                without.append(hit)
        if without:
            h = without[0]
            return self.add("11", PREMISE, f"Porównanie bez wskazanego źródła lub założeń: „{h.quote[:200]}”. Wstępna flaga do przeglądu analityka.",
                            quote=h.quote, measurements=[self.measure(self.main, h.block)], mode="wspomagany")
        self.add("11", OK, f"Porównanie ma wskazane źródło lub założenia w tej samej sekcji: „{hits[0].quote[:200]}”.", quote=hits[0].quote,
                 mode="wspomagany")

    def history_hits(self):
        return [h for h in find(self.main, lambda s: bool(R["history"].search(s)), "history") if h.block.role in {"body", "header"}]

    def section_text(self, block):
        return " ".join(b.text for b in self.main.blocks if (b.section == block.section and block.section) or b is block)

    def page_text(self):
        return " ".join(b.text for b in self.main.blocks if b.role != "dialog")

    def check_12(self):
        hits = self.history_hits()
        if not hits:
            for key in ("12a", "12b"):
                self.add(key, NA, "Nie wykryto prezentacji wyników historycznych.", why="Brak wyników historycznych.")
            return
        hit = hits[0]
        context = self.section_text(hit.block) + " " + " ".join(h.quote for h in hits)
        years = sorted({int(y) for y in re.findall(r"\b(20[0-2]\d)\b", context)})
        consecutive = max((len(run) for run in _runs(years)), default=0)
        five = consecutive >= 5 or re.search(r"ostatnich (?:5|pięciu) lat|od (?:początku działalności|debiutu|utworzenia)", context, re.I)
        partial = re.search(r"od początku roku|\bYTD\b|\b[136]M\b|ostatni\w* (?:miesiąc|kwartał|[2-9] miesi)", context, re.I)
        period = re.search(r"\b20\d\d\s*[–—-]\s*20\d\d\b|za okres|od \d{1,2}[./]\d{1,2}[./]20\d\d|stan na|na dzień", context, re.I)
        source = R["source"].search(context)
        missing = [name for name, ok in (("ostatnie 5 lat", five), ("pełne okresy 12-miesięczne", not partial),
                                         ("okres referencyjny", period), ("źródło danych", source)) if not ok]
        measurements = [self.measure(self.main, hit.block, {"years": years})]
        if missing:
            self.add("12a", PREMISE, f"Wyniki historyczne „{hit.quote[:160]}” bez: {', '.join(missing)}.", quote=hit.quote, measurements=measurements,
                     mode="wspomagany")
        else:
            self.add("12a", OK, f"Wyniki historyczne z okresem {years[0]}–{years[-1] if years else ''}, okresem referencyjnym i źródłem.", quote=hit.quote,
                     measurements=measurements, mode="wspomagany")
        foreign = re.search(r"\bUSD\b|\bEUR\b|\bGBP\b|\bCHF\b|\$|€|dolar\w*|\beuro\b", context, re.I)
        currency_ok = re.search(r"(?:kurs\w*|walut\w*) (?:\w+ ){0,6}(?:wpływ|zmniejsz|zwiększ|obniż|zmian|wah)\w*|ryzyk\w* walutow\w*", context, re.I)
        fees_ok = re.search(r"(?:uwzględnia\w*|nie uwzględnia\w*|po (?:potrąceniu|odliczeniu|uwzględnieniu)|przed (?:potrąceniem|odliczeniem)|pomniejszon\w*|brutto|netto)"
                            r"(?:\w+ ){0,1}\W*(?:\w+ ){0,4}(?:opłat|prowizj|koszt|podatk)\w*|(?:opłat|prowizj|koszt)\w* (?:\w+ ){0,4}(?:obniż|zmniejsz|pomniejsz|wpływ)\w*",
                            context, re.I)
        parts = []
        if foreign and not currency_ok:
            parts.append("ostrzeżenia o wpływie kursów walut (wynik w walucie obcej)")
        if not fees_ok:
            parts.append("informacji o wpływie prowizji, opłat i innych obciążeń")
        note = "" if foreign else " Część walutowa nie dotyczy (brak waluty obcej)."
        if parts:
            self.add("12b", PREMISE, f"Przy wynikach historycznych brak {' oraz '.join(parts)}.{note}", quote=hit.quote, measurements=measurements,
                     mode="wspomagany")
        else:
            self.add("12b", OK, f"Przy wynikach historycznych podano wpływ kosztów{' i kursów walut' if foreign else ''}.{note}", quote=hit.quote,
                     measurements=measurements, mode="wspomagany")

    def check_13(self):
        hits = self.history_hits()
        if not hits:
            return self.add("13", NA, "Nie wykryto prezentacji wyników historycznych.", why="Brak wyników historycznych.")
        first_screen = [b for b in self.main.blocks if b.visible and b.first >= 0.5 and b.px]
        biggest = max((b.px for b in first_screen), default=None)
        dominant = [h for h in hits if h.block.heading in {1, 2} or (h.block.first >= 0.5 and biggest and h.block.px and h.block.px >= 0.9 * biggest)]
        if dominant:
            h = dominant[0]
            return self.add("13", PREMISE, f"Wyniki historyczne zajmują najbardziej eksponowane miejsce (nagłówek lub największy tekst pierwszego ekranu): „{h.quote[:160]}”.",
                            quote=h.quote, measurements=[self.measure(self.main, h.block)])
        self.add("13", OK, f"Wyniki historyczne nie są najbardziej eksponowanym elementem (pierwszy: y={hits[0].block.top:g} px, {hits[0].block.px} px).",
                 quote=hits[0].quote, measurements=[self.measure(self.main, hits[0].block)])

    def check_14(self):
        hits = self.history_hits()
        if not hits:
            return self.add("14", NA, "Nie wykryto prezentacji wyników historycznych.", why="Brak wyników historycznych.")
        text = self.page_text()
        warn = R["historyWarning"].search(text)
        if not warn:
            return self.add("14", PREMISE, f"Wyniki historyczne „{hits[0].quote[:160]}” bez zastrzeżenia, że nie są wiarygodnym wskaźnikiem przyszłych wyników.",
                            quote=hits[0].quote, measurements=[self.measure(self.main, hits[0].block)])
        exact = "wiarygodn" in warn.group(0).lower()
        self.add("14", OK, f"Zastrzeżenie: „{warn.group(0)[:160]}”." + ("" if exact else " Sformułowanie zastępcze (brak gwarancji), szersze od wymaganego."),
                 quote=warn.group(0), mode="automatyczny" if exact else "wspomagany")

    def check_15(self):
        hits = [h for h in find(self.main, lambda s: bool(R["forecast"].search(s)), "forecast") if h.block.role in {"body", "header"}]
        hits = [h for h in hits if not re.search(r"prognoz\w* pogody|prognoz\w* (?:makro|gospodarcz|analityk)", h.quote, re.I)
                and not is_warning(h.quote) and not h.quote.rstrip().endswith("?")]
        if not hits:
            return self.add("15", NA, "Nie wykryto prognozy przyszłych wyników.", why="Brak prognozy.")
        warn = R["forecastWarning"].search(self.page_text())
        flags = ["wykryto prognozę"]
        if not warn:
            return self.add("15", PREMISE, f"Wykryto prognozę: „{hits[0].quote[:180]}”. Brak ostrzeżenia, że prognoza nie jest wiarygodnym wskaźnikiem przyszłych wyników.",
                            quote=hits[0].quote, measurements=[self.measure(self.main, hits[0].block)], flags=flags)
        self.add("15", OK, f"Wykryto prognozę: „{hits[0].quote[:160]}”. Jest zastrzeżenie: „{warn.group(0)[:140]}”. Założenia prognozy ocenia analityk.",
                 quote=hits[0].quote, measurements=[self.measure(self.main, hits[0].block)], flags=flags, mode="wspomagany")

    def check_16(self):
        hits = [h for h in find(self.main, lambda s: bool(R["tax"].search(s)), "tax") if h.block.role in {"body", "header"}
                and (not self.education or re.search(OWN_OFFER, h.quote, re.I))]
        if not hits:
            return self.add("16", NA, "Materiał nie odwołuje się do traktowania podatkowego.", why="Brak odwołania do podatków.")
        text = self.page_text()
        personal, change = R["taxPersonal"].search(text), R["taxChange"].search(text)
        missing = [name for name, ok in (("zależności od indywidualnej sytuacji klienta", personal), ("możliwości zmiany przepisów", change)) if not ok]
        if missing:
            return self.add("16", PREMISE, f"Odwołanie do podatków „{hits[0].quote[:160]}” bez informacji o {' i '.join(missing)}.", quote=hits[0].quote,
                            measurements=[self.measure(self.main, hits[0].block)])
        self.add("16", OK, f"Odwołanie do podatków z informacją o indywidualnej sytuacji („{personal.group(0)}”) i możliwych zmianach („{change.group(0)}”).",
                 quote=hits[0].quote)

    def authority_hits(self):
        return [h for h in find(self.main, lambda s: bool(R["authority"].search(s)), "authority")]

    def check_17(self):
        hits = self.authority_hits()
        if not hits:
            return self.add("17", NA, "Materiał nie odwołuje się do KNF ani innego organu nadzoru.", why="Brak odwołania do organu.")
        page_disclaimer = R["approvalDisclaimer"].search(self.page_text())
        suggestive = [h for h in hits if R["approval"].search(h.quote) and not R["approvalDisclaimer"].search(h.quote)
                      and not page_disclaimer]
        if suggestive:
            h = suggestive[0]
            return self.add("17", PREMISE, f"Odwołanie do organu nadzoru może sugerować zatwierdzenie lub poparcie oferty: „{h.quote[:200]}”.",
                            quote=h.quote, measurements=[self.measure(self.main, h.block)], mode="wspomagany")
        self.add("17", OK, f"Odwołanie do organu ma charakter informacyjny: „{hits[0].quote[:200]}”.", quote=hits[0].quote, mode="wspomagany")

    def check_18(self):
        hits = self.authority_hits()
        if not hits:
            return self.add("18", NA, "Materiał nie odwołuje się do KNF ani innego organu nadzoru.", why="Brak odwołania do organu.")
        found = None
        for h in hits:
            if h.block.role in {"footer", "dialog"}:
                continue
            if R["safety"].search(h.quote) and not R["notSafety"].search(h.quote):
                found = (h, h.quote)
                break
            heads = [b for b in self.main.blocks if b.section == h.block.section and h.block.section and b.heading and b.visible]
            safe_head = next((b for b in heads if R["safety"].search(b.text) and not R["notSafety"].search(b.text)), None)
            if safe_head:
                found = (h, f"{safe_head.text[:80]} — {h.quote}")
                break
        if found:
            h, quote = found
            return self.add("18", PREMISE, f"Bezpieczeństwo oferty wywiedzione z nadzoru: „{quote[:220]}”.", quote=h.quote,
                            measurements=[self.measure(self.main, h.block)], mode="wspomagany")
        self.add("18", OK, f"Odwołanie do nadzoru bez wywodzenia z niego bezpieczeństwa inwestycji: „{hits[0].quote[:160]}”.", quote=hits[0].quote,
                 mode="wspomagany")

    def run(self):
        if not self.main or not any(b.visible for b in self.main.blocks):
            for key in ORDER:
                self.add(key, UNKNOWN, "Brak odczytanego tekstu strony.", why="Brak danych z renderu.", mode="ręczny")
            return [self.rows[key] for key in ORDER]
        self.collect()
        for method in (self.check_1, self.check_2, self.check_3, self.check_4, self.check_5, self.check_6, self.check_7,
                       self.check_8, self.check_9, self.check_10, self.check_11, self.check_12, self.check_13, self.check_14,
                       self.check_15, self.check_16, self.check_17, self.check_18):
            method()
        return [self.rows[key] for key in ORDER]


def _runs(years):
    run = []
    for year in years:
        if run and year != run[-1] + 1:
            yield run
            run = []
        run.append(year)
    if run:
        yield run


def evaluate(material):
    """Return the 19 rows in UKNF order."""
    return Evaluation(material).run()
