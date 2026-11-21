"""SQLite Huey queue with a durable scan journal and recoverable claims."""
import logging
import os
from pathlib import Path
import time
from uuid import uuid4

from huey import SqliteHuey
from huey.exceptions import HueyException
from . import store

store.STATE.mkdir(parents=True,exist_ok=True,mode=0o700)
queue=SqliteHuey("investwatch", filename=str(store.STATE/"queue.sqlite3"), results=False)
logger=logging.getLogger("investwatch.worker")

def submit(mode, request_id, payload=None):
    scan,created=store.create_scan(mode,request_id,payload,retry_failed=mode=="upload")
    if created:
        enqueue(scan["id"])
    return scan

def enqueue(key):
    try:
        process(key)
    except Exception:
        logger.exception("Dispatch unavailable; durable job will be recovered")

def claim(key, owner):
    with store.connection(True) as db:
        row=db.execute("SELECT * FROM scans WHERE id=?",(key,)).fetchone()
        if not row or row["status"] not in ("queued","running") or row["lease_until"]>time.time():
            return None
        db.execute("UPDATE scans SET status='running',updated=?,lease_until=?,owner=?,attempts=attempts+1 WHERE id=?",
                   (store.utc(),time.time()+900,owner,key))
        return dict(row)

def build(row):
    import json
    from analysis.engine import analyze, demo_captures
    from analysis.semantic import suggest, review_suggestion
    def evaluate(cap):
        finding=analyze(cap)
        finding["semantic"]=suggest(cap)
        if "reviewSuggestion" not in finding:
            finding["reviewSuggestion"]=review_suggestion(cap, finding["semantic"], finding)
        return cap,finding
    mode=row["mode"]
    if mode=="upload":
        from analysis.transcribe import transcribe_file
        details=json.loads(row["payload"])
        path=store.STATE/"uploads"/details["file"]
        segments=transcribe_file(path)
        cap={"id":"upload-"+row["id"],"creatorId":"local","platform":"upload","module":"M1",
             "title":details["title"],"description":details["description"],"url":"/uploads/"+path.name,
             "mediaUrl":"/uploads/"+path.name,"segments":segments,"provenance":"Nagranie operatora · lokalne ASR",
             "sha256":details["sha256"]}
        return [evaluate(cap)],[],[{"name":"Nagrania operatora","status":"ok","count":1}]
    from collectors.discovery import discover
    with store.connection() as db:
        known=store.all_objects(db,"creators")
    discovery=discover(mode,{x["id"] for x in known},known_creators=known)
    if mode=="live":
        from .listen import sample_audio
        discovery["sources"].append(sample_audio(discovery["captures"]))
    from collectors.m2_archive import apply_rendered, staged_captures
    chromium = os.environ.get("INVESTWATCH_M2_BROWSER")
    refresh = None
    if mode == "live" and chromium:
        from collectors.m2_browser import refresh_from_worker
        refresh = lambda name, root: refresh_from_worker(name, root, chromium)
    proven_urls = apply_rendered(discovery, staged_captures(mode, store.STATE / "m2", refresh))
    demos = [cap for cap in demo_captures() if cap.get("module") != "M2" or cap["url"] not in proven_urls] if mode == "replay" else []
    captures=discovery["captures"]+demos
    return [evaluate(cap) for cap in captures],discovery["creators"],discovery["sources"]

@queue.task()
def process(key):
    owner=uuid4().hex
    row=claim(key,owner)
    if row is None:
        return
    try:
        findings,creators,sources=build(row)
        with store.connection(True) as db:
            active=db.execute("SELECT owner FROM scans WHERE id=?",(key,)).fetchone()[0]
            if active!=owner:
                return
            result=store.apply_scan(db,findings,creators,sources,row["mode"])
            errors=[s for s in sources if s.get("status") in ("error","failed","unavailable","partial","stale","forbidden","rate_limited")]
            status="done"
            if errors:
                status="partial" if len(errors)<len(sources) or findings else "failed"
                result["warnings"]=[s.get("error") or s["name"] for s in errors]
            db.execute("UPDATE scans SET status=?,updated=?,result=?,lease_until=0 WHERE id=?",
                       (status,store.utc(),store.dump(result),key))
            store.event(db,"scan",key,"Skan zakończony")
    except Exception as exc:
        logger.exception("Scan %s failed",key)
        with store.connection(True) as db:
            changed=db.execute("UPDATE scans SET status='failed',updated=?,result=?,lease_until=0 WHERE id=? AND owner=?",
                               (store.utc(),store.dump({"error":str(exc)[:400] or type(exc).__name__}),key,owner)).rowcount
            if changed:
                store.event(db,"scan",key,"Skan wymaga ponowienia")

def recover():
    with store.connection() as db:
        keys=[r[0] for r in db.execute("SELECT id FROM scans WHERE status='queued' OR (status='running' AND lease_until<?)",(time.time(),))]
    for key in keys:
        enqueue(key)

def work():
    logging.basicConfig(level=logging.INFO)
    store.init()
    submit("replay","bootstrap-m2-rendered-v1")
    next_check=0
    interval=int(os.environ.get("INVESTWATCH_DISCOVERY_INTERVAL","14400"))
    while True:
        now=time.time()
        if now>=next_check:
            if interval>0:
                submit("live",f"scheduled-{interval}-{int(now//interval)}")
            recover()
            next_check=now+30
        try:
            task=queue.dequeue()
        except HueyException:
            # A retired queue message can be recreated from the durable scan journal.
            logger.exception("Discarded incompatible queue message; recovering the scan journal")
            recover()
            continue
        if task is None:
            time.sleep(.35)
        else:
            queue.execute(task)

if __name__=="__main__":
    from api.jobs import work as registered_worker
    registered_worker()
