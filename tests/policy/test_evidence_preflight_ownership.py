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

"""Evidence preflight must not write into symlinked roots or delete foreign probes."""

from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "tools/evidence_guard.py"


def run_preflight(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GUARD), "preflight", "--root", str(path),
         "--min-free-bytes", "0", "--min-free-inodes", "0"],
        text=True, capture_output=True, timeout=10,
    )


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="dniv-evidence-preflight-") as scratch:
        root = Path(scratch)
        owned = root / "owned"
        owned.mkdir()
        sentinel = owned / ".dniv-evidence-probe"
        sentinel.write_text("FOREIGN-DO-NOT-DELETE\n", encoding="utf-8")
        result = run_preflight(owned)
        if result.returncode == 0 or sentinel.read_text() != "FOREIGN-DO-NOT-DELETE\n":
            raise AssertionError("O_EXCL failure deleted a pre-existing unowned probe")

        foreign = root / "foreign"
        foreign.mkdir()
        alias = root / "alias"
        alias.symlink_to(foreign, target_is_directory=True)
        for unsafe in (alias, alias / "child"):
            result = run_preflight(unsafe)
            if result.returncode == 0 or "symbolic link" not in result.stderr:
                raise AssertionError(f"symlinked evidence preflight accepted {unsafe}")
        if (foreign / "child").exists():
            raise AssertionError("preflight created evidence under a foreign symlink parent")

        clean = root / "clean"
        result = run_preflight(clean)
        if result.returncode or not clean.is_dir() or list(clean.iterdir()):
            raise AssertionError(f"normal evidence preflight failed: {result.stderr}")
    print("Evidence preflight symlink root and foreign-probe ownership passed")


if __name__ == "__main__":
    main()
