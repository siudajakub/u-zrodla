"""Stan startu pokazu z API: skany, kolejka review, E5. Tylko biblioteka standardowa (Python 3.8+).

    python3 ops/demo/queue_status.py --port 8769 [--expect-count 4] [--expect-ids ID,ID,...] [--require-ids ID,...] [--json]

Kod wyjścia: 0 = skany bootstrapu zakończone i kolejka zgodna z oczekiwaniem, 1 = jeszcze trwa lub niezgodna,
2 = API nie odpowiada.
"""
import argparse
import json
import sys
import urllib.request

KNOWN = "7M0rC6-Rueo,AqXHkxDzSDI,OIyPE0z2mng,ZJrT-X08Xwc"


def get(url):
    with urllib.request.urlopen(url, timeout=15) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default="8769")
    parser.add_argument("--min-scans", type=int, default=2, help="ile skanów bootstrapu musi istnieć (m2 + youtube replay)")
    parser.add_argument("--expect-count", type=int)
    parser.add_argument("--expect-ids", default=None, help="po przecinku; domyślnie cztery znane filmy, gdy podano --expect-count")
    parser.add_argument("--require-ids", default=None,
                        help="po przecinku; te pozycje muszą być w kolejce (inne mogą być obok, np. oferty M2/M3); 'known' = cztery filmy")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    base = f"http://127.0.0.1:{args.port}"
    try:
        state = get(base + "/v1/state")
        queue = get(base + "/v1/queues/review")
    except Exception as error:  # noqa: BLE001 - diagnostyka dla operatora
        print(f"api=niedostepne ({type(error).__name__})")
        return 2
    scans = state.get("scans", [])
    busy = [s for s in scans if s.get("status") in ("queued", "running")]
    ids = sorted(i["id"].split(":", 1)[-1] for i in queue.get("items", []))
    media = next((s for s in state.get("sources", []) if s.get("id") == "replay-media"), None)
    semantic = (state.get("semantic") or {}).get("status")
    report = {"scans": len(scans), "busy": len(busy), "reviewTotal": queue.get("total"), "reviewIds": ids,
              "counts": queue.get("counts"), "variant": (queue.get("threshold") or {}).get("variant"),
              "mediaPack": media and {"status": media.get("status"), "videos": media.get("count")},
              "semantic": semantic}
    ready = len(scans) >= args.min_scans and not busy
    ok = ready
    if args.expect_count is not None:
        want = sorted((args.expect_ids or KNOWN).split(","))
        ok = ready and queue.get("total") == args.expect_count and ids == want
    if args.require_ids:
        need = set((KNOWN if args.require_ids == "known" else args.require_ids).split(","))
        ok = ok and need.issubset(ids)
    if args.json:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print("scans={scans} busy={busy} review={reviewTotal} ids={ids} variant={variant} mediaPack={mediaPack} semantic={semantic}".format(
            **{**report, "ids": ",".join(ids)}))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
