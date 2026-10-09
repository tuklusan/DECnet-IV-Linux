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

"""Ensure tracked archive symlinks cannot escape source packaging."""

from pathlib import Path
import os
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
BUILDER = ROOT / "tools/build-source-release.sh"


def run(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, check=check, capture_output=True,
                          text=True, timeout=30)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="dniv-release-symlink-") as tmp:
        work = Path(tmp)
        repo = work / "repo"
        output = work / "output"
        repo.mkdir()
        output.mkdir()
        (repo / "tools").mkdir()
        shutil.copyfile(BUILDER, repo / "tools/build-source-release.sh")
        (repo / "VERSION").write_text("version=1.0.0\n", encoding="utf-8")
        victim = work / "victim.txt"
        victim.write_text("DO_NOT_OVERWRITE\n", encoding="utf-8")
        (repo / "SOURCE-METADATA").symlink_to(victim)
        run("git", "init", "-q", "-b", "main", cwd=repo)
        run("git", "config", "user.email", "fixture@invalid.example", cwd=repo)
        run("git", "config", "user.name", "Source Fixture", cwd=repo)
        run("git", "add", "VERSION", "tools/build-source-release.sh",
            "SOURCE-METADATA", cwd=repo)
        run("git", "commit", "-qm", "source symlink negative", cwd=repo)
        sha = run("git", "rev-parse", "HEAD", cwd=repo).stdout.strip()
        result = run("bash", "tools/build-source-release.sh", str(output),
                     "1.0.0", sha, cwd=repo, check=False)
        if result.returncode == 0:
            raise AssertionError("symlink source release unexpectedly succeeded")
        if "symbolic link in source archive" not in result.stderr:
            raise AssertionError("builder did not reject tracked symlink early")
        if victim.read_bytes() != b"DO_NOT_OVERWRITE\n":
            raise AssertionError("builder followed source link and overwrote victim")
        if list(output.iterdir()):
            raise AssertionError("rejected input produced a release artifact")
    print("source-release tracked symlink negative passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
