"""Render discovered M2 pages in Chromium on a desktop and a phone viewport and archive the proof.

Standalone CLI that produced data/probe-snapshots/m2/market/ (read by collectors/m2_market.py); the worker does not call it.

Usage (heavy: one Chromium at a time, closed after every page):
  /path/to/playwright-python -m collectors.m2_capture \
      --discovery data/probe-snapshots/m2/market/discovery.json \
      --output data/probe-snapshots/m2/market --runtime /abs/.runtime/m2-market

In Git: one manifest per page, a gzipped DOM block list and a JPEG of the first screen per viewport.
Outside Git (``--runtime``): the HTML response and a full-page JPEG, referenced by SHA-256.
"""
import argparse
import gzip
import json
from pathlib import Path
import re
import subprocess
import time
from urllib.parse import urlsplit

from .common import digest, utc_now
from .m2_discovery import FIRMS, MIN_DELAY, USER_AGENT, PoliteFetcher, register_row

SCHEMA = "investwatch-m2-market-1"
VIEWPORTS = (("desktop", 1440, 900), ("phone", 390, 844))
EXTRACT = Path(__file__).with_suffix(".js").read_text(encoding="utf-8")
COOKIE_TAIL = r"(\s+(pliki|plików)?\s*(cookie|cookies|ciasteczka)\w*)?\s*$"
REJECT = re.compile(r"^\s*(odrzuć( wszystkie| wszystko)?|odrzucam( wszystkie)?|tylko (niezbędne|wymagane|konieczne)|odmów|"
                    r"odrzuć opcjonalne|kontynuuj z niezbędnymi|nie zgadzam się|reject( all)?|deny|decline|only necessary)" + COOKIE_TAIL, re.I)
ACCEPT = re.compile(r"^\s*(akceptuj( wszystkie| wszystko)?|akceptuję( wszystkie)?|zaakceptuj( wszystkie| wszystko)?|zgadzam się( na wszystkie)?|"
                    r"zgoda na wszystkie|przejdź do serwisu|accept( all)?|allow all|zezwól na wszystkie|zezwalaj na wszystkie|"
                    r"ok,? rozumiem|rozumiem|wyrażam zgodę|akceptuję i (przechodzę|zamykam))" + COOKIE_TAIL, re.I)
OTHER_BROWSER = ("chrome", "chromium", "headless_shell", "chrome-headless")


def other_chromium():
    """PIDs of Chromium processes on this host (any owner process)."""
    try:
        out = subprocess.run(["pgrep", "-l", "chrom|headless_shell"], capture_output=True, text=True, check=False).stdout
    except OSError:
        return []
    return [line for line in out.splitlines() if any(name in line for name in OTHER_BROWSER)]


def wait_for_host(max_wait=900, poll=20):
    waited = 0
    while other_chromium() and waited < max_wait:
        print(f"  inny proces Chromium działa, czekam {poll}s", flush=True)
        time.sleep(poll)
        waited += poll
    if other_chromium():
        raise RuntimeError("Inny proces Chromium nie zakończył się w limicie oczekiwania.")


def page_id(firm, url):
    path = urlsplit(url).path.strip("/").replace("/", "-")
    path = re.sub(r"\.html?$", "", path)
    path = re.sub(r"[^a-z0-9-]+", "-", path.lower()).strip("-")[:60] or "home"
    return f"{firm}-{path}"


def save(root, data, ext):
    sha = digest(data)
    path = root / f"{sha}.{ext}"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(data)
    return sha


def dismiss_consent(page):
    """Click only a standard accept/reject button of a consent banner; nothing else is touched."""
    for (pattern, action), kind in ((p, k) for p in ((REJECT, "reject"), (ACCEPT, "accept")) for k in ("button", "link")):
        try:
            buttons = page.get_by_role(kind, name=pattern)
            for index in range(min(buttons.count(), 4)):
                button = buttons.nth(index)
                if button.is_visible():
                    button.click(timeout=2500)
                    page.wait_for_timeout(700)
                    return action
        except Exception:  # noqa: BLE001 - a banner that does not cooperate stays and is recorded
            continue
    return None


def consent_visible(page):
    return page.evaluate("""() => [...document.querySelectorAll(
        '[role=dialog],dialog,#CybotCookiebotDialog,#onetrust-banner-sdk,[id*=cookie i],[class*=cookie-banner i],[class*=consent i]')]
        .some(e => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e);
          return r.width > 40 && r.height > 40 && s.display !== 'none' && s.visibility !== 'hidden' &&
                 /cookie|ciastecz|zgod|prywatno/i.test(e.textContent || ''); })""")


def warm_lazy_content(page):
    page.evaluate("""async () => {
        const step = Math.max(300, innerHeight * 0.9);
        for (let y = 0, i = 0; y < document.documentElement.scrollHeight && i < 30; y += step, i++) {
            scrollTo(0, y); await new Promise(r => setTimeout(r, 120));
        }
        scrollTo(0, 0); await new Promise(r => setTimeout(r, 400));
    }""")


def capture_view(browser, url, hosts, label, width, height, git_root, runtime):
    context = browser.new_context(
        viewport={"width": width, "height": height}, device_scale_factor=1, locale="pl-PL",
        is_mobile=width <= 400, has_touch=width <= 400, reduced_motion="reduce", service_workers="block",
        accept_downloads=False, user_agent=None,
    )
    context.set_default_timeout(6000)
    requests = {"n": 0}

    def route(r):
        requests["n"] += 1
        kind = r.request.resource_type
        if requests["n"] > 700 or kind in {"media", "websocket", "eventsource"} or r.request.method not in {"GET", "HEAD", "POST"}:
            return r.abort()
        return r.continue_()

    page = context.new_page()
    try:
        context.route("**/*", route)
        response = page.goto(url, wait_until="domcontentloaded", timeout=30000)
        status = response.status if response else None
        final = page.url
        if status != 200 or urlsplit(final).hostname not in hosts:
            raise RuntimeError(f"HTTP {status} lub przekierowanie poza domenę ({final})")
        body = response.body()
        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:  # noqa: BLE001
            pass
        page.wait_for_timeout(800)
        overlay_before = consent_visible(page)
        before_jpg = page.screenshot(type="jpeg", quality=55, timeout=8000)
        action = dismiss_consent(page) if overlay_before else None
        warm_lazy_content(page)
        page.evaluate("() => document.fonts.ready")
        dom = page.evaluate(EXTRACT, {})
        dom.update(url=url, finalUrl=final, viewport=label, consent={"overlayBefore": overlay_before, "action": action,
                                                                      "overlayAfter": consent_visible(page)})
        top_jpg = page.screenshot(type="jpeg", quality=55, timeout=8000)
        full_jpg = page.screenshot(type="jpeg", quality=40, full_page=True, timeout=15000) if runtime else None
        view = {
            "viewport": label, "width": width, "height": height, "httpStatus": status,
            "screenshot": save(git_root / "assets", top_jpg, "jpg") + ".jpg",
            "screenshotBeforeConsent": save(git_root / "assets", before_jpg, "jpg") + ".jpg" if overlay_before else None,
            "dom": save(git_root / "assets", gzip.compress(json.dumps(dom, ensure_ascii=False, separators=(",", ":")).encode(), mtime=0), "json.gz") + ".json.gz",
            "fullPage": save(runtime / "assets", full_jpg, "jpg") + ".jpg" if full_jpg else None,
            "consent": dom["consent"], "docHeight": dom["docHeight"], "scrollWidth": dom["scrollWidth"],
            "blocks": len(dom["blocks"]), "requests": requests["n"],
        }
        return view, body, final, dom
    finally:
        context.close()


def capture_page(item, firm, fetcher, git_root, runtime, chromium=None):
    from playwright.sync_api import sync_playwright

    url, hosts = item["url"], set(firm.domains)
    if not fetcher.allowed(url, hosts):
        raise RuntimeError("robots.txt nie pozwala na odczyt tej strony")
    views, html, final, title, lang = [], None, url, None, None
    for label, width, height in VIEWPORTS:
        wait_for_host()
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=chromium, headless=True,
                                                 args=["--disable-dev-shm-usage"], timeout=30000)
            try:
                version = browser.version
                view, body, final, dom = capture_view(browser, url, hosts, label, width, height, git_root, runtime)
            finally:
                browser.close()
        views.append(view)
        html = html or body
        title, lang = title or dom["title"], lang or dom["lang"]
        time.sleep(MIN_DELAY + 0.5)
    html_sha = digest(html)
    if runtime:
        save(runtime / "html", gzip.compress(html, mtime=0), "html.gz")
    return {
        "schema": SCHEMA, "id": page_id(firm.key, url), "kind": item["kind"], "url": url, "finalUrl": final,
        "firm": {"key": firm.key, "brand": firm.brand, "home": firm.home, **register_row(firm)},
        "discovery": {k: item.get(k) for k in ("from", "anchor", "score", "reasons")},
        "capturedAt": utc_now(), "browser": "Chromium " + version, "userAgent": "Playwright Chromium (domyślny)",
        "robotsAgent": USER_AGENT, "htmlSha256": html_sha, "htmlBytes": len(html),
        "htmlStored": "runtime" if runtime else "not_stored", "title": title, "lang": lang, "views": views,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--discovery", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runtime", type=Path)
    parser.add_argument("--chromium")
    parser.add_argument("--only", action="append", help="tylko te ID stron")
    parser.add_argument("--extra", action="append", default=[], help="firm=url już zarchiwizowanego materiału M2")
    parser.add_argument("--max-pages", type=int, default=25)
    args = parser.parse_args()
    plan = json.loads(args.discovery.read_text(encoding="utf-8"))
    firms = {firm.key: firm for firm in FIRMS}
    items = [(firms[rec["firm"]], page) for rec in plan["firms"] for page in rec["pages"]]
    for extra in args.extra:
        key, url = extra.split("=", 1)
        items.append((firms[key], {"url": url, "kind": "archive", "from": "data/probe-snapshots/m2 (TARGETS)",
                                   "anchor": None, "score": None, "reasons": ["materiał z wcześniejszego archiwum M2"]}))
    fetcher = PoliteFetcher()
    done = 0
    for firm, item in items:
        pid = page_id(firm.key, item["url"])
        if args.only and pid not in args.only:
            continue
        target = args.output / "manifests" / f"{pid}.json"
        if target.exists() and not args.only:
            print("pomijam (jest)", pid, flush=True)
            continue
        if done >= args.max_pages:
            break
        print("Chromium:", pid, item["url"], flush=True)
        try:
            manifest = capture_page(item, firm, fetcher, args.output, args.runtime, args.chromium)
        except Exception as error:  # noqa: BLE001 - every failure is recorded with its reason
            failure = {"id": pid, "url": item["url"], "firm": firm.key, "error": str(error).split("\n")[0][:300], "at": utc_now()}
            print("  BŁĄD", failure["error"], flush=True)
            log = args.output / "failures.jsonl"
            log.parent.mkdir(parents=True, exist_ok=True)
            with log.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(failure, ensure_ascii=False) + "\n")
            time.sleep(MIN_DELAY)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        done += 1
        print("  ok", [(v["viewport"], v["blocks"], v["consent"]["action"]) for v in manifest["views"]], flush=True)


if __name__ == "__main__":
    main()
