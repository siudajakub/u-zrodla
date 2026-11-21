"""Regression tests for the project context kit."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import check_agent_docs
import session_log


class AgentContextTest(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.env = {
            key: value for key, value in os.environ.items()
            if key not in {"INVESTWATCH_SESSION_ID", "CODEX_THREAD_ID", "CODEX_SESSION_ID"}
        }
        for relative in ("tools/session_log.py", "tools/hack_context.sh", "tools/hack_status.py"):
            target = self.root / relative
            target.parent.mkdir(exist_ok=True)
            shutil.copyfile(check_agent_docs.ROOT / relative, target)

    def run_ok(self, *args, env=None, payload=None):
        result = subprocess.run(
            args, cwd=self.root, env=self.env if env is None else env, input=payload,
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        return result.stdout

    def test_mirror_detects_drift_and_syncs(self):
        agents = self.root / "AGENTS.md"
        claude = self.root / "CLAUDE.md"
        agents.write_bytes(b"# Canonical rules\n")
        claude.write_bytes(b"# Divergent rules\n")
        errors = []

        with patch.object(check_agent_docs, "ROOT", self.root):
            check_agent_docs.check_claude_mirror(False, errors)
            self.assertIn("CLAUDE.md differs from AGENTS.md", errors[0])
            self.assertEqual(claude.read_bytes(), b"# Divergent rules\n")

            check_agent_docs.check_claude_mirror(True, [])
            self.assertEqual(claude.read_bytes(), check_agent_docs.CLAUDE_HEADER + agents.read_bytes())
            errors.clear()
            check_agent_docs.check_claude_mirror(False, errors)
            self.assertEqual(errors, [])

            agents.write_bytes(b"# Updated canonical rules\n")
            check_agent_docs.check_claude_mirror(False, errors)
            self.assertIn("CLAUDE.md differs from AGENTS.md", errors[0])

    def test_concurrent_appends_and_latest(self):
        self.run_ok("git", "init", "-q")
        command = (sys.executable, "tools/session_log.py")

        def append(index):
            self.run_ok(*command, "append", "--session", f"session-{index % 3}",
                        "--goal", f"Cel {index}", "--next", f"Krok {index}")

        with ThreadPoolExecutor(max_workers=4) as workers:
            list(workers.map(append, range(18)))

        paths = list((self.root / "session-logs").iterdir())
        self.assertEqual(len(paths), 18)
        self.assertTrue(all(path.suffix == ".jsonl" for path in paths))
        records = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
        self.assertEqual({record["goal"] for record in records}, {f"Cel {i}" for i in range(18)})

        latest = self.run_ok(*command, "latest")
        self.assertEqual(latest.count("Cel:"), 3)
        history = self.run_ok(*command, "latest", "--session", "session-1", "--limit", "10")
        self.assertEqual(history.count("Cel:"), 6)
        self.assertNotIn("session-0", history)

    def test_linked_worktree_uses_primary_checkout(self):
        primary = self.root / "primary checkout"
        linked = self.root / "linked checkout"
        output = f"worktree {primary}\0\0worktree {linked}\0\0".encode()
        worktrees = subprocess.CompletedProcess("git", 0, stdout=output)
        with patch.object(session_log, "ROOT", linked), patch.object(
            session_log.subprocess, "run", return_value=worktrees
        ):
            self.assertEqual(session_log.log_directory(), primary / "session-logs")

    def test_cold_start_and_claude_hooks(self):
        self.run_ok("git", "init", "-q")
        env = {**self.env, "CODEX_THREAD_ID": "codex-test"}
        self.run_ok(sys.executable, "tools/session_log.py", "append",
                    "--goal", "Cel Codex", "--next", "Krok Codex", env=env)

        start = self.run_ok("sh", "tools/hack_context.sh")
        self.assertIn("Bootstrap:", start)
        self.assertIn("codex-test", start)

        settings = check_agent_docs.ROOT / ".claude/settings.json"
        hooks = json.loads(settings.read_text(encoding="utf-8"))["hooks"]
        env_file = self.root / "claude-env"
        env = {**self.env, "CLAUDE_PROJECT_DIR": str(self.root), "CLAUDE_ENV_FILE": str(env_file)}
        payload = json.dumps({"session_id": "test", "transcript_path": "private-transcript.jsonl"})
        command = hooks["SessionStart"][0]["hooks"][0]["command"]
        start = self.run_ok("sh", "-c", command, env=env, payload=payload)
        self.assertIn("claude-test", start)
        self.assertIn("Cel Codex", start)
        self.assertNotIn("private-transcript.jsonl", start)
        self.assertEqual(env_file.read_text(encoding="utf-8"), "export INVESTWATCH_SESSION_ID='claude-test'\n")

        self.run_ok("sh", "-c", '. "$CLAUDE_ENV_FILE" && python3 tools/session_log.py append '
                    '--goal "Cel Claude" --next "Krok Claude"', env=env)
        command = hooks["PreCompact"][0]["hooks"][0]["command"]
        precompact = self.run_ok("sh", "-c", command, env=env, payload=payload)
        self.assertIn("podsumowaniu", precompact)
        self.assertIn("Cel Claude", precompact)
        self.assertNotIn("private-transcript.jsonl", precompact)


if __name__ == "__main__":
    unittest.main()
