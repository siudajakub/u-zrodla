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
parser.add_argument("--out", default=str(Path(__file__).parent / "screens" / "2026-11-21-r2"))
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
    ("1-kolejka", "#review", None),
    ("2-karta-7M0rC6-Rueo", "#review?case=youtube%3A7M0rC6-Rueo", None),
    ("3-karta-AqXHkxDzSDI", "#review?case=youtube%3AAqXHkxDzSDI", "momenty"),
    ("4-rejestr-reklam", "#register", None),
    ("5-niepelne", "#incomplete", None),
    ("6-zrodla", "#sources", None),
    ("7-kalibracja", "#calibration", None),
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
            page.screenshot(path=str(out / f"{label}-{name}.png"), full_page=False)
            if "karta" in name:
                # drugi zrzut: przewinięcie karty do momentów i kadrów
                page.evaluate("document.getElementById('sekcja-momenty')?.scrollIntoView({block:'start'})")
                page.wait_for_timeout(500)
                page.screenshot(path=str(out / f"{label}-{name}-momenty.png"), full_page=False)
        context.close()
    browser.close()

expected = ("favicon",)
noise = [c for c in console if "Failed to load resource" not in c[2] and "favicon" not in c[2]]
unexpected = sorted({u for u in failed if not any(e in u for e in expected)})
check("odpowiedzi 4xx tylko z tras jeszcze nieistniejących", not unexpected, ", ".join(unexpected))
check("konsola bez błędów", not noise, json.dumps(noise, ensure_ascii=False)[:600])
print(datetime.datetime.now().isoformat(timespec="seconds"), "zrzuty:", out)
sys.exit(1 if failures else 0)
