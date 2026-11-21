"""Common validation and evidence fields for public sources."""

from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
from http.client import HTTPException
import ipaddress
import json
import os
import re
import secrets
from threading import Lock
from time import monotonic, time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener

from tools.watch_sources import NoRedirect, timestamp

MAX_RESPONSE = 3 * 1024 * 1024
MAX_TEXT = 24_000
TIMEOUT = 5


class SourceError(ValueError):
    def __init__(self, message, status=None, retry_after=None):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after  # seconds, only for 429/403/503 and a local backoff


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


# --- Transport identity: User-Agent pool, optional proxies, backoff -------------------------------
#
# The pool serves requirement R-§3.1-05 (rotation of User-Agent) and R-§3.1-06 (proxy). The scope is
# narrow on purpose: identity rotation spreads honest, labelled requests across variants and routes.
# It is never a means of getting past a block. A 429/403/503 puts the host into a local backoff and
# the source reports the status; the request is not repeated under another identity or route.

VERSION = "1.1"
DEFAULT_USER_AGENTS = (
    f"InvestWatch-SourceMonitor/{VERSION}",
    f"InvestWatch-SourceMonitor/{VERSION} (Linux; public-source research monitor)",
    f"InvestWatch-SourceMonitor/{VERSION} (X11; Linux x86_64; UKNF InvestWatch discovery)",
    f"InvestWatch-SourceMonitor/{VERSION} (compatible; InvestWatch discovery; rate-limited, no login)",
)
BACKOFF_DEFAULT = 300
BACKOFF_MAX = 3600
BACKOFF_STATUSES = (403, 429, 503)
PROXY_COOLDOWN = 300
LOOPBACK_NAMES = {"localhost", "localhost.localdomain", "ip6-localhost"}
UA_CLEAN = re.compile(r"[\x00-\x1f\x7f]")


def _clean_agents(values):
    out = []
    for value in values:
        value = value.strip()
        if value and len(value) <= 300 and not UA_CLEAN.search(value) and value not in out:
            out.append(value)
    return out


def configured_user_agents(environ=None):
    """Pool from INVESTWATCH_USER_AGENTS (one per line or separated by `|`), else from the file named
    in INVESTWATCH_USER_AGENTS_FILE (one per line, `#` comments), else the labelled defaults."""
    environ = os.environ if environ is None else environ
    raw = environ.get("INVESTWATCH_USER_AGENTS")
    if raw and raw.strip():
        agents = _clean_agents(re.split(r"[\n|]", raw))
        if agents:
            return tuple(agents)
    path = environ.get("INVESTWATCH_USER_AGENTS_FILE")
    if path:
        try:
            with open(path, encoding="utf-8") as handle:
                lines = [line for line in handle.read().splitlines() if not line.lstrip().startswith("#")]
            agents = _clean_agents(lines)
            if agents:
                return tuple(agents)
        except OSError:
            pass
    return DEFAULT_USER_AGENTS


def is_loopback(host):
    host = (host or "").strip("[]").lower()
    if host in LOOPBACK_NAMES or host.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def configured_proxies(environ=None):
    """INVESTWATCH_PROXIES: comma or whitespace separated http(s) proxy URLs. Invalid entries are dropped."""
    environ = os.environ if environ is None else environ
    out = []
    for item in re.split(r"[,\s]+", environ.get("INVESTWATCH_PROXIES", "")):
        if not item:
            continue
        try:
            parts = urlsplit(item)
            if parts.scheme in ("http", "https") and parts.hostname and parts.port != 0:
                if item not in out:
                    out.append(item)
        except ValueError:
            continue
    return tuple(out)


def redact_proxy(url):
    try:
        parts = urlsplit(url)
        host = parts.hostname or "?"
        return f"{parts.scheme}://{host}" + (f":{parts.port}" if parts.port else "")
    except ValueError:
        return "proxy"


class Identity:
    """One scan session: a User-Agent per host that stays the same for the whole session, a round
    robin over the proxy list that skips a proxy that failed, and the per-host backoff state."""

    def __init__(self, agents=None, proxies=None, session=None, clock=time):
        self.agents = tuple(agents) if agents is not None else configured_user_agents()
        self.proxies = tuple(proxies) if proxies is not None else configured_proxies()
        self.session = session or secrets.token_hex(8)
        self.clock = clock
        self.lock = Lock()
        self.assigned = {}
        self.down = {}
        self.blocked = {}
        self.turn = 0
        self.last = {}

    def user_agent(self, host):
        with self.lock:
            host = (host or "").lower()
            if host not in self.assigned:
                index = int(digest(f"{self.session}|{host}")[:8], 16) % len(self.agents)
                self.assigned[host] = self.agents[index]
            return self.assigned[host]

    def new_session(self, session=None):
        with self.lock:
            self.session = session or secrets.token_hex(8)
            self.assigned = {}

    def proxy_order(self, host):
        """Proxies to try for this host, rotating the first one. Never for a loopback target."""
        if is_loopback(host) or not self.proxies:
            return []
        with self.lock:
            now = self.clock()
            live = [p for p in self.proxies if self.down.get(p, 0) <= now]
            if not live:
                return []
            start = self.turn % len(live)
            self.turn += 1
            return live[start:] + live[:start]

    def mark_down(self, proxy):
        with self.lock:
            self.down[proxy] = self.clock() + PROXY_COOLDOWN

    def backoff_left(self, host):
        with self.lock:
            until = self.blocked.get((host or "").lower(), 0)
            return max(0, until - self.clock())

    def block(self, host, seconds):
        seconds = min(max(int(seconds or BACKOFF_DEFAULT), 1), BACKOFF_MAX)
        with self.lock:
            self.blocked[(host or "").lower()] = self.clock() + seconds
        return seconds


IDENTITY = Identity()


def _retry_after(headers):
    value = headers.get("Retry-After") if headers else None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _read_body(response):
    deadline = monotonic() + TIMEOUT
    body = bytearray()
    while monotonic() < deadline:
        chunk = response.read1(min(64 * 1024, MAX_RESPONSE + 1 - len(body)))
        if not chunk:
            return bytes(body)
        body.extend(chunk)
        if len(body) > MAX_RESPONSE:
            raise SourceError("Przekroczony limit wielkości odpowiedzi.")
    raise SourceError("Przekroczony czas pobrania.")


def open_url(url, identity=None, extra_headers=None, keep_errors=False):
    """One request with the session's User-Agent and, when configured, a proxy. Without INVESTWATCH_PROXIES
    this is the former behaviour. Returns (status, headers, body) when keep_errors, else the body of a 200."""
    identity = identity or IDENTITY
    host = (urlsplit(url).hostname or "").lower()
    left = identity.backoff_left(host)
    if left and not keep_errors:
        raise SourceError(f"Źródło wstrzymane po odmowie (HTTP 429/403/503); ponowienie za ok. {int(left)} s.",
                          retry_after=int(left))
    headers = {"User-Agent": identity.user_agent(host), **(extra_headers or {})}
    routes = identity.proxy_order(host)
    if identity.proxies and not routes and not is_loopback(host):
        raise SourceError("Żaden skonfigurowany proxy nie odpowiada; bez cichego przejścia na łącze bezpośrednie.")
    last_error = None
    for proxy in (routes or [None]):
        handlers = [NoRedirect]
        if proxy:
            handlers.append(ProxyHandler({"http": proxy, "https": proxy}))
        elif identity.proxies:
            handlers.append(ProxyHandler({}))
        identity.last = {"host": host, "userAgent": headers["User-Agent"],
                         "route": redact_proxy(proxy) if proxy else "direct"}
        try:
            with build_opener(*handlers).open(Request(url, headers=headers), timeout=TIMEOUT) as response:
                body = _read_body(response)
                if keep_errors:
                    return response.status, dict(response.headers), body
                if response.status != 200:
                    raise SourceError(f"HTTP {response.status}", response.status)
                return body
        except HTTPError as error:
            with error:
                status, retry = error.code, _retry_after(error.headers)
                if status in BACKOFF_STATUSES:
                    retry = identity.block(host, retry)
                if keep_errors:
                    return status, dict(error.headers), error.read(MAX_RESPONSE)
                raise SourceError(f"HTTP {status}", status, retry_after=retry if status in BACKOFF_STATUSES else None) from None
        except (URLError, HTTPException, OSError):
            last_error = True
            if proxy:
                identity.mark_down(proxy)  # next proxy, never a different identity against the same refusal
                continue
            break
    raise SourceError("Błąd połączenia ze źródłem." if not routes else "Proxy nie odpowiada.") from None


def safe_get(url, allowed_hosts):
    # Each adapter selects allowed origins independently of the network response.
    if not public_link(url) or urlsplit(url).hostname not in allowed_hosts:
        raise SourceError("Domena spoza listy publicznych źródeł.")
    return open_url(url)


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
