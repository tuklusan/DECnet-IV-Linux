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

"""Audited source run precedes full acceptance; compare bytes, not run IDs."""

import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/production-release.yml"


def main() -> int:
    content = WORKFLOW.read_text(encoding="utf-8")
    assertions = (
        'source_run != values["SOURCE_RELEASE"]' not in content,
        'AUDIT_SOURCE_RELEASE_RUN_ID' in content,
        'audit_run_json=$(gh api ' in content,
        'audit_attempt=$(printf' in content,
        'gh run download "$AUDIT_SOURCE_RELEASE_RUN_ID"' in content,
        'gh run download "$SOURCE_RELEASE_RUN_ID"' in content,
        'cmp "$release_dir/$versioned$suffix" "$full_dir/$versioned$suffix"' in content,
        'printf \'source_run_id=%s\\n\' "$AUDIT_SOURCE_RELEASE_RUN_ID"' in content,
        'printf \'source_attempt=%s\\n\' "$audit_attempt"' in content,
        '.head_sha == $sha and .head_branch == "main"' in content,
        '.status == "completed" and .conclusion == "success"' in content,
    )
    if not all(assertions):
        raise AssertionError(f"source release identity guards missing: {assertions}")

    with tempfile.TemporaryDirectory(prefix="dniv-production-run-ids-") as tmp:
        a, b = Path(tmp) / "audited", Path(tmp) / "full"
        a.mkdir()
        b.mkdir()
        tar = "DECnet-IV-Linux-1.0.0.tar.xz"
        for data, should_match in (
            (b"identical accepted source", True),
            (b"different source payload", False),
        ):
            (a / tar).write_bytes(b"identical accepted source")
            (b / tar).write_bytes(data)
            result = subprocess.run(
                ["cmp", str(a / tar), str(b / tar)],
                capture_output=True, timeout=5,
            )
            if (result.returncode == 0) != should_match:
                raise AssertionError("byte identity check returned false result")
    print("production audit/full source run IDs decoupled; byte mismatch fails")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
