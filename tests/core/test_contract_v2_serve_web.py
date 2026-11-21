"""INVESTWATCH_SERVE_WEB=0: the API does not mount "/" (Compose serves the desk elsewhere); the default keeps serving it."""
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
CODE = ("import sys; sys.path.insert(0, %r); from api import server; "
        "print(any(getattr(r, 'name', '') == 'desk' for r in server.app.routes))" % str(ROOT))


def mounted(flag):
    env = {**os.environ, "PYTHONPATH": str(ROOT), "INVESTWATCH_STATE": os.environ.get("INVESTWATCH_STATE", "/tmp/iw-serve-web")}
    if flag is None:
        env.pop("INVESTWATCH_SERVE_WEB", None)
    else:
        env["INVESTWATCH_SERVE_WEB"] = flag
    out = subprocess.run([sys.executable, "-B", "-c", CODE], env=env, cwd=ROOT, capture_output=True, text=True, timeout=60)
    return out.stdout.strip().splitlines()[-1] == "True"


class ServeWeb(unittest.TestCase):
    def test_flag_zero_leaves_slash_unmounted_and_default_serves_the_desk(self):
        self.assertFalse(mounted("0"))
        self.assertTrue(mounted(None))
        self.assertTrue(mounted("1"))


if __name__ == "__main__":
    unittest.main()
