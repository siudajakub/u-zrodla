"""Media adapter for public YouTube videos: captions, optional frames, coverage.

Decision of the product owner (21 Nov 2026): transcript and frames of public
videos may be fetched for the demo. Cheapest route first:

1. author or automatic Polish captions (yt-dlp ``--skip-download``, no media);
2. only without captions and on explicit request: the first <=120 s of the lowest
   quality audio plus the local Vosk model (heavy: one at a time);
3. unavailable (private, removed, age limit, rate limit, login wall): a status and
   a reason, never an exception.

Frames never need the whole film: the default route reads one public storyboard
sheet (about 17 kB for nine 320x180 tiles); the escalation route seeks with ffmpeg
inside the 360p stream (about 150 kB per frame). No cookies, no login, no
circumvention: when YouTube asks for a login the route stops with its message.

``enrich(capture, ctx)`` returns segments, frames, ``mediaCoverage`` (H contract)
and ``coverage`` (modalities, gaps). Everything is cached under
``.runtime/media-cache/<videoId>/`` and a repeat call makes no request.
"""

from datetime import datetime, timezone
from hashlib import sha256
from html import unescape
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / ".runtime" / "media-cache"
YTDLP = ROOT / ".runtime" / "venv" / "bin" / "yt-dlp"
MIN_GAP = 2.0  # seconds between two network requests
MAX_SECONDS = 120.0  # wall-clock budget per video
ASR_SECONDS = 120  # limit of analysis.transcribe
SB_MAX_INTERVAL = 5.0  # auto: storyboard only when tiles are at most this far apart
SOURCE = "youtube-captions-v1"
ID_RE = re.compile(r"[A-Za-z0-9_-]{11}")
TERMINAL = {"private", "unavailable", "age_restricted", "members_only"}

PROMO_PATTERNS = {
    "reklama": r"reklam\w*",
    "wspolpraca": r"wsp[oó]łprac\w*|wspolprac\w*",
    "partner": r"partner\w*",
    "sponsor": r"sponsor\w*",
    "link_w_opisie": r"link\w*\s+(?:w|pod)\s+opis\w*|w\s+opisie",
    "kod": r"\bkod(?:em|u|y|zie)?\b",
    "promocja": r"promocj\w*|oferta\s+specjaln\w*",
    "broker": (r"\bxtb\b|\bx\s*t\s*b\b|freedom\s*24|freedom\s*finance|etoro|trading\s*212|revolut|"
               r"dm\s+bo[sś]|\bbossa\b|saxo|exante|interactive\s+brokers|degiro|scalable"),
}


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def video_id(value):
    """Return the 11-character id from an id, watch/shorts/embed/youtu.be URL, or None."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    if ID_RE.fullmatch(value):
        return value
    try:
        url = urlsplit(value)
    except ValueError:
        return None
    host = (url.hostname or "").lower()
    if host == "youtu.be":
        candidate = url.path.strip("/").split("/")[0]
    elif host in {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}:
        parts = [p for p in url.path.split("/") if p]
        if url.path == "/watch":
            candidate = (parse_qs(url.query).get("v") or [""])[0]
        elif len(parts) == 2 and parts[0] in {"shorts", "embed", "live", "v"}:
            candidate = parts[1]
        else:
            return None
    else:
        return None
    return candidate if ID_RE.fullmatch(candidate) else None


def deep_link(vid, seconds=0):
    return f"https://www.youtube.com/watch?v={vid}&t={max(0, int(seconds))}s"


def digest(value):
    return sha256(value.encode() if isinstance(value, str) else value).hexdigest()


# ---------------------------------------------------------------- captions

_CUE = re.compile(r"^(?:(\d+):)?(\d{2}):(\d{2})[.,](\d{3})\s+-->\s+(?:(\d+):)?(\d{2}):(\d{2})[.,](\d{3})")
_TAG = re.compile(r"<[^>]*>")


def _seconds(h, m, s, ms):
    return int(h or 0) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def parse_vtt(text, *, rolling=False):
    """Parse WebVTT into [{start,end,text}].

    With ``rolling`` (YouTube automatic captions repeat the previous line in every cue
    and add 10 ms transition cues) only lines that were not visible in the previous
    cue are kept, so every spoken word appears exactly once.
    """
    cues = []
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    i = 0
    while i < len(lines):
        match = _CUE.match(lines[i].strip())
        i += 1
        if not match:
            continue
        g = match.groups()
        start, end = _seconds(*g[0:4]), _seconds(*g[4:8])
        body = []
        while i < len(lines) and lines[i] != "":  # a whitespace-only line is still part of the cue
            cleaned = " ".join(unescape(_TAG.sub("", lines[i])).split())
            if cleaned:
                body.append(cleaned)
            i += 1
        cues.append((start, end, body))
    segments = []
    previous = []
    for start, end, body in cues:
        if rolling and end - start < 0.1:
            previous = body or previous
            continue
        fresh = [line for line in body if line not in previous] if rolling else body
        if body:
            previous = body
        if not fresh:
            continue
        segments.append({"start": round(start, 3), "end": round(end, 3), "text": " ".join(fresh)})
    if rolling:  # a later cue may repeat the very same text again with a new window
        merged = []
        for segment in segments:
            if merged and merged[-1]["text"] == segment["text"] and segment["start"] <= merged[-1]["end"] + 0.05:
                merged[-1]["end"] = segment["end"]
            else:
                merged.append(segment)
        segments = merged
    return segments


# ---------------------------------------------------------------- markers

def find_markers(segments, description="", *, context=0):
    """Locate promotion or disclosure cues in segments. Matches are lexical hints only."""
    found = []
    for index, segment in enumerate(segments):
        text = segment.get("text", "")
        kinds = [name for name, pattern in PROMO_PATTERNS.items() if re.search(pattern, text, re.I)]
        if kinds:
            quote = text
            if context:
                around = segments[max(0, index - context):index + context + 1]
                quote = " ".join(item["text"] for item in around)
            found.append({"modality": "transcript", "start": segment["start"], "end": segment["end"],
                          "kinds": kinds, "quote": quote[:300], "method": segment.get("method"),
                          "deepLink": segment.get("deepLink")})
    for line in description.splitlines():
        kinds = [name for name, pattern in PROMO_PATTERNS.items() if re.search(pattern, line, re.I)]
        if kinds:
            found.append({"modality": "description", "start": None, "end": None, "kinds": kinds,
                          "quote": line.strip()[:300]})
    return found


# ---------------------------------------------------------------- transport

def classify_error(stderr, returncode=1):
    """Map yt-dlp stderr to (status, reason). Terminal statuses may be cached."""
    text = stderr or ""
    low = text.lower()
    line = next((x for x in reversed(text.splitlines()) if "ERROR" in x), text.strip().splitlines()[-1:] or [""])
    message = (line if isinstance(line, str) else line[0]).strip()[:240]
    rules = (
        ("private", ("private video",)),
        ("members_only", ("members-only", "join this channel", "members only")),
        ("age_restricted", ("confirm your age", "age-restricted", "inappropriate for some users")),
        ("login_required", ("sign in to confirm", "not a bot", "login required", "cookies-from-browser")),
        ("rate_limited", ("http error 429", "too many requests", "rate-limit", "rate limit")),
        ("unavailable", ("video unavailable", "has been removed", "no longer available", "does not exist",
                         "account associated", "copyright", "not available in your country", "blocked it")),
    )
    for status, needles in rules:
        if any(needle in low for needle in needles):
            return status, message
    return "error", message or f"yt-dlp zakończył się kodem {returncode}"


class Client:
    """Network access with spacing between requests, a deadline and a request/byte ledger."""

    def __init__(self, *, run=None, fetch=None, sleep=time.sleep, clock=time.monotonic,
                 ytdlp=None, min_gap=MIN_GAP, max_seconds=MAX_SECONDS):
        self.run, self.fetch = run or self._run, fetch or self._fetch
        self.sleep, self.clock, self.min_gap = sleep, clock, min_gap
        self.ytdlp = str(ytdlp or os.environ.get("INVESTWATCH_YTDLP") or
                         (YTDLP if YTDLP.exists() else shutil.which("yt-dlp") or YTDLP))
        self.started = clock()
        self.deadline = self.started + max_seconds
        self.requests = 0
        self.bytes = 0
        _STATE.setdefault("last", None)

    def remaining(self):
        return self.deadline - self.clock()

    def gap(self):
        last = _STATE["last"]
        if last is not None:
            wait = self.min_gap - (self.clock() - last)
            if wait > 0:
                self.sleep(wait)
        _STATE["last"] = self.clock()
        self.requests += 1

    def command(self, args, timeout=None):
        """Run one yt-dlp/ffmpeg command: (returncode, stdout, stderr); timeout gives (124, '', 'timeout')."""
        left = self.remaining()
        if left <= 0:
            return 124, "", "timeout: limit czasu na film"
        self.gap()
        return self.run(args, min(timeout or left, left))

    def download(self, url, timeout=20):
        left = self.remaining()
        if left <= 0:
            raise TimeoutError("limit czasu na film")
        self.gap()
        body = self.fetch(url, min(timeout, left))
        self.bytes += len(body)
        return body

    @staticmethod
    def _run(args, timeout):
        try:
            done = subprocess.run(args, capture_output=True, timeout=timeout, text=True, errors="replace")
        except subprocess.TimeoutExpired:
            return 124, "", "timeout"
        except OSError as exc:
            return 127, "", f"ERROR: {exc.strerror or exc}"
        return done.returncode, done.stdout, done.stderr

    @staticmethod
    def _fetch(url, timeout):
        host = urlsplit(url).hostname or ""
        if urlsplit(url).scheme != "https" or not (host.endswith(".ytimg.com") or host.endswith(".ggpht.com")):
            raise ValueError("Domena spoza listy miniatur YouTube.")
        request = Request(url, headers={"User-Agent": "InvestWatch-MediaProbe/1.0"})
        with urlopen(request, timeout=timeout) as response:
            return response.read(4 * 1024 * 1024)


_STATE = {"last": None}


# ---------------------------------------------------------------- cache

def _read_json(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None


def _write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    staged = path.with_name(path.name + ".tmp")
    staged.write_text(json.dumps(value, ensure_ascii=False, indent=1))
    os.replace(staged, path)


def _trim_info(info, version):
    boards = []
    for item in info.get("formats") or []:
        if item.get("format_note") == "storyboard" and item.get("fragments"):
            boards.append({"id": item["format_id"], "width": item.get("width"), "height": item.get("height"),
                           "rows": item.get("rows"), "columns": item.get("columns"),
                           "fragments": [{"url": f["url"], "duration": f.get("duration")} for f in item["fragments"]]})
    return {
        "videoId": info.get("id"), "title": info.get("title"), "duration": info.get("duration"),
        "channel": info.get("channel") or info.get("uploader"), "uploadDate": info.get("upload_date"),
        "language": info.get("language"), "availability": info.get("availability"),
        "ageLimit": info.get("age_limit"), "liveStatus": info.get("live_status"),
        "description": info.get("description") or "",
        "subtitles": sorted((info.get("subtitles") or {}).keys()),
        "automaticCaptions": sorted(k for k in (info.get("automatic_captions") or {}) if k.startswith("pl")),
        "storyboards": boards, "fetchedAt": now_iso(), "ytDlpVersion": version, "status": "ok",
    }


def load_meta(vid, client, cache, *, refresh=False):
    """Return (meta, error). One yt-dlp extraction yields metadata, caption files and storyboards."""
    folder = cache / vid
    meta = _read_json(folder / "meta.json")
    if meta and not refresh and (meta.get("status") in TERMINAL or meta.get("status") == "ok"):
        return meta, None
    raw = folder / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    code, out, err = client.command([
        client.ytdlp, "--skip-download", "--write-subs", "--write-auto-subs", "--sub-langs", "pl.*",
        "--sub-format", "vtt", "--write-info-json", "--no-playlist", "--no-warnings", "--socket-timeout", "15",
        "--retries", "1", "-o", str(raw / "%(id)s"), f"https://www.youtube.com/watch?v={vid}"], 60)
    info = _read_json(raw / f"{vid}.info.json")
    if code != 0 or info is None:
        status, reason = classify_error(err, code)
        if code == 124:
            status, reason = "timeout", "Przekroczony limit czasu na film."
        if status in TERMINAL:
            _write_json(folder / "meta.json", {"videoId": vid, "status": status, "reason": reason, "fetchedAt": now_iso()})
        return None, {"status": status, "reason": reason}
    client.bytes += sum(p.stat().st_size for p in raw.glob(f"{vid}.*.vtt"))  # caption files; extractor traffic not counted
    version = None
    try:
        code, out, _ = client.run([client.ytdlp, "--version"], 10)
        version = out.strip() if code == 0 else None
    except Exception:  # version is informational only
        pass
    meta = _trim_info(info, version)
    (raw / f"{vid}.info.json").unlink(missing_ok=True)
    _write_json(folder / "meta.json", meta)
    return meta, None


# ---------------------------------------------------------------- transcripts

def _failure_coverage(status, reason, duration=None):
    return {"transcript": {"state": "unavailable", "source": "none", "windows": [], "durationSec": duration,
                           "reason": f"{status}: {reason}"},
            "frames": {"state": "not_collected", "moments": [], "intervalSec": None}}


def captions(vid, meta, cache, *, now=None):
    """Segments from cached caption files of one extraction. Manual captions beat automatic ones."""
    raw = cache / vid / "raw"
    manual = [x for x in meta.get("subtitles", []) if x.startswith("pl")]
    auto = sorted(meta.get("automaticCaptions", []), key=lambda x: (not x.endswith("-orig"), x))
    for lang, kind in [(x, "author_captions") for x in manual] + [(x, "auto_captions") for x in auto]:
        path = raw / f"{vid}.{lang}.vtt"
        if not path.is_file():
            continue
        text = path.read_text(errors="replace")
        segments = parse_vtt(text, rolling=kind == "auto_captions")
        if not segments:
            continue
        translated = kind == "auto_captions" and not lang.endswith("-orig") and (meta.get("language") or "pl")[:2] != "pl"
        language = "pl"
        for number, segment in enumerate(segments):
            segment.update({"modality": "speech", "method": kind, "language": language,
                            "lang": language, "windowId": "w0", "deepLink": deep_link(vid, segment["start"])})
        return {"method": kind, "track": lang, "segments": segments, "captionsSha256": digest(text),
                "translated": translated}
    return None


def _jpeg_size(data):
    i = 2
    while i + 9 < len(data) and data[0:2] == b"\xff\xd8":
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            return int.from_bytes(data[i + 7:i + 9], "big"), int.from_bytes(data[i + 5:i + 7], "big")
        i += 2 + int.from_bytes(data[i + 2:i + 4], "big")
    return None, None


def asr_audio(vid, meta, client, cache, asr):
    """Heavy route: first <=120 s of the lowest-quality audio, then local Vosk. One run at a time."""
    import fcntl
    duration = meta.get("duration") or 0
    seconds = int(min(ASR_SECONDS, duration or ASR_SECONDS))
    folder = cache / vid
    lock = (cache / ".heavy.lock").open("w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return None, {"status": "busy", "reason": "Inny ciężki przebieg (ASR) już trwa."}
    try:
        for old in folder.glob("audio.*"):
            old.unlink()
        code, out, err = client.command([
            client.ytdlp, "-f", "worstaudio[ext=m4a]/worstaudio", "--download-sections", f"*0-{seconds}",
            "--no-playlist", "--no-warnings", "--socket-timeout", "15", "--retries", "1",
            "-o", str(folder / "audio.%(ext)s"), f"https://www.youtube.com/watch?v={vid}"], 120)
        files = sorted(folder.glob("audio.*"))
        if code != 0 or not files:
            status, reason = classify_error(err, code)
            return None, {"status": status, "reason": reason}
        audio = files[0]
        client.bytes += audio.stat().st_size
        began = time.monotonic()
        try:
            segments = asr(audio, seconds)
        except (RuntimeError, ValueError, OSError) as exc:
            return None, {"status": "asr_unavailable", "reason": str(exc)[:240]}
        elapsed = round(time.monotonic() - began, 2)
        for segment in segments:
            segment.update({"modality": "speech", "method": "asr", "language": "pl", "lang": "pl",
                            "windowId": "w0", "deepLink": deep_link(vid, segment["start"])})
        return {"method": "asr", "segments": segments, "seconds": seconds, "audioBytes": audio.stat().st_size,
                "asrSeconds": elapsed, "audioSha256": digest(audio.read_bytes())}, None
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()


# ---------------------------------------------------------------- frames

def _ffmpeg_crop(sheet, target, w, h, x, y):
    code, _, err = Client._run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(sheet), "-vf",
                                f"crop={w}:{h}:{x}:{y}", "-frames:v", "1", "-q:v", "2", str(target)], 30)
    return code == 0 and Path(target).is_file(), err


def _display_path(path):
    try:
        return str(Path(path).relative_to(ROOT))
    except ValueError:
        return str(path)


def _frame_record(vid, meta, path, requested, actual, method, bytes_fetched, version, extra=None):
    data = Path(path).read_bytes()
    width, height = _jpeg_size(data)
    link = deep_link(vid, actual)
    record = {"id": f"frame-{vid}-{int(actual)}-{method}", "kind": "frame", "modality": "frame", "method": method,
              "time": actual, "requestedTime": requested, "path": _display_path(path),
              "sha256": digest(data), "width": width, "height": height, "bytesFile": len(data),
              "bytesFetched": bytes_fetched, "deepLink": link, "sourceUrlAtTime": link, "url": link,
              "sourceVersion": version, "observedAt": now_iso(), "available": True}
    record.update(extra or {})
    return record


def storyboard_interval(meta):
    """Seconds between tiles of the largest storyboard, or None when the film has none."""
    boards = [b for b in meta.get("storyboards", []) if b.get("rows") and b.get("columns") and b.get("fragments")]
    if not boards:
        return None
    board = max(boards, key=lambda b: (b["width"] or 0))
    return (board["fragments"][0]["duration"] or 0) / (board["rows"] * board["columns"])


def storyboard_frames(vid, meta, times, client, cache, version):
    """Frames from the largest public storyboard: one sheet request serves up to nine frames."""
    boards = [b for b in meta.get("storyboards", []) if b.get("rows") and b.get("columns") and b.get("fragments")]
    if not boards:
        return [], {"status": "no_storyboard", "reason": "Film nie udostępnia storyboardów."}
    board = max(boards, key=lambda b: (b["width"] or 0))
    per = board["rows"] * board["columns"]
    full = board["fragments"][0]["duration"] or 0
    interval = full / per if per else 0
    frames, issues, seen = [], [], set()
    folder = cache / vid / "frames"
    folder.mkdir(parents=True, exist_ok=True)
    for requested in times:
        start, index = 0.0, None
        for number, fragment in enumerate(board["fragments"]):
            if requested < start + (fragment["duration"] or 0) or number == len(board["fragments"]) - 1:
                index = number
                break
            start += fragment["duration"] or 0
        tile = max(0, min(per - 1, round((requested - start) / interval))) if interval else 0
        tiles_here = max(1, math.ceil((board["fragments"][index]["duration"] or 0) / interval)) if interval else 1
        tile = min(tile, tiles_here - 1)
        actual = round(start + tile * interval, 2)
        method = f"storyboard_{board['width']}x{board['height']}"
        if (index, tile) in seen:  # the same tile already serves a nearer moment
            continue
        seen.add((index, tile))
        target = folder / f"{method}_{int(actual):06d}.jpg"
        fetched = 0
        if not target.is_file():
            sheet = folder / f"sheet_{board['id']}_{index}.jpg"
            if not sheet.is_file():
                try:
                    body = client.download(board["fragments"][index]["url"])
                except TimeoutError as exc:
                    issues.append({"time": requested, "status": "timeout", "reason": str(exc)})
                    continue
                except Exception as exc:  # network, 403 after URL expiry, bad host
                    issues.append({"time": requested, "status": "error", "reason": str(exc)[:200]})
                    continue
                sheet.write_bytes(body)
                fetched = len(body)
            ok, err = _ffmpeg_crop(sheet, target, board["width"], board["height"],
                                   (tile % board["columns"]) * board["width"], (tile // board["columns"]) * board["height"])
            if not ok:
                issues.append({"time": requested, "status": "error", "reason": f"ffmpeg: {err.strip()[:160]}"})
                continue
        frames.append(_frame_record(vid, meta, target, requested, actual, method, fetched, version,
                                    {"intervalSec": round(interval, 2)}))
    return frames, ({"status": "partial", "reason": "; ".join(f"{i['time']}s: {i['reason']}" for i in issues)} if issues else None)


def stream_frames(vid, meta, times, client, cache, version, height=360):
    """Escalation: ffmpeg range-seeks inside the stream, no full download (about 150 kB per frame)."""
    folder = cache / vid / "frames"
    folder.mkdir(parents=True, exist_ok=True)
    url = ""
    if any(not (folder / f"stream_{height}p_{int(t):06d}.jpg").is_file() for t in times):
        code, out, err = client.command([
            client.ytdlp, "-g", "-f", f"bv*[height<={height}][ext=mp4][protocol=https]/bv*[height<={height}]",
            "--no-playlist", "--no-warnings", f"https://www.youtube.com/watch?v={vid}"], 40)
        url = out.strip().splitlines()[0] if code == 0 and out.strip() else ""
        host = urlsplit(url).hostname or ""
        if not url or not host.endswith(".googlevideo.com"):
            status, reason = classify_error(err, code)
            return [], {"status": status, "reason": reason or "Brak adresu strumienia."}
    frames, issues = [], []
    for requested in times:
        target = folder / f"stream_{height}p_{int(requested):06d}.jpg"
        fetched = 0
        if not target.is_file():
            client.gap()
            left = client.remaining()
            if left <= 0:
                issues.append(f"{requested}s: limit czasu")
                continue
            code, _, log = Client._run(["ffmpeg", "-nostdin", "-v", "debug", "-ss", str(requested), "-i", url,
                                        "-frames:v", "1", "-q:v", "2", "-y", str(target)], min(30, left))
            match = re.findall(r"Statistics: (\d+) bytes read", log)
            fetched = int(match[-1]) if match else 0
            client.bytes += fetched
            if code != 0 or not target.is_file():
                issues.append(f"{requested}s: ffmpeg {code}")
                continue
        frames.append(_frame_record(vid, meta, target, requested, float(requested), f"stream_ffmpeg_{height}p",
                                    fetched, version))
    return frames, ({"status": "partial", "reason": "; ".join(issues)} if issues else None)


# ---------------------------------------------------------------- enrich

def _coverage(meta, transcript, frame_items, gaps, frames_state, reason_frames):
    duration = meta.get("duration") if meta else None
    description = (meta or {}).get("description") or ""
    segments = (transcript or {}).get("segments") or []
    if transcript and segments:
        source = transcript["method"]
        asr = source == "asr"
        end = transcript.get("seconds") if asr else duration
        state = "partial" if asr and duration and (end or 0) < duration - 1 else "full"
        speech = {"state": state, "source": source, "windows": [{"start": 0, "end": end or segments[-1]["end"]}],
                  "durationSec": duration, "reason": None, "spanSec": [segments[0]["start"], segments[-1]["end"]]}
    else:
        speech = {"state": "unavailable", "source": "none", "windows": [], "durationSec": duration,
                  "reason": next((g["reason"] for g in gaps if g["modality"] == "transcript"), "brak transkrypcji")}
    moments = [f["time"] for f in frame_items]
    frames = {"state": frames_state, "moments": moments, "intervalSec": (frame_items[0].get("intervalSec") if frame_items else None),
              "reason": reason_frames}
    description_state = {"state": "full" if description else "empty", "chars": len(description),
                         "originalTextSha256": digest(description) if description else None}
    covered = [speech["state"] in {"full", "partial"}, bool(description)]
    state = "full" if all(covered) and speech["state"] == "full" else ("partial" if any(covered) else "none")
    checked = [name for name, ok in (("description", bool(description)), ("speech", speech["state"] != "unavailable"),
                                     ("frames_selected", frames_state == "selected_moments")) if ok]
    return {"scope": "description+transcript", "state": state, "checked": checked,
            "modalities": {"description": description_state, "transcript": speech, "frames": frames},
            "gaps": gaps, "blocksConclusion": speech["state"] != "full",
            "label": f"opis: {len(description)} zn.; mowa: {speech['state']} ({speech['source']}); kadry: {frames_state}"}, {
        "transcript": {k: speech[k] for k in ("state", "source", "windows", "durationSec", "reason")},
        "frames": {"state": frames_state, "moments": moments, "intervalSec": frames["intervalSec"]}}


def enrich(capture, ctx=None, *, frames_at=None, frame_method=None, allow_asr=None, max_seconds=None,
           cache_dir=None, client=None, asr=None, refresh=False):
    """Add transcript segments, optional frames and coverage to a YouTube capture. Never raises.

    ``ctx`` may carry ``ctx.media`` (dict): frames_at, frame_method ("auto"|"storyboard"|"stream"),
    allow_asr (True: only when captions are missing; "force": skip captions, evidence run), max_seconds,
    cache_dir. Keyword arguments take precedence.
    """
    options = dict(getattr(ctx, "media", None) or (ctx.get("media") if isinstance(ctx, dict) else None) or {})
    frames_at = list(frames_at if frames_at is not None else options.get("frames_at") or [])
    frame_method = frame_method or options.get("frame_method") or "auto"
    allow_asr = options.get("allow_asr", False) if allow_asr is None else allow_asr
    cache = Path(cache_dir or options.get("cache_dir") or CACHE_DIR)
    extra = capture.get("extra") or {}
    vid = (video_id(capture.get("url")) or video_id(((extra.get("youtube") or {}).get("videoId")))
           or video_id(capture.get("videoId")) or video_id(capture.get("id") or ""))
    result = {"source": SOURCE, "videoId": vid, "url": f"https://www.youtube.com/watch?v={vid}" if vid else None,
              "observedAt": now_iso(), "segments": [], "frames": [], "stats": {}}
    if not vid:
        gap = [{"modality": "transcript", "code": "no_video_id", "reason": "To nie jest adres filmu YouTube."}]
        result.update(status="unsupported", mediaCoverage=_failure_coverage("no_video_id", "brak identyfikatora"),
                      coverage=_coverage(None, None, [], gap, "not_collected", None)[0])
        return result
    client = client or Client(max_seconds=max_seconds or options.get("max_seconds") or MAX_SECONDS)
    began = client.clock()
    result["stats"] = {"requests": 0, "bytes": 0, "wallSeconds": 0}

    def done(status):
        result["status"] = status
        result["stats"] = {"requests": client.requests, "bytes": client.bytes,
                           "wallSeconds": round(client.clock() - began, 2)}
        return result

    try:
        meta, error = load_meta(vid, client, cache, refresh=refresh)
    except Exception as exc:  # defensive: the adapter must not break a scan
        meta, error = None, {"status": "error", "reason": f"{type(exc).__name__}: {exc}"[:240]}
    if meta is None or meta.get("status") != "ok":
        error = error or {"status": meta["status"], "reason": meta.get("reason", "")}
        gaps = [{"modality": "transcript", "code": error["status"], "reason": error["reason"]}]
        result.update(error=error, mediaCoverage=_failure_coverage(error["status"], error["reason"]),
                      coverage=_coverage(None, None, [], gaps, "not_collected", error["reason"])[0])
        return done(error["status"])

    result["meta"] = {k: meta.get(k) for k in ("title", "duration", "channel", "uploadDate", "language", "availability")}
    transcript = None if allow_asr == "force" else _read_json(cache / vid / "transcript.json")
    gaps = []
    if allow_asr != "force" and (not transcript or refresh):
        transcript = captions(vid, meta, cache)
        if transcript:
            _write_json(cache / vid / "transcript.json", transcript)
    if not transcript and allow_asr:
        transcript = _read_json(cache / vid / "asr.json")
        if not transcript:
            from analysis.transcribe import transcribe_excerpt
            transcript, problem = asr_audio(vid, meta, client, cache, asr or transcribe_excerpt)
            if transcript:
                _write_json(cache / vid / "asr.json", transcript)
            else:
                gaps.append({"modality": "transcript", "code": problem["status"], "reason": problem["reason"]})
    elif not transcript:
        gaps.append({"modality": "transcript", "code": "no_captions",
                     "reason": "Brak napisów po polsku; ASR nie został zażądany (ciężki przebieg)."})
    version = {"videoId": vid, "readAt": result["observedAt"], "source": SOURCE,
               "captionsSha256": (transcript or {}).get("captionsSha256") or (transcript or {}).get("audioSha256"),
               "descriptionSha256": digest(meta.get("description") or ""), "ytDlpVersion": meta.get("ytDlpVersion")}
    if transcript:
        result["segments"] = transcript["segments"]
        result["transcript"] = {k: v for k, v in transcript.items() if k != "segments"}
        result["mediaVersion"] = version["captionsSha256"]
    result["sourceVersion"] = version

    frame_items, frame_problem = [], None
    if frames_at:
        times = sorted({max(0.0, float(t)) for t in frames_at})
        duration = meta.get("duration")
        if duration:
            times = [min(t, max(0.0, duration - 1)) for t in times]
        if frame_method == "auto":  # sparse tiles (long films, about 10 s) are too coarse to pin a moment
            step = storyboard_interval(meta)
            frame_method = "storyboard" if step and step <= SB_MAX_INTERVAL else "stream"
        if frame_method == "stream":
            frame_items, frame_problem = stream_frames(vid, meta, times, client, cache, version)
        else:
            frame_items, frame_problem = storyboard_frames(vid, meta, times, client, cache, version)
            if not frame_items and frame_problem and frame_problem["status"] == "no_storyboard":
                frame_items, frame_problem = stream_frames(vid, meta, times, client, cache, version)
        result["frames"] = frame_items
        if frame_problem:
            gaps.append({"modality": "frames", "code": frame_problem["status"], "reason": frame_problem["reason"]})
    state = "selected_moments" if frame_items else "not_collected"
    reason = (frame_problem or {}).get("reason") if frames_at else "nie zażądano"
    coverage, media_coverage = _coverage(meta, transcript, frame_items, gaps, state, reason)
    result.update(coverage=coverage, mediaCoverage=media_coverage)
    return done("ok" if transcript else "no_transcript")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Napisy i kadry publicznego filmu YouTube.")
    parser.add_argument("video")
    parser.add_argument("--frames", default="", help="sekundy oddzielone przecinkami")
    parser.add_argument("--frame-method", choices=("auto", "storyboard", "stream"), default="auto")
    parser.add_argument("--asr", action="store_true", help="ciężki przebieg: pierwsze 120 s audio + Vosk")
    parser.add_argument("--full", action="store_true", help="dołącz wszystkie segmenty")
    args = parser.parse_args()
    times = [float(x) for x in args.frames.split(",") if x.strip()]
    out = enrich({"url": args.video}, None, frames_at=times, frame_method=args.frame_method, allow_asr=args.asr)
    if not args.full:
        out["segments"] = f"{len(out['segments'])} segmentów (użyj --full)"
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
