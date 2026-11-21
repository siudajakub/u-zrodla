"""Search independent topic queries and monitor public podcast RSS."""

from datetime import timezone
from email.utils import parsedate_to_datetime
import re
from urllib.parse import urlencode, urlsplit
from xml.etree import ElementTree

from tools.watch_sources import iso_datetime, timestamp

from .audio import MP3_TYPES, provider_for
from .common import (
    SourceError, capture, digest, html_text, json_object, public_link, source_result, utc_now,
)

APPLE = "itunes.apple.com"
SEPIA = "sepiasearch.org"
PODCAST_QUERIES = ("inwestowanie", "obligacje", "portfel ETF")
PEERTUBE_QUERIES = ("ETF", "kryptowaluty")
FEED_HOSTS = {
    "www.spreaker.com", "rss.libsyn.com", "rss.buzzsprout.com", "anchor.fm",
    "feeds.soundcloud.com", "jakoszczedzacpieniadze.pl", "static.rmf.pl", "feed.firstory.me",
    "feeds.simplecast.com", "feeds.transistor.fm", "feeds.acast.com",
    "podcastaddict.com", "feeds.captivate.fm", "media.rss.com", "feeds.feedburner.com",
}
FINANCE = re.compile(
    r"\b(?:inwest\w*|etf\w*|obligac\w*|maklersk\w*|stockbroker\w*|gield\w*|"
    r"giełd\w*|finans\w*|oszczędz\w*|bitcoin\w*|kryptowalut\w*|portfel\w*|mająte?k\w*)\b",
    re.IGNORECASE,
)
CRYPTO = re.compile(r"\b(?:bitcoin\w*|blockchain\w*|kryptowalut\w*|btc|etf\w*)\b", re.I)
PODCAST_ID = re.compile(r"apple-podcasts:[1-9][0-9]{0,18}")
PODCAST_NS = "{https://podcastindex.org/namespace/1.0}"
MEDIA_NS = "{http://search.yahoo.com/mrss/}"


def apple_url(query):
    return f"https://{APPLE}/search?" + urlencode({
        "term": query, "country": "PL", "media": "podcast", "entity": "podcast", "limit": 12,
    })


def sepia_url(query):
    return f"https://{SEPIA}/api/v1/search/videos?" + urlencode({
        "search": query, "count": 10, "sort": "-publishedAt", "languageOneOf": "pl",
    })


def read_apple(query, fetch, clock=utc_now):
    url = apple_url(query)
    name = f"Apple Podcasts · {query}"
    key = f"apple-search:{query}"
    scope = "Katalog podcastów w polskim sklepie"
    try:
        body = fetch(url, {APPLE})
        data = json_object(body)
        results = data.get("results")
        if (not isinstance(results, list) or len(results) > 12
                or data.get("resultCount") != len(results)
                or any(not isinstance(item, dict) for item in results)):
            raise SourceError("Katalog zwrócił nieoczekiwany format wyników.")
    except SourceError as error:
        return [], source_result(key, name, url, clock(), error=error, scope=scope)
    observed = clock()
    response_hash = digest(body)
    creators = {}
    for rank, item in enumerate(results, 1):
        title = item.get("collectionName")
        feed = public_link(item.get("feedUrl"))
        show_id = item.get("collectionId")
        id = f"apple-podcasts:{show_id}"
        if (item.get("kind") != "podcast" or not isinstance(title, str)
                or not FINANCE.search(title) or not PODCAST_ID.fullmatch(id)):
            continue
        creators.setdefault(id, {
            "id": id, "name": title.strip()[:240], "platform": "apple-podcasts",
            "url": f"https://podcasts.apple.com/pl/podcast/id{show_id}",
            "discoveredVia": name, "feedUrl": feed, "firstDiscoveredAt": observed,
            "discovery": {"query": query, "rank": rank, "sourceUrl": url,
                          "responseSha256": response_hash, "observedAt": observed},
            "qualification": "candidate",
            "publisher": item["artistName"][:240] if isinstance(item.get("artistName"), str) else None,
        })
    result = source_result(key, name, url, observed, count=len(creators), raw_count=len(results), scope=scope)
    result["creatorIds"] = list(creators)
    return list(creators.values()), result


def rss_date(value):
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        return timestamp(parsed.astimezone(timezone.utc)) if parsed.tzinfo else None
    except (ValueError, OverflowError):
        return None


def feed_allowed(url):
    if not public_link(url) or urlsplit(url).hostname not in FEED_HOSTS:
        return False
    # Feed paths on these platforms share origins with open redirectors and other APIs.
    return not urlsplit(url).query


def parse_rss(body):
    # UTF-8 validation also blocks alternate encodings hiding a DTD declaration.
    try:
        text = body.decode("utf-8-sig")
    except UnicodeError:
        raise SourceError("Kanał RSS musi być zapisany w UTF-8.") from None
    if re.search(r"<!\s*(?:DOCTYPE|ENTITY)", text, re.IGNORECASE):
        raise SourceError("Nieoczekiwana deklaracja XML w kanale RSS.")
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError:
        raise SourceError("Niepoprawna odpowiedź RSS.") from None
    channel = root.find("channel")
    if root.tag != "rss" or channel is None:
        raise SourceError("Oczekiwano kanału RSS z odcinkami.")
    return channel


def podcast_media(item):
    media = {}
    for enclosure in item.findall("enclosure") + item.findall(f"{MEDIA_NS}content"):
        url = public_link(enclosure.get("url"))
        mime = (enclosure.get("type") or "").lower().split(";", 1)[0].strip()
        if url and mime in MP3_TYPES:
            media.update(audioUrl=url, audioMimeType=mime, audioHost=urlsplit(url).hostname,
                         audioExcerptAvailable=provider_for(url) is not None)
            break
    transcript = item.find(f"{PODCAST_NS}transcript")
    if transcript is not None:
        url = public_link(transcript.get("url"))
        if url:
            media["transcriptSource"] = {
                "url": url, "mediaType": transcript.get("type"), "language": transcript.get("language"),
                "scope": "publisher_link",
            }
    return media


def read_podcast(creator, fetch, clock=utc_now):
    creator = dict(creator)
    url = creator.get("feedUrl")
    name = f"RSS · {creator['name']}"
    key = f"rss:{creator['id']}"
    scope = "Tytuł i opis odcinka RSS"
    if not feed_allowed(url):
        checked = clock()
        result = source_result(key, name, creator["url"], checked, scope=scope)
        result.update(status="skipped", error="Kanał RSS poza listą hostów zatwierdzonych do odczytu.")
        result.pop("lastSuccessAt")
        return creator, [], result
    try:
        body = fetch(url, FEED_HOSTS)
        channel = parse_rss(body)
    except SourceError as error:
        creator["feedCheckedAt"] = clock()
        return creator, [], source_result(key, name, url, creator["feedCheckedAt"], error=error, scope=scope)
    observed = clock()
    creator["feedCheckedAt"] = observed
    items = channel.findall("item")
    language = channel.findtext("language", "").lower().strip()
    creator["feedLanguage"] = language or None
    # Store country is a distribution setting. The publisher's language narrows this queue.
    polish = language == "pl" or language.startswith("pl-")
    creator["qualification"] = "polish_feed" if polish else ("other_language" if language else "language_unknown")
    captures = {}
    body_hash = digest(body)
    if polish:
        def published(item):
            return rss_date(item.findtext("pubDate")) or ""

        for item in sorted(items, key=published, reverse=True):
            title = (item.findtext("title") or "").strip()
            link = public_link(item.findtext("link"))
            guid = (item.findtext("guid") or "").strip() or link
            link = link or public_link(guid)
            media = podcast_media(item)
            if not title or not guid:
                continue
            description = html_text(item.findtext("description", ""))
            id = f"{creator['id']}:episode:{digest(guid)[:32]}"
            episode = capture(
                id, creator, title[:300], link or media.get("audioUrl") or creator["url"], description,
                observed_at=observed, published_at=published(item) or None,
                source_url=url, response_hash=body_hash, scope="podcast_rss_title_description",
                publisher=creator.get("publisher"), **media,
            )
            link_scope = "episode" if link else ("audio_enclosure" if "audioUrl" in media else "show")
            episode["provenance"].update(itemGuid=guid[:512], publicLinkScope=link_scope)
            captures.setdefault(id, episode)
            if len(captures) >= 3:
                break
        if items and not captures:
            error = SourceError("Kanał nie zawiera tytułu lub identyfikatora odcinka.")
            return creator, [], source_result(key, name, url, observed, error=error, scope=scope)
    result = source_result(key, name, url, observed, count=len(captures), raw_count=len(items), scope=scope)
    result["language"] = creator["feedLanguage"]
    return creator, list(captures.values()), result


def read_peertube(query, fetch, clock=utc_now):
    url = sepia_url(query)
    name = f"PeerTube · {query}"
    key = f"peertube-search:{query}"
    scope = "Tytuł i opis zaindeksowany przez Sepia Search"
    try:
        body = fetch(url, {SEPIA})
        data = json_object(body)
        results = data.get("data")
        if (not isinstance(results, list) or len(results) > 10
                or type(data.get("total")) is not int or data["total"] < len(results)
                or any(not isinstance(item, dict) for item in results)):
            raise SourceError("Indeks PeerTube zwrócił nieoczekiwany format wyników.")
    except SourceError as error:
        return [], [], source_result(key, name, url, clock(), error=error, scope=scope)
    observed = clock()
    response_hash = digest(body)
    creators, captures = {}, {}
    for rank, item in enumerate(results, 1):
        title = item.get("name")
        description = item.get("description") or ""
        channel = item.get("channel")
        language = item.get("language")
        video_url = public_link(item.get("url"))
        video_id = item.get("uuid")
        if (not isinstance(title, str) or not isinstance(description, str)
                or not isinstance(channel, dict) or not isinstance(language, dict)
                or language.get("id") != "pl" or not video_url or not isinstance(video_id, str)
                or not re.fullmatch(r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}", video_id)
                or not CRYPTO.search(f"{title} {description}")):
            continue
        channel_url = public_link(channel.get("url"))
        handle = channel.get("name")
        label = channel.get("displayName") or handle
        if (not channel_url or urlsplit(channel_url).hostname != urlsplit(video_url).hostname
                or not isinstance(label, str) or not isinstance(handle, str)
                or not re.fullmatch(r"[a-zA-Z0-9_.-]{1,100}", handle)):
            continue
        id = f"peertube:{urlsplit(channel_url).hostname}/{handle.casefold()}"
        creator = creators.setdefault(id, {
            "id": id, "name": label[:240], "platform": "peertube", "url": channel_url,
            "discoveredVia": name, "firstDiscoveredAt": observed, "qualification": "topic_match",
            "discovery": {"query": query, "rank": rank, "sourceUrl": url,
                          "responseSha256": response_hash, "observedAt": observed},
        })
        published = iso_datetime(item.get("publishedAt"))
        id = f"peertube:{video_id}"
        captures[id] = capture(
            id, creator, title[:300], video_url, description,
            observed_at=observed, published_at=timestamp(published) if published else None,
            source_url=url, response_hash=response_hash, scope="peertube_index_description",
        )
    result = source_result(key, name, url, observed, count=len(captures), raw_count=len(results), scope=scope)
    result["indexedTotal"] = data["total"]
    result["creatorIds"] = list(creators)
    return list(creators.values()), list(captures.values()), result


# --- M3: seeds for advisory offers -----------------------------------------------------------------
# A seed is a firm domain found in a public catalogue or a recorded search result. Press, regulators,
# rankings and foreign pages are dropped; one seed per site keeps the deep result link as an offer hint.

import json as _json
from pathlib import Path as _Path

M3_NOT_FIRMS = {
    "analizy.pl", "bank.pl", "knf.gov.pl", "bip.knf.gov.pl", "parkiet.com", "money.pl", "bankier.pl", "forbes.pl",
    "icobench.com", "takeprofitapp.com", "wprost.pl", "infor.pl", "linkedin.com", "facebook.com", "youtube.com",
    "gpw.pl", "gov.pl", "esma.europa.eu", "udemy.com", "artykul.com.pl", "mfiles.pl", "krs-pobierz.pl",
}
M3_SEED_QUERIES = (
    "wealth management", "family office", "doradca inwestycyjny", "niezależny doradca finansowy",
    "opieka nad portfelem", "sygnały inwestycyjne", "portfel modelowy abonament", "grupa premium co kupić",
)


def _registrable(host):
    host = (host or "").lower().removeprefix("www.")
    parts = host.split(".")
    return ".".join(parts[-3:]) if len(parts) >= 3 and parts[-2] in ("com", "org", "net", "gov") else ".".join(parts[-2:])


def m3_seed_allowed(url):
    """A firm page: https, not press, a regulator or a document. The market axis later judges Poland."""
    if not public_link(url):
        return False
    parts = urlsplit(url)
    host = parts.hostname.lower()
    if _registrable(host) in M3_NOT_FIRMS or host in M3_NOT_FIRMS:
        return False
    if re.search(r"\.(?:pdf|docx?|xlsx?)$", parts.path, re.I):
        return False
    # Foreign-language paths of an international site are not an offer for Poland.
    return not re.search(r"/(?:en|de|en_us|en_gb)(?:/|$)", parts.path, re.I) or host.endswith(".pl")


def load_m3_seeds(path):
    """Read recorded search results or catalogue rows and return one seed per firm site, in order."""
    data = _json.loads(_Path(path).read_text(encoding="utf-8"))
    seeds, seen = [], set()
    for query in data.get("queries", []):
        for rank, url in enumerate(query.get("results", []), 1):
            if not m3_seed_allowed(url):
                continue
            parts = urlsplit(url)
            site = _registrable(parts.hostname)
            if site in seen:
                continue
            seen.add(site)
            deep = parts.path.strip("/") and not re.search(r"/(?:pl|pl_pl)/?$", parts.path)
            seeds.append({
                "url": f"https://{parts.hostname}/", "offerUrl": url if deep else None, "label": site,
                "discoveredVia": f"Wynik wyszukiwania · {query['query']}",
                "discovery": {"queryId": query.get("id"), "query": query["query"], "rank": rank, "resultUrl": url,
                              "observedAt": data.get("observedAt"), "source": str(path)},
            })
    return seeds
