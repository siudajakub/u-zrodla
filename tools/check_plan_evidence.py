"""Offline checks for the dated InvestWatch planning probes."""
import hashlib
import json
import re
import struct
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBES = ROOT / "data/probe-snapshots"
INDEX = "2026-11-21-evidence.sha256"
XTB = "https://www.xtb.com/pl/etf"
BOS = "https://bossa.pl/oferta/doradztwo-inwestycyjne"
VIEWS = {(XTB, 390, 844), (XTB, 768, 1024), (XTB, 1440, 900), (BOS, 1440, 900)}
REQUIRED_FILES = {
    "social/2026-11-21-source-check.json", "2026-11-21-discovery-check.json",
    "2026-11-21-additional-sites.json", "2026-11-21-browser-check.json",
    "2026-11-21-browser-files.json", "knf/knf_agenci_prawne.json", "knf/knf_domy_maklerskie.json",
} | {f"browser/{name}.{ext}" for name in ("xtb-390", "xtb-768", "xtb-1440", "bos-1440")
     for ext in ("json", "png")}


def read(base, filename):
    return json.loads((base / filename).read_text(encoding="utf-8"))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify_social(base):
    social = read(base, "social/2026-11-21-source-check.json")
    items_by_url = {}
    for source, count in (("youtube", 15), ("tiktok", 10)):
        runs = [run for run in social["runs"] if run["source"] == source]
        require(len(runs) == 2, f"{source}: expected two readings")
        for run in runs:
            items = run["items"]
            require(run["http"] == 200 and len(items) == count, f"{source}: incomplete reading")
            require(len({i["url"] for i in items}) == len({i["id"] for i in items}) == count,
                    f"{source}: duplicate item")
            for item in items:
                require(item["text_length"] > 0 and re.fullmatch("[0-9a-f]{64}", item["text_sha256"]),
                        f"{source}: missing description evidence")
                items_by_url[item["url"]] = item
        require(runs[0]["items"] == runs[1]["items"], f"{source}: snapshots differ")
    return items_by_url


def verify_discovery(base, items_by_url):
    result = read(base, "2026-11-21-discovery-check.json")
    channels = {row["handle"]: row for row in result["youtube"]}
    require(channels["ComparicRynki"]["readCount"] == 15, "second YouTube watchlist entry")
    links = result["secondTikTok"]["postLinks"]
    require(len(set(links)) == len(links) == 10 and
            all(re.fullmatch(r"https://www\.tiktok\.com/@tradewarspl/video/\d+", url) for url in links),
            "second TikTok watchlist entry")
    claims = channels["DETERMINACJA-OFFICIAL"]["disclosures"]
    require(len({row["url"] for row in claims}) == len({row["publication"] for row in claims}) == 2,
            "M1: two distinct dated publications required")
    require(len({row["textSha256"] for row in claims}) == 1, "M1: two identical descriptions required")
    for claim in claims:
        date = datetime.fromisoformat(claim["publication"])
        require(date.tzinfo is not None and date <= datetime.fromisoformat(result["capturedUtc"]),
                "M1: invalid publication date")
        require(claim["textSha256"] == items_by_url[claim["url"]]["text_sha256"]
                and claim["quote"] == "Partnerem odcinka jest XTB", "M1: joined disclosure missing")
    fetched = {item["url"] for seed in result["discoveries"]
               for item in seed.get("fetched", []) if item.get("htmlSha256")}
    required = {XTB, "https://www.xtb.com/pl/akcje", "https://www.xtb.com/pl/plany-inwestycyjne",
                "https://financewell.pl/o-nas/", "https://bossa.pl/oferta/rynek-zagraniczny/kid"}
    require(required <= fetched, "M2/M3: missing discovered source or negative control")
    bdm = read(base, "2026-11-21-additional-sites.json")["seeds"][0]
    required_bdm = {"https://www.bdm.pl/" + slug for slug in
                    ("rachunek-inwestycyjny", "rachunek-emerytalny", "doradztwo-inwestycyjne")}
    require(bdm["seed"] == "https://www.bdm.pl" and required_bdm ==
            {row["url"] for row in bdm["fetched"] if row["http"] == 200}, "second investment firm")
    firms = {r["id"]: r["name"].split("<")[0] for r in read(base, "knf/knf_domy_maklerskie.json")}
    require(firms.get(6884964) == "DOM MAKLERSKI BDM S.A." and firms.get(6884980) == "XTB S.A.",
            "M2: firms do not match the dated KNF entries")
    agents = read(base, "knf/knf_agenci_prawne.json")
    ids = {row["id"] for row in agents if "FINANCEWELL" in row["name"]
           and any("EVO Dom Maklerski" in str(a.get("value")) for a in row["attributes"])}
    require(ids == {4844186, 4844187}, "M3: two register candidates required")


def verify_views(base):
    initial = {}
    for name in ("2026-11-21-browser-check.json", "2026-11-21-browser-files.json"):
        views = read(base, name)["views"]
        require(len(views) == 4 and {(v["url"], v["width"], v["height"]) for v in views} == VIEWS,
                "missing viewport or firm")
        for view in views:
            key = (view["url"], view["width"], view["height"])
            require(view["http"] == 200 and re.fullmatch("[0-9a-f]{64}", view["domHash"])
                    and re.fullmatch("[0-9a-f]{64}", view["screenshotHash"]), "invalid browser digest")
            for row in view["measurement"]:
                box = row["bbox"]
                require(len(box) == 4 and all(type(x) is int for x in box) and min(box[2:]) > 0,
                        "invalid bounding box")
            if name.endswith("files.json"):
                require(initial[key] == view["measurement"], "geometry differs between the two probes")
                image = (base / view["screenshotFile"]).read_bytes()
                extracted = (base / view["domExtractFile"]).read_bytes()
                require(image[:8] == b'\x89PNG\r\n\x1a\n' and struct.unpack(">II", image[16:24]) ==
                        (view["width"], view["height"]), "PNG dimensions do not match viewport")
                require(sha(image) == view["screenshotHash"] and sha(extracted) == view["domExtractHash"],
                        "stored screenshot or DOM extract does not match its recorded digest")
                require(json.loads(extracted) == {key: view[key] for key in
                        ("url", "width", "height", "measurement")}, "geometry differs from captured extract")
            else:
                initial[key] = view["measurement"]


def verify(base=PROBES):
    index = (base / INDEX).read_bytes()
    rows = [line.split("  ", 1) for line in index.decode().splitlines()]
    require(len(rows) == len(REQUIRED_FILES) and {name for _, name in rows} == REQUIRED_FILES,
            "evidence index missing, duplicated or unexpected files")
    for expected, filename in rows:
        require(sha((base / filename).read_bytes()) == expected, f"archived file changed: {filename}")
    verify_discovery(base, verify_social(base))
    verify_views(base)
    return sha(index)


if __name__ == "__main__":
    print("Planning evidence package SHA-256:", verify())
