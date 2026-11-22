#!/usr/bin/env python3
"""Exercise decisions and stage transitions on a disposable copy of the candidate database."""
import argparse
import csv
import io
import json
import urllib.request
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument('--base', required=True, help='server with a disposable database; this test writes decisions')
parser.add_argument('--chromium', default=None)
parser.add_argument('--shots', default='')
args = parser.parse_args()
base = args.base.rstrip('/')


def read(path):
    req = urllib.request.Request(base + path, headers={'X-InvestWatch-Schema': '2'})
    with urllib.request.urlopen(req, timeout=90) as response:
        return json.load(response)


def card(case_id):
    return read('/v1/cases/' + quote(case_id, safe='/'))


def check(label, condition):
    if not condition:
        raise AssertionError(label)
    print('OK  ' + label, flush=True)


ids = [item['id'] for item in read('/v1/queues/review?limit=50')['items'][:4]]
assert len(ids) == 4

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path=args.chromium, headless=True, args=['--no-sandbox'])
    page = browser.new_page(viewport={'width': 1440, 'height': 1000}, locale='pl-PL')
    page.set_default_timeout(90000)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))

    def open_case(case_id, stage):
        fragment = '#review?case=' + quote(case_id, safe='')
        if stage != 'review':
            fragment += '&state=' + stage
        page.goto(base + '/' + fragment, wait_until='domcontentloaded')
        page.get_by_role('heading', name=card(case_id)['title']).first.wait_for()

    def decide(case_id, source, action, target, note, require_manual=False):
        open_case(case_id, source)
        page.get_by_role('button', name=action, exact=True).click()
        box = page.get_by_label('Uzasadnienie decyzji')
        draft = box.input_value()
        check(action + ': istnieje szkic oznaczony jako roboczy', bool(draft) and 'propozycja robocza' in page.inner_text('body').lower())
        save = page.get_by_role('button', name='Zatwierdź i zapisz decyzję')
        if require_manual:
            save.click()
            page.get_by_text('Podaj własnymi słowami', exact=False).first.wait_for()
            check(action + ': wymagane ustalenie człowieka', card(case_id)['workflowStage'] == source)
        box.fill(note)
        save.click()
        page.get_by_text('Decyzja zatwierdzona: ' + card(case_id)['title'], exact=True).first.wait_for()
        updated = card(case_id)
        check(action + ': zapis i etap ' + target, updated['workflowStage'] == target and updated['lastDecision']['note'] == note)
        queues = updated['queues']
        check(action + ': członkostwo docelowej kolejki', target in queues and (target == 'review' or 'review' not in queues))
        check(action + ': po zapisie poprzednia karta nie pozostaje otwarta', quote(case_id, safe='') not in page.url)
        destination = {'review': 'Do sprawdzenia', 'control': 'Przekazane do kontroli', 'supplement': 'Do uzupełnienia', 'closed': 'Zakończone'}[target]
        button = {'review': 'Otwórz do sprawdzenia', 'control': 'Otwórz w kontroli', 'supplement': 'Otwórz do uzupełnienia', 'closed': 'Otwórz w zakończonych'}[target]
        page.get_by_role('button', name=button).click()
        page.get_by_role('heading', name=updated['title']).first.wait_for()
        check(action + ': łącze prowadzi do zapisanej sprawy', quote(case_id, safe='') in page.url)

    # Changing actions must preserve a manually edited draft until the explicit replace action.
    open_case(ids[0], 'review')
    page.get_by_role('button', name='Przekaż do kontroli', exact=True).click()
    box = page.get_by_label('Uzasadnienie decyzji')
    check('propozycja zawiera rzeczywistą przesłankę', bool(box.input_value().strip()))
    box.fill('Ręcznie zachowany tekst')
    page.get_by_role('button', name='Zakończ bez przesłanki').click()
    page.get_by_role('button', name='Zatwierdź i zapisz decyzję').click()
    page.get_by_text('Podaj własnymi słowami', exact=False).first.wait_for()
    check('zmiana działania zachowuje edycję, lecz wymaga nowego powodu', box.input_value() == 'Ręcznie zachowany tekst')
    box.fill('Ręcznie zachowany tekst   ')
    page.get_by_role('button', name='Zatwierdź i zapisz decyzję').click()
    page.get_by_text('Podaj własnymi słowami', exact=False).first.wait_for()
    check('same spacje nie są własnym uzasadnieniem', card(ids[0])['workflowStage'] == 'review')
    page.get_by_role('button', name='Skieruj do uzupełnienia').click()
    check('zmiana działania zachowuje ręczną edycję', box.input_value().strip() == 'Ręcznie zachowany tekst')
    page.get_by_role('button', name='Zastąp tekst nową propozycją').click()
    check('jawna zamiana wstawia propozycję dla nowego działania', 'uzupełnić dane' in box.input_value())

    decide(ids[0], 'review', 'Przekaż do kontroli', 'control', 'Sprawdzić oznaczenie współpracy w źródle.')
    check('w kontroli widoczne poprzednie uzasadnienie', 'Sprawdzić oznaczenie współpracy w źródle.' in page.inner_text('body'))
    decide(ids[0], 'control', 'Wróć do sprawdzenia', 'review', 'Powrót po wstępnym przeglądzie.', True)
    decide(ids[0], 'review', 'Przekaż do kontroli', 'control', 'Skierowanie do dalszej kontroli.')
    decide(ids[0], 'control', 'Zakończ kontrolę', 'closed', 'Sprawdzono materiał i wpis w wykazie KNF.', True)
    decide(ids[0], 'closed', 'Wróć do sprawdzenia', 'review', 'Nowa informacja wymaga ponownej oceny.', True)

    decide(ids[1], 'review', 'Skieruj do uzupełnienia', 'supplement', 'Potrzebna pełna transkrypcja.')
    decide(ids[1], 'supplement', 'Dane uzupełnione', 'review', 'Uzyskano transkrypcję, wypowiedź 0:15.', True)
    decide(ids[1], 'review', 'Skieruj do uzupełnienia', 'supplement', 'Należy jeszcze ustalić podmiot.')
    decide(ids[1], 'supplement', 'Wróć do sprawdzenia', 'review', 'Dane nie są dostępne; ponowna ocena.', True)

    decide(ids[2], 'review', 'Zakończ bez przesłanki', 'closed', 'Przejrzano źródło; brak podstaw do kontroli.', True)
    decide(ids[3], 'review', 'Zakończ z innym uzasadnieniem', 'closed', 'Sprawę zakończono po przeglądzie.', True)
    # The server commits the first PATCH, but its response is lost in transit.
    # A retry must carry the identical requestId and original revision even after WS refresh.
    retry_id = next(item['id'] for item in read('/v1/queues/review?limit=50')['items'] if item['id'] not in ids)
    page.goto(base + '/#review', wait_until='domcontentloaded')
    page.get_by_role('button', name='Przekaż do kontroli').first.wait_for()
    before = read('/v1/queues/review?limit=1')['items'][0]['id']
    retry_id = before
    revision = card(retry_id)['revision']
    attempts = []

    def lose_first_response(route):
        if route.request.method != 'PATCH':
            route.continue_()
            return
        attempts.append(json.loads(route.request.post_data))
        if len(attempts) == 1:
            route.fetch()
            route.abort('failed')
        else:
            route.continue_()

    page.route('**/v1/cases/**', lose_first_response)
    page.get_by_role('button', name='Przekaż do kontroli').first.click()
    page.get_by_label('Uzasadnienie decyzji').fill('Powtórzenie zapisu po utracie odpowiedzi.')
    page.get_by_role('button', name='Zatwierdź i zapisz decyzję').click()
    page.get_by_text('Nie potwierdzono zapisu:', exact=False).first.wait_for()
    page.wait_for_timeout(1200)
    check('utracona odpowiedź: sprawa jest przypięta', quote(retry_id, safe='') in page.url)
    page.get_by_role('button', name='Zatwierdź i zapisz decyzję').click()
    page.get_by_text('Decyzja zatwierdzona:', exact=False).first.wait_for()
    page.unroute_all()
    check('ponowienie używa identycznego żądania i requestId', len(attempts) == 2 and attempts[0] == attempts[1] and bool(attempts[0].get('requestId')))
    check('utracona odpowiedź: decyzja zapisana tylko raz', card(retry_id)['revision'] == revision + 1)
    first_module = card(retry_id)['module']
    other_module = 'M2' if first_module == 'M1' else 'M1'
    other = next(item['id'] for item in read('/v1/queues/review?limit=100')['items'] if item.get('module') == other_module)
    decide(other, 'review', 'Przekaż do kontroli', 'control', 'Porównać dowód i jego źródło.')
    href = page.get_by_role('link', name='Raport', exact=True).get_attribute('href')
    check('raport kolejki kontroli obejmuje wszystkie moduły', 'module=all' in href and 'queue=control' in href)
    with urllib.request.urlopen(base + href, timeout=90) as response:
        csv_bytes = response.read()
    check('raport CSV jest w UTF-8 z BOM', csv_bytes.startswith(b'\xef\xbb\xbf'))
    report = list(csv.DictReader(io.StringIO(csv_bytes.decode('utf-8-sig'))))
    modules = {row['modul'] for row in report}
    check('raport zawiera oba moduły i rzeczywiste decyzje', {first_module, other_module}.issubset(modules) and all(row['etap'] == 'control' and row['rodzajDecyzji'] and row['uzasadnienieDecyzji'] for row in report))
    check('bez błędów JavaScript', not errors)
    page.close()

    mobile_item = read('/v1/queues/review?limit=1')['items'][0]
    mobile = browser.new_page(viewport={'width': 390, 'height': 844}, locale='pl-PL', has_touch=True)
    mobile.goto(base + '/#review?case=' + quote(mobile_item['id'], safe=''), wait_until='domcontentloaded')
    mobile.get_by_role('button', name='Przekaż do kontroli').click(timeout=90000)
    mobile.get_by_role('button', name='Zatwierdź i zapisz decyzję').click()
    target = mobile.get_by_role('button', name='Otwórz w kontroli')
    target.wait_for(timeout=90000)
    bounds = target.bounding_box()
    check('telefon: potwierdzenie i przejście do kontroli w oknie', bounds and bounds['y'] >= 0 and bounds['y'] + bounds['height'] <= 844)
    target.click()
    mobile.get_by_text('Poprzednia zatwierdzona decyzja:', exact=False).first.wait_for(timeout=90000)
    check('telefon: powrót do zapisanej sprawy w kontroli', 'state=control' in mobile.url and quote(mobile_item['id'], safe='') in mobile.url)
    mobile.close()

    if args.shots:
        output = Path(args.shots)
        output.mkdir(parents=True, exist_ok=True)
        for width, height in ((1440, 1000), (390, 844)):
            shot = browser.new_page(viewport={'width': width, 'height': height}, locale='pl-PL', has_touch=width == 390)
            shot.goto(base + '/#review?case=' + quote(ids[0], safe=''), wait_until='domcontentloaded')
            shot.get_by_role('button', name='Przekaż do kontroli').click(timeout=90000)
            shot.locator('#sekcja-decyzja').scroll_into_view_if_needed()
            shot.screenshot(path=str(output / f'{width}-decyzja.png'))
            check(f'{width}: brak poziomego przewijania', not shot.evaluate('document.documentElement.scrollWidth > innerWidth + 1'))
            shot.close()
    browser.close()
