"""Read the archived M2 market captures (many firms, desktop + phone) as Capture records.

No network and no browser: everything comes from data/probe-snapshots/m2/market/.
Each manifest names its firm (KNF register row with entity type), the discovery path from the
home page, the HTML response digest and, per viewport, a JPEG of the first screen and the gzipped
DOM block list. Digests are checked before a record is emitted.
"""
import gzip
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from .common import SourceError, capture, digest

ROOT = Path(__file__).resolve().parents[1]
MARKET = ROOT / "data" / "probe-snapshots" / "m2" / "market"
SCHEMA = "investwatch-m2-market-1"
ASSET = re.compile(r"[a-f0-9]{64}\.(?:jpg|json\.gz)")
EVIDENCE_PREFIX = "/evidence/m2/market/"


def asset(root, name, limit=6 * 1024 * 1024):
    if not isinstance(name, str) or not ASSET.fullmatch(name):
        raise SourceError("Nieprawidłowy identyfikator dowodu M2.")
    data = (root / "assets" / name).read_bytes()
    if len(data) > limit or digest(data) != name.split(".", 1)[0]:
        raise SourceError("Odcisk pliku dowodu M2 nie zgadza się.")
    return data


def case_id(url):
    parts = urlsplit(url)
    if parts.hostname == "www.xtb.com" and parts.path.rstrip("/") == "/pl/etf":
        return "dom-xtb-etf"  # the same material as the earlier archive case, decisions stay attached
    return f"web:{parts.hostname}{parts.path.rstrip('/')}"


def read_manifest(path, root=MARKET, mode="replay"):
    raw = Path(path).read_bytes()
    record = json.loads(raw)
    if record.get("schema") != SCHEMA:
        raise SourceError("Nieznany format manifestu M2.")
    views, text = {}, None
    for view in record["views"]:
        dom = json.loads(gzip.decompress(asset(root, view["dom"])))
        if dom.get("viewport") != view["viewport"] or dom.get("url") != record["url"]:
            raise SourceError("Widok M2 nie zgadza się z manifestem.")
        asset(root, view["screenshot"])
        views[view["viewport"]] = {
            **{k: dom.get(k) for k in ("docHeight", "scrollWidth", "consent", "riskLinks", "blocks", "lang")},
            # Requested screen size; the page's own layout size can differ when it ignores the phone viewport.
            "width": view["width"], "height": view["height"], "layoutWidth": dom.get("width"), "layoutHeight": dom.get("height"),
            "viewport": view["viewport"], "screenshotUrl": EVIDENCE_PREFIX + view["screenshot"], "domUrl": EVIDENCE_PREFIX + view["dom"],
            "screenshotSha256": view["screenshot"].split(".")[0], "domSha256": view["dom"].split(".")[0],
            # Older captures flagged any skipped tiny text; only hitting the block cap means the list is incomplete.
            "truncatedBlocks": len(dom.get("blocks") or []) >= (2500 if "skippedHiddenNavOrDialog" in dom else 1100),
        }
        text = text or dom.get("text")
    firm = record["firm"]
    host = urlsplit(record["url"]).hostname
    creator = {"id": f"www:{host}", "name": firm["brand"], "platform": "web", "url": firm["home"],
               "discoveredVia": "Strona główna firmy z wykazu KNF", "isSeed": False}
    result = capture(
        case_id(record["url"]), creator, record.get("title") or firm["brand"], record["url"], text or "",
        observed_at=record["capturedAt"], source_url=record["url"], response_hash=record["htmlSha256"],
        scope="rendered_marketing_dom", module="M2", brand=firm["brand"], mode=mode, creatorName=firm["brand"],
        legalName=firm["name"], fullText=True,
        m2Market={"manifest": record["id"], "manifestSha256": digest(raw), "kind": record["kind"], "firm": firm,
                  "discovery": record.get("discovery"), "views": views, "browser": record.get("browser"),
                  "htmlSha256": record["htmlSha256"], "finalUrl": record.get("finalUrl")},
    )
    result["provenance"].update(
        mode=mode, evidenceSha256=digest(raw), discoveredFrom=(record.get("discovery") or {}).get("from") or firm["home"],
        registryId=firm["registryId"], registryObservedAt=firm.get("checkedAt"), registrySource=firm.get("sourceFile"),
        entityType=firm.get("entityType"), entityLabel=firm.get("entityLabel"), browser=record.get("browser"),
    )
    return result, creator


def market_captures(root=MARKET, mode="replay"):
    """All archived market pages, with one source status per manifest (errors are kept, not hidden)."""
    captures, creators, sources = [], {}, []
    for path in sorted((root / "manifests").glob("*.json")):
        status = {"id": f"m2-market:{path.stem}", "name": f"M2 · {path.stem}", "kind": "page",
                  "scope": "Render Chromium · komputer 1440×900 i telefon 390×844"}
        try:
            result, creator = read_manifest(path, root, mode)
        except (OSError, ValueError, KeyError, TypeError, SourceError) as error:
            sources.append({**status, "status": "error", "count": 0, "error": str(error)[:200]})
            continue
        captures.append(result)
        creators[creator["id"]] = creator
        sources.append({**status, "status": "ok", "count": 1, "url": result["url"], "observedAt": result["observedAt"]})
    return captures, list(creators.values()), sources


def material(cap):
    """The input of analysis.m2_rules built from a Capture."""
    market = cap["m2Market"]
    return {"firm": market["firm"], "url": cap["url"], "title": cap.get("title"), "observedAt": cap["observedAt"],
            "kind": market["kind"], "audience": cap.get("audience"), "views": market["views"]}
