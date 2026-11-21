"""Manual import of Meta pages the analyst saved (POST /v1/import/meta) and the text-only qualification of its records.

No network: the file is parsed by collectors/meta_import.py, kept under STATE/meta-import with its SHA-256 in the
name and read back by the `meta_import` adapter of a scan. Nothing in the file is executed or rendered."""
from email import policy
from email.parser import BytesParser
from hashlib import sha256
import re
import tempfile
from pathlib import Path

from collectors import meta_import
from . import store

SUFFIXES = (".html", ".htm", ".txt")
TEXT_TYPES = ("text/", "application/xhtml+xml", "application/octet-stream")
INLINE_MAX = 2 * 1024 * 1024  # a larger file waits for the worker instead of holding the request


class ImportRejected(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status, self.message = status, message


def safe_name(filename, default="meta.txt"):
    """A name that cannot leave the import folder: no directories, no dots in front, only [A-Za-z0-9._-]."""
    base = Path(str(filename or "").replace("\\", "/")).name.strip()
    base = re.sub(r"[^A-Za-z0-9._-]", "_", base).lstrip(".")
    stem, dot, ext = base.rpartition(".")
    if not stem:
        stem, ext = base, ""
    cleaned = (stem[:70] or "meta") + ("." + ext[:8] if ext else "")
    return cleaned if cleaned.lower().endswith(SUFFIXES) else default


def check_type(filename, content_type):
    if Path(str(filename or "")).suffix.lower() not in SUFFIXES:
        raise ImportRejected(415, "Wybierz zapisaną stronę (.html, .htm lub .txt).")
    kind = (content_type or "").split(";")[0].strip().lower()
    if kind and not kind.startswith(TEXT_TYPES) and kind != "multipart/form-data":
        raise ImportRejected(415, "Przyjmujemy tylko pliki tekstowe (tekst lub HTML).")


def split_multipart(body, content_type):
    """The first file part of a multipart/form-data body: (filename, bytes). Standard library only."""
    message = BytesParser(policy=policy.HTTP).parsebytes(b"Content-Type: " + content_type.encode("latin-1", "replace")
                                                         + b"\r\n\r\n" + body)
    for part in message.iter_parts() if message.is_multipart() else ():
        name = part.get_filename()
        if name:
            return name, part.get_payload(decode=True) or b""
    raise ImportRejected(422, "W przesłanym formularzu nie ma pliku.")


def read_new(data, name, imported_at=None):
    """Parse `data` as a saved Meta page without storing it. Returns the file report of meta_import.read_file."""
    if b"\x00" in data[:65536]:
        raise ImportRejected(415, "To nie jest plik tekstowy.")
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / name
        path.write_bytes(data)
        return meta_import.read_file(path, imported_at=imported_at)


def known_ids(ids):
    ids, found = sorted(ids), set()
    with store.connection() as db:
        for start in range(0, len(ids), 500):
            chunk = ids[start:start + 500]
            found.update(r[0] for r in db.execute(f"SELECT id FROM cases WHERE id IN ({','.join('?' * len(chunk))})", chunk))
    return found


def summarize(report, name, digest, stored, again):
    captures = report["captures"]
    ads = [c for c in captures if c.get("adId")]
    posts = [c for c in captures if not c.get("adId")]
    have = known_ids({c["id"] for c in captures})
    warnings = []
    for key, note in (("duplicates", "Powtórzone karty reklam w pliku pominięto: {}."),):
        if report.get(key):
            warnings.append(note.format(report[key]))
    missing = sum(1 for c in captures if c.get("importMissing"))
    if missing:
        warnings.append(f"{missing} wpisów ma pola bez danych w zapisanym pliku (data, flaga lub platforma).")
    if ads and not any(c.get("publisherPlatforms") for c in ads):
        warnings.append("Platformy reklam nie wynikają z zapisanego tekstu (ikony bez nazw); reklamy liczone jako Facebook.")
    if again:
        warnings.append("Ten sam plik był już wczytany; istniejące wpisy nie zostaną zdublowane.")
    return {"file": name, "storedAs": stored, "sha256": digest, "kind": report["kind"], "recognized": len(captures),
            "ads": len(ads), "posts": len(posts), "new": sum(1 for c in captures if c["id"] not in have),
            "existing": sum(1 for c in captures if c["id"] in have), "warnings": warnings, "alreadyImported": again}


def accept(data, filename):
    """Validate, parse and store a file. Returns (summary, stored path). Raises ImportRejected with the HTTP status."""
    if not data:
        raise ImportRejected(422, "Plik jest pusty.")
    if len(data) > meta_import.MAX_FILE:
        raise ImportRejected(413, "Plik jest większy niż 25 MiB.")
    digest = sha256(data).hexdigest()
    name = safe_name(filename)
    stored = f"{digest[:16]}-{name}"
    report = read_new(data, stored)
    if report["status"] == "unrecognized":
        raise ImportRejected(422, report["message"])
    if report["status"] in ("empty", "error") or not report["captures"]:
        raise ImportRejected(422, report["message"] or "Plik jest rozpoznany, ale nie zawiera reklam ani postów.")
    folder = store.STATE / "meta-import"
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = folder / stored
    again = target.is_file() and sha256(target.read_bytes()).hexdigest() == digest
    if not again:
        with tempfile.NamedTemporaryFile(dir=folder, suffix=".part", delete=False) as out:
            out.write(data)
        Path(out.name).replace(target)
    return summarize(report, name, digest, stored, again), digest


# --- text-only qualification of imported records ----------------------------------------------------------------------

BENEFIT = re.compile(r"zarabi\w*|zysk\w*|korzy\w*|bez prowizji|0\s*%\s*prowizji|odsetk\w*|dochod\w*|dochód|"
                     r"pieniądz\w*.{0,40}prac\w*|prac\w*.{0,40}pieniądz\w*|oszczędz\w*", re.I)
WARNING = re.compile(r"ryzyk\w*|strat\w*|stracić|nie gwarantuj\w*|nie stanowi\w* gwarancji|wyniki z przeszłości|"
                     r"wyniki historyczne|CFD|konieczność.{0,20}wpłat|\d+\s*%\s*rachunków", re.I)
SCOPE_LABEL = {"ad": "tylko tekst reklamy z zapisanej strony, bez obrazu, wideo i renderu",
               "post": "tylko tekst podpisu posta z zapisanej strony, bez obrazu i renderu"}


def qualify_import(cap, finding):
    """Imported ads and captions are read as text. The text of an ad may omit what the graphic or the video carries,
    so a benefit claim without a warning in the text is never a strong flag by itself: it routes to "complete: check
    the creative" with the reason named. Whatever the M2 analysis itself established from the text stays as it is."""
    vendor = str(cap.get("materialType") or "").startswith("vendor_")  # the dated sample of the external service: text as well
    if not (cap.get("importLabel") or vendor) or finding.get("module") != "M2":
        return finding
    kind = "ad" if cap.get("adId") else "post"
    text = "\n".join(str(cap.get(k) or "") for k in ("adBody", "adTitle", "adDescription", "description") if cap.get(k))
    text = text or str(cap.get("description") or "")
    label = SCOPE_LABEL[kind]
    coverage = finding.get("coverage") if isinstance(finding.get("coverage"), dict) else {}
    finding["coverage"] = {**coverage, "scope": "ad_text" if kind == "ad" else "post_caption", "state": "partial",
                           "label": "Zbadano: " + label, "blocksConclusion": False,
                           "modalities": {**(coverage.get("modalities") or {}), "adText" if kind == "ad" else "caption": {"state": "full"},
                                          "render": {"state": "not_collected"}, "media": {"state": "not_collected"}},
                           "gaps": [{"modality": "render", "code": "not_collected",
                                     "reason": "obrazu, wideo i układu nie analizowano; ostrzeżenie mogło być w grafice lub wideo"}]}
    suggestion = finding.get("reviewSuggestion") if isinstance(finding.get("reviewSuggestion"), dict) else {}
    if suggestion.get("state") not in (None, "unavailable") or finding.get("checkCounts", {}).get("obserwacja"):
        return finding  # the text analysis itself reached a conclusion
    claim, warning = BENEFIT.search(text), WARNING.search(text)
    if claim and not warning:
        finding["reviewSuggestion"] = {
            "criterionId": "3", "source": "rules", "state": "uncertain",
            "reason": "Uzupełnij: sprawdź kreację. W tekście jest twierdzenie o korzyści („" + claim.group(0)[:60] +
                      "”) bez ostrzeżenia o ryzyku, ale ostrzeżenie mogło być w grafice lub wideo, których import nie zawiera."}
    elif claim:
        finding["reviewSuggestion"] = {
            "criterionId": "3", "source": "rules", "state": "unavailable",
            "reason": "Tekst zawiera i twierdzenie o korzyści, i ostrzeżenie o ryzyku; ich bliskość w kreacji wymaga obrazu (brak renderu)."}
    else:
        finding["reviewSuggestion"] = {**suggestion, "criterionId": "3", "source": "rules", "state": "unavailable",
                                       "reason": "W tekście nie wykryto twierdzenia o korzyści; obrazu i wideo nie zbadano."}
    return finding
