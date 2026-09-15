#!/usr/bin/env python3
"""Behavior tests for the project-state gate."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / "tools" / "project_state_gate.py"
STATE = Path("docs/PROJECT_STATE.md")
GOOD = "# State\n\n## Resume point\nready\n\n## Next action\ncontinue\n"
BAD = "# State\n\n## Resume point\n\n## Next action\ncontinue\n"


def run(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=repo, check=check, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


class ProjectStateGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        run(self.repo, "git", "init", "-q")
        run(self.repo, "git", "config", "user.name", "Gate Test")
        run(self.repo, "git", "config", "user.email", "gate@example.invalid")
        (self.repo / "tools").mkdir()
        shutil.copy2(SOURCE, self.repo / "tools" / "project_state_gate.py")
        (self.repo / STATE).parent.mkdir()
        (self.repo / STATE).write_text(GOOD, encoding="utf-8")
        (self.repo / "base.txt").write_text("base\n", encoding="utf-8")
        run(self.repo, "git", "add", ".")
        run(self.repo, "git", "commit", "-qm", "base")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def gate(self, *args: str) -> subprocess.CompletedProcess[str]:
        return run(self.repo, "python3", "tools/project_state_gate.py", *args, check=False)

    def test_staged_bytes_are_validated_not_worktree(self) -> None:
        (self.repo / "base.txt").write_text("changed\n", encoding="utf-8")
        (self.repo / STATE).write_text(BAD, encoding="utf-8")
        run(self.repo, "git", "add", "base.txt", str(STATE))
        (self.repo / STATE).write_text(GOOD, encoding="utf-8")
        result = self.gate("--staged")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Resume point must not be empty", result.stderr)

    def test_missing_staged_state_update_fails(self) -> None:
        (self.repo / "base.txt").write_text("changed\n", encoding="utf-8")
        run(self.repo, "git", "add", "base.txt")
        result = self.gate("--staged")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not update", result.stderr)

    def test_valid_staged_state_passes(self) -> None:
        (self.repo / "base.txt").write_text("changed\n", encoding="utf-8")
        (self.repo / STATE).write_text(GOOD + "more\n", encoding="utf-8")
        run(self.repo, "git", "add", "base.txt", str(STATE))
        result = self.gate("--staged")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_range_validates_state_from_each_commit(self) -> None:
        parent = run(self.repo, "git", "rev-parse", "HEAD").stdout.strip()
        (self.repo / "base.txt").write_text("changed\n", encoding="utf-8")
        (self.repo / STATE).write_text(BAD, encoding="utf-8")
        run(self.repo, "git", "add", "base.txt", str(STATE))
        run(self.repo, "git", "commit", "-qm", "bad state")
        head = run(self.repo, "git", "rev-parse", "HEAD").stdout.strip()
        (self.repo / STATE).write_text(GOOD, encoding="utf-8")
        result = self.gate("--base", parent, "--head", head)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Resume point must not be empty", result.stderr)


if __name__ == "__main__":
    unittest.main()
