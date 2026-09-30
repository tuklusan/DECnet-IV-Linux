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

"""Regression tests for staged/committed continuity source selection."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "tools" / "project_state_gate.py"


def run(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def write_valid(root: Path, marker: str) -> None:
    (root / "docs" / "PROJECT_STATE.md").write_text(
        f"# State\n\n## Resume point\n{marker}\n\n## Next action\ncontinue\n",
        encoding="utf-8",
    )
    (root / "scratch" / "RESUME.md").write_text(
        f"# Resume\n\n## Current checkpoint\n{marker}\n\n## Next action\ncontinue\n",
        encoding="utf-8",
    )


def gate(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return run(root, sys.executable, str(GATE), *args, check=False)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="dniv-state-gate-") as temporary:
        root = Path(temporary)
        (root / "docs").mkdir()
        (root / "scratch").mkdir()
        run(root, "git", "init", "-q", "-b", "main")
        run(root, "git", "config", "user.name", "State Gate Test")
        run(root, "git", "config", "user.email", "state-gate@example.invalid")
        write_valid(root, "base")
        (root / "payload.txt").write_text("one\n", encoding="utf-8")
        run(root, "git", "add", ".")
        run(root, "git", "commit", "-q", "-m", "base")

        write_valid(root, "staged")
        (root / "payload.txt").write_text("two\n", encoding="utf-8")
        run(root, "git", "add", ".")
        (root / "docs" / "PROJECT_STATE.md").write_text("working tree only\n", encoding="utf-8")
        (root / "scratch" / "RESUME.md").write_text("working tree only\n", encoding="utf-8")
        result = gate(root, "--staged")
        if result.returncode != 0:
            raise SystemExit("staged gate read working-tree continuity instead of the index")

        run(root, "git", "restore", "docs/PROJECT_STATE.md", "scratch/RESUME.md")
        run(root, "git", "commit", "-q", "-m", "staged state")
        (root / "docs" / "PROJECT_STATE.md").write_text("working tree only\n", encoding="utf-8")
        (root / "scratch" / "RESUME.md").write_text("working tree only\n", encoding="utf-8")
        result = gate(root, "--head", "HEAD")
        if result.returncode != 0:
            raise SystemExit("committed gate read working-tree continuity instead of the commit")

        run(root, "git", "restore", ".")
        (root / "payload.txt").write_text("three\n", encoding="utf-8")
        (root / "docs" / "PROJECT_STATE.md").write_text(
            "# State\n\n## Resume point\npartial\n\n## Next action\ncontinue\n",
            encoding="utf-8",
        )
        run(root, "git", "add", "payload.txt", "docs/PROJECT_STATE.md")
        result = gate(root, "--staged")
        if result.returncode == 0 or "scratch/RESUME.md" not in result.stderr:
            raise SystemExit("staged gate failed to require both continuity records")

    print("project-state gate regression tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
