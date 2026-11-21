"""Exercise real Chromium visibility, pairing, contrast and reflow on a fictional advert."""
import argparse
from pathlib import Path
import shutil
import sys

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from collectors.m2_browser import measure

AD = """<!doctype html><html lang=pl><meta charset=utf-8><meta name=viewport content="width=device-width">
<title>Jawna kontrola M2</title>
<style>
body { font: 16px Arial; background: white; color: #161616 }
small { font-size: 11px }
summary { cursor: pointer }
.warning { font-size: 16px; color: #555 }
@media (max-width: 480px) { .warning { font-size: 8px; color: #aaa } }
.gradient { background-image: linear-gradient(white, gray) }
.cover { position: fixed; inset: 0; z-index: 1; background: white }
</style>
<header><p>Kontrakty CFD wiążą się z ryzykiem utraty środków pieniężnych.</p></header>
<main>
<section data-ad-creative>
<h1>ETF bez prowizji</h1>
<p>Potencjalny zysk z funduszu ETF można osiągnąć po wzroście wartości aktywów.</p>
<p>Zdecyduj na podstawie swojego planu inwestycyjnego, pełnej informacji o instrumencie i kosztach.</p>
<details>
<summary>Pokaż informację o ryzyku</summary>
<p class=warning>W przypadku inwestycji w fundusze ETF występuje ryzyko utraty kapitału.</p>
</details>
</section>
</main></html>"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chromium", default=shutil.which("chromium"))
    args = parser.parse_args()
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=args.chromium, args=["--disable-dev-shm-usage"])
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.set_content(AD)
            page.locator("h1").evaluate("""element => element.insertAdjacentHTML('afterend',
                '<p>ETF bez prowizji. Potencjalny zysk z CFD może być wysoki.</p>')""")
            closed = measure(page, "etf", "")
            assert closed["profit"]["text"].startswith("Potencjalny zysk z funduszu ETF")
            assert closed["warning"]["visibleFraction"] == 0
            assert closed["profitRelation"] == "same_creative"
            assert closed["rejectedWarning"]["productScope"] == ["cfd"]
            page.get_by_text("Pokaż informację o ryzyku").click()
            desktop = measure(page, "etf", "")
            assert desktop["warning"]["visibleFraction"] == 1
            assert desktop["warning"]["px"] == "16px"
            assert desktop["warning"]["contrast"] > 7
            assert desktop["warningDominant"]["px"] == "16px"

            page.set_viewport_size({"width": 390, "height": 844})
            mobile = measure(page, "etf", "")
            assert mobile["warning"]["visibleFraction"] == 1
            assert mobile["warning"]["px"] == "8px"
            assert mobile["warning"]["contrast"] < 4.5
            page.locator(".warning").evaluate("(element) => element.classList.add('gradient')")
            gradient = measure(page, "etf", "")["warning"]
            assert gradient["contrast"] is None and gradient["contrastReason"] == "złożone tło CSS"
            page.evaluate("document.body.insertAdjacentHTML('beforeend', '<div class=cover></div>')")
            covered = measure(page, "etf", "")["warning"]
            assert covered["occluded"] and covered["visibleFraction"] == 0
            print("Chromium M2 na fikcyjnej kontroli: zakres ETF/CFD, rozwinięcie, 16/8 px, kontrast, gradient, zasłonięcie OK")
        finally:
            browser.close()


if __name__ == "__main__":
    main()
