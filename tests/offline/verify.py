"""Three cold Compose starts (web -> api -> worker) and a worker-loss drill in private, throwaway state.

Run on the host with prepared demo dependencies and the Docker daemon:
python3 tests/offline/verify.py --root /absolute/path/to/integration
Only starts and stops containers belonging to the random proof project.
"""
import argparse
from collections import Counter
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from subprocess import check_output, run, PIPE
import tempfile
import time
from urllib.error import URLError
from urllib.request import Request, urlopen
from uuid import uuid4


def command(args, **kwargs):
    result = run(args, stdout=PIPE, stderr=PIPE, text=True, **kwargs)
    if result.returncode:
        raise RuntimeError(f"{args[:8]}: {result.stderr.strip()[-900:]}")
    return result.stdout.strip()


def code_hash(root):
    files = check_output(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", "api", "analysis", "collectors",
                          "fixtures", "data/probe-snapshots", "web", "tools", "compose.yaml", "ops/web"], cwd=root)
    digest = hashlib.sha256()
    for name in sorted(os.fsdecode(n) for n in files.split(b"\0") if n):
        if not (root/name).is_file():
            continue  # plik śledzony, usunięty w katalogu roboczym: nie jest montowany
        digest.update(os.fsencode(name) + b"\0")
        digest.update(hashlib.sha256((root/name).read_bytes()).digest())
    return digest.hexdigest()


OBJECT_DIRS = ("uploads", "m2", "media-cache", "meta-import", "youtube-raw", "youtube-cache")  # compose.yaml: objects
KNOWN_REVIEW = {"7M0rC6-Rueo", "AqXHkxDzSDI", "OIyPE0z2mng", "ZJrT-X08Xwc"}
BOOTSTRAP_SCANS = 2  # co najmniej bootstrap-m2-rendered-v1 i bootstrap-youtube-replay-v1; worker (api/jobs.py: work) może zlecić więcej


def wait(fn, description, timeout=90, interval=.15):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        result = fn()
        if result:
            return result
        time.sleep(interval)
    raise RuntimeError("Przekroczono czas oczekiwania: " + description)


def db_read(path, query, args=()):
    if not path.is_file():
        return []
    try:
        with closing(sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=2)) as db:
            return db.execute(query, args).fetchall()
    except sqlite3.OperationalError as err:
        if "no such table" in str(err):
            return []
        raise


def once(root, dest, port, index):
    project = "investwatch-proof-" + uuid4().hex[:14]
    state, watch, objects = dest/"state", dest/"watch", dest/"objects"
    state.mkdir(parents=True, mode=0o700)
    watch.mkdir(mode=0o700)
    for sub in OBJECT_DIRS:  # punkty montowania i katalogi obiektów zakłada właściciel, nie demon Dockera (root)
        (state/sub).mkdir()
        (objects/sub).mkdir(parents=True)
    db = state/"cases.sqlite3"
    env = {**os.environ, "INVESTWATCH_PORT": str(port), "INVESTWATCH_UID": str(os.getuid()),
           "INVESTWATCH_GID": str(os.getgid()), "INVESTWATCH_DISCOVERY_INTERVAL": "0",
           "INVESTWATCH_MEDIA_PACK": str(Path(os.environ.get("INVESTWATCH_REPLAY_MEDIA") or root/".runtime/replay-media/2026-11-21")),
           "INVESTWATCH_PROOF_STATE": str(state), "INVESTWATCH_PROOF_WATCH": str(watch),
           "INVESTWATCH_OBJECTS_DIR": str(objects)}
    base = ["docker", "compose", "--project-directory", str(root), "-p", project,
            "-f", str(root/"compose.yaml"), "-f", str(Path(__file__).with_name("compose.yaml"))]

    def dc(*args):
        return command([*base, *args], cwd=root, env=env, timeout=90)

    config = json.loads(dc("config", "--format", "json"))
    assert config["name"] == project and set(config["services"]) == {"web", "api", "worker"}
    network = config["networks"]["backend"]
    assert network["internal"] and network["name"] == project+"_backend"
    assert not config["networks"]["edge"].get("internal")
    web = config["services"]["web"]
    assert set(web["networks"]) == {"edge", "backend"} and web["read_only"] and web["cap_drop"] == ["ALL"]
    assert all(v.get("read_only") for v in web["volumes"])
    writable = {"/data"} | {"/data/"+sub for sub in OBJECT_DIRS}
    for name, service in config["services"].items():
        if name == "web":
            continue
        assert set(service["networks"]) == {"backend"} and "ports" not in service, name
        assert service["read_only"] and service["cap_drop"] == ["ALL"]
        volumes = {v["target"]: v for v in service["volumes"]}
        assert volumes["/data"]["source"] == str(state)
        assert all(volumes["/data/"+sub]["source"] == str(objects/sub) for sub in OBJECT_DIRS)
        assert all(v["target"] in writable or v.get("read_only") for v in volumes.values())
        assert "/app/web" not in volumes, "api i worker nie dostają plików frontu"
        assert volumes["/app/.runtime/watch"]["source"] == str(watch)
        assert all(Path(v["source"]).exists() for v in volumes.values())
        pack = volumes["/replay-media"]
        assert pack["read_only"] and (Path(pack["source"])/"MANIFEST.json").is_file(), "brak paczki mediów replay"
        assert service["environment"]["INVESTWATCH_REPLAY_MEDIA"] == "/replay-media"
        assert service["environment"]["INVESTWATCH_DISCOVERY_INTERVAL"] == "0"
        assert float(service["cpus"]) == 1 and service["restart"] == "no"
    ports = web["ports"]
    assert len(ports) == 1 and ports[0]["host_ip"] == "127.0.0.1" and ports[0]["published"] == str(port)
    # Every HTTP read goes the user's way: host loopback -> web (nginx) -> api on the internal network.

    def api(path, body=None, content_type="application/json"):
        request = Request(f"http://127.0.0.1:{port}{path}", data=body or None, headers={"Content-Type": content_type})
        try:
            with urlopen(request, timeout=12) as response:
                return json.loads(response.read())
        except (URLError, OSError) as err:
            raise ConnectionError(str(err)) from err

    def cards():
        # Skany czytamy wprost z bazy (lekko); kolejkę i stan dopiero po zakończeniu obu skanów bootstrapu.
        rows = db_read(db, "select status from scans where mode='replay'")
        if len(rows) < BOOTSTRAP_SCANS or any(r[0] not in ("done", "partial") for r in rows):
            return None
        try:
            return {"state": api("/v1/state"), "review": api("/v1/queues/review")}
        except ConnectionError:
            return None

    def container_stats(service):
        cid = dc("ps", "-q", service)
        inspected = json.loads(command(["docker", "inspect", cid]))[0]
        assert inspected["Config"]["Labels"]["com.docker.compose.project"] == project
        networks = inspected["NetworkSettings"]["Networks"]
        assert list(networks) == [network["name"]], networks
        stats = dc("exec", "-T", service, "python", "-c",
            "from pathlib import Path; p=Path('/sys/fs/cgroup'); print((p/'memory.peak').read_text().strip() "
            "if (p/'memory.peak').is_file() else 0)")
        return {"oomKilled": inspected["State"]["OOMKilled"], "memoryPeakBytes": int(stats),
                "restartCount": inspected["RestartCount"]}

    result = {"trial": index, "project": project}
    try:
        start = time.monotonic()
        dc("up", "-d", "--no-build", "--pull", "never")
        network_state = json.loads(command(["docker", "network", "inspect", network["name"]]))[0]
        assert network_state["Internal"] and network_state["Labels"]["com.docker.compose.project"] == project
        if index == 3:
            running = wait(lambda: db_read(db, "select id,owner from scans where mode='replay' and status='running'"),
                           "worker przejął bootstrap", interval=.015)
            scan_id, owner = running[0]
            dc("kill", "-s", "SIGKILL", "worker")
            # The only write performed by the drill is expiring its own interrupted claim.
            with closing(sqlite3.connect(db)) as audit:
                changed = audit.execute("update scans set lease_until=0 where id=? and owner=? and status='running'",
                                        (scan_id, owner)).rowcount
                assert changed == 1, "worker ukończył próbę przed wymuszoną przerwą"
                audit.commit()
            dc("start", "worker")
            result["recovery"] = {"interrupted": True, "simulatedExpiry": True}
        both = wait(cards, "gotowa kolejka spraw HTTP", timeout=1500, interval=2)
        report, review = both["state"], both["review"]
        result["secondsToCases"] = round(time.monotonic()-start, 2)
        review_ids = {i["id"].split(":", 1)[-1] for i in review["items"]}
        # Cztery znane filmy muszą być w kolejce; obok nich mogą stać oferty M2/M3 (kolejka review łączy moduły).
        assert KNOWN_REVIEW.issubset(review_ids), (review["total"], sorted(review_ids))
        result["reviewTotal"] = review["total"]
        assert report["semantic"]["status"] == "ready", report["semantic"]
        pack_source = next(x for x in report["sources"] if x["id"] == "replay-media")
        assert pack_source["status"] == "ok" and pack_source["count"] == 17, pack_source
        result["queues"] = review["counts"]
        result["variant"] = review["threshold"]["variant"]
        findings = report["findings"]
        ids = {f["id"] for f in findings}
        assert {"demo-studio-aurora", "demo-aurora-kod"}.issubset(ids)
        assert len(findings) == len(ids)
        statuses = Counter(f.get("semantic", {}).get("status") for f in findings)
        assert statuses.get("ready", 0), statuses
        dup = db_read(db, "select count(*),count(distinct id) from versions")[0]
        # Wersje: bez luk i duplikatów numeracji; nadmiarowe wersje to dowód z transkrypcji (changeKind evidence), nie powtórzenie skanu.
        gaps = db_read(db, "select count(*) from versions v where v.version > (select count(*) from versions w where w.id=v.id)")[0][0]
        assert dup[1] == len(ids) and gaps == 0, (dup, gaps)
        result["extraVersions"] = dup[0]-dup[1]
        scans = db_read(db, "select id,owner,attempts,mode,status from scans")
        assert len(scans) >= BOOTSTRAP_SCANS and all(s[3] == "replay" and s[4] in ("done", "partial") for s in scans), scans
        by_id = {s[0]: s for s in scans}
        if index == 3:
            assert by_id[scan_id][1] != owner and by_id[scan_id][2] == 2
            assert all(s[2] == 1 for s in scans if s[0] != scan_id)
            result["recovery"].update(ownersDiffer=True, attempts=2, versions=len(ids),
                                      distinctCases=len(ids), terminalScans=len(scans))
        else:
            assert all(s[2] == 1 for s in scans)
        result.update(cases=len(ids), versions=dup[0], semantic=dict(statuses), offline=True)
        if index == 1:
            source = root/"analysis/media/wezwanie.mp4"
            submitted = api("/v1/media?title=Test%20offline&filename=test.mp4&description=Opis",
                            source.read_bytes(), "application/octet-stream")
            key = submitted["scanId"]
            def uploaded():
                record = api("/v1/state")
                scan = next(s for s in record["scans"] if s["id"] == key)
                assert scan["status"] != "failed", scan
                return next((f for f in record["findings"] if f["id"] == "upload-"+key), None)
            finding = wait(uploaded, "inferencja ASR na przesłanym pliku", timeout=35)
            audio = next(e for e in finding["evidence"] if e["kind"] == "audio" and "aurora" in e["text"])
            assert audio["start"] >= 0 and audio["end"] > audio["start"]
            result["uploadASR"] = {"done": True, "start": audio["start"], "end": audio["end"]}
        result["resources"] = {svc: container_stats(svc) for svc in ("api", "worker")}
        assert all(not v["oomKilled"] for v in result["resources"].values())
        return result
    finally:
        dc("down", "--timeout", "2")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--port", type=int, default=18771)
    parser.add_argument("--fingerprint-only", action="store_true", help="Sprawdź wyłącznie rzeczywisty odcisk kodu w montowanych ścieżkach.")
    args = parser.parse_args()
    root = args.root.resolve()
    if args.fingerprint_only:
        print(code_hash(root))
        return
    if not __debug__:
        raise SystemExit("Uruchom ten test bez flagi -O, aby wszystkie asercje pozostały aktywne.")
    scratch = root/".runtime"/"proof"
    scratch.mkdir(parents=True, mode=0o700, exist_ok=True)
    dest = Path(tempfile.mkdtemp(prefix="cold-", dir=scratch))
    before = code_hash(root)
    report = {"gitAtStart": command(["git", "rev-parse", "HEAD"], cwd=root), "codeSha256": before,
              "timeBasis": "monotonic, docker compose up to obu skanów bootstrapu zakończonych i kolejki review z 4 filmami (HTTP)",
              "network": "api/worker on an internal Docker network; HTTP probe from the host through the web proxy", "trials": []}
    for i in (1, 2, 3):
        record = once(root, dest/f"trial-{i}", args.port, i)
        report["trials"].append(record)
        print(json.dumps(record), flush=True)
    report["gitAtEnd"] = command(["git", "rev-parse", "HEAD"], cwd=root)
    report["codeSha256AtEnd"] = code_hash(root)
    (dest/"report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False)+"\n")
    print(dest/"report.json")
    assert report["codeSha256AtEnd"] == before, "Kod produktu zmienił się podczas prób; powtórz na zamrożonej wersji."


if __name__ == "__main__":
    main()
