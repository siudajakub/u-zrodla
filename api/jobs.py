"""SQLite Huey queue with a durable scan journal and recoverable claims."""
import json
import logging
import os
from pathlib import Path
import time
from uuid import uuid4

from huey import SqliteHuey
from huey.exceptions import HueyException
from collectors.adapter import LeaseLost, MemoryRunner, with_quota
from . import store

ROOT=store.ROOT

store.STATE.mkdir(parents=True,exist_ok=True,mode=0o700)
queue=SqliteHuey("investwatch", filename=str(store.STATE/"queue.sqlite3"), results=False)
logger=logging.getLogger("investwatch.worker")
# The lease is extended at every progress point (adapter request, step, analysed capture),
# so a live worker keeps its scan and a dead one releases it after this many seconds.
LEASE=int(os.environ.get("INVESTWATCH_LEASE_SECONDS","300"))
BEAT_EVERY=5.0

class ScanRunner(MemoryRunner):
    """Persists steps, source state and the quota ledger of one scan owned by `owner`."""
    def __init__(self, scan_id, owner, mode="live"):
        import threading
        self.scan_id,self.owner,self.mode=scan_id,owner,mode
        self._last,self._lock=0.0,threading.Lock()

    def heartbeat(self, force=False):
        with self._lock:
            if not force and time.monotonic()-self._last<BEAT_EVERY:
                return
            self._last=time.monotonic()
        with store.connection(True) as db:
            store.heartbeat(db,self.scan_id,self.owner,LEASE)

    def plan(self, steps):
        with store.connection(True) as db:
            store.plan_steps(db,self.scan_id,steps)

    def resume(self, step):
        with store.connection() as db:
            return store.step_output(db,self.scan_id,step)

    def started(self, step):
        self.heartbeat(True)
        with store.connection(True) as db:
            store.step_start(db,self.scan_id,step)

    def finished(self, step, status, summary, output):
        with store.connection(True) as db:
            store.step_finish(db,self.scan_id,step,status,summary,output)
        self.heartbeat(True)

    def mark(self, step, status, summary=None):
        if status=="running":
            self.started(step)
        else:
            self.finished(step,status,summary,None)

    def adapter_state(self, adapter_id):
        with store.connection() as db:
            return store.source_state(db,adapter_id)

    def quota(self, adapter, at):
        with store.connection() as db:
            day,_=store.quota_day(adapter,at)
            return store.quota_view(adapter,store.ledger_row(db,adapter.id,day),at)

    def record(self, adapter, result, at):
        if self.mode!="live":
            return result
        with store.connection(True) as db:
            body=store.record_adapter(db,adapter.id,result,at,self.scan_id,adapter)
        return with_quota(result,body.get("quota"))

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
                   (store.utc(),time.time()+LEASE,owner,key))
        return dict(row)

def evaluate(cap, previous=None):
    """One capture to (capture, finding) as a scan does it; `previous` is the stored finding of a recompute."""
    from analysis.engine import analyze
    from analysis.semantic import suggest, review_suggestion
    finding=analyze(cap)
    finding["semantic"]=(previous or {}).get("semantic") or suggest(cap)
    if "reviewSuggestion" not in finding:
        finding["reviewSuggestion"]=review_suggestion(cap,finding["semantic"],finding)
    return cap,finding

def recompute_pairs_raw():
    """(capture, stored finding) of the current version of every stored M1 case, with its media state merged back."""
    pairs=[]
    with store.connection() as db:
        rows=db.execute("SELECT id,body FROM cases").fetchall()
        for row in rows:
            body=json.loads(row["body"])
            if body.get("module","M1")!="M1":
                continue
            last=db.execute("SELECT capture,finding FROM versions WHERE id=? AND version=?",(row["id"],body.get("version"))).fetchone()
            if last is None:
                continue
            cap={k:v for k,v in json.loads(last["capture"]).items() if k not in ("discovery","reach")}
            pairs.append((cap,json.loads(last["finding"])))
        media=store.media_states(db)
    from .enrich import merge_known
    return [(merge_known([cap],media)[0],old) for cap,old in pairs]

def recompute_pairs(runner):
    """Stored M1 captures analysed again with the current rules. Observations are not replayed."""
    out=[]
    for cap,old in recompute_pairs_raw():
        runner.heartbeat()
        out.append(evaluate(cap,old))
    return out

def build(row, owner=None):
    import json
    from analysis.engine import analyze, demo_captures
    from analysis.semantic import suggest, review_suggestion
    mode=row["mode"]
    runner=ScanRunner(row["id"],owner,mode) if row.get("id") and owner else MemoryRunner()
    def evaluate(cap):
        runner.heartbeat()
        finding=analyze(cap)
        finding["semantic"]=suggest(cap)
        if "reviewSuggestion" not in finding:
            finding["reviewSuggestion"]=review_suggestion(cap, finding["semantic"], finding)
        return cap,finding
    if mode=="enrich":
        # Light scan: the media backlog of stored cases. No discovery adapter, no YouTube Data API quota.
        from analysis import engine
        from .enrich import enrich_media
        with store.connection() as db:
            engine.ACTIVE_VARIANT=store.active_variant(db)
        runner.plan(["enrich","analyze","apply"])
        runner.mark("enrich","running")
        pairs=recompute_pairs_raw()
        previous={cap["id"]:old for cap,old in pairs}
        stored=[cap for cap,_ in pairs]
        with store.connection() as db:
            known=store.media_states(db)
        changed,media_summary=enrich_media(stored,"enrich",runner,analyze=engine.analyze,heartbeat=runner.heartbeat,known=known,backlog=True)
        runner.mark("enrich","done",{"captures":len(changed),"media":media_summary})
        runner.mark("analyze","running")
        found=[]
        for cap in changed:
            runner.heartbeat()
            found.append(globals()["evaluate"](cap,previous.get(cap["id"])))
        runner.mark("analyze","done",{"captures":len(found)})
        return found,[],[]
    if mode=="recompute":
        from analysis import engine
        with store.connection() as db:
            engine.ACTIVE_VARIANT=store.active_variant(db)
        runner.plan(["analyze","apply"])
        runner.mark("analyze","running")
        found=recompute_pairs(runner)
        runner.mark("analyze","done",{"captures":len(found)})
        return found,[],[]
    from analysis import engine
    with store.connection() as db:
        engine.ACTIVE_VARIANT=store.active_variant(db)
    if mode=="upload":
        from analysis.transcribe import transcribe_file
        details=json.loads(row["payload"])
        path=store.STATE/"uploads"/details["file"]
        runner.plan(["transcribe","analyze","apply"])
        runner.mark("transcribe","running")
        segments=transcribe_file(path)
        runner.mark("transcribe","done")
        cap={"id":"upload-"+row["id"],"creatorId":"local","platform":"upload","module":"M1",
             "title":details["title"],"description":details["description"],"url":"/uploads/"+path.name,
             "mediaUrl":"/uploads/"+path.name,"segments":segments,"provenance":"Nagranie operatora · lokalne ASR",
             "sha256":details["sha256"]}
        return [evaluate(cap)],[],[{"name":"Nagrania operatora","status":"ok","count":1}]
    from collectors.discovery import discover, planned_steps
    with store.connection() as db:
        known=store.all_objects(db,"creators")
    only=(json.loads(row.get("payload") or "{}") or {}).get("adapters") if isinstance(row,dict) else None
    runner.plan([*planned_steps(mode,only),"enrich","analyze","apply"])
    options={"youtube":{"raw_dir":store.STATE/"youtube-raw","cache_dir":store.STATE/"youtube-cache"}}
    discovery=discover(mode,{x["id"] for x in known},known_creators=known,runner=runner,options=options,only=only)
    runner.mark("enrich","running")
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
    from .enrich import enrich_media
    with store.connection() as db:
        known=store.media_states(db)
    captures,media_summary=enrich_media(captures,mode,runner,analyze=analyze,heartbeat=runner.heartbeat,known=known)
    runner.mark("enrich","done",{"captures":len(captures),"media":media_summary})
    from .enrich import pack_source
    pack=pack_source(media_summary)
    if pack:
        discovery["sources"].append(pack)
    runner.mark("analyze","running")
    found=[evaluate(cap) for cap in captures]
    runner.mark("analyze","done",{"captures":len(found)})
    return found,discovery["creators"],discovery["sources"]

@queue.task()
def process(key):
    owner=uuid4().hex
    row=claim(key,owner)
    if row is None:
        return
    try:
        findings,creators,sources=build(row,owner)
        with store.connection(True) as db:
            active=db.execute("SELECT owner FROM scans WHERE id=?",(key,)).fetchone()[0]
            if active!=owner:
                return
            result=(store.apply_recompute(db,findings,key) if row["mode"] in ("recompute","enrich")
                    else store.apply_scan(db,findings,creators,sources,row["mode"],scan_id=key))
            errors=[s for s in sources if s.get("status") in ("error","failed","unavailable","partial","stale","forbidden","rate_limited","limit","needs_key")]
            status="done"
            if errors:
                status="partial" if len(errors)<len(sources) or findings else "failed"
                result["warnings"]=[s.get("error") or (s.get("lastError") or {}).get("message") or s["name"] for s in errors]
            db.execute("UPDATE scans SET status=?,updated=?,result=?,lease_until=0 WHERE id=?",
                       (status,store.utc(),store.dump(result),key))
            store.step_finish(db,key,"apply","done",{"changedFindings":result.get("changedFindings")})
            store.clear_step_outputs(db,key)
            store.event(db,"scan",key,"Skan zakończony")
    except LeaseLost:
        logger.warning("Scan %s was taken over by another worker; this run stops without writing",key)
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
    from collectors.discovery import ADAPTERS
    if "youtube-replay" in ADAPTERS and (ROOT/"fixtures/raw/discovery/youtube-api-2026-11-21/replay.json.gz").is_file():
        submit("replay","bootstrap-youtube-replay-v1",{"adapters":["youtube-replay"]})
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
