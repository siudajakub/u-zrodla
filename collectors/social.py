"""Adapt the existing YouTube and TikTok monitor without writing to its database."""

from pathlib import Path
import sqlite3
from urllib.parse import urlsplit

from tools.watch_sources import (
    CONFIG_PATH, ReadError, load_config, parse_tiktok, parse_youtube, read_database,
)

from .common import SourceError, capture, digest, public_link, source_result, utc_now

CONFIG = load_config(CONFIG_PATH)
POST_LIMIT = 50


def social_creator(source):
    return {
        "id": source.key, "name": source.label, "platform": source.platform,
        "url": source.profile_url, "discoveredVia": "Profil monitorowany", "isSeed": True,
    }


def make_social_capture(source, post_id, url, title, description, published_at, observed_at, response_hash):
    return capture(
        f"{source.platform}:{post_id}", social_creator(source), title or description[:120] or source.label,
        url, description, observed_at=observed_at, published_at=published_at,
        source_url=source.feed_url, response_hash=response_hash, scope=source.scope,
    )


def read_social(source, fetch, clock=utc_now):
    key = source.key
    name = f"{source.label} · {'YouTube' if source.platform == 'youtube' else 'TikTok'}"
    url = source.feed_url
    try:
        body = fetch(url, {urlsplit(url).hostname})
        parse = parse_youtube if source.platform == "youtube" else parse_tiktok
        posts = parse(source, body)
    except (ReadError, SourceError) as error:
        return [], source_result(key, name, url, clock(), error=error, scope=source.scope)
    observed = clock()
    body_hash = digest(body)
    captures = [
        make_social_capture(source, post.id, post.url, post.title, post.text,
                            post.published_at, observed, body_hash)
        for post in posts
    ]
    status = source_result(key, name, url, observed, count=len(captures), scope=source.scope)
    return captures, status


def read_watch(path: Path, clock=utc_now):
    captures, statuses = [], []
    try:
        with read_database(path) as db:
            for source in CONFIG.sources:
                items, status = read_watch_source(db, source, clock)
                captures.extend(items)
                statuses.append(status)
    except sqlite3.Error:
        captures = []
        statuses = [
            source_result(
                source.key, source.label, source.feed_url, clock(), scope=source.scope,
                error=SourceError("Baza monitoringu jest niedostępna lub ma niezgodny format."),
            )
            for source in CONFIG.sources
        ]
    return captures, statuses


def read_watch_source(db, source, clock):
    check = db.execute(
        """SELECT observed_at, status, found, http_status, retry_at
           FROM source_checks WHERE source_key = ? ORDER BY run_id DESC LIMIT 1""",
        (source.key,),
    ).fetchone()
    if check is None:
        return [], source_result(
            source.key, source.label, source.feed_url, clock(), scope=source.scope,
            error=SourceError("Monitor nie zapisał jeszcze odczytu tego profilu."),
        )
    latest_success = db.execute(
        """SELECT max(observed_at) FROM source_checks WHERE source_key = ? AND status = 'ok'""",
        (source.key,),
    ).fetchone()[0]
    rows = db.execute(
        """SELECT p.post_id, p.published_at, v.url, v.observed_at, v.text_sha256,
                  v.version, t.title, t.text, s.response_sha256
           FROM posts p
           JOIN post_versions v
             ON (v.platform, v.post_id, v.version) = (p.platform, p.post_id, p.latest_version)
           JOIN source_checks s ON (s.run_id, s.source_key) = (v.run_id, v.source_key)
           JOIN post_texts t ON (t.platform, t.post_id, t.version) = (v.platform, v.post_id, v.version)
           WHERE v.source_key = ?
           ORDER BY p.last_observed_at DESC, p.published_at DESC, p.post_id DESC
           LIMIT ?""",
        (source.key, POST_LIMIT),
    )
    captures = []
    for row in rows:
        if not public_link(row["url"]) or digest(row["text"]) != row["text_sha256"]:
            continue
        item = make_social_capture(source, row["post_id"], row["url"], row["title"], row["text"],
                                   row["published_at"], row["observed_at"], row["response_sha256"])
        item["provenance"].update(storage="watch_sqlite", sourceVersion=row["version"],
                                  originalTextSha256=row["text_sha256"])
        captures.append(item)
    error = None
    if check["status"] != "ok":
        code = check["http_status"]
        error = SourceError(f"HTTP {code}" if code else "Ostatni odczyt monitora nie powiódł się.", code)
    elif check["found"] and not captures:
        error = SourceError("Brak zachowanych opisów lub podpisów.")
    result = source_result(
        source.key, source.label, source.feed_url, check["observed_at"],
        count=len(captures), raw_count=check["found"], error=error, scope=source.scope,
    )
    if latest_success:
        result["lastSuccessAt"] = latest_success
    result["transport"] = "watch_sqlite"
    if check["retry_at"]:
        result["retryAt"] = check["retry_at"]
    return captures, result
