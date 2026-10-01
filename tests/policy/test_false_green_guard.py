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

import importlib.util
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
EVIDENCE_GUARD = ROOT / "tools" / "evidence_guard.py"

SPEC = importlib.util.spec_from_file_location("dniv_lab_false_green", ROOT / "tests/lab/dniv_lab.py")
assert SPEC and SPEC.loader
LAB = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = LAB
SPEC.loader.exec_module(LAB)


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

        # Guest pass-like text must never substitute for independent wire proof.
        valid_wire = {
            "routersA": 2, "routersB": 2, "endnodesA": 0, "endnodesB": 1,
            "nicHelloA": 0, "nicHelloB": 0,
            "changedNicHelloA": 0, "changedNicHelloB": 0,
            "ucastAB": 3, "ucastBA": 3,
        }
        LAB.validate_e1_wire_values(valid_wire)
        suppressed = dict(valid_wire)
        suppressed["ucastBA"] = 0
        try:
            LAB.validate_e1_wire_values(suppressed)
        except SystemExit as exc:
            if "wire evidence incomplete" not in str(exc):
                raise
        else:
            raise SystemExit("false-green regression accepted pass markers with suppressed wire traffic")

        class DeadCapture:
            @staticmethod
            def poll() -> int:
                return 1

        fake = object.__new__(LAB.Lab)
        fake.tcpdump = DeadCapture()
        try:
            fake.require_capture_running()
        except RuntimeError as exc:
            if "packet capture exited" not in str(exc):
                raise
        else:
            raise SystemExit("false-green regression accepted a dead packet capture")

        faults = root / "fault-events.log"
        try:
            LAB.require_fault_event(faults, "requested-injector")
        except SystemExit as exc:
            if "requested fault event" not in str(exc):
                raise
        else:
            raise SystemExit("false-green regression accepted an inactive requested injector")
        LAB.record_fault_event(faults, "requested-injector")
        LAB.require_fault_event(faults, "requested-injector")

        evidence = root / "evidence"
        run(root, sys.executable, str(EVIDENCE_GUARD), "preflight",
            "--root", str(evidence), "--min-free-bytes", "1", "--min-free-inodes", "1")
        evlog = evidence / "run.log"
        evstate = evidence / "state.json"
        evlog.write_text("wire proof\n", encoding="utf-8")
        evstate.write_text('{"status":"success"}\n', encoding="utf-8")
        manifest = evidence / "manifest.json"
        run(root, sys.executable, str(EVIDENCE_GUARD), "manifest",
            "--root", str(evidence), "--output", str(manifest),
            "--require", "run.log", "--require", "state.json")
        run(root, sys.executable, str(EVIDENCE_GUARD), "verify",
            "--root", str(evidence), "--manifest", str(manifest))

        evlog.write_text("truncated\n", encoding="utf-8")
        result = run(root, sys.executable, str(EVIDENCE_GUARD), "verify",
            "--root", str(evidence), "--manifest", str(manifest), check=False)
        expect_failure(result, "evidence size mismatch", "truncated evidence")

        result = run(root, sys.executable, str(EVIDENCE_GUARD), "preflight",
            "--root", str(evidence), "--min-free-bytes", str(1 << 62), "--min-free-inodes", "1",
            check=False)
        expect_failure(result, "insufficient free evidence bytes", "exhausted evidence bytes")
        result = run(root, sys.executable, str(EVIDENCE_GUARD), "preflight",
            "--root", str(evidence), "--min-free-bytes", "1", "--min-free-inodes", str(1 << 62),
            check=False)
        expect_failure(result, "insufficient free evidence inodes", "exhausted evidence inodes")

        blocked = root / "blocked-evidence"
        blocked.write_text("not a directory\n", encoding="utf-8")
        result = run(root, sys.executable, str(EVIDENCE_GUARD), "preflight",
            "--root", str(blocked), "--min-free-bytes", "1", "--min-free-inodes", "1",
            check=False)
        expect_failure(result, "cannot create evidence directory", "unavailable evidence directory")

    print("false-green acceptance-control regression passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
