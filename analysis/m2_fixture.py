"""Small builders of synthetic M2 pages for tests (no browser, no network)."""


def block(text, *, y=100, px=16, role="body", sec=1, h=None, hid=None, fix=None, cr=12.0, first=None, height=24,
          trunc=None, tag=None, occ=False, lang="pl", hint=None, x=40, w=600):
    first_screen = (1.0 if y + height <= 900 else 0.0) if first is None else first
    return {"t": text, "n": len(text), "tag": tag or (f"h{h}" if h else "p"), "h": h, "px": px, "fw": 400,
            "sizes": {px: len(text)}, "bbox": None if hid else [x, y, w, height], "first": 0 if hid else first_screen,
            "occ": occ, "hid": hid, "role": role, "sec": sec, "fix": fix, "cr": cr, "crw": None, "trunc": trunc,
            "lang": lang, "href": None, "hint": hint or []}


def view(name, blocks, *, width=None, height=None, doc_height=3000, scroll_width=None, risk_links=None):
    width = width or (1440 if name == "desktop" else 390)
    height = height or (900 if name == "desktop" else 844)
    return {"viewport": name, "width": width, "height": height, "docHeight": doc_height,
            "scrollWidth": scroll_width or width, "consent": {}, "riskLinks": risk_links or [], "blocks": blocks,
            "screenshotUrl": f"/evidence/m2/market/{name}.jpg", "domUrl": f"/evidence/m2/market/{name}.json.gz"}


def material(desktop, phone=None, *, url="https://www.example-dm.pl/etf", name="EXAMPLE DOM MAKLERSKI S.A.",
             kind="offer", title="ETF"):
    views = {"desktop": view("desktop", desktop)}
    if phone is not False:
        views["phone"] = view("phone", phone if phone is not None else desktop)
    return {"firm": {"name": name, "brand": "Example", "registryId": 1, "entityType": "domestic_investment_firm",
                     "entityLabel": "dom maklerski"}, "url": url, "title": title, "observedAt": "2026-11-21T20:00:00+00:00",
            "kind": kind, "views": views}


FOOTER_NAME = block("EXAMPLE DOM MAKLERSKI S.A. z siedzibą w Warszawie, nadzorowany przez KNF.", y=2900, px=12, role="footer", sec=9)
