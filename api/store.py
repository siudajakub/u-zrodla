"""Durable case data. Each transaction gets its own SQLite connection."""
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import lru_cache
from hashlib import sha256
import json
import os
from pathlib import Path
import random
import re
import sqlite3
import time
import unicodedata
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from collectors.adapter import LeaseLost, daily_limit, health_of, legacy_paths, merge_stored_paths, quota_day, redact

ROOT = Path(__file__).resolve().parents[1]
STATE = Path(os.environ.get("INVESTWATCH_STATE", ROOT / ".runtime/demo")).resolve()
SCHEMA = """
CREATE TABLE IF NOT EXISTS scans (
 id TEXT PRIMARY KEY, request_id TEXT UNIQUE NOT NULL, mode TEXT NOT NULL, status TEXT NOT NULL,
 created TEXT NOT NULL, updated TEXT NOT NULL, payload TEXT NOT NULL, result TEXT NOT NULL,
 lease_until REAL NOT NULL DEFAULT 0, owner TEXT, attempts INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS audio_cache (fingerprint TEXT PRIMARY KEY, result TEXT, retry_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS creators (id TEXT PRIMARY KEY, body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sources (id TEXT PRIMARY KEY, body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS cases (
 id TEXT PRIMARY KEY, body TEXT NOT NULL, fingerprint TEXT NOT NULL,
 status TEXT NOT NULL, revision INTEGER NOT NULL, updated TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS versions (
 id TEXT NOT NULL, version INTEGER NOT NULL, signature TEXT NOT NULL, observed TEXT NOT NULL,
 capture TEXT NOT NULL, finding TEXT NOT NULL, PRIMARY KEY(id,version)
);
CREATE TABLE IF NOT EXISTS history (
 seq INTEGER PRIMARY KEY, case_id TEXT NOT NULL, at TEXT NOT NULL, action TEXT NOT NULL,
 note TEXT NOT NULL, details TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
 seq INTEGER PRIMARY KEY, at TEXT NOT NULL, kind TEXT NOT NULL, ref TEXT NOT NULL, message TEXT NOT NULL
);
"""

TOKEN_PATH = re.compile(r"(?:~|/home/[^/\s\"]+)/\.config/investwatch/[\w.-]+")
HOME_PREFIX = re.compile(r"/home/[^/\s\"]+/")

def scrub(value):
    """No local file paths in an API answer: a token file is named "plik tokenu poza repozytorium", a path inside the
    repository is shown relative to it, any other home directory is cut."""
    if isinstance(value, str):
        value = TOKEN_PATH.sub("plik tokenu poza repozytorium", value).replace(str(ROOT) + "/", "")
        return HOME_PREFIX.sub("", value)
    if isinstance(value, dict):
        return {k: scrub(v) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub(v) for v in value]
    return value

def utc():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")

def dump(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

@contextmanager
def connection(write=False):
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    db = sqlite3.connect(STATE / "cases.sqlite3", timeout=20)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()

# Schema generations. Each step is additive and idempotent. Never ALTER the v1 tables
# (cases, versions, creators, sources): the v1 code inserts into them positionally
# ("INSERT INTO cases VALUES(...)"), so an extra column would break a rollback to 491094d.
# Per-case or per-version metadata goes into side tables created by later steps.
def _migration_2(db):
    db.execute("CREATE TABLE IF NOT EXISTS schema_meta("
               " version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL, note TEXT NOT NULL)")

def _migration_3(db):
    # Side tables only: the v1 tables keep their exact shape (see the note above).
    db.execute("CREATE TABLE IF NOT EXISTS version_meta("
               " id TEXT NOT NULL, version INTEGER NOT NULL, reason TEXT NOT NULL, content_sig TEXT NOT NULL,"
               " evidence_sig TEXT NOT NULL, analysis_sig TEXT NOT NULL, details TEXT NOT NULL,"
               " PRIMARY KEY(id,version))")
    db.execute("CREATE TABLE IF NOT EXISTS discoveries("
               " case_id TEXT NOT NULL, key TEXT NOT NULL, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,"
               " seen_count INTEGER NOT NULL, body TEXT NOT NULL, PRIMARY KEY(case_id,key))")
    db.execute("CREATE TABLE IF NOT EXISTS reach_samples("
               " case_id TEXT NOT NULL, observed TEXT NOT NULL, source TEXT NOT NULL, body TEXT NOT NULL,"
               " PRIMARY KEY(case_id,observed,source))")

def _migration_4(db):
    # Scan steps (resume), per-source state (cursor, last success, last error) and the quota ledger.
    db.execute("CREATE TABLE IF NOT EXISTS scan_steps("
               " scan_id TEXT NOT NULL, step TEXT NOT NULL, seq INTEGER NOT NULL, status TEXT NOT NULL,"
               " attempts INTEGER NOT NULL DEFAULT 0, started TEXT, finished TEXT,"
               " summary TEXT NOT NULL DEFAULT '{}', output TEXT, PRIMARY KEY(scan_id,step))")
    db.execute("CREATE TABLE IF NOT EXISTS source_state("
               " source_id TEXT PRIMARY KEY, body TEXT NOT NULL, updated TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS quota_ledger("
               " source_id TEXT NOT NULL, day TEXT NOT NULL, used INTEGER NOT NULL, units_limit INTEGER,"
               " reset_at TEXT, updated TEXT NOT NULL, PRIMARY KEY(source_id,day))")

def _migration_5(db):
    # Shadow qualification (S5): the D result of one case version, beside the v1 tables.
    db.execute("CREATE TABLE IF NOT EXISTS qualification_results("
               " case_id TEXT NOT NULL, version INTEGER NOT NULL, body TEXT NOT NULL, updated TEXT NOT NULL,"
               " PRIMARY KEY(case_id,version))")

def _migration_6(db):
    # Threshold per variant and the qualification switch, both append-only (S7).
    db.execute("CREATE TABLE IF NOT EXISTS thresholds("
               " id INTEGER PRIMARY KEY AUTOINCREMENT, variant TEXT NOT NULL, value INTEGER NOT NULL,"
               " note TEXT NOT NULL DEFAULT '', restored_from INTEGER, at TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS qualification_settings("
               " id INTEGER PRIMARY KEY AUTOINCREMENT, variant TEXT NOT NULL, previous_id INTEGER, restored_from INTEGER,"
               " note TEXT NOT NULL DEFAULT '', validation_ref TEXT, approved_by TEXT, at TEXT NOT NULL,"
               " rules_version TEXT, model_id TEXT, model_digest TEXT, prompt_version TEXT)")
    if not db.execute("SELECT 1 FROM thresholds").fetchone():
        for variant in ("rules_1_2", "qual_d", "qual_d_model"):
            db.execute("INSERT INTO thresholds(variant,value,note,at) VALUES(?,60,'Wpis domyślny',?)", (variant, utc()))
    if not db.execute("SELECT 1 FROM qualification_settings").fetchone():
        if db.execute("SELECT 1 FROM cases LIMIT 1").fetchone():
            # An existing database never switches variant by itself: it keeps the rules that produced its cases.
            db.execute("INSERT INTO qualification_settings(variant,note,at) VALUES('rules_1_2','Wariant domyślny',?)", (utc(),))
        else:
            # A new, empty database starts on the approved default (M1 measurement of 21 XI 2026, threshold 60).
            rules = "investwatch-qual-d"
            try:
                from analysis import qualification
                rules = qualification.RULES_VERSION
            except Exception:
                pass
            db.execute("INSERT INTO qualification_settings(variant,note,validation_ref,approved_by,at,rules_version) VALUES(?,?,?,?,?,?)",
                       (DEFAULT_VARIANT, DEFAULT_NOTE, DEFAULT_VALIDATION_REF, DEFAULT_APPROVED_BY, utc(), rules))

def _migration_7(db):
    # Media backlog of the speech gate: what was fetched for a video (transcript, frames) and what is still to do.
    db.execute("CREATE TABLE IF NOT EXISTS media_state("
               " case_id TEXT PRIMARY KEY, state TEXT NOT NULL, body TEXT NOT NULL, updated TEXT NOT NULL)")

def _migration_8(db):
    # Quota per key (additive): one row per (source, day, key) next to the source's own quota_ledger row.
    # The row holds the 8-character key id (a hash prefix computed by the adapter), never the key itself.
    db.execute("CREATE TABLE IF NOT EXISTS quota_keys("
               " source_id TEXT NOT NULL, day TEXT NOT NULL, key_id TEXT NOT NULL, used INTEGER NOT NULL,"
               " units_limit INTEGER, exhausted_at TEXT, updated TEXT NOT NULL, PRIMARY KEY(source_id,day,key_id))")

MIGRATIONS = ((2, "schema_meta i numeracja wersji schematu", _migration_2),
              (3, "version_meta, discoveries, reach_samples", _migration_3),
              (4, "scan_steps, source_state, quota_ledger", _migration_4),
              (5, "qualification_results (kwalifikacja D w cieniu)", _migration_5),
              (6, "thresholds, qualification_settings", _migration_6),
              (7, "media_state (zaległość mediów bramki mowy)", _migration_7),
              (8, "quota_keys (księga kwoty per klucz)", _migration_8))
SCHEMA_VERSION = MIGRATIONS[-1][0]

def migrate(db):
    """Apply missing steps under one write lock. A second process waits, then finds nothing to do."""
    db.execute("BEGIN IMMEDIATE")
    try:
        current = db.execute("PRAGMA user_version").fetchone()[0]
        for version, note, step in MIGRATIONS:
            if current >= version:
                continue
            step(db)
            db.execute("INSERT OR REPLACE INTO schema_meta VALUES(?,?,?)", (version, utc(), note))
            db.execute(f"PRAGMA user_version={int(version)}")
            current = version
        db.execute("COMMIT")
    except BaseException:
        if db.in_transaction:
            db.execute("ROLLBACK")
        raise
    return current

def _prepare():
    db = sqlite3.connect(STATE / "cases.sqlite3", timeout=20, isolation_level=None)
    try:
        # Switching the journal mode and the first CREATE TABLE ignore the busy timeout when
        # another process does the same, so the caller retries on "database is locked".
        if db.execute("PRAGMA journal_mode").fetchone()[0] != "wal":
            db.execute("PRAGMA journal_mode=WAL")
        db.executescript(SCHEMA)
        migrate(db)
    finally:
        db.close()

def init(wait=30):
    """Prepare the database. API and worker start together, so concurrent callers must not fail."""
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    deadline = time.monotonic() + wait
    while True:
        try:
            return _prepare()
        except sqlite3.OperationalError as error:
            if "locked" not in str(error) and "busy" not in str(error) or time.monotonic() > deadline:
                raise
            time.sleep(random.uniform(.02, .15))

def schema_info(db):
    version = db.execute("PRAGMA user_version").fetchone()[0]
    try:
        row = db.execute("SELECT applied_at FROM schema_meta WHERE version=?", (version,)).fetchone()
    except sqlite3.OperationalError:
        row = None
    return {"version": version, "migratedAt": row[0] if row else None}

# Analysis generation that new code writes. A record without analysisVersion predates it.
ANALYSIS_SCHEMA = 2
ANALYSIS_VARIANT = "rules_1_2"
# Default of a new, empty database (orchestrator decision of 21 XI 2026); the way back to rules_1_2 stays open.
DEFAULT_VARIANT = "qual_d"
DEFAULT_VALIDATION_REF = "fixtures/validation/q-v2/WYNIK-M1-2026-11-21.md@463cceb"
DEFAULT_APPROVED_BY = "Fable (orkiestrator)"
DEFAULT_NOTE = ("Domyślny wariant produktu, próg 60. Pomiar na 17 filmach: koszt 2×FN+FP 15 → 0 względem rules_1_2. "
                "To oceny agentów, nie walidacja ekspercka.")
# Fallback when the engine cannot be imported; the engine's module_rules() is the source of truth.
M2_RULES = "investwatch-m2-rendered-1"

@lru_cache(maxsize=1)
def _engine_versions():
    rules = model = None
    try:
        from analysis.engine import RULESET
        rules = RULESET
    except Exception:
        pass
    try:
        from analysis import semantic
        model = semantic.VERSION
    except Exception:
        pass
    return rules, model

def analysis_current():
    rules, model = _engine_versions()
    try:
        from analysis.engine import module_rules
        by_module = module_rules()
    except Exception:
        by_module = {"M1": rules, "M2": (M2_RULES,), "M3": rules}
    return {"rules": rules, "model": model, "schema": ANALYSIS_SCHEMA, "variant": ANALYSIS_VARIANT,
            "rulesByModule": by_module}

PLATFORM_ALIAS = {"www": "web", "studio": "web"}

def canonical_platform(value):
    """One spelling of the platform: sites are `web` (older records and fixtures say `WWW`, the demo studio `Studio`).
    A suffix after `:` (tiktok:handle) is kept."""
    text = str(value or "")
    head, sep, tail = text.partition(":")
    head = PLATFORM_ALIAS.get(head.lower(), head)
    return head + sep + tail if text else text

def derive_origin(item):
    """One origin per record: live, replay, synthetic or upload."""
    provenance = item.get("provenance") if isinstance(item.get("provenance"), dict) else {}
    if item.get("synthetic") or item.get("contractDemo"):
        return "synthetic"
    mode = item.get("mode") or provenance.get("mode")
    if item.get("platform") == "upload" or mode == "upload":
        return "upload"
    # Every stored case carries a mode; the fallback only keeps the value inside the enum.
    return mode if mode in ("live", "replay") else "replay"

def compat_view(body, current):
    """Fields v2 readers expect, derived for records written before they existed."""
    module = body.get("module", "M1")
    declared = body.get("analysisVersion") if isinstance(body.get("analysisVersion"), dict) else None
    schema = declared.get("schema", 1) if declared else (current["schema"] if "reviewDecision" in body else 1)
    rules = (declared or {}).get("rules") or body.get("rulesVersion")
    accepted = current["rulesByModule"].get(module) or current["rules"]
    accepted = (accepted,) if isinstance(accepted, str) else tuple(accepted or ())
    wanted = accepted[0] if accepted else None
    stale_schema = schema < current["schema"]
    stale_rules = bool(rules and accepted and rules not in accepted)
    needs = stale_schema or stale_rules
    parts = []
    if stale_rules:
        parts.append(f"Wynik z reguł {rules}; bieżące {wanted}")
    if stale_schema:
        parts.append(f"Analiza w schemacie {schema}; bieżący {current['schema']}")
    view = {
        "origin": body.get("origin") or derive_origin(body),
        "analysisVersion": declared or {"rules": rules, "model": (body.get("semantic") or {}).get("version"),
                                         "schema": schema, "variant": ANALYSIS_VARIANT},
        "needsRecalc": needs,
        "needsRecalcReason": "; ".join(parts) if needs else None,
        "requalification": {"state": "pending" if needs else "current",
                            "reasonCode": ("schema_%d" % schema) if stale_schema else ("rules_changed" if stale_rules else None),
                            "fromRules": rules, "toRules": wanted,
                            "fromVariant": (declared or {}).get("variant", ANALYSIS_VARIANT)},
    }
    if not declared:
        view["derived"] = "legacy"
    return view

def event(db, kind, ref, message):
    db.execute("INSERT INTO events(at,kind,ref,message) VALUES(?,?,?,?)", (utc(),kind,ref,message))

def record(db, case_id, action, note, details):
    db.execute("INSERT INTO history(case_id,at,action,note,details) VALUES(?,?,?,?,?)",
               (case_id,utc(),action,note,dump(details)))

def history(db, case_id):
    out = []
    for row in db.execute("SELECT at,action,note,details FROM history WHERE case_id=? ORDER BY seq", (case_id,)):
        out.append({**dict(row), **json.loads(row["details"])})
    return out

def details_object(entry):
    """History entry of schema 2: `details` is an object (the stored JSON, parsed); the flat fields stay beside it."""
    raw = entry.get("details")
    if isinstance(raw, dict):
        return entry
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else {}
    except ValueError:
        parsed = {}
    return {**entry, "details": parsed if isinstance(parsed, dict) else {"value": parsed}}

def scan_dict(row):
    return {"id":row["id"],"scanId":row["id"],"mode":row["mode"],"status":row["status"],
            "createdAt":row["created"],"updatedAt":row["updated"],"attempts":row["attempts"],
            **json.loads(row["result"])}

def create_scan(mode, request_id, payload=None, retry_failed=False):
    with connection(True) as db:
        row=db.execute("SELECT * FROM scans WHERE request_id=?", (request_id,)).fetchone()
        if row:
            if row["mode"] != mode:
                raise ValueError("Ten identyfikator żądania ma inny tryb.")
            if retry_failed and row["status"]=="failed":
                db.execute("UPDATE scans SET status='queued',owner=NULL,lease_until=0,updated=?,result='{}' WHERE id=?",
                           (utc(),row["id"]))
                event(db,"scan",row["id"],"Ponowiono nieudane zadanie")
                return scan_dict(db.execute("SELECT * FROM scans WHERE id=?",(row["id"],)).fetchone()), True
            return scan_dict(row), False
        key=uuid4().hex
        now=utc()
        db.execute("INSERT INTO scans(id,request_id,mode,status,created,updated,payload,result) VALUES(?,?,?,'queued',?,?,?,?)",
                   (key,request_id,mode,now,now,dump(payload or {}),"{}"))
        event(db,"scan",key,"Dodano skan do kolejki")
        return scan_dict(db.execute("SELECT * FROM scans WHERE id=?", (key,)).fetchone()),True

# --- scan steps, source state, quota ledger, lease heartbeat (contract v2, step S3) ---
def heartbeat(db, scan_id, owner, lease_seconds):
    """Extend the lease. Raises LeaseLost when the scan is no longer ours."""
    changed = db.execute("UPDATE scans SET lease_until=? WHERE id=? AND owner=? AND status='running'",
                         (time.time() + lease_seconds, scan_id, owner)).rowcount
    if not changed:
        raise LeaseLost(scan_id)

def plan_steps(db, scan_id, steps):
    """Register steps in order. Steps that already exist (a resumed scan) keep their state."""
    seq = db.execute("SELECT coalesce(max(seq),0) FROM scan_steps WHERE scan_id=?", (scan_id,)).fetchone()[0]
    for step in steps:
        if not db.execute("SELECT 1 FROM scan_steps WHERE scan_id=? AND step=?", (scan_id, step)).fetchone():
            seq += 1
            db.execute("INSERT INTO scan_steps(scan_id,step,seq,status) VALUES(?,?,?,'pending')", (scan_id, step, seq))

def step_start(db, scan_id, step):
    plan_steps(db, scan_id, [step])
    db.execute("UPDATE scan_steps SET status='running',attempts=attempts+1,started=?,finished=NULL WHERE scan_id=? AND step=?",
               (utc(), scan_id, step))

def step_finish(db, scan_id, step, status, summary=None, output=None):
    plan_steps(db, scan_id, [step])
    db.execute("UPDATE scan_steps SET status=?,finished=?,summary=?,output=? WHERE scan_id=? AND step=?",
               (status, utc(), dump(summary or {}), None if output is None else json.dumps(output, ensure_ascii=False, default=str),
                scan_id, step))

def step_output(db, scan_id, step):
    row = db.execute("SELECT status,output FROM scan_steps WHERE scan_id=? AND step=?", (scan_id, step)).fetchone()
    return json.loads(row["output"]) if row and row["status"] == "done" and row["output"] is not None else None

def clear_step_outputs(db, scan_id):
    db.execute("UPDATE scan_steps SET output=NULL WHERE scan_id=?", (scan_id,))

STEP_NAMES = {"enrich": "Transkrypcje i kadry", "analyze": "Analiza i kwalifikacja", "apply": "Zapis wyników",
              "transcribe": "Transkrypcja nagrania"}

def step_name(step):
    if step in STEP_NAMES:
        return STEP_NAMES[step]
    if step.startswith("discover:"):
        try:
            from collectors.discovery import ADAPTERS
            label = ADAPTERS[step[9:]].label
        except Exception:
            label = ""
        return "Odkrywanie: " + (label or step[9:])
    return step

def scan_steps(db, scan_id):
    return [{"id": r["step"], "name": step_name(r["step"]), "step": r["step"], "status": r["status"],
             "attempts": r["attempts"], "startedAt": r["started"],
             "finishedAt": r["finished"], "summary": json.loads(r["summary"])}
            for r in db.execute("SELECT * FROM scan_steps WHERE scan_id=? ORDER BY seq", (scan_id,))]

def ledger_row(db, source_id, day):
    return db.execute("SELECT * FROM quota_ledger WHERE source_id=? AND day=?", (source_id, day)).fetchone()

# Sources that stay visible as "no token" (needs_key, with the next step) but never make a scan partial or the source health
# degraded: the Meta Ad Library is optional, so a missing token is a known state of the installation, not a failure.
TOKEN_OPTIONAL = {"meta_ads", "facebook-ads", "instagram-ads", "m3-offers"}

KEY_ID = re.compile(r"[0-9a-f]{8}")

def ledger_keys(db, source_id, day):
    return [dict(r) for r in db.execute("SELECT * FROM quota_keys WHERE source_id=? AND day=? ORDER BY key_id", (source_id, day))]

def _key_limit(adapter, reported):
    """Per-key daily limit: what the adapter reports for the key, capped by the configured daily units (the reserve)."""
    configured = daily_limit(adapter)
    values = [v for v in (configured, reported) if isinstance(v, int) and v >= 0]
    return min(values) if values else None

def known_key_count(db, source_id, day):
    """Keys the source used on the most recent earlier day: the guess for a day that has no key row yet."""
    row = db.execute("SELECT count(*) FROM quota_keys WHERE source_id=? AND day=(SELECT max(day) FROM quota_keys WHERE source_id=? AND day<?)",
                     (source_id, source_id, day)).fetchone()
    return max(1, row[0] if row else 1)

def key_views(rows):
    return [{"keyId": r["key_id"], "used": r["used"], "limit": r["units_limit"], "exhaustedAt": r["exhausted_at"]} for r in rows]

def quota_view(adapter, row, at, keys=None, key_hint=1):
    """Remaining units today for an adapter, plus the snapshot shown on the source.

    With key rows the daily limit of the source is the sum of its keys' limits and the remaining units are the sum of what
    each key still has: one key refused by the platform does not block another."""
    day, reset = quota_day(adapter, at)
    limit = daily_limit(adapter)
    used = row["used"] if row else 0
    if limit is None and row:
        limit = row["units_limit"]
    if keys:
        spent = sum(k["used"] for k in keys)
        total = sum(k["units_limit"] for k in keys if k["units_limit"] is not None) if all(k["units_limit"] is not None for k in keys) else None
        left = None if total is None else sum(max(0, k["units_limit"] - k["used"]) for k in keys)
        return {"remaining": left, "resetAt": reset,
                "snapshot": {"used": spent, "limit": total, "resetAt": reset, "day": day, "keys": key_views(keys)}}
    configured = daily_limit(adapter)
    if configured is not None and key_hint > 1:
        limit = configured * key_hint
    snapshot = {"used": used, "limit": limit, "resetAt": reset, "day": day}
    return {"remaining": None if configured is None else max(0, (limit if key_hint > 1 else configured) - used),
            "resetAt": reset, "snapshot": snapshot}

def source_state(db, source_id):
    row = db.execute("SELECT body FROM source_state WHERE source_id=?", (source_id,)).fetchone()
    return json.loads(row[0]) if row else {}

def source_states(db):
    return [json.loads(r[0]) for r in db.execute("SELECT body FROM source_state ORDER BY source_id")]

def _last_error(result, at):
    for source in result.get("sources", []):
        if isinstance(source.get("lastError"), dict):
            return {"code": None, "message": "", "nextStep": None, **source["lastError"], "at": source["lastError"].get("at") or at}
    for source in result.get("sources", []):
        if source.get("error") and health_of(source.get("status")) != "ok":
            return {"code": source.get("status"), "message": redact(source["error"])[:300], "at": at, "nextStep": "Ponów skan."}
    return {"code": result.get("status"), "message": "Źródło zwróciło błąd bez opisu.", "at": at, "nextStep": "Ponów skan."}

def record_adapter(db, adapter_id, result, at, scan_id=None, adapter=None):
    """Persist one adapter run: cursor, last success, last error, retry and quota. Returns the stored state."""
    old = source_state(db, adapter_id)
    status = result.get("status") or "ok"
    health = "quota_exhausted" if result.get("blocked") else health_of(status)
    body = {**old, "sourceId": adapter_id, "updatedAt": at, "lastAttemptAt": at, "lastScanId": scan_id, "status": status,
            "health": health}
    if result.get("blocked"):
        body["retryAt"] = result.get("retryAt") or old.get("retryAt")
    else:
        body["retryAt"] = result.get("retryAt")
        body["resume"] = result.get("resume") or (old.get("resume") if health != "ok" else None)
        for key in ("etag", "cursor"):
            if key in result:
                body[key] = result[key]
        if health == "ok":
            body.update(lastSuccessAt=at, consecutiveErrors=0)
        else:
            body["consecutiveErrors"] = int(old.get("consecutiveErrors") or 0) + 1
            body["lastError"] = _last_error(result, at)
    quota = result.get("quota") if isinstance(result.get("quota"), dict) else None
    if quota is not None or (adapter is not None and daily_limit(adapter) is not None):
        day, reset = quota_day(adapter, at)
        reported = [k for k in ((quota or {}).get("keys") or []) if isinstance(k, dict) and KEY_ID.fullmatch(str(k.get("keyId") or ""))]
        row = ledger_row(db, adapter_id, day)
        if reported and not result.get("blocked"):
            for k in reported:
                before = db.execute("SELECT used,exhausted_at FROM quota_keys WHERE source_id=? AND day=? AND key_id=?",
                                    (adapter_id, day, k["keyId"])).fetchone()
                key_limit = _key_limit(adapter, k.get("limit"))
                used = max((before["used"] if before else 0) + int(k.get("usedThisRun") or 0), int(k.get("used") or 0))
                exhausted = k.get("exhaustedAt") or (before["exhausted_at"] if before else None)
                if k.get("exhaustedAt") and key_limit:
                    used = max(used, int(key_limit))  # this key was refused by the platform: its day is spent
                db.execute("INSERT OR REPLACE INTO quota_keys VALUES(?,?,?,?,?,?,?)",
                           (adapter_id, day, k["keyId"], used, key_limit, exhausted, at))
        keys = ledger_keys(db, adapter_id, day)
        if keys and all(k["units_limit"] is not None for k in keys):
            used, limit = sum(k["used"] for k in keys), sum(k["units_limit"] for k in keys)
        else:
            limit = daily_limit(adapter) if adapter is not None and daily_limit(adapter) is not None else (quota or {}).get("limit")
            used = (row["used"] if row else 0) + (0 if result.get("blocked") else int((quota or {}).get("used") or 0))
            code = (_last_error(result, at).get("code") if health == "quota_exhausted" and not result.get("blocked") else None)
            if code not in (None, "budget") and limit and not reported:
                used = max(used, int(limit))  # the platform refused: the day is spent whatever we counted
        db.execute("INSERT OR REPLACE INTO quota_ledger VALUES(?,?,?,?,?,?)",
                   (adapter_id, day, used, limit, (quota or {}).get("resetAt") or reset, at))
        body["quota"] = {"used": used, "limit": limit, "resetAt": (quota or {}).get("resetAt") or reset, "day": day}
        if keys:
            body["quota"]["keys"] = key_views(keys)
    db.execute("INSERT OR REPLACE INTO source_state VALUES(?,?,?)", (adapter_id, dump(body), at))
    return body

META_ADS_ROW = {"id": "meta_ads", "name": "Meta · Biblioteka Reklam (FB i IG)", "url": "https://www.facebook.com/ads/library/",
                "status": "needs_key", "count": 0, "kind": "feed", "observedAt": None, "derived": "not_run",
                "message": "Brak tokenu Biblioteki Reklam: źródło nie wysłało żadnego żądania.",
                "nextStep": "Token Ad Library API w pliku klucza (adapter meta_ads jest gotowy) albo import ręczny (POST /v1/import/meta)."}

def configured_youtube_keys():
    """Key ids (8 characters of the SHA-256) of the configured YouTube keys: the list the ledger shows before any use."""
    try:
        from collectors import youtube
        return [youtube.key_id(k) for k in youtube.load_keys()]
    except Exception:
        return []

def public_source(source):
    """A stored source row without the per-path snapshots that only rebuild the aggregate (paths[].row)."""
    paths=legacy_paths(source)
    if paths:
        out={**source,"paths":[{k:v for k,v in p.items() if k!="row"} for p in paths if isinstance(p,dict)]}
        return out if isinstance(source.get("paths"),list) else {**out,"bestPath":paths[0]["path"]}
    return source

def all_objects(db, table):
    assert table in {"creators","sources"}
    return [json.loads(r[0]) for r in db.execute(f"SELECT body FROM {table} ORDER BY id")]

# --- normalization, completeness, version reasons, observation layer (contract v2, step S2) ---
YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com"}
VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}")
CONTENT_KEYS = ("title","url","description","segments","mediaUrl","publishedAt","module","brand","platform",
                "creatorId","sha256","contractDemo")
EVIDENCE_KEYS = ("segments","mediaUrl","sha256")
COMPLETENESS_RANK = {"partial": 1, "full": 2}

def parse_time(value):
    """Aware UTC datetime or None. Naive values are not guessed."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else None

def norm_time(value):
    """Stored form: UTC. A value already written as +00:00 is kept byte for byte."""
    parsed = parse_time(value)
    if parsed is None:
        return value
    if value.strip().endswith("+00:00"):
        return value.strip()
    return parsed.isoformat(timespec="microseconds" if parsed.microsecond else "seconds")

def canonical_instant(value):
    """Same instant, same string, whatever the notation. Used only for comparing content."""
    parsed = parse_time(value)
    return parsed.isoformat(timespec="microseconds") if parsed else value

def norm_url(value):
    """Canonical YouTube links; every other URL is kept as received."""
    if not isinstance(value, str):
        return value
    try:
        parts = urlsplit(value.strip())
    except ValueError:
        return value
    host = (parts.hostname or "").lower()
    video = None
    if host in YOUTUBE_HOSTS and parts.path == "/watch":
        video = (parse_qs(parts.query).get("v") or [""])[0]
    elif host == "youtu.be":
        video = parts.path.strip("/")
    if video and VIDEO_ID.fullmatch(video):
        return f"https://www.youtube.com/watch?v={video}"
    if host in YOUTUBE_HOSTS and parts.path.startswith("/shorts/") and VIDEO_ID.fullmatch(parts.path[8:].strip("/")):
        return f"https://www.youtube.com/shorts/{parts.path[8:].strip('/')}"
    return value

def norm_text(value):
    if not isinstance(value, str):
        return value
    return unicodedata.normalize("NFC", value).replace("\r\n", "\n").replace("\r", "\n")

def normalize_capture(capture):
    """Stored form: times in UTC and canonical YouTube links. Text stays as received."""
    item = dict(capture)
    for field in ("publishedAt", "observedAt"):
        if field in item:
            item[field] = norm_time(item[field])
    if "url" in item:
        item["url"] = norm_url(item["url"])
    if isinstance(item.get("discovery"), list):
        item["discovery"] = [{**d, "observedAt": norm_time(d.get("observedAt"))} if isinstance(d, dict) else d
                             for d in item["discovery"]]
    return item

def _hash_view(capture, key):
    """Value of a content field as compared for versioning (text normalized)."""
    value = capture.get(key)
    if key in ("title", "description"):
        return norm_text(value)
    if key == "publishedAt":
        return canonical_instant(value)
    if key == "url":
        return norm_url(value)
    if key == "segments" and isinstance(value, list):
        return [{**x, "text": norm_text(x.get("text"))} if isinstance(x, dict) else x for x in value]
    return value

def completeness(capture):
    explicit = capture.get("contentCompleteness")
    if explicit in COMPLETENESS_RANK:
        return explicit
    provenance = capture.get("provenance") if isinstance(capture.get("provenance"), dict) else {}
    return "partial" if provenance.get("truncated") or provenance.get("sampled") or capture.get("sampled") else "full"

def signature_parts(capture, finding, raw=None):
    """Fingerprint and its components. `raw` is the capture as received: its v1-style fingerprint
    ("legacy") lets a case stored before S2 recognise an unchanged reading."""
    proof_revision = capture.get("m2EvidenceRevision")
    content_keys = CONTENT_KEYS + (("m2EvidenceRevision",) if proof_revision else ())
    checks = finding.get("checks")
    if proof_revision:
        checks = [
            {**check, "measurements": [
                {k: v for k, v in measurement.items() if k != "capturedAt"}
                for measurement in check["measurements"]
            ]} if "measurements" in check else check
            for check in checks or []
        ]
    partial = capture.get("contentCompleteness") == "partial"
    analysis = [finding.get("summary"), finding.get("score"), checks, finding.get("evidence"), finding.get("semantic"),
                finding.get("modalityComparison"), finding.get("reviewSuggestion")]
    payload = [[_hash_view(capture, k) for k in content_keys], *analysis]
    if partial:
        payload.append("partial")
    plain = [k for k in content_keys if k not in EVIDENCE_KEYS]
    legacy = None
    if raw is not None and not partial:
        legacy = sha256(dump([[raw.get(k) for k in content_keys], *analysis]).encode()).hexdigest()
    return {
        "signature": sha256(dump(payload).encode()).hexdigest(),
        "legacy": legacy,
        "content": sha256(dump([[_hash_view(capture, k) for k in plain], partial]).encode()).hexdigest(),
        "evidence": sha256(dump([_hash_view(capture, k) for k in EVIDENCE_KEYS]).encode()).hexdigest(),
        "analysis": sha256(dump([*analysis, finding.get("rulesVersion")]).encode()).hexdigest(),
    }

def version_reason(before, after, old_finding, new_finding):
    """Highest level that changed: content, then evidence, then analysis."""
    if before is None:
        return "content", {"initial": True}
    changed = [name for name in ("content", "evidence", "analysis") if before[name] != after[name]]
    reason = changed[0] if changed else "analysis"
    return reason, {"changed": changed, "rulesFrom": old_finding.get("rulesVersion"),
                    "rulesTo": new_finding.get("rulesVersion"), "scoreFrom": old_finding.get("score"),
                    "scoreTo": new_finding.get("score")}

def discovery_key(entry):
    return sha256(f"{entry.get('method')}|{entry.get('query') or ''}|{entry.get('sourceId') or ''}".encode()).hexdigest()[:16]

def observe_discovery(db, key, entries, scan_id):
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict) or not entry.get("method"):
            continue
        entry = {**entry, "observedAt": norm_time(entry.get("observedAt")) or utc()}
        if scan_id:
            entry["scanId"] = scan_id
        seen = entry["observedAt"]
        slot = discovery_key(entry)
        row = db.execute("SELECT * FROM discoveries WHERE case_id=? AND key=?", (key, slot)).fetchone()
        if row is None:
            db.execute("INSERT INTO discoveries VALUES(?,?,?,?,1,?)", (key, slot, seen, seen, dump(entry)))
            continue
        newest = max((row["last_seen"], seen), key=lambda v: parse_time(v) or datetime.min.replace(tzinfo=timezone.utc))
        body = {**json.loads(row["body"]), **entry} if seen >= row["last_seen"] else json.loads(row["body"])
        db.execute("UPDATE discoveries SET last_seen=?,seen_count=seen_count+1,body=? WHERE case_id=? AND key=?",
                   (newest, dump(body), key, slot))

def observe_reach(db, key, reach, observed_at):
    if not isinstance(reach, dict) or not isinstance(reach.get("metrics"), dict):
        return
    as_of = norm_time(reach.get("asOf") or observed_at) or utc()
    db.execute("INSERT OR REPLACE INTO reach_samples VALUES(?,?,?,?)",
               (key, as_of, str(reach.get("source") or ""), dump({**reach, "asOf": as_of})))

def _moment(value):
    return parse_time(value) or datetime.min.replace(tzinfo=timezone.utc)

def reach_series(db, key):
    return [json.loads(r["body"]) for r in db.execute(
        "SELECT body FROM reach_samples WHERE case_id=? ORDER BY observed,source", (key,))]

def latest_reach(samples):
    """Per metric the newest dated reading; a hidden or missing reading replaces an older number."""
    metrics, latest = {}, None
    for sample in samples:
        for name, metric in sample["metrics"].items():
            at = metric.get("observedAt") or sample["asOf"]
            if name not in metrics or _moment(at) >= _moment(metrics[name]["observedAt"]):
                metrics[name] = {**metric, "observedAt": norm_time(at)}
        if latest is None or _moment(sample["asOf"]) >= _moment(latest["asOf"]):
            latest = sample
    if latest is None:
        return None
    return {"asOf": latest["asOf"], "source": latest.get("source"), "primary": latest.get("primary"), "metrics": metrics}

def discovery_entries(db, key):
    return [{**json.loads(r["body"]), "firstSeenAt": r["first_seen"], "lastSeenAt": r["last_seen"],
             "seenCount": r["seen_count"]}
            for r in db.execute("SELECT * FROM discoveries WHERE case_id=? ORDER BY first_seen,key", (key,))]

def version_list(db, key):
    """Versions with the level that changed; versions stored before S2 are classified from their rows."""
    out, previous = [], None
    for row in db.execute("SELECT v.version,v.observed,v.signature,v.capture,v.finding,m.reason,m.details "
                          "FROM versions v LEFT JOIN version_meta m ON m.id=v.id AND m.version=v.version "
                          "WHERE v.id=? ORDER BY v.version", (key,)):
        capture, found = json.loads(row["capture"]), json.loads(row["finding"])
        parts = signature_parts(capture, found)
        if row["reason"]:
            reason, details = row["reason"], json.loads(row["details"])
        else:
            reason, details = version_reason(previous[0] if previous else None, parts,
                                             previous[1] if previous else {}, found)
        out.append({"version": row["version"], "observedAt": row["observed"], "sha256": row["signature"],
                    "changeKind": reason, "details": details})
        previous = (parts, found)
    return out

# --- shadow qualification (contract v2, step S5) ---
SHADOW_KEYS = ("reviewDecision", "reviewScore", "adRelationship", "relationships", "adRegistry", "premises",
               "counterEvidence", "coverage", "variants", "analysisVersion", "priority")

def split_shadow(finding):
    """(finding as v1 stores it, shadow fields). Findings without a qualification pass through untouched."""
    if "reviewDecision" not in finding:
        return finding, None
    shadow = {k: finding[k] for k in SHADOW_KEYS if k in finding}
    evidence = finding.get("evidence") or []
    shadow["evidence"] = [e for e in evidence if isinstance(e, dict) and "role" in e]
    kept = {k: v for k, v in finding.items() if k not in SHADOW_KEYS}
    kept["evidence"] = [e for e in evidence if not (isinstance(e, dict) and "role" in e)]
    return kept, shadow

def save_shadow(db, key, version, shadow):
    if shadow is not None:
        db.execute("INSERT OR REPLACE INTO qualification_results VALUES(?,?,?,?)", (key, version, dump(shadow), utc()))

def shadow_view(db, key, version):
    """Shadow fields of the current version. Names that clash with a v1 field get a V2 suffix until S7."""
    row = db.execute("SELECT body FROM qualification_results WHERE case_id=? AND version=?", (key, version)).fetchone()
    if row is None:
        return {}, {}
    shadow = json.loads(row[0])
    renamed = {"evidenceV2": shadow.pop("evidence", None), "coverageV2": shadow.pop("coverage", None)}
    return shadow, {k: v for k, v in renamed.items() if v is not None}

class Conflict(Exception):
    """The caller acted on an outdated entry (HTTP 409)."""

class Invalid(Exception):
    """The request breaks a rule of the contract (HTTP 422)."""

def model_available():
    """The local model of qual_d_model has no place to run yet (N3): the variant cannot be switched on."""
    return False

def threshold_history(db, variant):
    return [threshold_row(r) for r in db.execute("SELECT * FROM thresholds WHERE variant=? ORDER BY id", (variant,))]

def set_threshold(db, variant, value, note, expected_id, restored_from=None):
    if variant not in THRESHOLD_VARIANTS:
        raise Invalid("Nieznany wariant.")
    current = threshold_current(db, variant)
    if current and expected_id != current["id"]:
        raise Conflict("Próg został zmieniony. Odśwież go przed zapisem.")
    key = db.execute("INSERT INTO thresholds(variant,value,note,restored_from,at) VALUES(?,?,?,?,?)",
                     (variant, int(value), note or "", restored_from, utc())).lastrowid
    event(db, "threshold", variant, f"Próg wariantu {variant}: {int(value)}")
    return threshold_row(db.execute("SELECT * FROM thresholds WHERE id=?", (key,)).fetchone())

def restore_threshold(db, entry_id, expected_id, note):
    old = db.execute("SELECT * FROM thresholds WHERE id=?", (entry_id,)).fetchone()
    if old is None:
        raise Invalid("Nie ma takiego wpisu progu.")
    return set_threshold(db, old["variant"], old["value"], note or f"Przywrócono wpis {entry_id}", expected_id, entry_id)

def qualification_history(db):
    return [settings_row(r) for r in db.execute("SELECT * FROM qualification_settings ORDER BY id")]

def set_qualification(db, variant, expected_id, note, validation_ref, approved_by, restored_from=None):
    if variant not in VARIANTS:
        raise Invalid("Nieznany wariant kwalifikacji.")
    current = qualification_current(db)
    if current and expected_id != current["id"]:
        raise Conflict("Wariant został zmieniony. Odśwież go przed zapisem.")
    if variant != ANALYSIS_VARIANT and not (validation_ref and approved_by):
        raise Invalid("Wariant inny niż rules_1_2 wymaga validationRef (raport z odłożoną próbą) i approvedBy.")
    if variant == "qual_d_model" and not model_available():
        raise Invalid("Model lokalny jest niedostępny: brak digestu wag z locka i miejsca uruchomienia.")
    rules = analysis_current()["rules"]
    if variant != ANALYSIS_VARIANT:
        try:
            from analysis import qualification
            rules = qualification.RULES_VERSION
        except Exception:
            pass
    key = db.execute("INSERT INTO qualification_settings(variant,previous_id,restored_from,note,validation_ref,approved_by,at,rules_version)"
                     " VALUES(?,?,?,?,?,?,?,?)", (variant, current and current["id"], restored_from, note or "", validation_ref,
                                                  approved_by, utc(), rules)).lastrowid
    event(db, "qualification", variant, f"Wariant kwalifikacji: {variant}")
    return settings_row(db.execute("SELECT * FROM qualification_settings WHERE id=?", (key,)).fetchone()), current

def restore_qualification(db, entry_id, expected_id, note):
    old = db.execute("SELECT * FROM qualification_settings WHERE id=?", (entry_id,)).fetchone()
    if old is None:
        raise Invalid("Nie ma takiego wpisu wariantu.")
    return set_qualification(db, old["variant"], expected_id, note or f"Przywrócono wpis {entry_id}",
                             old["validation_ref"], old["approved_by"], entry_id)

def source_counts(sources):
    """{ok, empty, partial, failed, total}: what the scan summary shows for the sources of one run."""
    out = {"ok": 0, "empty": 0, "partial": 0, "failed": 0, "total": len(sources)}
    for source in sources:
        status = source.get("status")
        if status == "access_blocked":
            out["accessBlocked"] = out.get("accessBlocked", 0) + 1  # a known, documented state: not a failure of the run
        elif health_of(status) != "ok":
            out["failed"] += 1
        elif status in ("partial", "stale"):
            out["partial"] += 1
        elif status == "empty":
            out["empty"] += 1
        else:
            out["ok"] += 1
    return out

def blocked_sources(sources):
    """Sources whose access is blocked, as the scan summary names them (id, message, next step, date of the attempt)."""
    out = []
    for source in sources:
        if source.get("status") == "access_blocked":
            last = source.get("lastError") if isinstance(source.get("lastError"), dict) else {}
            out.append({"id": source.get("id") or source.get("name"), "name": source.get("name"),
                        "code": last.get("code") or "access_blocked", "message": last.get("message") or source.get("error"),
                        "nextStep": last.get("nextStep"), "attemptedAt": last.get("at") or source.get("observedAt")})
    return out

def _eligible_refer(db, body, shadow):
    """An eligible, un-gated refer of the active variant for a stored body plus its shadow record."""
    if not shadow or body.get("module", "M1") != "M1" or derive_origin(body) not in ("live", "replay"):
        return False
    variant = active_variant(db)
    view = variant_view({**body, **shadow}, variant, threshold_value(db, variant))
    return bool(view["queueEligible"] and not view.get("gated"))

def apply_recompute(db, pairs, scan_id):
    """Re-analysed stored captures. Each case keeps its own mode; analyst decisions are never touched."""
    total = {"newCreators": 0, "firstLiveCreators": 0, "changedFindings": 0, "captures": 0, "creatorsSeen": 0, "referred": 0}
    for capture, finding in pairs:
        result = apply_scan(db, [(capture, finding)], [], [], capture.get("mode") or "live", scan_id=scan_id)
        total["changedFindings"] += result["changedFindings"]
        total["referred"] += result["referred"]
        total["captures"] += 1
    return total

def shadow_eligible(shadow, threshold):
    """refer and above the threshold; a record without a score keeps its own queueEligible flag."""
    decision = (shadow or {}).get("reviewDecision") or {}
    if decision.get("route") != "refer":
        return False
    value = ((shadow or {}).get("reviewScore") or {}).get("value")
    return bool(decision.get("queueEligible")) if value is None else value >= threshold

def shadow_variant(shadow):
    return ((shadow or {}).get("analysisVersion") or {}).get("variant") or ANALYSIS_VARIANT

def latest_shadow(db, key):
    row = db.execute("SELECT body FROM qualification_results WHERE case_id=? ORDER BY version DESC LIMIT 1", (key,)).fetchone()
    return json.loads(row[0]) if row else None

def refer_transition(db, key, shadow):
    """high_risk for the qual_d variants: once, when a case becomes an eligible refer."""
    variant = shadow_variant(shadow)
    if shadow is None or not variant.startswith("qual_d"):
        return None
    threshold = threshold_value(db, variant)
    return shadow_eligible(shadow, threshold) and not shadow_eligible(latest_shadow(db, key), threshold)

MEDIA_KEYS = ("segments", "mediaCoverage", "frames", "mediaVersion", "framesAttempted", "mediaAttempts")

def media_outcome(capture):
    """done (transcript read), unavailable (permanent gap), failed (retry later) or None (not attempted)."""
    from analysis.engine import permanent_gap
    if not isinstance(capture.get("mediaCoverage"), dict):
        return None
    transcript = capture["mediaCoverage"].get("transcript") or {}
    if any(isinstance(x, dict) and str(x.get("text", "")).strip() for x in capture.get("segments") or []):
        return "done"
    if transcript.get("state") == "unavailable":
        return "unavailable" if permanent_gap(transcript.get("reason")) else "failed"
    if transcript.get("state") == "pending" and capture.get("mediaAttempts"):
        return "failed"  # a pending video with tries (429 of this video only): counts as an attempt, retried later
    return None

def save_media(db, key, capture):
    """Remember the media step of a case beside its versions; a finished reading is never replaced by a gap."""
    outcome = media_outcome(capture)
    if outcome is None or (outcome == "failed" and not capture.get("mediaAttempts")):
        return  # a stale gap copied from an older capture is not an attempt
    row = db.execute("SELECT state,body FROM media_state WHERE case_id=?", (key,)).fetchone()
    old = json.loads(row["body"]) if row else {}
    if row and row["state"] == "done" and outcome != "done":
        return
    body = {k: capture[k] for k in MEDIA_KEYS if k in capture}
    attempted = bool(capture.get("frames") or capture.get("framesAttempted") or old.get("framesAttempted"))
    body["framesAttempted"] = attempted
    body["attempts"] = int(capture.get("mediaAttempts") or old.get("attempts") or 0)
    db.execute("INSERT OR REPLACE INTO media_state VALUES(?,?,?,?)", (key, outcome, dump(body), utc()))

def media_states(db, keys=None):
    rows = db.execute("SELECT case_id,state,body FROM media_state")
    return {r["case_id"]: {**json.loads(r["body"]), "state": r["state"]} for r in rows if keys is None or r["case_id"] in keys}

def gate_of(shadow, variant):
    return (((shadow or {}).get("variants") or {}).get(variant) or {}).get("gated")

def stamp_analysis(db, key, body, finding):
    """M2 and M3 findings of the legacy form (no qualification record) keep their analysisVersion in the case body.
    A recompute that gives the same analysis writes no new version, so the stamp is written here: needsRecalc ends."""
    declared = finding.get("analysisVersion")
    if not isinstance(declared, dict) or body.get("analysisVersion") == declared:
        return body
    body = {**body, "analysisVersion": declared, "rulesVersion": finding.get("rulesVersion") or body.get("rulesVersion")}
    db.execute("UPDATE cases SET body=? WHERE id=?", (dump(body), key))
    return body

def apply_scan(db, findings, creators, sources, mode, scan_id=None):
    new_creators=0
    first_live=0
    updated_cases=0
    referred=0
    for creator in creators:
        key=creator["id"]
        before=db.execute("SELECT body FROM creators WHERE id=?", (key,)).fetchone()
        old=json.loads(before[0]) if before else {}
        if mode=="replay" and old.get("lastMode")=="live":
            continue
        is_new=not bool(before) and not creator.get("isSeed",False)
        first_live+=mode=="live" and old.get("lastMode")!="live" and not creator.get("isSeed",False)
        source_mode=old.get("firstMode",mode)
        body={**old,**creator,"isNew":is_new,"firstSeen":old.get("firstSeen") or utc(),
              "firstMode":source_mode,"lastMode":mode, "lastSeen":utc()}
        db.execute("INSERT INTO creators VALUES(?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body",(key,dump(body)))
        new_creators+=is_new
    for source in sources:
        key=source.get("id") or source["name"]
        before=db.execute("SELECT body FROM sources WHERE id=?",(key,)).fetchone()
        old=json.loads(before[0]) if before else {}
        if mode=="replay" and old.get("mode")=="live":
            continue
        body={**merge_stored_paths(old,source),"mode":mode,"checkedAt":utc()}
        body["lastSuccessAt"]=source.get("lastSuccessAt") or (utc() if source["status"]=="ok" else old.get("lastSuccessAt"))
        db.execute("INSERT INTO sources VALUES(?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body",(key,dump(body)))
    for capture,finding in findings:
        finding,shadow=split_shadow(finding)
        key=finding["id"]
        original=capture
        capture=normalize_capture(original)
        # Acquisition times, statistics and discovery paths change on each scan. Version only the
        # captured content and analysis; the observation layer is stored beside the versions.
        proof_revision=capture.get("m2EvidenceRevision")
        parts=signature_parts(capture,finding,original)
        signature=parts["signature"]
        before=db.execute("SELECT fingerprint,revision,body FROM cases WHERE id=?",(key,)).fetchone()
        previous_body=json.loads(before["body"]) if before else {}
        if mode=="replay" and previous_body.get("mode")=="live":
            continue
        if before and shadow is None:
            previous_body=stamp_analysis(db,key,previous_body,finding)
        if previous_body.get("m2EvidenceRevision") and not capture.get("m2Market"):
            latest=previous_body.get("latestM2Observation",previous_body["observedAt"])
            if not proof_revision or datetime.fromisoformat(capture["observedAt"])<datetime.fromisoformat(latest):
                continue
        observe_discovery(db,key,capture.get("discovery"),scan_id)
        observe_reach(db,key,capture.get("reach"),capture.get("observedAt"))
        save_media(db,key,capture)
        if before and COMPLETENESS_RANK[completeness(capture)]<COMPLETENESS_RANK[completeness(previous_body)]:
            # A thinner reading of known content adds its path and statistics but never a version.
            continue
        if before and before["fingerprint"] in (signature,parts["legacy"]):
            transition=refer_transition(db,key,shadow) if shadow else None
            referred+=bool(shadow and _eligible_refer(db,{**previous_body,**finding},shadow)
                           and not _eligible_refer(db,previous_body,latest_shadow(db,key)))
            if transition:
                event(db,"high_risk",key,finding["title"])
            elif shadow and shadow_variant(shadow)=="rules_1_2" and finding.get("score",0)>=70 \
                    and gate_of(latest_shadow(db,key),"rules_1_2") and not gate_of(shadow,"rules_1_2"):
                event(db,"high_risk",key,finding["title"])  # the speech gate was released (transcript examined or unobtainable)
            if mode=="live":
                if isinstance(capture.get("availability"),dict) and _moment(capture["availability"].get("observedAt"))>=_moment((previous_body.get("availability") or {}).get("observedAt")):
                    previous_body["availability"]=capture["availability"]
                if proof_revision:
                    previous_body["latestM2Observation"]=capture["observedAt"]
                else:
                    promoted=previous_body.get("mode")!="live"
                    if "observedAt" in capture and (_moment(capture["observedAt"])>=_moment(previous_body.get("observedAt"))):
                        previous_body["observedAt"]=capture["observedAt"]
                    if isinstance(capture.get("provenance"),dict):
                        # The reading that defined the stored content keeps its provenance; a replay case
                        # promoted to live takes the live one. Other paths are listed from `discovery`.
                        old_provenance=previous_body.get("provenance") if isinstance(previous_body.get("provenance"),dict) else {}
                        previous_body["provenance"]={**old_provenance,**capture["provenance"]} if promoted or not old_provenance else old_provenance
                previous_body["mode"]="live"
                db.execute("UPDATE cases SET body=? WHERE id=?",(dump(previous_body),key))
            save_shadow(db,key,previous_body.get("version"),shadow)
            continue
        version=db.execute("SELECT coalesce(max(version),0)+1 FROM versions WHERE id=?",(key,)).fetchone()[0]
        old_finding,old_parts={},None
        if before:
            last=db.execute("SELECT capture,finding FROM versions WHERE id=? AND version=?",(key,version-1)).fetchone()
            if last:
                old_finding=json.loads(last["finding"])
                old_parts=signature_parts(json.loads(last["capture"]),old_finding)
        reason,details=version_reason(old_parts,parts,old_finding,finding)
        body={k:v for k,v in {**capture,**finding,"version":version,"mode":mode}.items() if k!="m3Pages"}  # pages stay in versions.capture
        db.execute("INSERT INTO versions VALUES(?,?,?,?,?,?)",
                   (key,version,signature,utc(),dump(capture),dump(finding)))
        db.execute("INSERT INTO version_meta VALUES(?,?,?,?,?,?,?)",
                   (key,version,reason,parts["content"],parts["evidence"],parts["analysis"],dump(details)))
        db.execute("""INSERT INTO cases VALUES(?,?,?,'new',1,?) ON CONFLICT(id) DO UPDATE SET
                      body=excluded.body, fingerprint=excluded.fingerprint,revision=cases.revision+1,updated=excluded.updated""",
                   (key,dump(body),signature,utc()))
        transition=refer_transition(db,key,shadow) if shadow else None
        referred+=bool(shadow and _eligible_refer(db,body,shadow) and not _eligible_refer(db,previous_body,latest_shadow(db,key)))
        save_shadow(db,key,version,shadow)
        record(db,key,"capture","Zachowano wersję materiału",{"version":version,"changeKind":reason})
        fired=(finding.get("score",0)>=70 and not gate_of(shadow,"rules_1_2")) if transition is None else transition
        event(db,"high_risk" if fired else "finding",key,finding["title"])
        updated_cases+=1
    return {"newCreators":new_creators,"firstLiveCreators":first_live,"changedFindings":updated_cases,"captures":len(findings),"creatorsSeen":len(creators),
            "referred":referred,"sources":source_counts(sources),"accessBlocked":blocked_sources(sources)}

# --- settings, decisions and queues (contract v2, steps S6 and S7) ---
VARIANTS = ("rules_1_2", "qual_d", "qual_d_model")
# Thresholds of the M2 card and the M3 offers: separate entries in `thresholds` (no migration; an absent row is the default).
MODULE_VARIANT = {"M2": "m2_card", "M3": "m3_card"}
MODULE_DEFAULT = {"m2_card": 30, "m3_card": 60}
THRESHOLD_VARIANTS = VARIANTS + tuple(MODULE_VARIANT.values())
QUEUES = ("review", "adRegister", "offersM2", "offersM3", "incomplete", "closed", "all", "demo")
ROUTE_OF_SUGGESTION = {"review": "refer", "uncertain": "complete", "no_signal": "no_signal", "unavailable": "insufficient"}

def settings_row(row):
    return None if row is None else {"id": row["id"], "variant": row["variant"], "setAt": row["at"], "note": row["note"],
                                     "previousId": row["previous_id"], "restoredFrom": row["restored_from"],
                                     "validationRef": row["validation_ref"], "validatedBy": row["approved_by"],
                                     "rulesVersion": row["rules_version"], "modelId": row["model_id"]}

def qualification_current(db):
    return settings_row(db.execute("SELECT * FROM qualification_settings ORDER BY id DESC LIMIT 1").fetchone())

def active_variant(db):
    return (qualification_current(db) or {}).get("variant") or ANALYSIS_VARIANT

def threshold_row(row):
    return None if row is None else {"id": row["id"], "variant": row["variant"], "value": row["value"], "setAt": row["at"],
                                     "note": row["note"], "restoredFrom": row["restored_from"]}

def threshold_current(db, variant):
    row = threshold_row(db.execute("SELECT * FROM thresholds WHERE variant=? ORDER BY id DESC LIMIT 1", (variant,)).fetchone())
    if row is None and variant in MODULE_DEFAULT:
        return {"id": 0, "variant": variant, "value": MODULE_DEFAULT[variant], "setAt": None, "note": "Wpis domyślny", "restoredFrom": None}
    return row

def threshold_value(db, variant):
    return (threshold_current(db, variant) or {"value": MODULE_DEFAULT.get(variant, 60)})["value"]

def last_decision(db, key):
    row = db.execute("SELECT at,note,details FROM history WHERE case_id=? AND action='decision' ORDER BY seq DESC LIMIT 1", (key,)).fetchone()
    if row is None:
        return None
    details = json.loads(row["details"])
    return {"status": details.get("status"), "at": row["at"], "note": row["note"], "version": details.get("version"),
            "revision": details.get("revision"), "route": details.get("route"), "analysisSig": details.get("analysisSig"),
            "resolution": details.get("resolution")}

def variant_view(body, variant, threshold, module_threshold=None):
    """Route, score and queue eligibility of a case under one variant. `module_threshold` is the threshold of the
    M2 card or the M3 offers (their own scale), default the module's stored default."""
    variants = body.get("variants") if isinstance(body.get("variants"), dict) else {}
    chosen = variants.get(variant)
    decision = body.get("reviewDecision") if isinstance(body.get("reviewDecision"), dict) else {}
    score = body.get("reviewScore") if isinstance(body.get("reviewScore"), dict) else {}
    if chosen is not None:
        route = chosen.get("route")
        value = (chosen.get("reviewScore") or {}).get("value")
        value = body.get("score") if variant == "rules_1_2" and value is None else value
    elif (body.get("reviewSuggestion") or {}).get("state") and not decision:
        route, value = ROUTE_OF_SUGGESTION.get(body["reviewSuggestion"]["state"]), body.get("score")
    elif decision:
        route, value = decision.get("route"), score.get("value")
    else:
        route, value = None, body.get("score")
    if value is None and decision and variant != "rules_1_2" and decision.get("queueEligible"):
        eligible = route == "refer"
    else:
        eligible = bool(route == "refer" and isinstance(value, (int, float)) and value >= threshold)
    if chosen is None and decision.get("queueEligible") is not None and value is None:
        eligible = bool(route == "refer" and decision["queueEligible"])
    module = body.get("module", "M1")
    if module in ("M2", "M3") and chosen is None and decision:
        # The card of the module decided on its own scale (M2 card: premises from 30 points; M3: route refer).
        eligible = bool(route == "refer" and decision.get("queueEligible"))
        if module_threshold is not None and isinstance(value, (int, float)):
            if module == "M2":
                premises = bool((body.get("reviewScore") or {}).get("components"))
                eligible = bool(route in ("refer", "no_signal") and premises and value >= module_threshold)
            else:
                eligible = bool(route == "refer" and decision.get("queueEligible") and value >= module_threshold)
        return {"route": route, "value": value, "queueEligible": eligible, "gated": None}
    return {"route": route, "value": value, "queueEligible": eligible and module == "M1",
            "gated": (chosen or {}).get("gated")}

def rereview(db, key, status, body, decided):
    """pendingReReview: closed, and a content or evidence version came after the version that was decided."""
    if not decided or status != "closed" or decided.get("version") is None or body.get("version", 0) <= decided["version"]:
        return False, False
    kinds = set()
    for version in range(decided["version"] + 1, body["version"] + 1):
        row = db.execute("SELECT reason FROM version_meta WHERE id=? AND version=?", (key, version)).fetchone()
        kinds.add(row[0] if row else "content")
    return bool(kinds & {"content", "evidence"}), False

def has_signal(core):
    """A relation proof, a firm of the registry in the description or title, an unresolved identity or a computation gap."""
    relation = core.get("adRelationship") if isinstance(core.get("adRelationship"), dict) else {}
    firm = relation.get("firm") if isinstance(relation.get("firm"), dict) else {}
    decision = core.get("reviewDecision") if isinstance(core.get("reviewDecision"), dict) else {}
    score = core.get("reviewScore") if isinstance(core.get("reviewScore"), dict) else {}
    return bool(relation.get("status") in ("declared", "documented", "probable") or firm.get("mention") or firm.get("candidates")
                or (core.get("adRegistry") or {}).get("state") in ("included", "candidate")
                or core.get("relationships") or decision.get("completeReason") == "identity_unresolved"
                or str(score.get("notComputableReason") or "").startswith("Kwalifikacja nie powiodła się")
                or any(isinstance(p, dict) and p.get("status") in ("documented", "conditional", "candidate")
                       for p in core.get("premises") or []))

def queues_of(core, view, flags, threshold=None):
    """Queue names of one case (contract 3.4). A pure function of the case record."""
    origin = core.get("origin")
    out = set()
    live = origin in ("live", "replay")
    available = core.get("outOfScope") is None and (core.get("availability") or {}).get("state") != "removed"
    out.add("all")
    if origin in ("synthetic", "upload"):
        out.add("demo")
    if not live:
        return sorted(out)
    if available:
        module = core.get("module", "M1")
        if core.get("status") == "closed":
            out.add("closed")
        evidence = core.get("evidenceV2") if core.get("evidenceV2") is not None else core.get("_evidenceV2")
        has_evidence = not evidence or any(e.get("available", True) for e in evidence)
        reopened = core.get("status") == "closed" and (flags["pendingReReview"] or flags["reviewStale"])
        if module in ("M1", "M2", "M3") and (view["route"] == "refer" or module == "M2") and view["queueEligible"] and has_evidence and not core.get("needsRecalc") \
                and (core.get("status") != "closed" or reopened):
            out.add("review")
        if (core.get("adRegistry") or {}).get("state") in ("included", "candidate"):
            out.add("adRegister")
        decision = core.get("reviewDecision") if isinstance(core.get("reviewDecision"), dict) else {}
        if module == "M2":
            if (core.get("m2Scope") or {}).get("belongs") is not False:
                out.add("offersM2")
            # incomplete: only a concrete gap (too few measurable criteria), never the mere wait for a recompute.
            if decision and view["route"] == "insufficient":
                out.add("incomplete")
        elif module == "M3":
            identity = core.get("identity") if isinstance(core.get("identity"), dict) else {}
            if not decision or view["route"] in ("refer", "complete") or identity.get("licensed"):
                out.add("offersM3")  # a licensed firm stays visible as a negative control
            if decision and view["route"] == "complete" and decision.get("missing"):
                out.add("incomplete")
        else:
            # incomplete: only material with a signal and a concrete gap that can still be closed.
            # A video without any signal is no_signal with the coverage "mowy nie zbadano" and stays in `all`.
            if core.get("needsRecalc") or (view["route"] in ("complete", "insufficient") and (view.get("gated") or has_signal(core))):
                out.add("incomplete")
    else:
        out.discard("closed")
    return sorted(out)

def case_core(db, row, current, settings):
    """The case record without history, versions and observation layers: enough to classify it."""
    body = json.loads(row["body"])
    key = row["id"]
    shadow, renamed = shadow_view(db, key, body.get("version"))
    body = {**body, **shadow}
    view = compat_view(body, current)
    decided = last_decision(db, key)
    variant = settings["variant"]
    chosen = variant_view(body, variant, settings["thresholds"].get(variant, 60),
                          settings["thresholds"].get(MODULE_VARIANT.get(body.get("module"))))
    pending, _ = rereview(db, key, row["status"], body, decided)
    stale = bool(decided and decided.get("route") is not None and chosen["route"] is not None and decided["route"] != chosen["route"])
    flags = {"pendingReReview": pending, "reviewStale": stale}
    if body.get("platform"):
        body = {**body, "platform": canonical_platform(body["platform"])}
    core = {**view, **body, **{k: body[k] for k in ("origin", "analysisVersion", "derived") if k in body},
            **{k: view[k] for k in ("needsRecalc", "needsRecalcReason", "requalification")},
            "id": key, "status": row["status"], "revision": row["revision"], "updatedAt": row["updated"],
            "_evidenceV2": renamed.get("evidenceV2"), "_coverage": renamed.get("coverageV2")}
    return core, renamed, decided, chosen, flags

def load_settings(db):
    qualification = qualification_current(db)
    return {"variant": (qualification or {}).get("variant") or ANALYSIS_VARIANT, "qualification": qualification,
            "thresholds": {v: threshold_value(db, v) for v in THRESHOLD_VARIANTS}}

FRAME_NAME = re.compile(r"[A-Za-z0-9_.-]{1,80}\.jpg")

def frame_name(path):
    name = str(path or "").replace("\\", "/").rsplit("/", 1)[-1]
    return name if FRAME_NAME.fullmatch(name) else None

def with_thumbnail(case_id, evidence):
    """Frame evidence gets `thumbnailUrl` (read-only route /v1/frames/{videoId}/{name}); other evidence is untouched."""
    if not isinstance(evidence, dict) or evidence.get("modality") != "frame" or evidence.get("thumbnailUrl"):
        return evidence
    name, video = frame_name(evidence.get("framePath") or evidence.get("path")), str(case_id)[8:]
    if name and case_id.startswith("youtube:") and VIDEO_ID.fullmatch(video):
        return {**evidence, "thumbnailUrl": f"/v1/frames/{video}/{name}"}
    return evidence

def frame_file(db, video, name, roots):
    """Path of a frame JPEG that the stored case really lists, inside one of `roots`; else None. No path traversal."""
    if not VIDEO_ID.fullmatch(video) or not FRAME_NAME.fullmatch(name):
        return None
    row = db.execute("SELECT body FROM cases WHERE id=?", ("youtube:" + video,)).fetchone()
    if row is None:
        return None
    frames = json.loads(row[0]).get("frames") or []
    listed = [f for f in frames if isinstance(f, dict) and frame_name(f.get("path")) == name]
    if not listed:
        return None
    for root in roots:
        base = Path(root).resolve()
        target = (base / video / "frames" / name).resolve()
        if target.is_file() and target.parent == (base / video / "frames").resolve():
            wanted = listed[0].get("sha256")
            if wanted and sha256(target.read_bytes()).hexdigest() != wanted:
                continue
            return target
    return None

def apply_schema(case, renamed, legacy_coverage, schema):
    """schema 1 keeps the old desk working (v1 evidence, coverage as text); schema 2 uses the target names."""
    coverage = renamed.get("coverageV2")
    schema = schema if isinstance(schema, int) else 1
    if schema >= 2:
        case["history"] = [details_object({**h, "changeKind": h.get("changeKind") or (h["action"] if h["action"] != "capture" else "content")})
                           for h in case.get("history", [])]
        if renamed.get("evidenceV2"):
            case["evidence"] = renamed["evidenceV2"]
        if isinstance(case.get("evidence"), list):
            case["evidence"] = [with_thumbnail(case["id"], e) for e in case["evidence"]]
        if coverage is not None:
            case["coverage"] = {**coverage, **({"legacyText": legacy_coverage} if isinstance(legacy_coverage, str) else {})}
    else:
        case.update({k: v for k, v in renamed.items() if v is not None})
    return case

def case_dict(db,row,current=None,schema=2,settings=None,full=True):
    current=current or analysis_current()
    settings=settings or load_settings(db)
    core,renamed,decided,chosen,flags=case_core(db,row,current,settings)
    key=row["id"]
    core.pop("_evidenceV2",None)
    core.pop("_coverage",None)
    legacy_coverage=core.get("coverage") if isinstance(core.get("coverage"),str) else None
    probe={**core,"_evidenceV2":renamed.get("evidenceV2"),"_coverage":renamed.get("coverageV2")}
    out={**core,"queues":queues_of(probe,chosen,flags),"pendingReReview":flags["pendingReReview"],
         "reviewStale":flags["reviewStale"],"lastDecision":decided,"activeVariant":settings["variant"],
         "route":chosen["route"],"queueEligible":chosen["queueEligible"]}
    layer={}
    if full:
        entries=discovery_entries(db,key)
        if entries:
            layer["discovery"]=entries
            paths=[{k:e.get(k) for k in ("method","adapter","sourceId","sourceUrl","observedAt","responseSha256")} for e in entries]
            layer["provenance"]={**(core.get("provenance") if isinstance(core.get("provenance"),dict) else {}),"paths":paths}
        reach=latest_reach(reach_series(db,key))
        if reach:
            layer["reach"]=reach
        versions=version_list(db,key)
        if versions:
            layer["versions"]=versions
        layer["history"]=history(db,key)
    result=apply_schema({**out,**layer},renamed,legacy_coverage,schema)
    if schema>=2 and full:
        from .proof_path import proof_path
        result["proofPath"]=proof_path(result)
    return result

def band_of(value, threshold):
    """Strength band relative to the threshold of the active variant: strong from max(80, threshold), moderate from the
    threshold, weak below it; None when no score is computed."""
    if not isinstance(value, (int, float)):
        return None
    return "strong" if value >= max(80, threshold) else "moderate" if value >= threshold else "weak"

def disclosure_info(case):
    """Kind and time of the disclosure that put the case into the register (time in the material, seconds, if known)."""
    registry = case.get("adRegistry") if isinstance(case.get("adRegistry"), dict) else {}
    relation = case.get("adRelationship") if isinstance(case.get("adRelationship"), dict) else {}
    disclosure = relation.get("disclosure") if isinstance(relation.get("disclosure"), dict) else {}
    evidence = next((e for e in case.get("evidence") or [] if isinstance(e, dict) and disclosure.get("evidenceId")
                     and e.get("id") == disclosure["evidenceId"]), None)
    if not (registry.get("disclosureKind") or disclosure.get("state") not in (None, "not_checked")):
        return None
    return {"kind": registry.get("disclosureKind"), "state": disclosure.get("state"), "where": disclosure.get("where"),
            "atSec": (evidence or {}).get("start"), "text": disclosure.get("text")}

def firm_of(case):
    """The firm the row is about: the advertiser or registry firm (M1), the owner of the page (M2 card), the operator the
    page names (M3)."""
    module=case.get("module","M1")
    if module=="M3":
        return m3_report_cells(case)["podmiot"] or None
    if module=="M2":
        card=case.get("m2Card") if isinstance(case.get("m2Card"),dict) else {}
        firm=card.get("firm") if isinstance(card.get("firm"),dict) else {}
        return firm.get("name") or firm.get("brand") or case.get("legalName") or case.get("brand") or case.get("creatorName") or None
    name,_=_firm_cells(case)
    return name or None

def clean_firm(name):
    """The KNF copy of 21 XI lost the first letter of one word ("... S.A.) iuro Maklerskie PEKAO"): restore it for display."""
    return re.sub(r"\)\s+iuro\b",") Biuro",name) if isinstance(name,str) else name

def firm_names(case):
    """(short trade name, full registry name) of the firm of a row; the short one is the display name."""
    module=case.get("module","M1")
    if module=="M3":
        name=m3_report_cells(case)["podmiot"] or None
        return name,name
    if module=="M2":
        card=case.get("m2Card") if isinstance(case.get("m2Card"),dict) else {}
        firm=card.get("firm") if isinstance(card.get("firm"),dict) else {}
        legal=clean_firm(firm.get("name") or case.get("legalName") or None)
        return firm.get("brand") or legal or case.get("brand") or case.get("creatorName") or None, legal
    relation=case.get("adRelationship") if isinstance(case.get("adRelationship"),dict) else {}
    firm=relation.get("firm") if isinstance(relation.get("firm"),dict) else {}
    legal,_=_firm_cells(case)
    return firm.get("mention") or case.get("brand") or legal or None, legal or None

def clean_title(title):
    """A title without the separator that a cut left at its end ("Rachunek IKE -")."""
    return re.sub(r"[\s\-–—|·:,;]+$","",title).strip() if isinstance(title,str) else title

def summary_of_case(case, threshold=60, thresholds=None):
    module_threshold=(thresholds or {}).get(MODULE_VARIANT.get(case.get("module")))
    band_threshold=module_threshold if module_threshold is not None else threshold
    short,legal=firm_names(case)
    decision=case.get("reviewDecision") if isinstance(case.get("reviewDecision"),dict) else {}
    active=case.get("activeVariant") or ANALYSIS_VARIANT
    chosen=variant_view(case,active,threshold)
    moment=next(iter(decision.get("moments") or []),None)
    reason=decision.get("reason")
    if active==ANALYSIS_VARIANT:  # the shadow decision belongs to qual_d; the active rules explain themselves
        reason=(case.get("reviewSuggestion") or {}).get("reason") or reason
    registry=case.get("adRegistry") if isinstance(case.get("adRegistry"),dict) else {}
    reasons=decision.get("reasons") or []
    coverage=case.get("coverage") if isinstance(case.get("coverage"),dict) else {}
    return {"id":case["id"],"title":clean_title(case.get("title")),"module":case.get("module"),"platform":case.get("platform"),
            "creatorId":case.get("creatorId"),"creatorName":case.get("creatorName") or case.get("author"),"publishedAt":case.get("publishedAt"),
            "observedAt":case.get("observedAt"),"status":case["status"],"revision":case["revision"],"version":case.get("version"),
            "origin":case.get("origin"),"importLabel":case.get("importLabel"),"route":case.get("route"),"reviewScore":chosen["value"],
            "band":band_of(chosen["value"],band_threshold),"completeReason":decision.get("completeReason"),
            "firstReason":reasons[0] if reasons else None,
            "score":case.get("score"),"queueEligible":case.get("queueEligible"),"adRegistry":registry.get("state"),
            "adRegistryInfo":{"state":registry.get("state"),"summary":registry.get("summary"),
                              "identityStatus":registry.get("identityStatus")} if registry else None,
            "disclosure":disclosure_info(case),
            "transcriptState":((coverage.get("modalities") or {}).get("transcript") or {}).get("state"),
            "queues":case["queues"],"pendingReReview":case["pendingReReview"],"reviewStale":case["reviewStale"],
            "needsRecalc":case.get("needsRecalc"),"priority":case.get("priority"),"reason":reason,
            "firm":short,"firmShort":short,"firmLegal":legal,"licensed":(bool((case.get("identity") or {}).get("licensed")) if case.get("module")=="M3" else None),
            "publishedAtDerived":case.get("publishedAtDerived"),"publishedAtBasis":published_of(case)[1],
            "firstMoment":moment,"lastDecision":case.get("lastDecision"),"url":case.get("url")}

def creator_names(db):
    """creatorId to display name from the creators table (replay and older captures carry no creatorName)."""
    names={}
    for row in db.execute("SELECT id,body FROM creators"):
        try:
            name=(json.loads(row[1]) or {}).get("name")
        except ValueError:
            continue
        if name:
            names[row[0]]=name
    return names

def all_cases(db,schema=2,full=False):
    current=analysis_current()
    settings=load_settings(db)
    names=creator_names(db)
    cases=[case_dict(db,r,current,schema,settings,full) for r in db.execute("SELECT * FROM cases ORDER BY updated DESC,id")]
    for case in cases:
        if not case.get("creatorName") and names.get(case.get("creatorId")):
            case["creatorName"]=names[case["creatorId"]]
    return cases,settings

def queue_counts(cases):
    """Counters of every queue plus `transcriptPending`: live or replay M1 material whose speech is still to be fetched."""
    counts=dict.fromkeys(QUEUES,0)
    counts["transcriptPending"]=0
    for case in cases:
        for name in case["queues"]:
            counts[name]+=1
        coverage=case.get("coverage") if isinstance(case.get("coverage"),dict) else {}
        if case.get("origin") in ("live","replay") and ((coverage.get("modalities") or {}).get("transcript") or {}).get("state")=="pending":
            counts["transcriptPending"]+=1
    return counts

def _moment_of(value):
    return parse_time(value) or datetime.min.replace(tzinfo=timezone.utc)

def queue_effect(db, variant, threshold):
    """How many cases of the real review queue change if `variant` used `threshold` instead of its stored threshold."""
    current=analysis_current()
    settings=load_settings(db)
    stored=settings["thresholds"].get(variant,60)
    probe={**settings,"variant":variant,"thresholds":{**settings["thresholds"],variant:threshold}}
    base={**settings,"variant":variant}
    gained,lost,now=[],[],0
    for row in db.execute("SELECT * FROM cases"):
        in_now=in_then=False
        for setting,box in ((base,"now"),(probe,"then")):
            core,_,_,chosen,flags=case_core(db,row,current,setting)
            member="review" in queues_of(core,chosen,flags)
            if box=="now": in_now=member
            else: in_then=member
        now+=in_now
        if in_then and not in_now: gained.append(row["id"])
        if in_now and not in_then: lost.append(row["id"])
    return {"variant":variant,"storedThreshold":stored,"threshold":threshold,"reviewQueueAtStored":now,
            "reviewQueueAtThreshold":now+len(gained)-len(lost),"changed":len(gained)+len(lost),
            "gained":gained[:50],"lost":lost[:50]}

def module_queue_effect(db, module, threshold):
    """The review queue of one module (M2 card or M3 offers) at `threshold` against its stored threshold."""
    variant = MODULE_VARIANT[module]
    current, settings = analysis_current(), load_settings(db)
    stored = settings["thresholds"].get(variant, MODULE_DEFAULT[variant])
    probe = {**settings, "thresholds": {**settings["thresholds"], variant: threshold}}
    gained, lost, now = [], [], 0
    for row in db.execute("SELECT * FROM cases"):
        if json.loads(row["body"]).get("module") != module:
            continue
        member = []
        for setting in (settings, probe):
            core, _, _, chosen, flags = case_core(db, row, current, setting)
            member.append("review" in queues_of(core, chosen, flags))
        now += member[0]
        if member[1] and not member[0]: gained.append(row["id"])
        if member[0] and not member[1]: lost.append(row["id"])
    return {"module": module, "variant": variant, "storedThreshold": stored, "threshold": threshold, "reviewQueueAtStored": now,
            "reviewQueueAtThreshold": now + len(gained) - len(lost), "changed": len(gained) + len(lost),
            "gained": gained[:50], "lost": lost[:50]}

DEMO_ALERT_CASE = "web:www.bdm.pl/rachunek-emerytalny"
DEMO_ALERT_TABLES = (("cases", "id"), ("versions", "id"), ("version_meta", "id"), ("history", "case_id"), ("discoveries", "case_id"),
                     ("reach_samples", "case_id"), ("media_state", "case_id"), ("qualification_results", "case_id"))

def demo_alert_state(db):
    return {"case": DEMO_ALERT_CASE, "armed": db.execute("SELECT 1 FROM cases WHERE id=?", (DEMO_ALERT_CASE,)).fetchone() is None,
            "trigger": {"method": "POST", "path": "/v1/scans", "body": {"mode": "replay", "adapters": ["demo-alert"], "requestId": "<nowy identyfikator>"}},
            "reset": {"method": "POST", "path": "/v1/demo/alert/reset"}}

def reset_demo_alert(db):
    """Remove the one demo case (a saved real M2 page) so that the next `demo-alert` replay creates it again and raises
    `high_risk` exactly once. Idempotent: a second reset removes nothing. Nothing else is touched."""
    removed = db.execute("SELECT 1 FROM cases WHERE id=?", (DEMO_ALERT_CASE,)).fetchone() is not None
    for table, column in DEMO_ALERT_TABLES:
        db.execute(f"DELETE FROM {table} WHERE {column}=?", (DEMO_ALERT_CASE,))
    return {**demo_alert_state(db), "removed": removed}

def published_of(case):
    """Publication time; TikTok gives none, so the time derived from the video id stands in (flagged by the report)."""
    if case.get("publishedAt"):
        return case["publishedAt"], "platform"
    derived=case.get("publishedAtDerived")
    if isinstance(derived,dict) and derived.get("value"):
        return derived["value"], derived.get("basis") or "derived"
    return None, None

def filter_cases(items, *, module=None, creator=None, since=None, until=None, min_score=None, q=None, platform=None,
                 band=None, route=None, status=None, date_field="observedAt", variant="rules_1_2", threshold=60, thresholds=None):
    """The filters shared by the queues and the report: module, platform, date, risk (score, band), route, status."""
    if module:
        items=[c for c in items if c.get("module")==module]
    if creator:
        items=[c for c in items if c.get("creatorId")==creator]
    if platform:
        wanted=canonical_platform(platform).lower()
        items=[c for c in items if canonical_platform(str(c.get("platform") or "").split(":")[0]).lower()==wanted]
    if route:
        items=[c for c in items if c.get("route")==route]
    if status:
        items=[c for c in items if c.get("status")==status]
    if band:
        def band_threshold(c):
            own=(thresholds or {}).get(MODULE_VARIANT.get(c.get("module")))
            return threshold if own is None else own
        items=[c for c in items if band_of(variant_view(c,variant,threshold)["value"],band_threshold(c))==band]
    def when(c):
        return published_of(c)[0] if date_field=="publishedAt" else c.get("observedAt")
    if since:
        items=[c for c in items if when(c) and _moment_of(when(c))>=_moment_of(since)]
    if until:
        items=[c for c in items if when(c) and _moment_of(when(c))<=_moment_of(until)]
    if min_score is not None:
        def value(c):
            return variant_view(c,variant,threshold)["value"] if c.get("module","M1")=="M1" else c.get("score")
        items=[c for c in items if isinstance(value(c),(int,float)) and value(c)>=min_score]
    if q:
        needle=q.casefold()
        items=[c for c in items if any(needle in str(c.get(k) or "").casefold() for k in ("title","creatorName","author","creatorId"))]
    return items

def queue_list(db, name, *, limit=50, cursor=None, module=None, creator=None, since=None, until=None, min_score=None,
               q=None, section=None, platform=None, band=None, route=None, date_field="observedAt"):
    if name not in QUEUES:
        raise KeyError(name)
    cases,settings=all_cases(db)
    counts=queue_counts(cases)
    items=[c for c in cases if name in c["queues"]]
    if name=="adRegister" and section in ("confirmed","candidate"):
        want="included" if section=="confirmed" else "candidate"
        items=[c for c in items if (c.get("adRegistry") or {}).get("state")==want]
    items=filter_cases(items,module=module,creator=creator,since=since,until=until,min_score=min_score,q=q,platform=platform,
                       band=band,route=route,date_field=date_field,variant=settings["variant"],
                       threshold=settings["thresholds"].get(settings["variant"],60),thresholds=settings["thresholds"])
    def score(c):
        view=variant_view(c,settings["variant"],60)["value"]
        return view if isinstance(view,(int,float)) else -1
    if name=="review":
        items.sort(key=lambda c:(-score(c),(c.get("priority") or {}).get("review",{}).get("rank") is None,
                                  -((c.get("priority") or {}).get("review",{}).get("rank") or 0),
                                  [-ord(ch) for ch in (c.get("publishedAt") or "")]))
    elif name in ("adRegister",):
        items.sort(key=lambda c:[-ord(ch) for ch in (c.get("publishedAt") or "")])
    elif name=="incomplete":
        items.sort(key=lambda c:(not c.get("needsRecalc"),[-ord(ch) for ch in (c.get("observedAt") or "")]))
    elif name=="closed":
        items.sort(key=lambda c:[-ord(ch) for ch in ((c.get("lastDecision") or {}).get("at") or "")])
    else:
        items.sort(key=lambda c:[-ord(ch) for ch in (c.get("observedAt") or "")])
    start=int(cursor or 0)
    page=items[start:start+limit]
    scan=db.execute("SELECT id,status,updated FROM scans ORDER BY created DESC LIMIT 1").fetchone()
    return {"items":[summary_of_case(c,settings["thresholds"].get(settings["variant"],60),settings["thresholds"]) for c in page],"total":len(items),
            "nextCursor":str(start+limit) if start+limit<len(items) else None,"counts":counts,
            "threshold":{"variant":settings["variant"],**(threshold_current(db,settings["variant"]) or {})},
            "asOf":utc(),"lastScan":None if scan is None else {"id":scan["id"],"status":scan["status"],"updatedAt":scan["updated"]}}

# --- report (brief: filter by date, source, risk level and module; M1 database: firm, advertiser, content, URL) ---
REPORT_QUEUES = {"M1": ("review", "adRegister"), "M2": ("offersM2",), "M3": ("offersM3",)}
REPORT_COLUMNS = {
    "M1": ["firma", "typPodmiotu", "podmiotReklamujacy", "tresc", "url", "platforma", "dataPublikacji", "podstawaDatyPublikacji",
           "dataOdczytu", "trasa", "silaSygnalu", "relacjaReklamowa", "rejestrReklam", "statusDecyzji", "id"],
    "M2": ["firma", "typPodmiotu", "operator", "tresc", "url", "platforma", "dataPublikacji", "podstawaDatyPublikacji",
           "dataOdczytu", "trasa", "silaSygnalu", "statusDecyzji", "id"],
    "M3": ["podmiot", "daneRejestrowe", "trescOferty", "url", "stanUprawnien", "przejrzaneWykazy", "dataWykazow", "platforma",
           "dataOdczytu", "trasa", "silaSygnalu", "statusDecyzji", "id"],
}
ENTITY_NAMES = {"domestic_investment_firm": "krajowa firma inwestycyjna", "domestic_bank": "bank krajowy",
                "foreign_investment_firm": "zagraniczna firma inwestycyjna", "foreign_credit_institution": "zagraniczna instytucja kredytowa",
                "unresolved": "nieustalony", None: ""}

def _first_text(case):
    for e in case.get("evidence") or []:
        if isinstance(e, dict) and e.get("text") and e.get("role") in ("disclosure", "claim", None):
            return e["text"]
    return case.get("description") or case.get("title") or ""

def _firm_cells(case):
    relation=case.get("adRelationship") if isinstance(case.get("adRelationship"),dict) else {}
    firm=relation.get("firm") if isinstance(relation.get("firm"),dict) else {}
    names=sorted({c.get("name") for c in firm.get("candidates") or [] if c.get("name")})
    name=" / ".join(names) or firm.get("mention") or case.get("brand") or ""
    kinds=firm.get("entityTypes") or ([firm["entityType"]] if firm.get("entityType") else [])
    kind="; ".join(dict.fromkeys(ENTITY_NAMES.get(k,k) for k in kinds))
    if not kind and firm.get("identityStatus")=="no_registry_entry":
        kind="brak w przejrzanych wykazach"
    return name,kind

def report_row(case, module, variant):
    firm,kind=_firm_cells(case)
    published,basis=published_of(case)
    view=variant_view(case,variant,60)
    decision=(case.get("lastDecision") or {}).get("status") or case.get("status")
    row={"firma":firm,"typPodmiotu":kind,"tresc":" ".join(str(_first_text(case)).split())[:500],"url":case.get("url"),
         "platforma":str(case.get("platform") or "").split(":")[0],"dataPublikacji":published,"podstawaDatyPublikacji":basis or "",
         "dataOdczytu":case.get("observedAt"),"trasa":case.get("route") or (case.get("reviewSuggestion") or {}).get("state"),
         "silaSygnalu":view["value"],"statusDecyzji":decision,"id":case["id"]}
    who=case.get("creatorName") or case.get("author") or case.get("creatorId")
    if module=="M1":
        relation=case.get("adRelationship") if isinstance(case.get("adRelationship"),dict) else {}
        row.update(podmiotReklamujacy=who,relacjaReklamowa=relation.get("status"),rejestrReklam=(case.get("adRegistry") or {}).get("state"))
    elif module=="M2":
        row["operator"]=who
    else:
        row.update(m3_report_cells(case))
    return {k:row.get(k) for k in REPORT_COLUMNS[module]}

def m3_report_cells(case):
    """Columns of the M3 report: the firm as the page names it, registry data if any, the quotes of the axes,
    the licence state with the reviewed registers and their date."""
    identity=case.get("identity") if isinstance(case.get("identity"),dict) else {}
    operator=identity.get("operator") if isinstance(identity.get("operator"),dict) else {}
    offer=case.get("offer") if isinstance(case.get("offer"),dict) else {}
    name=(operator.get("names") or [None])[0] or offer.get("name") or case.get("brand") or case.get("creatorName") or ""
    ids=[f"NIP {n}" for n in operator.get("nip") or []]+[f"KRS {n}" for n in operator.get("krs") or []]+[f"REGON {n}" for n in operator.get("regon") or []]
    matches=[f"{m.get('register')}: {m.get('name') or ('nr '+str(m.get('number')))}" for m in identity.get("matches") or [] if isinstance(m,dict)]
    registry="; ".join([*ids,*matches[:3]])
    quotes=[f"{c.get('label')}: {c.get('evidence')}" for c in case.get("checks") or []
            if isinstance(c,dict) and c.get("id") in ("action","personalisation","instrument","market") and c.get("state")!="brak danych"]
    state=identity.get("label") or ""
    if identity.get("badge"):
        state=f"{identity['badge']} · {state}"
    return {"podmiot":name,"daneRejestrowe":registry,"trescOferty":" | ".join(" ".join(q.split()) for q in quotes)[:1500],
            "stanUprawnien":state,"przejrzaneWykazy":"; ".join(identity.get("reviewedRegisters") or []),
            "dataWykazow":identity.get("checkedAt") or ""}

def report_list(db, module, *, queue=None, limit=500, cursor=None, platform=None, since=None, until=None, min_score=None,
                band=None, route=None, q=None, date_field="observedAt"):
    """Rows of the module report. Default scope: M1 the review queue plus the ad register, M2/M3 their offer queues;
    `queue` picks any queue instead (`all` includes material without a signal)."""
    if module not in REPORT_COLUMNS:
        raise KeyError(module)
    if queue is not None and queue not in QUEUES:
        raise KeyError(queue)
    cases,settings=all_cases(db)
    wanted=(queue,) if queue else REPORT_QUEUES[module]
    items=[c for c in cases if c.get("module","M1")==module and any(n in c["queues"] for n in wanted)]
    items=filter_cases(items,platform=platform,since=since,until=until,min_score=min_score,q=q,band=band,route=route,
                       date_field=date_field,variant=settings["variant"],threshold=settings["thresholds"].get(settings["variant"],60))
    items.sort(key=lambda c:(published_of(c)[0] or c.get("observedAt") or "", c["id"]),reverse=True)
    start=max(0,int(cursor or 0))
    page=items[start:start+limit]
    return {"module":module,"queues":list(wanted),"columns":REPORT_COLUMNS[module],"total":len(items),
            "items":[report_row(c,module,settings["variant"]) for c in page],
            "nextCursor":str(start+limit) if start+limit<len(items) else None,"asOf":utc(),"variant":settings["variant"]}

FORMULA_START = ("=", "+", "-", "@", "\t", "\r")

def csv_safe(value):
    """A cell that a spreadsheet would read as a formula gets a leading apostrophe; control characters become spaces."""
    if value is None:
        return ""
    if isinstance(value,bool):
        return "tak" if value else "nie"
    if isinstance(value,(int,float)):
        return value
    text="".join(" " if (ord(ch)<32 or ord(ch)==127) else ch for ch in str(value))
    return "'"+text if text.lstrip().startswith(FORMULA_START) or text.startswith(FORMULA_START) else text

def report_csv(report):
    import csv, io
    buffer=io.StringIO()
    writer=csv.writer(buffer,lineterminator="\r\n")
    writer.writerow(report["columns"])
    for row in report["items"]:
        writer.writerow([csv_safe(row.get(c)) for c in report["columns"]])
    return "\ufeff"+buffer.getvalue()

def events_since(db, cursor, limit=100):
    return [dict(r) for r in db.execute("SELECT seq AS id,at,kind,ref,message FROM events WHERE seq>? ORDER BY seq LIMIT ?",(cursor,limit))]

COMPACT_DROP = ("m3Pages", "history", "evidence", "premises", "counterEvidence", "segments", "description", "versions", "discovery",
                "evidenceV2", "frames", "relationships")

def scan_view(db, row):
    """A scan as the desk lists it: result counters plus step progress."""
    out = scan_dict(row)
    steps = db.execute("SELECT status FROM scan_steps WHERE scan_id=?", (row["id"],)).fetchall()
    out["progress"] = {"done": sum(r[0] == "done" for r in steps), "total": len(steps)} if steps else None
    return out

LEGACY_METHOD = {"apple-podcasts": "apple_search", "peertube": "peertube_search", "youtube": "data_api_search"}

def creator_view(creator):
    """Schema 2 creator: `discoveries[]` and `reach` always present (derived and flagged when the record predates v2)."""
    out = dict(creator)
    if out.get("platform"):
        out["platform"] = canonical_platform(out["platform"])
    if not isinstance(out.get("discoveries"), list):
        legacy = out.get("discovery") if isinstance(out.get("discovery"), dict) else None
        platform = str(out.get("platform") or "").split(":")[0]
        out["discoveries"] = [] if not legacy else [{
            "method": legacy.get("method") or LEGACY_METHOD.get(platform, "unknown"), "query": legacy.get("query"),
            "position": legacy.get("rank", legacy.get("position")), "observedAt": legacy.get("observedAt"),
            "sourceUrl": legacy.get("sourceUrl"), "responseSha256": legacy.get("responseSha256"), "derived": "legacy"}]
    if not isinstance(out.get("reach"), dict):
        out["reach"] = {"asOf": None, "source": None, "primary": "subscriberCount",
                        "metrics": {"subscriberCount": {"value": None, "state": "not_collected", "observedAt": None, "source": None}}}
    return out

SOURCE_KINDS = {"youtube": "search", "youtube-replay": "search", "apple-podcasts": "feed", "peertube": "search", "social": "profile",
                "sites": "page", "crosslinks": "crosslink", "replay": "search", "replay-media": "asr",
                "tiktok": "profile", "facebook": "profile", "instagram": "profile", "meta_ads": "feed", "social-replay": "profile"}

def source_view(source, states):
    """Schema 2 source: lastError, quota, retryAt, kind and target from the persisted adapter state."""
    key = source.get("id") or source.get("name")
    state = states.get(key) or {}
    out = {**source, "kind": source.get("kind") or SOURCE_KINDS.get(key), "target": source.get("target") or source.get("url"),
           "lastError": source.get("lastError") or state.get("lastError"), "quota": source.get("quota") or state.get("quota"),
           "retryAt": state.get("retryAt"), "consecutiveErrors": state.get("consecutiveErrors", 0),
           "lastAttemptAt": state.get("lastAttemptAt")}
    if state.get("lastSuccessAt") and not out.get("lastSuccessAt"):
        out["lastSuccessAt"] = state["lastSuccessAt"]
    if key == "youtube":
        quota = out.get("quota") if isinstance(out.get("quota"), dict) else {}
        if not quota.get("keys"):  # an empty ledger still lists the configured keys, nothing used yet
            ids = configured_youtube_keys()
            if ids:
                from collectors.discovery import ADAPTERS
                limit = daily_limit(ADAPTERS["youtube"]) if "youtube" in ADAPTERS else None
                out["quota"] = {"used": quota.get("used") or 0, "limit": quota.get("limit") if quota.get("limit") is not None else
                                (limit * len(ids) if limit else None), "resetAt": quota.get("resetAt"),
                                "keys": [{"keyId": i, "used": 0, "limit": limit, "exhaustedAt": None} for i in ids]}
    return out

def trend(db, days=30):
    """Materials and referrals per scan and per day, from the scan journal (no history is invented for older scans)."""
    rows = db.execute("SELECT * FROM scans WHERE status IN ('done','partial') ORDER BY created DESC LIMIT 400").fetchall()
    by_scan, by_day = [], {}
    for row in reversed(rows):
        result = json.loads(row["result"])
        day = (row["updated"] or row["created"])[:10]
        item = {"scanId": row["id"], "mode": row["mode"], "at": row["updated"], "day": day, "captures": result.get("captures"),
                "changedFindings": result.get("changedFindings"), "referred": result.get("referred"),
                "newCreators": result.get("newCreators")}
        by_scan.append(item)
        entry = by_day.setdefault(day, {"day": day, "scans": 0, "captures": 0, "referred": 0, "referredKnown": True})
        entry["scans"] += 1
        entry["captures"] += 0 if row["mode"] == "recompute" else (result.get("captures") or 0)  # recompute re-reads stored cases
        if result.get("referred") is None:
            entry["referredKnown"] = False
        else:
            entry["referred"] += result["referred"]
    firsts = {}
    for key, at in db.execute("SELECT id, min(observed) FROM versions GROUP BY id"):
        firsts[str(at)[:10]] = firsts.get(str(at)[:10], 0) + 1
    for day, count in firsts.items():
        by_day.setdefault(day, {"day": day, "scans": 0, "captures": 0, "referred": 0, "referredKnown": True})["newMaterials"] = count
    points = [{"newMaterials": 0, **by_day[d]} for d in sorted(by_day)][-max(1, days):]
    return {"byScan": by_scan[-200:], "byDay": points}

def semantic_status():
    """Why the local E5 model is (not) available, without loading it: env var, weight files, Python packages."""
    import importlib.util, os
    from analysis import setup_semantic as setup
    configured = os.environ.get(setup.MODEL_DIR_ENV)
    directory = Path(configured or setup.DEFAULT_DIR)
    missing_files = [name for name in setup.LOCK["files"] if not (directory / name).is_file()]
    missing_packages = [name for name in ("numpy", "onnxruntime", "tokenizers") if importlib.util.find_spec(name) is None]
    reasons = []
    if not configured:
        reasons.append(f"nie ustawiono {setup.MODEL_DIR_ENV}")
    if missing_files:
        reasons.append(f"brak wag modelu E5 w {directory} ({len(missing_files)} z {len(setup.LOCK['files'])} plików)")
    if missing_packages:
        reasons.append("brak pakietów Pythona: " + ", ".join(missing_packages))
    ready = not missing_files and not missing_packages
    return {"status": "ready" if ready else "unavailable", "model": setup.LOCK["repository"], "directory": str(directory),
            "directoryConfigured": bool(configured), "missingFiles": missing_files, "missingPackages": missing_packages,
            "reasons": reasons if not ready else [],
            "m3Mode": "rules_and_model" if ready else "rules_only",
            "message": ("Lokalny model semantyczny jest dostępny." if ready else
                        "Lokalny model semantyczny jest niedostępny: " + "; ".join(reasons) +
                        ". M3 działa wtedy wyłącznie na regułach, a podobieństwo semantyczne nie jest liczone. To poprawny stan.")}

WORKER_WAIT_SECONDS = 10  # a live worker takes a queued scan within a second; longer means nobody is working

def recompute_status(db, now=None):
    """What the last recompute (after a variant, rules or model change) is doing, for /v1/state."""
    row = db.execute("SELECT * FROM scans WHERE mode='recompute' ORDER BY created DESC LIMIT 1").fetchone()
    if row is None:
        return {"state": "none", "scanId": None, "message": "Nie było przeliczenia."}
    status = row["status"]
    cases = db.execute("SELECT count(*) FROM cases").fetchone()[0]
    out = {"scanId": row["id"], "status": status, "since": row["created"], "updatedAt": row["updated"], "cases": cases}
    clock = now or datetime.now(timezone.utc)
    stalled = status == "running" and (row["lease_until"] or 0) < clock.timestamp()  # the worker died: nobody extends the lease
    if status == "queued" or stalled:
        queued = datetime.fromisoformat((row["created"] if status == "queued" else row["updated"]).replace("Z", "+00:00"))
        age = (clock - queued).total_seconds()
        waiting = age >= WORKER_WAIT_SECONDS
        since = row["created"] if status == "queued" else row["updated"]
        return {**out, "state": "waiting_for_worker" if waiting else "queued", "ageSec": round(age), "waitingSince": since if waiting else None,
                "stalled": stalled,
                "message": ("Przeliczenie czeka na worker od " + since + " (" + str(round(age)) + " s bez podjęcia zadania). "
                            "Uruchom worker albo wykonaj przeliczenie ręcznie.") if waiting else "Przeliczenie w kolejce."}
    if status == "running":
        return {**out, "state": "running", "message": "Przeliczenie trwa."}
    if status == "failed":
        return {**out, "state": "failed", "message": "Przeliczenie nie powiodło się; ponów je."}
    return {**out, "state": "done", "message": "Przeliczenie zakończone."}

_COUNTS = {}

def counts_key(db):
    current = analysis_current()
    settings = load_settings(db)
    parts = [db.execute(f"SELECT count(*),max({col}) FROM {table}").fetchone()[:] for table, col in
             (("cases", "updated"), ("qualification_results", "updated"), ("media_state", "updated"))]
    return json.dumps([[tuple(p) for p in parts], settings["variant"], settings["thresholds"], (settings["qualification"] or {}).get("id"), current,
                       str(STATE)], sort_keys=True, default=str)

def counts_of(db, cases=None):
    """Queue counters, cached per database state: the light overview must not classify every case on each request."""
    key = counts_key(db)
    if key not in _COUNTS:
        _COUNTS.clear()
        _COUNTS[key] = queue_counts(cases if cases is not None else all_cases(db)[0])
    return dict(_COUNTS[key])

_FUNNEL = {}

def funnel_of(cases, settings, counts):
    """The path from material to alert for the pitch: how many materials, how many in the ad register, how many are
    explained automatically (and by what), how many wait for speech, how many reach the review queue."""
    live = [c for c in cases if c.get("origin") in ("live", "replay")]
    disclosed = Counter()
    for c in live:
        if "adRegister" in c["queues"]:
            where = (((c.get("adRelationship") or {}).get("disclosure")) or {}).get("where")
            disclosed[{"transcript": "bySpeech", "platform": "byPlatformFlag", "frame": "byFrame", "description": "byDescription"}.get(where, "none")] += 1
    variant = settings["variant"]
    held = sum(1 for c in live if c.get("module", "M1") == "M1" and variant_view(c, variant, settings["thresholds"].get(variant, 60)).get("gated"))
    return {"materials": len(live), "adRegister": counts.get("adRegister", 0), "review": counts.get("review", 0),
            "explainedAutomatically": {k: disclosed.get(k, 0) for k in ("bySpeech", "byPlatformFlag", "byFrame", "byDescription")},
            "adRegisterUnexplained": disclosed.get("none", 0), "heldBySpeechGate": held,
            "byModule": {m: sum(1 for c in live if c.get("module", "M1") == m) for m in ("M1", "M2", "M3")},
            "byPlatform": dict(Counter(canonical_platform(str(c.get("platform") or "").split(":")[0]) for c in live))}

def funnel_cached(db, counts):
    key = counts_key(db)
    if key not in _FUNNEL:
        _FUNNEL.clear()
        cases, settings = all_cases(db)
        _FUNNEL[key] = funnel_of(cases, settings, counts)
    return dict(_FUNNEL[key])

SCAN_LABEL_DATE = ("stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia", "września", "października",
                   "listopada", "grudnia")

def scan_mode(db):
    """`scanMode` and `scanLabel` of the last scan that read sources (a recompute only analyses what is stored)."""
    row = db.execute("SELECT mode,created,updated FROM scans WHERE status IN ('done','partial') AND mode IN ('live','replay') "
                     "ORDER BY created DESC LIMIT 1").fetchone()
    if row is None:
        return {"scanMode": None, "scanLabel": "brak skanu"}
    moment = parse_time(row["created"])
    day = f"{moment.day} {SCAN_LABEL_DATE[moment.month - 1]} {moment.year}" if moment else ""
    if row["mode"] == "replay":
        return {"scanMode": "replay", "scanLabel": f"odtworzenie skanu z {day}".strip()}
    return {"scanMode": "live", "scanLabel": f"skan na żywo z {day}".strip()}

CREATOR_LIGHT = ("id", "name", "platform", "url", "handle", "isSeed", "isNew", "status", "persistentId", "firstSeen", "lastSeen",
                 "discoveredVia", "mode")

def state(schema=2, compact=False, findings=True):
    """The whole state. `findings=False` is the light overview: no cases, creators in short form with counters, the
    queue counters from a cache; sources, scans, health, trend, threshold and qualification as in the full state."""
    schema = schema if isinstance(schema, int) else 1
    compact = compact if isinstance(compact, (bool, int)) else False
    with connection() as db:
        current=analysis_current()
        if findings:
            cases,settings=all_cases(db,schema,full=not compact)
        else:
            cases,settings=[],load_settings(db)
        if compact:
            cases=[{k:v for k,v in c.items() if k not in COMPACT_DROP} for c in cases]
        scans=[scan_view(db,r) for r in db.execute("SELECT * FROM scans ORDER BY created DESC LIMIT 50")]
        events=[dict(r) for r in db.execute("SELECT seq AS id,at,kind,ref,message FROM events ORDER BY seq DESC LIMIT 50")]
        # Schema 1 keeps the v1 shape (T18): rows as stored, health a string per source id.
        sources=[public_source(x) for x in all_objects(db,"sources")]
        if schema>=2 and not any((x.get("id") or x.get("name"))=="meta_ads" for x in sources):
            sources.append(META_ADS_ROW)
        states={s["sourceId"]:s for s in source_states(db)}
        health={(s.get("id") or s.get("name")):health_of(s.get("status")) for s in sources}
        creators=all_objects(db,"creators")
        extra={}
        if not findings:
            by_platform={}
            for creator in creators:
                platform=canonical_platform(str(creator.get("platform") or "").split(":")[0]) or "unknown"
                by_platform[platform]=by_platform.get(platform,0)+1
            extra={"findingsOmitted":True,"creatorCounts":{"total":len(creators),"byPlatform":by_platform}}
            creators=[{k:c[k] for k in CREATOR_LIGHT if k in c} for c in creators]
        if schema>=2:
            by_key={(s.get("id") or s.get("name")):s for s in sources}
            detail={key:{"status":value,"sourceStatus":by_key[key].get("status"),
                         **{k:states.get(key,{}).get(k) for k in ("lastError","quota","retryAt","lastSuccessAt","consecutiveErrors")},
                         "lastAttemptAt":states.get(key,{}).get("lastAttemptAt") or by_key[key].get("observedAt") or by_key[key].get("checkedAt")}
                    for key,value in health.items()}
            for key,entry in detail.items():
                if entry["status"]=="access_blocked":  # replay and older rows keep the explanation on the source row itself
                    entry["lastError"]=entry["lastError"] or by_key[key].get("lastError")
                    entry["probe"]=by_key[key].get("probe")
                    entry["accessPath"]=by_key[key].get("accessPath")
            problem=lambda v:v["status"] not in ("ok","access_blocked") and not (v["status"]=="needs_key" and v.get("optional"))
            for key,entry in detail.items():
                entry["optional"]=key in TOKEN_OPTIONAL
            blocked=sorted(k for k,v in detail.items() if v["status"]=="access_blocked")
            overall="ok" if not any(problem(v) for v in detail.values()) else \
                    "failed" if all(problem(v) for v in detail.values()) and detail else "degraded"
            sources=[source_view(s,states) for s in sources]
            creators=[creator_view(c) for c in creators]
            extra={**extra,"trend":trend(db,14),"sourceHealthDetail":detail,"sourceHealthSummary":{"status":overall,"total":len(detail),
                   "problems":sum(problem(v) for v in detail.values()),
                   "accessBlocked":len(blocked),"accessBlockedSources":blocked}}
        active=settings["variant"]
        queue_numbers=queue_counts(cases) if findings else counts_of(db)
        funnel=funnel_of(cases,settings,queue_numbers) if findings else funnel_cached(db,queue_numbers)
        result={"creators":creators,"funnel":funnel,"sources":sources,"sourceHealth":health,"sourceState":[{k:v for k,v in x.items() if k!="cursor"} for x in states.values()],"findings":cases,"scans":scans,
                "events":events,"schema":{**schema_info(db),"views":[1,2],"served":schema},"analysisCurrent":{**current,"variant":active},
                "queues":queue_numbers,"threshold":{"variant":active,**(threshold_current(db,active) or {})},
                "qualification":settings["qualification"],"recompute":recompute_status(db),"semantic":semantic_status(),**scan_mode(db),**extra}
        for name in ("sources","sourceHealthDetail","sourceState","semantic","scans","events"):
            if name in result:
                result[name]=scrub(result[name])
        return result

def scan_detail(db,key):
    row=db.execute("SELECT * FROM scans WHERE id=?",(key,)).fetchone()
    if row is None:
        return None
    steps=scan_steps(db,key)
    done=sum(s["status"]=="done" for s in steps)
    budget={s["sourceId"]:s["quota"] for s in source_states(db) if s.get("quota")}
    return {**scan_dict(row),"steps":steps,"progress":{"done":done,"total":len(steps)} if steps else None,"budget":budget}
