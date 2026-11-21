"""Adapter contract for discovery sources (contract v2, step S3).

An adapter is ``discover(ctx) -> {creators, captures, sources, status, resume, retryAt, quota}``.
``ctx`` carries the mode, the persisted per-source state (cursor, etag, retry), the unit budget the
quota ledger still allows and ``ctx.heartbeat()``, which extends the scan lease. The runner in this
module validates every result, turns an adapter exception into a source error (never a failed scan),
persists each finished step and skips finished steps when an interrupted scan is resumed.

This module has no dependency on ``api``; persistence is injected through a runner. ``MemoryRunner``
keeps nothing, ``api.jobs.ScanRunner`` stores steps, source state and the quota ledger in SQLite.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import json
import re
from zoneinfo import ZoneInfo
import os

YOUTUBE_ID = re.compile(r"youtube:[A-Za-z0-9_-]{11}")
CANONICAL_ID = re.compile(r"[a-z][a-z0-9-]*:\S+")
# A key in a stored URL is a leak. A value already replaced by REDACTED is fine.
KEY_PARAM = re.compile(r"(?i)([?&](?:api[_-]?key|key)=)(?!REDACTED(?:[&#\s\"'\\]|$))[^&#\s\"'\\]+")
ERROR_STATUSES = {"error", "failed", "unavailable", "forbidden", "stale", "partial"}
QUOTA_STATUSES = {"limit", "rate_limited", "quota_exhausted"}


class LeaseLost(Exception):
    """Another owner holds the scan now. The current run stops without writing anything more."""


def redact(text):
    return KEY_PARAM.sub(r"\1REDACTED", str(text))


def leaks(value):
    return bool(KEY_PARAM.search(json.dumps(value, ensure_ascii=False, default=str)))


def health_of(status):
    """The source states the desk shows: ok, needs_key, access_blocked, quota_exhausted, error.

    access_blocked is a known, documented state (the platform offers no public access without a login or a research
    licence). It is neither an error nor an exhausted quota, so a scan that meets it is not `partial` because of it."""
    if status == "needs_key":
        return "needs_key"
    if status == "access_blocked":
        return "access_blocked"
    if status in QUOTA_STATUSES:
        return "quota_exhausted"
    if status in ERROR_STATUSES:
        return "error"
    return "ok"


def parse_time(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class Adapter:
    id: str
    discover: object
    label: str = ""
    modes: tuple = ("live",)
    legacy: bool = False            # result keeps its pre-v2 shape: no discovery[] required
    after: tuple = ()               # needs the captures of the first stage (ctx.captures)
    enabled: object = lambda: True
    daily_units_env: object = None  # environment variable holding the daily quota, if the source has one
    run_units_env: object = None    # environment variable holding the per-run cap
    daily_units_default: object = None  # quota when the variable is not set
    run_units_default: object = None
    own_network: bool = False       # uses its own transport; off when the caller injects a fetch (tests)
    explicit_only: bool = False     # runs only when a scan names it (payload adapters)
    quota_tz: str = "UTC"           # the day of the ledger ends at midnight in this zone


@dataclass
class AdapterContext:
    mode: str
    state: dict
    budget: object
    fetch: object
    clock: object
    previous: dict = field(default_factory=dict)       # creators already stored, by id
    known_ids: frozenset = frozenset()
    captures: list = field(default_factory=list)       # first-stage captures, for adapters with `after`
    options: dict = field(default_factory=dict)        # adapter specific overrides (tests, tools)
    beat: object = None

    def heartbeat(self):
        if self.beat:
            self.beat()


def quota_day(adapter, at):
    """Ledger day and the UTC instant at which the next day starts."""
    zone = ZoneInfo(getattr(adapter, "quota_tz", None) or "UTC")
    moment = (parse_time(at) or datetime.now(timezone.utc)).astimezone(zone)
    reset = (moment + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return moment.date().isoformat(), reset.astimezone(timezone.utc).isoformat()


def _env_int(name):
    try:
        return int(os.environ[name]) if name and os.environ.get(name) else None
    except ValueError:
        return None


def daily_limit(adapter):
    value = _env_int(getattr(adapter, "daily_units_env", None))
    return value if value is not None else getattr(adapter, "daily_units_default", None)


def run_limit(adapter):
    value = _env_int(getattr(adapter, "run_units_env", None))
    return value if value is not None else getattr(adapter, "run_units_default", None)


def _error(code, message, capture_id=None):
    out = {"code": code, "message": redact(message)[:300]}
    if capture_id is not None:
        out["id"] = redact(capture_id)[:120]
    return out


def _capture_problem(item, legacy):
    if not isinstance(item, dict):
        return "wpis nie jest obiektem"
    cid = item.get("id")
    if not isinstance(cid, str) or not cid:
        return "brak identyfikatora"
    if legacy:
        return "ścieżka odkrycia zawiera klucz API" if leaks(item.get("discovery")) else None
    if cid.startswith("youtube:"):
        if not YOUTUBE_ID.fullmatch(cid):
            return "identyfikator YouTube musi mieć postać youtube:<11 znaków>"
    elif not CANONICAL_ID.fullmatch(cid):
        return "identyfikator nie ma postaci platforma:id"
    if not isinstance(item.get("creatorId"), str) or not item["creatorId"]:
        return "brak creatorId"
    paths = item.get("discovery")
    if not isinstance(paths, list) or not paths:
        return "brak ścieżki odkrycia (discovery[])"
    if any(not isinstance(p, dict) or not isinstance(p.get("method"), str) or not p["method"] for p in paths):
        return "ścieżka odkrycia bez pola method"
    if leaks(item):
        return "wpis zawiera adres z kluczem API (key=)"
    return None


def result_status(result, sources):
    declared = result.get("status")
    if isinstance(declared, str) and declared:
        return declared
    states = [health_of(s.get("status")) for s in sources]
    blocked = [s for s in states if s == "access_blocked"]
    bad = [s for s in states if s not in ("ok", "access_blocked")]
    if not states or not bad:
        return "access_blocked" if blocked and len(blocked) == len(states) else "ok"
    return "error" if len(bad) == len(states) else "partial"


def validate_adapter_result(result, adapter=None, at=None):
    """Keep what is valid, report the rest. Never raises: a bad entry is a source error, not a failed scan."""
    errors = []
    legacy = bool(adapter and adapter.legacy)
    if not isinstance(result, dict):
        errors.append(_error("result_shape", "Adapter nie zwrócił słownika wyniku."))
        result = {}

    def listing(name):
        value = result.get(name)
        if value is None:
            return []
        if not isinstance(value, list):
            errors.append(_error("result_shape", f"Pole {name} musi być listą."))
            return []
        return value

    creators = []
    for item in listing("creators"):
        if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"]:
            creators.append(item)
        else:
            errors.append(_error("creator_invalid", "Twórca bez identyfikatora został odrzucony."))
    captures = []
    for item in listing("captures"):
        problem = _capture_problem(item, legacy)
        if problem:
            errors.append(_error("capture_invalid", f"Wpis odrzucony: {problem}.",
                                 item.get("id") if isinstance(item, dict) and isinstance(item.get("id"), str) else None))
        else:
            captures.append(item)
    sources = []
    for item in listing("sources"):
        if isinstance(item, dict) and (item.get("id") or item.get("name")):
            sources.append(item)
        else:
            errors.append(_error("source_invalid", "Źródło bez nazwy zostało odrzucone."))
    if errors and adapter is not None:
        note = redact(f"{len(errors)} wpisów odrzuconych przez walidator adaptera. {errors[0]['message']}")[:300]
        lasterror = {"code": "adapter_invalid", "message": note, "at": at,
                     "nextStep": "Popraw wynik adaptera. Pozostałe wpisy tego skanu zostały zachowane."}
        index = next((i for i, s in enumerate(sources) if s.get("id") == adapter.id), 0 if sources else None)
        if index is None:
            sources.append({"id": adapter.id, "name": adapter.label or adapter.id, "status": "partial",
                            "count": len(captures), "observedAt": at, "lastError": lasterror, "error": note})
        else:
            source = dict(sources[index])
            source.setdefault("lastError", lasterror)
            source.setdefault("error", note)
            if source.get("status") in (None, "ok", "empty"):
                source["status"] = "partial"
            sources[index] = source
    declared = isinstance(result.get("status"), str) and bool(result["status"])
    status = result_status(result, sources)
    if errors and (status in ("ok", "empty") or not declared):
        status = "partial" if captures or status in ("ok", "empty") else "error"
    out = {"creators": creators, "captures": captures, "sources": sources, "status": status,
           "resume": result.get("resume"), "retryAt": result.get("retryAt"), "quota": result.get("quota"),
           "errors": errors}
    for extra in ("etag", "cursor", "blocked"):
        if extra in result:
            out[extra] = result[extra]
    return out


def failure_result(adapter, exc, at):
    message = redact(f"{type(exc).__name__}: {exc}")[:300]
    return {"creators": [], "captures": [], "status": "error",
            "sources": [{"id": adapter.id, "name": adapter.label or adapter.id, "status": "error", "count": 0,
                         "observedAt": at, "error": message,
                         "lastError": {"code": "adapter_exception", "message": message, "at": at,
                                       "nextStep": "Sprawdź źródło i ponów skan. Pozostałe źródła zostały zapisane."}}]}


def blocked_result(adapter, state, at, retry_at, quota, reason):
    error = {"code": "quota_exhausted", "message": reason, "at": at,
             "nextStep": "Skan wznowi się od zapisanego kursora po resecie kwoty."}
    source = {"id": adapter.id, "name": adapter.label or adapter.id, "status": "limit", "count": 0,
              "observedAt": at, "retryAt": retry_at, "lastError": error, "error": reason}
    if quota:
        source["quota"] = quota
    return {"creators": [], "captures": [], "sources": [source], "status": "rate_limited", "retryAt": retry_at,
            "resume": state.get("resume"), "quota": quota, "blocked": True}


def with_quota(result, quota):
    """Sources show the ledger view {used, limit, resetAt}, not the adapter's own per-request list."""
    if not quota:
        return result
    view = {k: quota.get(k) for k in ("used", "limit", "resetAt")}
    if isinstance(quota.get("keys"), list):
        view["keys"] = quota["keys"]
    return {**result, "quota": view,
            "sources": [{**s, "quota": view} if "quota" in s else s for s in result["sources"]]}


def summary_of(result):
    return {"status": result["status"], "health": health_of(result["status"]), "captures": len(result["captures"]),
            "creators": len(result["creators"]), "sources": len(result["sources"]),
            "errors": len(result["errors"]), "retryAt": result.get("retryAt")}


class MemoryRunner:
    """No persistence. discover() without a runner behaves exactly like the former direct call."""

    def plan(self, steps):
        pass

    def resume(self, step):
        return None

    def started(self, step):
        pass

    def finished(self, step, status, summary, output):
        pass

    def mark(self, step, status, summary=None):
        pass

    def adapter_state(self, adapter_id):
        return {}

    def quota(self, adapter, at):
        return None

    def record(self, adapter, result, at):
        return result

    def heartbeat(self, force=False):
        pass


def execute(adapter, runner, base, extra=None):
    """Run one adapter as one resumable step and return its validated result."""
    step = "discover:" + adapter.id
    saved = runner.resume(step)
    if saved is not None:
        return saved
    runner.started(step)
    clock = base["clock"]
    at = clock()
    state = runner.adapter_state(adapter.id) or {}
    quota = runner.quota(adapter, at)
    failed = False
    raw = None
    retry_at = state.get("retryAt")
    if state.get("health") == "quota_exhausted" and retry_at and (parse_time(retry_at) or parse_time(at)) > parse_time(at):
        raw = blocked_result(adapter, state, at, retry_at, state.get("quota"),
                             "Źródło czeka na reset kwoty do " + retry_at + ".")
    elif quota and quota.get("remaining") is not None and quota["remaining"] <= 0:
        raw = blocked_result(adapter, state, at, quota.get("resetAt"), quota["snapshot"],
                             "Dzienna kwota źródła jest wyczerpana.")
    if raw is None:
        limits = [x for x in (run_limit(adapter), quota and quota.get("remaining")) if x is not None]
        fetch = base["fetch"]

        def beat_fetch(*args, **kwargs):
            runner.heartbeat()
            return fetch(*args, **kwargs)

        ctx = AdapterContext(mode=base["mode"], state=state, budget=min(limits) if limits else None,
                             fetch=beat_fetch, clock=clock, previous=base.get("previous", {}),
                             known_ids=base.get("known_ids", frozenset()), options=base.get("options", {}),
                             beat=runner.heartbeat, **(extra or {}))
        try:
            raw = adapter.discover(ctx)
        except LeaseLost:
            raise
        except Exception as exc:
            raw, failed = failure_result(adapter, exc, at), True
    result = validate_adapter_result(raw, adapter, at)
    result = runner.record(adapter, result, at)
    runner.finished(step, "failed" if failed else "done", summary_of(result), result)
    return result


def record_adapter_result(adapter_id, result, *, at=None, scan_id=None, adapter=None):
    """Persist cursor, last success, last error and quota of one adapter run (table source_state)."""
    from api import store
    with store.connection(True) as db:
        return store.record_adapter(db, adapter_id, validate_adapter_result(result, adapter, at or utc_now()),
                                    at or utc_now(), scan_id, adapter)


# --- one source row, several access paths (facebook-ads, instagram-ads, instagram, facebook) ---
# Several adapters report on the same platform: the Ad Library API (meta_ads, needs a token), the organic posts
# (facebook, instagram: access_blocked) and the analyst's saved pages (meta_import). The desk shows one row per
# source with `paths[]`; the row status is the best of the paths, and an inactive path (empty import) never hides a block.
PATH_OF = {"meta_import": "manual_import", "meta_ads": "ad_library_api", "facebook": "organic_posts",
           "instagram": "organic_posts", "social": "organic_posts", "social-replay": "organic_posts",
           "meta-import-replay": "manual_import"}
PATH_LABEL = {"manual_import": "import ręczny", "ad_library_api": "API reklam", "organic_posts": "wpisy automatycznie"}
PATH_SOURCES = frozenset({"facebook", "instagram", "facebook-ads", "instagram-ads"})
_RANK = {"ok": 0, "partial": 1, "stale": 1, "needs_key": 2, "access_blocked": 3}
_NEXT_STEP = {"manual_import": "Zapisz stronę Biblioteki Reklam lub osadzenie profilu i wgraj ją (POST /v1/import/meta).",
              "ad_library_api": "Token Ad Library API w pliku klucza (adapter meta_ads jest gotowy).",
              "organic_posts": "Meta Content Library albo osadzenie profilu zapisane ręcznie."}


def _rank(entry):
    return 9 if entry["status"] == "empty" else _RANK.get(entry["status"], 5 if health_of(entry["status"]) != "ok" else 4)


def _entry(path, row):
    last = row.get("lastError") if isinstance(row.get("lastError"), dict) else {}
    out = {"path": path, "status": row.get("status"), "detail": row.get("message") or last.get("message") or row.get("error"),
           "at": row.get("observedAt") or row.get("checkedAt"), "nextStep": row.get("nextStep") or last.get("nextStep") or _NEXT_STEP[path],
           "count": row.get("count"), "sampleDate": row.get("sampleDate"), "row": {k: v for k, v in row.items() if k != "paths"}}
    return out


def path_summary(name, paths, status, posts=False):
    """The sentence the desk puts under the source: the best path first, the others after a middle dot."""
    words = {"needs_key": "brak tokenu", "access_blocked": "blokada dostępu", "empty": "brak plików", "error": "błąd"}
    parts = []
    for entry in sorted(paths, key=_rank):
        label = PATH_LABEL[entry["path"]]
        if entry["status"] == "ok" and entry["path"] == "manual_import":
            day = entry.get("sampleDate")
            when = f", {int(day[8:10])} {('I II III IV V VI VII VIII IX X XI XII'.split())[int(day[5:7]) - 1]}" if day else ""
            text = f"próbka z importu ręcznego ({entry.get('count') or 0} {'postów' if posts else 'reklam'}{when})"
        elif entry["status"] == "ok":
            text = f"próbka ({entry.get('count') or 0})"
        else:
            text = words.get(entry["status"], str(entry["status"]))
        parts.append(text if not parts else f"{label}: {text}")
    return (name + ": " + " · ".join(parts)) if parts else None


def combine_paths(rows_by_path):
    """rows_by_path: {path: row} of one source id -> one row with `paths[]` and the best path's fields."""
    entries = [_entry(path, row) for path, row in rows_by_path.items()]
    return _row_of(entries)


def _row_of(entries):
    active = [e for e in entries if e["status"] != "empty"] or entries
    best = min(active, key=_rank)
    row = dict(best["row"])
    label = (row.get("name") or "").split(" · ")[0]
    ordered = sorted(entries, key=lambda e: (_rank(e), e["path"]))
    row["paths"] = [{**e} for e in ordered]
    row["pathsSummary"] = path_summary(label or row.get("id") or "", entries, best["status"], posts=row.get("id") in ("instagram", "facebook"))
    row["bestPath"] = best["path"]
    return row


def merge_source_rows(rows_with_adapter):
    """[(adapter id, source row)] -> source rows; rows of the PATH_SOURCES collapse to one row per id."""
    grouped, out = {}, []
    for adapter_id, row in rows_with_adapter:
        key = row.get("id") or row.get("name")
        path = PATH_OF.get(adapter_id)
        if key in PATH_SOURCES and path:
            if key not in grouped:
                grouped[key] = {}
                out.append(key)
            grouped[key][path] = row
        else:
            out.append(row)
    return [combine_paths(grouped[item]) if isinstance(item, str) else item for item in out]


def legacy_paths(row):
    """paths[] of a stored row written before paths existed: the row itself was one path (the only adapter that wrote
    it then). Rows of other sources have none."""
    key = row.get("id")
    if key not in PATH_SOURCES or isinstance(row.get("paths"), list):
        return row.get("paths") if isinstance(row.get("paths"), list) else []
    path = "manual_import" if row.get("importMethod") == "manual_import" else \
        "organic_posts" if key in ("facebook", "instagram") else "ad_library_api"
    return [{**_entry(path, row), "derived": "legacy"}]


def merge_stored_paths(old, new):
    """Fold a stored row of an earlier scan into the row of this scan: a path the new row does not report keeps its
    last entry; a path it reports replaces the old one. The stored `row` of every entry rebuilds the aggregate."""
    if not isinstance(new.get("paths"), list):
        return new
    entries = {e["path"]: e for e in legacy_paths(old) if isinstance(e, dict) and e.get("row")}
    entries.update({e["path"]: e for e in new["paths"]})
    return {**_row_of(list(entries.values())), **{k: new[k] for k in ("mode", "checkedAt") if k in new}}
