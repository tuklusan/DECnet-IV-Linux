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

"""Regression for independently successful, exact-parent PP-11 S1 before S2."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("pp11_s1_gate", ROOT / "tools/pp11_s1_gate.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

SHA = "a" * 40
REPO = "tuklusan/DECnet-IV-Linux"
RUN_ID = 12345
PARENT = 23456

def rejects(fn):
    try:
        fn()
    except ValueError:
        return
    raise AssertionError("PP-11 prerequisite accepted poisoned or failing evidence")

run = {"id": RUN_ID, "head_sha": SHA, "event": "workflow_dispatch",
       "repository": {"full_name": REPO}, "run_attempt": 2,
       "path": REPO + "/.github/workflows/vm-lab.yml@refs/heads/main"}
assert gate.require_run(run, REPO, RUN_ID, SHA) == 2
for key, bad in (("head_sha", "b" * 40), ("event", "push"),
                 ("id", RUN_ID + 1), ("path", ".github/workflows/interop.yml@refs/heads/main"),
                 ("run_attempt", 0)):
    rejects(lambda key=key, bad=bad: gate.require_run({**run, key: bad}, REPO, RUN_ID, SHA))

jobs = {"total_count": 2, "jobs": [
    {"name": name, "status": "completed", "conclusion": "success"}
    for name in gate.ARCH_RUNNERS.values()]}
gate.require_jobs(jobs)
rejects(lambda: gate.require_jobs({**jobs, "total_count": 1}))
rejects(lambda: gate.require_jobs({**jobs, "jobs": [jobs["jobs"][0], jobs["jobs"][0]]}))
rejects(lambda: gate.require_jobs({**jobs, "jobs": [jobs["jobs"][0],
        {**jobs["jobs"][1], "conclusion": "failure"}]}))

for arch in gate.ARCH_RUNNERS:
    state = {"format": 1, "workflow": "vm-lab", "arch": arch,
        "mode": "pp11s1-virtio-net-pci-2vcpu-ptfalse", "status": "success",
        "source_sha": SHA, "expected_sha": SHA, "repository": REPO,
        "event": "workflow_dispatch", "run_id": str(RUN_ID),
        "run_attempt": "2", "parent_run_id": str(PARENT)}
    gate.require_state(state, arch, REPO, RUN_ID, 2, PARENT, SHA)
    for key, value in (("mode", "pp11s2-virtio-net-pci-1vcpu-ptfalse"),
                       ("parent_run_id", "999"), ("expected_sha", "b" * 40),
                       ("status", "failure"), ("run_attempt", "1")):
        rejects(lambda key=key, value=value: gate.require_state(
            {**state, key: value}, arch, REPO, RUN_ID, 2, PARENT, SHA))

policy = (ROOT / ".github/workflows/repository-policy.yml").read_text()
vm = (ROOT / ".github/workflows/vm-lab.yml").read_text()
assert policy.count('pp11_s1_run_id=$(sed -n') == 2
assert policy.count('-f pp11_s1_run_id="$pp11_s1_run_id"') == 2
assert policy.count('dispatch_and_record VM_LAB_PP11_S1 vm-lab.yml') == 2
assert 'needs: pp11-s1-prerequisite' in vm
assert "inputs.lab_mode != 'pp11s2' || needs.pp11-s1-prerequisite.result == 'success'" in vm
assert "if: ${{ inputs.lab_mode == 'pp11s2' }}" in vm
assert 'python3 tools/pp11_s1_gate.py' in vm
print('PP-11 S1-before-S2 prerequisite and fault negatives PASS')
