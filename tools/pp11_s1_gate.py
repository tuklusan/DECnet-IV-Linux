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
"""Fail closed until the exact-parent, dual-architecture PP-11 S1 has passed."""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time

ARCH_RUNNERS = {"amd64": "python-two-node (ubuntu-24.04, x64)",
                "arm64": "python-two-node (ubuntu-24.04-arm, arm64)"}


def require_run(run, repo, run_id, sha):
    if (run.get("id") != run_id or run.get("head_sha") != sha or
        run.get("event") != "workflow_dispatch" or
        run.get("repository", {}).get("full_name") != repo or
        not re.search(r"(?:^|/)\.github/workflows/vm-lab\.yml@refs/heads/main$",
                      run.get("path", ""))):
        raise ValueError("S1 run is not the exact expected workflow/source/repository")
    attempt = run.get("run_attempt")
    if type(attempt) is not int or attempt < 1:
        raise ValueError("invalid S1 run attempt")
    return attempt


def require_jobs(data):
    jobs = data.get("jobs")
    if not isinstance(jobs, list) or data.get("total_count") != len(ARCH_RUNNERS):
        raise ValueError("S1 must have exactly two architecture jobs")
    by_name = {j.get("name"): j for j in jobs}
    if set(by_name) != set(ARCH_RUNNERS.values()):
        raise ValueError("S1 architecture jobs missing or duplicated")
    if any(j.get("status") != "completed" or j.get("conclusion") != "success"
           for j in jobs):
        raise ValueError("S1 must finish success on both architectures")


def require_state(state, arch, repo, run_id, attempt, parent, sha):
    expected_mode = "pp11s1-virtio-net-pci-2vcpu-ptfalse"
    expected = {"format": 1, "workflow": "vm-lab", "arch": arch,
                "mode": expected_mode, "status": "success", "source_sha": sha,
                "expected_sha": sha, "repository": repo, "event": "workflow_dispatch",
                "run_id": str(run_id), "run_attempt": str(attempt),
                "parent_run_id": str(parent)}
    for key, value in expected.items():
        if state.get(key) != value:
            raise ValueError(f"S1 evidence {arch} mismatched {key}")


def api(url):
    return json.loads(subprocess.check_output(["gh", "api", url], text=True))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--parent-run-id", type=int, required=True)
    parser.add_argument("--sha", required=True)
    args = parser.parse_args()
    if (not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repo)
        or not re.fullmatch(r"[0-9a-f]{40}", args.sha)
        or args.run_id < 1 or args.parent_run_id < 1
        or not os.getenv("GH_TOKEN")):
        parser.error("exact S1/parent identifiers and GH_TOKEN required")
    endpoint = f"repos/{args.repo}/actions/runs/{args.run_id}"
    deadline = time.monotonic() + 68 * 60
    while True:
        run = api(endpoint)
        attempt = require_run(run, args.repo, args.run_id, args.sha)
        if run.get("status") == "completed":
            if run.get("conclusion") != "success":
                raise ValueError("S1 completed without success")
            break
        if time.monotonic() >= deadline:
            raise TimeoutError("S1 did not complete within prerequisite deadline")
        time.sleep(20)
    require_jobs(api(endpoint + "/jobs?per_page=100"))
    artifacts = api(endpoint + "/artifacts?per_page=100").get("artifacts", [])
    with tempfile.TemporaryDirectory(prefix="dniv-pp11-s1-") as tmp:
        for arch in ARCH_RUNNERS:
            artifact_name = (f"scratch-vm-lab-evidence-{arch}-virtio-net-pci-"
                             f"2vcpu-none-ptfalse-{args.run_id}-{attempt}")
            matching = [a for a in artifacts if a.get("name") == artifact_name
                        and not a.get("expired", True)]
            if len(matching) != 1 or matching[0].get("workflow_run", {}).get("id") != args.run_id:
                raise ValueError(f"missing exact S1 {arch} attempt evidence")
            dest = Path(tmp) / arch
            dest.mkdir()
            subprocess.run(["gh", "run", "download", str(args.run_id), "--repo", args.repo,
                            "--name", artifact_name, "--dir", str(dest)], check=True)
            states = list(dest.rglob("state.json"))
            if len(states) != 1:
                raise ValueError(f"S1 {arch} missing/ambiguous scratch state")
            require_state(json.loads(states[0].read_text(encoding="utf-8")),
                          arch, args.repo, args.run_id, attempt, args.parent_run_id, args.sha)
    print(f"PP-11 S1 prerequisite PASS: {args.run_id}/{attempt}, both architectures, {args.sha}")


if __name__ == "__main__":
    main()
