"""Evidence-led triage of the 19 UKNF marketing material checks."""
from collections import Counter
import re

from .m2_evidence import show_checks

LABELS = {
    "1": "Nazwa prawna firmy", "2": "Rozpoznawalność reklamy", "3": "Korzyść a istotne ryzyko",
    "4": "Ostrzeżenie a dominujący krój pisma", "5": "Widoczność i kontrast",
    "6": "Stopka i przypisy", "7": "Dostęp po interakcji", "8": "Ekran odbiorcy",
    "9": "Zrozumiałość dla adresata", "10": "Język materiału i ostrzeżenia",
    "11": "Źródło i założenia porównania", "12a": "Okres i źródło wyników historycznych",
    "12b": "Waluta i koszty wyniku historycznego", "13": "Ekspozycja wyników historycznych",
    "14": "Ostrzeżenie przy wynikach historycznych", "15": "Prognoza i ostrzeżenie",
    "16": "Zastrzeżenia podatkowe", "17": "Sugestia aprobaty przez organ", "18": "Bezpieczeństwo dzięki nadzorowi",
}
UNKNOWN, OBS, OK, NA = "brak danych", "obserwacja", "spełnione", "nie dotyczy"
HISTORY = r"wynik\w* historyczn\w*|historyczn\w* stop\w* zwrotu|wynik\w* z przeszłości"
FORECAST = r"prognoz\w*|przewidywan\w* (?:zysk|wynik)\w*"
TAX = r"podatk\w*|podat(?:ek|ku)"


def excerpt(text, pattern):
    """Return a contiguous excerpt containing the match, with original casing."""
    match = re.search(pattern, text, re.I)
    if not match:
        return ""
    before = text.rfind("\n", max(0, match.start()-55), match.start())
    after = text.find("\n", match.end(), match.end()+90)
    return text[max(0, before+1, match.start()-55):after if after >= 0 else match.end()+90].strip()


def marketing(capture):
    text = capture.get("description") or ""
    full = capture.get("fullText") is True
    source = capture.get("url", "")
    rows = {}
    def add(key, state, evidence, mode="wspomagany", **extra):
        rows[key] = {"id": key, "label": LABELS[key], "state": state, "mode": mode,
                     "evidence": evidence, "url": source, **extra}

    def present(key, pattern, missing):
        quote = excerpt(text, pattern)
        add(key, OK if quote else OBS if full else UNKNOWN,
            quote or missing, "automatyczny" if quote or full else "ręczny")

    legal = capture.get("legalName")
    if legal:
        present("1", re.escape(legal), "W dostępnej treści nie znaleziono ustalonej nazwy prawnej.")
    else:
        add("1", UNKNOWN, "Potrzebna nazwa prawna zweryfikowana dla tego wydawcy.", "ręczny")
    present("2", r"\breklama\b|materiał (?:reklamowy|promocyjny)|komunikat marketingowy",
            "W dostępnym tekście brak jednoznacznej etykiety reklamy.")
    benefit = excerpt(text, r"prowizj\w* 0\s*%|bez prowizji|korzyś\w*|zysk\w*|bezpłatn\w*")
    add("3", OBS if benefit and full else UNKNOWN,
        " ".join(filter(None, [benefit, "Parę korzyść–ryzyko trzeba potwierdzić w tym samym materiale i dla tego samego produktu."])))

    for key, missing in {
        "4": "Brak pełnego rozkładu rozmiarów widocznych znaków w obszarze reklamy.",
        "5": "Brak potwierdzonych kolorów tła, tekstu i stanu przesłonięcia.",
        "6": "Brak hierarchii elementu i potwierdzenia roli stopki lub przypisu.",
        "7": "Brak dwóch stanów elementu przed interakcją i po niej.",
        "8": "Brak porównywalnych pomiarów na telefonie, tablecie i komputerze.",
    }.items():
        add(key, UNKNOWN, missing, "ręczny")

    # The optional ad-region measurements must refer to a single verified warning
    # and complete, visible, non-navigation text within the same creative.
    region = capture.get("adRegion") or {}
    if region.get("complete") and region.get("warningPx"):
        counts = Counter()
        for node in region.get("nodes", []):
            if node.get("visible") is True and not node.get("navigation"):
                counts[node["px"]] += len("".join(node["text"].split()))
        sizes = [px for px, count in counts.items() if count and count == max(counts.values())]
        if len(sizes) == 1:
            warning = region["warningPx"]
            add("4", OBS if warning < sizes[0] else OK, f"Ostrzeżenie {warning} px. Dominanta ważona liczbą widocznych znaków {sizes[0]} px.", "automatyczny")
    if region.get("warningRole") in {"footnote", "footer", "body"}:
        role = region["warningRole"]
        add("6", OK if role == "body" else OBS, "Rola elementu w przechwyconym DOM: " + role)
    if isinstance(region.get("before"), bool) and region.get("after") is True:
        add("7", OK if region["before"] else OBS, "Ostrzeżenie widoczne przed interakcją: " +
            ("tak" if region["before"] else "nie") + ". Po interakcji: tak.", "automatyczny")

    audience = capture.get("audience") or "nieustalony"
    add("9", UNKNOWN, f"Adresat materiału: {audience}. Brak potwierdzonego ostrzeżenia o reklamowanym produkcie.", "ręczny")
    langs = capture.get("verifiedLanguages", {})
    if langs.get("offer") and langs.get("warning"):
        add("10", OK if langs["offer"] == langs["warning"] else OBS,
            f"Język oferty: {langs['offer']}. Ostrzeżenie: {langs['warning']}.", "automatyczny")
    else:
        add("10", UNKNOWN, "Brak rozpoznania języka dla obu jednoznacznie wydzielonych fragmentów.", "ręczny")

    def contextual(key, context, required, why, manual=False):
        found = excerpt(text, context)
        if not found:
            add(key, NA if full else UNKNOWN, "Brak tego kontekstu " +
                ("w pełnym tekście." if full else "w dostępnym fragmencie."), "automatyczny" if full else "ręczny")
            return
        features = [name for name, pattern in required if re.search(pattern, text, re.I)]
        absent = [name for name, pattern in required if not re.search(pattern, text, re.I)]
        evidence = "„" + found + "”. " + why
        if features:
            evidence += " Znaleziono: " + ", ".join(features) + "."
        if absent:
            evidence += " Brak potwierdzenia: " + ", ".join(absent) + "."
        state = OBS if manual or absent and full else UNKNOWN if absent else OK
        add(key, state, evidence)

    contextual("11", r"w porównaniu|względem konkurencji|tańsz\w* niż", [("źródło", r"źródł\w*"), ("założenia", r"założ\w*")],
               "Sprawdź porównywalność usług.", True)
    contextual("12a", HISTORY, [("5 lat", r"pięciu lat|5 lat"), ("okresy roczne", r"12.miesięcz|pełn\w* (?:lata|rok)"),
               ("okres referencyjny", r"\b20\d{2}\s*[–—-]\s*20\d{2}\b"), ("źródło", r"źródł\w*")],
               "Ustal datę rozpoczęcia prezentacji i wyjątki.", True)
    if re.search(HISTORY, text, re.I) and re.search(r"USD|EUR|GBP|brutto", text, re.I):
        needed = []
        if re.search(r"USD|EUR|GBP", text, re.I):
            needed.append(("wpływ kursów walut", r"(?:zmian\w* kurs\w*|kurs\w* walut).{0,45}(?:wpływ\w*|zwiększ\w*|obniż\w*)"))
        if re.search("brutto", text, re.I):
            needed.append(("wpływ kosztów", r"(?:opłat\w*|prowizj\w*).{0,45}(?:obniż\w*|zmniejsz\w*|pomniejsz\w*)"))
        contextual("12b", HISTORY, needed, "Zidentyfikuj walutę klienta i sposób obliczenia wyniku.")
    else:
        add("12b", NA if full else UNKNOWN, "Brak potwierdzenia prezentacji historii w walucie obcej lub brutto.")
    contextual("13", HISTORY, [], "Dominację wizualną wyników ustala analityk na zrzucie.", True)
    contextual("14", HISTORY, [("ostrzeżenie o przyszłych wynikach", r"nie (?:gwarantuj\w*|stanowi\w* gwarancji).{0,45}przyszł\w*")],
               "Sprawdź sąsiedztwo z prezentacją wyników.")
    contextual("15", FORECAST, [("zastrzeżenie dla prognozy", r"prognoz\w*.{0,40}nie (?:stanowi\w*|gwarantuj\w*)")],
               "Sprawdź założenia prognozy.")
    contextual("16", TAX, [("sytuacja odbiorcy", r"indywidualn\w* sytuac\w*"), ("możliwa zmiana", r"(?:może|mogą) (?:ulec |się )?zmian\w*")],
               "Sprawdź obie części zastrzeżenia.")
    for key, pattern in [
        ("17", r"(?:KNF|komisja nadzoru finansowego) (?:poleca|zatwierdz\w*|rekomenduje|aprobuje)"),
        ("18", r"(?:KNF|nadzór) gwarantuje|bezpiecz\w*.{0,32}(?:dzięki|bo|ponieważ).{0,25}(?:KNF|nadzor\w*)"),
    ]:
        quote = excerpt(text, pattern)
        add(key, OBS if quote else OK if full else UNKNOWN, quote or "Brak jednoznacznej formuły w analizowanym zakresie.",
            "automatyczny" if quote or full else "ręczny")
    if capture.get("m2Views"):
        show_checks(capture, add)
    return list(rows.values())
