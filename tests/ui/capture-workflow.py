#!/usr/bin/env python3
"""Capture current story screens. The server must use a disposable candidate copy."""
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument('--base', required=True)
parser.add_argument('--chromium', default=None)
parser.add_argument('--out', required=True)
args = parser.parse_args()
base = args.base.rstrip('/')
out = Path(args.out)
out.mkdir(parents=True, exist_ok=True)

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path=args.chromium, headless=True, args=['--no-sandbox'])
    for width, height in ((1440, 1000), (390, 844)):
        page = browser.new_page(viewport={'width': width, 'height': height}, locale='pl-PL', has_touch=width == 390)
        page.goto(base + '/#review', wait_until='domcontentloaded')
        page.get_by_text('Freedom24 Alternatywy', exact=False).first.wait_for(timeout=90000)
        page.screenshot(path=str(out / f'{width}-kolejka.png'))
        page.get_by_text('Freedom24 Alternatywy', exact=False).first.click()
        page.get_by_role('heading', name='Freedom24 Alternatywy: Którego brokera wybrać? (2026)').wait_for(timeout=90000)
        page.screenshot(path=str(out / f'{width}-forexmind.png'))
        page.get_by_role('button', name='Przekaż do kontroli').click()
        page.get_by_label('Uzasadnienie decyzji').scroll_into_view_if_needed()
        page.screenshot(path=str(out / f'{width}-decyzja.png'))
        assert not page.evaluate('document.documentElement.scrollWidth > innerWidth + 1')
        page.close()

    page = browser.new_page(viewport={'width': 1440, 'height': 1000}, locale='pl-PL')
    page.goto(base + '/#review?case=youtube%3AAqXHkxDzSDI', wait_until='domcontentloaded')
    page.get_by_role('button', name='Przekaż do kontroli').click(timeout=90000)
    page.get_by_role('button', name='Zatwierdź i zapisz decyzję').click()
    page.get_by_role('button', name='Otwórz w kontroli').wait_for(timeout=90000)
    page.screenshot(path=str(out / '1440-zapisano.png'))
    page.get_by_role('button', name='Otwórz w kontroli').click()
    page.get_by_text('Poprzednia zatwierdzona decyzja:', exact=False).first.wait_for(timeout=90000)
    page.screenshot(path=str(out / '1440-kontrola.png'))
    page.close()
    browser.close()
print('Zapisano zrzuty kolejki, sprawy, szkicu i rzeczywiście zatwierdzonej decyzji.')
