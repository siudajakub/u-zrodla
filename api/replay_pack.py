"""Replay media pack: full transcripts and frames of the dated event, kept OUT of Git.

The pack is a folder (default `.runtime/replay-media/2026-11-21/`) with the layout of the media cache
(`<videoId>/meta.json`, `<videoId>/transcript.json`, `<videoId>/frames/*.jpg`) and a `MANIFEST.json` that lists every
file with its SHA-256. Only the tool and the manifest copy (`fixtures/raw/media/2026-11-21/replay-pack.manifest.json`)
live in the repository. A replay scan reads the pack through `api.enrich` with no network; a missing or damaged pack is
reported as a source status and a coverage gap, never as an error.

    python -m api.replay_pack build --from .runtime/media-cache --ids ID1,ID2 [--out DIR] [--manifest-out FILE]
    python -m api.replay_pack verify [--pack DIR] [--manifest FILE]
"""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
EVENT = "2026-11-21"
DEFAULT_PACK = ROOT / ".runtime/replay-media" / EVENT
REPO_MANIFEST = ROOT / "fixtures/raw/media" / EVENT / "replay-pack.manifest.json"
SCHEMA = 1


def pack_dir():
    return Path(os.environ.get("INVESTWATCH_REPLAY_MEDIA") or DEFAULT_PACK)


def digest(path):
    h = sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _files(root, video):
    """The files of one video that the pack keeps: metadata, transcript, extracted frames (no storyboard sheets)."""
    base = root / video
    for name in ("meta.json", "transcript.json"):
        if (base / name).is_file():
            yield base / name
    frames = base / "frames"
    if frames.is_dir():
        for path in sorted(frames.glob("*.jpg")):
            if not path.name.startswith("sheet_"):
                yield path


def build(source, ids, out, manifest_out=None):
    source, out = Path(source), Path(out)
    videos, files = [], []
    for video in ids:
        found = list(_files(source, video))
        if not any(p.name == "meta.json" for p in found):
            raise SystemExit(f"{video}: brak meta.json w {source}")
        for path in found:
            target = out / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            files.append({"path": str(target.relative_to(out)), "sha256": digest(target), "bytes": target.stat().st_size})
        videos.append(video)
    manifest = {"schema": SCHEMA, "event": EVENT, "builtAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "source": "media-cache of lane C (yt-dlp captions, storyboard and stream frames)",
                "note": "Pełne transkrypcje i kadry; poza Gitem. W repozytorium tylko ten manifest.",
                "videos": videos, "files": sorted(files, key=lambda f: f["path"])}
    text = json.dumps(manifest, ensure_ascii=False, indent=1) + "\n"
    (out / "MANIFEST.json").write_text(text, encoding="utf-8")
    if manifest_out:
        Path(manifest_out).parent.mkdir(parents=True, exist_ok=True)
        Path(manifest_out).write_text(text, encoding="utf-8")
    return manifest


def inspect(pack=None, manifest=None):
    """State of the pack: {state: present|missing|corrupt, videos, files, manifestSha256, problems}."""
    pack = Path(pack) if pack else pack_dir()
    path = pack / "MANIFEST.json"
    if not path.is_file():
        return {"state": "missing", "pack": str(pack), "videos": [], "files": 0, "manifestSha256": None,
                "problems": ["brak MANIFEST.json (paczka nie została zbudowana na tym hoście)"]}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        entries = data["files"]
    except (ValueError, KeyError, OSError) as exc:
        return {"state": "corrupt", "pack": str(pack), "videos": [], "files": 0, "manifestSha256": None,
                "problems": [f"nieczytelny MANIFEST.json: {type(exc).__name__}"]}
    problems = []
    for entry in entries:
        target = pack / entry["path"]
        if not target.is_file():
            problems.append(f"brak pliku {entry['path']}")
        elif digest(target) != entry["sha256"]:
            problems.append(f"zła suma SHA-256: {entry['path']}")
    if manifest is not None:
        reference = Path(manifest)
        if not reference.is_file():
            problems.append(f"brak manifestu odniesienia {reference}")
        elif digest(reference) != digest(path):
            problems.append("MANIFEST.json różni się od manifestu odniesienia")
    return {"state": "corrupt" if problems else "present", "pack": str(pack), "videos": data.get("videos", []),
            "files": len(entries), "manifestSha256": digest(path), "problems": problems}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build")
    b.add_argument("--from", dest="source", required=True, type=Path)
    b.add_argument("--ids", required=True, help="identyfikatory filmów oddzielone przecinkami")
    b.add_argument("--out", type=Path, default=DEFAULT_PACK)
    b.add_argument("--manifest-out", type=Path, default=REPO_MANIFEST)
    v = sub.add_parser("verify")
    v.add_argument("--pack", type=Path)
    v.add_argument("--manifest", type=Path, default=REPO_MANIFEST, help="manifest odniesienia z repozytorium")
    args = parser.parse_args(argv)
    if args.command == "build":
        ids = [x.strip() for x in args.ids.split(",") if x.strip()]
        manifest = build(args.source, ids, args.out, args.manifest_out)
        print(json.dumps({"videos": len(manifest["videos"]), "files": len(manifest["files"]),
                          "bytes": sum(f["bytes"] for f in manifest["files"]), "out": str(args.out)}, ensure_ascii=False))
        return 0
    report = inspect(args.pack, args.manifest)
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0 if report["state"] == "present" else 1


if __name__ == "__main__":
    sys.exit(main())
