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

"""Prove source archives cannot disagree with committed root VERSION."""

import pathlib
import shutil
import subprocess
import tarfile
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
BUILDER = ROOT / "tools" / "build-source-release.sh"
REQUIRED = (
    "build.sh", "install.sh", "uninstall.sh", "INSTALL.md", "LICENSE",
    "docs/DELIVERY.md", "docs/FEATURES.md", "docs/COMPONENTS.md",
)


def run(*args, cwd, check=True):
    return subprocess.run(
        args, cwd=cwd, check=check, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )


def commit(repo):
    run("git", "add", "-A", cwd=repo)
    run("git", "-c", "user.name=Source Release Regression",
        "-c", "user.email=fixture@example.invalid", "commit", "-q",
        "-m", "Version regression fixture", cwd=repo)
    return run("git", "rev-parse", "HEAD", cwd=repo).stdout.strip()


def expect_rejection(repo, output, sha, version):
    result = run(str(BUILDER), str(output), version, sha,
                 cwd=repo, check=False)
    assert result.returncode != 0, "source builder accepted inconsistent VERSION"
    assert "committed VERSION" in result.stderr, result.stderr
    assert not list(output.glob("*.tar.xz")), "invalid archive was published"


def main():
    with tempfile.TemporaryDirectory(prefix="dniv-release-version-") as td:
        work = pathlib.Path(td)
        repo = work / "fixture"
        repo.mkdir()
        (repo / "tools").mkdir()
        shutil.copy2(BUILDER, repo / "tools" / BUILDER.name)
        for name in REQUIRED:
            target = repo / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("fixture\n", encoding="utf-8")
        version_file = repo / "VERSION"
        version_file.write_text("version=1.0.0\n", encoding="utf-8")
        run("git", "init", "-q", "-b", "main", cwd=repo)
        sha = commit(repo)

        bad = work / "mismatch"
        expect_rejection(repo, bad, sha, "9.9.9")

        good = work / "good"
        result = run(str(BUILDER), str(good), "1.0.0", sha, cwd=repo)
        archive = pathlib.Path(result.stdout.strip())
        assert archive.is_file(), "matching version did not produce archive"
        with tarfile.open(archive, "r:xz") as tf:
            assert tf.extractfile("DECnet-IV-Linux-1.0.0/VERSION").read() == b"version=1.0.0\n"
            metadata = tf.extractfile("DECnet-IV-Linux-1.0.0/SOURCE-METADATA").read()
            assert b"version=1.0.0\n" in metadata
            assert ("source_sha=" + sha + "\n").encode() in metadata

        version_file.write_text("version=1.0.0\nversion=1.0.0\n", encoding="utf-8")
        duplicate_sha = commit(repo)
        expect_rejection(repo, work / "duplicate", duplicate_sha, "1.0.0")

        version_file.write_text("other_version=1.0.0\n", encoding="utf-8")
        missing_sha = commit(repo)
        expect_rejection(repo, work / "missing", missing_sha, "1.0.0")

    print("source-release VERSION matches the exact pinned source commit")


if __name__ == "__main__":
    main()
