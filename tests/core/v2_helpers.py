"""Shared fixtures for the v2 contract tests (docs/lanes/2026-11-21-fable-h-kontrakt.md).

Every test runs on a private temporary SQLite state and never touches .runtime/demo.
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import threading
import time
import types
import unittest
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from api import store

ROOT = Path(__file__).resolve().parents[2]
V1_COMMIT = "491094d"
VIDEO = "youtube:AAAAAAAAAAA"


NO_CAPTIONS = {"transcript": {"state": "unavailable", "source": "none", "windows": [], "durationSec": None,
                              "reason": "no_captions: brak napisów po polsku"},
               "frames": {"state": "not_collected", "moments": [], "intervalSec": None}}


def capture(id=VIDEO, **extra):
    """A YouTube capture whose transcript is permanently unavailable (the speech gate is open); pass
    mediaCoverage=None for a video whose transcript is still to be fetched."""
    base = {"id": id, "creatorId": "youtube:UCexampleexampleexample00", "title": "Tytuł", "description": "Opis filmu.",
            "url": "https://www.youtube.com/watch?v=AAAAAAAAAAA", "module": "M1", "platform": "youtube",
            "publishedAt": "2026-11-01T10:00:00+00:00", "observedAt": "2026-11-21T10:00:00+00:00",
            "provenance": {"sourceUrl": "https://example.org/atom", "mode": "live"}, "mediaCoverage": NO_CAPTIONS}
    merged = {**base, **extra}
    if merged.get("mediaCoverage") is None:
        del merged["mediaCoverage"]
    return merged


def finding(cap, **extra):
    base = {"id": cap["id"], "title": cap["title"], "module": cap.get("module", "M1"), "score": 30,
            "summary": "Streszczenie.", "evidence": [], "rulesVersion": "investwatch-rules-pl-1.2"}
    return {**base, **extra}


def load_v1_store(state_dir):
    """Import api/store.py exactly as committed at 491094d, bound to state_dir."""
    try:
        source = subprocess.run(["git", "show", f"{V1_COMMIT}:api/store.py"], cwd=ROOT, capture_output=True,
                                text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        raise unittest.SkipTest(f"brak commitu {V1_COMMIT} w repozytorium")
    module = types.ModuleType("store_v1")
    module.__file__ = str(ROOT / "api" / "store.py")
    with patch.dict(os.environ, {"INVESTWATCH_STATE": str(state_dir)}):
        exec(compile(source, "store_v1", "exec"), module.__dict__)
    return module


class StateCase(unittest.TestCase):
    """A fresh migrated database per test."""

    def setUp(self):
        self.temp = self.enterContext(TemporaryDirectory())
        self.enterContext(patch.object(store, "STATE", Path(self.temp)))
        # Replay must not pick up the real replay media pack of this host (it lives in .runtime, outside Git).
        self.enterContext(patch.dict(os.environ, {"INVESTWATCH_REPLAY_MEDIA": str(Path(self.temp) / "replay-media-absent")}))
        store.init()

    def scan(self, pairs, mode="live", creators=(), sources=()):
        with store.connection(True) as db:
            return store.apply_scan(db, list(pairs), list(creators), list(sources), mode)

    def put(self, cap=None, mode="live", **extra):
        cap = cap or capture()
        return self.scan([(cap, finding(cap, **extra))], mode)

    def case(self, key=VIDEO):
        with store.connection() as db:
            row = db.execute("SELECT * FROM cases WHERE id=?", (key,)).fetchone()
            return store.case_dict(db, row)

    def events(self, kind=None):
        with store.connection() as db:
            rows = store.events_since(db, 0, 1000)
        return [e for e in rows if kind is None or e["kind"] == kind]

    def versions(self, key=VIDEO):
        with store.connection() as db:
            return db.execute("SELECT count(*) FROM versions WHERE id=?", (key,)).fetchone()[0]


class HttpCase(StateCase):
    """The real app on a loopback socket, same approach as test_site_routes."""

    def setUp(self):
        super().setUp()
        import uvicorn
        from api import server
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        sock.listen(128)
        self.enterContext(sock)
        self.base = "http://127.0.0.1:" + str(sock.getsockname()[1])
        self.web = uvicorn.Server(uvicorn.Config(server.app, log_level="error", lifespan="off"))
        self.thread = threading.Thread(target=self.web.run, kwargs={"sockets": [sock]}, daemon=True)
        self.thread.start()
        for _ in range(100):
            if self.web.started:
                break
            time.sleep(.02)
        self.assertTrue(self.web.started)
        self.addCleanup(self.stop_server)

    def stop_server(self):
        self.web.should_exit = True
        self.thread.join(5)

    def request(self, method, path, data=None):
        body = json.dumps(data).encode() if data is not None else None
        req = Request(self.base + path, data=body, method=method, headers={"Content-Type": "application/json"})
        try:
            with urlopen(req, timeout=4) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            raw = error.read()
            try:
                return error.code, json.loads(raw)
            except ValueError:
                return error.code, {"raw": raw.decode("utf-8", "replace")}
