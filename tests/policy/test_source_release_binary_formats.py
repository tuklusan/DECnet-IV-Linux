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

"""Build actual version-pinned source archives; reject disguised compiled files."""

import pathlib
import shutil
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
BUILDER = ROOT / "tools/build-source-release.sh"
REQUIRED = (
    "build.sh", "install.sh", "uninstall.sh", "INSTALL.md", "LICENSE",
    "docs/DELIVERY.md", "docs/FEATURES.md", "docs/COMPONENTS.md",
)


def run(*args, cwd, check=True):
    return subprocess.run(args, cwd=cwd, text=True, check=check,
                          capture_output=True, timeout=30)


def commit(repo):
    run("git", "add", "-A", cwd=repo)
    run("git", "-c", "user.name=Binary Fixture",
        "-c", "user.email=fixture@example.invalid", "commit", "-qm",
        "binary fixture", cwd=repo)
    return run("git", "rev-parse", "HEAD", cwd=repo).stdout.strip()


def main():
    with tempfile.TemporaryDirectory(prefix="dniv-release-binary-") as temp:
        work = pathlib.Path(temp)
        repo = work / "fixture"
        (repo / "tools").mkdir(parents=True)
        (repo / "payloads").mkdir()
        shutil.copy2(BUILDER, repo / "tools/build-source-release.sh")
        for name in REQUIRED:
            item = repo / name
            item.parent.mkdir(parents=True, exist_ok=True)
            item.write_text("fixture\n")
        (repo / "VERSION").write_text("version=1.0.0\n")
        # A normal text file beginning MZ must remain legitimate source data.
        (repo / "payloads/notes.txt").write_text("MZ is a DOS marker\n")
        run("git", "init", "-q", "-b", "main", cwd=repo)
        sha = commit(repo)
        okay = run(str(BUILDER), str(work / "text"), "1.0.0", sha, cwd=repo)
        assert okay.returncode == 0

        pe = bytearray(256)
        pe[:2] = b"MZ"
        pe[60:64] = (128).to_bytes(4, "little")
        pe[128:132] = b"PE\x00\x00"
        formats = {
            "renamed-pe.data": bytes(pe),
            "renamed-macho.data": bytes.fromhex("cffaedfe") + b"\x00" * 32,
            "renamed-fat.data": bytes.fromhex("cafebabe") + b"\x00" * 32,
            "renamed-wasm.data": b"\x00asm\x01\x00\x00\x00",
            "renamed-llvm.data": bytes.fromhex("4243c0de") + b"\x00" * 32,
            "renamed-elf.data": bytes.fromhex("7f454c46") + b"\x00" * 32,
        }
        for label, data in formats.items():
            binary = repo / "payloads" / label
            binary.write_bytes(data)
            sha = commit(repo)
            output = work / label
            result = run(str(BUILDER), str(output), "1.0.0", sha,
                         cwd=repo, check=False)
            assert result.returncode != 0, f"accepted compiled binary {label}"
            assert "binary payload present" in result.stderr, (label, result.stderr)
            assert not list(output.glob("*.tar.xz")), label
            binary.unlink()
            commit(repo)
    print("source archive rejects ELF, PE, Mach-O, LLVM and WebAssembly payloads")


if __name__ == "__main__":
    main()
