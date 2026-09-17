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

"""Regression checks for the main-only branch update rule."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import repo_policy  # noqa: E402


def main() -> int:
    cases = (
        (b"refs/heads/main", False, None),
        (b"refs/heads/main", True, "main branch deletion is prohibited"),
        (b"refs/heads/topic", False, "non-main branch updates are prohibited"),
        (b"refs/heads/topic", True, None),
        (b"refs/tags/v1", False, None),
    )
    for ref, deleting, expected in cases:
        actual = repo_policy.branch_update_error(ref, deleting)
        if actual != expected:
            raise SystemExit(
                f"branch policy mismatch for {ref!r} deleting={deleting}: {actual!r} != {expected!r}"
            )

    workflow_sop = (ROOT / "tools/workflow_sop.sh").read_text(encoding="utf-8")
    repository_workflow = (
        ROOT / ".github/workflows/repository-policy.yml"
    ).read_text(encoding="utf-8")
    required_sop = (
        'main|maintenance|event',
        'if [[ "$scope" == main || "$scope" == maintenance ]]; then',
    )
    for snippet in required_sop:
        if snippet not in workflow_sop:
            raise SystemExit(
                f"branch policy regression: maintenance SoP support missing: {snippet}"
            )
    maintenance_call = (
        'tools/workflow_sop.sh "$DNIV_SCRATCH_DIR" "$candidate" maintenance'
    )
    if maintenance_call not in repository_workflow:
        raise SystemExit(
            "branch policy regression: branch cleanup must verify current main with maintenance scope"
        )
    stale_cleanup_call = (
        'tools/workflow_sop.sh "$DNIV_SCRATCH_DIR" "$candidate" main'
    )
    if stale_cleanup_call in repository_workflow:
        raise SystemExit(
            "branch policy regression: branch cleanup still uses acceptance-only main scope"
        )

    print("branch policy regression tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
