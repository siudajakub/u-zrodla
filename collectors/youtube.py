"""YouTube adapter: Data API v3 discovery with Atom as a second path for the same material.

Contract v2 (docs/lanes/2026-11-21-fable-h-kontrakt.md, section 3.3 and 3.8):
``discover(ctx)`` returns ``{creators, captures, sources, status, resume, quota}``.

Flow (live), rules of docs/MONITORING.md ("Oszczędne budowanie bazy kanałów YouTube"):
1. monitoring of known Polish channels from the adapter's persistent channel base (playlistItems, 1 unit per
   50 films; channels with a firm-promotion signal first), within ``monitor_share`` of the run budget;
2. discovery: search.list per query (Polish topic and promotional phrases first, Polish company names last),
   each query followed by its cheap enrichment (videos.list, channels.list for new channels); a channel gets a
   language label after its first read, non-Polish channels go to the skip list and cost nothing afterwards; a
   query without a new Polish channel in two runs moves to a sparser cycle;
3. uploads of the best new channels, then Atom (no quota) for the strongest ones.
Every observation adds one ``discovery[]`` entry; the same video from Atom and the API stays one capture with two
paths. The result carries ``report`` (units, new Polish channels per 100 units per query family, channel base
size, films waiting for transcription) and ``cursor`` (the channel base, persisted by H as it is).

API keys are read only outside the repository: INVESTWATCH_YT_KEY_FILES (paths separated by ":"; the next key
is used only after quotaExceeded of the current one, each key has its own ledger row identified by the first
8 characters of its SHA-256), or YOUTUBE_API_KEY / YOUTUBE_API_KEY_FILE, or the default file
~/.config/investwatch/youtube.key. A key never leaves the request: every stored URL has ``key=REDACTED``.
A missing key gives ``status="needs_key"`` without an exception.
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
from urllib.parse import urlencode, urlsplit
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
CACHE_TTL = {"search": 24 * 3600, "videos": 600, "channels": 3600, "playlistItems": 1800}
PACIFIC = ZoneInfo("America/Los_Angeles")
STATE_VERSION = 1
DAILY_KEY_UNITS = 10_000
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

# Default query set (owner's rules 2-3, docs/MONITORING.md): Polish topic and promotional phrases first
# (best yield of new Polish channels per 100 units), company names only in Polish wording with context and
# last (lowest yield). Bare "eToro", "Trading 212" and "Interactive Brokers" are out of the default set.
QUERIES = (
    ("topic", "inwestowanie", 2), ("topic", "giełda", 1), ("topic", "ETF", 1), ("topic", "akcje dywidendowe", 1),
    ("topic", "obligacje skarbowe", 1), ("topic", "IKE IKZE", 1), ("topic", "jak zacząć inwestować", 1),
    ("topic", "pasywny dochód inwestowanie", 1), ("topic", "portfel inwestycyjny", 1),
    ("topic", "konto maklerskie", 1), ("topic", "jak kupić akcje", 1), ("topic", "ETF na IKE", 1),
    ("topic", "dywidendy", 1), ("topic", "trading", 1), ("topic", "kontrakty CFD", 1),
    ("promo", "partnerem odcinka", 1), ("promo", "kod promocyjny konto maklerskie", 1),
    ("promo", "link w opisie darmowe akcje", 1), ("promo", "kod polecający giełda kryptowalut", 1),
    ("topic", "kryptowaluty", 1), ("topic", "bitcoin", 1), ("topic", "analiza techniczna", 1),
    ("topic", "forex", 1), ("topic", "złoto srebro inwestowanie", 1),
    ("brand", "XTB opinie", 1), ("brand", "konto maklerskie XTB", 1), ("brand", "Freedom24 opinie", 1),
    ("brand", "Saxo Bank opinie", 1), ("brand", "mBank eMakler", 1),
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


def key_id(key):
    """Ledger identity of a key: first 8 hex characters of the SHA-256 of the key text (never the key)."""
    return sha256(key.strip().encode("utf-8")).hexdigest()[:8]


def _read_key_file(path):
    try:
        resolved = Path(path).expanduser().resolve()
        if ROOT in resolved.parents:
            return None  # a key file inside the repository is refused
        return resolved.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def load_key(env=None):
    env = os.environ if env is None else env
    if env.get("YOUTUBE_API_KEY"):
        return env["YOUTUBE_API_KEY"].strip() or None
    return _read_key_file(env["YOUTUBE_API_KEY_FILE"] if env.get("YOUTUBE_API_KEY_FILE") else DEFAULT_KEY_FILE)


def load_keys(env=None):
    """Ordered, de-duplicated key list. INVESTWATCH_YT_KEY_FILES (paths separated by ':') lists several key files
    outside the repository; without it the single key of ``load_key`` (default ~/.config/investwatch/youtube.key)."""
    env = os.environ if env is None else env
    listed = (env.get("INVESTWATCH_YT_KEY_FILES") or "").strip()
    if not listed:
        key = load_key(None if env is os.environ else env)
        return [key] if key else []
    keys = []
    for path in listed.split(":"):
        key = _read_key_file(path.strip()) if path.strip() else None
        if key and key not in keys:
            keys.append(key)
    return keys


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

    Additive fields (2026-11-21, wave 3; all with defaults, v1 callers are unaffected):
    keys             explicit key list (tests); None/empty -> key, key_source or ``load_keys()``
                     (INVESTWATCH_YT_KEY_FILES); a next key is used only after quotaExceeded of the current one
    key_daily_units  daily unit limit of one key in the adapter's own per-key ledger (default 10000)
    state_dir        directory for the adapter's channel base (``channels.json``); None -> the base travels in
                     ``state["cursor"]`` and the result's ``cursor`` (H persists it as is)
    known_channels   extra rows {channelId|id, name, polish, subscribers, firmPromotionVideos} for the channel base
    monitor_share    share of the run budget for monitoring known Polish channels before discovery (default 0.4)
    monitor_channels limit of known channels read per run (default 200); monitor_min_hours: a channel read
                     more recently than that is not read again (default 6)
    sparse_after / sparse_every   a query without a new Polish channel in that many runs runs only every N-th run
    min_yield / yield_streak      stop discovery when new Polish channels per 100 search units stay below
                     ``min_yield`` in ``yield_streak`` consecutive queries (0 = off)
    Result adds ``cursor`` (channel base), ``report`` (units, yield per query family, channel base size, videos
    waiting for transcription) and ``quota.keys`` (one ledger row per key id).

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
    keys: tuple = ()
    key_daily_units: int = DAILY_KEY_UNITS
    state_dir: object = None
    known_channels: tuple = ()
    monitor_share: float = 0.4
    monitor_channels: int = 200
    monitor_min_hours: float = 6.0
    sparse_after: int = 2
    sparse_every: int = 4
    min_yield: float = 0.0
    yield_streak: int = 3

    def heartbeat(self):
        pass


def _ctx(value, name, default=None):
    return getattr(value, name, default)


class Session:
    """Quota ledger (one row per key), response cache and raw recording around one adapter run."""

    def __init__(self, ctx, keys, rows=None):
        keys = [keys] if isinstance(keys, str) else list(keys)
        self.ctx, self.keys = ctx, keys
        self.ids = [key_id(k) for k in keys]
        self.rows = {i: {"used": 0, "exhaustedAt": None, **(rows or {}).get(i, {})} for i in self.ids}
        self.daily = int(_ctx(ctx, "key_daily_units", DAILY_KEY_UNITS) or DAILY_KEY_UNITS)
        self.current = 0
        self.budget = int(_ctx(ctx, "budget", 0) or 0)
        self.used = 0
        self.ledger = []
        self.cache_dir = Path(ctx.cache_dir) if _ctx(ctx, "cache_dir") else None
        self.raw_dir = Path(ctx.raw_dir) if _ctx(ctx, "raw_dir") else None
        self.requests = 0
        self.exhausted = None  # set when every key is out of quota: no further API calls in this run
        self.reset_at = next_reset(ctx.clock())
        if self.raw_dir:
            self.raw_dir.mkdir(parents=True, exist_ok=True)
            index = self.raw_dir / "requests.jsonl"
            self.requests = len(index.read_text(encoding="utf-8").splitlines()) if index.exists() else 0
        self._advance()

    @property
    def key(self):
        return self.keys[self.current]

    @property
    def key_id(self):
        return self.ids[self.current]

    def _advance(self, at=None):
        """Move to the first key that is not exhausted (and below its daily limit); none -> exhausted."""
        for index in range(len(self.keys)):
            row = self.rows[self.ids[index]]
            if not row["exhaustedAt"] and row["used"] < self.daily:
                self.current = index
                return True
        self.exhausted = ("quotaExceeded", self.reset_at)
        return False

    def mark_exhausted(self, observed, reason):
        self.rows[self.key_id]["exhaustedAt"] = observed
        self.reset_at = next_reset(observed)
        self._advance()
        if self.exhausted:
            self.exhausted = (reason, self.reset_at)

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
               "cached": cached, "units": 0 if cached or method == "atom" else COST.get(method, 0),
               "keyId": None if cached or method == "atom" else self.key_id}
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
        if cached is not None:
            url = API + method + "?" + urlencode({**public, "key": self.key})
            status, body, observed = 200, cached["body"].encode(), cached["observedAt"]
            self._record(method, url, status, body, observed, True, label)
            return json.loads(body), observed, sha256(body).hexdigest(), redact(url)
        while True:
            if self.exhausted:
                raise QuotaExceeded(*self.exhausted)
            if self.rows[self.key_id]["used"] + cost > self.daily:  # own ledger: this key is spent for the day
                self.rows[self.key_id]["exhaustedAt"] = self.rows[self.key_id]["exhaustedAt"] or self.ctx.clock()
                self.reset_at = next_reset(self.ctx.clock())
                self._advance()
                continue
            if self.used + cost > self.budget:
                raise QuotaExceeded("budget", None)
            url = API + method + "?" + urlencode({**public, "key": self.key})
            if _ctx(self.ctx, "pause", 0):
                time.sleep(self.ctx.pause)
            self.ctx.heartbeat() if hasattr(self.ctx, "heartbeat") else None
            observed = self.ctx.clock()
            status, body = (self.ctx.fetch or http_fetch)(url)
            self.used += cost  # Google charges failed requests too.
            self.rows[self.key_id]["used"] += cost
            self.ledger.append({"method": method, "units": cost, "at": observed, "label": label, "status": status,
                                "keyId": self.key_id})
            self._record(method, url, status, body or b"", observed, False, label)
            if status == 200:
                self._cache_put(cache_key, body, observed)
                return json.loads(body), observed, sha256(body).hexdigest(), redact(url)
            reason = _error_reason(body)
            if status == 403 and reason in ("quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded"):
                self.mark_exhausted(observed, reason)  # next key (if any) takes over; the request is repeated
                continue
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


# ---------- persistent channel base (state of the adapter) ----------

def pacific_day(iso):
    return datetime.fromisoformat(iso).astimezone(PACIFIC).date().isoformat()


def _empty_db():
    return {"version": STATE_VERSION, "runs": 0, "channels": {}, "skipped": {}, "queries": {},
            "keyLedger": {"day": None, "keys": {}}}


def load_db(ctx, state):
    """Channel base: ``state_dir/channels.json`` when configured, else ``state["cursor"]`` (what H persists)."""
    saved = None
    directory = _ctx(ctx, "state_dir")
    if directory:
        try:
            saved = json.loads((Path(directory) / "channels.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            saved = None
    if saved is None and isinstance((state or {}).get("cursor"), dict):
        saved = json.loads(json.dumps(state["cursor"]))
    db = _empty_db()
    if isinstance(saved, dict) and saved.get("version") == STATE_VERSION:
        db.update(saved)
    return db


def save_db(ctx, db):
    directory = _ctx(ctx, "state_dir")
    if directory:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        tmp = directory / "channels.json.tmp"
        tmp.write_text(json.dumps(db, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(directory / "channels.json")


def _new_entry(cid, name, lang, basis, at, *, subs=None, subs_at=None, uploads=None, via=None, promo=False, firms=(), run=0):
    return {"name": name, "lang": lang, "langBasis": basis, "langAt": at, "firmPromo": bool(promo),
            "firms": sorted(firms), "subs": subs, "subsAt": subs_at or at, "uploads": uploads or "UU" + cid[2:],
            "firstSeen": at, "firstRun": run, "via": via, "lastRead": None, "newest": None}


def _file_language(row):
    polish = row.get("polish")
    if polish is True:
        return "pl", "baza wejściowa: kanał polski"
    if polish is False:
        return "other", "baza wejściowa: kanał niepolski"
    sample = row.get("languageSample") or {}
    if sample.get("total"):
        return ("pl" if sample.get("pl", 0) * 2 >= sample["total"] else "other"), "próbka języka z poprzedniego skanu"
    return "unknown", "język nieustalony"


def seed_db(db, rows, at, run):
    """Add known channels (rows of the report file or creator objects). Never overwrites a known label."""
    added = 0
    for row in rows or ():
        if not isinstance(row, dict) or row.get("platform", "youtube") != "youtube":
            continue
        cid = row.get("channelId") or row.get("persistentId") or str(row.get("id") or "").split(":", 1)[-1]
        if not CHANNEL_ID.fullmatch(cid or "") or cid in db["channels"] or cid in db["skipped"]:
            continue
        lang, basis = _file_language(row)
        name = row.get("name")
        if lang == "other":
            db["skipped"][cid] = {"name": name, "lang": "other", "basis": basis, "at": at, "via": "seed"}
            continue
        subs = row.get("subscribers")
        if subs is None:
            subs = _value(row.get("reach"), "subscriberCount")
        db["channels"][cid] = _new_entry(cid, name, lang, basis, at, subs=subs, subs_at=row.get("subscribersAsOf"),
                                         uploads=row.get("uploadsPlaylistId"), via="seed", run=run,
                                         promo=(row.get("firmPromotionVideos") or 0) > 0)
        added += 1
    return added


def label_language(languages, snippet):
    """Channel language label; the content of its films decides, not region or country. A single non-Polish
    sample is not enough to skip a channel (unless the channel itself declares another language)."""
    known = [x for x in languages if x and x != "unknown"]
    declared = str(snippet.get("defaultLanguage") or "").lower()
    if known:
        pl = sum(1 for x in known if x == "pl")
        basis = f"{pl}/{len(known)} filmów po polsku"
        if pl * 2 >= len(known):
            return "pl", basis
        if len(known) >= 2 or (declared and not declared.startswith("pl")):
            return "other", basis
        return "unknown", basis + "; jedna próbka, za mało na pominięcie"
    if declared.startswith("pl"):
        return "pl", "metadane kanału (defaultLanguage)"
    return "unknown", "brak próbki filmów"


def creator_from_db(cid, entry, captures, creators_discovery=None):
    first = _first_discovery(cid, captures)
    own = [c["youtube"].get("detectedLanguage") for c in captures.values() if c["creatorId"] == f"youtube:{cid}"]
    pl = sum(1 for x in own if x == "pl")
    observed = entry.get("subsAt") or entry.get("firstSeen")
    metric = ({"value": int(entry["subs"]), "state": "observed", "observedAt": observed, "source": "channel_base"}
              if entry.get("subs") is not None else
              {"value": None, "state": "unavailable", "observedAt": observed, "source": "channel_base"})
    return {"id": f"youtube:{cid}", "name": entry.get("name"), "platform": "youtube",
            "url": f"https://www.youtube.com/channel/{cid}", "handle": None,
            "discoveredVia": "baza kanałów adaptera", "status": "confirmed", "persistentId": cid,
            "country": None, "defaultLanguage": None, "uploadsPlaylistId": entry.get("uploads"),
            "reach": {"asOf": observed, "source": "channel_base", "primary": "subscriberCount",
                      "metrics": {"subscriberCount": metric}},
            "discoveries": [first] if first else [], "discovery": None,
            "firstDiscoveredAt": entry.get("firstSeen"),
            "languageSample": {"pl": pl, "total": len(own)}, "_language": f"baza kanałów: {entry.get('lang')}"}


def _learn(db, captures, at):
    """Update the channel base from this run's captures: firm-promotion signal and language of unknown channels."""
    langs = {}
    signals = {}
    for cid, capture in captures.items():
        channel = capture["creatorId"].split(":", 1)[1]
        signals[cid] = description_signals(capture.get("description"))
        langs.setdefault(channel, []).append((capture.get("youtube") or {}).get("detectedLanguage"))
        entry = db["channels"].get(channel)
        if entry and signals[cid]["firmEvidence"]:
            entry["firmPromo"] = True
            entry["firms"] = sorted(set(entry.get("firms") or ()) | {e["firm"] for e in signals[cid]["firmEvidence"]})
    for channel, entry in list(db["channels"].items()):
        if entry["lang"] == "unknown" and channel in langs:
            lang, basis = label_language(langs[channel], {})
            if lang != "unknown":
                entry.update(lang=lang, langBasis=basis, langAt=at)
                if lang == "other":
                    db["skipped"][channel] = {"name": entry.get("name"), "lang": "other", "basis": basis, "at": at,
                                              "via": entry.get("via")}
                    del db["channels"][channel]
    return signals


def _excerpt(text, needle, width=240):
    text = (text or "").replace("\n", " ")
    at = text.find(needle) if needle else -1
    start = max(0, at - width // 3) if at >= 0 else 0
    return text[start:start + width].strip()


def flag_candidates(captures, creators):
    """Polish films whose description carries a firm link or code, with no disclosure wording and the paid-promotion
    flag checked as false, ordered by reach (channel subscribers, then views)."""
    subs = {c["id"]: _value(c.get("reach"), "subscriberCount") for c in creators}
    rows = []
    for capture in captures:
        info = capture.get("youtube") or {}
        if info.get("languageStatus") != "in_scope" or info.get("paidPromotionFlag") is not False:
            continue
        signal = description_signals(capture.get("description"))
        if not signal["firmEvidence"] or signal["disclosure"]:
            continue
        evidence = signal["firmEvidence"][0]
        rows.append({"videoId": info.get("videoId") or capture["id"].split(":", 1)[1], "url": capture["url"],
                     "channel": capture.get("author"), "channelId": info.get("channelId"),
                     "subscribers": subs.get(capture["creatorId"]), "views": _value(capture.get("reach"), "viewCount"),
                     "isShort": info.get("isShort"), "firm": evidence["firm"], "evidence": evidence["kind"],
                     "quote": _excerpt(capture.get("description"), evidence["value"])})
    rows.sort(key=lambda r: (r["subscribers"] is None, -(r["subscribers"] or 0), -(r["views"] or 0), r["videoId"]))
    return rows


# ---------- one run ----------

def _resolve_keys(ctx):
    keys = [k for k in (_ctx(ctx, "keys") or ()) if k]
    if keys:
        return keys
    single = _ctx(ctx, "key")
    if single:
        return [single]
    source = _ctx(ctx, "key_source")
    if source:
        key = source()
        return [key] if key else []
    return load_keys()


def discover(ctx):
    """Run one YouTube scan. ``ctx`` follows the adapter contract (mode, state, budget, heartbeat)."""
    mode = _ctx(ctx, "mode", "live")
    clock = _ctx(ctx, "clock", utc_now)
    if mode == "replay":
        return replay()
    keys = _resolve_keys(ctx)
    observed = clock()
    state = _ctx(ctx, "state", {}) or {}
    if not keys:
        return {"creators": [], "captures": [], "status": "needs_key", "resume": state.get("resume"),
                "quota": {"used": 0, "limit": 0},
                "sources": [_source("needs_key", observed, error={"code": "needs_key", "message": "Brak klucza YouTube Data API v3."},
                                    next_step="Ustaw YOUTUBE_API_KEY_FILE lub INVESTWATCH_YT_KEY_FILES poza repozytorium.")]}
    db = load_db(ctx, state)
    run_no = int(db.get("runs") or 0) + 1
    db["runs"] = run_no
    seed_db(db, tuple(_ctx(ctx, "known_creators", ()) or ()) + tuple(_ctx(ctx, "known_channels", ()) or ()), observed, run_no)
    day = pacific_day(observed)
    ledger = db.get("keyLedger") or {}
    session = Session(ctx, keys, ledger.get("keys") if ledger.get("day") == day else {})
    queries = list(_ctx(ctx, "queries", QUERIES))
    resume = dict(state.get("resume") or {})
    start = int(resume.get("queryIndex", 0))
    # Day granularity keeps the window (and the cache key) stable within a day and across resumes.
    published_after = _ctx(ctx, "published_after") or (datetime.fromisoformat(observed) - timedelta(
        days=_ctx(ctx, "window_days", 180))).strftime("%Y-%m-%dT00:00:00Z")
    out = {"status": "ok", "error": None, "retry_at": None, "resume": None}

    def fail(exc, where):
        if isinstance(exc, QuotaExceeded):
            out["status"], out["retry_at"] = "rate_limited", exc.retry_at or out["retry_at"]
            out["error"] = out["error"] or {"code": exc.reason, "message": "Wyczerpany budżet przebiegu." if exc.reason == "budget"
                                            else f"Limit Data API ({exc.reason})."}
        else:
            out["status"] = "error" if out["status"] == "ok" else out["status"]
            out["error"] = out["error"] or {"code": exc.reason or str(exc.status), "message": str(exc)}

    captures, creators = {}, {}
    report = {"runNo": run_no, "at": observed, "monitoring": {}, "discovery": {"families": {}, "queries": [],
                                                                               "sparseSkipped": [], "stoppedEarly": None}}
    new_polish = []

    # 1. Monitoring of known Polish channels (cheap: playlistItems 1 unit per 50 films), promotion signal first.
    before = session.used
    try:
        report["monitoring"] = _monitor(session, ctx, db, captures, creators, published_after, observed)
    except (QuotaExceeded, ApiError) as exc:
        fail(exc, "monitoring")
        report["monitoring"] = {"interrupted": str(exc)}
    report["monitoring"]["units"] = session.used - before

    # 2. Discovery: per query search pages, then the cheap enrichment of that query's films and new channels.
    families, qreports, low = report["discovery"]["families"], report["discovery"]["queries"], 0
    discovery_before = session.used
    for index in range(start, len(queries)):
        if out["status"] != "ok":
            break
        kind, query, pages = queries[index]
        qstate = db["queries"].setdefault(f"{kind}|{query}", {"runs": 0, "dry": 0, "nextRun": 0, "lastNew": 0, "lastRun": None})
        resuming = index == start and bool(resume.get("pageToken"))
        if not resuming and int(qstate.get("nextRun") or 0) > run_no:
            report["discovery"]["sparseSkipped"].append(query)
            continue
        token = resume.get("pageToken") if index == start else None
        first_page = int(resume.get("page", 1)) if index == start and token else 1
        qhits, fresh, completed = {}, 0, False
        reserve = lambda: 1 + len(qhits) // 50 + 1 + len({h["snippet"]["channelId"] for h, _ in qhits.values()}) // 50 + 1
        try:
            for page in range(first_page, pages + 1):
                params = {"part": "snippet", "q": query, "type": "video", "maxResults": _ctx(ctx, "max_results", 50),
                          "regionCode": "PL", "relevanceLanguage": "pl", "publishedAfter": published_after,
                          "order": "relevance", "safeSearch": "none"}
                if token:
                    params["pageToken"] = token
                is_cached = session.cached("search", params)
                if not is_cached and session.remaining() < COST["search"] + reserve():
                    out["resume"] = {"queryIndex": index, "query": query, "pageToken": token, "page": page}
                    raise QuotaExceeded("budget")
                try:
                    data, at, sha, url = session.api("search", params, f"{kind} {query} p{page}")
                except QuotaExceeded:
                    out["resume"] = {"queryIndex": index, "query": query, "pageToken": token, "page": page}
                    raise
                fresh += 0 if is_cached else COST["search"]
                base = (page - 1) * params["maxResults"]
                for position, hit in enumerate(data.get("items") or [], 1):
                    video = (hit.get("id") or {}).get("videoId")
                    if not video or not VIDEO_ID.fullmatch(video):
                        continue
                    path = _path("data_api_search", at, sha, url, kind=kind, query=query, position=base + position,
                                 page=page, reason=f"wynik wyszukiwania ({kind})", units=COST["search"] if position == 1 else 0)
                    qhits.setdefault(video, (hit, []))[1].append(path)
                token = data.get("nextPageToken")
                if not token:
                    break
            completed = True
        except (QuotaExceeded, ApiError) as exc:
            fail(exc, "search")
        created, skipped_hits = [], 0
        try:
            created, skipped_hits = _enrich_query(session, qhits, captures, creators, db, run_no, kind, query)
        except (QuotaExceeded, ApiError) as exc:
            fail(exc, "enrich")
            if not out["resume"]:  # films of this query stay unread: start it again after the limit (search is cached)
                out["resume"] = {"queryIndex": index, "query": query, "page": first_page,
                                 "pageToken": resume.get("pageToken") if index == start else None}
        new_pl = [cid for cid, lang in created if lang == "pl"]
        new_polish.extend({"channelId": cid, "kind": kind, "query": query} for cid in new_pl)
        family = families.setdefault(kind, {"searchUnits": 0, "newPolishChannels": 0, "queries": 0})
        family["searchUnits"] += fresh
        family["newPolishChannels"] += len(new_pl)
        family["queries"] += 1
        qreports.append({"kind": kind, "query": query, "searchUnits": fresh, "videos": len(qhits), "skippedHits": skipped_hits,
                         "newChannels": len(created), "newPolishChannels": len(new_pl),
                         "per100": round(len(new_pl) * 100 / fresh, 2) if fresh else None, "completed": completed})
        if completed and fresh:
            qstate["runs"] = int(qstate.get("runs") or 0) + 1
            qstate["dry"] = 0 if new_pl else int(qstate.get("dry") or 0) + 1
            qstate["lastNew"], qstate["lastRun"] = len(new_pl), run_no
            qstate["nextRun"] = run_no + int(_ctx(ctx, "sparse_every", 4)) if qstate["dry"] >= int(_ctx(ctx, "sparse_after", 2)) else 0
            minimum = float(_ctx(ctx, "min_yield", 0) or 0)
            low = low + 1 if minimum and len(new_pl) * 100 / fresh < minimum else 0
            if minimum and low >= int(_ctx(ctx, "yield_streak", 3)):
                nxt = index + 1
                report["discovery"]["stoppedEarly"] = {
                    "reason": f"nowe polskie kanały na 100 j. poniżej {minimum} w {low} kolejnych zapytaniach", "afterQuery": query}
                out["resume"] = ({"queryIndex": nxt, "query": queries[nxt][1], "pageToken": None, "page": 1}
                                 if nxt < len(queries) else None)
                break
    for kind, family in families.items():
        family["per100"] = round(family["newPolishChannels"] * 100 / family["searchUnits"], 2) if family["searchUnits"] else None
    report["discovery"]["units"] = session.used - discovery_before

    # 3. Uploads of the best new channels, then Atom (no quota) for the strongest ones.
    skipped = db["skipped"]
    try:
        ordered = rank_channels([c for c in creators.values() if c["persistentId"] not in skipped])
        ordered = sorted(ordered, key=lambda c: 0 if (db["channels"].get(c["persistentId"]) or {}).get("firmPromo") else 1)
        _playlists(session, [c for c in ordered if c["persistentId"] not in report["monitoring"].get("readIds", ())]
                   [:_ctx(ctx, "playlist_channels", 8)], captures, creators)
    except (QuotaExceeded, ApiError) as exc:
        fail(exc, "playlists")
    ordered = rank_channels([c for c in creators.values() if c["persistentId"] not in skipped])
    ordered = sorted(ordered, key=lambda c: 0 if (db["channels"].get(c["persistentId"]) or {}).get("firmPromo") else 1)
    atom_errors = _atom(session, ordered[:_ctx(ctx, "atom_channels", 3)], captures)
    for capture in captures.values():
        creator = creators.get(capture["creatorId"])
        if creator is None:
            channel = capture["creatorId"].split(":", 1)[1]
            if channel in db["channels"]:
                creator = creators[capture["creatorId"]] = creator_from_db(channel, db["channels"][channel], captures)
        if creator is not None:
            creator["_foundViews"] = creator.get("_foundViews", 0) + (_value(capture.get("reach"), "viewCount") or 0)
    signals = _learn(db, captures, clock())
    ordered = rank_channels(list(creators.values()))
    ranked = rank_videos(list(captures.values()))
    for creator in ordered:
        creator.pop("_foundViews", None)
        creator.pop("_language", None)

    # 4. State, quota rows per key, run report.
    db["keyLedger"] = {"day": day, "keys": session.rows}
    this_run = {}
    for entry in session.ledger:
        this_run[entry["keyId"]] = this_run.get(entry["keyId"], 0) + entry["units"]
    quota = {"used": session.used, "limit": session.budget, "resetAt": next_reset(observed), "entries": session.ledger,
             "keys": [{"keyId": i, "day": day, "used": session.rows[i]["used"], "usedThisRun": this_run.get(i, 0),
                       "limit": session.daily, "exhaustedAt": session.rows[i]["exhaustedAt"]} for i in session.ids]}
    waiting = {"relationEvidence": 0, "firmName": 0, "shorts": 0}
    for capture in ranked:
        info = capture.get("youtube") or {}
        signal = signals.get(capture["id"]) or description_signals(capture.get("description"))
        if info.get("languageStatus") != "in_scope":
            continue
        if signal["firmEvidence"]:
            waiting["relationEvidence"] += 1
        elif signal["firms"]:
            waiting["firmName"] += 1
        else:
            continue
        waiting["shorts"] += 1 if info.get("isShort") else 0
    waiting["total"] = waiting["relationEvidence"] + waiting["firmName"]
    channels = db["channels"]
    report.update(units=session.used, unitsLimit=session.budget, keys=quota["keys"], newPolishChannelList=new_polish,
                  channelBase={"total": len(channels), "polish": sum(1 for e in channels.values() if e["lang"] == "pl"),
                               "unknown": sum(1 for e in channels.values() if e["lang"] == "unknown"),
                               "skippedNonPolish": len(db["skipped"]),
                               "withFirmPromotion": sum(1 for e in channels.values() if e["firmPromo"]),
                               "newPolishThisRun": len(new_polish)},
                  waitingForTranscript=waiting, videos=len(ranked),
                  shorts=sum(1 for c in ranked if (c.get("youtube") or {}).get("isShort")))
    report["monitoring"].pop("readIds", None)
    save_db(ctx, db)
    scope = {"queries": [{"kind": k, "query": q, "pages": p} for k, q, p in queries], "window": {"publishedAfter": published_after},
             "regionCode": "PL", "relevanceLanguage": "pl", "maxResults": _ctx(ctx, "max_results", 50)}
    status, error, retry_at = out["status"], out["error"], out["retry_at"]
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
            "resume": out["resume"], "retryAt": retry_at, "quota": quota, "cursor": db, "report": report}


def _monitor(session, ctx, db, captures, creators, window_start, at):
    """Read the uploads of known Polish channels (1 unit per 50 films) within the monitoring share of the budget.
    Order: with a firm-promotion signal first, then the rest; the longest unread first within each group."""
    cap = session.used + int(session.budget * float(_ctx(ctx, "monitor_share", 0.4)))
    min_age = timedelta(hours=float(_ctx(ctx, "monitor_min_hours", 6)))
    now = datetime.fromisoformat(at)
    due = [(cid, e) for cid, e in db["channels"].items() if e["lang"] in ("pl", "unknown")
           and (not e.get("lastRead") or now - datetime.fromisoformat(e["lastRead"]) >= min_age)]
    due.sort(key=lambda item: (0 if item[1]["firmPromo"] else 1, item[1].get("lastRead") or "", -(item[1].get("subs") or 0), item[0]))
    limit = int(_ctx(ctx, "monitor_channels", 200))
    info = {"channelsDue": len(due), "channelsRead": 0, "withSignalRead": 0, "newVideos": 0, "stopped": None, "errors": 0,
            "readIds": set()}
    pending, newest = {}, {}

    def flush(count):
        ids = list(pending)[:count]
        for chunk_start in range(0, len(ids), 50):
            chunk = ids[chunk_start:chunk_start + 50]
            (data, found_at, sha, url), flag = _videos_list(session, chunk, f"videos monitoring {len(captures)}")
            found = {item["id"]: item for item in data.get("items") or []}
            for video in chunk:
                paths = pending.pop(video)
                if video in found and f"youtube:{video}" not in captures:
                    captures[f"youtube:{video}"] = capture_from_video(found[video], found_at, sha, url, paths, flag)
                    info["newVideos"] += 1
        for cid in [c for c, vids in newest.items() if not any(v in pending for v in vids["ids"])]:
            entry = db["channels"].get(cid)
            if entry and newest[cid]["published"]:
                entry["newest"] = max(entry.get("newest") or "", newest[cid]["published"])
            del newest[cid]

    for cid, entry in due[:limit]:
        if session.used + 2 + len(pending) // 50 > cap:
            info["stopped"] = "budget"
            break
        try:
            data, read_at, sha, url = session.api("playlistItems", {"part": "contentDetails", "playlistId": entry["uploads"],
                                                                    "maxResults": 50}, f"monitor {cid}")
        except ApiError as failure:
            info["errors"] += 1
            entry["lastError"] = {"at": at, "code": failure.reason or str(failure.status)}
            entry["lastRead"] = at
            continue
        entry["lastRead"] = read_at
        entry.pop("lastError", None)
        info["channelsRead"] += 1
        info["withSignalRead"] += 1 if entry["firmPromo"] else 0
        info["readIds"].add(cid)
        row = {"ids": [], "published": entry.get("newest")}
        for position, item in enumerate(data.get("items") or [], 1):
            details = item.get("contentDetails") or {}
            video, published = details.get("videoId"), details.get("videoPublishedAt")
            if not video or not VIDEO_ID.fullmatch(video):
                continue
            if published and (published < window_start or (entry.get("newest") and published <= entry["newest"])):
                continue
            if f"youtube:{video}" in captures:
                continue
            pending.setdefault(video, []).append(_path(
                "data_api_playlist", read_at, sha, url, position=position, page=1, reason="monitoring znanego kanału",
                units=COST["playlistItems"] if position == 1 else 0))
            row["ids"].append(video)
            row["published"] = max(row["published"] or "", published or "")
        newest[cid] = row
        if len(pending) >= 50:
            flush(50)
    try:
        flush(len(pending))
    except QuotaExceeded as exhausted:
        if exhausted.reason != "budget":
            raise
        info["stopped"] = info["stopped"] or "budget"
    for video_id, capture in captures.items():
        channel = capture["creatorId"].split(":", 1)[1]
        if channel in db["channels"] and capture["creatorId"] not in creators:
            creators[capture["creatorId"]] = creator_from_db(channel, db["channels"][channel], captures)
    return info


def _videos_list(session, ids, label):
    parts = "snippet,statistics,contentDetails,status,paidProductPlacementDetails"
    try:
        return session.api("videos", {"part": parts, "id": ",".join(ids), "maxResults": 50}, label), True
    except ApiError as failure:
        if failure.status != 400:
            raise
        return session.api("videos", {"part": "snippet,statistics,contentDetails,status", "id": ",".join(ids),
                                      "maxResults": 50}, label + " bez flagi"), False


def _enrich_query(session, hits, captures, creators, db, run_no, kind, query):
    """Cheap enrichment of one query's results: films of channels on the skip list are dropped without spending,
    films already captured only gain a path, the rest go through videos.list and new channels through channels.list."""
    fresh, skipped = {}, 0
    for video, (hit, paths) in hits.items():
        channel = (hit.get("snippet") or {}).get("channelId")
        if channel in db["skipped"]:
            skipped += 1
        elif f"youtube:{video}" in captures:
            captures[f"youtube:{video}"]["discovery"].extend(paths)
        else:
            fresh[video] = (hit, paths)
    ids = list(fresh)
    for start in range(0, len(ids), 50):
        chunk = ids[start:start + 50]
        (data, at, sha, url), flag = _videos_list(session, chunk, f"videos {kind} {query} {start}")
        found = {item["id"]: item for item in data.get("items") or []}
        for video in chunk:
            hit, paths = fresh[video]
            if video in found:
                captures[f"youtube:{video}"] = capture_from_video(found[video], at, sha, url, paths, flag)
            else:
                captures[f"youtube:{video}"] = capture_from_search_only(
                    hit, at, sha, url, paths, "videos.list nie zwrócił filmu: usunięty, prywatny lub zablokowany")
    channels = {c["creatorId"].split(":", 1)[1] for v, c in captures.items() if v[len("youtube:"):] in fresh}
    created = _channels(session, channels, captures, creators, db, run_no, f"{kind}: {query}")
    return created, skipped


def _channels(session, channel_ids, captures, creators, db, run_no, via):
    """Known channels come from the base (no spending); new ones from channels.list get a language label from the
    content of their films. Non-Polish channels go to the skip list and are not read again."""
    pending = sorted(c for c in channel_ids if CHANNEL_ID.fullmatch(c or "") and f"youtube:{c}" not in creators)
    for cid in [c for c in pending if c in db["channels"]]:
        creators[f"youtube:{cid}"] = creator_from_db(cid, db["channels"][cid], captures)
    pending = [c for c in pending if c not in db["channels"]]
    created = []
    for start in range(0, len(pending), 50):
        data, at, sha, url = session.api("channels", {"part": "snippet,statistics,contentDetails",
                                                      "id": ",".join(pending[start:start + 50]), "maxResults": 50},
                                         f"channels {start}")
        for item in data.get("items") or []:
            snippet = item.get("snippet") or {}
            first = _first_discovery(item["id"], captures)
            languages = [c["youtube"].get("detectedLanguage") for c in captures.values() if c["creatorId"] == f"youtube:{item['id']}"]
            pl = sum(1 for x in languages if x == "pl")
            reach = channel_reach(item, at)
            uploads = (item.get("contentDetails") or {}).get("relatedPlaylists", {}).get("uploads")
            creators[f"youtube:{item['id']}"] = {
                "id": f"youtube:{item['id']}", "name": snippet.get("title"), "platform": "youtube",
                "url": f"https://www.youtube.com/channel/{item['id']}", "handle": snippet.get("customUrl"),
                "discoveredVia": "YouTube Data API: search.list", "status": "confirmed", "persistentId": item["id"],
                "country": snippet.get("country"), "defaultLanguage": snippet.get("defaultLanguage"),
                "uploadsPlaylistId": uploads,
                "reach": reach, "discoveries": [first] if first else [],
                "discovery": ({"query": first["query"], "rank": first["position"], "sourceUrl": first["sourceUrl"],
                               "responseSha256": first["responseSha256"], "observedAt": first["observedAt"]} if first else None),
                "firstDiscoveredAt": first["observedAt"] if first else at,
                "languageSample": {"pl": pl, "total": len(languages)}, "_language": f"{pl}/{len(languages)} filmów po polsku",
            }
            lang, basis = label_language(languages, snippet)
            subs = _value(reach, "subscriberCount")
            if lang == "other":
                db["skipped"][item["id"]] = {"name": snippet.get("title"), "lang": "other", "basis": basis, "at": at, "via": via}
            else:
                db["channels"][item["id"]] = _new_entry(item["id"], snippet.get("title"), lang, basis, at, subs=subs,
                                                        uploads=uploads, via=via, run=run_no)
            created.append((item["id"], lang))
    return created


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
    parser.add_argument("--state-dir", type=Path, help="stan adaptera: channels.json (baza kanałów, księga kluczy)")
    parser.add_argument("--known-channels", type=Path, help="JSON z listą znanych kanałów (channelId, name, polish, subscribers)")
    parser.add_argument("--seed-used", type=int, default=0, help="jednostki już zużyte dziś przez pierwszy klucz (do księgi)")
    parser.add_argument("--out", type=Path, help="zapis wyniku {creators,captures,sources,...}")
    parser.add_argument("--out-dir", type=Path, help="zapis report.json i candidates.json")
    parser.add_argument("--pause", type=float, default=0.3)
    parser.add_argument("--published-after", help="stały początek okna (ISO, Z)")
    parser.add_argument("--refresh", default="", help="metody bez cache, np. videos,channels")
    parser.add_argument("--monitor-share", type=float, default=0.4)
    parser.add_argument("--monitor-channels", type=int, default=200)
    parser.add_argument("--playlist-channels", type=int, default=8)
    parser.add_argument("--atom-channels", type=int, default=3)
    parser.add_argument("--min-yield", type=float, default=0.0, help="nowe polskie kanały na 100 j.; 0 = bez przerwania")
    args = parser.parse_args()
    ttl = {method: 0 for method in args.refresh.split(",") if method}
    known = tuple(json.loads(args.known_channels.read_text(encoding="utf-8"))) if args.known_channels else ()
    if args.seed_used and args.state_dir:
        keys = load_keys()
        if keys:
            db = load_db(Context(state_dir=args.state_dir), {})
            day = pacific_day(utc_now())
            rows = db["keyLedger"]["keys"] if db["keyLedger"].get("day") == day else {}
            row = rows.setdefault(key_id(keys[0]), {"used": 0, "exhaustedAt": None})
            row["used"] = max(row["used"], args.seed_used)
            db["keyLedger"] = {"day": day, "keys": rows}
            save_db(Context(state_dir=args.state_dir), db)
    result = discover(Context(budget=args.budget, raw_dir=args.raw_dir, cache_dir=args.cache_dir, pause=args.pause,
                              published_after=args.published_after, cache_ttl=ttl, state_dir=args.state_dir,
                              known_channels=known, monitor_share=args.monitor_share, monitor_channels=args.monitor_channels,
                              playlist_channels=args.playlist_channels, atom_channels=args.atom_channels,
                              min_yield=args.min_yield))
    if args.out:
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if args.out_dir and "report" in result:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        (args.out_dir / "report.json").write_text(json.dumps(result["report"], ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        (args.out_dir / "candidates.json").write_text(json.dumps(flag_candidates(result["captures"], result["creators"]),
                                                                 ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "captures": len(result["captures"]), "creators": len(result["creators"]),
                      "quotaUsed": result["quota"]["used"], "resume": result["resume"],
                      "channelBase": (result.get("report") or {}).get("channelBase")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
