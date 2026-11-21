"""Meta Ad Library (Graph API ``ads_archive``): Facebook and Instagram ads shown in Poland.

The Ad Library is Meta's public transparency archive. For the EU it holds the ads shown in the EU, with
text, advertiser page, platforms, delivery dates, EU reach and, for EU ads, payer and beneficiary. Access is
a user access token of an identity-verified Facebook account. The token is read from a file outside the
repository (``INVESTWATCH_META_TOKEN_FILE`` or ``~/.config/investwatch/meta.token``). Without it the source
reports ``needs_key`` and costs nothing. A token never reaches a log, a stored URL or a result: every URL is
stored with ``access_token=REDACTED`` and the token string is removed from every message.

Nothing here logs in, scrapes the public library page or works around a refusal. A rate limit or an
OAuth error ends the run with a status and the reason.
"""

from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .common import MAX_TEXT, SourceError, capture, digest, open_url, public_link, source_result, utc_now
from .social import _firm_index

GRAPH = "https://graph.facebook.com/v21.0/ads_archive"
DEFAULT_TOKEN_FILE = "~/.config/investwatch/meta.token"
TOKEN_SHAPE = re.compile(r"[A-Za-z0-9_|\-]{20,512}\Z")
FIELDS = ("id,ad_creation_time,ad_creative_bodies,ad_creative_link_captions,ad_creative_link_descriptions,"
          "ad_creative_link_titles,ad_delivery_start_time,ad_delivery_stop_time,ad_snapshot_url,beneficiary_payers,"
          "eu_total_reach,languages,page_id,page_name,publisher_platforms,target_ages,target_gender,target_locations")
PAGE_SIZE = 50
MAX_PAGES = 2
REQUEST_PAUSE = 1.0
CACHE_HOURS = 12
RATE_LIMIT_CODES = {4, 17, 32, 613, 80004}
AUTH_CODES = {102, 190}
RATE_RETRY_SECONDS = 3600
PHRASES = ("konto maklerskie", "inwestowanie", "kod promocyjny broker", "darmowe akcje", "ETF inwestowanie",
           "handel CFD", "giełda akcje", "IKE IKZE")
SEARCH_TERMS = {"bos": "DM BOŚ", "pkobp": "PKO Biuro Maklerskie", "ing": "ING Bank Śląski", "mbank": "mBank eMakler",
                "pekao": "Pekao Biuro Maklerskie", "santander": "Santander Biuro Maklerskie",
                "millennium": "Bank Millennium inwestowanie"}
NEXT_STEP = ("Właściciel: potwierdzić tożsamość konta na facebook.com/ID, utworzyć aplikację na developers.facebook.com, "
             "wygenerować token użytkownika w Graph API Explorer i zapisać go w ~/.config/investwatch/meta.token (tryb 600).")
URLS = re.compile(r"https?://[^\s<>\"']+", re.I)


def load_token(environ=None):
    """Token from the file outside the repo, or None. Returns (token, problem)."""
    environ = os.environ if environ is None else environ
    path = Path(environ.get("INVESTWATCH_META_TOKEN_FILE") or DEFAULT_TOKEN_FILE).expanduser()
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None, "brak pliku z tokenem"
    if not text:
        return None, "plik z tokenem jest pusty"
    if not TOKEN_SHAPE.fullmatch(text):
        return None, "plik z tokenem ma nieoczekiwany format"
    return text, None


def token_file_mode_warning(environ=None):
    environ = os.environ if environ is None else environ
    path = Path(environ.get("INVESTWATCH_META_TOKEN_FILE") or DEFAULT_TOKEN_FILE).expanduser()
    try:
        return bool(path.stat().st_mode & 0o077)
    except OSError:
        return False


def redact_url(url):
    parts = urlsplit(url)
    query = [(k, "REDACTED" if k.lower() in ("access_token", "token") else v) for k, v in parse_qsl(parts.query, keep_blank_values=True)]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))


def scrub(text, token):
    text = str(text)
    if token:
        text = text.replace(token, "REDACTED")
    return re.sub(r"(?i)(access_token=)[^&\s\"'\\]+", r"\1REDACTED", text)


def queries():
    """Brand queries from the firm index, then Polish investment phrases: (kind, query, firm key or None)."""
    out, seen = [], set()
    for key, label, _pattern, _domains in _firm_index():
        term = SEARCH_TERMS.get(key) or re.sub(r"\s*\(.*?\)", "", label).strip()
        if term.lower() not in seen:
            seen.add(term.lower())
            out.append(("brand", term[:100], key))
    out.extend(("phrase", phrase, None) for phrase in PHRASES)
    return out


def _time(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        moment = datetime.fromisoformat(re.sub(r"([+-]\d\d)(\d\d)$", r"\1:\2", value.replace("Z", "+00:00")))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _texts(ad):
    parts = []
    for field, label in (("ad_creative_bodies", "Treść"), ("ad_creative_link_titles", "Tytuł linku"),
                         ("ad_creative_link_descriptions", "Opis linku"), ("ad_creative_link_captions", "Podpis linku")):
        values = ad.get(field)
        for value in (values if isinstance(values, list) else []):
            if isinstance(value, str) and value.strip() and value.strip() not in parts:
                parts.append(value.strip())
    return parts


def _firms():
    return [(key, label, pattern, domains) for key, label, pattern, domains in _firm_index()]


def relate(ad, text):
    """The registered firm an ad concerns and in which role (advertiser, payer, beneficiary, mentioned)."""
    firms = _firms()
    page = str(ad.get("page_name") or "")
    roles = []
    for key, label, pattern, domains in firms:
        if pattern.search(page) or any(d in page.lower() for d in domains):
            return {"firm": key, "label": label, "role": "advertiser", "quote": page}
    for entry in ad.get("beneficiary_payers") if isinstance(ad.get("beneficiary_payers"), list) else []:
        for role in ("payer", "beneficiary"):
            name = str(entry.get(role) or "") if isinstance(entry, dict) else ""
            for key, label, pattern, domains in firms:
                if name and pattern.search(name):
                    roles.append({"firm": key, "label": label, "role": role, "quote": name})
    if roles:
        return sorted(roles, key=lambda r: r["role"] != "payer")[0]
    for key, label, pattern, domains in firms:
        match = pattern.search(text)
        domain = next((d for d in domains if d in text.lower()), None)
        if match or domain:
            return {"firm": key, "label": label, "role": "mentioned", "quote": match.group(0) if match else domain}
    return None


def _count(value):
    return value if type(value) is int else None


def make_capture(ad, query_info, observed, response_hash, request_url, rank, page, token):
    ad_id = str(ad.get("id") or "")
    platforms = [p.lower() for p in ad.get("publisher_platforms") or [] if isinstance(p, str)]
    primary = "facebook" if "facebook" in platforms or "instagram" not in platforms else "instagram"
    texts = _texts(ad)
    text = "\n".join(texts)
    page_id, page_name = str(ad.get("page_id") or ""), str(ad.get("page_name") or "")
    creator = {"id": f"facebook:page-{page_id}", "platform": "facebook"}
    relation = relate(ad, text)
    module = "M2" if relation and relation["role"] == "advertiser" else "M1"
    started = _time(ad.get("ad_delivery_start_time")) or _time(ad.get("ad_creation_time"))
    links = []
    for chunk in [*texts, *(ad.get("ad_creative_link_captions") or [])]:
        for match in URLS.finditer(str(chunk)):
            link = public_link(match.group().rstrip(".,;:!?)"))
            if link and link not in links:
                links.append(link)
    snapshot = redact_url(ad["ad_snapshot_url"]) if isinstance(ad.get("ad_snapshot_url"), str) else None
    reach = _count(ad.get("eu_total_reach"))
    kind, query, _key = query_info
    path = {"method": "ad_library", "adapter": "meta_ads", "sourceId": "meta_ads", "query": query, "queryKind": kind,
            "rank": rank, "page": page, "sourceUrl": redact_url(request_url), "observedAt": observed,
            "responseSha256": response_hash, "reason": f"wynik Biblioteki Reklam Meta ({kind}: {query})",
            "quotaUnits": 1, "import": False}
    item = capture(
        f"{primary}:ad-{ad_id}", creator, (texts[0] if texts else page_name or ad_id)[:120],
        f"https://www.facebook.com/ads/library/?id={ad_id}", text, observed_at=observed, published_at=started,
        source_url=redact_url(request_url), response_hash=response_hash, scope="meta_ad_library_text", module=module,
        contentCompleteness="full", discovery=[path], author=page_name,
        reach={"asOf": observed, "source": "meta_ad_library", "primary": "euTotalReach", "metrics": {"euTotalReach": {
            "value": reach, "state": "observed" if reach is not None else "not_collected", "observedAt": observed,
            "source": "meta_ad_library"}}},
        mediaCoverage={"transcript": {"state": "unavailable", "source": "none", "windows": [], "durationSec": None,
                                      "reason": "Reklama: odczytano tekst i dane biblioteki, obrazu i wideo nie analizowano"},
                       "frames": {"state": "not_collected", "moments": [], "intervalSec": None}},
        adId=ad_id, publisherPlatforms=platforms, adSnapshotUrl=snapshot, links=links,
        adDeliveryStopTime=_time(ad.get("ad_delivery_stop_time")), adCreationTime=_time(ad.get("ad_creation_time")),
        languages=[x for x in ad.get("languages") or [] if isinstance(x, str)],
        beneficiaryPayers=[b for b in ad.get("beneficiary_payers") or [] if isinstance(b, dict)],
        targeting={"locations": ad.get("target_locations") or [], "ages": ad.get("target_ages") or [],
                   "gender": ad.get("target_gender")},
        firmRelation=relation,
    )
    item["platform"] = primary
    item["creatorId"] = creator["id"]
    item["provenance"]["sourceUrl"] = redact_url(request_url)
    return item, {"id": creator["id"], "name": page_name[:200] or page_id, "platform": "facebook",
                  "url": f"https://www.facebook.com/{page_id}", "handle": None, "isSeed": False,
                  "discoveredVia": "Reklama w Bibliotece Reklam Meta", "status": "confirmed", "profileVerified": True,
                  "persistentId": page_id, "pageId": page_id,
                  "discoveries": [path], "firmRelation": relation if relation and relation["role"] == "advertiser" else None}


def request_url(token, query, after=None):
    params = {"access_token": token, "ad_type": "ALL", "ad_reached_countries": '["PL"]', "ad_active_status": "ALL",
              "search_terms": query, "search_type": "KEYWORD_UNORDERED", "fields": FIELDS, "limit": PAGE_SIZE}
    if after:
        params["after"] = after
    return GRAPH + "?" + urlencode(params)


def _default_fetch(url):
    return open_url(url, keep_errors=True)


def _blocked(status, error, at, token, message=None):
    text = scrub(message or "", token)[:300]
    last = {"code": error, "message": text, "at": at, "nextStep": NEXT_STEP if error != "rate_limited" else
            "Skan wznowi się po upływie limitu Meta (zwykle do godziny); zapisano kursor."}
    return last


def discover(ctx):
    clock = ctx.clock
    at = clock()
    token, problem = load_token(ctx.options.get("env"))
    token = ctx.options.get("meta_token") or token
    if not token:
        message = f"Brak tokenu Biblioteki Reklam Meta ({problem or 'brak pliku'}); reklamy FB i IG nie są pobierane."
        last = {"code": "needs_key", "message": message, "at": at, "nextStep": NEXT_STEP}
        rows = [{"id": "meta_ads", "name": "Meta · Biblioteka Reklam", "url": "https://www.facebook.com/ads/library/",
                 "status": "needs_key", "count": 0, "observedAt": at, "error": message, "lastError": last,
                 "scope": "Reklamy wyświetlane w PL (Facebook i Instagram), API ads_archive"}]
        rows += _platform_rows(0, 0, at, "needs_key", last)
        return {"creators": [], "captures": [], "sources": rows, "status": "needs_key", "resume": ctx.state.get("resume")}
    fetch = ctx.options.get("meta_fetch") or _default_fetch
    sleep, pause = ctx.options.get("sleep", time.sleep), ctx.options.get("pause", REQUEST_PAUSE)
    budget = ctx.budget if ctx.budget is not None else 30
    resume = ctx.state.get("resume") if isinstance(ctx.state.get("resume"), dict) else {}
    done = {q: t for q, t in (resume.get("done") or {}).items() if _fresh(t, at)}
    plan = queries()
    start = resume.get("next") or {}
    ads, creators, summaries = {}, {}, []
    used, status, error, retry_at, rank = 0, "ok", None, None, 0
    pending_next = None
    first = True
    for index, info in enumerate(plan):
        kind, query, _key = info
        if query in done and not (start and start.get("query") == query):
            summaries.append({"query": query, "kind": kind, "count": 0, "pages": 0, "status": "cached"})
            continue
        after = start.get("after") if start.get("query") == query else None
        pages, found = 0, 0
        while pages < MAX_PAGES:
            if used >= budget:
                pending_next = {"query": query, "after": after}
                status = "partial"
                error = error or "Wyczerpano budżet żądań przebiegu; wznowienie od zapisanego kursora."
                break
            if not first:
                sleep(pause)
            first = False
            url = request_url(token, query, after)
            used += 1
            ctx.heartbeat()
            try:
                code, headers, body = fetch(url)
            except SourceError as exc:
                status, error = "error", scrub(exc, token)
                pending_next = {"query": query, "after": after}
                break
            observed = clock()
            try:
                data = json.loads(body)
            except ValueError:
                data = {}
            failure = data.get("error") if isinstance(data, dict) else None
            if failure or code != 200:
                failure = failure if isinstance(failure, dict) else {}
                number = failure.get("code")
                message = scrub(failure.get("message") or f"HTTP {code}", token)
                if number in RATE_LIMIT_CODES or code == 429:
                    status, error = "rate_limited", f"Limit zapytań Meta (kod {number or code}): {message}"
                    retry_at = _plus(at, RATE_RETRY_SECONDS)
                    last = _blocked(status, "rate_limited", at, token, error)
                elif number in AUTH_CODES or code in (401, 403):
                    status, error = "error", f"Token Meta odrzucony (kod {number or code}): {message}"
                    last = _blocked(status, "oauth_190" if number == 190 else f"auth_{number or code}", at, token, error)
                else:
                    status, error = "error", f"Biblioteka Reklam zwróciła błąd (HTTP {code}, kod {number}): {message}"
                    last = _blocked(status, f"graph_{number or code}", at, token, error)
                pending_next = {"query": query, "after": after}
                summaries.append({"query": query, "kind": kind, "count": found, "pages": pages, "status": status})
                return _finish(ads, creators, summaries, status, error, last, used, at, token, retry_at, resume, done, pending_next, plan)
            response_hash = sha256(body).hexdigest()
            rows = data.get("data") if isinstance(data.get("data"), list) else []
            for ad in rows:
                if not isinstance(ad, dict) or not ad.get("id") or not ad.get("page_id"):
                    continue
                rank += 1
                item, creator = make_capture(ad, info, observed, response_hash, url, rank, pages + 1, token)
                if item["id"] in ads:
                    _merge_path(ads[item["id"]], item["discovery"][0])
                else:
                    ads[item["id"]] = item
                creators.setdefault(creator["id"], creator)
                found += 1
            pages += 1
            paging = data.get("paging") if isinstance(data.get("paging"), dict) else {}
            cursor = (paging.get("cursors") or {}).get("after") if isinstance(paging.get("cursors"), dict) else None
            if not rows or not paging.get("next") or not cursor:
                done[query] = observed
                after = None
                break
            after = cursor
        else:
            done[query] = clock()  # page limit reached: this query is covered as far as the run goes
        summaries.append({"query": query, "kind": kind, "count": found, "pages": pages,
                          "status": "ok" if query in done else "partial"})
        start = {}
        if pending_next or status in ("error", "rate_limited"):
            break
    return _finish(ads, creators, summaries, status, error, None, used, at, token, retry_at, resume, done, pending_next, plan)


def _fresh(then, now):
    try:
        return (datetime.fromisoformat(now) - datetime.fromisoformat(then)).total_seconds() < CACHE_HOURS * 3600
    except (TypeError, ValueError):
        return False


def _plus(at, seconds):
    return datetime.fromtimestamp(datetime.fromisoformat(at).timestamp() + seconds, timezone.utc).replace(microsecond=0).isoformat()


def _merge_path(item, path):
    paths = item["discovery"]
    if not any(p["query"] == path["query"] for p in paths):
        paths.append(path)


def _platform_rows(fb, ig, at, status, last=None, error=None):
    rows = []
    for platform, label, count in (("facebook", "Facebook", fb), ("instagram", "Instagram", ig)):
        row = {"id": f"{platform}-ads", "name": f"{label} · reklamy (Biblioteka Reklam Meta)",
               "url": "https://www.facebook.com/ads/library/", "status": status, "count": count, "observedAt": at,
               "scope": "Reklamy wyświetlane w PL; wpisy organiczne to osobne źródło"}
        if status != "ok" and status != "empty":
            row["error"] = error or (last or {}).get("message")
            row["lastError"] = last
        else:
            row["lastSuccessAt"] = at
        rows.append(row)
    return rows


def _finish(ads, creators, summaries, status, error, last, used, at, token, retry_at, resume, done, pending_next, plan):
    captures = list(ads.values())
    fb = sum(1 for c in captures if c["platform"] == "facebook")
    ig = sum(1 for c in captures if c["platform"] == "instagram")
    if status == "ok" and not captures:
        status = "ok" if any(q.get("status") == "cached" for q in summaries) else "empty"
    summary = source_result("meta_ads", "Meta · Biblioteka Reklam", "https://www.facebook.com/ads/library/", at,
                            count=len(captures), scope="Reklamy wyświetlane w PL (Facebook i Instagram), API ads_archive")
    summary["status"] = status
    summary["requests"] = used
    summary["queries"] = summaries
    summary["m2Ads"] = sum(1 for c in captures if c["module"] == "M2")
    summary["m1WithFirmRelation"] = sum(1 for c in captures if c["module"] == "M1" and c.get("firmRelation"))
    if status in ("partial", "error", "rate_limited"):
        summary.pop("lastSuccessAt", None)
        summary["error"] = scrub(error or "", token)[:300]
        summary["lastError"] = last or {"code": "meta_ads_partial", "message": summary["error"], "at": at,
                                        "nextStep": "Kolejny skan wznowi odczyt od zapisanego kursora."}
    if token_file_mode_warning():
        summary["warning"] = "Plik tokenu jest czytelny dla innych użytkowników; ustaw tryb 600."
    if retry_at:
        summary["retryAt"] = retry_at
    row_status = status if status in ("error", "rate_limited") else ("ok" if captures else status)
    rows = [summary, *_platform_rows(fb, ig, at, row_status if row_status != "partial" else "partial", summary.get("lastError"), summary.get("error"))]
    result = {"creators": list(creators.values()), "captures": captures, "sources": rows, "status": status,
              "resume": {"done": done, "next": pending_next} if (pending_next or done) else None}
    if retry_at:
        result["retryAt"] = retry_at
    return json.loads(scrub(json.dumps(result, ensure_ascii=False), token))
