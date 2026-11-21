"""Discover selected public investment offers one link from an approved home page."""

from dataclasses import dataclass
from html.parser import HTMLParser
import re
from urllib.parse import urljoin, urlsplit, urlunsplit

from .common import SourceError, capture, digest, public_link, source_result, utc_now


@dataclass(frozen=True)
class Site:
    home: str
    brand: str
    module: str
    path_pattern: str
    index_path: str = ""
    source_suffix: str = ""

    @property
    def host(self):
        return urlsplit(self.home).hostname

    @property
    def key(self):
        return f"www:{self.host}{self.source_suffix}"

    @property
    def creator(self):
        return {
            "id": self.key, "name": self.brand, "platform": "web", "url": self.home,
            "discoveredVia": "Domena na liście monitorowanej", "isSeed": True,
        }


SITES = (
    Site("https://www.xtb.com/pl", "XTB", "M2", r"/pl/(?:etf|akcje|plany-inwestycyjne)"),
    Site("https://www.bdm.pl/", "Dom Maklerski BDM", "M2", r"/rachunek-(?:inwestycyjny|emerytalny)"),
    Site("https://bossa.pl/", "DM BOŚ", "M3", r"/oferta/doradztwo", "/oferta"),
    Site("https://bossa.pl/edukacja", "DM BOŚ · edukacja", "M3", r"/edukacja/rynek-i-inwestycje/instrumenty-finansowe", source_suffix=":edukacja"),
    Site("https://financewell.pl/", "FinanceWell", "M3", r"/(?:o-nas|oferta|uslugi|doradztwo-inwestycyjne)"),
)


class Page(HTMLParser):
    breaks = {"title", "br", "div", "main", "section", "article", "p", "li", "h1", "h2", "h3", "dt", "dd"}
    excluded = {"script", "style", "svg", "noscript", "template", "nav", "header", "footer"}

    def __init__(self, include_footer=False):
        super().__init__()
        self.links = []
        self.parts = []
        self.title = []
        self.in_title = False
        self.ignored = []
        self.excluded = self.excluded - {"footer"} if include_footer else self.excluded

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)
        if tag in self.excluded:
            self.ignored.append(tag)
        if tag == "title":
            self.in_title = True
        if tag in self.breaks and not self.ignored:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if self.ignored and self.ignored[-1] == tag:
            self.ignored.pop()
        if tag == "title":
            self.in_title = False
        if tag in self.breaks and not self.ignored:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.ignored:
            self.parts.append(data)
        if self.in_title:
            self.title.append(data)

    def text(self):
        lines = (" ".join(line.split()) for line in "".join(self.parts).splitlines())
        return "\n".join(line for line in lines if line)


def parse_page(body, include_footer=False):
    parser = Page(include_footer=include_footer)
    parser.feed(body.decode("utf-8", errors="replace"))
    parser.close()
    return parser


def one_hop_links(site, links):
    candidates = {}
    for href in links:
        try:
            candidate = urljoin(site.home, href)
            if not public_link(candidate):
                continue
            parts = urlsplit(candidate)
        except ValueError:
            continue
        path = parts.path.rstrip("/")
        if parts.hostname == site.host and re.fullmatch(site.path_pattern, path):
            url = urlunsplit(("https", site.host, parts.path, "", ""))
            candidates.setdefault(path, url)
    return list(candidates.values())


def read_site(site, fetch, clock=utc_now):
    scope = "Tekst HTML strony firmy · " + ("przez wskazany indeks oferty" if site.index_path else "jeden poziom od strony głównej")
    try:
        home = fetch(site.home, {site.host})
        index_url = site.home
        index = home
        if site.index_path:
            index_url = urljoin(site.home, site.index_path)
            permitted = Site(site.home, site.brand, site.module, re.escape(site.index_path))
            if index_url not in one_hop_links(permitted, parse_page(home).links):
                return [], source_result(site.key, site.brand, site.home, clock(), count=0, scope=scope)
            index = fetch(index_url, {site.host})
        links = one_hop_links(site, parse_page(index).links)
    except SourceError as error:
        return [], source_result(site.key, site.brand, site.home, clock(), error=error, scope=scope)

    captures, failures = [], []
    for url in links[:1]:
        try:
            body = fetch(url, {site.host})
            page = parse_page(body)
            description = page.text()
            if len(description) < 60:
                raise SourceError("Strona nie zwróciła tekstu oferty.")
        except SourceError as error:
            failures.append(error)
            continue
        output = capture(
            f"web:{site.host}{urlsplit(url).path.rstrip('/')}", site.creator,
            " ".join("".join(page.title).split())[:300] or site.brand, url, description,
            observed_at=clock(), source_url=url, response_hash=digest(body), scope="public_html_text",
            module=site.module, brand=site.brand,
        )
        output["provenance"].update(discoveredFrom=site.home, indexSha256=digest(home))
        if site.index_path:
            output["provenance"].update(indexUrl=index_url, offerIndexSha256=digest(index))
        if site.module == "M3":
            # Preserve only the compact identity statement, not contact details.
            full = parse_page(body, include_footer=True).text()
            identity = re.search(r"(?P<name>Dom Maklerski Banku Ochrony Środowiska Spółka Akcyjna)[^\n]{0,400}?(?P<krs>KRS[^\n]{0,50}?\b\d{10}\b)[^\n]{0,150}?(?P<nip>NIP\s*[\d-]+)", full, re.I)
            if identity:
                output["identityEvidence"] = {key: identity.group(key) for key in ("name", "krs", "nip")}
                output["identityEvidence"]["krsCandidates"] = re.findall(r"\bKRS\b[^\n\d]{0,50}(\d{10})\b", full, re.I)
                output["identityEvidence"].update(url=url, observedAt=output["observedAt"])
        captures.append(output)
    status = source_result(
        site.key, site.brand, site.home, clock(), count=len(captures),
        raw_count=len(links), error=failures[0] if failures else None, scope=scope,
    )
    return captures, status


# --- M3: prospective discovery of advisory offers ------------------------------------------------
# Seeds come from public catalogues and recorded search results (collectors/catalogs.py). For each
# firm domain the crawler reads robots.txt, the home page and the best offer page(s), with at least
# three seconds between requests and a hard request budget for the whole run. No browser is used.

import json as _json
from pathlib import Path as _Path
import time as _time
from urllib import robotparser as _robotparser
from urllib.error import HTTPError as _HTTPError, URLError as _URLError
from urllib.request import HTTPRedirectHandler as _RedirectHandler, Request as _Request, build_opener as _build_opener

M3_AGENT = "InvestWatch-SourceMonitor/1.0"
M3_INTERVAL = 3.0
M3_BUDGET = 150
M3_MAX_BYTES = 2 * 1024 * 1024
M3_OFFER_WORDS = (
    (r"doradztw|doradca|advis", 6), (r"wealth|majat|majątk|family", 5), (r"ofert|uslug|usług|services?", 5),
    (r"portfel|portfolio|zarzadz|zarządz", 4), (r"cennik|pakiet|abonament|subskryp|premium|sygna|alert", 4),
    (r"inwest|invest|fundusz|akcj|obligac", 3), (r"konsultac|wspolprac|współprac|jak-dzialamy", 2),
)
M3_SKIP = re.compile(r"(?:blog|artykul|aktualnosc|news|polityka|privacy|cookies|regulamin|rodo|login|logowanie|koszyk|cart|"
                     r"\.pdf$|\.jpe?g$|\.png$|wp-content|tag/|category/|kategoria|autor|author|/feed|/en(?:/|$)|/de(?:/|$))", re.I)


class _NoFollow(_RedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


def site_key(host):
    host = (host or "").lower()
    return host[4:] if host.startswith("www.") else host


class PoliteFetcher:
    """HTTP GET with a shared budget, a minimum interval, robots.txt and same-site redirects only."""

    def __init__(self, budget=M3_BUDGET, interval=M3_INTERVAL, sleep=_time.sleep, opener=None, clock=_time.monotonic, now=utc_now):
        self.budget, self.interval, self.sleep, self.clock, self.now = budget, interval, sleep, clock, now
        self.opener = opener or _build_opener(_NoFollow)
        self.log, self.robots, self._last = [], {}, None

    @property
    def used(self):
        return len(self.log)

    def _raw(self, url):
        if self.used >= self.budget:
            raise SourceError("Wyczerpany budżet żądań.")
        if self._last is not None:
            wait = self.interval - (self.clock() - self._last)
            if wait > 0:
                self.sleep(wait)
        self._last = self.clock()
        entry = {"url": url, "at": self.now()}
        self.log.append(entry)
        request = _Request(url, headers={"User-Agent": M3_AGENT, "Accept-Language": "pl,en;q=0.5"})
        try:
            with self.opener.open(request, timeout=12) as response:
                body = response.read(M3_MAX_BYTES + 1)
                entry["status"] = response.status
                if len(body) > M3_MAX_BYTES:
                    raise SourceError("Przekroczony limit wielkości odpowiedzi.")
                return response.status, dict(response.headers), body
        except _HTTPError as error:
            entry["status"] = error.code
            with error:
                return error.code, dict(error.headers or {}), b""
        except (_URLError, OSError, ValueError):
            entry["status"] = "error"
            raise SourceError("Błąd połączenia ze źródłem.") from None

    def get(self, url, hops=3):
        """Return (final_url, body). Redirects are followed only within the same site."""
        start = urlsplit(url).hostname
        for _ in range(hops + 1):
            status, headers, body = self._raw(url)
            if status in (301, 302, 303, 307, 308):
                location = headers.get("Location") or headers.get("location") or ""
                parts = urlsplit(urljoin(url, location))
                if parts.scheme not in ("https", "http") or site_key(parts.hostname) != site_key(start):
                    raise SourceError("Przekierowanie poza witrynę.", status)
                url = urlunsplit(("https", parts.hostname, parts.path or "/", parts.query, ""))
                continue
            if status != 200:
                raise SourceError(f"HTTP {status}", status)
            return url, body
        raise SourceError("Zbyt wiele przekierowań.")

    def allowed(self, url):
        host = urlsplit(url).hostname
        key = site_key(host)
        if key not in self.robots:
            parser = _robotparser.RobotFileParser()
            try:
                _, body = self.get(f"https://{host}/robots.txt", hops=2)
                parser.parse(body.decode("utf-8", errors="replace").splitlines())
                self.robots[key] = ("ok", parser)
            except SourceError as error:
                # A 4xx answer means there is no robots.txt; a connection error stops the site.
                if isinstance(error.status, int) and 400 <= error.status < 500:
                    parser.parse([])
                    self.robots[key] = ("absent", parser)
                else:
                    self.robots[key] = ("error", None)
        _, parser = self.robots[key]
        return parser is not None and parser.can_fetch(M3_AGENT, url)


def page_record(url, body, observed_at):
    parsed = parse_page(body)
    text = parsed.text()
    full = parse_page(body, include_footer=True).text()
    # The footer (operator name, NIP, KRS) is kept apart from the offer text for the identity step.
    extra = "\n".join(line for line in full.split("\n") if line not in set(text.split("\n")))
    return {"url": url, "observedAt": observed_at, "sha256": digest(body), "bytes": len(body),
            "title": " ".join("".join(parsed.title).split())[:300], "text": text[:60_000], "textSha256": digest(text[:60_000]),
            "identityText": extra[-6000:]}, parsed.links


def offer_links(home_url, links, limit=2):
    """Rank same-site links whose path points to an offer, a service or a price list."""
    scored = {}
    host = site_key(urlsplit(home_url).hostname)
    for href in links:
        try:
            parts = urlsplit(urljoin(home_url, href))
        except ValueError:
            continue
        if parts.scheme not in ("http", "https") or site_key(parts.hostname) != host:
            continue
        path = parts.path.rstrip("/")
        if not path or M3_SKIP.search(path) or path.count("/") > 3:
            continue
        score = sum(weight for pattern, weight in M3_OFFER_WORDS if re.search(pattern, path, re.I))
        if score:
            url = urlunsplit(("https", parts.hostname, parts.path, "", ""))
            scored[url] = max(scored.get(url, 0), score - path.count("/"))
    return [url for url, _ in sorted(scored.items(), key=lambda item: (-item[1], len(item[0])))][:limit]


def read_m3_firm(seed, fetcher, clock=utc_now, subpages=1):
    """Fetch the home page and the best offer page(s) of one discovered firm domain."""
    home = seed["url"]
    domain = site_key(urlsplit(home).hostname)
    entity = {"id": f"m3:{domain}", "domain": domain, "label": seed.get("label"),
              "discoveredVia": seed.get("discoveredVia"), "seed": seed, "pages": [], "errors": []}
    try:
        if not fetcher.allowed(home):
            entity["errors"].append({"url": home, "error": "robots.txt nie zezwala albo jest nieosiągalny"})
            return entity
        final, body = fetcher.get(home)
        record, links = page_record(final, body, clock())
        entity["pages"].append({**record, "role": "home"})
    except SourceError as error:
        entity["errors"].append({"url": home, "error": str(error)})
        return entity
    hint = seed.get("offerUrl")
    ranked = [u for u in offer_links(final, links, limit=subpages + 1) if u not in (hint, final)]
    for url in ([hint] if hint and hint != final else []) + ranked:
        if len(entity["pages"]) > subpages:
            break
        try:
            if not fetcher.allowed(url):
                entity["errors"].append({"url": url, "error": "robots.txt nie zezwala"})
                continue
            got, body = fetcher.get(url)
            record, _ = page_record(got, body, clock())
            entity["pages"].append({**record, "role": "offer"})
        except SourceError as error:
            entity["errors"].append({"url": url, "error": str(error)})
    return entity


def discover_m3(seeds, fetcher, out_dir, clock=utc_now, subpages=1):
    """Crawl the seeds and keep every page with its URL, time and hash. Returns the written summary."""
    out_dir = _Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    entities = []
    for seed in seeds:
        if fetcher.used + 3 > fetcher.budget:
            domain = site_key(urlsplit(seed["url"]).hostname)
            entities.append({"id": f"m3:{domain}", "domain": domain, "label": seed.get("label"), "seed": seed, "pages": [],
                             "discoveredVia": seed.get("discoveredVia"), "errors": [{"url": seed["url"], "error": "pominięty: budżet żądań"}]})
            continue
        entities.append(read_m3_firm(seed, fetcher, clock, subpages=subpages))
    summary = {"startedAt": fetcher.log[0]["at"] if fetcher.log else None, "requests": fetcher.used, "budget": fetcher.budget,
               "intervalSeconds": fetcher.interval, "userAgent": M3_AGENT,
               "robots": {k: v[0] for k, v in fetcher.robots.items()}, "entities": entities}
    (out_dir / "entities.json").write_text(_json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (out_dir / "requests.jsonl").write_text("".join(_json.dumps(e, ensure_ascii=False) + "\n" for e in fetcher.log), encoding="utf-8")
    return summary


def _main(argv=None):
    import argparse
    from .catalogs import load_m3_seeds
    parser = argparse.ArgumentParser(description="M3: odkrywanie ofert doradczych (sieć).")
    parser.add_argument("seeds", type=_Path)
    parser.add_argument("--out", type=_Path, required=True)
    parser.add_argument("--budget", type=int, default=100)
    parser.add_argument("--subpages", type=int, default=1)
    args = parser.parse_args(argv)
    summary = discover_m3(load_m3_seeds(args.seeds), PoliteFetcher(budget=args.budget), args.out, subpages=args.subpages)
    pages = sum(len(e["pages"]) for e in summary["entities"])
    print(f"{len(summary['entities'])} podmiotów, {pages} stron, {summary['requests']} żądań")


def m3_creator(entity):
    return {"id": f"www:{entity['domain']}:m3", "name": entity.get("label") or entity["domain"], "platform": "web",
            "url": f"https://{entity['domain']}/", "discoveredVia": entity.get("discoveredVia") or "Odkrywanie ofert M3",
            "isSeed": False}


def m3_entity_captures(entity):
    """Turn one crawled firm into shared Captures (module M3), one per saved page, with the raw entity attached."""
    creator = m3_creator(entity)
    out = []
    for page in entity.get("pages", []):
        item = capture(
            f"web:{entity['domain']}{urlsplit(page['url']).path.rstrip('/')}:m3", creator, page.get("title") or creator["name"],
            page["url"], page["text"], observed_at=page["observedAt"], source_url=page["url"],
            response_hash=page["sha256"], scope="public_html_text", module="M3", brand=creator["name"],
        )
        item["provenance"].update(discoveredFrom=(entity.get("seed") or {}).get("discovery", {}).get("resultUrl"), role=page.get("role"))
        item["m3Entity"] = entity["id"]
        out.append(item)
    return creator, out


def read_m3_replay(path):
    """Offline: the saved M3 discovery run as creators, Captures and one source status."""
    data = _json.loads(_Path(path).read_text(encoding="utf-8"))
    creators, captures = [], []
    for entity in data["entities"]:
        if entity.get("pages"):
            creator, items = m3_entity_captures(entity)
            creators.append(creator)
            captures.extend(items)
    status = source_result("m3-offers-replay", "Oferty doradcze M3 · zapis 21 XI", str(path), data.get("startedAt") or utc_now(),
                           count=len(captures), raw_count=len(data["entities"]), scope="Tekst HTML stron firm (zapis)")
    return creators, captures, status


if __name__ == "__main__":
    _main()
