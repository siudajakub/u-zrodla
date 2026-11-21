"""Fetch a bounded prefix of a public podcast MP3 for local transcription."""

from http.client import HTTPException
import os
from pathlib import Path
import re
from tempfile import NamedTemporaryFile
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, build_opener

from tools.watch_sources import NoRedirect

from .common import public_link

MAX_BYTES = 1536 * 1024
TIMEOUT = 10
# Exact provider and CDN origins seen in live RSS enclosures and HTTP redirects.
PROVIDER_REDIRECTS = {
    "api.spreaker.com": {"api.spreaker.com", "d1bxy2pveef3fq.cloudfront.net"},
    "anchor.fm": {"anchor.fm", "d3ctxlq1ktw2nl.cloudfront.net"},
    "www.buzzsprout.com": {"www.buzzsprout.com", "audio.buzzsprout.com"},
    "podcast.rmf.fm": {"podcast.rmf.fm"},
    "traffic.libsyn.com": {"traffic.libsyn.com", "content.libsyn.com"},
}
MP3_TYPES = {"audio/mpeg", "audio/mp3", "audio/mpeg3"}


def provider_for(url):
    if public_link(url):
        host = urlsplit(url).hostname
        return host if host in PROVIDER_REDIRECTS else None
    return None


def _prefix(url):
    provider = provider_for(url)
    if provider is None:
        return None
    allowed = PROVIDER_REDIRECTS[provider]
    opener = build_opener(NoRedirect)
    deadline = monotonic() + TIMEOUT
    headers = {"User-Agent": "InvestWatch-SourceMonitor/1.0", "Range": f"bytes=0-{MAX_BYTES - 1}"}
    current = url
    for _ in range(4):
        if not public_link(current) or urlsplit(current).hostname not in allowed:
            return None
        timeout = deadline - monotonic()
        if timeout <= 0:
            return None
        try:
            with opener.open(Request(current, headers=headers), timeout=timeout) as response:
                return _read_mp3(response, deadline)
        except HTTPError as error:
            with error:
                location = error.headers.get("Location")
                if error.code not in {301, 302, 303, 307, 308} or not location:
                    return None
                current = urljoin(current, location)
    return None


def _read_mp3(response, deadline):
    if response.status not in {200, 206}:
        return None
    mime = response.headers.get_content_type()
    if mime not in MP3_TYPES | {"application/octet-stream"} or response.headers.get("Content-Encoding") not in (None, "identity"):
        return None
    if response.status == 206 and not re.fullmatch(
        r"bytes 0-[0-9]+/(?:[0-9]+|\*)", response.headers.get("Content-Range", ""),
    ):
        return None
    body = bytearray()
    while len(body) < MAX_BYTES:
        if monotonic() >= deadline:
            return None
        chunk = response.read1(min(MAX_BYTES - len(body), 64 * 1024))
        if not chunk:
            break
        body.extend(chunk)
    if len(body) < 4 or not (body.startswith(b"ID3") or (body[0] == 0xff and body[1] & 0xe0 == 0xe0)):
        return None
    return body


def fetch_excerpt(capture, target_path):
    """Write no more than the first 1.5 MiB of an allowlisted, live RSS enclosure."""
    if (capture.get("mode") != "live" or capture.get("platform") != "apple-podcasts"
            or capture.get("materialType") != "podcast_rss_title_description"
            or capture.get("audioMimeType") not in MP3_TYPES):
        return False
    path = Path(target_path)
    staged = None
    try:
        body = _prefix(capture.get("audioUrl"))
        if not body:
            return False
        with NamedTemporaryFile(dir=path.parent, delete=False) as local:
            staged = Path(local.name)
            local.write(body)
        os.replace(staged, path)
        return True
    except (OSError, URLError, HTTPException, ValueError):
        return False
    finally:
        if staged is not None:
            staged.unlink(missing_ok=True)
