"""Common validation and evidence fields for public sources."""

from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
from http.client import HTTPException
import json
import re
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener

from tools.watch_sources import NoRedirect, timestamp

MAX_RESPONSE = 3 * 1024 * 1024
MAX_TEXT = 24_000
TIMEOUT = 5


class SourceError(ValueError):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


def public_link(value):
    if not isinstance(value, str) or len(value) > 2048:
        return None
    if re.search(r"[\s\\\x00-\x1f\x7f]", value):
        return None
    try:
        url = urlsplit(value)
        hostname = url.hostname
        if (url.scheme == "https" and hostname and "." in hostname
                and hostname[-1].isalpha() and not url.username and not url.password
                and url.port in (None, 443) and url.netloc.lower() in (hostname, f"{hostname}:443")):
            return value
    except ValueError:
        pass
    return None


def safe_get(url, allowed_hosts):
    # Each adapter selects allowed origins independently of the network response.
    if not public_link(url) or urlsplit(url).hostname not in allowed_hosts:
        raise SourceError("Domena spoza listy publicznych źródeł.")
    request = Request(url, headers={"User-Agent": "InvestWatch-SourceMonitor/1.0"})
    deadline = monotonic() + TIMEOUT
    try:
        with build_opener(NoRedirect).open(request, timeout=TIMEOUT) as response:
            if response.status != 200:
                raise SourceError(f"HTTP {response.status}", response.status)
            body = bytearray()
            while monotonic() < deadline:
                chunk = response.read1(min(64 * 1024, MAX_RESPONSE + 1 - len(body)))
                if not chunk:
                    return bytes(body)
                body.extend(chunk)
                if len(body) > MAX_RESPONSE:
                    raise SourceError("Przekroczony limit wielkości odpowiedzi.")
            raise SourceError("Przekroczony czas pobrania.")
    except HTTPError as error:
        with error:
            raise SourceError(f"HTTP {error.code}", error.code) from None
    except (URLError, HTTPException, OSError):
        raise SourceError("Błąd połączenia ze źródłem.") from None


def utc_now():
    return timestamp(datetime.now(timezone.utc))


def digest(value):
    return sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def json_object(body):
    try:
        value = json.loads(body)
    except (ValueError, RecursionError):
        raise SourceError("Niepoprawna odpowiedź JSON.") from None
    if not isinstance(value, dict):
        raise SourceError("Odpowiedź JSON ma nieoczekiwany format.")
    return value


class Description(HTMLParser):
    BREAKS = {"br", "p", "div", "li", "ul", "ol", "blockquote", "section"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in self.BREAKS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.BREAKS:
            self.parts.append("\n")

    def handle_data(self, data):
        self.parts.append(data)


def html_text(text):
    parser = Description()
    parser.feed(text)
    parser.close()
    lines = [" ".join(line.split()) for line in "".join(parser.parts).splitlines()]
    return "\n".join(line for line in lines if line)


def source_result(id, name, url, observed_at, *, count=0, raw_count=None, error=None, scope=None):
    source = {
        "id": id, "name": name, "url": url, "count": count,
        "status": "error" if error else ("ok" if count else "empty"),
        "observedAt": observed_at,
    }
    if error:
        source["error"] = str(error)
        if getattr(error, "status", None):
            source["httpStatus"] = error.status
    else:
        source["lastSuccessAt"] = observed_at
    if raw_count is not None:
        source["rawCount"] = raw_count
    if scope:
        source["scope"] = scope
    return source


def capture(id, creator, title, url, text, *, observed_at, published_at=None, source_url,
            response_hash, scope, module="M1", **extra):
    return {
        "id": id,
        "creatorId": creator["id"],
        "title": title,
        "url": url,
        "platform": creator["platform"],
        "description": text[:MAX_TEXT],
        "module": module,
        "observedAt": observed_at,
        "publishedAt": published_at,
        "contentHash": digest(text[:MAX_TEXT]),
        "materialType": scope,
        "provenance": {
            "sourceUrl": source_url, "observedAt": observed_at,
            "responseSha256": response_hash, "scope": scope,
            "truncated": len(text) > MAX_TEXT,
        },
        **extra,
    }
