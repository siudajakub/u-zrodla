"""Durable case data. Each transaction gets its own SQLite connection."""
from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
from uuid import uuid4

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

def init():
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    with sqlite3.connect(STATE / "cases.sqlite3",timeout=20) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.executescript(SCHEMA)

def event(db, kind, ref, message):
    db.execute("INSERT INTO events(at,kind,ref,message) VALUES(?,?,?,?)", (utc(),kind,ref,message))

def record(db, case_id, action, note, details):
    db.execute("INSERT INTO history(case_id,at,action,note,details) VALUES(?,?,?,?,?)",
               (case_id,utc(),action,note,dump(details)))

def history(db, case_id):
    return [{**dict(row), **json.loads(row["details"])} for row in db.execute(
        "SELECT at,action,note,details FROM history WHERE case_id=? ORDER BY seq", (case_id,))]

def scan_dict(row):
    return {"id":row["id"],"scanId":row["id"],"mode":row["mode"],"status":row["status"],
            "createdAt":row["created"],"updatedAt":row["updated"],"attempts":row["attempts"],
            **json.loads(row["result"])}

def create_scan(mode, request_id, payload=None):
    with connection(True) as db:
        row=db.execute("SELECT * FROM scans WHERE request_id=?", (request_id,)).fetchone()
        if row:
            if row["mode"] != mode:
                raise ValueError("Ten identyfikator żądania ma inny tryb.")
            return scan_dict(row), False
        key=uuid4().hex
        now=utc()
        db.execute("INSERT INTO scans(id,request_id,mode,status,created,updated,payload,result) VALUES(?,?,?,'queued',?,?,?,?)",
                   (key,request_id,mode,now,now,dump(payload or {}),"{}"))
        event(db,"scan",key,"Dodano skan do kolejki")
        return scan_dict(db.execute("SELECT * FROM scans WHERE id=?", (key,)).fetchone()),True

def all_objects(db, table):
    assert table in {"creators","sources"}
    return [json.loads(r[0]) for r in db.execute(f"SELECT body FROM {table} ORDER BY id")]

def apply_scan(db, findings, creators, sources, mode):
    new_creators=0
    first_live=0
    updated_cases=0
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
        body={**source,"mode":mode,"checkedAt":utc()}
        body["lastSuccessAt"]=source.get("lastSuccessAt") or (utc() if source["status"]=="ok" else old.get("lastSuccessAt"))
        db.execute("INSERT INTO sources VALUES(?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body",(key,dump(body)))
    for capture,finding in findings:
        key=finding["id"]
        # Acquisition times change on each scan. Version only the captured content and analysis.
        content_keys=("title","url","description","segments","mediaUrl","publishedAt","module","brand","platform","creatorId","sha256","contractDemo")
        signature=sha256(dump([[capture.get(k) for k in content_keys],finding.get("summary"),finding.get("score"),
                                finding.get("checks"),finding.get("evidence")]).encode()).hexdigest()
        before=db.execute("SELECT fingerprint,revision,body FROM cases WHERE id=?",(key,)).fetchone()
        if before and mode=="replay" and json.loads(before["body"]).get("mode")=="live":
            continue
        if before and before["fingerprint"]==signature:
            previous_body=json.loads(before["body"])
            if mode=="live":
                previous_body.update({field:capture[field] for field in ("observedAt","provenance") if field in capture})
                previous_body["mode"]="live"
                db.execute("UPDATE cases SET body=? WHERE id=?",(dump(previous_body),key))
            continue
        version=db.execute("SELECT coalesce(max(version),0)+1 FROM versions WHERE id=?",(key,)).fetchone()[0]
        body={**capture,**finding,"version":version,"mode":mode}
        db.execute("INSERT INTO versions VALUES(?,?,?,?,?,?)",
                   (key,version,signature,utc(),dump(capture),dump(finding)))
        db.execute("""INSERT INTO cases VALUES(?,?,?,'new',1,?) ON CONFLICT(id) DO UPDATE SET
                      body=excluded.body, fingerprint=excluded.fingerprint,revision=cases.revision+1,updated=excluded.updated""",
                   (key,dump(body),signature,utc()))
        record(db,key,"capture","Zachowano wersję materiału",{"version":version})
        event(db,"high_risk" if finding.get("score",0)>=70 else "finding",key,finding["title"])
        updated_cases+=1
    return {"newCreators":new_creators,"firstLiveCreators":first_live,"changedFindings":updated_cases,"captures":len(findings),"creatorsSeen":len(creators)}

def case_dict(db,row):
    return {**json.loads(row["body"]),"id":row["id"],"status":row["status"],"revision":row["revision"],
            "updatedAt":row["updated"],"history":history(db,row["id"])}

def events_since(db, cursor, limit=100):
    return [dict(r) for r in db.execute("SELECT seq AS id,at,kind,ref,message FROM events WHERE seq>? ORDER BY seq LIMIT ?",(cursor,limit))]

def state():
    with connection() as db:
        cases=[case_dict(db,r) for r in db.execute("SELECT * FROM cases ORDER BY updated DESC,id")]
        scans=[scan_dict(r) for r in db.execute("SELECT * FROM scans ORDER BY created DESC LIMIT 50")]
        events=[dict(r) for r in db.execute("SELECT seq AS id,at,kind,ref,message FROM events ORDER BY seq DESC LIMIT 50")]
        return {"creators":all_objects(db,"creators"),"sources":all_objects(db,"sources"),"findings":cases,"scans":scans,"events":events}
