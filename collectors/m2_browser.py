"""Capture approved first-party marketing material using a local Chromium worker."""
import argparse
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlsplit

from .common import MAX_RESPONSE, SourceError, digest, safe_get, utc_now
from .m2_archive import PUBLISHERS, SCHEMA, TARGETS, VIEWPORTS, encode, read_bundle, save_asset, write_once
from .sites import SITES, one_hop_links, parse_page

SUPPLEMENTAL = {
    "www.xtb.com": {"xas-cdn.xtb.com", "xas-new-cdn.xtb.com"},
    "www.bdm.pl": set(),
}
READ_TYPES = {"stylesheet", "script", "image", "font"}
REJECT_CONSENT = re.compile(r"^(odrzuć wszystkie|tylko niezbędne|odmów|reject all|deny)$", re.I)
EXTRACT = Path(__file__).with_suffix(".js").read_text(encoding="utf-8")


def allowed_resource(url, method, resource_type, target, asset_hosts, main_frame):
    try:
        parts = urlsplit(url)
        if parts.scheme != "https" or parts.port not in (None, 443) or parts.username or parts.password:
            return False
    except ValueError:
        return False
    if method not in {"GET", "HEAD"}:
        return False
    if resource_type == "document":
        return main_frame and url == target
    return parts.hostname in asset_hosts and resource_type in READ_TYPES


def wait_fonts(page):
    page.evaluate("() => Promise.race([document.fonts.ready.then(() => true), new Promise(done => setTimeout(done, 900))])")


def measure(page, product, legal):
    return page.evaluate(EXTRACT, {"product": product, "legalName": legal})


def anchors(evidence):
    return [evidence[k] for k in ("scrollX", "scrollY", "consentOverlay", "benefit", "warning", "relation", "claimDominant", "warningDominant", "legal", "label", "profit", "profitRelation")]


def snapshot(page, root, url, product, legal, state, response_hash, consent):
    for _ in range(2):
        before = measure(page, product, legal)
        screenshot = page.screenshot(type="png", timeout=4000, caret="hide", scale="css")
        after = measure(page, product, legal)
        if anchors(before) == anchors(after):
            break
    else:
        raise SourceError("Układ zmienił się podczas zapisu zrzutu M2.")
    screenshot_hash = save_asset(root, screenshot, "png")
    dom = {**after, "url": url, "product": product, "state": state, "responseSha256": response_hash,
           "screenshotHash": screenshot_hash, "consentAction": consent, "measurementMethod": "chromium-range-intersection-v1"}
    dom_hash = save_asset(root, encode(dom), "json")
    frame = {k: dom[k] for k in ("width", "height", "state", "screenshotHash")}
    return {**frame, "domHash": dom_hash}, dom


def capture_view(browser, root, url, product, legal, width, height, timeout_error):
    # CSS pixels and the site responsive layout are measured at these declared viewport sizes.
    mobile = width <= 390
    context = browser.new_context(
        viewport={"width": width, "height": height}, device_scale_factor=1, locale="pl-PL",
        has_touch=mobile, reduced_motion="reduce", service_workers="block",
        accept_downloads=False, ignore_https_errors=False,
    )
    context.set_default_timeout(2500)
    page = context.new_page()
    host = urlsplit(url).hostname
    asset_hosts = {host, *SUPPLEMENTAL[host]}
    requests = 0

    def restrict(route):
        nonlocal requests
        request = route.request
        requests += 1
        main = request.resource_type == "document" and request.is_navigation_request() and request.frame == page.main_frame
        if requests <= 260 and not request.redirected_from and allowed_resource(
                request.url, request.method, request.resource_type, url, asset_hosts, main):
            route.continue_()
        else:
            route.abort()

    def block_socket(socket):
        socket.close()

    try:
        context.route("**/*", restrict)
        context.route_web_socket("**/*", block_socket)
        response = page.goto(url, wait_until="domcontentloaded", timeout=15000)
        if response is None or response.status != 200 or page.url != url:
            raise SourceError(f"Strona reklamy nie zwróciła oczekiwanego HTTP 200 ({getattr(response, 'status', 'brak')}).",
                              getattr(response, "status", None))
        if "text/html" not in response.headers.get("content-type", ""):
            raise SourceError("Materiał M2 nie jest stroną HTML.")
        transfer_size = response.headers.get("content-length", "")
        if transfer_size.isdigit() and int(transfer_size) > MAX_RESPONSE:
            raise SourceError("Materiał M2 przekroczył limit odpowiedzi HTML.")
        body = response.body()
        if len(body) > MAX_RESPONSE:
            raise SourceError("Materiał M2 przekroczył limit odpowiedzi HTML.")
        response_hash = digest(body)
        try:
            page.wait_for_load_state("load", timeout=3500)
        except timeout_error:
            pass
        wait_fonts(page)

        frames = []
        scope = None
        consent = None

        def save(state):
            frame, dom = snapshot(page, root, url, product, legal, state, response_hash, consent)
            frames.append(frame)
            return dom

        initial = save("initial")
        if not initial["benefit"]:
            raise SourceError("Chromium nie znalazł w DOM oczekiwanej korzyści w ofercie.")
        scope = (initial["title"], initial["textScope"])
        can_dismiss = page.get_by_role("button", name=REJECT_CONSENT)
        if initial["consentOverlay"] and can_dismiss.count() == 1 and can_dismiss.is_visible():
            can_dismiss.click(timeout=2000)
            consent = "essential_only"
        if initial["benefit"]["visibleFraction"] < 0.98 or consent:
            page.evaluate(EXTRACT, {"product": product, "action": "claim"})
            wait_fonts(page)
            save("claim")
        warning_state = None
        if initial["warning"] and initial["warning"]["visibleFraction"] < 0.98:
            page.evaluate(EXTRACT, {"product": product, "action": "warning"})
            wait_fonts(page)
            warning_state = save("warning")
        if initial["profit"] and initial["profit"]["visibleFraction"] < 0.98 and (
                not warning_state or not warning_state.get("profit") or warning_state["profit"]["visibleFraction"] < 0.98):
            page.evaluate(EXTRACT, {"product": product, "action": "profit"})
            wait_fonts(page)
            save("profit")
        if width == VIEWPORTS[0][0] and initial["legal"] and initial["legal"]["visibleFraction"] < 0.98:
            page.evaluate(EXTRACT, {"product": product, "legalName": legal, "action": "identity"})
            wait_fonts(page)
            save("identity")
        return frames, scope
    finally:
        context.close()


def collect(name, root, executable_path=None):
    try:
        from playwright.sync_api import Error as BrowserError, TimeoutError, sync_playwright
    except ImportError:
        raise SourceError("Chromium M2 wymaga lokalnego modułu Playwright.") from None
    url, product = TARGETS[name]
    _, legal, _, home = PUBLISHERS[urlsplit(url).hostname]
    site = next(item for item in SITES if item.home == home)
    index = safe_get(home, {site.host})
    if url not in one_hop_links(site, parse_page(index).links):
        raise SourceError("Brak tej oferty w publicznej nawigacji monitorowanej domeny.")
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                executable_path=executable_path, headless=True, args=["--disable-dev-shm-usage"], timeout=15000,
            )
            try:
                frames, title, text = [], None, None
                for width, height in VIEWPORTS:
                    view_frames, scope = capture_view(browser, root, url, product, legal, width, height, TimeoutError)
                    frames.extend(view_frames)
                    if title is None:
                        title, text = scope
                version = browser.version
            finally:
                browser.close()
    except BrowserError as error:
        raise SourceError("Chromium M2 nie ukończył odczytu: " + str(error).split("\n", 1)[0][:150]) from None
    manifest = {
        "schema": SCHEMA, "url": url, "capturedAt": utc_now(), "frames": frames,
        "browser": "Chromium " + version, "title": title, "description": text,
        "discoveredFrom": home, "indexSha256": digest(index),
    }
    raw = encode(manifest)
    validated = read_bundle(root, name, "live", raw=raw)
    write_once(root / "manifests" / f"{name}.json", raw)
    return validated


def refresh_from_worker(name, root, executable_path):
    """Give the optional browser acquisition its own deadline and failure path."""
    try:
        run = subprocess.run(
            [sys.executable, "-m", "collectors.m2_browser", name, "--output", str(root), "--chromium", executable_path],
            capture_output=True, text=True, timeout=65, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise SourceError("Chromium M2 przekroczył limit czasu lub nie można go uruchomić.") from None
    if run.returncode:
        match = re.fullmatch(r"HTTP (\d{3}): (.+)", run.stderr.strip())
        error = match[2] if match else "Chromium M2 nie zakończył odczytu."
        raise SourceError(error, int(match[1]) if match else None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", choices=TARGETS)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--chromium", help="Ścieżka do lokalnej binarki Chromium")
    args = parser.parse_args()
    try:
        result, _ = collect(args.name, args.output.resolve(), args.chromium)
    except SourceError as error:
        prefix = f"HTTP {error.status}: " if error.status else ""
        parser.exit(2, prefix + str(error) + "\n")
    print(result["url"], result["observedAt"], len(result["m2Views"]), result["m2EvidenceRevision"])


if __name__ == "__main__":
    main()
