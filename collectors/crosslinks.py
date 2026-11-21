"""Find public social profiles linked from descriptions, without implying ownership.

Only profile references are followed. A YouTube alias must expose its own channel
identifier in page metadata; arbitrary channel IDs in recommendations are ignored.
The shared fetcher blocks redirects and limits response size and duration.
"""
from hashlib import sha256
from html.parser import HTMLParser
import re
from urllib.parse import parse_qs, urlencode, urlsplit

from tools.watch_sources import Source
from .common import SourceError, json_object, public_link, safe_get, source_result, utc_now
from .social import CONFIG, read_social

PROFILE_LIMIT = 8
ALIAS_LIMIT = 8
VIDEO_LIMIT = 4
URL_LIMIT = 32
CHANNEL = re.compile(r"UC[A-Za-z0-9_-]{22}\Z")
HANDLE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,99}\Z")
TIKTOK = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.]{0,31}\Z")
URLS = re.compile(r"https://[^\s<>\"']+", re.I)
SEEDS = {source.key for source in CONFIG.sources}


def profile_url(raw):
    """Return a canonical candidate URL, rejecting content and off-site URLs."""
    if not isinstance(raw, str):
        return None
    raw = raw.rstrip(".,;:!?)]}")
    if not public_link(raw):
        return None
    parts = urlsplit(raw)
    host, path = parts.hostname.lower(), parts.path.rstrip("/")
    if host in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        direct = re.fullmatch(r"/channel/(UC[A-Za-z0-9_-]{22})", path)
        alias = re.fullmatch(r"/(?:@([A-Za-z0-9_][A-Za-z0-9_.-]{0,99})|c/([A-Za-z0-9_][A-Za-z0-9_.-]{0,99}))", path)
        if direct:
            return f"https://www.youtube.com/channel/{direct.group(1)}"
        if alias:
            return f"https://www.youtube.com{path}"
    if host in {"tiktok.com", "www.tiktok.com", "m.tiktok.com"}:
        match = re.fullmatch(r"/@([A-Za-z0-9_][A-Za-z0-9_.]{0,31})", path)
        if match:
            return f"https://www.tiktok.com/@{match.group(1).lower()}"
    return None


def video_id(raw):
    """Accept only an explicit video URL; never follow arbitrary source links."""
    if not isinstance(raw, str):
        return None
    raw = raw.rstrip(".,;:!?)]}")
    if not public_link(raw):
        return None
    parts = urlsplit(raw)
    host = parts.hostname.lower()
    if host in {"youtu.be", "www.youtu.be"}:
        value = parts.path.strip("/")
    elif host in {"youtube.com", "www.youtube.com", "m.youtube.com"} and parts.path == "/watch":
        values = parse_qs(parts.query).get("v", [])
        value = values[0] if len(values) == 1 else ""
    else:
        return None
    return value if re.fullmatch(r"[A-Za-z0-9_-]{11}", value) else None


def video_candidate(video, refs, fetch, clock):
    """Official oEmbed identifies an author, not a stable channel ID or ownership."""
    video_url = f"https://www.youtube.com/watch?v={video}"
    endpoint = "https://www.youtube.com/oembed?" + urlencode({"url": video_url, "format": "json"})
    data = json_object(fetch(endpoint, {"www.youtube.com"}))
    author = data.get("author_name")
    url = profile_url(data.get("author_url", ""))
    if not isinstance(author, str) or not author.strip() or not url or urlsplit(url).hostname != "www.youtube.com":
        raise SourceError("oEmbed nie zwrócił poprawnego publicznego profilu autora.")
    key = "youtube-candidate:" + sha256(url.encode()).hexdigest()[:20]
    discovery = {"profileUrl": url, "videoUrl": video_url, "references": refs,
                 "description": "Autor filmu według YouTube oEmbed; odnośnik nie dowodzi własności konta przez autora opisu.",
                 "discoveredAt": clock(), "method": "youtube_oembed"}
    return {"id":key, "platform":"youtube", "name":author.strip()[:200], "url":url,
            "discoveredVia":"Autor filmu wskazanego w opisie (YouTube oEmbed)", "crosslinkDiscovery":discovery,
            "isSeed":False, "status":"candidate", "qualification":"candidate", "profileVerified":False}


class ChannelMetadata(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = set()

    def handle_starttag(self, tag, attributes):
        if tag not in ("meta", "link"):
            return
        attrs = dict(attributes)
        # Identity comes only from meta/link elements (itemprop, canonical, og:url, feed alternate).
        # YouTube emits them after </head> as well, so the position in the document does not matter;
        # IDs in scripts, text and recommendation links are never read.
        if tag == "meta" and (attrs.get("itemprop") or "").lower() == "channelid":
            self._id(attrs.get("content", ""))
        if tag == "link" and "canonical" in (attrs.get("rel") or "").lower().split():
            self._channel_url(attrs.get("href", ""))
        if tag == "meta" and (attrs.get("property") or "").lower() == "og:url":
            self._channel_url(attrs.get("content", ""))
        if tag == "link" and "alternate" in (attrs.get("rel") or "").lower().split():
            url = attrs.get("href", "")
            if public_link(url) and urlsplit(url).hostname in {"www.youtube.com", "youtube.com"}:
                parts = urlsplit(url)
                if parts.path == "/feeds/videos.xml":
                    for channel in parse_qs(parts.query).get("channel_id", []):
                        self._id(channel)

    def _id(self, value):
        if isinstance(value, str) and CHANNEL.fullmatch(value):
            self.ids.add(value)

    def _channel_url(self, value):
        normalized = profile_url(value)
        if normalized and "/channel/" in normalized:
            self._id(normalized.rsplit("/", 1)[-1])


def channel_id(url, fetch):
    """Resolve from explicit profile metadata only, never from page-wide IDs."""
    body = fetch(url, {"www.youtube.com"})
    parser = ChannelMetadata()
    try:
        parser.feed(body.decode("utf-8"))
        parser.close()
    except (UnicodeError, ValueError, RecursionError):
        raise SourceError("Nie można odczytać metadanych profilu YouTube.") from None
    if len(parser.ids) != 1:
        raise SourceError("Nie ustalono jednoznacznego identyfikatora kanału z metadanych profilu.")
    return next(iter(parser.ids))


def candidate_status(url, clock, message, status=None):
    key = "crosslink:" + sha256(url.encode()).hexdigest()[:20]
    result = source_result(key, "Odkrywanie profilu", url, clock(),
                           error=SourceError(message, status), scope="Odnośnik w opisie publikacji")
    return result


def extend_from_posts(captures, known_creators, fetch=safe_get, clock=utc_now):
    """Verify linked profiles and revisit previously verified non-seed profiles.

    Returns (creators, captures, statuses). The caller persists returned creators,
    including their ``crosslinkCheckedAt``, and passes them on subsequent scans.
    An error or budget skip is reported; it is never represented as an empty feed.
    """
    references = {}
    videos = {}
    for post in captures:
        description = post.get("description")
        if not isinstance(description, str):
            continue
        for match in URLS.finditer(description):
            url = profile_url(match.group())
            ref = {"captureId": post.get("id"), "creatorId": post.get("creatorId"),
                   "url": public_link(post.get("url"))}
            video = video_id(match.group())
            if video and (video in videos or len(videos) < URL_LIMIT):
                video_refs = videos.setdefault(video, [])
                if ref not in video_refs and len(video_refs) < 8:
                    video_refs.append(ref)
            if url:
                refs = references.setdefault(url, [])
                if ref not in refs and len(refs) < 8:
                    refs.append(ref)
                if len(references) >= URL_LIMIT:
                    break
        if len(references) >= URL_LIMIT:
            break

    known = {c.get("id"): c for c in known_creators if isinstance(c, dict) and c.get("id")}
    queue = {}
    for creator in known.values():
        if not creator.get("crosslinkDiscovery") or creator.get("isSeed"):
            continue
        platform = creator.get("platform")
        key = creator.get("id", "")
        account = key[len(platform) + 1:] if isinstance(platform, str) and key.startswith(platform + ":") else ""
        if (platform == "youtube" and CHANNEL.fullmatch(account)) or (platform == "tiktok" and TIKTOK.fullmatch(account)):
            queue[key] = (Source(platform, account, str(creator.get("name") or account)[:80]), creator)

    statuses = []
    aliases = 0
    for url, refs in references.items():
        path = urlsplit(url).path
        if urlsplit(url).hostname == "www.tiktok.com":
            source = Source("tiktok", path[2:].lower(), path[1:])
        else:
            if path.startswith("/channel/"):
                account = path.rsplit("/", 1)[-1]
            else:
                if aliases >= ALIAS_LIMIT:
                    status = candidate_status(url, clock, "Pominięto: limit rozwiązywania nazw profili.")
                    status["status"] = "skipped"
                    statuses.append(status)
                    continue
                aliases += 1
                try:
                    account = channel_id(url, fetch)
                except SourceError as error:
                    statuses.append(candidate_status(url, clock, str(error), error.status))
                    continue
            source = Source("youtube", account, account)
        if source.key in SEEDS:
            continue
        prior = queue.get(source.key, (None, known.get(source.key)))[1] or {}
        discovery = prior.get("crosslinkDiscovery") or {
            "profileUrl": url, "references": refs,
            "description": "Profil wskazany w opisie; związek i własność wymagają potwierdzenia.",
            "discoveredAt": clock(),
        }
        creator = {**prior, "id": source.key, "platform": source.platform,
                   "name": prior.get("name") or source.label, "url": source.profile_url,
                   "discoveredVia": "Odnośnik w opisie publikacji", "crosslinkDiscovery": discovery,
                   "isSeed": False}
        queue[source.key] = (Source(source.platform, source.account, creator["name"]), creator)

    # Keep unresolved candidates across scans; they are explicitly not verified profiles.
    candidates = {c["id"]: c for c in known.values() if c.get("status") == "candidate"
                  and c.get("crosslinkDiscovery", {}).get("method") == "youtube_oembed"}
    for index, (video, refs) in enumerate(videos.items()):
        endpoint = f"https://www.youtube.com/watch?v={video}"
        if index >= VIDEO_LIMIT:
            status = candidate_status(endpoint, clock, "Pominięto: limit filmów oEmbed w tym przebiegu.")
            status["status"] = "skipped"
            statuses.append(status)
            continue
        try:
            candidate = video_candidate(video, refs, fetch, clock)
            if candidate["id"] not in candidates:
                candidates[candidate["id"]] = candidate
            status = source_result("oembed:" + video, "Autor filmu YouTube", endpoint, clock(),
                                   count=1, scope="Autor z oEmbed; konto do potwierdzenia")
            status["status"] = "candidate"
            statuses.append(status)
        except SourceError as error:
            statuses.append(candidate_status(endpoint, clock, str(error), error.status))
    creators, found = list(candidates.values()), []
    pending = sorted(queue.values(), key=lambda item: (item[1].get("crosslinkCheckedAt") or "", item[0].key))
    for index, (source, creator) in enumerate(pending):
        if index >= PROFILE_LIMIT:
            status = candidate_status(source.profile_url, clock, "Pominięto: limit profili w tym przebiegu.")
            status["status"] = "skipped"
            statuses.append(status)
            # Already verified creators remain available and can rotate into a later scan.
            if creator.get("crosslinkVerifiedAt"):
                creators.append(creator)
            continue
        posts, status = read_social(source, fetch, clock)
        status["crosslink"] = True
        statuses.append(status)
        previous = bool(creator.get("crosslinkVerifiedAt"))
        if status["status"] == "ok" or previous:
            creator = {**creator, "crosslinkCheckedAt": clock()}
            if status["status"] == "ok":
                creator["crosslinkVerifiedAt"] = creator.get("crosslinkVerifiedAt") or clock()
            creators.append(creator)
            found.extend(posts)
    issues = sum(item["status"] in {"error", "skipped"} for item in statuses)
    summary = source_result("crosslink-discovery", "Odkrywanie profili z opisów", "https://www.youtube.com/",
                            clock(), count=len(creators), raw_count=len(references),
                            scope="Publiczne odnośniki w opisach; brak domniemania własności")
    if issues or candidates:
        summary["status"] = "partial" if creators else "error"
        summary["error"] = (f"Nie sprawdzono w pełni {issues} profili; "
                            f"kandydaci do potwierdzenia: {len(candidates)}. Szczegóły w statusach źródeł.")
        summary.pop("lastSuccessAt", None)
    statuses.append(summary)
    return creators, found, statuses
