"""Current desk and presentation acceptance checks against a disposable database."""
import argparse
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import sync_playwright


def request(base, path, method='GET', data=None):
    body = json.dumps(data).encode() if data is not None else None
    headers = {'X-InvestWatch-Schema': '2', 'Content-Type': 'application/json'}
    req = urllib.request.Request(base + path, data=body, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=90) as response:
        return json.load(response)


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print('OK  ' + name, flush=True)


def page_for(browser, width=1440):
    return browser.new_page(viewport={'width': width, 'height': 900}, locale='pl-PL', has_touch=width == 390)


def check_film(browser, base, shots):
    page = page_for(browser)
    page.set_default_timeout(90000)
    page.goto(base + '/#review', wait_until='domcontentloaded')
    page.get_by_text('Freedom24 Alternatywy', exact=False).first.click()
    page.get_by_role('heading', name='Freedom24 Alternatywy: Którego brokera wybrać? (2026)').wait_for()
    check('ForexMind: przesłanka i kontekst 0:15', 'TRADEXTB' in page.inner_text('body') and page.get_by_text('Odtwórz od 0:15').count() == 1)
    page.get_by_role('button', name='Dokumentacja i historia').click()
    page.get_by_role('tab', name='Zebrane kadry').click()
    check('ForexMind: dostęp do zebranych kadrów', page.locator('img[src*="/v1/frames/AqXHkxDzSDI/"]').count() >= 1)
    if shots:
        output = Path(shots)
        output.mkdir(parents=True, exist_ok=True)
        for width in (1440, 390):
            capture = page_for(browser, width)
            capture.goto(base + '/#review?case=youtube%3AAqXHkxDzSDI', wait_until='domcontentloaded')
            capture.get_by_role('heading', name='Freedom24 Alternatywy: Którego brokera wybrać? (2026)').wait_for(timeout=90000)
            capture.get_by_role('button', name='Przekaż do kontroli').click()
            capture.get_by_label('Uzasadnienie decyzji').scroll_into_view_if_needed()
            capture.screenshot(path=str(output / f'{width}-decyzja.png'))
            check(f'{width}: decyzja bez poziomego przewijania', not capture.evaluate('document.documentElement.scrollWidth > innerWidth+1'))
            capture.close()
    page.keyboard.press('Escape')
    page.get_by_role('tab', name=re.compile('^Rejestr')).click()
    page.get_by_role('searchbox').fill('Comparic')
    page.get_by_text('ARABIA', exact=False).first.click()
    page.get_by_text('10:14', exact=False).first.wait_for()
    check('Comparic: rejestr i ujawnienie w mowie', '10:14' in page.inner_text('body'))
    page.get_by_role('tab', name=re.compile('^Rejestr')).click()
    report = page.get_by_role('link', name='Raport', exact=True).get_attribute('href')
    with urllib.request.urlopen(base + report, timeout=90) as response:
        check('eksport CSV z rejestru', response.status == 200 and response.read().startswith(b'\xef\xbb\xbf'))
    page.get_by_role('tab', name='Źródła', exact=True).click()
    page.get_by_role('heading', name='Źródła').wait_for()
    check('źródła: platformy i stan skanu', 'Platformy' in page.inner_text('body'))
    page.goto(base + '/#review?case=web%3Awww.finax.eu%2Fpl%2Fprodukty%2Finwestowanie-w-etf')
    page.get_by_role('heading', name='Globalne portfele | Finax.eu').wait_for()
    page.get_by_label('zrzut strony, komputer').first.click()
    check('reklama: otwarcie zrzutu dowodu', page.get_by_role('dialog').is_visible())
    page.keyboard.press('Escape')
    page.goto(base + '/#review?case=web%3Ardmwm.pl%3Am3')
    page.get_by_text('Sprawdź ofertę i uprawnienia').wait_for()
    check('doradztwo: widoczne cechy oceny', page.locator('[data-axis]').count() > 0)
    page.get_by_role('tab', name='Kalibracja').click()
    page.get_by_role('combobox', name='Temat kalibracji').click()
    page.get_by_role('option', name='Reklamy firm', exact=True).click()
    page.get_by_text('Fałszywe alarmy', exact=False).first.wait_for()
    page.get_by_role('slider').focus()
    for _ in range(4):
        page.keyboard.press('ArrowRight')
    page.get_by_text('Przy progu 50 pkt', exact=False).wait_for()
    check('kalibracja reklam: próg 30 → 50', 'Przeoczenia' in page.inner_text('body'))
    if shots:
        Path(shots).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(shots) / 'film-kalibracja.png'))
    page.close()


def check_desktop_and_phone(browser, base, width):
    page = page_for(browser, width)
    page.set_default_timeout(90000)
    errors = []
    requests = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('request', lambda req: requests.append(req.url))
    page.goto(base + '/#review', wait_until='domcontentloaded')
    page.get_by_text('Freedom24 Alternatywy', exact=False).first.wait_for()
    check(f'{width}: wyszukiwanie, filtry, raport', page.get_by_role('searchbox').count() == 1 and page.get_by_role('button', name='Filtry').count() == 1 and page.get_by_role('link', name='Raport', exact=True).count() == 1)
    page.get_by_role('button', name='Filtry').click()
    check(f'{width}: stan i źródło w filtrach', page.get_by_role('combobox', name='Stan').count() == 1 and page.get_by_role('combobox', name='Źródło').count() == 1)
    page.keyboard.press('Escape')
    page.get_by_role('searchbox').fill('Freedom24')
    page.get_by_text('Pokazano 1 z 1').wait_for()
    check(f'{width}: wyszukiwanie po stronie API', 'q=Freedom24' in page.url)
    page.get_by_role('searchbox').fill('zzzznieistnieje')
    page.get_by_text('Brak materiałów dla wybranych filtrów').first.wait_for()
    page.get_by_role('button', name='Wyczyść filtry').first.click()
    page.get_by_text('Freedom24 Alternatywy', exact=False).first.click()
    page.get_by_role('heading', name='Freedom24 Alternatywy: Którego brokera wybrać? (2026)').wait_for()
    check(f'{width}: moment i działania decyzji', page.get_by_text('Odtwórz od 0:15').count() == 1 and page.get_by_role('button', name='Przekaż do kontroli').count() == 1)
    page.get_by_role('button', name='Przekaż do kontroli').click()
    check(f'{width}: szkic i zatwierdzenie', page.get_by_label('Uzasadnienie decyzji').input_value() != '' and page.get_by_role('button', name='Zatwierdź i zapisz decyzję').bounding_box()['height'] >= 44)
    page.get_by_role('tab', name='Źródła', exact=True).click()
    page.get_by_role('heading', name='Źródła').wait_for()
    start = len(requests)
    page.get_by_role('tab', name=re.compile('^Do sprawdzenia')).click()
    page.wait_for_timeout(1000)
    check(f'{width}: powrót bez pobrania listy', not any('/v1/queues/' in url for url in requests[start:]))
    check(f'{width}: bez błędów JS i poziomego przewijania', not errors and not page.evaluate('document.documentElement.scrollWidth > innerWidth+1'))
    page.close()


def check_desk_regressions(browser, base):
    page = page_for(browser)
    page.set_default_timeout(90000)
    page.goto(base + '/#register', wait_until='domcontentloaded')
    page.get_by_role('button', name='Pokaż więcej').wait_for()
    page.get_by_role('button', name='Pokaż więcej').click()
    page.get_by_text(re.compile(r'Pokazano 100 z')).wait_for()
    check('paginacja rejestru', True)
    page.goto(base + '/#review?q=brak_wyniku_987')
    page.get_by_text('Brak materiałów dla wybranych filtrów').first.wait_for()
    check('pusty wynik daje możliwość wyczyszczenia', page.get_by_role('button', name='Wyczyść filtry').count() > 0)
    page.route('**/v1/queues/review?*', lambda route: route.fulfill(status=500, content_type='application/json', body='{"detail":"Błąd testowy"}'))
    page.goto(base + '/#review?q=blad_testowy')
    page.get_by_text('Błąd testowy', exact=False).first.wait_for()
    check('błąd pobrania jest widoczny', True)
    page.unroute_all()
    item = request(base, '/v1/queues/review?limit=1')['items'][0]
    first = page_for(browser)
    second = page_for(browser)
    first.goto(base + '/#review?case=' + quote(item['id'], safe=''))
    second.goto(base + '/#review')
    first.get_by_role('button', name='Zakończ bez przesłanki').wait_for(timeout=90000)
    row = second.locator('[id="row-' + item['id'] + '"]')
    row.wait_for(timeout=90000)
    changes = []
    second.on('request', lambda req: changes.append(req.url))
    first.get_by_role('button', name='Zakończ bez przesłanki').click()
    first.get_by_label('Uzasadnienie decyzji').fill('Test na odizolowanej kopii')
    first.get_by_role('button', name='Zatwierdź i zapisz decyzję').click()
    first.get_by_text('Decyzja zatwierdzona:', exact=False).first.wait_for(timeout=90000)
    row.wait_for(state='detached', timeout=90000)
    check('zapis decyzji i aktualizacja drugiej sesji WS', any('/v1/queues/review?' in url for url in changes))
    case_path = '/v1/cases/' + quote(item['id'], safe='/')
    current = request(base, case_path)
    try:
        request(base, case_path, 'PATCH', {'resolution': 'no_signal', 'note': 'Stara rewizja', 'expectedRevision': current['revision'] - 1, 'reviewedVersion': current['version']})
    except urllib.error.HTTPError as error:
        check('nieaktualna rewizja zwraca 409', error.code == 409)
    else:
        raise AssertionError('nieaktualna rewizja nie zwróciła 409')
    def stale_revision(route):
        if route.request.method != 'PATCH':
            route.continue_()
            return
        payload = json.loads(route.request.post_data)
        payload['expectedRevision'] = current['revision'] - 1
        route.continue_(post_data=json.dumps(payload))

    first.goto(base + '/#review?case=' + quote(item['id'], safe=''))
    first.get_by_role('button', name='Wróć do sprawdzenia').wait_for(timeout=90000)
    first.route('**/v1/cases/**', stale_revision)
    first.get_by_role('button', name='Wróć do sprawdzenia').click()
    first.get_by_label('Uzasadnienie decyzji').fill('Szkic po konflikcie')
    first.get_by_role('button', name='Zatwierdź i zapisz decyzję').click()
    first.get_by_text('Sprawa zmieniła się podczas edycji').wait_for(timeout=90000)
    check('konflikt 409 zachowuje szkic', first.get_by_label('Uzasadnienie decyzji').input_value() == 'Szkic po konflikcie')
    first.unroute_all()
    first.close()
    second.close()
    threshold = request(base, '/v1/threshold')
    page.goto(base + '/#calibration')
    page.get_by_role('slider').wait_for(timeout=90000)
    page.get_by_role('slider').focus()
    page.keyboard.press('ArrowRight')
    new_value = min(100, threshold['value'] + 5)
    page.get_by_role('button', name=f'Zastosuj {new_value} pkt').click()
    page.get_by_role('button', name='Potwierdź zmianę progu').click()
    page.get_by_text(f'Próg ustawiony na {new_value} pkt.').wait_for(timeout=90000)
    check('zapis progu', request(base, '/v1/threshold')['value'] == new_value)
    page.get_by_text('Więcej: historia ustawień, porównanie reguł, zbiór etykiet').click()
    page.get_by_role('button', name='Przywróć').last.click()
    for _ in range(30):
        if request(base, '/v1/threshold')['value'] == threshold['value']:
            break
        time.sleep(0.5)
    check('przywrócenie progu', request(base, '/v1/threshold')['value'] == threshold['value'])
    page.close()


def main(mode):
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', required=True, help='serwer na kopii bazy (desk zapisuje decyzję i próg)')
    parser.add_argument('--chromium', default='')
    if mode == 'film':
        parser.add_argument('--shots', default='')
    args = parser.parse_args()
    base = args.base.rstrip('/')
    binary = args.chromium or next(iter(sorted(Path.home().glob('.cache/ms-playwright/chromium-*/chrome-linux64/chrome'))), None)
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=str(binary) if binary else None, headless=True, args=['--no-sandbox'])
        if mode == 'film':
            check_film(browser, base, args.shots)
        else:
            for width in (1440, 390):
                check_desktop_and_phone(browser, base, width)
            check_desk_regressions(browser, base)
        browser.close()
    print(f'{mode}: wszystkie sprawdzenia OK', flush=True)
    return 0
