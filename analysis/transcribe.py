"""Local Polish speech recognition for short, user-provided audio or video."""
import argparse
import ctypes as ct
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
ASR = ROOT / ".runtime" / "asr"
MODEL = "vosk-model-small-pl-0.22"
MEDIA = ROOT / "analysis" / "media"
RATE = 16000
MAX_SECONDS = 120


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def pcm_from_file(path, excerpt_seconds=None):
    media = Path(path).resolve(strict=True)
    seconds = MAX_SECONDS + 1 if excerpt_seconds is None else excerpt_seconds
    command = [
        "ffmpeg", "-nostdin", "-v", "error", "-threads", "1",
        "-protocol_whitelist", "file,pipe",
        "-format_whitelist", "wav,mov,matroska,webm,mp3,ogg,flac,aac,aiff",
        "-i", str(media), "-map", "0:a:0", "-t", str(seconds),
        "-ar", str(RATE), "-ac", "1", "-f", "s16le", "pipe:1",
    ]
    if excerpt_seconds is None:
        command.insert(1, "-xerror")
    try:
        result = subprocess.run(command, capture_output=True, timeout=40, check=True)
    except FileNotFoundError as exc:
        raise RuntimeError("Brak dekodera ffmpeg w PATH.") from exc
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise ValueError("Nie udało się odczytać ścieżki audio w obsługiwanym pliku.") from exc
    if len(result.stdout) > RATE * 2 * MAX_SECONDS:
        raise ValueError(f"Maksymalna długość nagrania to {MAX_SECONDS} s.")
    if not result.stdout:
        raise ValueError("Ścieżka audio jest pusta.")
    return result.stdout


def library():
    path = os.environ.get("INVESTWATCH_VOSK_LIBRARY", ASR / "vosk" / "libvosk.so")
    try:
        lib = ct.CDLL(str(path))
    except OSError as exc:
        raise RuntimeError("Nie można załadować Vosk. Uruchom python3 -m analysis.setup_asr.") from exc
    handle, char, num = ct.c_void_p, ct.c_char_p, ct.c_int
    signatures = {
        "vosk_set_log_level": (None, [num]),
        "vosk_model_new": (handle, [char]),
        "vosk_model_free": (None, [handle]),
        "vosk_recognizer_new": (handle, [handle, ct.c_float]),
        "vosk_recognizer_free": (None, [handle]),
        "vosk_recognizer_set_words": (None, [handle, num]),
        "vosk_recognizer_accept_waveform": (num, [handle, char, num]),
        "vosk_recognizer_result": (char, [handle]),
        "vosk_recognizer_final_result": (char, [handle]),
    }
    for name, (result, arguments) in signatures.items():
        function = getattr(lib, name)
        function.argtypes = arguments
        function.restype = result
    lib.vosk_set_log_level(-1)
    return lib


def segment(payload):
    item = json.loads(payload)
    words = item.get("result", [])
    if not words:
        return []
    return [{"start": words[0]["start"], "end": words[-1]["end"], "text": item["text"],
             "confidence": round(sum(w["conf"] for w in words) / len(words), 3)}]


def transcribe_file(path):
    """Decode all audio (max. 120 s) and return timed, unedited Vosk utterances."""
    return recognize(pcm_from_file(path))


def transcribe_excerpt(path, seconds=45):
    """Recognize the initial audio only, including complete frames of a partial MP3."""
    if not isinstance(seconds, int) or not 1 <= seconds <= MAX_SECONDS:
        raise ValueError(f"Długość odsłuchu musi wynosić od 1 do {MAX_SECONDS} sekund.")
    return recognize(pcm_from_file(path, seconds))


def recognize(pcm):
    model_dir = Path(os.environ.get("INVESTWATCH_VOSK_MODEL", ASR / MODEL))
    if not (model_dir / "am" / "final.mdl").is_file():
        raise RuntimeError("Brak modelu języka polskiego. Uruchom python3 -m analysis.setup_asr.")
    lib = library()
    model = lib.vosk_model_new(os.fsencode(model_dir))
    if not model:
        raise RuntimeError("Vosk nie odczytał lokalnego modelu.")
    recognizer = None
    try:
        recognizer = lib.vosk_recognizer_new(model, RATE)
        if not recognizer:
            raise RuntimeError("Vosk nie uruchomił dekodera.")
        lib.vosk_recognizer_set_words(recognizer, 1)
        segments = []
        for index in range(0, len(pcm), 8000):
            chunk = pcm[index:index + 8000]
            state = lib.vosk_recognizer_accept_waveform(recognizer, chunk, len(chunk))
            if state < 0:
                raise RuntimeError("Vosk przerwał rozpoznawanie.")
            if state:
                segments.extend(segment(lib.vosk_recognizer_result(recognizer)))
        return segments + segment(lib.vosk_recognizer_final_result(recognizer))
    finally:
        if recognizer:
            lib.vosk_recognizer_free(recognizer)
        lib.vosk_model_free(model)


def replay_file(path):
    report = json.loads((MEDIA / "studio.asr.json").read_text())
    if digest(path) != report["sha256"]:
        raise ValueError("Ta transkrypcja pochodzi z innego pliku. Uruchom analizę audio.")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("--replay", action="store_true", help="Odtwórz zachowany wynik dla identycznych bajtów.")
    args = parser.parse_args()
    try:
        report = replay_file(args.file) if args.replay else {
            "model": MODEL, "engine": "Vosk 0.3.45", "language": "pl", "sha256": digest(args.file),
            "segments": transcribe_file(args.file),
        }
    except (ValueError, RuntimeError, OSError) as exc:
        parser.exit(2, f"{exc}\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
