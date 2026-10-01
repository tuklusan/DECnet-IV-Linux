#!/usr/bin/env python3
# ============================================================================
# Copyright (c) 2026 Supratim Sanyal of SANYALnet Labs.
# Proprietary rights reserved except as expressly licensed herein.
#
# DECnet-IV-Linux
# This file is governed by the SANYALnet Labs Non-Commercial License in the
# root LICENSE file. Non-Commercial use is permitted; Commercial Use and use
# for AI/ML model training are prohibited unless separately authorized.
#
# Attribution is required: "Based on original work by Supratim Sanyal of
# SANYALnet Labs." See LICENSE for full terms, warranty disclaimer, termination,
# patent, trademark, and governing-law provisions.
# ============================================================================

"""Executable false-green regressions for exact-source acceptance controls."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INTEGRITY = ROOT / "tools" / "integrity_scan.py"
SCRATCH = ROOT / "tools" / "scratch_state.py"
WORKFLOW_GUARD = ROOT / "tools" / "workflow_guard.sh"


def run(root: Path, *args: str, check: bool = True, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=root,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )


def expect_failure(result: subprocess.CompletedProcess[str], marker: str, label: str) -> None:
    output = result.stdout + result.stderr
    if result.returncode == 0 or marker not in output:
        raise SystemExit(f"false-green regression did not reject {label}: {output}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="dniv-false-green-") as temporary:
        root = Path(temporary)
        run(root, "git", "init", "-q", "-b", "main")
        run(root, "git", "config", "user.name", "False Green Test")
        run(root, "git", "config", "user.email", "false-green@example.invalid")

        payload = root / "payload.txt"
        payload.write_text("base\n", encoding="utf-8")
        run(root, "git", "add", "payload.txt")
        run(root, "git", "commit", "-q", "-m", "base")
        parent = run(root, "git", "rev-parse", "HEAD").stdout.strip()

        payload.write_text("candidate\n", encoding="utf-8")
        run(root, "git", "add", "payload.txt")
        run(root, "git", "commit", "-q", "-m", "candidate")
        head = run(root, "git", "rev-parse", "HEAD").stdout.strip()

        baseline = root / "baseline.json"
        final = root / "final.json"
        run(
            root, sys.executable, str(INTEGRITY), "--rev", head,
            "--pass-id", "baseline", "--output", str(baseline),
        )

        payload.write_text("tampered checkout\n", encoding="utf-8")
        result = run(
            root, sys.executable, str(INTEGRITY), "--rev", head,
            "--pass-id", "tampered", "--baseline", str(baseline),
            "--output", str(final), check=False,
        )
        expect_failure(result, "tracked checkout differs", "tracked checkout mutation")
        run(root, "git", "restore", "payload.txt")

        corrupt = root / "corrupt-baseline.json"
        baseline_data = json.loads(baseline.read_text(encoding="utf-8"))
        baseline_data["scan_sha256"] = "0" * 64
        corrupt.write_text(json.dumps(baseline_data) + "\n", encoding="utf-8")
        result = run(
            root, sys.executable, str(INTEGRITY), "--rev", head,
            "--pass-id", "corrupt", "--baseline", str(corrupt),
            "--output", str(final), check=False,
        )
        expect_failure(result, "scan differs from baseline", "corrupt integrity manifest")

        state = root / "state"
        result = run(
            root, sys.executable, str(SCRATCH), "init", "--dir", str(state),
            "--workflow", "false-green", "--job", "lineage",
            "--source-sha", head, "--parent-run-id", "1", "--expected-sha", parent,
            check=False,
        )
        expect_failure(result, "does not match parent expected SHA", "wrong parent candidate")

        run(
            root, sys.executable, str(SCRATCH), "init", "--dir", str(state),
            "--workflow", "false-green", "--job", "lineage",
            "--source-sha", head, "--parent-run-id", "1", "--expected-sha", head,
        )
        state_path = state / "state.json"
        state_data = json.loads(state_path.read_text(encoding="utf-8"))
        state_data["source_tree"] = "0" * 40
        state_path.write_text(json.dumps(state_data) + "\n", encoding="utf-8")
        result = run(root, sys.executable, str(SCRATCH), "verify", "--dir", str(state), check=False)
        expect_failure(result, "checkout no longer matches recorded source commit/tree", "stale scratch lineage")

        run(
            root, sys.executable, str(SCRATCH), "init", "--dir", str(state),
            "--workflow", "false-green", "--job", "guard",
            "--source-sha", head, "--parent-run-id", "1", "--expected-sha", head,
        )
        env = os.environ.copy()
        env["GITHUB_REF"] = "refs/heads/not-main"
        result = run(root, "bash", str(WORKFLOW_GUARD), str(state), head, "main", check=False, env=env)
        expect_failure(result, "acceptance workflows must run from main", "non-main acceptance")

        env["GITHUB_REF"] = "refs/heads/main"
        result = run(root, "bash", str(WORKFLOW_GUARD), str(state), parent, "main", check=False, env=env)
        expect_failure(result, "does not match requested", "wrong requested revision")

    print("false-green acceptance-control regression passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
