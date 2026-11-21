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
