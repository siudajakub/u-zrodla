"""Build InvestWatch.pdf with Python 3 and the system Cairo and FreeFont.

Edit the slide functions below, then run: python3 presentation/prepare.py
Numbers come from the files named in each slide footer; screenshots from tests/ui/screens/2026-11-21-r3/.
"""
from argparse import ArgumentParser
from ctypes import CDLL, c_char_p as S, c_double as D, c_int as I, c_void_p as P
from pathlib import Path
from textwrap import wrap

HERE = Path(__file__).resolve().parent
parser = ArgumentParser(description=__doc__)
parser.add_argument("--repo-root", type=Path, default=HERE.parent, help="Checkout ze zrzutami pulpitu.")
parser.add_argument("--out", type=Path, default=HERE / "InvestWatch.pdf")
args = parser.parse_args()
ROOT = args.repo_root.resolve()
SHOTS = ROOT / "tests/ui/screens/2026-11-21-r3"
W, H = 960, 540
INK, DEEP, PAPER = "#102a37", "#103c43", "#f7f4ea"
GREEN, TEAL, GREY, LINE, RED = "#afdec3", "#216966", "#425862", "#b3c0b5", "#a33b2b"
cairo = CDLL("libcairo.so.2")


def bind(name, result, *types):
    func = getattr(cairo, name)
    func.restype, func.argtypes = result, types
    return func


surface = bind("cairo_pdf_surface_create", P, S, D, D)(str(args.out).encode(), W, H)
ctx = bind("cairo_create", P, P)(surface)
set_rgb = bind("cairo_set_source_rgb", None, P, D, D, D)
set_font = bind("cairo_select_font_face", None, P, S, I, I)
size_font = bind("cairo_set_font_size", None, P, D)
move = bind("cairo_move_to", None, P, D, D)
to = bind("cairo_line_to", None, P, D, D)
stroke = bind("cairo_stroke", None, P)
width = bind("cairo_set_line_width", None, P, D)
rect = bind("cairo_rectangle", None, P, D, D, D, D)
fill = bind("cairo_fill", None, P)
clip = bind("cairo_clip", None, P)
text = bind("cairo_show_text", None, P, S)
go = bind("cairo_show_page", None, P)
load_png = bind("cairo_image_surface_create_from_png", P, S)
image_width = bind("cairo_image_surface_get_width", I, P)
surface_status = bind("cairo_surface_status", I, P)
destroy_surface = bind("cairo_surface_destroy", None, P)
save = bind("cairo_save", None, P)
restore = bind("cairo_restore", None, P)
translate = bind("cairo_translate", None, P, D, D)
scale = bind("cairo_scale", None, P, D, D)
source_surface = bind("cairo_set_source_surface", None, P, P, D, D)
paint = bind("cairo_paint", None, P)


def color(code):
    set_rgb(ctx, *(int(code[i:i+2], 16)/255 for i in (1, 3, 5)))


def box(x, y, w, h, shade):
    color(shade)
    rect(ctx, x, y, w, h)
    fill(ctx)


def rule(x, y, x2, y2, shade=LINE, thick=1):
    color(shade)
    width(ctx, thick)
    move(ctx, x, y)
    to(ctx, x2, y2)
    stroke(ctx)


def put(x, y, message, size=20, shade=INK, face="FreeSans", bold=False):
    color(shade)
    set_font(ctx, face.encode(), 0, int(bold))
    size_font(ctx, size)
    move(ctx, x, y)
    text(ctx, message.encode())


def para(x, y, message, chars, size=17, shade=INK, gap=None, bold=False):
    lines = wrap(message, width=chars)
    for index, line in enumerate(lines):
        put(x, y + index * (gap or size * 1.32), line, size, shade, bold=bold)
    return y + len(lines) * (gap or size * 1.32)


def shot(name, x, y, w, h, sx=0, sy=0, sw=None):
    """Draw the region (sx, sy, sw wide) of a screenshot scaled into the box x, y, w, h."""
    path = SHOTS / name
    picture = load_png(str(path).encode())
    try:
        if surface_status(picture):
            raise SystemExit(f"Nie można wczytać zrzutu {path}.")
        ratio = w / (sw or image_width(picture))
        box(x - 1, y - 1, w + 2, h + 2, LINE)
        save(ctx)
        rect(ctx, x, y, w, h)
        clip(ctx)
        translate(ctx, x - sx * ratio, y - sy * ratio)
        scale(ctx, ratio, ratio)
        source_surface(ctx, picture, 0, 0)
        paint(ctx)
        restore(ctx)
    finally:
        destroy_surface(picture)


def foil(heading, source, dark=False):
    box(0, 0, W, H, DEEP if dark else PAPER)
    put(50, 44, heading, 15, GREEN if dark else TEAL, bold=True)
    put(737, 44, "HackNation  /  UKNF", 15, GREEN if dark else TEAL)
    rule(50, 62, 910, 62, "#54847d" if dark else LINE)
    put(50, 518, source, 11, "#c6ded1" if dark else GREY)


def problem():
    foil("InvestWatch", "Źródło: docs/zrodla-uknf/BRIEF.md §2 oraz TEMAT-1..3", True)
    put(50, 140, "Promocja inwestycji przeniosła się", 44, PAPER, face="FreeSerif")
    put(50, 190, "do twórców i na telefony", 44, PAPER, face="FreeSerif")
    for y, tag, question, note in [
        (270, "M1", "Kto reklamuje firmę inwestycyjną i czy to oznacza?", "Finfluencerzy, także firmy transgraniczne"),
        (350, "M2", "Czy przy obietnicy zysku widać ryzyko tego produktu?", "Strona własna firmy, ekran komputera i telefonu"),
        (430, "M3", "Kto oferuje doradztwo i czy ma zezwolenie?", "Treść oferty, operator strony, wykaz KNF"),
    ]:
        put(52, y, tag, 26, GREEN, bold=True)
        put(130, y, question, 23, PAPER, bold=True)
        put(130, y + 28, note, 17, "#c6ded1")


def what_it_does():
    foil("InvestWatch  /  co robi system", "Liczby: /v1/overview bazy pokazu, replay z 21 XI 2026")
    put(50, 128, "Od odkrycia do decyzji analityka", 42, face="FreeSerif")
    steps = [("Odkryj", "Data API, Atom,", "odsyłacze, wyszukiwanie"),
             ("Odczytaj", "opis, mowa, kadry,", "zrzut strony 1440 i 390 px"),
             ("Zakwalifikuj", "rejestr, przegląd albo", "niepełne dane z powodem"),
             ("Zdecyduj", "analityk, z rewizją", "i eksportem raportu")]
    for i, (title, a, b) in enumerate(steps):
        x = 52 + i * 218
        box(x, 168, 200, 106, "#e6ecdf")
        put(x + 14, 202, title, 22, TEAL, bold=True)
        put(x + 14, 232, a, 15)
        put(x + 14, 253, b, 15)
    for x, count, a, b in [(52, "381", "kanałów YouTube", "w bazie"), (272, "1345", "materiałów YouTube", "w replayu"),
                           (490, "269", "pozycji w rejestrze", "reklam M1"), (708, "4", "filmy do", "sprawdzenia")]:
        put(x, 356, count, 54, TEAL, face="FreeSerif")
        put(x, 386, a, 16, bold=True)
        put(x, 406, b, 16, bold=True)
    para(52, 452, "Jawna współpraca trafia do rejestru. Do przeglądu trafia tylko film z dowodem relacji handlowej, "
         "w którym nie znaleziono oznaczenia w opisie, mowie ani kadrach.", 98, 17, GREY)


def first_slice():
    foil("InvestWatch  /  pierwszy pion M1", "Sprawa youtube:AqXHkxDzSDI  /  zrzut tests/ui/screens/2026-11-21-r3/1440-2-karta-flagi-momenty.png")
    put(50, 112, "Film znaleziony bez seedów", 36, face="FreeSerif")
    put(52, 148, "ForexMind · „Freedom24 Alternatywy” · XTB", 16, GREY, bold=True)
    y = para(52, 186, "W opisie: skrócony link przy XTB i kod twórcy „TRADEXTB”.", 40, 16)
    y = para(52, y + 8, "Oznaczenia brak w opisie, w całej mowie (0:00–3:24) i w 2 kadrach. "
             "YouTube nie oznacza płatnej promocji.", 40, 16)
    put(52, y + 22, "MOWA, 0:15", 13, TEAL, bold=True)
    y = para(52, y + 46, "„znajdziesz linki do specjalnych ofert w opisie poniżej. Zaczynajmy. XTB jest”", 34, 19, bold=True)
    para(52, y + 12, "Karta podaje też niewinne wyjaśnienie i zakres tego, czego nie zbadano. Decyzję podejmuje analityk.", 44, 14, GREY)
    shot("1440-2-karta-flagi-momenty.png", 470, 86, 440, 418, sx=580, sy=225, sw=860)


def modules():
    foil("InvestWatch  /  trzy moduły", "docs/lanes/2026-11-21-fable-c-media.md, -e-m2.md, -f-m3.md; M3-WERYFIKACJA-2026-11-21.md")
    put(50, 120, "Przesłanka i kontrprzykład na tym samym materiale", 33, face="FreeSerif")
    rows = [
        ("M1", "Konopskyy: „[reklama] Zarejestruj się w XTB z kodem KONOP” → rejestr, nie alarm.",
         "Comparic: link i kod bez słowa „reklama”, ale w 614 s „znajdziecie u partnera tego odcinka XTB” → podejrzenie obalone."),
        ("M2", "ETF XTB: obietnica dywidend, ostrzeżenie dla ETF poza kadrem telefonu → przegląd.",
         "Noble IKE: „Zyskaj więcej… bez podatku od zysków kapitałowych” bez ryzyka produktu. 19 kryteriów, 25 stron, 11 firm."),
        ("M3", "rdmwm.pl: „Na podstawie tych danych dobieramy proporcje między akcjami, obligacjami…” → ustalić operatora.",
         "DM BOŚ: cechy doradztwa, ale wykaz KNF podaje zezwolenie z pozycją 5 → kontrola przed fałszywym alarmem."),
    ]
    y = 168
    for tag, first, second in rows:
        put(52, y + 20, tag, 26, TEAL, bold=True)
        end = para(130, y, first, 88, 16, bold=True)
        end = para(130, end + 4, second, 92, 15, GREY)
        rule(52, end + 6, 908, end + 6)
        y = end + 26


def sources():
    foil("InvestWatch  /  źródła", "/v1/overview (sourceHealth); docs/lanes/2026-11-21-fable-k-social.md; zrzut 1440-6-zrodla.png")
    put(50, 112, "Co czytamy i gdzie jest granica", 36, face="FreeSerif")
    rows = [("YouTube", "działa", "Data API v3 z księgą kwoty, Atom, napisy i kadry"),
            ("TikTok", "działa", "64 posty z 6 profili z odsyłaczy YouTube, sam podpis"),
            ("Facebook / IG", "próbka", "22 reklamy z Biblioteki Reklam, 6 postów IG, import zapisanej strony"),
            ("Meta automat.", "zablokowany", "bez tokenu: wyzwanie 403 lub logowanie; nie obchodzimy"),
            ("WWW firm i ofert", "replay", "Chromium 1440/390 px (M2), uprzejmy crawler (M3)")]
    y = 156
    for name, state, note in rows:
        put(52, y, name, 16, bold=True)
        put(190, y, state, 15, RED if state == "zablokowany" else TEAL, bold=True)
        para(300, y, note, 34, 13, GREY, gap=16)
        rule(52, y + 42, 520, y + 42)
        y += 62
    put(52, 482, "Następny krok Meta: Ad Library API po tokenie albo Meta Content Library.", 14, GREY)
    shot("1440-6-zrodla.png", 545, 112, 365, 386, sx=960, sy=500, sw=470)


def architecture():
    foil("InvestWatch  /  architektura", "Szczegóły: docs/ARCHITEKTURA.md; kontrakt v2: docs/lanes/2026-11-21-fable-h-kontrakt.md", True)
    put(50, 128, "Adaptery, analiza, sprawa z wersjami", 40, PAPER, face="FreeSerif")
    for x, title, a, b in [(55, "Adaptery", "YouTube, TikTok, Meta,", "WWW M2/M3, replay"),
                           (275, "Kolejka", "Huey na SQLite,", "dzierżawa, wznowienie"),
                           (495, "Analiza", "reguły M1–M3,", "E5 lokalnie (opisowo)"),
                           (715, "Sprawa", "wersje, dowód,", "decyzja, WebSocket")]:
        box(x, 180, 185, 100, "#28565a")
        put(x + 15, 214, title, 22, PAPER, bold=True)
        put(x + 15, 244, a, 15, "#c6ded1")
        put(x + 15, 264, b, 15, "#c6ded1")
    for text_line, y in [("Kontrakt przed kodem: zmiana źródła nie zmienia API ani pulpitu.", 330),
                         ("Statystyka zasięgu nie tworzy nowej wersji; zmiana treści lub dowodu tworzy.", 362),
                         ("Compose: API i worker, kod tylko do odczytu, jeden katalog zapisu.", 394)]:
        put(52, y, text_line, 19, PAPER)
    put(52, 446, "Jedno stanowisko. Skalowanie: Postgres i osobne workery bez zmiany kontraktu.", 16, GREEN)


def accuracy():
    foil("InvestWatch  /  trafność", "q-v2/WYNIK-M1-2026-11-21.md; fixtures/labeled/m2-agent-eval.json, m3-agent-eval-v1/v2.json; zrzut 1440-7-kalibracja.png")
    put(50, 112, "Liczby z mianownikami", 36, face="FreeSerif")
    box(52, 128, 470, 30, "#f3e2a8")
    put(62, 149, "Oceny agentów, nie walidacja ekspercka", 15, INK, bold=True)
    rows = [("M1 · 26 materiałów, 20 kampanii", "kwalifikacja D, próg 60: FP 0, FN 0", "poprzednie reguły: FP 7, FN 4; zbiór strojenia"),
            ("M2 · 25 stron, 11 firm", "próg 30: TP 9, FP 1, TN 12, FN 3", "etykiety zapisane przed 1. uruchomieniem"),
            ("M3 · 31 materiałów", "v1 na ślepo: TP 0, FP 3, FN 1", "v2 poprawione na tym samym zbiorze")]
    y = 192
    for head, main, note in rows:
        put(52, y, head, 15, TEAL, bold=True)
        put(52, y + 24, main, 18, bold=True)
        put(52, y + 46, note, 14, GREY)
        y += 84
    put(52, 462, "Próg 95 w M1: 2 trafienia przechodzą w przeoczenia, koszt 2×FN+FP 0 → 4.", 14, GREY)
    shot("1440-7-kalibracja.png", 545, 112, 365, 386, sx=0, sy=210, sw=730)


def process():
    foil("InvestWatch  /  proces z AI", "docs/PROCES-AI.md; trailery Lane/Gate w git log")
    put(50, 112, "Agenci pilnują agentów", 36, face="FreeSerif")
    y = para(52, 150, "J decyduje o produkcie. Orkiestrator nie pisze kodu. Każda linia ma jednego wykonawcę i wyłączny zakres "
             "plików. Sędziowie i oceniający nie widzą wyników ani ocen innych.", 100, 16)
    put(52, y + 16, "STANDARDY", 13, TEAL, bold=True)
    y = para(52, y + 38, "kontrakt i testy expectedFailure przed kodem · zamrożony protokół etykiet · ślepe etykiety przed regułami · "
             "lista referencyjna ukryta przed wyszukującym · rejestr kosztów · sekrety poza repo · commit z Lane i Gate", 104, 15, GREY)
    put(52, y + 18, "PRZYKŁADY BŁĘDÓW ZŁAPANYCH PRZEZ DRUGIEGO AGENTA", 13, TEAL, bold=True)
    for i, line in enumerate([
        "Jawna deklaracja dostawała 94 pkt i alarm; po zmianie reguł FP 7 → 0 na q-v2.",
        "„Blokada hosta 429” okazała się żądaniem tłumaczonych napisów jednego filmu.",
        "Testy zużyły ok. 2900 jednostek kwoty YouTube; teraz budżet domyślny 0 i blokada sieci.",
        "Próba pokrycia kanałów 3 z 5 zostaje niezaliczona; zmieniono strategię na monitoring bazy.",
    ]):
        put(66, y + 46 + i * 28, "• " + line, 16)


def next_steps():
    foil("InvestWatch  /  co dalej", "docs/hackathon/demo.md (trudne pytania); docs/ODBIOR-UKNF.md", True)
    put(50, 132, "Pilot w UKNF: pięć kroków", 42, PAPER, face="FreeSerif")
    for i, (head, note) in enumerate([
        ("Etykiety ekspertów", "na nowych kampaniach, przed strojeniem; dopiero to zamyka bramkę trafności"),
        ("Dostęp instytucjonalny Meta", "Ad Library API i Meta Content Library; adapter czeka na token"),
        ("Uprawnione transkrypcje", "zgoda platformy albo ASR z dozwolonego źródła zamiast publicznych napisów"),
        ("Rejestr KNF na żywo", "bieżący odczyt wykazów i KRS zamiast datowanych kopii"),
        ("Skalowanie", "Postgres, osobne workery i OCR kadrów; kontrakt i adaptery bez zmian"),
    ]):
        y = 200 + i * 60
        put(52, y, f"{i + 1}.", 24, GREEN, bold=True)
        put(90, y, head, 22, PAPER, bold=True)
        put(90, y + 25, note, 16, "#c6ded1")


for slide in [problem, what_it_does, first_slice, modules, sources, architecture, accuracy, process, next_steps]:
    slide()
    go(ctx)
bind("cairo_destroy", None, P)(ctx)
bind("cairo_surface_finish", None, P)(surface)
if surface_status(surface):
    raise SystemExit("Nie udało się zapisać PDF.")
destroy_surface(surface)
