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
parser.add_argument("--out", default=str(Path(__file__).parent / "screens" / "2026-11-21"))
parser.add_argument("--only", default="")
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


with sync_playwright() as p:
    binary = args.chromium or next(iter(sorted(Path.home().glob(".cache/ms-playwright/chromium-*/chrome-linux64/chrome"))), None)
    browser = p.chromium.launch(executable_path=str(binary) if binary else None, headless=True, args=["--no-sandbox"])
    for label, width, height in (("1440", 1440, 1000), ("390", 390, 844)):
        context = browser.new_context(viewport={"width": width, "height": height}, locale="pl-PL", timezone_id="Europe/Warsaw",
                                      has_touch=width < 500, is_mobile=width < 500, device_scale_factor=1)
        page = context.new_page()
        page.on("console", lambda m, label=label: console.append((label, m.type, m.text)) if m.type in ("error", "warning") else None)
        page.on("response", lambda r: failed.append(r.url) if r.status >= 400 else None)
        page.on("pageerror", lambda e, label=label: console.append((label, "pageerror", str(e))))

        def shot(name):
            if args.only and args.only not in name:
                return
            page.screenshot(path=str(out / f"{label}-{name}.png"), full_page=False)

        page.goto(f"{base}/#review", wait_until="networkidle")
        page.wait_for_selector("text=Co wymaga sprawdzenia", timeout=15000)
        page.wait_for_timeout(600)
        check(f"[{label}] tytuł zakładki i liczba", page.get_by_role("heading", name="Co wymaga sprawdzenia").first.is_visible())
        shot("1-co-wymaga-sprawdzenia")
        # szczegół flagi
        if width >= 1000:
            shot("2-szczegol-flagi")
            panel = page.locator("[role=complementary]")
            panel.evaluate("el => { const s = el.querySelector('[class*=scroll]') || el; s.scrollTop = 900; el.scrollTop = 900; }")
            page.wait_for_timeout(300)
            shot("2b-szczegol-dowody")
        else:
            page.get_by_role("link", name="Inwestycyjna wyprawa", exact=False).first.click() if page.get_by_role("link", name="Ile trzeba mieć").count() == 0 else page.get_by_role("link", name="Ile trzeba mieć").first.click()
            page.wait_for_timeout(500)
            shot("2-szczegol-flagi")
            page.get_by_role("button", name="Wróć do listy").first.click()
            page.wait_for_timeout(300)
        page.goto(f"{base}/#register", wait_until="networkidle")
        page.wait_for_timeout(700)
        shot("3-rejestr-reklam")
        page.goto(f"{base}/#sources", wait_until="networkidle")
        page.wait_for_timeout(700)
        shot("4-zrodla")
        if args.only == "" and width >= 1000:
            for name, hash_ in (("5-m2", "#m2"), ("6-niepelne", "#incomplete"), ("7-kalibracja", "#calibration"), ("8-dodaj-dowod", "#evidence")):
                page.goto(f"{base}/{hash_}", wait_until="networkidle")
                page.wait_for_timeout(600)
                shot(name)
        context.close()
    browser.close()

expected = ("/v1/queues/", "/v1/threshold/history", "favicon")  # trasy, które starszy backend jeszcze nie ma
noise = [c for c in console if "Failed to load resource" not in c[2] and "favicon" not in c[2]]
unexpected = sorted({u for u in failed if not any(e in u for e in expected)})
check("odpowiedzi 4xx tylko z tras jeszcze nieistniejących", not unexpected, ", ".join(unexpected))
check("konsola bez błędów", not noise, json.dumps(noise, ensure_ascii=False)[:600])
print(datetime.datetime.now().isoformat(timespec="seconds"), "zrzuty:", out)
sys.exit(1 if failures else 0)
