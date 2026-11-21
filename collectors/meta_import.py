"""Manual import of pages the analyst saved from Meta in their own browser (no request to Meta is made here).

Three kinds of saved files are read and turned into captures shaped like those of ``meta_ads``:

* the public Meta Ad Library results page (saved HTML or copied page text, Polish or English interface);
* the Instagram profile embed (saved HTML of ``/<account>/embed/``): the latest posts with caption, date, likes and
  the paid-partnership flag;
* a single Instagram post embed (saved HTML of ``/p/<code>/embed/captioned/``).

Nothing is guessed. A field the saved file does not contain stays empty and is listed in ``importMissing`` of the
capture ("brak danych w zapisanym pliku"). Platforms of an ad are taken only from names present in the file; the
Ad Library page draws them as icons, so a text copy usually carries only their number (``publisherPlatformIcons``).

CLI: ``python -m collectors.meta_import <file or folder> [...] --out replay.json[.gz]``.
Adapter: ``meta_import`` (``discover(ctx)``) reads the import folder (``INVESTWATCH_META_IMPORT_DIR``, default
``<state>/meta-import``) in live mode and the dated sample fixture in replay mode.
"""

from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
import gzip
import json
import os
from pathlib import Path
import re
import sys

from .common import capture, public_link, utc_now
from .meta_ads import relate
from .social import firm_signals

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DIR = ROOT / "fixtures/raw/discovery/social-2026-11-21"
SAMPLE_REPLAY = SAMPLE_DIR / "replay-meta.json.gz"
SAMPLE_MANIFEST = SAMPLE_DIR / "manifest-meta.json"
PARSER_VERSION = "meta-import-1"
MISSING = "brak danych w zapisanym pliku"
NEXT_STEP = "Ad Library API po uzyskaniu tokenu (adapter meta_ads gotowy) / Meta Content Library"
LIBRARY_URL = "https://www.facebook.com/ads/library/"
SUFFIXES = {".html", ".htm", ".txt", ".mhtml"}
MAX_FILE = 25 * 1024 * 1024

ZERO_WIDTH = "​‌‍﻿"
ID_RE = re.compile(r"(?:Identyfikator biblioteki|ID biblioteki|Library ID)\s*:?\s*(\d{6,})", re.I)
STATUS_WORDS = {"aktywna": "active", "nieaktywna": "inactive", "active": "active", "inactive": "inactive"}
STATUS_RE = re.compile(r"(?im)^\s*(Nieaktywna|Aktywna|Inactive|Active)\s*$")
PLATFORM_LABEL = re.compile(r"(?im)^\s*(?:Platformy|Platforms)\s*:?\s*$")
VERSIONS_RE = re.compile(r"Reklama ma kilka wersji|This ad has multiple versions", re.I)
COUNT_RE = re.compile(r"Liczba reklam[^:\n]*:\s*(\d+)|(\d[\d\s,.]*)\s+ads use this creative and text", re.I)
EU_RE = re.compile(r"Transparentność w UE|EU transparency", re.I)
SPONSOR_RE = re.compile(r"(?im)^\s*(?:Sponsorowane|Sponsored)\s*$")
VIDEO_RE = re.compile(r"^\d{1,2}:\d{2}\s*/\s*(\d{1,2}:\d{2})$")
DOMAIN_RE = re.compile(r"^(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}$")
RESULT_COUNT_RE = re.compile(r"(?:Liczba wyników|Results?)\s*:?\s*~?\s*([\d][\d\s ,.]*)", re.I)
UI_LINES = re.compile(r"(?i)^(?:Otwórz menu rozwijane|Open dropdown|Zobacz szczegóły (?:podsumowania|reklamy)|"
                      r"See (?:summary|ad) details|Wyświetl więcej|See more|Stan systemu|System status)$")
FOOTER_RE = re.compile(r"(?im)^\s*(?:Wyświetl więcej|See more|Stan systemu|System status)\s*$")
CTAS = {c.lower() for c in (
    "Sign Up", "Install Now", "Learn More", "Download", "See Details", "Shop Now", "Apply Now", "Get Offer", "Contact Us",
    "Subscribe", "Book Now", "Watch More", "Order Now", "Send Message", "Get Quote", "Get Started", "Donate Now",
    "Zarejestruj się", "Dowiedz się więcej", "Zainstaluj", "Zainstaluj teraz", "Pobierz", "Wyślij wiadomość", "Kup teraz",
    "Zobacz szczegóły", "Zapisz się", "Skontaktuj się", "Zarezerwuj", "Złóż wniosek", "Obejrzyj więcej", "Zamów teraz")}
PLATFORM_NAMES = (("facebook", "Facebook"), ("instagram", "Instagram"), ("audience_network", "Audience Network"),
                  ("messenger", "Messenger"), ("threads", "Threads"))
MONTHS = {"sty": 1, "jan": 1, "lut": 2, "feb": 2, "mar": 3, "kwi": 4, "apr": 4, "maj": 5, "may": 5, "cze": 6, "jun": 6,
          "lip": 7, "jul": 7, "sie": 8, "aug": 8, "wrz": 9, "sep": 9, "paź": 10, "paz": 10, "oct": 10, "lis": 11,
          "nov": 11, "gru": 12, "dec": 12}
DATE_PL = re.compile(r"(\d{1,2})\s+([^\W\d_]{3,12})\.?,?\s+(\d{4})")
DATE_EN = re.compile(r"([^\W\d_]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})")


# --- reading the saved file -----------------------------------------------------------------------------------------

class _Text(HTMLParser):
    """Visible text of a saved page: one line per text node; scripts and styles dropped. An icon that carries a
    platform name in alt/aria-label/title is kept as a line, because the Ad Library draws platforms as icons."""

    SKIP = {"script", "style", "noscript", "head", "template"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lines, self.skip = [], 0
        self.names = {n.lower() for _k, n in PLATFORM_NAMES}

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
            return
        if self.skip:
            return
        if tag == "br":
            self.lines.append("")
        for key, value in attrs:
            if key in ("alt", "aria-label", "title") and value and value.strip().lower() in self.names:
                self.lines.append(value.strip())

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.lines.extend(part.strip() for part in data.splitlines())


def html_to_text(html):
    parser = _Text()
    parser.feed(html)
    parser.close()
    return "\n".join(parser.lines)


def _decode(data):
    for encoding in ("utf-8-sig", "utf-16"):
        try:
            return data.decode(encoding)
        except UnicodeError:
            continue
    return data.decode("cp1250", "replace")


def _clean(line):
    return line.replace(" ", " ").strip(" " + ZERO_WIDTH).strip()


def _date(day, month, year):
    number = MONTHS.get(month.lower()[:3])
    try:
        return datetime(int(year), number, int(day)).date().isoformat() if number else None
    except ValueError:
        return None


def parse_dates(text):
    """(start, stop) as ISO dates from "18 wrz 2025 – 1 wrz 2026", "Rozpoczęcie wyświetlania 8 paź 2026",
    "Sep 18, 2025 - Sep 1, 2026" or "Started running on Sep 18, 2025". None where the text has no date."""
    found = [(m.start(), _date(m.group(1), m.group(2), m.group(3))) for m in DATE_PL.finditer(text)]
    if not found:
        found = [(m.start(), _date(m.group(2), m.group(1), m.group(3))) for m in DATE_EN.finditer(text)]
    dates = [d for _pos, d in sorted(found) if d]
    return (dates[0] if dates else None), (dates[1] if len(dates) > 1 else None)


def _int(*groups):
    digits = re.sub(r"\D", "", next((g for g in groups if g), "") or "")
    return int(digits) if digits else None


# --- Ad Library -----------------------------------------------------------------------------------------------------

def _ad_card(chunk, status_word, library_id):
    raw_lines = chunk.splitlines()
    lines = [_clean(line) for line in raw_lines]
    card = {"libraryId": library_id, "adStatus": STATUS_WORDS.get((status_word or "").lower()), "missing": []}
    label = next((i for i, line in enumerate(lines) if PLATFORM_LABEL.match(line)), None)
    head = lines[:label] if label is not None else lines[:3]
    card["datesRaw"] = " ".join(line for line in head if line) or None
    card["startDate"], card["stopDate"] = parse_dates(card["datesRaw"] or "")
    stops = [i for i, line in enumerate(lines) if i > (label or 0) and (VERSIONS_RE.search(line) or COUNT_RE.search(line)
             or EU_RE.search(line) or UI_LINES.match(line) or SPONSOR_RE.match(line))]
    region_end = stops[0] if stops else len(lines)
    names, icons = [], None
    if label is not None:
        region = lines[label + 1:region_end]
        for key, name in PLATFORM_NAMES:
            if any(name.lower() in line.lower() for line in region):
                names.append(key)
        icons = sum(1 for raw in raw_lines[label + 1:region_end] if raw.strip() and not raw.strip(ZERO_WIDTH + "  "))
    card["publisherPlatforms"] = names
    card["publisherPlatformIcons"] = icons
    card["multipleVersions"] = bool(VERSIONS_RE.search(chunk))
    count = COUNT_RE.search(chunk)
    card["versionsCount"] = _int(count.group(1), count.group(2)) if count else None
    card["euTransparency"] = bool(EU_RE.search(chunk))
    card.update(advertiser=None, body=None, title=None, description=None, domain=None, cta=None, video=False,
                videoDuration=None, layout=None)
    sponsor = next((i for i, line in enumerate(lines) if SPONSOR_RE.match(line)), None)
    if sponsor is not None:
        before = [line for line in lines[:sponsor] if line and not UI_LINES.match(line)]
        card["advertiser"] = before[-1] if before and lines[sponsor - 1] else None
        tail = list(lines[sponsor + 1:])
        while tail and (not tail[-1] or FOOTER_RE.match(tail[-1])):
            tail.pop()
        if tail and tail[-1].lower() in CTAS:
            card["cta"] = tail.pop()
        video = next((i for i, line in enumerate(tail) if VIDEO_RE.match(line)), None)
        if video is not None:
            card["video"] = True
            card["videoDuration"] = VIDEO_RE.match(tail[video]).group(1)
        domain = max((i for i, line in enumerate(tail) if DOMAIN_RE.match(line) and len(line) <= 80), default=None)
        if domain is not None:
            card["domain"] = tail[domain].lower()
            body = [line for line in tail[:domain] if not VIDEO_RE.match(line)]
            rest = [line for line in tail[domain + 1:] if line]
            card["layout"] = "domain"
        elif video is not None:
            body = tail[:video]
            rest = [line for line in tail[video + 1:] if line]
            card["layout"] = "video"
        else:
            body, rest = list(tail), []
            card["layout"] = "plain"
            if len([line for line in body if line]) > 1:
                card["layoutNote"] = "bez domeny i wideo: tytuł i opis nie są rozdzielone od treści (wszystko w treści)"
        card["title"] = rest[0] if rest else None
        card["description"] = "\n".join(rest[1:]) or None
        card["body"] = "\n".join(body).strip() or None
    for field in ("advertiser", "body", "title", "description", "domain", "cta"):
        if not card[field]:
            card["missing"].append(field)
    for field, absent in (("startDate", not card["startDate"]), ("adStatus", not card["adStatus"]),
                          ("publisherPlatforms", not names),
                          ("versionsCount", card["versionsCount"] is None and not card["euTransparency"])):
        if absent:
            card["missing"].append(field)
    return card


def parse_ad_library(text):
    """Cards of a saved Ad Library page (text, Polish or English). Returns {"ads", "page", "duplicates"}."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    matches = list(ID_RE.finditer(text))
    statuses = []
    for match in matches:
        found = list(STATUS_RE.finditer(text, max(0, match.start() - 40), match.start()))
        statuses.append(found[-1] if found else None)
    ads, seen, duplicates = [], set(), 0
    for index, match in enumerate(matches):
        end = len(text)
        if index + 1 < len(matches):
            end = statuses[index + 1].start() if statuses[index + 1] else matches[index + 1].start()
        chunk = text[match.end():end]
        if index + 1 == len(matches):
            footer = FOOTER_RE.search(chunk)
            if footer:
                chunk = chunk[:footer.start()]
        if match.group(1) in seen:
            duplicates += 1
            continue
        seen.add(match.group(1))
        ads.append(_ad_card(chunk, statuses[index].group(1) if statuses[index] else None, match.group(1)))
    page = {}
    head = text[:matches[0].start()] if matches else text
    total = RESULT_COUNT_RE.search(head)
    if total and _int(total.group(1)) is not None:
        page["resultCount"] = _int(total.group(1))
    page["interfaceLanguage"] = ("pl" if re.search(r"Identyfikator biblioteki|Biblioteka reklam", text) else
                                 "en" if re.search(r"Library ID|Ad Library", text) else None)
    return {"ads": ads, "page": page, "duplicates": duplicates}


def _primary(platforms):
    return "facebook" if "facebook" in platforms or "instagram" not in platforms else "instagram"


def _slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower().replace("ł", "l")).strip("-")[:60] or "nieznany"


def _day(value):
    return f"{value}T00:00:00+00:00" if value else None


def _discovery(meta, rank, reason):
    return {"method": "manual_import", "adapter": "meta_import", "sourceId": "meta_import", "queryKind": "import",
            "query": None, "position": rank, "page": None, "sourceFile": meta["file"], "savedAt": meta["savedAt"],
            "importedAt": meta["importedAt"], "sourceUrl": None, "observedAt": meta["importedAt"],
            "responseSha256": meta["sha256"], "reason": reason, "quotaUnits": 0, "import": True}


def _provenance(item, meta, kind):
    item["provenance"].update({
        "sourceFile": meta["file"], "sourceFileSha256": meta["sha256"], "savedAt": meta["savedAt"],
        "importedAt": meta["importedAt"], "import": True, "importKind": kind, "parser": PARSER_VERSION,
        "collectionMethod": "manual_import"})
    return item


def ad_capture(card, meta, rank):
    platforms = card["publisherPlatforms"]
    primary = _primary(platforms)
    advertiser = card["advertiser"] or ""
    text = "\n".join(p for p in (card["body"], card["title"], card["description"]) if p)
    relation = relate({"page_name": advertiser}, text)
    module = "M2" if relation and relation["role"] == "advertiser" else "M1"
    creator = {"id": f"facebook:page-name-{_slug(advertiser)}", "platform": "facebook"}
    links = []
    if card["domain"] and public_link("https://" + card["domain"]):
        links.append("https://" + card["domain"])
    observed = meta["importedAt"]
    item = capture(
        f"{primary}:ad-{card['libraryId']}", creator, ((card["body"] or card["title"] or advertiser or card["libraryId"]).splitlines() or [""])[0][:120],
        f"{LIBRARY_URL}?id={card['libraryId']}", text, observed_at=observed, published_at=_day(card["startDate"]),
        source_url=f"file:{meta['file']}", response_hash=meta["sha256"], scope="meta_ad_library_text", module=module,
        contentCompleteness="full" if text else "partial",
        discovery=[_discovery(meta, rank, "reklama z zapisanej strony Biblioteki Reklam Meta")], author=advertiser or None,
        reach={"asOf": observed, "source": "meta_ad_library", "primary": "euTotalReach", "metrics": {"euTotalReach": {
            "value": None, "state": "not_collected", "observedAt": observed, "source": "meta_ad_library"}}},
        mediaCoverage={"transcript": {"state": "unavailable", "source": "none", "windows": [], "durationSec": None,
                                      "reason": "Reklama z zapisanej strony: tylko tekst, obrazu i wideo nie analizowano"},
                       "frames": {"state": "not_collected", "moments": [], "intervalSec": None}},
        coverage={"scope": "ad_text", "state": "partial", "label": "Zbadano: tylko tekst reklamy z zapisanej strony, bez renderu",
                  "modalities": {"adText": {"state": "full" if text else "empty"}, "render": {"state": "not_collected"},
                                 "media": {"state": "not_collected"}}},
        adId=card["libraryId"], publisherPlatforms=platforms, publisherPlatformIcons=card["publisherPlatformIcons"],
        adSnapshotUrl=None, links=links, adDeliveryStopTime=_day(card["stopDate"]), adCreationTime=None,
        adStatus=card["adStatus"], adDeliveryStartDate=card["startDate"], adDeliveryStopDate=card["stopDate"],
        publishedAtPrecision="day" if card["startDate"] else None, adTitle=card["title"], adDescription=card["description"],
        adBody=card["body"], linkDomain=card["domain"], callToAction=card["cta"], hasVideo=card["video"],
        videoDuration=card["videoDuration"], multipleVersions=card["multipleVersions"], versionsCount=card["versionsCount"],
        euTransparencyShown=card["euTransparency"], languages=[], beneficiaryPayers=[],
        targeting={"locations": [], "ages": [], "gender": None}, firmRelation=relation,
        importLabel="import ręczny", importMissing=card["missing"], importNote=MISSING if card["missing"] else None,
        **({"importLayoutNote": card["layoutNote"]} if card.get("layoutNote") else {}),
    )
    item["platform"] = primary
    item["creatorId"] = creator["id"]
    _provenance(item, meta, "ad_library")
    row = {"id": creator["id"], "name": advertiser[:200] or MISSING, "platform": "facebook", "url": None, "handle": None,
           "isSeed": False, "discoveredVia": "Reklama na zapisanej stronie Biblioteki Reklam Meta (import ręczny)",
           "status": "confirmed", "profileVerified": False, "persistentId": None, "pageId": None,
           "discoveries": [item["discovery"][0]],
           "firmRelation": relation if relation and relation["role"] == "advertiser" else None}
    return item, row


# --- Instagram embeds ---------------------------------------------------------------------------------------------

def _context_json(html):
    marker = '"contextJSON":'
    start = html.find(marker)
    if start < 0:
        return None
    try:
        raw, _end = json.JSONDecoder().raw_decode(html[start + len(marker):])
        return json.loads(raw)["context"] if isinstance(raw, str) else None
    except (ValueError, KeyError, TypeError):
        return None


def _epoch(value):
    if type(value) is int and value > 0:
        return datetime.fromtimestamp(value, timezone.utc).replace(microsecond=0).isoformat()
    return None


def _metric(value, observed):
    ok = type(value) is int
    return {"value": value if ok else None, "state": "observed" if ok else "not_collected", "observedAt": observed,
            "source": "instagram_embed"}


def parse_instagram_profile(html):
    context = _context_json(html)
    if not isinstance(context, dict) or not context.get("username"):
        return None
    posts = []
    for node in context.get("graphql_media") or []:
        media = node.get("shortcode_media") if isinstance(node, dict) else None
        if not isinstance(media, dict) or not media.get("shortcode"):
            continue
        edges = (media.get("edge_media_to_caption") or {}).get("edges") or []
        first = edges[0].get("node") if edges and isinstance(edges[0], dict) else None
        caption = first.get("text") if isinstance(first, dict) else None
        flag = media.get("is_paid_partnership")
        coauthors = media.get("coauthor_producers")
        posts.append({"shortcode": media["shortcode"], "caption": caption if isinstance(caption, str) else None,
                      "publishedAt": _epoch(media.get("taken_at_timestamp")),
                      "likes": (media.get("edge_liked_by") or {}).get("count"),
                      "comments": (media.get("edge_media_to_comment") or {}).get("count"),
                      "paidPartnership": flag if isinstance(flag, bool) else None,
                      "isVideo": media.get("is_video") if isinstance(media.get("is_video"), bool) else None,
                      "coauthors": len(coauthors) if isinstance(coauthors, list) else None})
    return {"username": context.get("username"), "fullName": context.get("full_name"), "verified": context.get("is_verified"),
            "followers": context.get("followers_count"), "postsCount": context.get("posts_count"), "posts": posts}


class _Post(HTMLParser):
    """Caption, author, likes and post link of a captioned single-post embed."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.mode, self.depth, self.in_author = None, 0, False
        self.caption, self.author, self.likes, self.url = [], [], [], None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get("class") or ""
        if tag == "a" and self.url is None:
            match = re.match(r"https://www\.instagram\.com/(?:p|reel|tv)/[\w-]+", a.get("href") or "")
            if match:
                self.url = match.group(0) + "/"
        if tag == "div" and cls.strip() == "Caption":
            self.mode, self.depth = "caption", 1
            return
        if self.mode == "caption":
            if tag == "div":
                self.depth += 1
                if "CaptionComments" in cls:
                    self.mode = None
                    return
            elif tag == "a" and "CaptionUsername" in cls:
                self.in_author = True
            elif tag == "br":
                self.caption.append("\n")
        elif tag == "div" and "SocialProof" in cls:
            self.mode = "likes"

    def handle_endtag(self, tag):
        if tag == "a":
            self.in_author = False
        if tag == "div" and self.mode == "caption":
            self.depth -= 1
            if self.depth <= 0:
                self.mode = None
        elif tag == "div" and self.mode == "likes":
            self.mode = None

    def handle_data(self, data):
        if self.mode == "caption":
            (self.author if self.in_author else self.caption).append(data)
        elif self.mode == "likes":
            self.likes.append(data)


def parse_instagram_post(html):
    parser = _Post()
    parser.feed(html)
    caption = re.sub(r"\n{3,}", "\n\n", "".join(parser.caption).replace(" ", " ")).strip()
    author = "".join(parser.author).strip()
    code = re.search(r"/(?:p|reel|tv)/([\w-]+)", parser.url or "")
    if not code:
        return None
    likes = re.search(r"([\d][\d,.\s]*)\s+likes?|([\d][\d\s.,]*)\s+polubie", " ".join(parser.likes), re.I)
    return {"shortcode": code.group(1), "url": parser.url, "username": author or None, "caption": caption or None,
            "likes": _int(*likes.groups()) if likes else None, "comments": None, "publishedAt": None,
            "paidPartnership": None, "isVideo": None}


def instagram_captures(profile, meta, kind):
    """Captures and creator row of a profile embed (kind "instagram_profile") or a single post embed."""
    observed = meta["importedAt"]
    username = profile.get("username")
    full_name = profile.get("fullName") or "" if kind == "instagram_profile" else ""
    posts = profile["posts"] if kind == "instagram_profile" else [profile]
    handle_text = f"{full_name} {(username or '').replace('_', ' ').replace('.', ' ')}".strip()
    account = relate({"page_name": handle_text}, "") if handle_text else None
    if account:
        account = {**account, "role": "author", "basis": "nazwa konta"}
    creator = {"id": f"instagram:{username}" if username else "instagram:nieznany", "platform": "instagram"}
    captures = []
    for rank, post in enumerate(posts, start=1):
        shortcode = post.get("shortcode")
        if not shortcode:
            continue
        text = post.get("caption") or ""
        relation = account or relate({"page_name": ""}, text)
        missing = [name for name, value in (("caption", post.get("caption")), ("publishedAt", post.get("publishedAt")),
                                            ("likes", post.get("likes")), ("paidPartnership", post.get("paidPartnership")),
                                            ("username", username)) if value is None]
        first = text.strip().splitlines()[0][:120] if text.strip() else (username or shortcode)
        item = capture(
            f"instagram:{shortcode}", creator, first, post.get("url") or f"https://www.instagram.com/p/{shortcode}/", text,
            observed_at=observed, published_at=post.get("publishedAt"), source_url=f"file:{meta['file']}",
            response_hash=meta["sha256"], scope="instagram_embed_caption", module="M2" if account else "M1",
            contentCompleteness="full" if text else "partial",
            discovery=[_discovery(meta, rank, "post z zapisanego osadzenia Instagrama (import ręczny)")],
            author=full_name or username,
            reach={"asOf": observed, "source": "instagram_embed", "primary": "likeCount", "metrics": {
                "likeCount": _metric(post.get("likes"), observed), "commentCount": _metric(post.get("comments"), observed)}},
            mediaCoverage={"transcript": {"state": "unavailable", "source": "none", "windows": [], "durationSec": None,
                                          "reason": "Instagram: odczytano tylko podpis z zapisanego osadzenia"},
                           "frames": {"state": "not_collected", "moments": [], "intervalSec": None}},
            coverage={"scope": "caption", "state": "partial", "label": "Zbadano: tylko podpis z zapisanego osadzenia",
                      "modalities": {"caption": {"state": "full" if text else "empty"},
                                     "platformFlags": {"state": "observed" if post.get("paidPartnership") is not None else "unavailable",
                                                       "paidPromotion": post.get("paidPartnership")}}},
            isPaidPartnership=post.get("paidPartnership"), mediaIsVideo=post.get("isVideo"), shortcode=shortcode,
            firmRelation=relation, importLabel="import ręczny", importMissing=missing,
            importNote=MISSING if missing else None, **firm_signals(text))
        item["platform"] = "instagram"
        _provenance(item, meta, kind)
        captures.append(item)
    row = None
    if username and captures:
        row = {"id": creator["id"], "name": (full_name or username)[:200], "platform": "instagram",
               "url": f"https://www.instagram.com/{username}/", "handle": f"@{username}", "isSeed": False,
               "discoveredVia": "Zapisane osadzenie Instagrama (import ręczny)", "status": "confirmed",
               "profileVerified": False, "discoveries": [captures[0]["discovery"][0]], "firmRelation": account}
        if kind == "instagram_profile":
            row["reach"] = {"asOf": observed, "source": "instagram_embed", "primary": "followerCount",
                            "metrics": {"followerCount": _metric(profile.get("followers"), observed)}}
    return captures, row


# --- one file, many files -------------------------------------------------------------------------------------------

def _looks_html(text):
    return bool(re.search(r"<(?:html|body|div|span)\b", text[:20000], re.I))


def detect(text):
    """Kind of a saved file: ad_library, instagram_profile, instagram_post or None."""
    if 'class="Caption"' in text and "instagram.com" in text:
        return "instagram_post"
    if '"isProfileEmbed"' in text and '"contextJSON"' in text:
        return "instagram_profile"
    if ID_RE.search(html_to_text(text) if _looks_html(text) else text):
        return "ad_library"
    return None


def _mtime(path):
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).replace(microsecond=0).isoformat()


def read_file(path, *, saved_at=None, imported_at=None):
    """Read one saved file into captures. Status: ok, empty, unrecognized or error; content never raises."""
    path = Path(path)
    imported_at = imported_at or utc_now()
    out = {"file": path.name, "kind": None, "status": "error", "message": None, "captures": [], "creators": [],
           "count": 0, "sha256": None, "savedAt": None}
    try:
        if path.stat().st_size > MAX_FILE:
            out["message"] = "Plik jest większy niż 25 MiB."
            return out
        data = path.read_bytes()
        meta = {"file": path.name, "sha256": sha256(data).hexdigest(), "savedAt": saved_at or _mtime(path),
                "importedAt": imported_at}
    except OSError as error:
        out["message"] = f"Nie można odczytać pliku ({error.__class__.__name__})."
        return out
    out.update(sha256=meta["sha256"], savedAt=meta["savedAt"])
    text = _decode(data)
    kind = out["kind"] = detect(text)
    if kind is None:
        out.update(status="unrecognized", message="Nie rozpoznano zapisanej strony (Biblioteka Reklam Meta, osadzenie profilu "
                   "lub posta Instagrama). Zapisz stronę ponownie albo skopiuj cały tekst strony.")
        return out
    if kind == "ad_library":
        parsed = parse_ad_library(html_to_text(text) if _looks_html(text) else text)
        out["page"], out["duplicates"] = parsed["page"], parsed["duplicates"]
        creators = {}
        for rank, card in enumerate(parsed["ads"], start=1):
            item, creator = ad_capture(card, meta, rank)
            out["captures"].append(item)
            creators.setdefault(creator["id"], creator)
        out["creators"] = list(creators.values())
    else:
        profile = parse_instagram_profile(text) if kind == "instagram_profile" else parse_instagram_post(text)
        if profile is None:
            out.update(status="empty", message=f"Zapisany plik nie zawiera danych konta ani posta ({MISSING}).")
            return out
        if kind == "instagram_profile":
            out["account"] = {k: profile[k] for k in ("username", "fullName", "followers", "postsCount")}
        captures, creator = instagram_captures(profile, meta, kind)
        out["captures"], out["creators"] = captures, ([creator] if creator else [])
    out["count"] = len(out["captures"])
    if out["count"]:
        out["status"] = "ok"
    else:
        out.update(status="empty", message=f"Zapisany plik nie zawiera wpisów ({MISSING}).")
    return out


def collect_paths(paths):
    files = []
    for entry in map(Path, paths):
        if entry.is_dir():
            files.extend(sorted(p for p in entry.rglob("*") if p.is_file() and p.suffix.lower() in SUFFIXES))
        else:
            files.append(entry)
    return files


def import_files(files, *, imported_at=None, saved_at=None):
    """Read many files; a capture met twice keeps the first copy and gains the second discovery path."""
    imported_at = imported_at or utc_now()
    captures, creators, reports = {}, {}, []
    for path in files:
        result = read_file(path, saved_at=(saved_at or {}).get(Path(path).name), imported_at=imported_at)
        for item in result.pop("captures"):
            if item["id"] in captures:
                captures[item["id"]]["discovery"].append(item["discovery"][0])
            else:
                captures[item["id"]] = item
        for creator in result.pop("creators"):
            creators.setdefault(creator["id"], creator)
        reports.append(result)
    return {"creators": list(creators.values()), "captures": list(captures.values()), "files": reports,
            "importedAt": imported_at}


def source_rows(result, at, note=None):
    """Source rows of lane K: facebook-ads and instagram-ads (Library ads) and instagram (embed posts)."""
    ads = [c for c in result["captures"] if c.get("adId")]
    posts = [c for c in result["captures"] if not c.get("adId")]
    dates = sorted({f["savedAt"][:10] for f in result["files"] if f.get("savedAt") and f.get("count")})
    day = dates[-1] if dates else at[:10]
    unknown = sum(1 for c in ads if not c.get("publisherPlatforms"))
    rows = []
    for platform, name in (("facebook", "Facebook"), ("instagram", "Instagram")):
        row = {"id": f"{platform}-ads", "name": f"{name} · reklamy (Biblioteka Reklam Meta, import ręczny)", "url": LIBRARY_URL,
               "status": "ok" if ads else "empty", "count": sum(1 for c in ads if c["platform"] == platform), "observedAt": at,
               "scope": "Reklamy wyświetlane w PL; próbka z zapisanych stron, nie skan ciągły",
               "importMethod": "manual_import", "sampleDate": day if ads else None, "nextStep": NEXT_STEP,
               "message": (f"próbka datowana z publicznej Biblioteki Reklam, wczytana z zapisanych stron ({len(ads)} reklam, {day})"
                           if ads else "brak zapisanych stron Biblioteki Reklam w katalogu importu")}
        if ads:
            row["lastSuccessAt"] = at
        if unknown:
            row["note"] = (f"Platformy {unknown} reklam nie wynikają z zapisanego tekstu (ikony bez nazw); reklama bez nazwy "
                           "platformy jest liczona jako facebook, jak w meta_ads, więc 0 przy Instagramie nie oznacza braku reklam na nim.")
        rows.append(row)
    ig = {"id": "instagram", "name": "Instagram · wpisy z zapisanego osadzenia profilu", "url": "https://www.instagram.com/",
          "status": "ok" if posts else "empty", "count": len(posts), "observedAt": at, "importMethod": "manual_import",
          "scope": "Próbka ostatnich wpisów z zapisanego osadzenia profilu; odczyt automatyczny wyłączony",
          "nextStep": NEXT_STEP,
          "message": (f"próbka wpisów z zapisanego osadzenia profilu ({len(posts)} postów, {day}); odczyt automatyczny wyłączony"
                      if posts else "brak zapisanych osadzeń Instagrama w katalogu importu")}
    if posts:
        ig.update(lastSuccessAt=at, sampleDate=day)
    problems = [{"file": f["file"], "status": f["status"], "message": f["message"]}
                for f in result["files"] if f["status"] in ("unrecognized", "error")]
    if problems:
        ig["files"] = problems
    if note:
        for row in rows + [ig]:
            row["message"] += f" ({note})"
    return rows + [ig]


def build_result(files, *, imported_at=None, saved_at=None, note=None):
    result = import_files(files, imported_at=imported_at, saved_at=saved_at)
    result["sources"] = source_rows(result, result["importedAt"], note)
    result["status"] = "ok" if result["captures"] else "empty"
    return result


# --- sample fixture: files saved by the research run on 2026-11-21 ----------------------------------------------------

SAMPLE_FILES = ("alt/metaadlib-browser-body.txt", "alt/ig-profile-embed.html", "alt/ig-profile-embed-etoro.html",
                "alt/ig-profile-embed-trading212_pl.html")
SAMPLE_SAVED_AT = {  # file mtimes of the research run, fixed so that the replay does not depend on a checkout
    "metaadlib-browser-body.txt": "2026-11-21T21:04:00+00:00", "ig-profile-embed.html": "2026-11-21T21:01:51+00:00",
    "ig-profile-embed-etoro.html": "2026-11-21T21:02:30+00:00", "ig-profile-embed-trading212_pl.html": "2026-11-21T21:02:40+00:00"}
SAMPLE_NOTE = "plik z 21 XI 2026"


def build_sample(root=SAMPLE_DIR, imported_at=None):
    result = build_result([Path(root) / name for name in SAMPLE_FILES], imported_at=imported_at,
                          saved_at=SAMPLE_SAVED_AT, note=SAMPLE_NOTE)
    result["fixtureNote"] = ("Próbka z 2026-11-21 wczytana z zapisanych plików (Biblioteka Reklam Meta dla PL, hasło XTB; "
                             "osadzenia profili Instagrama). Import ręczny, bez zapytań do Meta.")
    return result


def manifest_of(result):
    return {"parser": PARSER_VERSION, "importedAt": result["importedAt"],
            "sourceDir": "fixtures/raw/discovery/social-2026-11-21",
            "files": [{"file": "alt/" + f["file"], "sha256": f["sha256"], "kind": f["kind"], "status": f["status"],
                       "savedAt": f["savedAt"], "count": f["count"],
                       **{k: f[k] for k in ("account", "page", "message") if f.get(k)}} for f in result["files"]],
            "captures": len(result["captures"]), "creators": len(result["creators"])}


def write_json(path, value):
    path = Path(path)
    if path.suffix == ".gz":
        path.write_bytes(gzip.compress(json.dumps(value, ensure_ascii=False, sort_keys=True).encode(), mtime=0))
    else:
        path.write_text(json.dumps(value, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def read_sample(path=SAMPLE_REPLAY):
    return json.loads(gzip.decompress(Path(path).read_bytes()))


# --- adapter ------------------------------------------------------------------------------------------------------------

def import_dir(environ=None):
    environ = os.environ if environ is None else environ
    if environ.get("INVESTWATCH_META_IMPORT_DIR"):
        return Path(environ["INVESTWATCH_META_IMPORT_DIR"]).expanduser()
    state = environ.get("INVESTWATCH_STATE")
    return (Path(state) if state else ROOT / ".runtime/demo") / "meta-import"


def discover(ctx):
    """Live: the analyst's saved files in the import folder. Replay: the dated sample fixture. No network in either."""
    options = ctx.options or {}
    if ctx.mode == "replay":
        result = read_sample(options.get("meta_import_sample") or SAMPLE_REPLAY)
        for item in result.get("captures", []):
            item["mode"] = "replay"
            item.setdefault("provenance", {}).setdefault("fixture", "social-2026-11-21/replay-meta.json.gz")
        for key in ("fixtureNote", "files", "importedAt"):
            result.pop(key, None)
        return result
    folder = Path(options.get("meta_import_dir") or import_dir(options.get("env")))
    files = collect_paths([folder]) if folder.is_dir() else []
    ctx.heartbeat()
    result = build_result(files, imported_at=ctx.clock(), note=None if files else f"katalog importu: {folder}")
    result.pop("files", None)
    result.pop("importedAt", None)
    return result


# --- command line ---------------------------------------------------------------------------------------------------------

def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(prog="python -m collectors.meta_import",
                                     description="Import stron zapisanych ręcznie z Meta (bez żadnych żądań sieciowych).")
    parser.add_argument("paths", nargs="+", help="plik lub katalog z zapisanymi stronami (.html, .txt)")
    parser.add_argument("--out", help="plik wynikowy (.json lub .json.gz); bez niego tylko podsumowanie")
    parser.add_argument("--imported-at", help="znacznik czasu importu (ISO); domyślnie teraz")
    args = parser.parse_args(argv)
    files = collect_paths(args.paths)
    if not files:
        print("Nie znaleziono plików do importu.", file=sys.stderr)
        return 2
    result = build_result(files, imported_at=args.imported_at)
    if args.out:
        write_json(args.out, result)
    for report in result["files"]:
        print(f"{report['file']}: {report['kind'] or '-'} {report['status']} ({report['count']}) {report['message'] or ''}".rstrip())
    print(f"Razem: {len(result['captures'])} wpisów, {len(result['creators'])} kont.")
    return 0 if result["captures"] else 1


if __name__ == "__main__":
    sys.exit(main())
