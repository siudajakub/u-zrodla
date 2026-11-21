"""YouTube adapter: Data API v3 discovery with Atom as a second path for the same material.

Contract v2 (docs/lanes/2026-11-21-fable-h-kontrakt.md, section 3.3 and 3.8):
``discover(ctx)`` returns ``{creators, captures, sources, status, resume, quota}``.

Flow (live): search.list for three query families (registry brand aliases, promotional phrases,
neutral investment topics) -> videos.list (full title/description, statistics, duration, status,
paid promotion flag) -> channels.list (subscribers, uploads playlist) -> playlistItems.list for the
highest-ranked channels -> optional Atom read of the same channels. Every observation adds one
``discovery[]`` entry; the same video from Atom and the API stays one capture with two paths.

The API key is read only from the environment (YOUTUBE_API_KEY, YOUTUBE_API_KEY_FILE) or the
default file outside the repository. It never leaves the request: every stored URL has
``key=REDACTED``. A missing key gives ``status="needs_key"`` without an exception.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, parse_qsl
from urllib.request import Request, urlopen
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
API = "https://www.googleapis.com/youtube/v3/"
ATOM_URL = "https://www.youtube.com/feeds/videos.xml?channel_id="
DEFAULT_KEY_FILE = Path("~/.config/investwatch/youtube.key").expanduser()
REPLAY = ROOT / "fixtures/raw/discovery/youtube-api-2026-11-21/replay.json.gz"
UA = "InvestWatch-SourceMonitor/1.0"
MAX_BYTES = 4 * 1024 * 1024
MAX_TEXT = 24_000
COST = {"search": 100, "videos": 1, "channels": 1, "playlistItems": 1}
CACHE_TTL = {"search": 6 * 3600, "videos": 600, "channels": 3600, "playlistItems": 1800}
PACIFIC = ZoneInfo("America/Los_Angeles")
ATOM = "{http://www.w3.org/2005/Atom}"
YT = "{http://www.youtube.com/xml/schemas/2015}"
MEDIA = "{http://search.yahoo.com/mrss/}"
VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}")
CHANNEL_ID = re.compile(r"UC[A-Za-z0-9_-]{22}")

# Aliases from the KNF snapshots in data/probe-snapshots/knf: domestic brokerage houses
# (knf_domy_maklerskie.json, knf_banki_maklerskie.json) and cross-border notifications
# (knf_notyfikacje_zagr_FI.json). Saxo is not in the local snapshots; marked unresolved.
FIRMS = {
    "XTB": ("XTB S.A.", False), "X-Trade Brokers": ("XTB S.A.", False),
    "mBank": ("mBank S.A. (Biuro maklerskie)", False), "eMakler": ("mBank S.A. (Biuro maklerskie)", False),
    "bossa": ("DM BOŚ S.A.", False), "DM BOŚ": ("DM BOŚ S.A.", False),
    "Pekao": ("Bank Pekao S.A. (Biuro maklerskie)", False), "PKO BP": ("PKO BP (DM PKO BP)", False),
    "eToro": ("eToro (Europe) Ltd", True), "Trading 212": ("Trading 212 EU GmbH / Markets Ltd", True),
    "Trading212": ("Trading 212 EU GmbH / Markets Ltd", True),
    "Freedom24": ("Freedom Finance Europe Ltd", True), "Freedom Finance": ("Freedom Finance Europe Ltd", True),
    "Interactive Brokers": ("Interactive Brokers Ireland Ltd", True), "IBKR": ("Interactive Brokers Ireland Ltd", True),
    "Finax": ("Finax o.c.p., a.s.", True), "Lightyear": ("Lightyear Europe AS", True),
    "Capital.com": ("Capital Com SV Investments / Group", True), "Plus500": ("Plus500CY Ltd", True),
    "Admiral Markets": ("Admiral Markets AS", True), "Admirals": ("Admiral Markets AS", True),
    "IG Europe": ("IG Europe GmbH", True), "Exante": ("EXT Ltd", True),
    "Revolut": ("Revolut (inwestycje: podmiot do ustalenia)", "unresolved"),
    "Saxo": ("Saxo Bank A/S", "unresolved"), "DEGIRO": ("flatexDEGIRO Bank AG", "unresolved"),
    "Scalable Capital": ("Scalable Capital GmbH", "unresolved"), "Conotoxia": ("Conotoxia Ltd", "unresolved"),
}
FIRM_RE = re.compile(r"(?<![\w-])(" + "|".join(re.escape(k) for k in sorted(FIRMS, key=len, reverse=True)) + r")(?![\w-])", re.I)

QUERIES = (
    ("brand", "XTB", 2), ("brand", "eToro", 1), ("brand", "Trading 212", 1), ("brand", "Freedom24", 1),
    ("brand", "Interactive Brokers", 1), ("brand", "Saxo Bank", 1), ("brand", "mBank eMakler", 1),
    ("topic", "inwestowanie", 2), ("topic", "giełda", 1), ("topic", "ETF", 1), ("topic", "akcje dywidendowe", 1),
    ("topic", "obligacje skarbowe", 1), ("topic", "IKE IKZE", 1), ("topic", "jak zacząć inwestować", 1),
    ("promo", "partnerem odcinka", 1), ("promo", "kod promocyjny konto maklerskie", 1),
    ("promo", "link w opisie darmowe akcje", 1),
    ("topic", "kryptowaluty", 1), ("topic", "bitcoin", 1), ("topic", "analiza techniczna", 1),
    ("topic", "forex", 1), ("topic", "złoto srebro inwestowanie", 1),
    ("promo", "kod polecający giełda kryptowalut", 1),
)
DISCLOSURE = re.compile(
    r"(?i)(reklam\w*|współprac\w*|wspolprac\w*|sponsor\w*|partner\w*\s+(?:odcinka|materiału|filmu|publikacji|kanału|programu|wideo)|partnerzy\b|"
    r"materiał\s+sponsorowany|płatn\w+\s+(?:promocj\w*|współprac\w*|partnerstw\w*)|lokowanie\s+produktu|#ad\b|#reklama|"
    r"#płatnawspółpraca|paid\s+partnership|link\w*\s+afiliac\w*|link\w*\s+partnersk\w*|link\w*\s+reflink\w*|afiliacyjn\w*)"
)
TRACKING = re.compile(
    r"https?://[^\s<>\"]*(?:[?&](?:ref\w*|aff\w*|a|i|utm_\w+|partner\w*|code|promo|via|tag|campaign\w*)=|"
    r"link-pso\.xtb\.com|link\.pl\.xtb\.com|c\.freedom24\.com|bit\.ly/|tinyurl\.com/|ibkr\.com/referral|"
    r"/campaigns?/|/referral|/invite|/ref/)[^\s<>\"]*", re.I)
CODE = re.compile(r"\b(?i:kod(?:em|u)?)\s+(?:(?i:rabatowy|promocyjny|polecający|partnerski)\s+)?[„\"'“]?\s?([A-Z0-9][A-Z0-9_-]{2,19})\b")
CODE_STOP = {"SMS", "PIN", "QR", "BLIK", "PL", "PDF", "CVV", "OTP"}
FIRM_HOSTS = {"XTB S.A.": ("xtb.com", "xtb.pl"), "eToro (Europe) Ltd": ("etoro.",), "Freedom Finance Europe Ltd": ("freedom24.",),
              "Trading 212 EU GmbH / Markets Ltd": ("trading212.",), "Interactive Brokers Ireland Ltd": ("interactivebrokers.", "ibkr."),
              "Saxo Bank A/S": ("home.saxo", "saxo."), "Plus500CY Ltd": ("plus500.",), "Lightyear Europe AS": ("lightyear.",),
              "Finax o.c.p., a.s.": ("finax.",), "Admiral Markets AS": ("admiralmarkets.", "admirals."),
              "Capital Com SV Investments / Group": ("capital.com",), "mBank S.A. (Biuro maklerskie)": ("mbank.pl",),
              "DM BOŚ S.A.": ("bossa.pl",), "Revolut (inwestycje: podmiot do ustalenia)": ("revolut.",)}
SHORTENER = re.compile(r"https?://(?:bit\.ly|tinyurl\.com|t\.ly|rebrand\.ly|cutt\.ly|tmlead\.pl)/\S+", re.I)
PL_CHARS = re.compile(r"[ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]")
PL_WORDS = re.compile(r"(?i)\b(się|jest|nie|czy|jak|oraz|który|która|które|dlaczego|tylko|będzie|już|także|giełd\w*|inwest\w*|akcj\w*)\b")


class QuotaExceeded(Exception):
    def __init__(self, reason, retry_at=None):
        super().__init__(reason)
        self.reason, self.retry_at = reason, retry_at


def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def redact(url):
    return re.sub(r"([?&]key=)[^&]+", r"\1REDACTED", url)


def next_reset(now_iso):
    """Data API quota resets at midnight Pacific time."""
    now = datetime.fromisoformat(now_iso).astimezone(PACIFIC)
    reset = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return reset.astimezone(timezone.utc).isoformat()


def load_key(env=None):
    env = os.environ if env is None else env
    if env.get("YOUTUBE_API_KEY"):
        return env["YOUTUBE_API_KEY"].strip() or None
    path = Path(env["YOUTUBE_API_KEY_FILE"]).expanduser() if env.get("YOUTUBE_API_KEY_FILE") else DEFAULT_KEY_FILE
    try:
        resolved = path.resolve()
        if ROOT in resolved.parents:
            return None  # a key file inside the repository is refused
        return resolved.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def http_fetch(url):
    """Return (status, body). Never includes the URL in error text."""
    try:
        with urlopen(Request(url, headers={"User-Agent": UA, "Accept-Language": "pl"}), timeout=20) as response:
            return response.status, response.read(MAX_BYTES)
    except HTTPError as error:
        with error:
            return error.code, error.read(MAX_BYTES)
    except (URLError, OSError):
        return None, b""


@dataclass
class Context:
    """Stable adapter interface (v1, 2026-11-21; change only with an entry in the lane record).

    mode       "live" | "replay"
    state      source_state body of "youtube"; ``state["resume"]`` = {queryIndex, query, pageToken, page}
    budget     hard unit cap of this run; 0 (default without INVESTWATCH_YT_RUN_UNITS) = no API calls
    fetch      callable(url) -> (status:int|None, body:bytes); None = http_fetch (urllib, looked up at call time)
    clock      callable() -> ISO-8601 UTC string
    key        explicit key (tests); None -> key_source() or module ``load_key()`` (patchable)
    key_source callable() -> str|None
    heartbeat  method; the runner (H) replaces it to extend the scan lease; called before each API request
    raw_dir    directory for raw responses + requests.jsonl (key=REDACTED); None = nothing written
    cache_dir  directory for the response cache; None = no cache
    cache_ttl  per-method TTL override in seconds, e.g. {"videos": 0}
    queries, window_days, published_after, max_results, playlist_channels, atom_channels, pause,
    known_creators: scan settings (overridable by ctx.options["youtube"] in the runner).

    Result: {creators, captures, sources, status, resume, retryAt, quota}. status: ok | empty |
    rate_limited | error | needs_key. Run budget exhausted -> status rate_limited with
    ``sources[0].lastError.code == "budget"``, source status partial/empty and no retryAt; API quota -> lastError.code
    "quotaExceeded" (or dailyLimitExceeded/rateLimitExceeded) with retryAt = next Pacific midnight.
    """
    mode: str = "live"
    state: dict = field(default_factory=dict)          # source_state body for "youtube" (resume cursor)
    # No explicit budget means no spending: a scan with a key never draws on the daily quota
    # unless the runner (H) or the CLI passes a limit, or INVESTWATCH_YT_RUN_UNITS is set.
    budget: int = field(default_factory=lambda: int(os.environ.get("INVESTWATCH_YT_RUN_UNITS") or 0))
    fetch: object = None                               # None -> http_fetch (looked up at call time)
    clock: object = utc_now
    key: object = None                                 # None -> key_source() or module load_key()
    key_source: object = None
    queries: tuple = QUERIES
    window_days: int = 180
    published_after: object = None                     # fixed window start; default: day start minus window_days
    cache_ttl: object = None                           # per-method TTL override, e.g. {"videos": 0}
    max_results: int = 50
    playlist_channels: int = 8
    atom_channels: int = 3
    cache_dir: object = None
    raw_dir: object = None
    pause: float = 0.0
    known_creators: tuple = ()

    def heartbeat(self):
        pass


def _ctx(value, name, default=None):
    return getattr(value, name, default)


class Session:
    """Quota ledger, response cache and raw recording around one adapter run."""

    def __init__(self, ctx, key):
        self.ctx, self.key = ctx, key
        self.budget = int(_ctx(ctx, "budget", 0) or 0)
        self.used = 0
        self.ledger = []
        self.cache_dir = Path(ctx.cache_dir) if _ctx(ctx, "cache_dir") else None
        self.raw_dir = Path(ctx.raw_dir) if _ctx(ctx, "raw_dir") else None
        self.requests = 0
        self.exhausted = None  # set after a real quotaExceeded: no further API calls in this run
        if self.raw_dir:
            self.raw_dir.mkdir(parents=True, exist_ok=True)
            index = self.raw_dir / "requests.jsonl"
            self.requests = len(index.read_text(encoding="utf-8").splitlines()) if index.exists() else 0

    def remaining(self):
        return self.budget - self.used

    def _record(self, method, url, status, body, observed, cached, label):
        if not self.raw_dir:
            return None
        self.requests += 1
        name = None if cached else f"{self.requests:03d}-{method}-{re.sub(r'[^a-z0-9]+', '-', label.lower()).strip('-')[:50]}.{'xml' if method == 'atom' else 'json'}"
        if name:  # a cache hit is indexed but its body is already stored under the original request
            (self.raw_dir / name).write_bytes(body)
        row = {"n": self.requests, "method": method, "label": label, "url": redact(url), "observedAt": observed,
               "status": status, "bytes": len(body), "sha256": sha256(body).hexdigest(), "file": name,
               "cached": cached, "units": 0 if cached or method == "atom" else COST.get(method, 0)}
        with (self.raw_dir / "requests.jsonl").open("a", encoding="utf-8") as index:
            index.write(json.dumps(row, ensure_ascii=False) + "\n")
        return name

    @staticmethod
    def _cache_key(method, params):
        public = {k: v for k, v in params.items() if k != "key"}
        return sha256(json.dumps([method, public], sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    def cached(self, method, params):
        return self._cache_get(self._cache_key(method, params), method) is not None

    def api(self, method, params, label):
        cost = COST[method]
        public = {k: v for k, v in params.items() if k != "key"}
        cache_key = self._cache_key(method, params)
        cached = self._cache_get(cache_key, method)
        url = API + method + "?" + urlencode({**public, "key": self.key})
        if cached is not None:
            status, body, observed = 200, cached["body"].encode(), cached["observedAt"]
            self._record(method, url, status, body, observed, True, label)
            return json.loads(body), observed, sha256(body).hexdigest(), redact(url)
        if self.exhausted:
            raise QuotaExceeded(*self.exhausted)
        if self.used + cost > self.budget:
            raise QuotaExceeded("budget", None)
        if _ctx(self.ctx, "pause", 0):
            time.sleep(self.ctx.pause)
        self.ctx.heartbeat() if hasattr(self.ctx, "heartbeat") else None
        observed = self.ctx.clock()
        status, body = (self.ctx.fetch or http_fetch)(url)
        self.used += cost  # Google charges failed requests too.
        self.ledger.append({"method": method, "units": cost, "at": observed, "label": label, "status": status})
        self._record(method, url, status, body or b"", observed, False, label)
        if status == 200:
            self._cache_put(cache_key, body, observed)
            return json.loads(body), observed, sha256(body).hexdigest(), redact(url)
        reason = _error_reason(body)
        if status == 403 and reason in ("quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded"):
            self.exhausted = (reason, next_reset(observed))
            raise QuotaExceeded(*self.exhausted)
        raise ApiError(status, reason)

    def atom(self, channel):
        url = ATOM_URL + channel
        observed = self.ctx.clock()
        status, body = (self.ctx.fetch or http_fetch)(url)
        self._record("atom", url, status, body or b"", observed, False, channel)
        return status, body or b"", observed, url

    def _cache_get(self, key, method):
        if not self.cache_dir:
            return None
        path = self.cache_dir / f"{key}.json"
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        age = datetime.fromisoformat(self.ctx.clock()) - datetime.fromisoformat(saved["observedAt"])
        ttl = {**CACHE_TTL, **(_ctx(self.ctx, "cache_ttl") or {})}[method]
        return saved if age.total_seconds() <= ttl else None

    def _cache_put(self, key, body, observed):
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            (self.cache_dir / f"{key}.json").write_text(json.dumps({"observedAt": observed, "body": body.decode("utf-8")}), encoding="utf-8")


class ApiError(Exception):
    def __init__(self, status, reason):
        super().__init__(f"HTTP {status}: {reason}")
        self.status, self.reason = status, reason


def _error_reason(body):
    try:
        errors = json.loads(body)["error"].get("errors") or [{}]
        return errors[0].get("reason") or json.loads(body)["error"].get("status")
    except (ValueError, KeyError, TypeError, AttributeError):
        return None


def iso_duration(value):
    match = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", value or "")
    if not match or not value or value in ("P", "PT"):
        return None
    days, hours, minutes, seconds = (int(x or 0) for x in match.groups())
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def detect_language(declared, title, description):
    """Declared Polish wins; a strong Polish text overrides another declared language (uploaders
    often leave en-US or zxx); otherwise the declared language, then the text. regionCode never decides."""
    declared = [v.lower() for v in declared if v and v.lower() not in ("zxx", "und")]
    if declared and declared[0].startswith("pl"):
        return "pl", "declared"
    text = f"{title or ''}\n{description or ''}"[:4000]
    words = re.findall(r"\w+", text)
    text_lang = None
    if len(words) >= 4:
        score = len(PL_CHARS.findall(text)) / max(len(text), 1) * 100 + len(PL_WORDS.findall(text)) / len(words) * 100
        text_lang = "pl" if score >= 3 else "other"
    if text_lang == "pl":
        return "pl", f"text_heuristic_over_declared_{declared[0]}" if declared else "text_heuristic"
    if declared:
        return declared[0].split("-")[0], "declared"
    return (text_lang or "unknown"), ("text_heuristic" if text_lang else "text_too_short")


def description_signals(text):
    """Description-level signals for D and the report: firms, firm-linked tracking links or codes, disclosure.
    Not a qualification: whether a link is paid promotion is decided downstream (D) with full context."""
    text = text or ""
    firms, evidence = {}, []
    for m in FIRM_RE.finditer(text):
        alias = next(k for k in FIRMS if k.lower() == m.group(1).lower())
        name = FIRMS[alias][0]
        firms.setdefault(name, {"alias": m.group(1), "crossBorder": FIRMS[alias][1]})
        window = text[max(0, m.start() - 200):m.end() + 200]
        for link in SHORTENER.findall(window):
            evidence.append({"firm": name, "kind": "shortener_near_mention", "value": link.rstrip(".,;)")})
        for code in CODE.findall(window):
            if code not in CODE_STOP:
                evidence.append({"firm": name, "kind": "code_near_mention", "value": code})
    for link in TRACKING.findall(text):
        host = urlsplit(link).hostname or ""
        for name, hosts in FIRM_HOSTS.items():
            if any(h in host or h in link for h in hosts):
                firms.setdefault(name, {"alias": host, "crossBorder": next(v[1] for v in FIRMS.values() if v[0] == name)})
                evidence.append({"firm": name, "kind": "firm_tracking_link", "value": link.rstrip(".,;)")})
    unique = list({(e["firm"], e["kind"], e["value"]): e for e in evidence}.values())
    return {"firms": firms, "firmEvidence": unique[:12], "tracking": sorted(set(TRACKING.findall(text)))[:10],
            "codes": sorted({c for c in CODE.findall(text) if c not in CODE_STOP})[:10],
            "disclosure": disclosure_phrases(text)}


CONTACT_LINE = re.compile(r"(?i)[\w.+-]+@[\w-]+\.[\w.]+|\bkontakt\w*\b|\boferty?\s+współprac")


def disclosure_phrases(text):
    """Disclosure wording, ignoring business-contact lines such as "Współpraca: biuro@…"."""
    lines = [line for line in (text or "").splitlines() if not CONTACT_LINE.search(line)]
    return sorted({m.group(0).lower() for m in DISCLOSURE.finditer("\n".join(lines))})


def _metric(stats, name, observed, source, *, hidden=None):
    if hidden:
        return {"value": None, "state": "hidden", "observedAt": observed, "source": source}
    if name in stats and stats[name] not in (None, ""):
        return {"value": int(stats[name]), "state": "observed", "observedAt": observed, "source": source}
    return {"value": None, "state": "hidden" if stats else "unavailable", "observedAt": observed, "source": source}


def video_reach(item, observed):
    stats = item.get("statistics") or {}
    live = (item.get("snippet") or {}).get("liveBroadcastContent")
    metrics = {}
    for name in ("viewCount", "likeCount", "commentCount"):
        metric = _metric(stats, name, observed, "data_api")
        if name == "viewCount" and metric["state"] == "hidden" and live in ("upcoming", "live"):
            metric["state"] = "unavailable"
        metrics[name] = metric
    return {"asOf": observed, "source": "data_api", "primary": "viewCount", "metrics": metrics}


def channel_reach(item, observed):
    stats = item.get("statistics") or {}
    return {"asOf": observed, "source": "data_api", "primary": "subscriberCount", "metrics": {
        "subscriberCount": _metric(stats, "subscriberCount", observed, "data_api", hidden=stats.get("hiddenSubscriberCount")),
        "viewCount": _metric(stats, "viewCount", observed, "data_api"),
        "videoCount": _metric(stats, "videoCount", observed, "data_api")}}


def _value(reach, name):
    metric = (reach or {}).get("metrics", {}).get(name) or {}
    return metric.get("value") if metric.get("state") == "observed" else None


def _path(method, observed, sha, url, *, kind=None, query=None, position=None, page=None, reason=None, units=0):
    return {"method": method, "adapter": "youtube", "queryKind": kind, "query": query, "position": position,
            "page": page, "sourceId": "youtube", "sourceUrl": redact(url), "observedAt": observed,
            "responseSha256": sha, "reason": reason, "quotaUnits": units, "import": False}


def _capture_base(video_id, channel_id, title, description, url, observed, published, completeness, source_url, sha, scope):
    text = (description or "")[:MAX_TEXT]
    return {
        "id": f"youtube:{video_id}", "creatorId": f"youtube:{channel_id}", "title": title or "",
        "url": url, "platform": "youtube", "description": text, "module": "M1", "observedAt": observed,
        "publishedAt": published, "contentHash": sha256(text.encode()).hexdigest(), "materialType": scope,
        "contentCompleteness": completeness,
        "provenance": {"sourceUrl": redact(source_url), "observedAt": observed, "responseSha256": sha, "scope": scope,
                       "truncated": len(description or "") > MAX_TEXT},
    }


def capture_from_video(item, observed, sha, url, paths, flag_checked):
    snippet, details, status = item.get("snippet") or {}, item.get("contentDetails") or {}, item.get("status") or {}
    duration = iso_duration(details.get("duration"))
    language, method = detect_language((snippet.get("defaultAudioLanguage"), snippet.get("defaultLanguage")),
                                       snippet.get("title"), snippet.get("description"))
    paid = (item.get("paidProductPlacementDetails") or {}).get("hasPaidProductPlacement") if flag_checked else None
    privacy = status.get("privacyStatus")
    capture = _capture_base(item["id"], snippet.get("channelId"), snippet.get("title"), snippet.get("description"),
                            f"https://www.youtube.com/watch?v={item['id']}", observed, snippet.get("publishedAt"),
                            "full", url, sha, "youtube_data_api_title_description")
    capture.update(
        author=snippet.get("channelTitle"), discovery=list(paths), reach=video_reach(item, observed),
        youtube={"channelId": snippet.get("channelId"), "videoId": item["id"], "publishedAt": snippet.get("publishedAt"),
                 "durationSec": duration, "isShort": (True if duration is not None and duration <= 60 else
                                                     None if duration is not None and duration <= 180 else False),
                 "defaultAudioLanguage": snippet.get("defaultAudioLanguage"),
                 "defaultLanguage": snippet.get("defaultLanguage"), "detectedLanguage": language,
                 "languageMethod": method, "languageStatus": "in_scope" if language == "pl" else
                 ("unknown" if language == "unknown" else "out_of_scope"),
                 "privacyStatus": privacy, "liveBroadcastContent": snippet.get("liveBroadcastContent"),
                 "paidPromotionFlag": paid if isinstance(paid, bool) else None,
                 "madeForKids": status.get("madeForKids")},
        availability={"state": "private" if privacy == "private" else "available", "observedAt": observed,
                      "reason": None if privacy != "private" else "privacyStatus=private"},
    )
    return capture


def capture_from_search_only(hit, observed, sha, url, paths, reason):
    """search.list returned the video but videos.list did not: removed, private or blocked."""
    snippet = hit.get("snippet") or {}
    video_id = hit["id"]["videoId"]
    capture = _capture_base(video_id, snippet.get("channelId"), snippet.get("title"), snippet.get("description"),
                            f"https://www.youtube.com/watch?v={video_id}", observed, snippet.get("publishedAt"),
                            "partial", url, sha, "youtube_search_snippet")
    language, method = detect_language((), snippet.get("title"), snippet.get("description"))
    capture.update(author=snippet.get("channelTitle"), discovery=list(paths),
                   reach={"asOf": observed, "source": "data_api", "primary": "viewCount",
                          "metrics": {"viewCount": {"value": None, "state": "not_collected", "observedAt": observed,
                                                    "source": "data_api"}}},
                   youtube={"channelId": snippet.get("channelId"), "videoId": video_id,
                            "publishedAt": snippet.get("publishedAt"), "durationSec": None, "isShort": None,
                            "defaultAudioLanguage": None, "detectedLanguage": language, "languageMethod": method,
                            "languageStatus": "unknown" if language != "pl" else "in_scope",
                            "privacyStatus": None, "paidPromotionFlag": None},
                   availability={"state": "unavailable", "observedAt": observed, "reason": reason})
    return capture


def parse_atom(body):
    if re.search(br"<!\s*(?:DOCTYPE|ENTITY)", body, re.I):
        raise ValueError("Atom zawiera deklarację dokumentu.")
    feed = ElementTree.fromstring(body)
    channel = feed.findtext(f"{YT}channelId") or ""
    channel = "UC" + channel if len(channel) == 22 else channel
    author = feed.findtext(f"{ATOM}author/{ATOM}name")
    items = []
    for position, entry in enumerate(feed.findall(f"{ATOM}entry"), 1):
        video = entry.findtext(f"{YT}videoId") or ""
        if not VIDEO_ID.fullmatch(video):
            continue
        link = entry.find(f"{ATOM}link")
        href = link.get("href") if link is not None else None
        group = entry.find(f"{MEDIA}group")
        stats = group.find(f"{MEDIA}community/{MEDIA}statistics") if group is not None else None
        items.append({"position": position, "videoId": video, "url": href, "title": entry.findtext(f"{ATOM}title"),
                      "published": entry.findtext(f"{ATOM}published"),
                      "description": group.findtext(f"{MEDIA}description") if group is not None else None,
                      "views": int(stats.get("views")) if stats is not None and stats.get("views") else None,
                      "isShort": bool(href and "/shorts/" in href)})
    return channel, author, items


def captures_from_atom(channel, body, observed, url, sha):
    feed_channel, author, items = parse_atom(body)
    if feed_channel != channel:
        raise ValueError("Atom zwrócił inny kanał.")
    result = []
    for item in items:
        if item["description"] is None or item["title"] is None:
            continue
        capture = _capture_base(item["videoId"], channel, item["title"], item["description"],
                                f"https://www.youtube.com/watch?v={item['videoId']}", observed, item["published"],
                                "full", url, sha, "youtube_atom_title_description")
        views = item["views"]
        language, method = detect_language((), item["title"], item["description"])
        capture.update(
            author=author,
            discovery=[_path("atom", observed, sha, url, position=item["position"], reason="monitor znanego kanału")],
            reach={"asOf": observed, "source": "atom", "primary": "viewCount", "metrics": {"viewCount": {
                "value": views, "state": "observed" if views is not None else "unavailable",
                "observedAt": observed, "source": "atom"}}},
            youtube={"channelId": channel, "videoId": item["videoId"], "publishedAt": item["published"],
                     "durationSec": None, "isShort": True if item["isShort"] else None, "detectedLanguage": language,
                     "languageMethod": method, "languageStatus": "in_scope" if language == "pl" else "unknown",
                     "privacyStatus": None, "paidPromotionFlag": None},
            availability={"state": "available", "observedAt": observed, "reason": None})
        result.append(capture)
    return result


def rank_channels(creators):
    """Scan order: observed subscribers desc; hidden subscribers after observed ones, by found views."""
    def key(creator):
        subs = _value(creator.get("reach"), "subscriberCount")
        return (0 if subs is not None else 1, -(subs or 0), -creator.get("_foundViews", 0), creator["id"])
    ordered = sorted(creators, key=key)
    for rank, creator in enumerate(ordered, 1):
        subs = _value(creator.get("reach"), "subscriberCount")
        basis = f"{subs} subskrybentów" if subs is not None else f"subskrybenci ukryci; {creator.get('_foundViews', 0)} wyświetleń znalezionych filmów"
        creator["scanPriority"] = {"rank": rank, "reason": f"{basis}; język: {creator.get('_language', 'nieustalony')}"}
    return ordered


def rank_videos(captures):
    """Long-form first, Shorts in their own bucket; views desc, then newer, then id (ties)."""
    def key(capture):
        info = capture.get("youtube") or {}
        views = _value(capture.get("reach"), "viewCount")
        return (1 if info.get("isShort") else 0, 0 if views is not None else 1, -(views or 0),
                "".join(chr(0x10FFFF - ord(c)) for c in (info.get("publishedAt") or "")), capture["id"])
    ordered = sorted(captures, key=key)
    for rank, capture in enumerate(ordered, 1):
        info, views = capture.get("youtube") or {}, _value(capture.get("reach"), "viewCount")
        bucket = "Shorts" if info.get("isShort") else "dłuższe formy"
        capture["priority"] = {"acquisition": {"rank": rank, "reason": f"{bucket}; " + (
            f"{views} wyświetleń (stan {capture['reach']['asOf']})" if views is not None else "wyświetlenia nieznane")},
            "review": {"rank": None}, "basis": "reach", "affectsDecision": False}
    return ordered


def _source(status, observed, *, count=0, error=None, retry_at=None, quota=None, scope=None, next_step=None):
    source = {"id": "youtube", "name": "YouTube · Data API v3 + Atom", "kind": "search", "status": status,
              "count": count, "observedAt": observed, "url": "https://www.googleapis.com/youtube/v3/search",
              "scope": scope}
    if status in ("ok", "empty", "partial"):
        source["lastSuccessAt"] = observed
    if error:
        source["error"] = error["message"]
        source["lastError"] = {**error, "at": observed, "nextStep": next_step, **({"retryAt": retry_at} if retry_at else {})}
    if retry_at:
        source["retryAt"] = retry_at
    if quota is not None:
        source["quota"] = quota
    return source


def discover(ctx):
    """Run one YouTube scan. ``ctx`` follows the adapter contract (mode, state, budget, heartbeat)."""
    mode = _ctx(ctx, "mode", "live")
    clock = _ctx(ctx, "clock", utc_now)
    if mode == "replay":
        return replay()
    key = _ctx(ctx, "key") or (_ctx(ctx, "key_source") or load_key)()
    observed = clock()
    if not key:
        return {"creators": [], "captures": [], "status": "needs_key", "resume": _ctx(ctx, "state", {}).get("resume"),
                "quota": {"used": 0, "limit": 0},
                "sources": [_source("needs_key", observed, error={"code": "needs_key", "message": "Brak klucza YouTube Data API v3."},
                                    next_step="Ustaw YOUTUBE_API_KEY_FILE poza repozytorium.")]}
    session = Session(ctx, key)
    queries = list(_ctx(ctx, "queries", QUERIES))
    resume = dict((_ctx(ctx, "state", {}) or {}).get("resume") or {})
    start = int(resume.get("queryIndex", 0))
    # Day granularity keeps the window (and the cache key) stable within a day and across resumes.
    published_after = _ctx(ctx, "published_after") or (datetime.fromisoformat(observed) - timedelta(
        days=_ctx(ctx, "window_days", 180))).strftime("%Y-%m-%dT00:00:00Z")
    hits, status, error, retry_at, next_resume = {}, "ok", None, None, None
    reserve = lambda: 1 + len(hits) // 50 + 1 + len({h["snippet"]["channelId"] for h, _ in hits.values()}) // 50 + 1
    try:
        for index in range(start, len(queries)):
            kind, query, pages = queries[index]
            token = resume.get("pageToken") if index == start else None
            first_page = int(resume.get("page", 1)) if index == start and token else 1
            for page in range(first_page, pages + 1):
                params = {"part": "snippet", "q": query, "type": "video", "maxResults": _ctx(ctx, "max_results", 50),
                          "regionCode": "PL", "relevanceLanguage": "pl", "publishedAfter": published_after,
                          "order": "relevance", "safeSearch": "none"}
                if token:
                    params["pageToken"] = token
                if not session.cached("search", params) and session.remaining() < COST["search"] + reserve():
                    next_resume = {"queryIndex": index, "query": query, "pageToken": token, "page": page}
                    raise QuotaExceeded("budget")
                try:
                    data, at, sha, url = session.api("search", params, f"{kind} {query} p{page}")
                except QuotaExceeded:
                    next_resume = {"queryIndex": index, "query": query, "pageToken": token, "page": page}
                    raise
                base = (page - 1) * params["maxResults"]
                for position, hit in enumerate(data.get("items") or [], 1):
                    video = (hit.get("id") or {}).get("videoId")
                    if not video or not VIDEO_ID.fullmatch(video):
                        continue
                    path = _path("data_api_search", at, sha, url, kind=kind, query=query, position=base + position,
                                 page=page, reason=f"wynik wyszukiwania ({kind})", units=COST["search"] if position == 1 else 0)
                    hits.setdefault(video, (hit, []))[1].append(path)
                token = data.get("nextPageToken")
                if not token:
                    break
    except QuotaExceeded as exhausted:
        status, retry_at = "rate_limited", exhausted.retry_at
        error = {"code": exhausted.reason, "message": "Wyczerpany budżet przebiegu." if exhausted.reason == "budget"
                 else f"Limit Data API ({exhausted.reason})."}
    except ApiError as failure:
        status, error = "error", {"code": failure.reason or str(failure.status), "message": str(failure)}

    captures, creators = {}, {}
    try:
        _enrich(session, hits, captures, creators)
        ordered = rank_channels(list(creators.values()))
        _playlists(session, ordered[:_ctx(ctx, "playlist_channels", 8)], captures, creators)
    except QuotaExceeded as exhausted:
        status, retry_at = "rate_limited", exhausted.retry_at or retry_at
        error = error or {"code": exhausted.reason, "message": "Budżet wyczerpany podczas wzbogacania."}
    except ApiError as failure:
        status, error = "error" if status == "ok" else status, error or {"code": failure.reason, "message": str(failure)}
    ordered = rank_channels(list(creators.values()))
    atom_errors = _atom(session, ordered[:_ctx(ctx, "atom_channels", 3)], captures)
    for capture in captures.values():
        creator = creators.get(capture["creatorId"])
        if creator is not None:
            creator["_foundViews"] = creator.get("_foundViews", 0) + (_value(capture.get("reach"), "viewCount") or 0)
    ordered = rank_channels(list(creators.values()))
    ranked = rank_videos(list(captures.values()))
    for creator in ordered:
        creator.pop("_foundViews", None)
        creator.pop("_language", None)
    quota = {"used": session.used, "limit": session.budget, "resetAt": next_reset(observed), "entries": session.ledger}
    scope = {"queries": [{"kind": k, "query": q, "pages": p} for k, q, p in queries], "window": {"publishedAfter": published_after},
             "regionCode": "PL", "relevanceLanguage": "pl", "maxResults": _ctx(ctx, "max_results", 50)}
    source_status = {"rate_limited": "limit", "error": "partial" if ranked else "error"}.get(status, "ok" if ranked else "empty")
    if status == "rate_limited" and (error or {}).get("code") == "budget":
        source_status = "partial" if ranked else "empty"  # own run cap, not the API quota: no "limit"
    source = _source(source_status, clock(), count=len(ranked), error=error, retry_at=retry_at, quota=quota, scope=scope,
                     next_step="Wznowić od kursora po resecie kwoty." if status == "rate_limited" else None)
    atom_source = {"id": "youtube-atom", "name": "YouTube · Atom (druga ścieżka)", "kind": "feed",
                   "status": "error" if atom_errors and not any(d["method"] == "atom" for c in ranked for d in c.get("discovery", [])) else "ok",
                   "count": sum(1 for c in ranked if any(d["method"] == "atom" for d in c.get("discovery", []))),
                   "observedAt": clock(), "errors": atom_errors}
    return {"creators": ordered, "captures": ranked, "sources": [source, atom_source], "status": status,
            "resume": next_resume, "retryAt": retry_at, "quota": quota}


def _videos_list(session, ids, label):
    parts = "snippet,statistics,contentDetails,status,paidProductPlacementDetails"
    try:
        return session.api("videos", {"part": parts, "id": ",".join(ids), "maxResults": 50}, label), True
    except ApiError as failure:
        if failure.status != 400:
            raise
        return session.api("videos", {"part": "snippet,statistics,contentDetails,status", "id": ",".join(ids),
                                      "maxResults": 50}, label + " bez flagi"), False


def _enrich(session, hits, captures, creators):
    ids = list(hits)
    for start in range(0, len(ids), 50):
        chunk = ids[start:start + 50]
        (data, at, sha, url), flag = _videos_list(session, chunk, f"videos {start}")
        found = {item["id"]: item for item in data.get("items") or []}
        for video in chunk:
            hit, paths = hits[video]
            if video in found:
                captures[f"youtube:{video}"] = capture_from_video(found[video], at, sha, url, paths, flag)
            else:
                captures[f"youtube:{video}"] = capture_from_search_only(
                    hit, at, sha, url, paths, "videos.list nie zwrócił filmu: usunięty, prywatny lub zablokowany")
    _channels(session, {c["creatorId"].split(":", 1)[1] for c in captures.values()}, captures, creators, hits)


def _channels(session, channel_ids, captures, creators, hits):
    pending = sorted(c for c in channel_ids if CHANNEL_ID.fullmatch(c or "") and f"youtube:{c}" not in creators)
    for start in range(0, len(pending), 50):
        data, at, sha, url = session.api("channels", {"part": "snippet,statistics,contentDetails",
                                                      "id": ",".join(pending[start:start + 50]), "maxResults": 50},
                                         f"channels {start}")
        for item in data.get("items") or []:
            snippet = item.get("snippet") or {}
            first = _first_discovery(item["id"], captures)
            languages = [c["youtube"].get("detectedLanguage") for c in captures.values() if c["creatorId"] == f"youtube:{item['id']}"]
            pl = sum(1 for x in languages if x == "pl")
            creators[f"youtube:{item['id']}"] = {
                "id": f"youtube:{item['id']}", "name": snippet.get("title"), "platform": "youtube",
                "url": f"https://www.youtube.com/channel/{item['id']}", "handle": snippet.get("customUrl"),
                "discoveredVia": "YouTube Data API: search.list", "status": "confirmed", "persistentId": item["id"],
                "country": snippet.get("country"), "defaultLanguage": snippet.get("defaultLanguage"),
                "uploadsPlaylistId": (item.get("contentDetails") or {}).get("relatedPlaylists", {}).get("uploads"),
                "reach": channel_reach(item, at), "discoveries": [first] if first else [],
                "discovery": ({"query": first["query"], "rank": first["position"], "sourceUrl": first["sourceUrl"],
                               "responseSha256": first["responseSha256"], "observedAt": first["observedAt"]} if first else None),
                "firstDiscoveredAt": first["observedAt"] if first else at,
                "languageSample": {"pl": pl, "total": len(languages)}, "_language": f"{pl}/{len(languages)} filmów po polsku",
            }


def _first_discovery(channel, captures):
    paths = [d for c in captures.values() if c["creatorId"] == f"youtube:{channel}" for d in c.get("discovery", [])
             if d["method"] in ("data_api_search", "data_api_playlist")]
    return min(paths, key=lambda d: (d["observedAt"], d.get("position") or 0), default=None)


def _playlists(session, ordered, captures, creators):
    new = {}
    for creator in ordered:
        playlist = creator.get("uploadsPlaylistId")
        if not playlist or session.remaining() < 2:
            continue
        data, at, sha, url = session.api("playlistItems", {"part": "contentDetails", "playlistId": playlist, "maxResults": 50},
                                         f"uploads {creator['id']}")
        for position, item in enumerate(data.get("items") or [], 1):
            video = (item.get("contentDetails") or {}).get("videoId")
            if video and VIDEO_ID.fullmatch(video):
                path = _path("data_api_playlist", at, sha, url, position=position, page=1,
                             reason=f"lista przesłanych, kanał #{creator['scanPriority']['rank']}",
                             units=COST["playlistItems"] if position == 1 else 0)
                if f"youtube:{video}" in captures:
                    captures[f"youtube:{video}"]["discovery"].append(path)
                else:
                    new.setdefault(video, []).append(path)
        creator["uploadsNextPageToken"] = data.get("nextPageToken")
    ids = list(new)
    for start in range(0, len(ids), 50):
        chunk = ids[start:start + 50]
        if session.remaining() < 1:
            break
        (data, at, sha, url), flag = _videos_list(session, chunk, f"videos uploads {start}")
        for item in data.get("items") or []:
            captures[f"youtube:{item['id']}"] = capture_from_video(item, at, sha, url, new[item["id"]], flag)


def _atom(session, ordered, captures):
    errors = []
    for creator in ordered:
        channel = creator["persistentId"]
        status, body, observed, url = session.atom(channel)
        if status != 200:
            errors.append({"channelId": channel, "status": status})
            continue
        try:
            items = captures_from_atom(channel, body, observed, url, sha256(body).hexdigest())
        except (ValueError, ElementTree.ParseError) as failure:
            errors.append({"channelId": channel, "status": "parse", "message": str(failure)})
            continue
        for item in items:
            current = captures.get(item["id"])
            if current is None:
                captures[item["id"]] = item
                continue
            # Same material from a second path: one capture, one more discovery entry. The fuller
            # API record keeps content, reach and metadata; Atom adds its dated view count to the path.
            path = {**item["discovery"][0], "atomViews": _value(item["reach"], "viewCount"),
                    "atomContentSha256": item["contentHash"]}
            current["discovery"].append(path)
            if item["youtube"].get("isShort"):
                current["youtube"]["isShort"] = True
                current["youtube"]["shortsBasis"] = "atom_link"
    return errors


def replay(path=REPLAY):
    import gzip
    raw = Path(path).read_bytes()
    result = json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)
    for capture in result["captures"]:
        capture["mode"] = "replay"
        capture.setdefault("provenance", {})["fixture"] = Path(path).name
    result.setdefault("status", "ok")
    result.setdefault("resume", None)
    return result


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--budget", type=int, default=1500, help="twardy budżet jednostek tego przebiegu")
    parser.add_argument("--raw-dir", type=Path)
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--out", type=Path, help="zapis wyniku {creators,captures,sources,...}")
    parser.add_argument("--pause", type=float, default=0.3)
    parser.add_argument("--published-after", help="stały początek okna (ISO, Z)")
    parser.add_argument("--refresh", default="", help="metody bez cache, np. videos,channels")
    args = parser.parse_args()
    ttl = {method: 0 for method in args.refresh.split(",") if method}
    result = discover(Context(budget=args.budget, raw_dir=args.raw_dir, cache_dir=args.cache_dir, pause=args.pause,
                              published_after=args.published_after, cache_ttl=ttl))
    if args.out:
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "captures": len(result["captures"]), "creators": len(result["creators"]),
                      "quotaUsed": result["quota"]["used"], "resume": result["resume"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
