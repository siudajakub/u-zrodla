"""Build InvestWatch.pdf with Python 3, system Cairo/FreeFont and ffmpeg.

Edit the slide functions below, then run: python3 presentation/prepare.py
"""
from argparse import ArgumentParser
from array import array
from ctypes import CDLL, c_char_p as S, c_double as D, c_int as I, c_void_p as P
from datetime import datetime
import json
from pathlib import Path
from subprocess import check_output
import sys
from textwrap import wrap

HERE = Path(__file__).resolve().parent
parser = ArgumentParser(description=__doc__)
parser.add_argument("--repo-root", type=Path, default=HERE.parent,
                    help="Checkout źródłowy z artefaktami M2 i analizą.")
ROOT = parser.parse_args().repo_root.resolve()
sys.path.insert(0, str(ROOT))
from analysis.engine import analyze, calibration
from collectors.m2_archive import REPLAY, read_bundle
W, H = 960, 540
INK, DEEP, PAPER = "#102a37", "#103c43", "#f7f4ea"
GREEN, TEAL, GREY, LINE = "#afdec3", "#216966", "#425862", "#b3c0b5"
cairo = CDLL("libcairo.so.2")


def bind(name, result, *args):
    func = getattr(cairo, name)
    func.restype, func.argtypes = result, args
    return func


surface = bind("cairo_pdf_surface_create", P, S, D, D)(str(HERE / "InvestWatch.pdf").encode(), W, H)
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
text = bind("cairo_show_text", None, P, S)
go = bind("cairo_show_page", None, P)
tag_begin = bind("cairo_tag_begin", None, P, S, S)
tag_end = bind("cairo_tag_end", None, P, S)
load_png = bind("cairo_image_surface_create_from_png", P, S)
image_width = bind("cairo_image_surface_get_width", I, P)
image_height = bind("cairo_image_surface_get_height", I, P)
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


def box(x, y, w, h, paint):
    color(paint)
    rect(ctx, x, y, w, h)
    fill(ctx)


def rule(x, y, x2, y2, paint=LINE, thick=1):
    color(paint)
    width(ctx, thick)
    move(ctx, x, y)
    to(ctx, x2, y2)
    stroke(ctx)


def put(x, y, message, size=20, paint=INK, face="FreeSans", bold=False):
    color(paint)
    set_font(ctx, face.encode(), 0, int(bold))
    size_font(ctx, size)
    move(ctx, x, y)
    text(ctx, message.encode())


def link(x, y, label, url, size=15):
    tag_begin(ctx, b"Link", f"uri='{url}'".encode())
    put(x, y, label, size, TEAL, bold=True)
    tag_end(ctx, b"Link")


def image(path, x, y, height):
    shot = load_png(str(path).encode())
    try:
        if surface_status(shot):
            raise ValueError(f"Nie można wczytać dowodu z {path}.")
        ratio = height / image_height(shot)
        w = image_width(shot) * ratio
        box(x - 1, y - 1, w + 2, height + 2, LINE)
        save(ctx)
        translate(ctx, x, y)
        scale(ctx, ratio, ratio)
        source_surface(ctx, shot, 0, 0)
        paint(ctx)
        restore(ctx)
    finally:
        destroy_surface(shot)


def number(value):
    return f"{value:g}".replace(".", ",")


def etf_data():
    capture, _ = read_bundle(REPLAY, "xtb-etf", "replay")
    finding = analyze(capture)
    check = next(item for item in finding["checks"] if item["id"] == "3")
    views = {(item["width"], item["state"]): item for item in check["measurements"]}
    return capture, views


def etf_proof(capture, views):
    phone = views[(390, "profit")]
    captured = datetime.fromisoformat(capture["observedAt"]).strftime("%d.%m.%Y, %H:%M UTC")
    foil("InvestWatch  /  M2", f"Odczyt Chromium  /  {captured}  /  sprawa {capture['id']} · kryterium 3")
    put(50, 128, "Czy przy dywidendach widać ryzyko?", 46, face="FreeSerif")
    put(52, 176, "TWIERDZENIE O POTENCJALNYM DOCHODZIE", 14, TEAL, bold=True)
    for index, line in enumerate(wrap(f"„{phone['profit']['text']}”", width=66)):
        put(52, 212 + index * 27, line, 25, bold=True)
    put(52, 277, "OSTRZEŻENIE DLA TEJ SAMEJ OFERTY ETF", 14, TEAL, bold=True)
    put(52, 312, f"„{phone['warning']['text']}”", 25, bold=True)
    rule(52, 333, 908, 333)
    for x, width_in_css, label in [(52, 1440, "Komputer"), (348, 768, "Tablet"), (644, 390, "Telefon")]:
        view = views[(width_in_css, "profit")]
        put(x, 386, number(view["profitDistancePx"]), 46, TEAL, face="FreeSerif")
        put(x, 416, f"{label}  ·  {width_in_css} px szerokości", 18)
    put(52, 450, "Odległość między ramkami tekstu w pikselach CSS. Reguła kieruje materiał do przeglądu.", 18, GREY)
    link(52, 480, "Oryginalna strona XTB ↗", capture["url"])
    put(260, 480, f"Odcisk wersji {capture['m2EvidenceRevision']}", 11, GREY)


def etf_mobile(views):
    profit = views[(390, "profit")]
    warning = views[(390, "warning")]
    origin = "http://127.0.0.1:8769"
    foil("InvestWatch  /  M2 · dowód", "Dwa zachowane widoki tej samej strony i wersji  /  ramki tekstu po przewinięciu")
    put(50, 111, "Co widać na telefonie?", 43, face="FreeSerif")
    for x, label, view in [(52, "Ujęcie wzmianki o dochodzie", profit), (278, "Ujęcie ostrzeżenia", warning)]:
        put(x, 145, label, 14, GREY, bold=True)
        image(REPLAY / "assets" / f"{view['screenshotHash']}.png", x, 157, 326)
    rule(484, 150, 484, 474)
    put(520, 173, f"{profit['width']} × {profit['height']} px", 25, bold=True)
    put(520, 221, "Widok wzmianki o dywidendach", 19, TEAL, bold=True)
    put(520, 248, "Widoczna cała wzmianka. Ostrzeżenie poza kadrem.", 16)
    put(520, 289, "Widok ostrzeżenia", 19, TEAL, bold=True)
    put(520, 316, "Widoczne całe ostrzeżenie. Wzmianka poza kadrem.", 16)
    put(520, 368, "Baner cookies widoczny w zapisie.", 16, GREY)
    link(520, 410, "PNG wzmianki ↗", origin + profit["url"])
    link(704, 410, "DOM wzmianki ↗", origin + profit["domUrl"])
    link(520, 439, "PNG ostrzeżenia ↗", origin + warning["url"])
    link(704, 439, "DOM ostrzeżenia ↗", origin + warning["domUrl"])
    put(520, 473, "Odnośniki otwierają dowód w lokalnym demie.", 14, GREY)


def foil(heading, subtitle, dark=False):
    box(0, 0, W, H, DEEP if dark else PAPER)
    put(50, 44, heading, 15, GREEN if dark else TEAL, bold=True)
    put(737, 44, "HackNation  /  UKNF", 15, GREEN if dark else TEAL)
    rule(50, 62, 910, 62, "#54847d" if dark else LINE)
    put(50, 511, subtitle, 13, "#c6ded1" if dark else GREY)


def discovery():
    foil("InvestWatch", "Zapis pierwszego monitoringu i osobny odczyt katalogów  /  21 XI 2026")
    put(50, 148, "Skąd przychodzą nowe materiały?", 49, face="FreeSerif")
    put(52, 203, "Monitor śledzi publikacje na kontach. Wyszukiwanie tematyczne", 25)
    put(52, 236, "dodaje do obserwacji kolejne audycje i kanały.", 25)
    for x, count, note, hint in [
        (52, "4/4", "monitorowane konta", "YouTube i TikTok"),
        (325, "50", "publikacji z tych kont", "pierwszy odczyt monitora"),
        (620, "+13", "audycji i kanałów", "spoza 8 źródeł startowych"),
    ]:
        put(x, 355, count, 86, TEAL, face="FreeSerif")
        put(x, 397, note, 23, bold=True)
        put(x, 428, hint, 19, GREY)
    rule(286, 275, 286, 447)
    rule(587, 275, 587, 447)


def audio_evidence():
    foil("InvestWatch  /  odsłuch dowodu", "Klip „Od czego zacząć?”  /  głos i marka fikcyjne  /  rzeczywiste rozpoznanie Vosk PL", True)
    put(50, 139, "„Pobierz aplikację Aurora i otwórz rachunek”", 40, PAPER, face="FreeSerif")
    put(52, 185, "W opisie jest ogólna wskazówka. Zachęta z nazwą marki pojawia się w mowie.", 22, PAPER)
    sample = ROOT / "analysis/media/wezwanie.mp4"
    report = json.loads((ROOT / "analysis/media/wezwanie.asr.json").read_text())
    start, end = report["segments"][0]["start"], report["segments"][0]["end"]
    data = array("h")
    data.frombytes(check_output(["ffmpeg", "-v", "error", "-i", str(sample), "-ac", "1", "-ar", "8000", "-f", "s16le", "-"]))
    length = len(data)/8000
    left, right = 52, 908
    xat = lambda t: left + (right-left)*t/length
    box(xat(start), 234, xat(end)-xat(start), 99, "#2c605d")
    n = 230
    for i in range(n):
        group = data[i*len(data)//n:(i+1)*len(data)//n]
        amp = max(1, max(abs(x) for x in group)/32768*42)
        x = xat((i+.5)*length/n)
        rule(x, 284-amp, x, 284+amp, GREEN if start <= (i+.5)*length/n <= end else "#8ca8a4", 2)
    rule(xat(start), 227, xat(start), 337, GREEN, 2)
    put(xat(start)-6, 219, f"{start:.2f}".replace(".", ",") + " s", 20, GREEN, bold=True)
    put(xat(end)-8, 356, f"{end:.2f}".replace(".", ",") + " s", 16, GREEN)
    put(53, 415, "12 pkt", 36, PAPER, bold=True)
    put(190, 416, "z samego opisu", 23, PAPER)
    put(499, 415, "74 pkt", 36, GREEN, bold=True)
    put(640, 416, "po dodaniu audio", 23, PAPER)
    put(53, 455, "Priorytet według tych samych reguł. Analityk ustala charakter relacji.", 17, "#c6ded1")


def validation():
    a, b = calibration(35), calibration(70)
    foil("InvestWatch  /  próg przeglądu", f"Historyczny zbiór {a['datasetId']}  /  etykiety robocze autora")
    put(50, 132, "Które sprawy pominie wyższy próg?", 45, face="FreeSerif")
    put(52, 183, f"Ta sama próbka: {a['publicExamples']} publiczne przypadki i {a['syntheticExamples']} kontroli syntetycznych.", 22)
    columns = [(55, "Próg", "threshold"), (224, "Fałszywe alarmy", "fp"),
               (464, "Przeoczenia", "fn"), (685, "Koszt 2 × FN + FP", "cost")]
    for x, label, _ in columns:
        put(x, 246, label, 19, GREY, bold=True)
    rule(52, 260, 908, 260)
    for y, record in [(315, a), (379, b)]:
        for x, _, key in columns:
            put(x, y, str(record[key]), 42, TEAL if key == "cost" else INK, face="FreeSerif")
        rule(52, y+15, 908, y+15)
    put(52, 431, "Etykiety wskazują materiały do sprawdzenia. BOŚ i ETF pochodzą ze starszych wycinków.", 17, GREY)
    put(52, 463, "Pomiar dotyczy reguł na tej próbce. Ocena nowych flag wymaga niezależnej walidacji.", 17, GREY)


def challenge():
    foil("InvestWatch  /  zakres wyzwania", "5 dokumentów UKNF  /  źródła w docs/zrodla-uknf")
    put(50, 134, "Trzy pytania analityka", 49, face="FreeSerif")
    for y, tag, first, second in [
        (205, "M2", "Czy przy twierdzeniu o zysku widać ryzyko?", "Materiał własny firmy, treść i widok odbiorcy."),
        (310, "M3", "Kto może świadczyć oferowane doradztwo?", "Treść oferty, tożsamość, rejestr i zakres uprawnień."),
        (415, "M1", "Kto reklamuje firmę lub jej usługi?", "Także polskojęzyczna promocja firm transgranicznych."),
    ]:
        put(51, y, tag, 28, TEAL, bold=True)
        put(146, y, first, 26, bold=True)
        put(146, y+32, second, 18, GREY)
        if y < 415:
            rule(51, y+60, 909, y+60)


def model_control():
    foil("InvestWatch  /  kontrola modelu", "Rzeczywista oferta i materiał edukacyjny BOŚ  /  próba lokalna 21 XI 2026")
    put(50, 132, "Model wskazuje fragment, człowiek sprawdza", 42, face="FreeSerif")
    put(52, 201, "Oferta · 5 956 znaków", 23, TEAL, bold=True)
    put(52, 238, "„My podpowiadamy co kupić i sprzedać, Ty decydujesz.”", 24)
    put(52, 268, "E5: sygnał do przeglądu. KRS i wpis KNF mają odrębne źródła.", 19, GREY)
    rule(52, 294, 908, 294)
    put(52, 337, "Kontrola · 1 481 znaków edukacji", 23, TEAL, bold=True)
    put(52, 373, "Lista instrumentów została błędnie wskazana jako doradztwo.", 23)
    put(52, 407, "Bez czynności i odbiorcy wynik pozostaje niejednoznaczny.", 20, GREY)
    put(52, 461, "Dwie kontrole faktów, bez oceny skuteczności modelu na całym rynku.", 18, GREY)


def architecture():
    foil("InvestWatch  /  architektura i awaria", "Kod: api/jobs.py, api/store.py  /  raport: tests/offline/proof-2026-11-21.json", True)
    put(50, 132, "Skan jest zadaniem, sprawa ma wersje", 44, PAPER, face="FreeSerif")
    for x, title, detail in [(55, "Źródła", "odczyt i pochodzenie"), (275, "Huey", "kolejka SQLite"),
                             (495, "Analiza", "reguły i lokalny E5"), (715, "Sprawa", "dowód i decyzja")]:
        box(x, 187, 185, 88, "#28565a")
        put(x+15, 222, title, 22, PAPER, bold=True)
        put(x+15, 253, detail, 16, "#c6ded1")
    put(52, 310, "Lokalny stos open source: FastAPI, SQLite, Huey, Chromium, Vosk, E5, React i Astryx.", 16, GREEN)
    put(52, 343, "Worker zapisuje dzierżawę. Po jej wygaśnięciu można odzyskać zadanie.", 22, PAPER)
    put(52, 380, "W próbie offline drugi worker ukończył skan po zatrzymaniu pierwszego.", 20, PAPER)
    put(52, 409, "Liczba wersji pozostała równa liczbie spraw.", 20, PAPER)
    put(52, 457, "Pojedyncze stanowisko demo. Kopia i odporność produkcyjna wymagają osobnej próby.", 17, "#c6ded1")


etf_capture, etf_views = etf_data()
for slide in [
    challenge,
    lambda: etf_proof(etf_capture, etf_views),
    lambda: etf_mobile(etf_views),
    model_control,
    discovery,
    audio_evidence,
    validation,
    architecture,
]:
    slide()
    go(ctx)
bind("cairo_destroy", None, P)(ctx)
bind("cairo_surface_finish", None, P)(surface)
if surface_status(surface):
    raise SystemExit("Nie udało się zapisać PDF.")
destroy_surface(surface)
