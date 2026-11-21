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
from starlette.responses import FileResponse
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
    mode:Literal["live","replay"]
    requestId:str=Field(min_length=1,max_length=160)
    sourceId:Literal["all"]="all"

class Decision(BaseModel):
    status:Literal["new","reviewing","closed"]
    expectedRevision:int=Field(ge=1)
    note:str=Field(min_length=1,max_length=2000)

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

@app.get("/v1/health")
def health():
    with store.connection() as db:
        db.execute("SELECT 1").fetchone()
    return {"status":"ok"}

@app.get("/v1/calibration")
def calibration(threshold:int=Query(60,ge=0,le=100)):
    return calculate_cached(threshold)

@lru_cache(maxsize=101)
def calculate_cached(threshold):
    from analysis.engine import calibration as calculate
    return calculate(threshold)

@app.get("/v1/state")
def state():
    return {**store.state(),"calibration":calibration(60)}

@app.post("/v1/scans",status_code=202)
def scan(body:ScanRequest):
    try:
        return jobs.submit(body.mode,body.requestId)
    except ValueError as e:
        raise HTTPException(409,str(e)) from e

def get_case(db,key):
    row=db.execute("SELECT * FROM cases WHERE id=?",(key,)).fetchone()
    if row is None:
        raise HTTPException(404,"Nie znaleziono sprawy.")
    return row

def require_revision(row,expected):
    if expected is not None and expected!=row["revision"]:
        raise HTTPException(409,"Sprawa została zmieniona. Odśwież ją przed zapisem.")

@app.get("/v1/cases/{key}")
def case(key:str):
    with store.connection() as db:
        return store.case_dict(db,get_case(db,key))

@app.get("/v1/cases/{key}/versions/{version}")
def case_version(key:str,version:int):
    with store.connection() as db:
        row=db.execute("SELECT * FROM versions WHERE id=? AND version=?",(key,version)).fetchone()
        if not row:
            raise HTTPException(404,"Brak tej wersji.")
        return {"observedAt":row["observed"],"sha256":row["signature"],"version":version,
                "capture":json.loads(row["capture"]),"finding":json.loads(row["finding"])}

@app.patch("/v1/cases/{key}")
def decision(key:str,body:Decision):
    with store.connection(True) as db:
        row=get_case(db,key)
        require_revision(row,body.expectedRevision)
        if not body.note.strip():
            raise HTTPException(422,"Wpisz uzasadnienie decyzji.")
        db.execute("UPDATE cases SET status=?,revision=revision+1,updated=? WHERE id=?",(body.status,store.utc(),key))
        store.record(db,key,"decision",body.note.strip(),{"status":body.status})
        store.event(db,"case",key,"Zapisano decyzję analityka")
        return store.case_dict(db,get_case(db,key))

@app.post("/v1/cases/{key}/inquiry")
def inquiry(key:str,body:Inquiry):
    with store.connection(True) as db:
        row=get_case(db,key)
        require_revision(row,body.expectedRevision)
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

@app.post("/v1/cases/{key}/contract")
def contract(key:str,body:Contract):
    with store.connection(True) as db:
        row=get_case(db,key)
        require_revision(row,body.expectedRevision)
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
    if cursor<0:
        with store.connection() as db:
            cursor=db.execute("SELECT coalesce(max(seq),0) FROM events").fetchone()[0]
    await ws.send_json({"kind":"ready","id":cursor})
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

for route,folder in [("/evidence/browser",store.ROOT/"data/probe-snapshots/browser"),("/media",store.ROOT/"analysis/media")]:
    app.mount(route,StaticFiles(directory=folder,check_dir=False),name=route)
web=store.ROOT/"web"
app.mount("/",StaticFiles(directory=web/"dist" if (web/"dist/index.html").exists() else web,html=True,check_dir=False),name="desk")
