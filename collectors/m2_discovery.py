"""Discover offer and landing pages of registered investment firms, starting from the home page.

Usage: python -m collectors.m2_discovery --output data/probe-snapshots/m2/market/discovery.json

Firms come from the dated KNF register copies (domy maklerskie, banki prowadzące działalność
maklerską, oddziały zagranicznych firm inwestycyjnych). For each firm only the home page is
configured; offer pages are chosen from its links (optionally through one investment hub page)
by a transparent score over the address and the anchor text. robots.txt is honoured and
requests to one host are spaced by at least MIN_DELAY seconds.
"""
import argparse
from dataclasses import dataclass, field
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.robotparser import RobotFileParser

from .common import SourceError, digest, public_link, utc_now

ROOT = Path(__file__).resolve().parents[1]
KNF = ROOT / "data" / "probe-snapshots" / "knf"
USER_AGENT = "InvestWatch-M2/1.0 (prototyp badawczy UKNF hackathon)"
MIN_DELAY = 3.0
MAX_BODY = 3 * 1024 * 1024
MIN_SCORE = 4
ENTITY_TYPES = {
    "knf_domy_maklerskie.json": ("domestic_investment_firm", "dom maklerski"),
    "knf_banki_maklerskie.json": ("domestic_bank", "bank prowadzący działalność maklerską"),
    "knf_oddzialy_zagr_FI.json": ("foreign_investment_firm_branch", "oddział zagranicznej firmy inwestycyjnej"),
}


@dataclass(frozen=True)
class Firm:
    key: str
    register: str
    registry_id: int
    home: str
    domains: tuple
    brand: str
    hub_hint: str = ""          # extra words that mark the investment section of a universal bank
    limit: int = 2              # offer pages taken from this firm
    education: bool = False     # also keep one education page as a negative control


# Only the home page is configured. Every offer URL is found by following links.
FIRMS = (
    Firm("xtb", "knf_domy_maklerskie.json", 6884980, "https://www.xtb.com/pl", ("www.xtb.com",), "XTB", limit=3, education=True),
    Firm("bossa", "knf_domy_maklerskie.json", 8353437, "https://bossa.pl/", ("bossa.pl",), "DM BOŚ (bossa)", hub_hint="oferta"),
    Firm("bdm", "knf_domy_maklerskie.json", 6884964, "https://www.bdm.pl/", ("www.bdm.pl",), "Dom Maklerski BDM"),
    Firm("noble", "knf_domy_maklerskie.json", 6884971, "https://noblesecurities.pl/", ("noblesecurities.pl",), "Noble Securities"),
    Firm("tms", "knf_domy_maklerskie.json", 6884972, "https://www.tms.pl/", ("www.tms.pl",), "OANDA TMS Brokers"),
    Firm("pekao", "knf_banki_maklerskie.json", 7976968, "https://www.pekao.com.pl/", ("www.pekao.com.pl",), "Bank Pekao",
         hub_hint="inwestycje|makler"),
    Firm("ing", "knf_banki_maklerskie.json", 8387348, "https://www.ing.pl/", ("www.ing.pl",), "ING Bank Śląski",
         hub_hint="inwestycje|makler"),
    Firm("millennium", "knf_banki_maklerskie.json", 7410389, "https://www.bankmillennium.pl/", ("www.bankmillennium.pl",),
         "Bank Millennium", hub_hint="inwestycje|makler"),
    Firm("lynx", "knf_oddzialy_zagr_FI.json", 9328617, "https://www.lynxbroker.pl/", ("www.lynxbroker.pl",), "LYNX"),
    Firm("finax", "knf_oddzialy_zagr_FI.json", 8510435, "https://www.finax.eu/pl", ("www.finax.eu",), "Finax", education=True),
    Firm("cmc", "knf_oddzialy_zagr_FI.json", 9378948, "https://www.cmcmarkets.com/pl-pl/", ("www.cmcmarkets.com",), "CMC Markets"),
)

OFFER_WORDS = {  # address or anchor word → weight
    r"etf": 5, r"akcj": 5, r"obligacj": 5, r"fundusz": 4, r"\bike\b|\bikze\b|emerytaln": 5, r"cfd": 5,
    r"forex|waluty": 4, r"kryptowalut": 4, r"surowc": 3, r"opcj": 3, r"kontrakt": 3, r"plan\w*.inwest": 5,
    r"rachun\w*.(?:inwest|makler)|konto.(?:inwest|makler)": 5, r"robo|portfel": 4, r"lokat\w*.inwest": 2,
    r"oferta|produkt|instrument": 2, r"inwestuj|inwestowani": 2, r"promocj": 3, r"trading|platform": 2,
    r"odsetk|oprocentowan": 3, r"dywidend": 3,
}
NEGATIVE_WORDS = (
    r"blog|aktualno|news|wiadomo|kariera|praca|kontakt|pomoc|faq|regulamin|dokument|polityk|cookie|login|logow|"
    r"zaloguj|rejestr|o-nas|o_nas|about|relacje|investor|analiz|rekomendac|notowan|kalendarz|webinar|kredyt|"
    r"hipote|karta|kart-|leasing|ubezpiecz|firm[ay]|biznes|korporac|private|prasa|media|tabela|oplat|cennik|"
    r"opłat|przedsiebior|bezpieczen|placowk|oddzial|bankomat|kurs|wykres|app|aplikacj|pobierz|download|\.pdf|mailto|tel:|"
    r"edukac|akadem|poradnik|slownik|baza-wiedzy|wiedza|szkoleni|platforma-demo|demo|partner|affiliate|"
    r"\bkid\b|kiid|warunki|logowanie|likwidac"
)
EDUCATION = r"edukac|akadem|poradnik|slownik|słownik|baza-wiedzy|wiedza|kurs-|szkoleni|learn|lekcj"


class Anchors(HTMLParser):
    """Collect (href, visible anchor text) without executing anything."""

    skip = {"script", "style", "noscript", "template", "svg"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links, self.stack, self.ignored = [], [], 0
        self.title, self.in_title = [], False

    def handle_starttag(self, tag, attrs):
        if tag in self.skip:
            self.ignored += 1
        if tag == "title":
            self.in_title = True
        if tag == "a":
            attrs = dict(attrs)
            self.stack.append([attrs.get("href") or "", [attrs.get("aria-label") or attrs.get("title") or ""]])

    def handle_endtag(self, tag):
        if tag in self.skip and self.ignored:
            self.ignored -= 1
        if tag == "title":
            self.in_title = False
        if tag == "a" and self.stack:
            href, text = self.stack.pop()
            self.links.append((href, " ".join(" ".join(text).split())[:160]))

    def handle_data(self, data):
        if self.in_title:
            self.title.append(data)
        if not self.ignored and self.stack:
            self.stack[-1][1].append(data)


def anchors(body):
    parser = Anchors()
    parser.feed(body.decode("utf-8", errors="replace"))
    parser.close()
    return parser.links, " ".join("".join(parser.title).split())[:300]


def canonical(base, href, hosts):
    """Absolute https URL on an allowed host, without query and fragment; None otherwise."""
    try:
        url = urljoin(base, href.strip())
        if not public_link(url):
            return None
        parts = urlsplit(url)
    except ValueError:
        return None
    if parts.hostname not in hosts:
        return None
    path = re.sub(r"/{2,}", "/", parts.path) or "/"
    return urlunsplit(("https", parts.hostname, path, "", ""))


def locale_prefix(url):
    """'/pl', '/ie/pl' or '/pl-pl' when the home page lives under a language path, else ''."""
    match = re.match(r"^(/(?:[a-z]{2}/)?[a-z]{2}(?:-[a-z]{2})?)(?:/|$)", urlsplit(url).path.lower())
    return match.group(1) if match else ""


def offer_score(url, text, home):
    """Return (score, reasons) for one link. Positive words come from the address and the anchor."""
    path = urlsplit(url).path.lower()
    if url.rstrip("/") == home.rstrip("/") or path.count("/") > 5:
        return 0, ["strona główna lub zbyt głęboko"]
    haystack = path + " " + text.lower()
    if re.search(NEGATIVE_WORDS, haystack):
        return 0, ["sekcja poza ofertą"]
    reasons, score = [], 0
    for pattern, weight in OFFER_WORDS.items():
        if re.search(pattern, haystack):
            score += weight
            reasons.append(pattern.split("|")[0].strip("\\b").replace("\\w*", "").replace(".", " "))
    return score, reasons


def product_family(url):
    """Two pages of one firm should promote different things: the first offer word in the address."""
    path = urlsplit(url).path.lower()
    return next((pattern for pattern in OFFER_WORDS if re.search(pattern, path)), url)


def rank_links(links, base, firm, *, exclude=(), prefix=""):
    best = {}
    for href, text in links:
        url = canonical(base, href, firm.domains)
        if not url or url in exclude or not urlsplit(url).path.lower().startswith(prefix):
            continue
        score, reasons = offer_score(url, text, firm.home)
        if score >= MIN_SCORE and (url not in best or best[url]["score"] < score):
            best[url] = {"url": url, "anchor": text, "score": score, "reasons": reasons, "from": base}
    # Prefer distinct offers: one URL per last path segment family.
    ranked = sorted(best.values(), key=lambda item: (-item["score"], len(item["url"]), item["url"]))
    return ranked


def hub_links(links, base, firm):
    if not firm.hub_hint:
        return []
    found = []
    for href, text in links:
        url = canonical(base, href, firm.domains)
        if url and url.rstrip("/") != base.rstrip("/") and re.search(firm.hub_hint, (urlsplit(url).path + " " + text).lower()):
            if not re.search(r"blog|kontakt|pomoc|aktualno|dokument|regulamin|login|\.pdf|private|premium|korporac|firm|przedsiebior|relacje", url.lower()):
                found.append((len(urlsplit(url).path), url, text))
    return [url for _, url, _ in sorted(set(found))][:1]


def education_links(links, base, firm):
    for href, text in links:
        url = canonical(base, href, firm.domains)
        if url and url.rstrip("/") != base.rstrip("/") and re.search(EDUCATION, urlsplit(url).path.lower()):
            if not re.search(r"\.pdf|login|webinar|kalendarz", url.lower()):
                return {"url": url, "anchor": text, "score": 0, "reasons": ["strona edukacyjna (kontrola)"], "from": base}
    return None


class NoForeignRedirect(HTTPRedirectHandler):
    def __init__(self, hosts):
        self.hosts = hosts

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlsplit(newurl).hostname not in self.hosts or not public_link(newurl):
            raise SourceError(f"Przekierowanie poza domenę firmy ({urlsplit(newurl).hostname}).")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class PoliteFetcher:
    """GET with robots.txt, a per-host delay and redirects kept inside the firm's hosts."""

    def __init__(self, delay=MIN_DELAY, sleep=time.sleep, clock=time.monotonic):
        self.delay, self.sleep, self.clock = delay, sleep, clock
        self.last, self.robots = {}, {}

    def _wait(self, host):
        gap = self.clock() - self.last.get(host, -1e9)
        if gap < self.delay:
            self.sleep(self.delay - gap)
        self.last[host] = self.clock()

    def _open(self, url, hosts):
        self._wait(urlsplit(url).hostname)
        request = Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "pl-PL,pl;q=0.9"})
        try:
            with build_opener(NoForeignRedirect(hosts)).open(request, timeout=20) as response:
                body = response.read(MAX_BODY + 1)
                if len(body) > MAX_BODY:
                    raise SourceError("Przekroczony limit wielkości odpowiedzi.")
                return response.geturl(), response.status, response.headers.get("content-type", ""), body
        except HTTPError as error:
            raise SourceError(f"HTTP {error.code}", error.code) from None
        except (URLError, OSError) as error:
            raise SourceError(f"Błąd połączenia: {error}") from None

    def allowed(self, url, hosts):
        host = urlsplit(url).hostname
        if host not in self.robots:
            parser = RobotFileParser()
            try:
                _, _, _, body = self._open(f"https://{host}/robots.txt", hosts)
                parser.parse(body.decode("utf-8", "replace").splitlines())
            except SourceError as error:
                if error.status in (401, 403):
                    parser.disallow_all = True
                else:
                    parser.allow_all = True  # no robots.txt: the convention is full access
            self.robots[host] = parser
        return self.robots[host].can_fetch(USER_AGENT, url)

    def get(self, url, hosts):
        if not self.allowed(url, hosts):
            raise SourceError("robots.txt nie pozwala na odczyt tej strony.")
        final, status, kind, body = self._open(url, hosts)
        if status != 200 or "html" not in kind:
            raise SourceError(f"Odpowiedź nie jest stroną HTML ({status}, {kind}).", status)
        return final, body


def register_row(firm):
    rows = json.loads((KNF / firm.register).read_text(encoding="utf-8"))
    row = next((r for r in rows if r["id"] == firm.registry_id), None)
    if row is None:
        raise SourceError(f"Brak wpisu {firm.registry_id} w {firm.register}.")
    name = re.sub(r"<strike>.*?</strike>", " ", row["name"], flags=re.S | re.I)
    lines = [" ".join(re.sub(r"<[^>]+>", " ", part).split()) for part in re.split(r"<br\s*/?>", name, flags=re.I)]
    entity_type, label = ENTITY_TYPES[firm.register]
    return {
        "registryId": row["id"], "name": lines[0], "unit": next((x for x in lines[1:] if x), None),
        "category": row.get("subcategoryName"), "entityType": entity_type, "entityLabel": label,
        "sourceFile": "data/probe-snapshots/knf/" + firm.register, "checkedAt": "2026-11-21",
    }


def discover_firm(firm, fetcher, clock=utc_now):
    record = {"firm": firm.key, "brand": firm.brand, "home": firm.home, "register": register_row(firm),
              "observedAt": clock(), "pages": [], "errors": []}
    try:
        base, body = fetcher.get(firm.home, set(firm.domains))
    except SourceError as error:
        record["errors"].append({"url": firm.home, "error": str(error)})
        return record
    record["homeFinal"], record["homeSha256"] = base, digest(body)
    links, _ = anchors(body)
    prefix = locale_prefix(base)
    ranked = rank_links(links, base, firm, prefix=prefix)
    hubs = []
    # A universal bank: offers are taken from its investment section (one more link), the home page is a fallback.
    if firm.hub_hint or not ranked or ranked[0]["score"] < 5:
        for hub in hub_links(links, base, firm):
            try:
                hub_final, hub_body = fetcher.get(hub, set(firm.domains))
            except SourceError as error:
                record["errors"].append({"url": hub, "error": str(error)})
                continue
            hubs.append({"url": hub_final, "sha256": digest(hub_body)})
            hub_ranked = rank_links(anchors(hub_body)[0], hub_final, firm, exclude={base}, prefix=prefix)
            if hub_ranked:
                ranked = hub_ranked + [item for item in ranked if item["url"] not in {x["url"] for x in hub_ranked}]
    record["hubs"] = hubs
    chosen, families = [], set()
    for item in ranked:
        family = product_family(item["url"])
        if family in families or not fetcher.allowed(item["url"], set(firm.domains)):
            continue
        families.add(family)
        chosen.append({**item, "kind": "offer"})
        if len(chosen) == firm.limit:
            break
    if firm.education:
        control = education_links(links, base, firm)
        if control and fetcher.allowed(control["url"], set(firm.domains)):
            chosen.append({**control, "kind": "education"})
    record["candidates"] = len(ranked)
    record["pages"] = chosen
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--firm", action="append", help="tylko wskazane klucze firm")
    args = parser.parse_args()
    fetcher = PoliteFetcher()
    records = []
    for firm in FIRMS:
        if args.firm and firm.key not in args.firm:
            continue
        record = discover_firm(firm, fetcher)
        records.append(record)
        print(firm.key, [(p["kind"], p["url"], p["score"]) for p in record["pages"]], record["errors"], flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"schema": "investwatch-m2-discovery-1", "generatedAt": utc_now(),
                                       "userAgent": USER_AGENT, "minDelaySec": MIN_DELAY, "firms": records},
                                      ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
