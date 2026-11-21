"""InvestWatch private, same-origin analyst application."""
from contextlib import asynccontextmanager
from datetime import date
from hashlib import sha256
import asyncio
import json
import os
from pathlib import Path
import tempfile
from typing import Literal
from urllib.parse import urlsplit
from functools import lru_cache

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import FileResponse, Response
from starlette.staticfiles import StaticFiles
from . import jobs, store

@asynccontextmanager
async def lifespan(app):
    store.init()
    (store.STATE/"uploads").mkdir(mode=0o700,exist_ok=True)
    yield

app=FastAPI(title="InvestWatch",lifespan=lifespan,docs_url=None,redoc_url=None)
app.add_middleware(TrustedHostMiddleware,allowed_hosts=["localhost","127.0.0.1","[::1]","testserver"]+
                   [x for x in os.getenv("INVESTWATCH_HOSTS","").split(",") if x])

def origin_ok(origin, host):
    if not origin:
        return True
    parsed=urlsplit(origin)
    return parsed.scheme in ("http","https") and parsed.netloc==host

@app.middleware("http")
async def same_origin(request,call_next):
    if request.method not in ("GET","HEAD","OPTIONS") and not origin_ok(request.headers.get("origin"),request.headers.get("host")):
        from starlette.responses import JSONResponse
        return JSONResponse({"detail":"Żądanie musi pochodzić z lokalnego pulpitu."},status_code=403)
    response=await call_next(request)
    response.headers["X-Content-Type-Options"]="nosniff"
    response.headers["Referrer-Policy"]="no-referrer"
    return response

class ScanRequest(BaseModel):
    mode:Literal["live","replay","recompute","enrich"]
    requestId:str=Field(min_length=1,max_length=160)
    sourceId:Literal["all"]="all"
    adapters:list[str]|None=None

RESOLUTION_STATUS={"refer_to_control":"reviewing","complete_data":"reviewing","no_signal":"closed","close":"closed"}

class Decision(BaseModel):
    """`status` as before; `resolution` records the kind of the analyst's decision (and implies a status when none is given)."""
    status:Literal["new","reviewing","closed"]|None=None
    resolution:Literal["refer_to_control","complete_data","no_signal","close"]|None=None
    expectedRevision:int=Field(ge=1)
    note:str=Field(min_length=1,max_length=2000)
    reviewedVersion:int|None=Field(None,ge=1)

class ThresholdBody(BaseModel):
    value:int=Field(ge=0,le=100)
    expectedId:int
    note:str=Field("",max_length=500)
    variant:str|None=None

class QualificationBody(BaseModel):
    variant:str
    expectedId:int
    note:str=Field("",max_length=500)
    validationRef:str|None=Field(None,max_length=200)
    approvedBy:str|None=Field(None,max_length=100)

class RestoreBody(BaseModel):
    id:int
    expectedId:int
    note:str=Field("",max_length=500)

class EvidenceBody(BaseModel):
    caseId:str
    kind:Literal["transcript"]
    source:Literal["analyst"]="analyst"
    text:str|None=Field(None,max_length=200000)
    segments:list[dict]|None=None
    note:str=Field("",max_length=2000)
    expectedRevision:int=Field(ge=1)

class Contract(BaseModel):
    endDate:date
    label:str=Field(min_length=1,max_length=200)
    expectedRevision:int|None=None
    channel:str=Field("",max_length=100)
    requiredLabel:str=Field("",max_length=120)

class Inquiry(BaseModel):
    action:Literal["draft","waiting","denied","confirmed","documents"]
    expectedRevision:int=Field(ge=1)
    note:str=Field("",max_length=2000)

def wanted_schema(request,schema=None):
    """View 2 for the new desk: `?schema=2` or the header `X-InvestWatch-Schema: 2`. Default 1 (old desk, web/legacy.html)."""
    if isinstance(schema,int):
        return schema
    if request is None:
        return 1
    try:
        value=int(request.headers.get("x-investwatch-schema","1"))
    except ValueError:
        return 1
    return value if value in (1,2) else 1

@app.get("/v1/health")
def health():
    with store.connection() as db:
        db.execute("SELECT 1").fetchone()
        schema=store.schema_info(db)["version"]
    return {"status":"ok","schema":schema}

@app.get("/v1/calibration")
def calibration(threshold:int|None=Query(None,ge=0,le=100),variant:str|None=Query(None),dataset:str=Query("q-v2"),
                coverage:str=Query("pelne")):
    """Default dataset q-v2 (M1, agent labels, both variants); `dataset=illustrative` keeps the old illustrative set.
    Without `threshold` the threshold of the variant that filters the real queue is used, and the response says
    how many cases of that queue would change under a different one."""
    if variant is not None and variant not in store.VARIANTS:
        raise HTTPException(422,"Nieznany wariant.")
    if dataset not in ("q-v2","illustrative"):
        raise HTTPException(422,"Nieznany zbiór. Dostępne: q-v2, illustrative.")
    with store.connection() as db:
        active=store.active_variant(db)
        chosen=variant or active
        stored=store.threshold_value(db,chosen)
        value=stored if threshold is None else threshold
        effect=store.queue_effect(db,chosen,value) if dataset=="q-v2" else None
    if dataset=="illustrative":
        return calculate_cached(value,chosen)
    from . import calibration_q2
    if not calibration_q2.available():
        raise HTTPException(503,"Brak plików zbioru q-v2 w fixtures/validation/q-v2.")
    try:
        out=calibration_q2.compare(value,coverage)
    except ValueError as error:
        raise HTTPException(422,str(error)) from error
    # headline of the requested (default: active) variant, in the shape of the old calibration
    head=out["variants"].get(chosen) or out["variants"]["qual_d"]
    return {**out,"variant":chosen,"activeVariant":active,"storedThreshold":stored,"thresholdSource":"request" if threshold is not None else "stored",
            **{k:head[k] for k in ("tp","fp","tn","fn","cost","errors","withheld")},
            "precisionCI":{"low":head["precisionCI95"][0],"high":head["precisionCI95"][1],"method":"Wilson 95%"} if isinstance(head["precisionCI95"],list) else None,
            "groups":head["independentCampaigns"],"publicExamples":out["n"],"syntheticExamples":0,"queueEffect":effect}

def state_calibration():
    """The calibration block of /v1/state: the q-v2 comparison at the threshold of the active variant (illustrative set if absent)."""
    from . import calibration_q2
    with store.connection() as db:
        variant=store.active_variant(db)
        value=store.threshold_value(db,variant)
    if not calibration_q2.available():
        return calculate_cached(60,"rules_1_2")
    return calibration_q2.compare(value)

def labeled_digest():
    """Digest of the illustrative set's files: a cached result never outlives a change of the set."""
    folder=Path(__file__).resolve().parents[1]/"fixtures"/"labeled"
    digest=sha256()
    for path in sorted(folder.glob("*.json")):
        digest.update(path.name.encode()+sha256(path.read_bytes()).digest())
    return digest.hexdigest()[:16]

def calculate_cached(threshold,variant="rules_1_2"):
    return _calculate(threshold,variant,labeled_digest())

@lru_cache(maxsize=303)
def _calculate(threshold,variant,digest):
    from analysis.engine import calibration as calculate
    return calculate(threshold,variant)

@app.get("/v1/state")
def state(schema:int|None=Query(None,ge=1,le=2),compact:int=Query(0),findings:int=Query(1),request:Request=None):
    """The whole state. `?findings=0` (same as GET /v1/overview) leaves the cases out: creators in short form with
    counters (`creatorCounts`), queue counters, sources, scans, `sourceHealth*`, trend, threshold, qualification and
    the recompute state. `compact=1` keeps the cases but drops their heavy fields."""
    chosen=wanted_schema(request,schema)
    jobs.recover_recompute()
    return {**store.state(chosen,bool(compact) if isinstance(compact,(bool,int)) else False,bool(findings)),
            "calibration":state_calibration()}

@app.get("/v1/overview")
def overview(schema:int|None=Query(None,ge=1,le=2),request:Request=None):
    """The light state for the desk header and the sources view: no cases (see `GET /v1/state?findings=0`)."""
    return state(schema,0,0,request)

@app.get("/v1/trend")
def trend(days:int=Query(30,ge=1,le=365)):
    with store.connection() as db:
        return store.trend(db,days)

@app.api_route("/v1/frames/{video}/{name}",methods=["GET","HEAD"])
def frame(video:str,name:str):
    """Read-only frame thumbnail: only a JPEG that the stored case lists (by video id and file name), from the media
    folders of the state or of the replay pack. Nothing else on disk is reachable."""
    from . import enrich,replay_pack
    with store.connection() as db:
        path=store.frame_file(db,video,name,[replay_pack.pack_dir(),enrich.cache_dir()])
    if path is None:
        raise HTTPException(404,"Nie ma takiego kadru.")
    return FileResponse(path,media_type="image/jpeg",headers={"Cache-Control":"private, max-age=86400"})

@app.get("/v1/report")
def report(module:Literal["M1","M2","M3"]=Query(...),format:Literal["json","csv"]="json",limit:int=Query(500,ge=1,le=5000),
           cursor:str|None=None,queue:str|None=None,platform:str|None=None,since:str|None=None,until:str|None=None,
           minScore:float|None=None,band:str|None=None,route:str|None=None,q:str|None=None,
           dateField:Literal["observedAt","publishedAt"]="observedAt"):
    """Report of one module: firm and entity type, advertiser or author, content, URL, platform, dates, route, signal
    strength, decision status. CSV is UTF-8 with a BOM and neutralises formulas; `cursor`/`limit` page it
    (X-Next-Cursor, X-Total-Count)."""
    if queue is not None and queue not in store.QUEUES:
        raise HTTPException(404,"Nie ma takiej kolejki.")
    with store.connection() as db:
        out=store.report_list(db,module,queue=queue,limit=limit,cursor=cursor,platform=platform,since=since,until=until,
                              min_score=minScore,band=band,route=route,q=q,date_field=dateField)
    if format=="json":
        return out
    headers={"Content-Disposition":f'attachment; filename="investwatch-raport-{module}.csv"',"X-Total-Count":str(out["total"]),
             "Cache-Control":"private, no-store"}
    if out["nextCursor"]:
        headers["X-Next-Cursor"]=out["nextCursor"]
    return Response(store.report_csv(out).encode("utf-8"),media_type="text/csv; charset=utf-8",headers=headers)

@app.get("/v1/queues/{name}")
def queue(name:str,limit:int=Query(50,ge=1,le=500),cursor:str|None=None,module:str|None=None,creator:str|None=None,
          since:str|None=None,until:str|None=None,minScore:float|None=None,q:str|None=None,section:str|None=None,
          platform:str|None=None,band:str|None=None,route:str|None=None,
          dateField:Literal["observedAt","publishedAt"]="observedAt"):
    if name not in store.QUEUES:
        raise HTTPException(404,"Nie ma takiej kolejki.")
    with store.connection() as db:
        return store.queue_list(db,name,limit=limit,cursor=cursor,module=module,creator=creator,since=since,until=until,
                                min_score=minScore,q=q,section=section,platform=platform,band=band,route=route,
                                date_field=dateField)

@app.post("/v1/scans",status_code=202)
def scan(body:ScanRequest):
    try:
        if body.mode in ("recompute","enrich"):
            return jobs.submit(body.mode,body.requestId)
        return jobs.submit(body.mode,body.requestId,{"adapters":body.adapters} if body.adapters else None)
    except ValueError as e:
        raise HTTPException(409,str(e)) from e

def settings_error(error):
    if isinstance(error,store.Conflict):
        raise HTTPException(409,str(error)) from error
    raise HTTPException(422,str(error)) from error

def recompute_for(entry):
    import hashlib
    key=hashlib.sha256(f"{entry['variant']}|{entry.get('rulesVersion')}|{entry.get('modelId')}".encode()).hexdigest()[:12]
    try:
        scan=jobs.submit("recompute",f"recompute-{entry['id']}-{key}")
    except ValueError:
        return
    # Without a worker a queued recompute would wait forever: a small database is recomputed inside the request,
    # a large one stays queued and /v1/state.recompute says that it is waiting for the worker.
    if scan.get("status")=="queued" and jobs.small_enough_for_inline():
        jobs.run_inline(scan["id"])

@app.get("/v1/threshold")
def threshold(variant:str|None=None):
    with store.connection() as db:
        return store.threshold_current(db,variant or store.active_variant(db))

@app.get("/v1/threshold/history")
def threshold_history(variant:str|None=None):
    with store.connection() as db:
        return {"items":store.threshold_history(db,variant or store.active_variant(db))}

@app.put("/v1/threshold")
def threshold_put(body:ThresholdBody):
    try:
        with store.connection(True) as db:
            return store.set_threshold(db,body.variant or store.active_variant(db),body.value,body.note,body.expectedId)
    except (store.Conflict,store.Invalid) as error:
        settings_error(error)

@app.post("/v1/threshold/restore")
def threshold_restore(body:RestoreBody):
    try:
        with store.connection(True) as db:
            return store.restore_threshold(db,body.id,body.expectedId,body.note)
    except (store.Conflict,store.Invalid) as error:
        settings_error(error)

@app.get("/v1/qualification")
def qualification():
    with store.connection() as db:
        return store.qualification_current(db)

@app.get("/v1/qualification/history")
def qualification_history():
    with store.connection() as db:
        return {"items":store.qualification_history(db)}

@app.put("/v1/qualification")
def qualification_put(body:QualificationBody):
    try:
        with store.connection(True) as db:
            entry,_=store.set_qualification(db,body.variant,body.expectedId,body.note,body.validationRef,body.approvedBy)
    except (store.Conflict,store.Invalid) as error:
        settings_error(error)
    recompute_for(entry)
    return entry

@app.post("/v1/qualification/restore")
def qualification_restore(body:RestoreBody):
    try:
        with store.connection(True) as db:
            entry,_=store.restore_qualification(db,body.id,body.expectedId,body.note)
    except (store.Conflict,store.Invalid) as error:
        settings_error(error)
    recompute_for(entry)
    return entry

@app.post("/v1/evidence")
def evidence(body:EvidenceBody):
    """A transcript supplied by the analyst: a new evidence version; origin and decisions stay as they were."""
    import hashlib
    if not (body.text or body.segments):
        raise HTTPException(422,"Podaj tekst lub segmenty transkrypcji.")
    with store.connection(True) as db:
        row=get_case(db,body.caseId)
        require_revision(row,body.expectedRevision,db)
        data=json.loads(row["body"])
        last=db.execute("SELECT capture,finding FROM versions WHERE id=? AND version=?",(body.caseId,data["version"])).fetchone()
        capture={k:v for k,v in json.loads(last["capture"]).items() if k not in ("discovery","reach")}
        base={"method":"analyst","windowId":"analyst","modality":"speech","language":"pl"}
        segments=[{**base,**seg,"method":"analyst"} for seg in (body.segments or [])] or \
                 [{**base,"start":0,"end":None,"text":body.text.strip()}]
        capture.update(segments=segments,mediaVersion=hashlib.sha256(store.dump(segments).encode()).hexdigest(),
                       mediaCoverage={"transcript":{"state":"full","source":"analyst","windows":[{"start":0,"end":None}],
                                                    "durationSec":None,"reason":None},
                                      "frames":{"state":"not_collected","moments":[],"intervalSec":None}})
        _,finding=jobs.evaluate(capture,json.loads(last["finding"]))
        result=store.apply_scan(db,[(capture,finding)],[],[],data.get("mode") or "live")
        if not result["changedFindings"]:
            raise HTTPException(409,"Transkrypcja nie zmienia materiału.")
        store.record(db,body.caseId,"evidence",body.note or "Transkrypcja dostarczona przez analityka",{"source":"analyst"})
        store.event(db,"case",body.caseId,"Dodano transkrypcję analityka")
        return store.case_dict(db,get_case(db,body.caseId))

@app.get("/v1/scans/{scan_id}")
def scan_status(scan_id:str):
    with store.connection() as db:
        detail=store.scan_detail(db,scan_id)
    if detail is None:
        raise HTTPException(404,"Nie znaleziono skanu.")
    return detail

def get_case(db,key):
    row=db.execute("SELECT * FROM cases WHERE id=?",(key,)).fetchone()
    if row is None:
        raise HTTPException(404,"Nie znaleziono sprawy.")
    return row

class StaleCase(HTTPException):
    def __init__(self,message,current):
        super().__init__(409,message)
        self.current=current

@app.exception_handler(StaleCase)
async def stale_case(request,error):
    from starlette.responses import JSONResponse
    return JSONResponse({"detail":error.detail,"current":error.current},status_code=409)

def current_of(db,row):
    return {"revision":row["revision"],"status":row["status"],"version":json.loads(row["body"]).get("version")}

def require_revision(row,expected,db=None):
    if expected is not None and expected!=row["revision"]:
        raise StaleCase("Sprawa została zmieniona. Odśwież ją przed zapisem.",current_of(db,row))

@app.get("/v1/cases/{key:path}/versions/{version}")
def case_version(key:str,version:int):
    with store.connection() as db:
        row=db.execute("SELECT * FROM versions WHERE id=? AND version=?",(key,version)).fetchone()
        if not row:
            raise HTTPException(404,"Brak tej wersji.")
        return {"observedAt":row["observed"],"sha256":row["signature"],"version":version,
                "capture":json.loads(row["capture"]),"finding":json.loads(row["finding"])}

@app.get("/v1/cases/{key:path}/versions")
def case_versions(key:str):
    with store.connection() as db:
        get_case(db,key)
        return {"versions":store.version_list(db,key)}

@app.get("/v1/cases/{key:path}/reach")
def case_reach(key:str):
    with store.connection() as db:
        get_case(db,key)
        samples=store.reach_series(db,key)
        return {"samples":samples,"latest":store.latest_reach(samples)}

@app.get("/v1/cases/{key:path}")
def case(key:str,schema:int|None=Query(None,ge=1,le=2),request:Request=None):
    with store.connection() as db:
        return store.case_dict(db,get_case(db,key),schema=wanted_schema(request,schema))

@app.patch("/v1/cases/{key:path}")
def decision(key:str,body:Decision,request:Request=None):
    status=body.status or RESOLUTION_STATUS.get(body.resolution)
    if status is None:
        raise HTTPException(422,"Podaj status lub rodzaj decyzji (resolution).")
    with store.connection(True) as db:
        row=get_case(db,key)
        require_revision(row,body.expectedRevision,db)
        version=json.loads(row["body"]).get("version")
        if body.reviewedVersion is not None and body.reviewedVersion!=version:
            raise StaleCase("Materiał ma nowszą wersję niż oglądana. Odśwież sprawę przed decyzją.",current_of(db,row))
        if not body.note.strip():
            raise HTTPException(422,"Wpisz uzasadnienie decyzji.")
        route=store.case_dict(db,row,full=False).get("route")
        db.execute("UPDATE cases SET status=?,revision=revision+1,updated=? WHERE id=?",(status,store.utc(),key))
        details={"status":status,"version":version,"revision":row["revision"]+1,"route":route,"analysisSig":row["fingerprint"]}
        if body.resolution:
            details["resolution"]=body.resolution
        store.record(db,key,"decision",body.note.strip(),details)
        store.event(db,"case",key,"Zapisano decyzję analityka")
        return store.case_dict(db,get_case(db,key),schema=wanted_schema(request))

@app.post("/v1/cases/{key:path}/inquiry")
def inquiry(key:str,body:Inquiry):
    with store.connection(True) as db:
        row=get_case(db,key)
        require_revision(row,body.expectedRevision,db)
        data=json.loads(row["body"])
        if not data.get("contractDemo"):
            raise HTTPException(422,"Korespondencja demonstracyjna jest dostępna w fikcyjnej sprawie.")
        steps=store.history(db,key)
        previous=next((s for s in reversed(steps) if s["action"]=="inquiry"),{})
        allowed={None:{"draft"},"draft":{"draft","waiting"},"waiting":{"denied","confirmed","documents"},
                 "confirmed":{"documents"},"denied":{"draft"},"documents":{"documents","draft"}}
        if body.action not in allowed.get(previous.get("stage"),set()):
            raise HTTPException(409,"Wybierz kolejny etap po przygotowaniu pytania.")
        draft=(f'Czy firma rozpoznaje twórcę materiału „{data["title"]}” ({data["url"]}) i czy '
               'publikacja była przedmiotem umowy? Prosimy wskazać okres, kanał, wymagane oznaczenie i ewentualne aneksy.')
        messages={"draft":"Przygotowano szkic pytania","waiting":"Oczekujemy na odpowiedź (symulacja)",
                  "denied":"Firma zaprzecza współpracy (symulacja)","confirmed":"Potwierdzenie współpracy bez warunków (symulacja)",
                  "documents":"Dołączono warunki współpracy (symulacja)"}
        result={"stage":body.action,"text":draft,"reply":body.note}
        store.record(db,key,"inquiry",messages[body.action],result)
        db.execute("UPDATE cases SET revision=revision+1,updated=? WHERE id=?",(store.utc(),key))
        store.event(db,"case",key,messages[body.action])
        return {**result,"revision":row["revision"]+1}

@app.post("/v1/cases/{key:path}/contract")
def contract(key:str,body:Contract):
    with store.connection(True) as db:
        row=get_case(db,key)
        require_revision(row,body.expectedRevision,db)
        data=json.loads(row["body"])
        if not data.get("contractDemo"):
            raise HTTPException(422,"Porównanie jest dostępne w fikcyjnej sprawie z dokumentem.")
        published=date.fromisoformat(data["publishedAt"][:10])
        aligned=published<=body.endDate
        details={"endDate":str(body.endDate),"label":body.label,"publishedAt":str(published),
                 "aligned":aligned,"result":"Data mieści się w okresie umowy" if aligned else "Publikacja po zakończeniu okresu umowy"}
        comparisons=[{"field":"Okres publikacji","state":"zgodne" if aligned else "rozbieżność","note":details["result"]}]
        if body.channel.strip():
            channel=data.get("platform","").casefold()
            equal=body.channel.strip().casefold()==channel
            comparisons.append({"field":"Kanał","state":"zgodne" if equal else "do wyjaśnienia",
                                "note":f'W dokumencie: {body.channel}. W materiale: {data.get("platform") or "brak danych"}.'})
        if body.requiredLabel.strip():
            present=body.requiredLabel.strip().casefold() in data.get("description","").casefold()
            comparisons.append({"field":"Wymagane oznaczenie","state":"widoczne w opisie" if present else "do wyjaśnienia",
                                "note":f'Sprawdzono opis pod kątem „{body.requiredLabel}”. Obraz i inne miejsca publikacji wymagają własnego dowodu.'})
        details["comparisons"]=comparisons
        db.execute("UPDATE cases SET revision=revision+1,updated=? WHERE id=?",(store.utc(),key))
        store.record(db,key,"contract",details["result"],details)
        store.event(db,"case",key,"Porównano okres obowiązywania umowy")
        return {**details,"revision":row["revision"]+1}

@app.post("/v1/media",status_code=202)
async def upload(request:Request,title:str=Query(min_length=1,max_length=180),
                 description:str=Query("",max_length=5000),filename:str=Query("nagranie.mp4",max_length=300)):
    limit=40*1024*1024
    ext=Path(filename).suffix.lower()
    if ext not in {".mp4",".wav",".mp3",".m4a",".webm",".ogg",".mov",".mkv",".aac",".flac"}:
        raise HTTPException(415,"Wybierz obsługiwany plik audio lub wideo.")
    folder=store.STATE/"uploads"
    folder.mkdir(parents=True,exist_ok=True,mode=0o700)
    digest=sha256()
    count=0
    with tempfile.NamedTemporaryFile(dir=folder,suffix=".part",delete=False) as out:
        temp=Path(out.name)
    try:
        with temp.open("wb") as out:
            async for chunk in request.stream():
                count+=len(chunk)
                if count>limit:
                    raise HTTPException(413,"Limit lokalnego nagrania wynosi 40 MiB.")
                digest.update(chunk)
                out.write(chunk)
        if not count:
            raise HTTPException(422,"Przesłany plik jest pusty.")
        name=digest.hexdigest()+ext
        temp.replace(folder/name)
        payload={"title":title,"description":description,"file":name,"sha256":digest.hexdigest()}
        request_id="upload-"+sha256(store.dump(payload).encode()).hexdigest()
        return jobs.submit("upload",request_id,payload)
    finally:
        temp.unlink(missing_ok=True)

@app.websocket("/v1/events")
async def events(ws:WebSocket):
    if not origin_ok(ws.headers.get("origin"),ws.headers.get("host")):
        await ws.close(code=1008)
        return
    await ws.accept()
    try:
        cursor=int(ws.query_params.get("after","-1"))
    except ValueError:
        await ws.close(code=1008)
        return
    with store.connection() as db:
        newest=db.execute("SELECT coalesce(max(seq),0) FROM events").fetchone()[0]
    reset=cursor>newest
    if cursor<0 or reset:
        cursor=newest
    await ws.send_json({"kind":"ready","id":cursor})
    if reset:  # the client remembers an event that this database never had (restored or rebuilt state)
        await ws.send_json({"kind":"reset","id":newest})
    try:
        while True:
            with store.connection() as db:
                pending=store.events_since(db,cursor)
            for item in pending:
                await ws.send_json(item)
                cursor=item["id"]
            try:
                msg=await asyncio.wait_for(ws.receive(),timeout=.6)
                if msg["type"]=="websocket.disconnect":
                    return
            except asyncio.TimeoutError:
                pass
    except (WebSocketDisconnect,RuntimeError):
        return

@app.get("/uploads/{name}")
def uploaded_file(name:str):
    import re
    if not re.fullmatch(r"[a-f0-9]{64}\.[a-z0-9]{2,4}",name) or not (store.STATE/"uploads"/name).is_file():
        raise HTTPException(404)
    return FileResponse(store.STATE/"uploads"/name)

@app.api_route("/evidence/m2/{name}", methods=["GET", "HEAD"])
def m2_asset(name: str):
    from collectors.common import SourceError
    from collectors.m2_archive import ASSET_NAME, REPLAY, asset_bytes

    match = ASSET_NAME.fullmatch(name)
    if match is None:
        raise HTTPException(404)
    for root in (store.STATE / "m2", REPLAY):
        try:
            data = asset_bytes(root, name)
        except SourceError:
            continue
        media_type = "image/png" if match[2] == "png" else "application/json"
        return Response(data, media_type=media_type, headers={
            "ETag": f'"{match[1]}"', "Cache-Control": "private, max-age=31536000, immutable",
        })
    raise HTTPException(404)


for route,folder in [("/evidence/browser",store.ROOT/"data/probe-snapshots/browser"),("/media",store.ROOT/"analysis/media")]:
    app.mount(route,StaticFiles(directory=folder,check_dir=False),name=route)
web=store.ROOT/"web"
app.mount("/",StaticFiles(directory=web/"dist" if (web/"dist/index.html").exists() else web,html=True,check_dir=False),name="desk")
