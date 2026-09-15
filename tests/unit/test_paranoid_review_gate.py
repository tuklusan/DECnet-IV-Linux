#!/usr/bin/env python3
"""Behavior tests for the independent review gate."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / "tools" / "paranoid_review_gate.py"
RECEIPT = Path("reviews/CHECKIN_REVIEW.json")


def run(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=repo, check=check, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


class ReviewGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        run(self.repo, "git", "init", "-q")
        run(self.repo, "git", "config", "user.name", "Gate Test")
        run(self.repo, "git", "config", "user.email", "gate@example.invalid")
        (self.repo / "tools").mkdir()
        shutil.copy2(SOURCE, self.repo / "tools" / "paranoid_review_gate.py")
        (self.repo / "base.txt").write_text("base\n", encoding="utf-8")
        (self.repo / "other.txt").write_text("other\n", encoding="utf-8")
        run(self.repo, "git", "add", ".")
        run(self.repo, "git", "commit", "-qm", "base")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def gate(self, *args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
        return run(self.repo, "python3", "tools/paranoid_review_gate.py", *args, check=check)

    def write_receipt_from_template(self) -> dict:
        receipt = json.loads(self.gate("--staged", "--template", check=True).stdout)
        (self.repo / RECEIPT).parent.mkdir(exist_ok=True)
        (self.repo / RECEIPT).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        run(self.repo, "git", "add", str(RECEIPT))
        return receipt

    def stage_reviewed_change(self) -> dict:
        (self.repo / "base.txt").write_text("changed\n", encoding="utf-8")
        run(self.repo, "git", "add", "base.txt")
        return self.write_receipt_from_template()

    def test_valid_staged_receipt_passes(self) -> None:
        self.stage_reviewed_change()
        result = self.gate("--staged")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_full_tree_content_change_invalidates_receipt(self) -> None:
        self.stage_reviewed_change()
        (self.repo / "other.txt").write_text("changed after review\n", encoding="utf-8")
        run(self.repo, "git", "add", "other.txt")
        result = self.gate("--staged")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("reviewed_tree does not match", result.stderr)

    def test_mode_change_invalidates_receipt(self) -> None:
        receipt = self.stage_reviewed_change()
        run(self.repo, "git", "update-index", "--chmod=+x", "base.txt")
        result = self.gate("--staged")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("reviewed_tree does not match", result.stderr)
        self.assertEqual(receipt["reviewed_tree"]["base.txt"]["mode"], "100644")

    def test_deletion_is_bound_by_full_tree(self) -> None:
        run(self.repo, "git", "rm", "-q", "base.txt")
        receipt = self.write_receipt_from_template()
        self.assertNotIn("base.txt", receipt["reviewed_tree"])
        result = self.gate("--staged")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_receipt_fails(self) -> None:
        (self.repo / "base.txt").write_text("changed\n", encoding="utf-8")
        run(self.repo, "git", "add", "base.txt")
        result = self.gate("--staged")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not update", result.stderr)

    def test_receipt_only_commit_fails(self) -> None:
        (self.repo / RECEIPT).parent.mkdir(exist_ok=True)
        (self.repo / RECEIPT).write_text("{}\n", encoding="utf-8")
        run(self.repo, "git", "add", str(RECEIPT))
        result = self.gate("--staged")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("receipt-only", result.stderr)

    def test_invalid_finding_severity_fails(self) -> None:
        receipt = self.stage_reviewed_change()
        receipt["findings"] = [{"severity": "MINOR", "summary": "not allowed", "programmer_disposition": "ignored"}]
        (self.repo / RECEIPT).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        run(self.repo, "git", "add", str(RECEIPT))
        result = self.gate("--staged")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("severity must be BLOCKER, CRITICAL, or MAJOR", result.stderr)

    def test_nonclean_sop_pass_fails(self) -> None:
        receipt = self.stage_reviewed_change()
        receipt["sop_clean_passes"] = ["clean", "dirty", "clean"]
        (self.repo / RECEIPT).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        run(self.repo, "git", "add", str(RECEIPT))
        result = self.gate("--staged")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("may contain only 'clean'", result.stderr)

    def test_unknown_receipt_field_fails(self) -> None:
        receipt = self.stage_reviewed_change()
        receipt["surprise"] = "nope"
        (self.repo / RECEIPT).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        run(self.repo, "git", "add", str(RECEIPT))
        result = self.gate("--staged")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unknown receipt field", result.stderr)

    def test_committed_range_passes(self) -> None:
        self.stage_reviewed_change()
        parent = run(self.repo, "git", "rev-parse", "HEAD").stdout.strip()
        run(self.repo, "git", "commit", "-qm", "reviewed change")
        head = run(self.repo, "git", "rev-parse", "HEAD").stdout.strip()
        result = self.gate("--base", parent, "--head", head)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
