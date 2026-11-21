"""Poll a fixed list of public YouTube Atom feeds and TikTok profile embeds."""

import argparse
from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import date, datetime, time as day_time, timedelta, timezone
from email.utils import parsedate_to_datetime
import fcntl
from hashlib import sha256
from html.parser import HTMLParser
from http.client import HTTPException
import json
import os
from pathlib import Path
import re
import sqlite3
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from xml.etree import ElementTree
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


CONFIG_PATH = Path(__file__).with_suffix(".json")
YOUTUBE = "https://www.youtube.com"
TIKTOK = "https://www.tiktok.com"
ATOM = "{http://www.w3.org/2005/Atom}"
YT = "{http://www.youtube.com/xml/schemas/2015}"
MEDIA = "{http://search.yahoo.com/mrss/}"
TIKTOK_STATE_ID = "__FRONTITY_CONNECT_STATE__"
MAX_POSTS = 50
MAX_QUOTE = 120
SIGNALS = {
    "sponsor": re.compile(
        r"(?i)\b(?:sponsor\w*|partner(?:em|stwo|stwa|zy)?|współprac\w*|"
        r"reklam\w*|kod\s+(?:rabatowy|polecający|promocyjny)|paid partnership)\b|#ad\b"
    ),
    "risk": re.compile(
        r"(?i)\b(?:ryzyk\w*|strat\w*|utrata kapitału|risk\w*|lose\s+(?:money|capital))\b"
    ),
}


@dataclass(frozen=True)
class Source:
    platform: str
    account: str
    label: str

    @property
    def key(self):
        return f"{self.platform}:{self.account}"

    @property
    def profile_url(self):
        if self.platform == "youtube":
            return f"{YOUTUBE}/channel/{self.account}"
        return f"{TIKTOK}/@{self.account}"

    @property
    def feed_url(self):
        if self.platform == "youtube":
            return f"{YOUTUBE}/feeds/videos.xml?channel_id={self.account}"
        return f"{TIKTOK}/embed/@{self.account}"

    @property
    def scope(self):
        return "youtube_atom_title_description" if self.platform == "youtube" else "tiktok_embed_caption"


@dataclass(frozen=True)
class Config:
    sources: tuple[Source, ...]
    request_timeout_seconds: int
    max_response_bytes: int
    retry_fallback_seconds: int


@dataclass(frozen=True)
class Post:
    id: str
    url: str
    text: str
    title: str | None = None
    published_at: str | None = None
    published_basis: str | None = None


@dataclass(frozen=True)
class Fetch:
    status: int
    body: bytes = b""
    retry_after: str | None = None


class ReadError(ValueError):
    """The public response did not provide a reliable reading."""


class BusyError(RuntimeError):
    """Another process holds the database's run lock."""


def load_config(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Configuration must be a JSON object.")
    limits = {
        "request_timeout_seconds": (1, 60),
        "max_response_bytes": (1, 4 * 1024 * 1024),
        "retry_fallback_seconds": (60, 7 * 24 * 3600),
    }
    for key, (minimum, maximum) in limits.items():
        value = data.get(key)
        if type(value) is not int or not minimum <= value <= maximum:
            raise ValueError(f"{key} must be an integer between {minimum} and {maximum}.")
    entries = data.get("sources")
    if not isinstance(entries, list) or not 1 <= len(entries) <= 20:
        raise ValueError("Configure between 1 and 20 public sources.")
    sources = {}
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"platform", "account", "label"}:
            raise ValueError("Each source requires platform, account and label.")
        if not all(isinstance(value, str) for value in entry.values()):
            raise ValueError("Source fields must be strings.")
        source = Source(**entry)
        label = source.label.strip()
        if source.platform == "youtube":
            valid_account = re.fullmatch(r"UC[\w-]{22}", source.account, re.ASCII)
        elif source.platform == "tiktok":
            valid_account = re.fullmatch(r"[a-zA-Z0-9_][a-zA-Z0-9_.]{0,31}", source.account)
            source = Source(source.platform, source.account.lower(), label)
        else:
            valid_account = False
        if not valid_account or not 1 <= len(label) <= 80 or source.key in sources:
            raise ValueError("Invalid or duplicate source.")
        sources[source.key] = source
    return Config(tuple(sources.values()), **{key: data[key] for key in limits})


def timestamp(value):
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds")


def iso_datetime(value):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        value = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        return value.astimezone(timezone.utc) if value.tzinfo is not None else None
    except (ValueError, OverflowError):
        return None


def tiktok_published(item):
    for field in ("createTime", "create_time", "publishedAt", "published_at"):
        value = item.get(field)
        if type(value) is int or (isinstance(value, str) and re.fullmatch(r"[0-9]{10,13}", value)):
            number = int(value)
            seconds = number / 1000 if number >= 10**12 else number
            try:
                date = datetime.fromtimestamp(seconds, tz=timezone.utc)
            except (ValueError, OverflowError, OSError):
                continue
        else:
            date = iso_datetime(value)
        if date is not None and 2016 <= date.year < 2100:
            return timestamp(date), f"tiktok.embed.{field}"
    return None, None


def parse_youtube(source, body):
    if re.search(br"<!\s*(?:DOCTYPE|ENTITY)", body, re.IGNORECASE):
        raise ReadError("Atom returned an unexpected document declaration.")
    try:
        feed = ElementTree.fromstring(body)
    except ElementTree.ParseError:
        raise ReadError("Could not read the Atom response.") from None
    feed_channel = feed.findtext(f"{YT}channelId")
    if feed.tag != f"{ATOM}feed" or feed_channel not in (source.account, source.account[2:]):
        raise ReadError("Atom returned an unexpected channel.")
    posts = {}
    entries = feed.findall(f"{ATOM}entry")
    if not 1 <= len(entries) <= MAX_POSTS:
        raise ReadError("Atom returned an empty or oversized list of publications.")
    for entry in entries:
        post_id = entry.findtext(f"{YT}videoId", "")
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", post_id):
            raise ReadError("Atom returned an invalid video ID.")
        if entry.findtext(f"{YT}channelId") != source.account:
            raise ReadError("Atom returned a video from a different channel.")
        text = entry.findtext(f"{MEDIA}group/{MEDIA}description")
        title = entry.findtext(f"{ATOM}title")
        if text is None or title is None:
            raise ReadError("Atom omitted a title or description field.")
        published = iso_datetime(entry.findtext(f"{ATOM}published"))
        post = Post(
            post_id,
            f"{YOUTUBE}/watch?v={post_id}",
            text,
            title=title,
            published_at=timestamp(published) if published else None,
            published_basis="youtube.atom.published" if published else None,
        )
        add_post(posts, post)
    return list(posts.values())


class TikTokEmbed(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.source = source
        self.links = set()
        self.state_parts = []
        self.inside_state = False
        self.state_count = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script" and attrs.get("id") == TIKTOK_STATE_ID:
            self.state_count += 1
            self.inside_state = attrs.get("type") == "application/json"
        if tag == "a" and attrs.get("href"):
            try:
                url = urlsplit(urljoin(self.source.feed_url, attrs["href"]))
            except ValueError:
                return
            if url.scheme == "https" and url.netloc.lower() == "www.tiktok.com":
                account = re.escape(self.source.account)
                video = re.fullmatch(rf"/@{account}/video/([0-9]{{15,22}})/?", url.path, re.IGNORECASE)
                if video:
                    self.links.add(video[1])

    def handle_data(self, data):
        if self.inside_state:
            self.state_parts.append(data)

    def handle_endtag(self, tag):
        if tag == "script":
            self.inside_state = False


def parse_tiktok(source, body):
    parser = TikTokEmbed(source)
    try:
        parser.feed(body.decode("utf-8"))
        parser.close()
        if parser.state_count != 1:
            raise ValueError
        state = json.loads("".join(parser.state_parts))
        page = state["source"]["data"][urlsplit(source.feed_url).path]
        user = page["userInfo"]
        items = page["videoList"]
    except (KeyError, TypeError, ValueError, RecursionError):
        raise ReadError("Could not read the TikTok profile embed.") from None
    handle = user.get("uniqueId") if isinstance(user, dict) else None
    if not isinstance(handle, str) or handle.lower() != source.account:
        raise ReadError("TikTok returned an unexpected profile.")
    if user.get("privateAccount") is not False or page.get("isReady") is not True or page.get("isError"):
        raise ReadError("TikTok did not return an accessible public profile.")
    if not isinstance(items, list) or not 1 <= len(items) <= MAX_POSTS:
        raise ReadError("TikTok returned an empty or oversized list of publications.")
    posts = {}
    for item in items:
        if not isinstance(item, dict):
            raise ReadError("TikTok returned invalid video metadata.")
        if item.get("privateItem") is not False:
            continue
        post_id = item.get("id")
        author = item.get("authorUniqueId")
        text = item.get("desc")
        if (not isinstance(post_id, str) or not re.fullmatch(r"[0-9]{15,22}", post_id)
                or not isinstance(author, str) or author.lower() != source.account
                or not isinstance(text, str) or post_id not in parser.links):
            raise ReadError("TikTok video metadata did not match the public link.")
        try:
            text.encode("utf-8")
        except UnicodeError:
            raise ReadError("TikTok returned an invalid caption encoding.") from None
        published, basis = tiktok_published(item)
        add_post(posts, Post(
            post_id,
            f"{source.profile_url}/video/{post_id}",
            text,
            published_at=published,
            published_basis=basis,
        ))
    if not posts or parser.links != posts.keys():
        raise ReadError("TikTok returned incomplete public video metadata.")
    return list(posts.values())


def add_post(posts, post):
    if posts.setdefault(post.id, post) != post:
        raise ReadError("The feed returned conflicting copies of the same video ID.")


def excerpts(text):
    quotes = {}
    for kind, pattern in SIGNALS.items():
        for line in text.splitlines():
            line = line.strip()
            match = pattern.search(line)
            if match:
                start = max(0, match.start() - 24)
                quotes[kind] = line[start:start + MAX_QUOTE].strip()
                break
    if text.strip() and not quotes:
        quotes["fallback"] = text.strip()[:MAX_QUOTE].rstrip()
    return quotes


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


def fetch_source(source, config):
    request = Request(source.feed_url, headers={"User-Agent": "InvestWatch-SourceMonitor/1.0"})
    opener = build_opener(NoRedirect)
    try:
        with opener.open(request, timeout=config.request_timeout_seconds) as response:
            if response.status != 200:
                return Fetch(response.status)
            deadline = time.monotonic() + config.request_timeout_seconds
            body = bytearray()
            while time.monotonic() < deadline:
                chunk = response.read1(min(65536, config.max_response_bytes + 1 - len(body)))
                if not chunk:
                    return Fetch(response.status, bytes(body))
                body.extend(chunk)
                if len(body) > config.max_response_bytes:
                    raise ReadError("The response exceeded the configured size limit.")
            raise TimeoutError
    except HTTPError as error:
        with error:
            return Fetch(error.code, retry_after=error.headers.get("Retry-After"))


def next_retry(now, header, fallback):
    if header:
        header = header.strip()
        try:
            if re.fullmatch(r"[0-9]{1,12}", header):
                date = now + timedelta(seconds=int(header))
            else:
                date = parsedate_to_datetime(header)
                if date.tzinfo is None:
                    date = date.replace(tzinfo=timezone.utc)
            if date > now:
                return timestamp(date)
        except (ValueError, OverflowError, TypeError):
            pass
    return timestamp(now + timedelta(seconds=fallback))


SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    sources_expected INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS source_checks (
    run_id INTEGER NOT NULL REFERENCES runs(id),
    source_key TEXT NOT NULL,
    platform TEXT NOT NULL,
    label TEXT NOT NULL,
    profile_url TEXT NOT NULL,
    feed_url TEXT NOT NULL,
    scope TEXT NOT NULL,
    started_at TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    status TEXT NOT NULL,
    http_status INTEGER,
    error TEXT,
    response_sha256 TEXT,
    retry_at TEXT,
    found INTEGER NOT NULL DEFAULT 0,
    first_observations INTEGER NOT NULL DEFAULT 0,
    new_publications INTEGER NOT NULL DEFAULT 0,
    changed INTEGER NOT NULL DEFAULT 0,
    unchanged INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (run_id, source_key)
);
CREATE INDEX IF NOT EXISTS source_check_history ON source_checks (source_key, run_id DESC);

CREATE TABLE IF NOT EXISTS cooldowns (
    scope TEXT PRIMARY KEY,
    retry_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS posts (
    platform TEXT NOT NULL,
    post_id TEXT NOT NULL,
    first_observed_at TEXT NOT NULL,
    last_observed_at TEXT NOT NULL,
    published_at TEXT,
    published_basis TEXT,
    latest_version INTEGER NOT NULL,
    PRIMARY KEY (platform, post_id)
);

CREATE TABLE IF NOT EXISTS post_versions (
    platform TEXT NOT NULL,
    post_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    run_id INTEGER NOT NULL,
    source_key TEXT NOT NULL,
    event TEXT NOT NULL,
    url TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    published_at TEXT,
    published_basis TEXT,
    text_sha256 TEXT NOT NULL,
    text_length INTEGER NOT NULL,
    title_sha256 TEXT,
    excerpts_json TEXT NOT NULL,
    PRIMARY KEY (platform, post_id, version),
    FOREIGN KEY (platform, post_id) REFERENCES posts(platform, post_id),
    FOREIGN KEY (run_id, source_key) REFERENCES source_checks(run_id, source_key)
);

CREATE TABLE IF NOT EXISTS observations (
    run_id INTEGER NOT NULL,
    source_key TEXT NOT NULL,
    platform TEXT NOT NULL,
    post_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    published_at TEXT,
    published_basis TEXT,
    PRIMARY KEY (run_id, source_key, platform, post_id),
    FOREIGN KEY (run_id, source_key) REFERENCES source_checks(run_id, source_key),
    FOREIGN KEY (platform, post_id, version) REFERENCES post_versions(platform, post_id, version)
);
CREATE INDEX IF NOT EXISTS source_check_observed ON source_checks (observed_at);

CREATE TABLE IF NOT EXISTS post_texts (
    platform TEXT NOT NULL,
    post_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    run_id INTEGER NOT NULL,
    source_key TEXT NOT NULL,
    text TEXT NOT NULL,
    title TEXT,
    PRIMARY KEY (platform, post_id, version),
    FOREIGN KEY (platform, post_id, version) REFERENCES post_versions(platform, post_id, version),
    FOREIGN KEY (run_id, source_key) REFERENCES source_checks(run_id, source_key)
);
"""


@contextmanager
def run_lock(path):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock = os.open(path.with_name(f"{path.name}.lock"), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise BusyError from None
        yield
    finally:
        os.close(lock)


def open_database(path):
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        if os.fstat(descriptor).st_mode & 0o077:
            raise PermissionError("Set owner-only permissions on the monitor database.")
    finally:
        os.close(descriptor)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA foreign_keys = ON")
        db.executescript(SCHEMA)
    except BaseException:
        db.close()
        raise
    return db


def store_post(db, source, run_id, post, observed_at, previous_check):
    text_hash = sha256(post.text.encode("utf-8")).hexdigest()
    title_hash = sha256(post.title.encode("utf-8")).hexdigest() if post.title is not None else None
    key = (source.platform, post.id)
    previous = db.execute(
        """SELECT p.latest_version, v.text_sha256, v.title_sha256
           FROM posts p JOIN post_versions v
             ON v.platform = p.platform AND v.post_id = p.post_id AND v.version = p.latest_version
           WHERE p.platform = ? AND p.post_id = ?""",
        key,
    ).fetchone()
    if previous:
        changed = (previous["text_sha256"], previous["title_sha256"]) != (text_hash, title_hash)
        version = previous["latest_version"] + int(changed)
        db.execute(
            """UPDATE posts SET last_observed_at = ?, latest_version = ?,
                   published_at = coalesce(?, published_at), published_basis = coalesce(?, published_basis)
               WHERE platform = ? AND post_id = ?""",
            (observed_at, version, post.published_at, post.published_basis, *key),
        )
        if not changed:
            return "unchanged", version
        event = "changed"
    else:
        event = "first_observation"
        if previous_check and post.published_at and previous_check <= post.published_at <= observed_at:
            event = "new_publication"
        version = 1
        db.execute(
            """INSERT INTO posts (platform, post_id, first_observed_at, last_observed_at,
                                  published_at, published_basis, latest_version)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (*key, observed_at, observed_at, post.published_at, post.published_basis, version),
        )
    evidence = excerpts(post.text)
    if not evidence and post.title:
        evidence = {"title_fallback": post.title.strip()[:MAX_QUOTE].rstrip()}
    db.execute(
        """INSERT INTO post_versions (platform, post_id, version, run_id, source_key, event, url,
                                      observed_at, published_at, published_basis,
                                      text_sha256, text_length, title_sha256, excerpts_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (*key, version, run_id, source.key, event, post.url, observed_at, post.published_at,
         post.published_basis, text_hash, len(post.text), title_hash, json.dumps(evidence, ensure_ascii=False)),
    )
    return event, version


def check_source(db, run_id, source, config, fetch, clock, keep_text):
    now = clock()
    started_at = timestamp(now)
    waiting = db.execute(
        "SELECT max(retry_at) FROM cooldowns WHERE scope IN (?, ?) AND retry_at > ?",
        (source.key, source.platform, started_at),
    ).fetchone()[0]
    status, error, retry_at = "ok", None, None
    response = None
    response_hash = None
    posts = []
    cooldown_scope = None
    if waiting:
        status, retry_at = "cooldown", waiting
    else:
        try:
            response = fetch(source, config)
            if response.status in (403, 429):
                status = "forbidden" if response.status == 403 else "rate_limited"
                cooldown_scope = source.key if response.status == 403 else source.platform
                retry_at = next_retry(clock(), response.retry_after, config.retry_fallback_seconds)
            elif response.status != 200:
                status = "http_error"
            else:
                parse = parse_youtube if source.platform == "youtube" else parse_tiktok
                posts = parse(source, response.body)
                response_hash = sha256(response.body).hexdigest()
        except ReadError as problem:
            status, error = "read_error", str(problem)
        except (URLError, HTTPException, OSError) as problem:
            status, error = "network_error", type(problem).__name__
    observed_at = timestamp(clock())
    counters = dict(first_observation=0, new_publication=0, changed=0, unchanged=0)
    with db:
        previous = db.execute(
            """SELECT started_at FROM source_checks
               WHERE source_key = ? AND status = 'ok' ORDER BY run_id DESC LIMIT 1""",
            (source.key,),
        ).fetchone()
        db.execute(
            """INSERT INTO source_checks
               (run_id, source_key, platform, label, profile_url, feed_url, scope, started_at,
                observed_at, status, http_status, error, response_sha256, retry_at, found)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (run_id, source.key, source.platform, source.label, source.profile_url, source.feed_url,
             source.scope, started_at, observed_at, status, response.status if response else None,
             error, response_hash, retry_at, len(posts)),
        )
        if cooldown_scope:
            db.execute(
                """INSERT INTO cooldowns (scope, retry_at) VALUES (?, ?)
                   ON CONFLICT(scope) DO UPDATE SET retry_at = max(retry_at, excluded.retry_at)""",
                (cooldown_scope, retry_at),
            )
        if status == "ok":
            for post in posts:
                event, version = store_post(db, source, run_id, post, observed_at, previous[0] if previous else None)
                db.execute(
                    """INSERT INTO observations
                       (run_id, source_key, platform, post_id, version, published_at, published_basis)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (run_id, source.key, source.platform, post.id, version, post.published_at, post.published_basis),
                )
                if keep_text:
                    db.execute(
                        """INSERT INTO post_texts (platform, post_id, version, run_id, source_key, text, title)
                           VALUES (?, ?, ?, ?, ?, ?, ?)
                           ON CONFLICT (platform, post_id, version) DO NOTHING""",
                        (source.platform, post.id, version, run_id, source.key, post.text, post.title),
                    )
                counters[event] += 1
            db.execute(
                """UPDATE source_checks SET first_observations = :first_observation,
                       new_publications = :new_publication, changed = :changed, unchanged = :unchanged
                   WHERE run_id = :run_id AND source_key = :source_key""",
                {**counters, "run_id": run_id, "source_key": source.key},
            )
    return status


def utc_now():
    return datetime.now(timezone.utc)


def run(path, config, fetch=fetch_source, clock=utc_now, *, keep_text=False):
    path = path.resolve()
    with run_lock(path), closing(open_database(path)) as db:
        with db:
            now = timestamp(clock())
            db.execute("UPDATE runs SET finished_at = ?, status = 'interrupted' WHERE status = 'running'", (now,))
            run_id = db.execute(
                "INSERT INTO runs (started_at, status, sources_expected) VALUES (?, 'running', ?)",
                (now, len(config.sources)),
            ).lastrowid
        try:
            results = [
                check_source(db, run_id, source, config, fetch, clock, keep_text)
                for source in config.sources
            ]
            successes = results.count("ok")
            if successes == len(results):
                status = "ok"
            elif successes:
                status = "partial"
            else:
                status = "failed"
        except BaseException:
            with db:
                db.execute("UPDATE runs SET finished_at = ?, status = 'interrupted' WHERE id = ?",
                           (timestamp(clock()), run_id))
            raise
        with db:
            db.execute("UPDATE runs SET finished_at = ?, status = ? WHERE id = ?",
                       (timestamp(clock()), status, run_id))
        return run_report(db, run_id)


def run_report(db, run_id=None):
    if run_id is None:
        current = db.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 1").fetchone()
    else:
        current = db.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    if current is None:
        return {"status": "no_runs", "sources": []}
    checks = db.execute(
        """SELECT sc.*, (
               SELECT s.observed_at FROM source_checks s
               WHERE s.source_key = sc.source_key AND s.status = 'ok' AND s.run_id <= sc.run_id
               ORDER BY s.run_id DESC LIMIT 1
           ) AS last_success_at
           FROM source_checks sc WHERE sc.run_id = ? ORDER BY sc.rowid""",
        (current["id"],),
    )
    return {
        **dict(current),
        "post_count": db.execute("SELECT count(*) FROM posts").fetchone()[0],
        "version_count": db.execute("SELECT count(*) FROM post_versions").fetchone()[0],
        "sources": [dict(check) for check in checks],
    }


@contextmanager
def read_database(path):
    with closing(sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        db.execute("BEGIN")
        yield db


def run_lock_held(path):
    lock_path = path.with_name(f"{path.name}.lock")
    try:
        with lock_path.open("rb") as lock:
            fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
    except FileNotFoundError:
        pass
    except BlockingIOError:
        return True
    return False


def status(path):
    if not path.exists():
        return {"status": "no_runs", "sources": []}
    with read_database(path) as db:
        result = run_report(db)
    if result["status"] == "running" and not run_lock_held(path.resolve()):
        result["status"] = "interrupted"
    return result


def daily_report(path, day, zone, limit):
    start = timestamp(datetime.combine(day, day_time.min, tzinfo=zone))
    end = timestamp(datetime.combine(day + timedelta(days=1), day_time.min, tzinfo=zone))
    result = {"date": day.isoformat(), "timezone": zone.key, "status": "no_checks", "sources": [], "sample": []}
    if not path.exists():
        return result
    with read_database(path) as db:
        checks = list(db.execute(
            """SELECT source_key, platform, label, profile_url, feed_url, scope, status,
                      observed_at, http_status, found, first_observations, new_publications,
                      changed, unchanged, error, retry_at
               FROM source_checks WHERE observed_at >= ? AND observed_at < ?
               ORDER BY observed_at, run_id, rowid""",
            (start, end),
        ))
        if checks:
            successes = sum(check["status"] == "ok" for check in checks)
            result["status"] = "ok" if successes == len(checks) else ("partial" if successes else "failed")
        result["sources"] = [dict(check) for check in checks]
        result["sample"] = daily_sample(db, start, end, limit)
    return result


def daily_sample(db, start, end, limit):
    rows = db.execute(
        """WITH seen AS (
               SELECT o.platform, o.post_id, o.version, o.published_at, o.published_basis,
                      c.source_key, c.profile_url, c.feed_url, c.scope, c.response_sha256, c.observed_at,
                      o.run_id, v.url, v.text_sha256, v.text_length, v.title_sha256, v.excerpts_json,
                      v.observed_at AS version_observed_at, p.first_observed_at,
                      CASE WHEN v.observed_at >= ? THEN v.event ELSE 'unchanged' END AS event,
                      row_number() OVER (
                          PARTITION BY o.platform, o.post_id ORDER BY c.observed_at DESC, o.run_id DESC
                      ) AS recency
               FROM source_checks c
               JOIN observations o ON o.run_id = c.run_id AND o.source_key = c.source_key
               JOIN posts p ON p.platform = o.platform AND p.post_id = o.post_id
               JOIN post_versions v ON v.platform = o.platform AND v.post_id = o.post_id AND v.version = o.version
               WHERE c.observed_at >= ? AND c.observed_at < ?
           ), ranked AS (
               SELECT *, row_number() OVER (
                   PARTITION BY source_key
                   ORDER BY excerpts_json NOT LIKE '{"sponsor":%' AND excerpts_json NOT LIKE '{"risk":%',
                       event = 'unchanged', published_at DESC, post_id DESC
               ) AS profile_rank
               FROM seen WHERE recency = 1
           )
           SELECT * FROM ranked ORDER BY profile_rank, source_key LIMIT ?""",
        (start, start, end, limit),
    )
    sample = []
    for row in rows:
        item = dict(row)
        item.pop("profile_rank")
        item.pop("recency")
        item["excerpts"] = json.loads(item.pop("excerpts_json"))
        sample.append(item)
    return sample


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "status", "report"), nargs="?", default="run")
    parser.add_argument("--db", type=Path, required=True, help="Path to the private local SQLite database.")
    parser.add_argument("--config", type=Path, default=CONFIG_PATH, help="Path to the public source settings.")
    parser.add_argument("--keep-text", action="store_true", help="Keep exact public text fields in the private database.")
    parser.add_argument("--date", type=date.fromisoformat, help="Local report date in YYYY-MM-DD format.")
    parser.add_argument("--timezone", default="Europe/Warsaw", help="IANA timezone for the daily report.")
    parser.add_argument("--limit", type=int, default=10, help="Maximum posts in the daily sample.")
    args = parser.parse_args()
    os.umask(0o077)
    try:
        if not 1 <= args.limit <= 50:
            raise ValueError("The report limit must be between 1 and 50.")
        if args.command == "status":
            result = status(args.db)
        elif args.command == "report":
            zone = ZoneInfo(args.timezone)
            day = args.date or datetime.now(zone).date()
            result = daily_report(args.db, day, zone, args.limit)
        else:
            result = run(args.db, load_config(args.config), keep_text=args.keep_text)
    except BusyError:
        print(json.dumps({"status": "already_running"}))
        return os.EX_TEMPFAIL
    except (OSError, ValueError, sqlite3.Error, ZoneInfoNotFoundError) as error:
        parser.exit(2, f"Monitor error: {error}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(args.command == "run" and result["status"] != "ok")


if __name__ == "__main__":
    raise SystemExit(main())
