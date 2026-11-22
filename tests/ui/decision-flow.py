#!/usr/bin/env python3
"""Desktop and phone decision flow. --base MUST point to a disposable database copy."""
import argparse
import json
import urllib.request

from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument('--base', required=True, help='API on a disposable copy; this test writes decisions')
parser.add_argument('--chromium', default=None)
args = parser.parse_args()
base = args.base.rstrip('/')


def first_review():
    request = urllib.request.Request(base + '/v1/queues/review?limit=1', headers={'X-InvestWatch-Schema': '2'})
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.load(response)['items'][0]


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=args.chromium, headless=True, args=['--no-sandbox'])
    for width in (1440, 390):
        case = first_review()
        page = browser.new_page(viewport={'width': width, 'height': 900}, locale='pl-PL')
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(base + '/#review', wait_until='domcontentloaded')
        page.get_by_text(case['title'], exact=True).first.click(timeout=90000)
        selector = page.get_by_role('combobox', name='Rodzaj decyzji')
        selector.wait_for(timeout=90000)
        save = page.get_by_role('button', name='Zapisz decyzję')
        assert save.bounding_box()['height'] >= 44
        selector.click()
        page.get_by_role('option', name='Bez przesłanki', exact=True).click()
        page.get_by_label('Uzasadnienie decyzji').fill('Weryfikacja na kopii testowej')
        save.click()
        page.get_by_text('Decyzja została zapisana.').wait_for(timeout=90000)
        assert not errors, errors
        assert not page.evaluate('document.documentElement.scrollWidth > innerWidth + 1')
        print(f'{width}: wybór i zapis decyzji OK; przycisk ≥44 px')
        page.close()
    browser.close()
