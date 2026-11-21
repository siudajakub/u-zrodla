"""Instagram, Facebook and Meta Ad Library material collected ONCE through an external service (ScrapeCreators).

Why this exists: Meta offers no free, key-less way to read public posts and ads, and the official routes need an
approved account or institution. The owner opened a free ScrapeCreators account (100 credits, 1 credit = 1 request)
to collect one dated sample for the demo. The service, not this host, talks to Meta. Meta treats automated
collection as contrary to its terms; that risk sits with the service and with the decision to use it.

Two separate parts, deliberately apart:

* ``collect`` (CLI, ``python -m collectors.vendor_social collect --plan plan.json --max-credits N``) is the only
  code that calls ``api.scrapecreators.com``. It reads the key from a file outside the repo, counts credits, stops on
  an auth, credit or rate-limit error and when the balance would fall to the reserve, and stores every raw response
  as gzip (the key is never stored; logged headers read ``REDACTED``).
* ``build`` / the ``vendor-social-replay`` adapter read only the stored sample. A product scan NEVER calls the
  service: the brief forbids paid APIs in the product, so this source is a dated replay, not a monitor.

Nothing here contacts facebook.com, instagram.com or graph.facebook.com.
"""

from datetime import datetime, timezone
from hashlib import sha256
import gzip
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from .common import SourceError, capture, public_link, utc_now
from .meta_ads import relate
from .social import firm_signals, _firm_index

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.scrapecreators.com"
VENDOR = "scrapecreators"
DEFAULT_TOKEN_FILE = "~/.config/investwatch/scrapecreators.token"
KEY_SHAPE = re.compile(r"[A-Za-z0-9_\-.]{16,200}\Z")
SAMPLE_DIR = ROOT / "fixtures/raw/discovery/social-2026-11-21/vendor"
SAMPLE_REPLAY = SAMPLE_DIR / "replay-vendor.json.gz"
SAMPLE_MANIFEST = SAMPLE_DIR / "manifest-vendor.json"
PARSER_VERSION = "vendor-social-1"
PAUSE = 2.2
TIMEOUT_S = 60
MAX_BODY = 8 * 1024 * 1024
RESERVE = 15
TOTAL_CREDITS = 100
FATAL = {"auth", "no_credits", "rate_limited"}
NEXT_STEP = ("Odczyt cykliczny w produkcie: import ręczny (POST /v1/import/meta) lub oficjalne API (Ad Library API, "
             "Meta Content Library) po uzyskaniu dostępu.")
SAMPLE_STATUS = "próbka datowana z 21 XI zebrana przez usługę zewnętrzną ({detail}); odczyt cykliczny w produkcie: import ręczny lub oficjalne API po uzyskaniu dostępu"

ENDPOINTS = {  # op -> (path, required parameter names)
    "ig_profile": ("/v1/instagram/profile", ("handle",)),
    "ig_posts": ("/v2/instagram/user/posts", ("handle",)),
    "fb_posts": ("/v1/facebook/profile/posts", ()),
    "fb_company_search": ("/v1/facebook/adLibrary/search/companies", ("query",)),
    "fb_company_ads": ("/v1/facebook/adLibrary/company/ads", ()),
    "fb_ads_search": ("/v1/facebook/adLibrary/search/ads", ("query",)),
    "fb_ad_detail": ("/v1/facebook/adLibrary/ad", ()),
}
# keys dropped from stored raw responses: comments of users, follower lists and signed CDN media addresses
DROP_KEYS = frozenset({
    "topComments", "edge_media_preview_comment", "edge_media_to_parent_comment", "edge_liked_by", "edge_followed_by_edges",
    "edge_mutual_followed_by", "edge_related_profiles", "edge_saved_media", "edge_media_collections", "edge_felix_video_timeline",
    "profile_pic_url", "profile_pic_url_hd", "profile_picture_url", "page_profile_picture_url", "image_uri", "display_url",
    "display_resources", "thumbnail_resources", "thumbnail_src", "video_url", "video_versions", "image_versions2", "videoDetails",
    "videos", "images", "image", "video_hd_url", "video_sd_url", "video_preview_image_url", "extra_images", "extra_videos", "watermarked_video_hd_url", "clips_metadata",
    "clips_music_attribution_info", "original_image_url", "resized_image_url", "ai_label_info", "sharing_friction_info"})
COMMENT_EDGES = ("edge_media_to_comment",)
TAG_KEYS = ("edge_media_to_tagged_user", "usertags", "coauthor_producers")


class VendorError(SourceError):
    """A mapped failure of the service. ``code`` is auth, no_credits, rate_limited, not_found, bad_request or error."""

    def __init__(self, code, message, status=None, retry_after=None):
        super().__init__(message, status, retry_after)
        self.code = code


# --- key and requests -----------------------------------------------------------------------------------------------

def token_path(environ=None):
    environ = os.environ if environ is None else environ
    return Path(environ.get("INVESTWATCH_SCRAPECREATORS_TOKEN_FILE") or DEFAULT_TOKEN_FILE).expanduser()


def load_key(environ=None):
    """(key, problem). The file lives outside the repository; the key is never logged or stored."""
    try:
        text = token_path(environ).read_text(encoding="utf-8").strip()
    except OSError:
        return None, "brak pliku z kluczem"
    if not text:
        return None, "plik z kluczem jest pusty"
    if not KEY_SHAPE.fullmatch(text):
        return None, "plik z kluczem ma nieoczekiwany format"
    return text, None


def scrub(text, key=None):
    text = str(text)
    if key:
        text = text.replace(key, "REDACTED")
    return re.sub(r"(?i)(x-api-key['\"]?\s*[:=]\s*['\"]?)[^\s'\",}]+", r"\1REDACTED", text)


def request_url(op, params):
    path, _required = ENDPOINTS[op]
    clean = {k: v for k, v in params.items() if v not in (None, "")}
    return API + path + ("?" + urlencode(clean) if clean else "")


def _default_fetch(url, headers):
    """GET to api.scrapecreators.com only (the service scrapes slowly, so the timeout is longer than the default)."""
    if urlsplit(url).hostname != "api.scrapecreators.com":
        raise SourceError("Adres spoza api.scrapecreators.com.")
    try:
        with urlopen(Request(url, headers={"User-Agent": "investwatch-vendor-sample/1", **headers}), timeout=TIMEOUT_S) as response:
            return response.status, dict(response.headers), response.read(MAX_BODY + 1)[:MAX_BODY]
    except HTTPError as error:
        with error:
            return error.code, dict(error.headers), error.read(MAX_BODY)
    except (URLError, OSError, ValueError):
        raise SourceError("Błąd połączenia z usługą.") from None


def call(op, params, key, fetch=None):
    """One request to the service. Returns (data, body bytes, http status). Raises VendorError (mapped)."""
    path, required = ENDPOINTS[op]
    missing = [name for name in required if not params.get(name)]
    if missing:
        raise VendorError("bad_request", "Brak parametru: " + ", ".join(missing))
    url = request_url(op, params)
    try:
        status, headers, body = (fetch or _default_fetch)(url, {"x-api-key": key, "Accept": "application/json"})
    except VendorError:
        raise
    except SourceError as exc:
        raise VendorError("error", scrub(exc, key)) from None
    try:
        data = json.loads(body)
    except ValueError:
        data = None
    message = scrub((data.get("message") or data.get("error") or "") if isinstance(data, dict) else "", key)[:200]
    if status in (401, 403):
        raise VendorError("auth", f"Klucz odrzucony przez usługę (HTTP {status}). {message}".strip(), status)
    if status == 402:
        raise VendorError("no_credits", "Wyczerpane kredyty usługi (HTTP 402).", status)
    if status == 429:
        raise VendorError("rate_limited", "Limit zapytań usługi (HTTP 429).", status, retry_after=60)
    if status == 404:
        raise VendorError("not_found", f"Nie znaleziono (HTTP 404). {message}".strip(), status)
    if status in (400, 422):
        raise VendorError("bad_request", f"Błędne zapytanie (HTTP {status}). {message}".strip(), status)
    if status != 200:
        raise VendorError("error", f"Błąd usługi (HTTP {status}). {message}".strip(), status)
    if not isinstance(data, dict):
        raise VendorError("error", "Odpowiedź usługi nie jest obiektem JSON.", status)
    if data.get("success") is False:
        raise VendorError("error", f"Usługa zgłosiła błąd: {message or 'brak opisu'}", status)
    return data, body, status


def _username_only(value):
    if isinstance(value, dict):
        if isinstance(value.get("username"), str):
            return {"username": value["username"]}
        return {k: _username_only(v) for k, v in value.items() if k in ("user", "node", "in", "edges", "position", "count")}
    if isinstance(value, list):
        return [_username_only(v) for v in value]
    return value


def sanitize(value):
    """Raw response reduced to public texts and counts: comments, follower lists, signed media URLs removed;
    tagged and co-author accounts reduced to their public account name."""
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if k in DROP_KEYS:
                continue
            if k in TAG_KEYS:
                out[k] = _username_only(v)
                continue
            if k in COMMENT_EDGES and isinstance(v, dict):
                out[k] = {kk: vv for kk, vv in v.items() if kk != "edges"}
                continue
            out[k] = sanitize(v)
        return out
    if isinstance(value, list):
        return [sanitize(v) for v in value]
    return value


# --- credit ledger and collection -----------------------------------------------------------------------------------

def step_key(step):
    return step.get("op", "") + ":" + json.dumps({k: v for k, v in sorted(step.get("params", {}).items())}, sort_keys=True)


def collect(plan, out_dir, key, max_credits, reserve=RESERVE, pause=PAUSE, fetch=None, sleep=time.sleep, clock=utc_now):
    """Run plan steps in order. Stops on auth/credit/rate errors, at ``max_credits`` spent this run, or when the
    balance reported by the service would fall below ``reserve``. Returns the run log (also written to out_dir)."""
    out = Path(out_dir)
    (out / "raw").mkdir(parents=True, exist_ok=True)
    log_path = out / "requests.json"
    log = json.loads(log_path.read_text(encoding="utf-8")) if log_path.exists() else {
        "vendor": VENDOR, "api": API, "keyHeader": "x-api-key: REDACTED", "requests": [], "creditsSpent": 0,
        "creditsRemaining": None, "stopped": None}
    done = {step_key(r["step"]) for r in log["requests"] if r.get("ok")}
    spent_run, first = 0, True
    log["stopped"] = None
    for step in plan.get("steps", []):
        sk = step_key(step)
        if sk in done:
            continue
        remaining = log.get("creditsRemaining")
        cost = int(step.get("expectedCredits", 1))
        if spent_run + cost > max_credits:
            log["stopped"] = {"reason": "max_credits", "message": f"Limit przebiegu {max_credits} kredytów."}
            break
        if remaining is not None and remaining - cost < reserve:
            log["stopped"] = {"reason": "reserve", "message": f"Saldo {remaining} spadłoby poniżej rezerwy {reserve}."}
            break
        if not first:
            sleep(pause)
        first = False
        at = clock()
        entry = {"n": len(log["requests"]) + 1, "at": at, "step": step, "url": request_url(step["op"], step.get("params", {})),
                 "headers": {"x-api-key": "REDACTED"}, "ok": False}
        try:
            data, body, status = call(step["op"], step.get("params", {}), key, fetch)
        except VendorError as exc:
            entry.update(error={"code": exc.code, "message": scrub(exc, key), "status": exc.status})
            log["requests"].append(entry)
            if exc.code in FATAL:
                log["stopped"] = {"reason": exc.code, "message": scrub(exc, key)}
                break
            continue
        charged = data.get("credits_charged") if type(data.get("credits_charged")) is int else cost
        left = data.get("credits_remaining") if type(data.get("credits_remaining")) is int else None
        spent_run += charged
        log["creditsSpent"] += charged
        if left is not None:
            log["creditsRemaining"] = left
        name = f"{entry['n']:03d}-{step['op']}-" + re.sub(r"[^A-Za-z0-9]+", "-", str(next(iter(step.get('params', {}).values()), "")))[:40].strip("-") + ".json.gz"
        stored = sanitize(data)
        payload = json.dumps(stored, ensure_ascii=False, sort_keys=True).encode()
        (out / "raw" / name).write_bytes(gzip.compress(payload, mtime=0))
        entry.update(ok=True, httpStatus=status, creditsCharged=charged, creditsRemaining=left, file="raw/" + name,
                     bodySha256=sha256(body).hexdigest(), storedSha256=sha256(payload).hexdigest(), observedAt=clock())
        log["requests"].append(entry)
        log_path.write_text(scrub(json.dumps(log, ensure_ascii=False, indent=1), key) + "\n", encoding="utf-8")
        if left is not None and left <= reserve:
            log["stopped"] = {"reason": "reserve", "message": f"Saldo {left} osiągnęło rezerwę {reserve}."}
            break
    log_path.write_text(scrub(json.dumps(log, ensure_ascii=False, indent=1), key) + "\n", encoding="utf-8")
    return log


# --- normalisation: stored responses -> creators and captures ---------------------------------------------------------

YOUTUBE_REPLAYS = (ROOT / "fixtures/raw/discovery/youtube-api-2026-11-21/replay.json.gz",)
HASHTAG = re.compile(r"#[^\W\d_][\w]*", re.U)
URLS = re.compile(r"https?://[^\s<>\"']+", re.I)
DISCLOSURE = re.compile(
    r"#(?:reklama|sponsor\w*|wsp[oó][lł]praca\w*|ad|sponsored|partner\w*|paidpartnership|collab)\b|"
    r"wsp[oó]łpraca\s+(?:reklamowa|z|płatna|barterowa)|\[wsp[oó]łpraca|płatn\w+\s+partnerstw\w*|materiał\s+sponsorowany|"
    r"\breklama\b|paid\s+partnership|\bsponsored\b|\bpost\s+sponsorowany\b", re.I)
BENEFIT = re.compile(
    r"zarabiaj\w*|zarób\w*|zysk\w*|odsetk\w*|oprocentowan\w*|pieniądze\s+(?:mogą\s+)?pracuj\w*|pracowa[ćc]\s+(?:dla|na)\s+\w+|"
    r"bez\s+prowizji|0\s?%\s+prowizji|\d+(?:[.,]\d+)?\s?%\s+(?:w\s+skali\s+roku|rocznie|odsetek|zwrotu)|stop\w+\s+zwrotu|dochód|dochod\w*|"
    r"wzrost\w*\s+wartości|\bprofits?\b|\bearn\w*|bonus\w*|akcj\w+\s+za\s+darmo|darmow\w+\s+akcj\w+", re.I)
WARNING = re.compile(
    r"ryzyk\w*|także\s+ujemn\w*|wynik\s+może\s+być\s+inny|\bstrat(?:a|y|ę|ą|ami|om|ach)\b|\bstraci\w*|\bCFD\b|utrat\w+\s+(?:całości|kapitału|pieniędzy)|nie\s+gwarantuj\w*|wyniki\s+z\s+przeszłości|"
    r"wartość\s+inwestycji\s+może|rachunków\s+.{0,40}odnotowuje|\brisk\w*|capital\s+at\s+risk", re.I)
TEMPLATE = re.compile(r"\{\{[^}]+\}\}")


def _iso(value):
    """Epoch seconds (int, float or numeric string) or an ISO string -> UTC ISO 8601, else None."""
    if isinstance(value, bool) or value in (None, ""):
        return None
    try:
        if isinstance(value, (int, float)) or (isinstance(value, str) and re.fullmatch(r"\d{9,13}(?:\.\d+)?", value)):
            number = float(value)
            number = number / 1000 if number > 1e11 else number
            moment = datetime.fromtimestamp(number, timezone.utc)
        else:
            moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            moment = moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)
    except (ValueError, OverflowError, OSError):
        return None
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _count(value):
    return value if type(value) is int and value >= 0 else None


def _metric(value, observed, source="scrapecreators"):
    value = _count(value)
    return {"value": value, "state": "observed" if value is not None else "not_collected", "observedAt": observed, "source": source}


def _first(*values):
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _dig(value, *path):
    for key in path:
        value = value.get(key) if isinstance(value, dict) else None
    return value


def _signals(text):
    """firm_signals with a deterministic order of the markers (the shared helper orders ties by set iteration)."""
    out = firm_signals(text)
    out["promoMarkers"] = sorted(out["promoMarkers"], key=lambda t: (t.lower(), t))
    return out


def text_signals(text):
    """Benefit claims and risk warnings found in the TEXT. A warning may sit in a graphic; only text was examined."""
    benefit = sorted({m.group(0).strip() for m in BENEFIT.finditer(text)}, key=lambda t: (t.lower(), t))[:6]
    warning = sorted({m.group(0).strip() for m in WARNING.finditer(text)}, key=lambda t: (t.lower(), t))[:6]
    return {"benefitClaims": benefit, "riskWarnings": warning, "benefitClaim": bool(benefit),
            "riskWarningInText": bool(warning), "scope": "tekst; ostrzeżenie w grafice lub wideo nie jest zbadane"}


def disclosure_of(text, flag, coauthors=()):
    markers = sorted({m.group(0).strip() for m in DISCLOSURE.finditer(text)}, key=lambda t: (t.lower(), t))[:6]
    return {"platformFlag": flag if isinstance(flag, bool) else None, "textMarkers": markers, "coauthors": list(coauthors),
            "labelled": bool(flag is True or markers)}


def links_of(text, *extra):
    found = []
    for chunk in (text, *extra):
        for match in URLS.finditer(str(chunk or "")):
            link = public_link(match.group().rstrip(".,;:!?)"))
            if link and link not in found:
                found.append(link)
    return found


def _firm_by_key():
    return {key: (label, pattern) for key, label, pattern, _domains in _firm_index()}


def firm_relation_of(text, step_firm=None, account=None, basis=None, page_name=None, extra=None):
    """firmRelation: the account's own firm (role author/advertiser) or a firm mentioned in the text (role mentioned)."""
    firms = _firm_by_key()
    if step_firm and step_firm in firms:
        return {"firm": step_firm, "label": firms[step_firm][0], "role": "author" if not page_name else "advertiser",
                "quote": account or page_name, "basis": basis or "konto firmy z rejestru"}
    ad = {"page_name": page_name or "", "beneficiary_payers": extra or []}
    return relate(ad, text)


def _vendor_path(entry, query, observed, reason, sha=None):
    step = entry["step"]
    return {"method": "vendor_api", "vendor": VENDOR, "endpoint": ENDPOINTS[step["op"]][0], "query": query,
            "observedAt": observed, "adapter": "vendor_social", "sourceId": "vendor_social", "reason": reason,
            "responseSha256": sha or entry.get("bodySha256"), "quotaUnits": entry.get("creditsCharged") or 1, "import": False}


def _provenance(item, entry, observed):
    item["provenance"].update(vendor=VENDOR, vendorEndpoint=ENDPOINTS[entry["step"]["op"]][0], vendorCollectedAt=observed,
                              sourceUrl=entry["url"], sample=True, parser=PARSER_VERSION,
                              note="jednorazowa próbka z 21 XI 2026 zebrana przez usługę zewnętrzną; skan produktu nie woła usługi")
    return item


def _media_coverage(kind):
    return {"transcript": {"state": "unavailable", "source": "none", "windows": [], "durationSec": None,
                           "reason": f"{kind}: odczytano tekst i liczby, obrazu i wideo nie analizowano"},
            "frames": {"state": "not_collected", "moments": [], "intervalSec": None}}


def youtube_references(paths=None):
    """{platform: {account: {"captures": {id: url}, "creators": set}}} from links in YouTube descriptions."""
    refs = {"instagram": {}, "facebook": {}}
    rx = {"instagram": re.compile(r"(?:https?://)?(?:www\.)?instagram\.com/([A-Za-z0-9_.]+)", re.I),
          "facebook": re.compile(r"(?:https?://)?(?:www\.|m\.|pl-pl\.)?facebook\.com/([A-Za-z0-9_.\-]+)", re.I)}
    for path in (paths or YOUTUBE_REPLAYS):
        try:
            data = json.loads(gzip.decompress(Path(path).read_bytes()))
        except (OSError, ValueError):
            continue
        for item in data.get("captures", []):
            text = item.get("description") or ""
            for platform, pattern in rx.items():
                for match in pattern.finditer(text):
                    account = match.group(1).rstrip(".").lower()
                    entry = refs[platform].setdefault(account, {"captures": {}, "creators": set()})
                    entry["captures"].setdefault(item.get("id"), item.get("url"))
                    entry["creators"].add(item.get("creatorId"))
    return refs


# -- Instagram

def _ig_caption(node):
    edges = _dig(node, "edge_media_to_caption", "edges")
    if isinstance(edges, list) and edges:
        return str(_dig(edges[0], "node", "text") or "")
    caption = node.get("caption")
    return str(caption.get("text") or "") if isinstance(caption, dict) else str(caption or "")


def ig_creator(user, entry, observed, refs=None):
    """Creator record of an Instagram account from the profile (or the user block of the posts endpoint)."""
    username = str(user.get("username") or entry["step"]["params"].get("handle") or "").lower()
    step = entry["step"]
    followers = _first(_dig(user, "edge_followed_by", "count"), user.get("follower_count"))
    bio = str(user.get("biography") or "")[:300]
    firm = step.get("firm") if step.get("role") == "firm" else None
    relation = firm_relation_of(bio, firm, account="@" + username, basis="konto Instagram firmy: " + (step.get("verifiedBy") or "ig_username strony w Bibliotece Reklam"))
    creator = {"id": f"instagram:{username}", "name": str(user.get("full_name") or username)[:200], "platform": "instagram",
               "url": f"https://www.instagram.com/{username}/", "handle": "@" + username, "isSeed": False,
               "discoveredVia": "Konto firmy z Biblioteki Reklam" if firm else "Odnośnik w opisie publikacji YouTube",
               "status": "confirmed", "profileVerified": False, "isVerified": bool(user.get("is_verified")), "bio": bio,
               "category": user.get("category_name") or user.get("business_category_name"),
               "externalUrl": public_link(user.get("external_url")) if user.get("external_url") else None,
               "postCount": _count(_dig(user, "edge_owner_to_timeline_media", "count")), "firmRelation": relation if firm else None,
               "reach": {"asOf": observed, "source": VENDOR, "primary": "followerCount",
                         "metrics": {"followerCount": _metric(followers, observed)}},
               "bioSignals": _signals(bio) if bio else None}
    path = _vendor_path(entry, {"handle": username}, observed, "profil Instagram odczytany przez usługę zewnętrzną (próbka)")
    discoveries = [path]
    ref = (refs or {}).get(username)
    if ref and not firm:
        via = {"creatorIds": sorted(c for c in ref["creators"] if c), "captureIds": sorted(ref["captures"])[:8],
               "urls": [u for u in ref["captures"].values() if u][:8]}
        discoveries.append({"method": "crosslink", "adapter": "vendor_social", "sourceId": "instagram", "observedAt": observed,
                            "reason": "konto Instagram wskazane w opisach publikacji YouTube", "via": via, "quotaUnits": 0, "import": False})
        creator["crosslinkDiscovery"] = {"profileUrl": creator["url"], "references": via["captureIds"], "method": "crosslink",
                                         "description": "Konto wskazane w opisie; własność konta i związek z autorem opisu wymagają potwierdzenia.",
                                         "discoveredAt": observed}
    creator["discoveries"] = discoveries
    return creator


def ig_post(node, creator, entry, observed):
    code = str(node.get("shortcode") or node.get("code") or "")
    if not code:
        return None
    text = _ig_caption(node)
    step = entry["step"]
    firm = step.get("firm") if step.get("role") == "firm" else None
    flag = node.get("is_paid_partnership")
    coauthors = [str(c.get("username")) for c in (node.get("coauthor_producers") or []) if isinstance(c, dict) and c.get("username")]
    tagged = [str(_dig(e, "node", "user", "username")) for e in (_dig(node, "edge_media_to_tagged_user", "edges") or []) if _dig(e, "node", "user", "username")]
    tagged += [str(_dig(u, "user", "username")) for u in (_dig(node, "usertags", "in") or []) if _dig(u, "user", "username")]
    likes = _first(_dig(node, "edge_media_preview_like", "count"), node.get("like_count"))
    comments = _first(_dig(node, "edge_media_to_comment", "count"), node.get("comment_count"))
    views = _first(node.get("video_play_count"), node.get("play_count"), node.get("video_view_count"))
    when = _iso(_first(node.get("taken_at_timestamp"), node.get("taken_at"), node.get("created_at")))
    signals = _signals(text)
    relation = firm_relation_of(text, firm, account=creator["handle"], basis="konto firmy z rejestru") if firm else relate({}, text)
    item = capture(
        f"instagram:{code}", creator, (text.strip().splitlines() or [""])[0][:120] or creator["name"],
        f"https://www.instagram.com/p/{code}/", text, observed_at=observed, published_at=when, source_url=entry["url"],
        response_hash=entry.get("bodySha256") or "", scope="vendor_instagram_caption", module="M2" if firm else "M1",
        contentCompleteness="full", discovery=[_vendor_path(entry, {"handle": creator["handle"][1:]}, observed,
                                                            "post z profilu Instagram odczytanego przez usługę zewnętrzną (próbka)")],
        reach={"asOf": observed, "source": VENDOR, "primary": "likeCount", "metrics": {
            "likeCount": _metric(likes, observed), "commentCount": _metric(comments, observed),
            "viewCount": _metric(views, observed)}},
        mediaCoverage=_media_coverage("Instagram"), author=creator["name"], handle=creator["handle"],
        followerCount=creator["reach"]["metrics"]["followerCount"]["value"], isPaidPartnership=flag if isinstance(flag, bool) else None,
        disclosure=disclosure_of(text, flag, coauthors), hashtags=sorted({h.lower() for h in HASHTAG.findall(text)}),
        links=links_of(text), taggedAccounts=sorted(set(tagged))[:10], postKind=("video" if node.get("is_video") else "image"),
        isAd=bool(node.get("is_ad")) if node.get("is_ad") is not None else None, textSignals=text_signals(text),
        firmRelation=relation, **signals)
    return _provenance(item, entry, observed)


# -- Facebook posts

def fb_creator(post, entry, observed, refs=None):
    step = entry["step"]
    params = step.get("params", {})
    author = post.get("author") if isinstance(post.get("author"), dict) else {}
    page_id = str(params.get("pageId") or author.get("id") or "")
    slug = None
    if params.get("url"):
        slug = urlsplit(params["url"]).path.strip("/").split("/")[0]
    firm = step.get("firm") if step.get("role") == "firm" else None
    name = str(author.get("name") or author.get("short_name") or slug or page_id)[:200]
    relation = firm_relation_of("", firm, account=name, basis="strona firmy ustalona z wyszukiwania firm Biblioteki Reklam") if firm else None
    creator = {"id": f"facebook:page-{page_id}", "name": name, "platform": "facebook", "pageId": page_id,
               "url": f"https://www.facebook.com/{slug or page_id}", "handle": None, "isSeed": False,
               "discoveredVia": "Strona firmy z Biblioteki Reklam" if firm else "Odnośnik w opisie publikacji YouTube",
               "status": "confirmed", "profileVerified": False, "persistentId": page_id, "firmRelation": relation}
    discoveries = [_vendor_path(entry, params, observed, "wpisy strony Facebook odczytane przez usługę zewnętrzną (próbka)")]
    ref = (refs or {}).get((slug or "").lower())
    if ref and not firm:
        via = {"creatorIds": sorted(c for c in ref["creators"] if c), "captureIds": sorted(ref["captures"])[:8],
               "urls": [u for u in ref["captures"].values() if u][:8]}
        discoveries.append({"method": "crosslink", "adapter": "vendor_social", "sourceId": "facebook", "observedAt": observed,
                            "reason": "strona Facebook wskazana w opisach publikacji YouTube", "via": via, "quotaUnits": 0, "import": False})
    creator["discoveries"] = discoveries
    return creator


def fb_post(post, creator, entry, observed):
    post_id = str(post.get("id") or "")
    url = public_link(post.get("permalink")) or public_link(post.get("url"))
    if not post_id or not url:
        return None
    text = str(post.get("text") or "")
    step = entry["step"]
    firm = step.get("firm") if step.get("role") == "firm" else None
    flag = post.get("is_paid_partnership")
    when = _iso(_first(post.get("publishTime"), post.get("parent_publication_time"), post.get("creation_time")))
    relation = firm_relation_of(text, firm, account=creator["name"], basis="strona firmy z rejestru") if firm else relate({}, text)
    item = capture(
        f"facebook:{post_id}", creator, (text.strip().splitlines() or [""])[0][:120] or creator["name"], url, text,
        observed_at=observed, published_at=when, source_url=entry["url"], response_hash=entry.get("bodySha256") or "",
        scope="vendor_facebook_post_text", module="M2" if firm else "M1", contentCompleteness="full",
        discovery=[_vendor_path(entry, entry["step"].get("params", {}), observed, "wpis strony Facebook odczytany przez usługę zewnętrzną (próbka)")],
        reach={"asOf": observed, "source": VENDOR, "primary": "reactionCount", "metrics": {
            "reactionCount": _metric(post.get("reactionCount"), observed), "commentCount": _metric(post.get("commentCount"), observed),
            "shareCount": _metric(post.get("share_count"), observed), "viewCount": _metric(post.get("videoViewCount"), observed)}},
        mediaCoverage=_media_coverage("Facebook"), author=creator["name"], isPaidPartnership=flag if isinstance(flag, bool) else None,
        disclosure=disclosure_of(text, flag), hashtags=sorted({h.lower() for h in HASHTAG.findall(text)}), links=links_of(text),
        textSignals=text_signals(text), firmRelation=relation, **_signals(text))
    return _provenance(item, entry, observed)


# -- Ad Library

def _ad_texts(ad):
    snap = ad.get("snapshot") if isinstance(ad.get("snapshot"), dict) else {}
    parts, dynamic = [], False
    def add(value):
        nonlocal dynamic
        if isinstance(value, str) and value.strip():
            if TEMPLATE.search(value):
                dynamic = True
                return
            if value.strip() not in parts:
                parts.append(value.strip())
    add(_dig(snap, "body", "text"))
    add(snap.get("title"))
    add(snap.get("link_description"))
    for card in snap.get("cards") or []:
        if isinstance(card, dict):
            for field in ("body", "title", "link_description"):
                add(card.get(field))
    return parts, dynamic, snap


def ad_capture(ad, entry, observed, rank, details):
    ad_id = str(ad.get("ad_archive_id") or ad.get("adArchiveID") or "")
    page_id = str(ad.get("page_id") or ad.get("pageID") or "")
    if not ad_id or not page_id:
        return None, None
    parts, dynamic, snap = _ad_texts(ad)
    text = "\n".join(parts)
    page_name = str(ad.get("page_name") or snap.get("page_name") or "")
    platforms = [p.lower() for p in (ad.get("publisher_platform") or []) if isinstance(p, str)]
    primary = "facebook" if "facebook" in platforms or "instagram" not in platforms else "instagram"
    detail = details.get(ad_id) or {}
    aaa = detail.get("aaa_info") if isinstance(detail.get("aaa_info"), dict) else {}
    payers = [{"payer": p.get("payer"), "beneficiary": p.get("beneficiary")} for p in aaa.get("payer_beneficiary_data") or [] if isinstance(p, dict)]
    relation = relate({"page_name": page_name, "beneficiary_payers": payers}, text)
    module = "M2" if relation and relation["role"] == "advertiser" else "M1"
    started, stopped = _iso(ad.get("start_date")), _iso(ad.get("end_date"))
    creator = {"id": f"facebook:page-{page_id}", "platform": "facebook"}
    link_url = _first(snap.get("link_url"), next((c.get("link_url") for c in snap.get("cards") or [] if isinstance(c, dict) and c.get("link_url")), None))
    link = public_link(link_url) if link_url else None
    domain = urlsplit(link).hostname if link else None
    cta = _first(snap.get("cta_text"), next((c.get("cta_text") for c in snap.get("cards") or [] if isinstance(c, dict) and c.get("cta_text")), None))
    eu_reach = _count(aaa.get("eu_total_reach"))
    path = _vendor_path(entry, entry["step"].get("params", {}), observed, "reklama z Biblioteki Reklam Meta (PL) odczytana przez usługę zewnętrzną (próbka)")
    path["rank"] = rank
    item = capture(
        f"{primary}:ad-{ad_id}", creator, (parts[0] if parts else page_name or ad_id)[:120], f"https://www.facebook.com/ads/library/?id={ad_id}",
        text, observed_at=observed, published_at=started, source_url=entry["url"], response_hash=entry.get("bodySha256") or "",
        scope="meta_ad_library_text", module=module, contentCompleteness="full", discovery=[path], author=page_name,
        reach={"asOf": observed, "source": VENDOR, "primary": "euTotalReach", "metrics": {"euTotalReach": {
            "value": eu_reach, "state": "observed" if eu_reach is not None else "not_collected", "observedAt": observed, "source": VENDOR}}},
        mediaCoverage={"transcript": {"state": "unavailable", "source": "none", "windows": [], "durationSec": None,
                                      "reason": "Reklama: odczytano tekst i dane biblioteki, obrazu i wideo nie analizowano"},
                       "frames": {"state": "not_collected", "moments": [], "intervalSec": None}},
        adId=ad_id, publisherPlatforms=platforms, adStatus="active" if ad.get("is_active") else "inactive",
        adDeliveryStartDate=started[:10] if started else None, adDeliveryStopDate=stopped[:10] if stopped else None,
        adBody=text, adTitle=snap.get("title") if not TEMPLATE.search(str(snap.get("title") or "")) else None,
        callToAction=cta, linkDomain=domain, links=links_of(text, link or ""), versionsCount=_count(ad.get("collation_count")),
        multipleVersions=bool((ad.get("collation_count") or 0) > 1), displayFormat=snap.get("display_format"),
        dynamicCreative=dynamic or snap.get("display_format") == "DCO", pageLikeCount=_count(snap.get("page_like_count")),
        finservAdData=ad.get("finserv_ad_data"), beneficiaryPayers=payers, euTotalReach=eu_reach,
        targeting={"targetsEu": aaa.get("targets_eu"), "locations": [l.get("name") for l in aaa.get("location_audience") or [] if isinstance(l, dict)],
                   "ages": aaa.get("age_audience"), "gender": aaa.get("gender_audience")} if aaa else None,
        euReachBreakdown=aaa.get("age_country_gender_reach_breakdown") if aaa else None,
        textSignals=text_signals(text), firmRelation=relation, **_signals(text))
    item["platform"] = primary
    item["creatorId"] = creator["id"]
    item["provenance"]["sourceUrl"] = entry["url"]
    _provenance(item, entry, observed)
    firm_page = relation["role"] == "advertiser" if relation else False
    crt = {"id": creator["id"], "name": page_name[:200] or page_id, "platform": "facebook", "url": f"https://www.facebook.com/{page_id}",
           "handle": None, "isSeed": False, "discoveredVia": "Reklama w Bibliotece Reklam Meta", "status": "confirmed",
           "profileVerified": False, "persistentId": page_id, "pageId": page_id, "pageLikeCount": _count(snap.get("page_like_count")),
           "pageCategories": [c for c in snap.get("page_categories") or [] if isinstance(c, str)],
           "discoveries": [path], "firmRelation": relation if firm_page else None}
    return item, crt


# -- build

def _load_raw(directory, entry):
    return json.loads(gzip.decompress((Path(directory) / entry["file"]).read_bytes()))


def build_result(directory=SAMPLE_DIR, references=None):
    """Replay of the stored sample: creators, captures, source rows. Pure function of the stored files."""
    directory = Path(directory)
    log = json.loads((directory / "requests.json").read_text(encoding="utf-8"))
    refs = youtube_references() if references is None else references
    entries = [e for e in log["requests"] if e.get("ok") and e.get("file") and not e.get("discard")]
    creators, captures, pages = {}, {}, []
    details = {}
    for entry in entries:
        if entry["step"]["op"] == "fb_ad_detail":
            data = _load_raw(directory, entry)
            if data.get("adArchiveID") is not None:
                details[str(data["adArchiveID"])] = data
    ig_accounts, fb_pages, rank = set(), set(), 0
    for entry in entries:
        op, observed = entry["step"]["op"], entry.get("observedAt") or entry["at"]
        data = _load_raw(directory, entry)
        if op in ("ig_profile", "ig_posts"):
            user = _dig(data, "data", "user") if op == "ig_profile" else data.get("user")
            if not isinstance(user, dict):
                continue
            creator = ig_creator(user, entry, observed, refs["instagram"])
            creators.setdefault(creator["id"], creator)
            ig_accounts.add(creator["id"])
            nodes = [e.get("node") for e in (_dig(user, "edge_owner_to_timeline_media", "edges") or []) if isinstance(e, dict)] if op == "ig_profile" else data.get("items") or []
            for node in nodes:
                item = ig_post(node, creator, entry, observed) if isinstance(node, dict) else None
                if item:
                    captures.setdefault(item["id"], item)
        elif op == "fb_posts":
            posts = [p for p in data.get("posts") or [] if isinstance(p, dict)]
            if not posts:
                continue
            creator = fb_creator(posts[0], entry, observed, refs["facebook"])
            creators.setdefault(creator["id"], creator)
            fb_pages.add(creator["id"])
            for post in posts:
                item = fb_post(post, creator, entry, observed)
                if item:
                    captures.setdefault(item["id"], item)
        elif op in ("fb_company_ads", "fb_ads_search"):
            for ad in data.get("results") or data.get("searchResults") or []:
                rank += 1
                item, creator = ad_capture(ad, entry, observed, rank, details) if isinstance(ad, dict) else (None, None)
                # a keyword search returns many unrelated ads: only those that name a registered firm are kept
                if item and op == "fb_ads_search" and not item.get("firmRelation"):
                    continue
                if item:
                    if item["id"] in captures:
                        captures[item["id"]]["discovery"].extend(item["discovery"])
                    else:
                        captures[item["id"]] = item
                    creators.setdefault(creator["id"], creator)
        elif op == "fb_company_search":
            pages.append({"query": entry["step"]["params"].get("query"), "firm": entry["step"].get("firm"),
                          "results": [{k: r.get(k) for k in ("page_id", "name", "ig_username", "ig_followers", "country", "category")}
                                      for r in (data.get("searchResults") or [])[:8] if isinstance(r, dict)]})
    items = list(captures.values())
    return {"creators": list(creators.values()), "captures": items, "sources": source_rows(items, creators, log),
            "status": "ok" if items else "empty", "resume": None, "vendorSample": sample_summary(items, creators, log),
            "fixtureNote": ("Jednorazowa próbka z 2026-11-21 zebrana przez usługę zewnętrzną (ScrapeCreators) dla Instagrama, "
                            "Facebooka i Biblioteki Reklam Meta (PL). Zapis replay; skan produktu nie woła usługi.")}


def sample_summary(items, creators, log):
    ig = [c for c in items if c["id"].startswith("instagram:") and not c["id"].startswith("instagram:ad-")]
    fb = [c for c in items if c["provenance"].get("scope") == "vendor_facebook_post_text"]
    ads = [c for c in items if c.get("adId")]
    return {"vendor": VENDOR, "collectedOn": "2026-11-21", "creditsSpent": log.get("creditsSpent"),
            "creditsRemaining": log.get("creditsRemaining"),
            "instagram": {"accounts": len({c["creatorId"] for c in ig}), "posts": len(ig)},
            "facebook": {"pages": len({c["creatorId"] for c in fb}), "posts": len(fb)},
            "ads": {"count": len(ads), "advertisers": len({c["creatorId"] for c in ads}),
                    "withEuReach": sum(1 for c in ads if c.get("euTotalReach") is not None)},
            "firmsWithMaterial": sorted({(c.get("firmRelation") or {}).get("firm") for c in items if c.get("firmRelation")} - {None}),
            "m2": sum(1 for c in items if c["module"] == "M2"), "m1": sum(1 for c in items if c["module"] == "M1")}


def source_rows(items, creators, log):
    at = max((e.get("observedAt") or e["at"] for e in log["requests"] if e.get("ok")), default=None)
    rows = []
    def row(sid, name, url, count, detail, scope):
        status = "ok" if count else "empty"
        return {"id": sid, "name": name, "url": url, "status": status, "count": count, "observedAt": at, "lastSuccessAt": at if count else None,
                "sampleDate": "2026-11-21", "message": SAMPLE_STATUS.format(detail=detail), "nextStep": NEXT_STEP, "scope": scope,
                "vendor": VENDOR, "path": "vendor_sample"}
    ig = [c for c in items if c["id"].startswith("instagram:") and not c.get("adId")]
    fb = [c for c in items if c["provenance"].get("scope") == "vendor_facebook_post_text"]
    ig_ads = [c for c in items if c.get("adId") and c["platform"] == "instagram"]
    fb_ads = [c for c in items if c.get("adId") and c["platform"] == "facebook"]
    n = lambda xs: len({c["creatorId"] for c in xs})
    rows.append(row("instagram", "Instagram · wpisy (próbka z usługi zewnętrznej)", "https://www.instagram.com/", len(ig),
                    f"{n(ig)} kont, {len(ig)} postów", "Podpisy, liczby i flaga płatnego partnerstwa; bez obrazu, wideo i komentarzy"))
    rows.append(row("facebook", "Facebook · wpisy (próbka z usługi zewnętrznej)", "https://www.facebook.com/", len(fb),
                    f"{n(fb)} stron, {len(fb)} postów", "Tekst wpisów stron i liczby; po 3 wpisy na stronę; bez komentarzy"))
    ads = fb_ads + ig_ads
    rows.append(row("facebook-ads", "Facebook · reklamy (próbka z usługi zewnętrznej)", "https://www.facebook.com/ads/library/", len(fb_ads),
                    f"{n(fb_ads)} reklamodawców, {len(fb_ads)} reklam", "Tekst reklam wyświetlanych w PL (Biblioteka Reklam Meta)"))
    rows.append(row("instagram-ads", "Instagram · reklamy (próbka z usługi zewnętrznej)", "https://www.facebook.com/ads/library/", len(ig_ads),
                    f"{n(ig_ads)} reklamodawców, {len(ig_ads)} reklam", "Reklamy z platformą Instagram bez Facebooka (w próbce zwykle 0: platformy są na liście obok Facebooka)"))
    summary = {"id": "vendor_social", "name": "Usługa zewnętrzna · próbka FB/IG/reklamy (ScrapeCreators)", "url": "https://scrapecreators.com/",
               "status": "ok" if items else "empty", "count": len(items), "observedAt": at, "sampleDate": "2026-11-21",
               "scope": "Datowana próbka; skan produktu nie wywołuje usługi", "creditsSpent": log.get("creditsSpent"),
               "creditsRemaining": log.get("creditsRemaining"), "vendor": VENDOR, "adsTotal": len(ads),
               "message": SAMPLE_STATUS.format(detail=f"{len(items)} materiałów"), "nextStep": NEXT_STEP}
    return [summary, *rows]


# -- stored sample, manifest, adapter

def write_json(path, value):
    path = Path(path)
    if path.suffix == ".gz":
        path.write_bytes(gzip.compress(json.dumps(value, ensure_ascii=False, sort_keys=True).encode(), mtime=0))
    else:
        path.write_text(json.dumps(value, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def read_sample(path=SAMPLE_REPLAY):
    return json.loads(gzip.decompress(Path(path).read_bytes()))


def manifest_of(directory, result, replay_path):
    directory = Path(directory)
    log = json.loads((directory / "requests.json").read_text(encoding="utf-8"))
    files = []
    for entry in log["requests"]:
        if entry.get("ok") and entry.get("file"):
            data = (directory / entry["file"]).read_bytes()
            files.append({"file": entry["file"], "op": entry["step"]["op"], "query": entry["step"].get("params"),
                          "gzSha256": sha256(data).hexdigest(), "storedJsonSha256": entry.get("storedSha256"),
                          "responseBodySha256": entry.get("bodySha256"), "observedAt": entry.get("observedAt"),
                          "creditsCharged": entry.get("creditsCharged"), "creditsRemaining": entry.get("creditsRemaining")})
    return {"parser": PARSER_VERSION, "vendor": VENDOR, "collectedOn": "2026-11-21", "api": API, "keyHeader": "x-api-key: REDACTED",
            "creditsSpent": log.get("creditsSpent"), "creditsRemaining": log.get("creditsRemaining"), "stopped": log.get("stopped"),
            "requests": len(log["requests"]), "failedRequests": sum(1 for e in log["requests"] if not e.get("ok")),
            "sanitization": "Z odpowiedzi usunięto komentarze użytkowników, listy obserwujących, podpisane adresy mediów i profilowych; "
                            "zostały publiczne nazwy kont, treść postów i reklam oraz liczby.",
            "replay": {"file": Path(replay_path).name, "gzSha256": sha256(Path(replay_path).read_bytes()).hexdigest(),
                       "captures": len(result["captures"]), "creators": len(result["creators"])},
            "sample": result["vendorSample"], "files": files}


def discover(ctx):
    """Adapter ``vendor-social-replay``. Reads ONLY the stored sample. It never calls the service, whatever the mode
    or the environment: the brief forbids paid APIs in the product, so this source is a dated replay."""
    options = ctx.options or {}
    path = Path(options.get("vendor_social_sample") or SAMPLE_REPLAY)
    try:
        result = read_sample(path)
    except (OSError, ValueError):
        at = ctx.clock()
        row = {"id": "vendor_social", "name": "Usługa zewnętrzna · próbka FB/IG/reklamy (ScrapeCreators)", "status": "empty", "count": 0,
               "observedAt": at, "message": "Brak zapisanej próbki z usługi zewnętrznej.", "nextStep": NEXT_STEP}
        return {"creators": [], "captures": [], "sources": [row], "status": "empty", "resume": None}
    for item in result.get("captures", []):
        item["mode"] = "replay"
        item.setdefault("provenance", {}).setdefault("fixture", "social-2026-11-21/vendor/replay-vendor.json.gz")
    result.pop("fixtureNote", None)
    return result


def build_main(args):
    result = build_result(args.raw_dir)
    write_json(args.out, result)
    write_json(args.manifest, manifest_of(args.raw_dir, result, args.out))
    s = result["vendorSample"]
    print(f"IG: {s['instagram']['accounts']} kont, {s['instagram']['posts']} postów; FB: {s['facebook']['pages']} stron, "
          f"{s['facebook']['posts']} postów; reklamy: {s['ads']['count']} ({s['ads']['advertisers']} reklamodawców); "
          f"M2 {s['m2']}, M1 {s['m1']}")
    return 0


# --- command line ---------------------------------------------------------------------------------------------------

def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(prog="python -m collectors.vendor_social",
                                     description="Jednorazowa próbka FB/IG/Biblioteki Reklam przez usługę zewnętrzną.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect", help="wykonaj plan zapytań (jedyna komenda, która woła usługę)")
    c.add_argument("--plan", required=True)
    c.add_argument("--max-credits", type=int, required=True, help="limit kredytów w tym przebiegu")
    c.add_argument("--reserve", type=int, default=RESERVE, help="saldo, poniżej którego przerywamy")
    c.add_argument("--out-dir", default=str(SAMPLE_DIR))
    c.add_argument("--pause", type=float, default=PAUSE)
    b = sub.add_parser("build", help="zbuduj replay i manifest z zapisanych odpowiedzi (bez sieci)")
    b.add_argument("--raw-dir", default=str(SAMPLE_DIR))
    b.add_argument("--out", default=str(SAMPLE_REPLAY))
    b.add_argument("--manifest", default=str(SAMPLE_MANIFEST))
    args = parser.parse_args(argv)
    if args.cmd == "collect":
        key, problem = load_key()
        if not key:
            print(f"needs_key: {problem}; nie wykonano żadnego żądania.", file=sys.stderr)
            return 3
        plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
        log = collect(plan, args.out_dir, key, args.max_credits, args.reserve, args.pause)
        ok = sum(1 for r in log["requests"] if r.get("ok"))
        print(f"żądań: {len(log['requests'])} (udanych {ok}), kredyty zużyte łącznie: {log['creditsSpent']}, "
              f"saldo: {log['creditsRemaining']}, stop: {(log['stopped'] or {}).get('reason')}")
        return 0 if not log["stopped"] or log["stopped"]["reason"] in ("max_credits", "reserve") else 1
    return build_main(args)


if __name__ == "__main__":
    sys.exit(main())
