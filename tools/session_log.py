#!/usr/bin/env python3
"""Record short InvestWatch session checkpoints shared by local Git worktrees."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from tempfile import NamedTemporaryFile
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
SESSION_ID = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}")
FIELDS = (("goal", "Cel"), ("decision", "Decyzja"), ("test", "Próba"), ("next", "Następny krok"))


def session_id(value: str) -> str:
    if not SESSION_ID.fullmatch(value):
        raise argparse.ArgumentTypeError("ID sesji musi mieć 1–128 znaków: litery A–Z, cyfry, kropka, _ lub -")
    return value


def current_session_id() -> str | None:
    candidates = (
        os.environ.get("INVESTWATCH_SESSION_ID"),
        os.environ.get("CODEX_THREAD_ID"),
        os.environ.get("CODEX_SESSION_ID"),
    )
    return next((value for value in candidates if value and SESSION_ID.fullmatch(value)), None)


def claude_session_id() -> str | None:
    try:
        event = json.load(sys.stdin)
    except (ValueError, OSError):
        return None
    value = event.get("session_id") if isinstance(event, dict) else None
    if isinstance(value, str) and value and SESSION_ID.fullmatch("claude-" + value):
        return "claude-" + value
    return None


def short_note(value: str) -> str:
    value = value.strip()
    if not value or len(value) > 300 or not value.isprintable():
        raise argparse.ArgumentTypeError("podaj jedno zdanie, do 300 znaków")
    return value


def positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("limit musi wynosić co najmniej 1")
    return number


def log_directory() -> Path:
    worktrees = subprocess.run(
        ["git", "worktree", "list", "--porcelain", "-z"],
        cwd=ROOT, check=False, capture_output=True,
    )
    first = worktrees.stdout.split(b"\0", 1)[0]
    if worktrees.returncode == 0 and first.startswith(b"worktree "):
        return Path(os.fsdecode(first.removeprefix(b"worktree "))) / "session-logs"
    return ROOT / "session-logs"


def append_event(directory: Path, session: str, args: argparse.Namespace) -> Path:
    directory.mkdir(mode=0o700, exist_ok=True)
    now = datetime.now(timezone.utc)
    event = {
        "timestamp": now.isoformat(timespec="microseconds"),
        "session_id": session,
        **{field: getattr(args, field) for field, _ in FIELDS if getattr(args, field)},
    }
    name = f"{now:%Y%m%dT%H%M%S%fZ}-{uuid4().hex}.jsonl"
    path = directory / name

    # Publish a complete file without replacing any existing event.
    with NamedTemporaryFile(dir=directory, prefix=".event-", mode="w", encoding="utf-8",
                            delete=False) as draft:
        temporary = Path(draft.name)
        try:
            draft.write(json.dumps(event, ensure_ascii=False) + "\n")
            draft.flush()
            os.fsync(draft.fileno())
            os.link(temporary, path)
        finally:
            temporary.unlink()
    return path


def show_latest(directory: Path, limit: int, session: str | None) -> None:
    shown: set[str] = set()
    count = 0
    for path in sorted(directory.glob("*.jsonl"), reverse=True):
        try:
            event = json.loads(path.read_text(encoding="utf-8"))
            recorded_id = event["session_id"]
            timestamp = event["timestamp"]
            notes = [(label, event[field]) for field, label in FIELDS if field in event]
            if not isinstance(recorded_id, str) or not SESSION_ID.fullmatch(recorded_id):
                raise ValueError("nieprawidłowe ID sesji")
            if not isinstance(timestamp, str) or not all(
                isinstance(content, str) and content.isprintable() for _, content in notes
            ):
                raise ValueError("nieprawidłowa treść wpisu")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(f"Pominięto uszkodzony wpis {path.name}: {exc}", file=sys.stderr)
            continue
        if (session and recorded_id != session) or (not session and recorded_id in shown):
            continue
        print(f"[{timestamp}] {recorded_id}")
        for label, content in notes:
            print(f"  {label}: {content}")
        shown.add(recorded_id)
        count += 1
        if count == limit:
            break
    if count == 0:
        print("Brak wpisów dla tej sesji." if session else "Brak wpisów w logu projektu.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    identify = commands.add_parser("id", help="pokaż ID sesji lub wygeneruj identyfikator")
    identify.add_argument("--claude-hook", action="store_true", help=argparse.SUPPRESS)

    append = commands.add_parser("append", help="dopisz wpis do logu projektu")
    append.add_argument("--session", type=session_id)
    append.add_argument("--goal", type=short_note, required=True)
    append.add_argument("--decision", type=short_note)
    append.add_argument("--test", type=short_note)
    append.add_argument("--next", type=short_note, required=True)

    latest = commands.add_parser("latest", help="przeczytaj ostatnie wpisy")
    latest.add_argument("--session", type=session_id)
    latest.add_argument("--limit", type=positive_int, default=5)

    args = parser.parse_args()
    if args.command == "id":
        value = claude_session_id() if args.claude_hook else current_session_id() or uuid4().hex
        if value:
            print(value)
        return 0

    try:
        if args.command == "append":
            value = args.session or current_session_id()
            if not value:
                append.error("podaj --session ID. Polecenie id może wygenerować identyfikator")
            path = append_event(log_directory(), value, args)
            print(f"Zapisano wpis {value} w {path}")
        else:
            show_latest(log_directory(), args.limit, args.session)
    except OSError as exc:
        print(f"Błąd logu projektu: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
