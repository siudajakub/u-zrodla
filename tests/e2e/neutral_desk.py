"""Compare the same analyst workflow on desktop and mobile against a disposable API."""

import argparse
import re
from pathlib import Path
from urllib.parse import quote, urljoin
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright


def run(base, kind, out, binary, require_live):
    is_preview = kind == "neutral"
    route = "/theme-preview/" if is_preview else "/"
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=binary, args=["--no-sandbox", "--disable-dev-shm-usage"])
        for device, width, height in [("desktop", 1440, 1000), ("mobile", 390, 844)]:
            page = browser.new_page(viewport={"width": width, "height": height}, locale="pl-PL",
                                    is_mobile=device == "mobile", has_touch=device == "mobile")
            page.set_default_timeout(9000)
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.route("**/*", lambda request: request.continue_() if request.request.url.startswith(base + "/")
                       else request.abort())
            page.goto(base + route, wait_until="networkidle")
            page.evaluate("document.fonts.ready")
            search = page.get_by_role("searchbox")
            expect(search).to_be_visible()
            page.screenshot(path=str(out / f"{kind}-{device}-queue.png"))
            if is_preview and require_live:
                flag = page.get_by_role("combobox", name="Sygnał do sprawdzenia")
                flag.click()
                page.get_by_role("option", name="Oznaczone do sprawdzenia").click()
                expect(page.get_by_role("cell", name=re.compile("Doradztwo.*Model wskazał materiał")).first).to_be_visible()
                expect(page.get_by_role("cell", name=re.compile("Fundusze ETF.*Reguły wskazały materiał")).first).to_be_visible()
                expect(page.get_by_role("button", name=re.compile("^Instrumenty finansowe"))).to_have_count(0)
                flag.click()
                page.get_by_role("option", name="Wszystkie sprawy").click()

            def open_case(case_id):
                case_response = page.request.get(f"{base}/v1/cases/{quote(case_id, safe='')}")
                assert case_response.ok, case_response.text()
                case = case_response.json()
                search.fill(case["title"])
                page.get_by_role("button", name=re.compile(re.escape(case["title"]))).last.click()
                expect(page.get_by_role("heading", name=case["title"])).to_be_visible()
                return case

            material = open_case("demo-aurora-kod")
            player = page.locator("video, audio").first
            page.wait_for_function("document.querySelector('video, audio')?.readyState >= 1")
            player.scroll_into_view_if_needed()
            if is_preview:
                page.get_by_role("button", name=re.compile(r"^Odtwórz 0:00,33")).first.click()
            else:
                page.locator(".timecode").first.click()
            page.wait_for_function("document.querySelector('video, audio')?.currentTime >= 0.33")
            player.evaluate("(player) => player.pause()")
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
            page.screenshot(path=str(out / f"{kind}-{device}-audio.png"))
            page.get_by_role("tab" if is_preview else "button", name=re.compile("Decyzja")).click()
            if is_preview:
                page.get_by_role("combobox", name="Status sprawy").click()
                page.get_by_role("option", name="W analizie").click()
            else:
                page.locator("#decision").select_option("reviewing")
            note = f"Sprawdzono dowód podczas próby {kind} {device} {uuid4().hex[:6]}"
            field = page.get_by_role("textbox", name="Uzasadnienie decyzji")
            field.fill(note)
            if is_preview:
                page.get_by_role("tab", name="Dowody").click()
                assert player.evaluate("(player) => player.currentTime") >= 0.33
                page.get_by_role("tab", name="Decyzja").click()
                expect(field).to_have_value(note)
            page.get_by_role("button", name="Zapisz decyzję").click()
            expect(page.get_by_text("Decyzja została zapisana.", exact=True)).to_be_visible()
            stored = page.request.get(f"{base}/v1/cases/{material['id']}").json()
            assert stored["status"] == "reviewing" and any(item["note"] == note for item in stored["history"])
            if is_preview and device == "desktop":
                case_url = f"{base}/v1/cases/{quote(material['id'], safe='')}"
                conflict = f"Szkic po równoległym zapisie {uuid4().hex[:6]}"
                field.fill(conflict)

                def change_before_patch(route):
                    if route.request.method == "PATCH":
                        current = page.request.get(case_url).json()
                        other = page.request.patch(case_url, data={
                            "status": "new", "note": "Równoległa decyzja w teście",
                            "expectedRevision": current["revision"],
                        })
                        assert other.ok, other.text()
                    route.continue_()

                page.route(case_url, change_before_patch)
                with page.expect_response(lambda response: response.url == case_url and response.status == 409):
                    page.get_by_role("button", name="Zapisz decyzję").click()
                page.unroute(case_url, change_before_patch)
                expect(page.get_by_text("Sprawa zmieniła się podczas edycji")).to_be_visible()
                expect(field).to_have_value(conflict)
                page.get_by_role("button", name="Przejrzałem zmiany").click()
                page.get_by_role("button", name="Zapisz decyzję").click()
                expect(field).to_have_value("")
                expect(page.get_by_text(conflict, exact=True)).to_be_visible()

            if is_preview and device == "mobile":
                page.get_by_role("button", name="Wróć do kolejki").click()
                expect(page.get_by_role("button", name=re.compile(re.escape(material["title"]))).last).to_be_focused()

            capture = open_case("dom-xtb-etf")
            assert len(capture["checks"]) == 19
            if is_preview:
                exact = next(check for check in capture["checks"]
                             if (str(check["id"]) == "3" if require_live
                                 else any(m.get("url") for m in check.get("measurements", []))))
                measurement = page.get_by_role("button", name=re.compile(re.escape(exact["label"]))).first
                if measurement.get_attribute("aria-expanded") != "true":
                    measurement.click()
                def measurement_link(url):
                    return page.get_by_role("link", name=re.compile(r"^Zrzut ·")).and_(
                        page.locator(f'a[href="{url}"]')).first

                for viewport in exact["measurements"]:
                    if not viewport.get("url"):
                        continue
                    # The evidence anchor is inside the selected control and points to the exact archived view.
                    archive_url = urljoin(base, viewport["url"])
                    archive = measurement_link(archive_url)
                    expect(archive).to_be_visible()
                    archive_response = page.request.get(archive_url)
                    assert archive_response.ok, archive_response.text()
                    if viewport.get("screenshotHash"):
                        assert viewport["screenshotHash"] in archive_url
                    if viewport.get("domUrl"):
                        dom = page.request.get(urljoin(base, viewport["domUrl"]))
                        assert dom.ok, dom.text()
                        if viewport.get("state"):
                            assert dom.json()["state"] == viewport["state"]
                if require_live:
                    target = next(item for item in exact["measurements"] if item.get("width") == width and item.get("state") == "profit")
                    assert target["warning"]["text"] and target["profit"]["text"]
                    target_archive = urljoin(base, target["url"])
                    viewport_row = measurement_link(target_archive).locator("xpath=../..")
                    viewport_row.get_by_role("button", name="Pokaż podgląd").click()
                    image = page.get_by_role("img", name=re.compile("Zapis widoku"))
                    expect(image).to_have_attribute("src", target_archive)
                    page.wait_for_function("(url) => [...document.images].some(image => image.src === url && image.naturalWidth > 0)", arg=target_archive)
                    viewport_row.get_by_text(target["profit"]["text"], exact=False).first.scroll_into_view_if_needed()
                    expect(viewport_row.get_by_text(target["warning"]["text"], exact=False).first).to_be_visible()
                    viewport_row.screenshot(path=str(out / f"{kind}-{device}-etf-id3.png"))
                elif device == "desktop":
                    page.get_by_text(exact["label"], exact=True).scroll_into_view_if_needed()
                    page.screenshot(path=str(out / f"{kind}-{device}-measurement.png"))
            else:
                image = page.locator(".detail img").first
                expect(image).to_be_visible()
                assert image.evaluate("(image) => image.complete && image.naturalWidth > 0")
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
            if is_preview and require_live:
                if device == "mobile":
                    page.get_by_role("button", name="Wróć do kolejki").click()
                open_case("web:www.bdm.pl/rachunek-inwestycyjny")
                page.get_by_role("tab", name="Decyzja").click()
                live_note = f"Potwierdzono pomiar reklamy {uuid4().hex[:6]}"
                page.get_by_role("textbox", name="Uzasadnienie decyzji").fill(live_note)
                page.get_by_role("button", name="Zapisz decyzję").click()
                expect(page.get_by_text(live_note, exact=True)).to_be_visible()
                if device == "mobile":
                    page.get_by_role("button", name="Wróć do kolejki").click()

                m3_cases = page.request.get(base + "/v1/state").json()["findings"]
                bossa = next(item for item in m3_cases if item["id"].startswith("web:bossa.pl/oferta/doradztwo"))
                open_case(bossa["id"])
                proof = page.get_by_role("tabpanel", name="Dowody")
                assert bossa.get("reviewSuggestion"), bossa["id"]
                suggestion = bossa["reviewSuggestion"]
                assert suggestion["source"] == "semantic", suggestion
                expect(proof.get_by_text(suggestion["reason"], exact=True)).to_be_visible()
                expect(proof.get_by_text(suggestion["evidence"]["text"], exact=False).first).to_be_visible()
                expect(proof.get_by_role("link", name="Źródło sugestii")).to_have_attribute("href", bossa["url"])
                expect(proof.get_by_text(re.compile("pozycja 5: doradztwo inwestycyjne", re.I)).first).to_be_visible()
                proof.get_by_text("Kontekst w zapisanym tekście", exact=True).click()
                context = proof.locator("details").filter(has_text="Kontekst w zapisanym tekście").first
                expect(context.get_by_text(suggestion["evidence"]["text"], exact=False)).to_be_visible()
                page.screenshot(path=str(out / f"{kind}-{device}-m3.png"))

            def navigate(name):
                item = page.get_by_role("link" if is_preview else "button", name=name).first
                if not is_preview and device == "mobile":
                    # Exercise the accessible button name on the fixed legacy navigation.
                    item.press("Enter")
                else:
                    item.click()

            navigate(re.compile("Źródła"))
            expect(page.get_by_text("Odkryci twórcy", exact=False).first).to_be_visible()
            navigate("Kalibracja" if is_preview else re.compile("Jakość analizy"))
            expect(page.get_by_text("Robocze etykiety oznaczają materiały do sprawdzenia.", exact=False)).to_be_visible()
            slider = page.get_by_role("slider").first
            slider.focus()
            slider.press("End")
            expect(page.get_by_text(re.compile("Próg (kierowania do analizy: )?100")).first).to_be_visible()
            assert not errors, errors
            page.close()
            print(f"{kind} {device}: kolejka, odsłuch, zapisana decyzja, M2, źródła, próg")
        browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="URL osobnej instancji. Test zmienia dane spraw.")
    parser.add_argument("kind", choices=["baseline", "neutral"])
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--chromium")
    parser.add_argument("--require-live", action="store_true", help="Wymagaj przechwycenia BDM i pełnego dowodu M3 BOŚ.")
    args = parser.parse_args()
    run(args.url.rstrip("/"), args.kind, args.out, args.chromium, args.require_live)
