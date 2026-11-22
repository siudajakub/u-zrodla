"""Archiwum gotowego stanu pokazu: SQLite (spójna kopia przez backup API) + magazyn obiektów + odcisk kodu.

  python3 ops/demo/state_pack.py fingerprint
  python3 ops/demo/state_pack.py pack --state DIR [--objects DIR] --out ARCHIWUM.tar.gz [--flavor compose|local]
  python3 ops/demo/state_pack.py restore --archive A --state DIR [--objects DIR]

Układ archiwum: state-pack.json (pierwszy), state/cases.sqlite3 (+ inne pliki stanu bez kolejki), objects/<podkatalog>/...
Kolejka (queue.sqlite3) jest przejściowa i nie trafia do archiwum: worker odtwarza ją z dziennika skanów.
Kody wyjścia restore: 0 przywrócono, 10 odcisk kodu niezgodny (nic nie zmieniono), 11 stan już istnieje, 1 błąd.
Tylko biblioteka standardowa (macOS i Linux, Python >= 3.8).
"""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[2]
EVENT = "2026-11-21"
FORMAT = 1
OBJECT_DIRS = ("uploads", "m2", "media-cache", "meta-import", "youtube-raw", "youtube-cache")
TRANSIENT = ("queue.sqlite3", "queue.sqlite3-wal", "queue.sqlite3-shm", "cases.sqlite3-wal", "cases.sqlite3-shm")
# Wejścia, od których zależy wynik analizy. Zmiana któregokolwiek pliku = inny odcisk = normalny bootstrap.
INPUTS = ("api", "analysis", "collectors", "fixtures", "data/probe-snapshots", "tools/eval_validation.py")
MODULE_ROOTS = {"api", "analysis", "collectors"}


def code_fingerprint(root=ROOT):
    try:
        def files(options, paths):
            out = subprocess.run(["git", "ls-files", "-z", *options, "--", *paths],
                                 cwd=root, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True).stdout
            return {os.fsdecode(n) for n in out.split(b"\0") if n}

        names = files(("--cached",), INPUTS)
        # A new Python module is executable before commit. Ignore untracked data, results and dependency caches.
        names.update(name for name in files(("--others", "--exclude-standard"), sorted(MODULE_ROOTS))
                     if Path(name).suffix == ".py")
    except (OSError, subprocess.CalledProcessError):
        return None  # bez git nie da się wiarygodnie porównać: zawsze normalny bootstrap
    digest = hashlib.sha256()
    for name in sorted(names):
        path = root / name
        if not path.is_file() or "__pycache__" in path.parts or path.name.startswith("test_") or path.suffix == ".md":
            continue
        digest.update(os.fsencode(name) + b"\0")
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for block in iter(lambda: fh.read(1 << 20), b""):
                h.update(block)
        digest.update(h.digest())
    return digest.hexdigest()


def scans_ready(db_path):
    with sqlite3.connect(f"{db_path.as_uri()}?mode=ro", uri=True, timeout=5) as db:
        rows = db.execute("select request_id,status from scans").fetchall()
        if db.execute("select 1 from sqlite_schema where name='queue_members'").fetchone():
            cases = db.execute("select count(*) from queue_members where name='all'").fetchone()[0]
        else:
            cases = db.execute("select count(*) from cases").fetchone()[0]
    pending = [r for r in rows if r[1] in ("queued", "running")]
    return rows, pending, cases


def remove_synthetic_cases(db_path):
    """Clean the transferable snapshot while keeping the operator's original database intact."""
    related = {"cases": "id", "versions": "id", "version_meta": "id", "history": "case_id",
               "events": "ref", "discoveries": "case_id", "reach_samples": "case_id", "media_state": "case_id",
               "qualification_results": "case_id", "queue_rows": "id", "queue_members": "id"}
    with closing(sqlite3.connect(db_path)) as db:
        db.execute("CREATE TEMP TABLE synthetic_cases(id TEXT PRIMARY KEY)")
        db.execute("""
            INSERT INTO synthetic_cases
            SELECT id FROM cases WHERE json_valid(body) AND (
                json_extract(body,'$.synthetic') = 1 OR json_extract(body,'$.contractDemo') = 1
                OR json_extract(body,'$.origin') = 'synthetic')
        """)
        if not db.execute("SELECT 1 FROM synthetic_cases LIMIT 1").fetchone():
            return
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_schema WHERE type='table'")}
        for table, column in related.items():
            if table in tables:
                db.execute(f"DELETE FROM {table} WHERE {column} IN (SELECT id FROM synthetic_cases)")
        if "queue_dirty" in tables:
            db.execute("DELETE FROM queue_dirty WHERE kind='case' AND key IN (SELECT id FROM synthetic_cases)")
        db.commit()
        db.execute("VACUUM")


def pack(args):
    state = Path(args.state).resolve()
    objects = Path(args.objects).resolve() if args.objects else state
    db_path = state / "cases.sqlite3"
    if not db_path.is_file():
        sys.exit(f"Brak {db_path}: najpierw zakończony bootstrap (sh ops/demo/start.sh).")
    fp = code_fingerprint()
    if not fp:
        sys.exit("Brak git: nie da się policzyć odcisku kodu.")
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="state-pack-", dir=out.parent) as tmp:
        snap = Path(tmp) / "cases.sqlite3"
        with sqlite3.connect(f"{db_path.as_uri()}?mode=ro", uri=True, timeout=30) as src, sqlite3.connect(snap) as dst:
            src.backup(dst)  # spójna kopia także przy działającym api/workerze
        remove_synthetic_cases(snap)
        rows, pending, cases = scans_ready(snap)
        if pending or not rows:
            sys.exit(f"Skany nie są zakończone ({len(pending)} w toku z {len(rows)}). Poczekaj na GOTOWE i powtórz.")
        meta = {"format": FORMAT, "event": EVENT, "codeFingerprint": fp, "flavor": args.flavor,
                "createdAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "cases": cases, "scans": sorted(r[0] for r in rows),
                "git": subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, stdout=subprocess.PIPE,
                                      stderr=subprocess.DEVNULL, text=True).stdout.strip() or None}
        part = out.with_name(out.name + ".part")
        with tarfile.open(part, "w:gz", compresslevel=6) as tar:
            blob = json.dumps(meta, indent=2, ensure_ascii=False).encode()
            info = tarfile.TarInfo("state-pack.json"); info.size = len(blob); info.mode = 0o600
            tar.addfile(info, io.BytesIO(blob))
            tar.add(snap, "state/cases.sqlite3")
            for item in sorted(state.iterdir()):
                if item.name in TRANSIENT or item.name in ("cases.sqlite3", "state-pack.json") or item.name in OBJECT_DIRS:
                    continue
                tar.add(item, f"state/{item.name}")
            for name in OBJECT_DIRS:
                if (objects / name).is_dir():
                    tar.add(objects / name, f"objects/{name}")
        part.replace(out)
    digest = sha256_file(out)
    out.with_name(out.name + ".sha256").write_text(f"{digest}  {out.name}\n")
    print(json.dumps({"archive": str(out), "sha256": digest, "bytes": out.stat().st_size, **{k: meta[k] for k in
                      ("codeFingerprint", "cases", "flavor", "git")}}, ensure_ascii=False))


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def safe_members(tar):
    for m in tar.getmembers():
        p = Path(m.name)
        if p.is_absolute() or ".." in p.parts or not (m.isfile() or m.isdir()):
            raise SystemExit(f"Niedozwolony element archiwum: {m.name}")
        if m.name != "state-pack.json" and p.parts[0] not in ("state", "objects"):
            raise SystemExit(f"Nieoczekiwany element archiwum: {m.name}")
        yield m


def restore(args):
    archive = Path(args.archive).resolve()
    state = Path(args.state).resolve()
    objects = Path(args.objects).resolve() if args.objects else state
    if (state / "cases.sqlite3").exists():
        print(f"Stan już istnieje ({state}); archiwum pominięte.")
        return 11
    side = archive.with_name(archive.name + ".sha256")
    if side.is_file():
        want = side.read_text().split()[0]
        if sha256_file(archive) != want:
            print(f"Suma SHA-256 {archive.name} nie zgadza się z {side.name}.", file=sys.stderr)
            return 1
    else:
        print(f"Uwaga: brak {side.name}; integralność sprawdza tylko format archiwum.", file=sys.stderr)
    with tarfile.open(archive, "r:gz") as tar:
        head = tar.next()
        if head is None or head.name != "state-pack.json":
            print("Archiwum nie zaczyna się od state-pack.json.", file=sys.stderr)
            return 1
        meta = json.load(tar.extractfile(head))
        current = code_fingerprint()
        if meta.get("format") != FORMAT or meta.get("event") != EVENT or not current or meta.get("codeFingerprint") != current:
            print(f"UWAGA: archiwum stanu z innej wersji kodu (archiwum {str(meta.get('codeFingerprint'))[:12]}, git {meta.get('git')}; "
                  f"teraz {str(current)[:12]}). Robię normalny bootstrap (kilka minut).", file=sys.stderr)
            return 10
        state.parent.mkdir(parents=True, exist_ok=True)
        tmp = Path(tempfile.mkdtemp(prefix=".state-restore-", dir=state.parent))
        try:
            members = list(safe_members(tar))
            if sys.version_info >= (3, 12):
                tar.extractall(tmp, members=members, filter="data")
            else:
                tar.extractall(tmp, members=members)
            snapshot = tmp / "state/cases.sqlite3"
            with closing(sqlite3.connect(f"{snapshot.as_uri()}?mode=ro", uri=True)) as db:
                if db.execute("pragma integrity_check").fetchone()[0] != "ok":
                    print("Baza z archiwum nie przeszła integrity_check.", file=sys.stderr)
                    return 1
            state.mkdir(parents=True, exist_ok=True, mode=0o700)
            objects.mkdir(parents=True, exist_ok=True, mode=0o700)
            for item in (tmp / "state").iterdir():
                if item.name in TRANSIENT or item.name in ("cases.sqlite3", "state-pack.json"):
                    continue
                dest = state / item.name
                if dest.is_dir() and not any(dest.iterdir()):
                    dest.rmdir()
                shutil.move(str(item), str(dest))
            if (tmp / "objects").is_dir():
                for item in (tmp / "objects").iterdir():
                    dest = objects / item.name
                    if dest.is_dir() and not any(dest.iterdir()):
                        dest.rmdir()
                    if dest.exists():
                        print(f"Pomijam {item.name}: {dest} nie jest pusty.", file=sys.stderr)
                        continue
                    shutil.move(str(item), str(dest))
            shutil.move(str(snapshot), str(state / snapshot.name))
            (tmp / "state-pack.json").replace(state / "state-pack.json")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    print(f"Przywrócono stan z {archive.name} ({meta.get('cases')} spraw, kod {meta.get('git')}, {meta.get('createdAt')}).")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fingerprint")
    p = sub.add_parser("pack")
    p.add_argument("--state", required=True); p.add_argument("--objects"); p.add_argument("--out", required=True)
    p.add_argument("--flavor", choices=("compose", "local"), default="compose")
    r = sub.add_parser("restore")
    r.add_argument("--archive", required=True); r.add_argument("--state", required=True); r.add_argument("--objects")
    args = parser.parse_args()
    if args.cmd == "fingerprint":
        print(code_fingerprint() or "")
        return 0
    if args.cmd == "pack":
        pack(args)
        return 0
    return restore(args)


if __name__ == "__main__":
    sys.exit(main())
