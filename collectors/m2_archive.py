"""Versioned public marketing captures and their content-addressed proof."""
import json
import os
from pathlib import Path
import re
import struct
import tempfile
from datetime import datetime
from urllib.parse import urlsplit

from .common import MAX_TEXT, SourceError, capture, digest

ROOT = Path(__file__).resolve().parents[1]
REPLAY = ROOT / "data" / "probe-snapshots" / "m2"
SCHEMA = "investwatch-m2-1"
HASH = re.compile(r"[a-f0-9]{64}")
ASSET_NAME = re.compile(r"([a-f0-9]{64})\.(png|json)")
MAX_ASSET = {"png": 4 * 1024 * 1024, "json": 384 * 1024}
VIEWPORTS = ((1440, 900), (768, 1024), (390, 844))
STATES = {"initial", "claim", "warning", "expanded", "identity", "profit"}
PUBLISHERS = {
    "www.xtb.com": ("XTB", "XTB S.A.", 6884980, "https://www.xtb.com/pl"),
    "www.bdm.pl": ("Dom Maklerski BDM", "Dom Maklerski BDM S.A.", 6884964, "https://www.bdm.pl/"),
}
TARGETS = {
    "xtb-etf": ("https://www.xtb.com/pl/etf", "etf"),
    "xtb-akcje": ("https://www.xtb.com/pl/akcje", "stocks"),
    "bdm-rachunek": ("https://www.bdm.pl/rachunek-inwestycyjny", "account"),
}


def encode(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def write_once(path, data):
    """Publish complete bytes even if a refresh overlaps an API read."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_file() and path.read_bytes() == data:
        return
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temp = Path(stream.name)
        try:
            stream.write(data)
            stream.close()
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)


def asset_bytes(root, name):
    match = ASSET_NAME.fullmatch(name)
    if match is None:
        raise SourceError("Nieprawidłowy identyfikator dowodu M2.")
    checksum, extension = match.groups()
    try:
        with (root / "assets" / name).open("rb") as stream:
            data = stream.read(MAX_ASSET[extension] + 1)
    except OSError:
        raise SourceError("Plik dowodu M2 jest niedostępny.") from None
    if len(data) > MAX_ASSET[extension] or digest(data) != checksum:
        raise SourceError("Odcisk pliku dowodu M2 nie zgadza się.")
    return data


def save_asset(root, data, extension):
    if len(data) > MAX_ASSET[extension]:
        raise SourceError("Dowód M2 przekroczył limit rozmiaru.")
    checksum = digest(data)
    write_once(root / "assets" / f"{checksum}.{extension}", data)
    return checksum


def png_size(data):
    if len(data) < 24 or data[:16] != b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR":
        raise SourceError("Dowód M2 nie ma oczekiwanego nagłówka PNG.")
    return struct.unpack(">II", data[16:24])


def read_bundle(root, name, mode, raw=None):
    """Check frame identity, dimensions and both byte digests before emitting links."""
    url, product = TARGETS[name]
    host = urlsplit(url).hostname
    brand, legal, registry_id, home = PUBLISHERS[host]
    try:
        if raw is None:
            with (root / "manifests" / f"{name}.json").open("rb") as stream:
                raw = stream.read(64 * 1024 + 1)
        if len(raw) > 64 * 1024:
            raise ValueError("oversized bundle")
        record = json.loads(raw)
        if record["schema"] != SCHEMA or record["url"] != url or record["discoveredFrom"] != home:
            raise ValueError("bundle identity")
        captured = record["capturedAt"]
        if datetime.fromisoformat(captured).utcoffset() is None:
            raise ValueError("observation time")
        title, scope = record["title"], record["description"]
        if not 1 <= len(title) <= 300 or not 30 <= len(scope) <= MAX_TEXT:
            raise ValueError("text scope")
        if not HASH.fullmatch(record["indexSha256"]):
            raise ValueError("index digest")
        frames = []
        initial_sizes = set()
        frame_ids = set()
        for frame in record["frames"]:
            state = frame["state"]
            size = (frame["width"], frame["height"])
            frame_id = (*size, state)
            if size not in VIEWPORTS or state not in STATES or frame_id in frame_ids:
                raise ValueError("frame identity")
            frame_ids.add(frame_id)
            if state == "initial":
                initial_sizes.add(size)
            screenshot = asset_bytes(root, frame["screenshotHash"] + ".png")
            if png_size(screenshot) != size:
                raise ValueError("image dimensions")
            dom = json.loads(asset_bytes(root, frame["domHash"] + ".json"))
            if any(dom[k] != frame[k] for k in ("width", "height", "state", "screenshotHash")):
                raise ValueError("crossed frame")
            if dom["url"] != url or dom["product"] != product or not HASH.fullmatch(dom["responseSha256"]):
                raise ValueError("crossed source")
            frames.append({
                **dom, **frame,
                "url": "/evidence/m2/" + frame["screenshotHash"] + ".png",
                "domUrl": "/evidence/m2/" + frame["domHash"] + ".json",
            })
        if initial_sizes != set(VIEWPORTS):
            raise ValueError("missing initial state")
        first = next(frame for frame in frames if frame["state"] == "initial")
        if (first["textScope"], first["title"]) != (scope, title):
            raise ValueError("crossed text scope")
        revision = digest(encode([url, title, scope, record["frames"]]))
        for frame in frames:
            del frame["textScope"]
        creator = {
            "id": f"www:{host}", "name": brand, "platform": "web", "url": home,
            "discoveredVia": "Domena na liście monitorowanej", "isSeed": True,
        }
        result = capture(
            case_id(url), creator, title, url, scope,
            observed_at=captured, source_url=url, response_hash=first["responseSha256"],
            scope="rendered_marketing_dom", module="M2", brand=brand, mode=mode,
            creatorName=brand, legalName=legal, m2EvidenceRevision=revision,
            m2Views=frames, fullText=False,
        )
        result["provenance"].update(
            mode=mode, evidenceSha256=digest(raw), discoveredFrom=home, indexSha256=record["indexSha256"],
            browser=record["browser"], registryId=registry_id, registryObservedAt="2026-11-21",
            registryUrl="https://www.knf.gov.pl/api/podmioty-children?parentId=19&type=COMPANY&pageSize=100",
        )
        return result, creator
    except (OSError, ValueError, KeyError, TypeError, StopIteration, AttributeError):
        raise SourceError("Archiwum M2 jest brakujące, niepełne albo niespójne.") from None


def case_id(url):
    if url == TARGETS["xtb-etf"][0]:
        return "dom-xtb-etf"  # Preserve the existing ETF case and its analyst decisions.
    parts = urlsplit(url)
    return f"web:{parts.hostname}{parts.path}"


def staged_captures(mode, root, refresh=None):
    """Read the offline archive or a prior live acquisition, with one status per source."""
    archive = REPLAY if mode == "replay" else root
    captures, creators, sources = [], {}, []
    for name, (url, _) in TARGETS.items():
        brand = PUBLISHERS[urlsplit(url).hostname][0]
        failure = None
        if refresh:
            try:
                refresh(name, archive)
            except SourceError as error:
                failure = error
        result = creator = None
        if (archive / "manifests" / f"{name}.json").is_file():
            try:
                result, creator = read_bundle(archive, name, mode)
            except SourceError as error:
                failure = failure or error
        if result:
            captures.append(result)
            creators[creator["id"]] = creator
        status = {
            "id": f"m2:{name}", "name": f"{brand} · Chromium M2 · {urlsplit(url).path}",
            "url": url, "count": int(result is not None),
            "status": "ok" if result else "unavailable",
            "scope": "Widok początkowy i fragmenty oferty · komputer, tablet, telefon",
        }
        if result:
            status.update(observedAt=result["observedAt"], lastSuccessAt=result["observedAt"])
        if failure:
            status.update(status="stale" if result else "forbidden" if failure.status == 403 else "error", error=str(failure))
            if failure.status:
                status["httpStatus"] = failure.status
        elif not result:
            status["error"] = "Brak zapisanego odczytu Chromium dla tego materiału."
        sources.append(status)
    return captures, list(creators.values()), sources


def apply_rendered(discovery, rendered):
    captures, creators, sources = rendered
    proven_urls = {item["url"] for item in captures}
    raw = [item for item in discovery["captures"] if item.get("module") != "M2" or item["url"] not in proven_urls]
    for item in raw:
        if item.get("module") == "M2" and item["url"] == TARGETS["xtb-etf"][0]:
            item["id"] = case_id(item["url"])
    discovery["captures"] = raw + captures
    discovery["creators"] = list({item["id"]: item for item in discovery["creators"] + creators}.values())
    discovery["sources"].extend(sources)
    return proven_urls
