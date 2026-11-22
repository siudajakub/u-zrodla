"""Build InvestWatch.pdf with Python 3 and the system Cairo and FreeFont.

Run: python3 presentation/prepare.py
Data and screenshots come from the accepted demo snapshot.
"""
from argparse import ArgumentParser
from ctypes import CDLL, c_char_p as S, c_double as D, c_int as I, c_void_p as P
from pathlib import Path
from textwrap import wrap

HERE = Path(__file__).resolve().parent
parser = ArgumentParser(description=__doc__)
parser.add_argument("--repo-root", type=Path, default=HERE.parent, help="Checkout ze zrzutami pulpitu.")
parser.add_argument("--screens", type=Path, help="Katalog zrzutów z zaakceptowanego stanowiska.")
parser.add_argument("--out", type=Path, default=HERE / "InvestWatch.pdf")
args = parser.parse_args()
ROOT = args.repo_root.resolve()
SHOTS = args.screens or ROOT / "tests/ui/screens/2026-11-22-final-workflow"
SUPPORT_SHOTS = args.screens or ROOT / "tests/ui/screens/2026-11-22-final"
SNAPSHOT = ("1 922", "274", "17")  # /v1/overview: materiały, rejestr reklam, do sprawdzenia
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


def shot(name, x, y, w, h, sx=0, sy=0, sw=None, directory=SHOTS):
    """Draw the region (sx, sy, sw wide) of a screenshot scaled into the box x, y, w, h."""
    path = directory / name
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
    foil("InvestWatch", "Datowany stan pokazu · docs/hackathon/demo.md · brief UKNF §2", True)
    put(50, 119, "Sprawy inwestycyjne", 39, PAPER, face="FreeSerif")
    put(50, 164, "z dowodem do sprawdzenia", 39, PAPER, face="FreeSerif")
    for x, count, label in zip((52, 204, 355), SNAPSHOT, ("materiałów", "w rejestrze", "do sprawdzenia")):
        put(x, 205, count, 29, GREEN, bold=True)
        put(x, 226, label, 14, PAPER)
    for y, tag, question, note in [
        (269, "M1", "Współpraca i reklama twórców", "Cytat, dokładny adres i sekunda filmu"),
        (346, "M2", "Ryzyko w reklamie firmy", "Ostrzeżenie dotyczące właściwego produktu"),
        (423, "M3", "Oferty doradcze", "Przesłanka, operator i datowany wykaz KNF"),
    ]:
        put(52, y, tag, 21, GREEN, bold=True)
        put(110, y, question, 20, PAPER, bold=True)
        put(110, y + 24, note, 15, "#c6ded1")
    shot("1440-kolejka.png", 505, 93, 405, 393, sy=40, sw=659)


def what_it_does():
    foil("InvestWatch  /  co robi system", "Liczby: /v1/overview bazy pokazu, replay z 21 XI 2026")
    put(50, 128, "Od odkrycia do decyzji analityka", 42, face="FreeSerif")
    steps = [("Odkryj", "kanały i publikacje,", "strony firm i ofert"),
             ("Odczytaj", "dostępny opis i mowę,", "zrzut strony 1440 i 390 px"),
             ("Zakwalifikuj", "rejestr, sprawdzenie", "lub braki w materiale"),
             ("Zdecyduj", "działanie i szkic,", "zatwierdzenie i historia")]
    for i, (title, a, b) in enumerate(steps):
        x = 52 + i * 218
        box(x, 168, 200, 106, "#e6ecdf")
        put(x + 14, 202, title, 22, TEAL, bold=True)
        put(x + 14, 232, a, 15)
        put(x + 14, 253, b, 15)
    rows = [(52, "7 · M1", "Materiały twórców", "z przesłanką do kontroli"),
            (345, "9 · M2", "Reklamy firm", "sprawdzone według 19 kryteriów"),
            (640, "1 · M3", "Oferta doradztwa", "z operatorem do ustalenia")]
    for x, tag, title, subtitle in rows:
        put(x, 350, tag, 38, TEAL, face="FreeSerif")
        put(x, 382, title, 17, bold=True)
        put(x, 404, subtitle, 16, GREY)
    para(52, 459, "Analityk otwiera cytat lub zrzut, sprawdza zakres odczytu i zapisuje decyzję. "
         "Raport CSV podaje źródło, uzasadnienie i sprawdzoną wersję.", 100, 17, GREY)


def first_slice():
    foil("InvestWatch  /  M1", "Sprawa youtube:AqXHkxDzSDI · datowany odczyt YouTube · docs/hackathon/demo.md")
    put(50, 112, "Sprawdź film od 0:15", 36, face="FreeSerif")
    put(52, 148, "ForexMind · „Freedom24 Alternatywy” · XTB", 16, GREY, bold=True)
    y = para(52, 186, "Opis zawiera skrócony link przy XTB i kod twórcy „TRADEXTB”.", 40, 16)
    y = para(52, y + 8, "W opisie i odczytanej mowie system nie znalazł oznaczenia współpracy.", 40, 16)
    put(52, y + 22, "MOWA, 0:15", 13, TEAL, bold=True)
    y = para(52, y + 46, "„znajdziesz linki do specjalnych ofert w opisie poniżej”", 34, 19, bold=True)
    para(52, y + 12, "Film trafia do sprawdzenia. Analityk może obejrzeć dostępne kadry i ocenić kontekst.", 44, 14, GREY)
    shot("1440-forexmind.png", 470, 86, 440, 418, sx=660, sy=150, sw=780)


def workflow():
    foil("InvestWatch  /  decyzja urzędnika", "Datowany pokaz · docs/hackathon/demo.md · stan sprawy i historia decyzji")
    put(50, 112, "Od dowodu do dalszego działania", 36, face="FreeSerif")
    y = para(52, 152, "Urzędnik wybiera działanie. System wstawia szkic z danych sprawy. Urzędnik sprawdza tekst, edytuje go i zatwierdza decyzję.", 47, 16)
    for label, detail in [
        ("Kontrola", "W wewnętrznej kolejce zespół zapisuje wynik lub wraca do sprawdzenia."),
        ("Do uzupełnienia", "Urzędnik opisuje nowe dane i źródło. Sprawa wraca do sprawdzenia."),
        ("Zakończone", "Historia zachowuje powód. Urzędnik może ponownie otworzyć sprawę."),
    ]:
        y += 20
        put(52, y, label, 18, TEAL, bold=True)
        y = para(52, y + 21, detail, 43, 15, GREY)
    put(468, 142, "SZKIC PRZED ZATWIERDZENIEM", 13, TEAL, bold=True)
    shot("1440-decyzja.png", 468, 154, 442, 229, sx=663, sy=518, sw=777)
    put(468, 398, "ZAPISANA SPRAWA W KOLEJCE KONTROLA", 13, TEAL, bold=True)
    shot("1440-kontrola.png", 468, 407, 442, 96, sx=663, sy=735, sw=777)


def modules():
    foil("InvestWatch  /  trzy moduły", "docs/lanes/2026-11-21-fable-c-media.md, -e-m2.md, -f-m3.md; M3-WERYFIKACJA-2026-11-21.md")
    put(50, 120, "Przesłanki i kontrole z trzech modułów", 36, face="FreeSerif")
    rows = [
        ("M1", "ForexMind trafia do sprawdzenia. Podaje link i kod XTB, a w 0:15 odsyła do ofert.",
         "Comparic też podaje link i kod. W 10:14 nazywa XTB partnerem odcinka i trafia do rejestru reklam."),
        ("M2", "ETF XTB trafia do sprawdzenia. Właściwe ostrzeżenie jest poza pierwszym ekranem telefonu.",
         "Ostrzeżenie o CFD dotyczy innego produktu. Próba 19 kryteriów objęła 25 stron z 11 firm."),
        ("M3", "rdmwm.pl opisuje dobór portfela na podstawie danych klienta. Trzeba ustalić operatora.",
         "DM BOŚ ma cechy oferty doradczej. Datowany wykaz KNF potwierdza zakres uprawnienia."),
    ]
    y = 168
    for tag, first, second in rows:
        put(52, y + 20, tag, 26, TEAL, bold=True)
        end = para(130, y, first, 88, 16, bold=True)
        end = para(130, end + 4, second, 92, 15, GREY)
        rule(52, end + 6, 908, end + 6)
        y = end + 26


def sources():
    foil("InvestWatch  /  źródła", "Źródła: /v1/overview, docs/MONITORING.md i docs/lanes/2026-11-21-fable-k-social.md")
    put(50, 112, "Co czytamy i gdzie jest granica", 36, face="FreeSerif")
    rows = [("YouTube", "oficjalne API", "1 307 filmów, pełna transkrypcja 23"),
            ("TikTok", "osadzenia", "64 podpisy postów z wybranych profili"),
            ("Facebook / IG", "próbka", "494 materiały, próbka zewnętrzna i import"),
            ("Meta Ad Library", "wymaga tokenu", "oficjalny adapter czeka na konfigurację"),
            ("WWW", "zapis odczytu", "zrzuty stron firm i treść ofert doradczych")]
    y = 156
    for name, state, note in rows:
        put(52, y, name, 16, bold=True)
        put(190, y, state, 15, RED if state == "wymaga tokenu" else TEAL, bold=True)
        para(316, y, note, 30, 13, GREY, gap=16)
        rule(52, y + 42, 520, y + 42)
        y += 62
    put(52, 482, "Tryb pokazu korzysta z datowanego zapisu.", 14, GREY)
    shot("1440-zrodla.png", 545, 154, 365, 240, sy=86, sw=1280, directory=SUPPORT_SHOTS)


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
    for text_line, y in [("Kontrakt adaptera stabilizuje API i pulpit przy zmianie źródła.", 330),
                         ("Zmiana treści lub dowodu tworzy wersję. Aktualizacja zasięgu zmienia metrykę.", 362),
                         ("Compose uruchamia web, API i worker. Scheduler i Ollama mają osobne profile.", 394)]:
        put(52, y, text_line, 19, PAPER)
    put(52, 446, "Prototyp obsługuje jedno stanowisko. Ścieżka wzrostu obejmuje Postgres i osobne workery.", 16, GREEN)


def accuracy():
    foil("InvestWatch  /  trafność", "M1: fixtures/validation/q-v2 · M2 i M3: /v1/calibration oraz fixtures/labeled")
    put(50, 112, "Liczby z mianownikami", 36, face="FreeSerif")
    box(52, 128, 470, 30, "#f3e2a8")
    put(62, 149, "Etykiety agentów i ograniczone próby", 15, INK, bold=True)
    rows = [("M1 · 26 materiałów, 20 kampanii", "Próg 60: 4 trafienia, 0 FP, 0 FN", "Zbiór strojenia, trzy kampanie dodatnie XTB"),
             ("M2 · 25 stron, 11 firm", "20 → 30 → 50: FP 1 → 0 → 0", "Przeoczenia: 3 → 3 → 5"),
            ("M3 · 31 materiałów, jeden pozytyw", "Reguły v1: 3 FP i 1 FN", "Wersję v2 poprawiono na tej samej próbie")]
    y = 192
    for head, main, note in rows:
        put(52, y, head, 15, TEAL, bold=True)
        put(52, y + 24, main, 18, bold=True)
        put(52, y + 46, note, 14, GREY)
        y += 84
    put(52, 452, "Próba diagnostyczna M1: 8 kontroli ujemnych, 0 skierowań.", 14, GREY)
    put(52, 476, "FP = fałszywy alarm. FN = przeoczenie.", 14, GREY)
    shot("390-kalibracja-m2.png", 622, 112, 288, 386, sy=140, directory=SUPPORT_SHOTS)


def process():
    foil("InvestWatch  /  proces z AI", "docs/PROCES-AI.md; trailery Lane/Gate w git log")
    put(50, 112, "Jak agenci sprawdzali swoją pracę", 36, face="FreeSerif")
    y = para(52, 150, "J decyduje o produkcie. Orkiestrator ustala kontrakty i odbiera pracę. Wykonawcy mają przypisane zakresy. "
             "Świeży sędzia sprawdza dowód i szuka przypadku, który podważa wniosek.", 100, 16)
    put(52, y + 16, "STANDARDY", 13, TEAL, bold=True)
    y = para(52, y + 38, "Kontrakty i testy, zamrożony protokół etykiet, lista referencyjna ukryta przed zespołem odkrywania, "
             "rejestr kosztów i trailery Lane oraz Gate wskazujące zakres i próbę.", 104, 15, GREY)
    put(52, y + 18, "PRZYKŁADY BŁĘDÓW ZŁAPANYCH PRZEZ DRUGIEGO AGENTA", 13, TEAL, bold=True)
    for i, line in enumerate([
        "Po poprawce kwalifikacji liczba fałszywych alarmów spadła na q-v2 z 7 do 0.",
        "„Blokada hosta 429” okazała się żądaniem tłumaczonych napisów jednego filmu.",
        "Po próbie z kwotą YouTube ustawiono budżet testowy na zero i odcięto sieć w testach.",
        "Wynik odkrywania 3 z 5 kanałów uzasadnił priorytet monitoringu znanej bazy.",
    ]):
        put(66, y + 46 + i * 28, "• " + line, 16)


def next_steps():
    foil("InvestWatch  /  co dalej", "docs/hackathon/demo.md (trudne pytania); docs/ODBIOR-UKNF.md", True)
    put(50, 132, "Pięć kroków do pilotażu w UKNF", 42, PAPER, face="FreeSerif")
    for i, (head, note) in enumerate([
        ("Etykiety ekspertów", "na nowych kampaniach przed strojeniem"),
        ("Dostęp instytucjonalny Meta", "uruchomienie Ad Library API za pomocą tokenu"),
        ("Źródło transkrypcji", "uzgodnienie zgody platformy lub ASR z udostępnionych mediów"),
        ("Rejestr KNF na żywo", "bieżący odczyt wykazów i potwierdzanie operatora"),
        ("Skalowanie", "pomiar większej kolejki i kilku stanowisk analityków"),
    ]):
        y = 200 + i * 60
        put(52, y, f"{i + 1}.", 24, GREEN, bold=True)
        put(90, y, head, 22, PAPER, bold=True)
        put(90, y + 25, note, 16, "#c6ded1")


for slide in [problem, what_it_does, first_slice, workflow, modules, sources, architecture, accuracy, process, next_steps]:
    slide()
    go(ctx)
bind("cairo_destroy", None, P)(ctx)
bind("cairo_surface_finish", None, P)(surface)
if surface_status(surface):
    raise SystemExit("Nie udało się zapisać PDF.")
destroy_surface(surface)
