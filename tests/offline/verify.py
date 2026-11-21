"""Three cold Compose starts and a worker-loss drill in private, throwaway state.

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
from uuid import uuid4


def command(args, **kwargs):
    result = run(args, stdout=PIPE, stderr=PIPE, text=True, **kwargs)
    if result.returncode:
        raise RuntimeError(f"{args[:8]}: {result.stderr.strip()[-900:]}")
    return result.stdout.strip()


def code_hash(root):
    files = check_output(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", "api", "analysis", "collectors",
                          "fixtures", "data/probe-snapshots", "web", "tools", "compose.yaml"], cwd=root)
    digest = hashlib.sha256()
    for name in sorted(os.fsdecode(n) for n in files.split(b"\0") if n):
        digest.update(os.fsencode(name) + b"\0")
        digest.update(hashlib.sha256((root/name).read_bytes()).digest())
    return digest.hexdigest()


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
    state, watch = dest/"state", dest/"watch"
    state.mkdir(parents=True, mode=0o700)
    watch.mkdir(mode=0o700)
    db = state/"cases.sqlite3"
    env = {**os.environ, "INVESTWATCH_PORT": str(port), "INVESTWATCH_UID": str(os.getuid()),
           "INVESTWATCH_GID": str(os.getgid()), "INVESTWATCH_DISCOVERY_INTERVAL": "0",
           "INVESTWATCH_PROOF_STATE": str(state), "INVESTWATCH_PROOF_WATCH": str(watch)}
    base = ["docker", "compose", "--project-directory", str(root), "-p", project,
            "-f", str(root/"compose.yaml"), "-f", str(Path(__file__).with_name("compose.yaml"))]

    def dc(*args):
        return command([*base, *args], cwd=root, env=env, timeout=90)

    config = json.loads(dc("config", "--format", "json"))
    assert config["name"] == project and set(config["services"]) == {"api", "worker"}
    network = config["networks"]["default"]
    assert network["internal"] and network["name"] == project+"_default"
    for service in config["services"].values():
        volumes = {v["target"]: v for v in service["volumes"]}
        assert volumes["/data"]["source"] == str(state)
        assert all(v["target"] == "/data" or v.get("read_only") for v in volumes.values())
        assert volumes["/app/.runtime/watch"]["source"] == str(watch)
        assert all(Path(v["source"]).exists() for v in volumes.values())
        assert service["environment"]["INVESTWATCH_DISCOVERY_INTERVAL"] == "0"
        assert float(service["cpus"]) == 1 and service["restart"] == "no"
    ports = config["services"]["api"]["ports"]
    assert len(ports) == 1 and ports[0]["host_ip"] == "127.0.0.1" and ports[0]["published"] == str(port)
    # An internal Docker bridge may deliberately omit host port forwarding.
    # Reach the actual HTTP server over loopback inside its network namespace.
    client = """import json, sys
from urllib.request import Request, urlopen
body = sys.stdin.buffer.read()
request = Request("http://127.0.0.1:8769" + sys.argv[1], data=body or None,
                  headers={"Content-Type": sys.argv[2]})
with urlopen(request, timeout=6) as response:
    sys.stdout.buffer.write(response.read())
"""

    def api(path, body=None, content_type="application/json"):
        r = run([*base, "exec", "-T", "api", "python", "-c", client, path, content_type],
                input=body or b"", stdout=PIPE, stderr=PIPE, env=env, cwd=root, timeout=12)
        if r.returncode:
            raise ConnectionError(r.stderr.decode(errors="replace")[-500:])
        return json.loads(r.stdout)

    def cards():
        try:
            report = api("/v1/state")
        except ConnectionError:
            return None
        terminal = [s for s in report["scans"] if s["mode"] == "replay" and s["status"] == "done"]
        return report if terminal and report["findings"] else None

    def container_stats(service):
        cid = dc("ps", "-q", service)
        inspected = json.loads(command(["docker", "inspect", cid]))[0]
        assert inspected["Config"]["Labels"]["com.docker.compose.project"] == project
        networks = inspected["NetworkSettings"]["Networks"]
        assert list(networks) == [network["name"]]
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
        report = wait(cards, "gotowa kolejka spraw HTTP")
        result["secondsToCases"] = round(time.monotonic()-start, 2)
        findings = report["findings"]
        ids = {f["id"] for f in findings}
        assert {"demo-studio-aurora", "demo-aurora-kod"}.issubset(ids)
        assert len(findings) == len(ids)
        statuses = Counter(f.get("semantic", {}).get("status") for f in findings)
        assert statuses.get("ready", 0) and not statuses.get("unavailable"), statuses
        dup = db_read(db, "select count(*),count(distinct id) from versions")[0]
        assert dup == (len(ids),len(ids))
        scans = db_read(db, "select id,owner,attempts,mode,status from scans")
        assert len(scans) == 1 and scans[0][3:] == ("replay", "done")
        assert scans[0][2] == (2 if index == 3 else 1)
        if index == 3:
            assert scans[0][0] == scan_id and scans[0][1] != owner
            result["recovery"].update(ownersDiffer=True, attempts=2, versions=len(ids),
                                      distinctCases=len(ids), terminalScans=1)
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
              "timeBasis": "monotonic, docker compose up to populated HTTP /v1/state",
              "network": "Docker internal; HTTP probe over loopback inside the API container", "trials": []}
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
