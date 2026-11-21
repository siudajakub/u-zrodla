"""Build InvestWatch.pdf with Python 3, system Cairo/FreeFont and ffmpeg.

Edit the slide functions below, then run: python3 presentation/prepare.py
"""
from array import array
from ctypes import CDLL, c_char_p as S, c_double as D, c_int as I, c_void_p as P
import json
from pathlib import Path
from subprocess import check_output

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
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
    foil("InvestWatch  /  odsłuch dowodu", "Fikcyjna publikacja Studio Aurora  /  głos syntetyczny  /  rzeczywiste rozpoznanie Vosk PL", True)
    put(50, 139, "„Partnerem programu jest firma Aurora”", 42, PAPER, face="FreeSerif")
    put(52, 185, "Kliknięcie cytatu otwiera moment deklaracji. Opis zapowiada jedynie przewodnik.", 22, PAPER)
    sample = ROOT / "analysis/media/studio.mp4"
    report = json.loads((ROOT / "analysis/media/studio.asr.json").read_text())
    start, end = report["segments"][1]["start"], report["segments"][1]["end"]
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
    put(xat(start)-6, 219, "4,35 s", 20, GREEN, bold=True)
    put(xat(end)-8, 356, "7,26 s", 16, GREEN)
    put(53, 415, "12 pkt", 36, PAPER, bold=True)
    put(190, 416, "z samego opisu", 23, PAPER)
    put(499, 415, "94 pkt", 36, GREEN, bold=True)
    put(640, 416, "po dodaniu audio", 23, PAPER)
    put(53, 455, "Priorytet przeglądu według tych samych reguł. Wypłata wynagrodzenia wymaga potwierdzenia.", 17, "#c6ded1")


def decision():
    foil("InvestWatch  /  sprawa analityka", "Źródła przykładu  /  zachowane pomiary strony XTB, publiczna oferta i wykaz agentów KNF z 21 XI 2026")
    put(50, 136, "Co może sprawdzić analityk?", 49, face="FreeSerif")
    for y, label, desc, detail in [
        (204, "Promocja w mowie", "„Pobierz aplikację Aurora i otwórz rachunek”.", "Drugi syntetyczny klip. Jedna wzmianka, zachęta i brak oznaczenia w badanym opisie."),
        (312, "Reklama firmy", "Sprawdza ostrzeżenie w kontekście korzyści.", "Pomiary strony XTB pokazują położenie elementu na trzech ekranach."),
        (417, "Zakres usługi", "Ustala, kto faktycznie oferuje doradztwo.", "Dla marki FinanceWell wykaz KNF wskazuje dwa podmioty o podobnych nazwach."),
    ]:
        put(51, y, label, 22, TEAL, bold=True)
        put(286, y, desc, 24, bold=True)
        put(286, y+32, detail, 17, GREY)
        if y < 417:
            rule(51, y+60, 909, y+60)


def validation():
    foil("InvestWatch  /  próg przeglądu", "Etykiety robocze autora  /  próbka ilustracyjna  /  ocena zgodności z prawem pozostaje po stronie analityka")
    put(50, 133, "Które sprawy pominie wyższy próg?", 47, face="FreeSerif")
    put(51, 185, "Ta sama próbka obejmuje 4 publiczne przypadki i 9 kontroli syntetycznych.", 23)
    from sys import path
    path.insert(0, str(ROOT))
    from analysis.engine import calibration
    a, b = calibration(35), calibration(70)
    for x, label in [(55, "Próg"), (355, "Fałszywe alarmy"), (683, "Przeoczenia")]:
        put(x, 251, label, 20, GREY, bold=True)
    rule(52, 267, 908, 267)
    for y, record in [(331, a), (409, b)]:
        for x, key in [(55, "threshold"), (355, "fp"), (683, "fn")]:
            put(x, y, str(record[key]), 48, TEAL if key == "fn" else INK, face="FreeSerif")
        rule(52, y+18, 908, y+18)
    put(53, 473, "Przykład przeoczenia przy obu progach: autor opisuje przelew za każdy otwarty rachunek.", 20)


for slide in [discovery, audio_evidence, decision, validation]:
    slide()
    go(ctx)
bind("cairo_destroy", None, P)(ctx)
bind("cairo_surface_finish", None, P)(surface)
if bind("cairo_surface_status", I, P)(surface):
    raise SystemExit("Nie udało się zapisać PDF.")
bind("cairo_surface_destroy", None, P)(surface)
