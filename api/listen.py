"""Sample the opening of a bounded number of public podcast enclosures per scan."""
from hashlib import sha256
import json
import logging
from pathlib import Path
import subprocess
import tempfile
import time

from . import store

SECONDS = 45
MAX_ATTEMPTS = 3
RETRY_AFTER = 6 * 3600
logger = logging.getLogger(__name__)

def sample_one(capture):
    from analysis.transcribe import transcribe_excerpt
    from collectors.audio import fetch_excerpt
    uploads = store.STATE / "uploads"
    uploads.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=uploads) as tmp:
        source = Path(tmp) / "prefix.mp3"
        if not fetch_excerpt(capture, source):
            raise ValueError("Nie udało się odczytać publicznego początku nagrania.")
        clip = Path(tmp) / "clip.mp3"
        proc = subprocess.run(
            ["ffmpeg","-nostdin","-loglevel","error","-protocol_whitelist","file,pipe",
             "-f","mp3","-i",str(source),"-map","0:a:0","-t",str(SECONDS),"-c:a","copy","-map_metadata","-1",str(clip)],
            timeout=30, capture_output=True)
        if proc.returncode or not clip.is_file() or clip.stat().st_size == 0:
            raise ValueError("Dekoder nie odczytał początku pliku MP3.")
        segments = transcribe_excerpt(clip, SECONDS)
        sample_hash = sha256(clip.read_bytes()).hexdigest()
        name = sample_hash + ".mp3"
        clip.replace(uploads / name)
    return {"segments":segments, "mediaUrl":"/uploads/"+name, "sampleSha256":sample_hash,
            "coverage":"Początek audycji, maksymalnie 45 s · lokalny ASR PL",
            "asrScope":{"start":0,"maxSeconds":SECONDS,"sourceUrl":capture["audioUrl"]}}

def sample_audio(captures):
    completed = attempts = reused = 0
    problems = []
    for cap in captures:
        if not cap.get("audioExcerptAvailable") or not cap.get("audioUrl"):
            continue
        fingerprint=sha256(store.dump([cap["id"],cap["audioUrl"]]).encode()).hexdigest()
        with store.connection() as db:
            previous=db.execute("SELECT * FROM audio_cache WHERE fingerprint=?",(fingerprint,)).fetchone()
        if previous and previous["result"]:
            cap.update(json.loads(previous["result"]))
            reused+=1
            continue
        if attempts>=MAX_ATTEMPTS or completed or (previous and previous["retry_at"]>time.time()):
            continue
        attempts+=1
        try:
            extra=sample_one(cap)
        except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
            logger.info("Skipped enclosure %s: %s",cap["id"],exc)
            problems.append(str(exc)[:200])
            with store.connection(True) as db:
                db.execute("INSERT OR REPLACE INTO audio_cache VALUES(?,?,?)",(fingerprint,None,time.time()+RETRY_AFTER))
        else:
            with store.connection(True) as db:
                db.execute("INSERT OR REPLACE INTO audio_cache VALUES(?,?,0)",(fingerprint,store.dump(extra)))
            cap.update(extra)
            completed+=1
    status="ok" if completed or reused else ("partial" if problems else "empty")
    return {"id":"local-public-asr","name":"Odsłuch nowych podcastów · pierwsze 45 s","status":status,
            "count":completed+reused,"newSamples":completed,"reused":reused,"attempts":attempts,
            "scope":"Do jednego nowego wycinka na skan. Reszta audycji poza zakresem.",
            **({"error":" · ".join(problems)} if problems else {})}
