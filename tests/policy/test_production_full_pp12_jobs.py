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

"""Check that production publication requires all native PP-12 source jobs."""

from pathlib import Path
import re
import json
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
workflow = (ROOT / ".github/workflows/production-release.yml").read_text()
marker = "python3 - \"$DNIV_RELEASE_EVIDENCE/full-source-jobs.jsonl\" <<\u0027PY_PP12_JOBS\u0027"
assert workflow.count(marker) == 1
assert "actions/runs/$SOURCE_RELEASE_RUN_ID/jobs?per_page=100" in workflow
body = workflow.split(marker, 1)[1].split("\n          PY_PP12_JOBS", 1)
assert len(body) == 2
script = "\n".join(line.removeprefix("          ") for line in body[0].splitlines())
names = ["package-amd64", "validate-arm64", "portability (ubuntu-24.04, amd64)", "portability (ubuntu-24.04-arm, arm64)", "pp12-real-peers (ubuntu-24.04, amd64, qemu-system-x86)", "pp12-real-peers (ubuntu-24.04-arm, arm64, qemu-system-arm)"]
good = [dict(name=name, status="completed", conclusion="success") for name in names]
variants = [(good, True), (good[:-1], False), (good + [good[-1]], False)]
for i in (4, 5):
    for status in ("skipped", "failure", "in_progress"):
        rows = [dict(row) for row in good]
        rows[i]["conclusion"] = status if status != "in_progress" else None
        rows[i]["status"] = "in_progress" if status == "in_progress" else "completed"
        variants.append((rows, False))
with tempfile.TemporaryDirectory() as td:
    p = Path(td) / "jobs.jsonl"
    for rows, success in variants:
        p.write_text("".join(json.dumps(row) + "\n" for row in rows))
        run = subprocess.run([sys.executable, "-c", script, str(p)], capture_output=True, timeout=5)
        assert (run.returncode == 0) == success, (rows, run.stderr)
print("production requires complete native PP12 source run")
