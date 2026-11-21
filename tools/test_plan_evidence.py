"""Regression tests for the specific gaps found by the planning reviewers."""
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from check_plan_evidence import INDEX, PROBES, REQUIRED_FILES, verify


class EvidenceReviewTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.base = Path(directory.name)
        for filename in REQUIRED_FILES | {INDEX}:
            dest = self.base / filename
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(PROBES / filename, dest)

    def reseal(self):
        lines = []
        for name in sorted(REQUIRED_FILES):
            digest = hashlib.sha256((self.base / name).read_bytes()).hexdigest()
            lines.append(f"{digest}  {name}\n")
        (self.base / INDEX).write_text("".join(lines))

    def test_clean_package(self):
        self.assertEqual(verify(self.base), verify(PROBES))

    def test_empty_and_duplicate_index(self):
        index = self.base / INDEX
        lines = index.read_text().splitlines(keepends=True)
        for content in ("", "".join(lines[1:] + [lines[1]])):
            index.write_text(content)
            with self.assertRaises(ValueError):
                verify(self.base)

    def test_resealed_invalid_claims(self):
        discovery = "2026-11-21-discovery-check.json"
        old_views = "2026-11-21-browser-check.json"
        new_views = "2026-11-21-browser-files.json"
        bdm = "2026-11-21-additional-sites.json"
        cases = [
            (discovery, lambda d: d["youtube"].pop()),
            (discovery, lambda d: d.pop("secondTikTok")),
            (discovery, lambda d: d["secondTikTok"].update(postLinks=list(map(str, range(10))))),
            (discovery, lambda d: d["youtube"][0]["disclosures"].pop()),
            (discovery, lambda d: d["youtube"][0]["disclosures"][0].update(publication="0")),
            (discovery, lambda d: d["youtube"][0]["disclosures"][0].update(quote="XTB")),
            (discovery, lambda d: d["discoveries"][0]["fetched"].pop()),
            (bdm, lambda d: d["seeds"][0]["fetched"].pop()),
            (new_views, lambda d: d["views"].pop()),
            (new_views, lambda d: d["views"][0].pop("domHash")),
            (new_views, lambda d: d["views"][0].update(screenshotHash="z" * 64)),
            (new_views, lambda d: d["views"][0]["measurement"][0].update(bbox=[0, 0, 10, 20])),
            (old_views, lambda d: d["views"][0]["measurement"][0].update(bbox=[0, 0, 10, 20])),
        ]
        for filename, alter in cases:
            with self.subTest(filename=filename, mutation=alter.__code__.co_firstlineno):
                path = self.base / filename
                data = json.loads(path.read_bytes())
                alter(data)
                path.write_text(json.dumps(data))
                self.reseal()
                with self.assertRaises((ValueError, KeyError)):
                    verify(self.base)
                shutil.copyfile(PROBES / filename, path)

    def test_changed_artifact_bytes(self):
        for filename in ("browser/xtb-390.png", "browser/bos-1440.json"):
            with self.subTest(filename=filename):
                path = self.base / filename
                original = path.read_bytes()
                path.write_bytes(original + b"!")
                with self.assertRaises(ValueError):
                    verify(self.base)
                path.write_bytes(original)


if __name__ == "__main__":
    unittest.main()
