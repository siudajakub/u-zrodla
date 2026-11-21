#!/usr/bin/env python3
"""Zrzuty pulpitu 1440 i 390 px (jeden proces Chromium, kolejno) oraz kontrola konsoli i podstawowych stanów.

Użycie:  /home/codexdev/.venvs/playwright/bin/python tests/ui/capture-screens.py --base http://127.0.0.1:18790 [--out DIR]
Zapisuje zrzuty w tests/ui/screens/<data>/ i drukuje wynik sprawdzeń. Nie dotyka podglądu Compose.
"""
import argparse
import datetime
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument("--base", required=True)
parser.add_argument("--out", default=str(Path(__file__).parent / "screens" / "2026-11-21-r4"))
parser.add_argument("--only", default="")
parser.add_argument("--widths", default="1440,390")
parser.add_argument("--chromium", default="")
args = parser.parse_args()
out = Path(args.out)
out.mkdir(parents=True, exist_ok=True)
base = args.base.rstrip("/")
console = []
failed = []
failures = []


def check(name, ok, detail=""):
    print(("OK   " if ok else "FAIL ") + name + (f" · {detail}" if detail else ""))
    if not ok:
        failures.append(name)


SCREENS = [
    ("1-kolejka-trzech-modulow", "#review", "kolejka"),
    ("2-karta-m1", "#review?case=youtube%3AAqXHkxDzSDI", "momenty"),
    ("2b-karta-m2-kryteria", "#review?case=web%3Anoblesecurities.pl%2Fklient-indywidualny%2Frachunek-ike", "rozwin"),
    ("2c-karta-m3", "#review?case=web%3Ardmwm.pl%3Am3", "m3"),
    ("2d-karta-m3-uprawniony", "#m3?case=web%3Aerste.pl%3Am3", "m3"),
    ("3-karta-tiktok", "#register?case=tiktok%3A7707284619103718689", None),
    ("4-rejestr-reklam", "#register", None),
    ("5-rejestr-tiktok", "#register?source=tiktok", None),
    ("6-zrodla", "#sources", "wykresy"),
    ("7-kalibracja", "#calibration", "suwak"),
    ("8-niepelne", "#incomplete", None),
    ("9-oferty-m2", "#m2", None),
    ("9b-karta-reklamy-meta", "#m2?case=facebook%3Aad-1353099026431942", None),
    ("10-oferty-m3", "#m3", None),
    ("11-zamkniete", "#closed", None),
    ("12-demo", "#demo", None),
    ("14-rejestr-instagram", "#register?source=instagram", None),
    ("13-dodaj-dowod", "#evidence", None),
]
with sync_playwright() as p:
    binary = args.chromium or next(iter(sorted(Path.home().glob(".cache/ms-playwright/chromium-*/chrome-linux64/chrome"))), None)
    browser = p.chromium.launch(executable_path=str(binary) if binary else None, headless=True, args=["--no-sandbox"])
    for label, width, height in (("1440", 1440, 1000), ("390", 390, 844)):
        if label not in args.widths.split(","):
            continue
        context = browser.new_context(viewport={"width": width, "height": height}, locale="pl-PL", timezone_id="Europe/Warsaw",
                                      has_touch=width < 500, is_mobile=width < 500, device_scale_factor=1)
        page = context.new_page()
        page.on("console", lambda m, label=label: console.append((label, m.type, m.text)) if m.type in ("error", "warning") else None)
        page.on("response", lambda r: failed.append(r.url) if r.status >= 400 else None)
        page.on("pageerror", lambda e, label=label: console.append((label, "pageerror", str(e))))
        for name, hash_, extra in SCREENS:
            if args.only and args.only not in name:
                continue
            page.goto(f"{base}/{hash_}", wait_until="networkidle")
            page.wait_for_selector("h1, h2", timeout=90000)
            page.wait_for_timeout(2500)
            if extra == "suwak":
                page.wait_for_selector("canvas[data-chart=line]", timeout=30000)
                page.get_by_role("slider").focus()
                for _ in range(4):
                    page.keyboard.press("ArrowRight")
                page.wait_for_timeout(2500)
            if extra == "kolejka":
                page.wait_for_selector("text=Pokazano 15 z 15", timeout=30000)
                body = page.inner_text("body")
                check(f"{label} {name}: wiersze trzech modułów", all(m in body for m in ("Finfluencer", "Reklama firmy", "Doradztwo")))
            if extra == "rozwin":
                page.wait_for_selector("text=Wszystkie 19 kryteriów wg stanu", timeout=30000)
                page.get_by_text("Wszystkie 19 kryteriów wg stanu").click()
                page.wait_for_timeout(600)
                page.evaluate("document.getElementById('sekcja-momenty')?.scrollIntoView({block:'start'})")
            if extra == "m3":
                page.wait_for_selector("text=Cztery cechy rekomendacji", timeout=30000)
            if extra == "wykresy":
                page.wait_for_function("document.querySelectorAll('canvas[data-chart]').length >= 3", timeout=30000)
                page.wait_for_timeout(800)
            page.screenshot(path=str(out / f"{label}-{name}.png"), full_page=False)
            if label == "390" or name.startswith("7") or name.startswith("6"):
                # poziome przewijanie: strona nie może być szersza niż okno
                wide = page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
                check(f"{label} {name}: bez poziomego przewijania", not wide, str(page.evaluate("document.documentElement.scrollWidth")))
            if "karta" in name:
                # drugi zrzut: przewinięcie karty do momentów i kadrów
                page.evaluate("document.getElementById('sekcja-momenty')?.scrollIntoView({block:'start'})")
                page.wait_for_timeout(500)
                page.screenshot(path=str(out / f"{label}-{name}-momenty.png"), full_page=False)
        context.close()
    browser.close()

expected = ("favicon",)
noise = [c for c in console if "Failed to load resource" not in c[2] and "favicon" not in c[2]]
print(f"komunikaty konsoli (błędy i ostrzeżenia): {len(console)}")
unexpected = sorted({u for u in failed if not any(e in u for e in expected)})
check("odpowiedzi 4xx tylko z tras jeszcze nieistniejących", not unexpected, ", ".join(unexpected))
check("konsola bez błędów", not noise, json.dumps(noise, ensure_ascii=False)[:600])
print(datetime.datetime.now().isoformat(timespec="seconds"), "zrzuty:", out)
sys.exit(1 if failures else 0)
