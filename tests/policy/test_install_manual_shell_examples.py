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
"""Run the shipped installation manual's extraction commands as actual Bash."""

import hashlib
from io import BytesIO
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[2]
manual = (ROOT / "INSTALL.md").read_text(encoding="utf-8")
version_match = re.search(r"^version=([0-9]+\.[0-9]+\.[0-9]+)$", (ROOT / "VERSION").read_text(), re.M)
assert version_match is not None, "VERSION must have one semantic version"
version = version_match.group(1)


def sh_example(section: str) -> str:
    start = manual.find(section)
    assert start >= 0, f"missing manual section: {section}"
    fence = re.escape(chr(96) * 3)
    code = re.search(fence + r"sh\n(.*?)\n" + fence, manual[start:], re.S)
    assert code is not None, f"no shell example in section: {section}"
    return code.group(1)


with tempfile.TemporaryDirectory(prefix="dniv-install-manual-") as temp:
    root = Path(temp)
    archive = root / f"DECnet-IV-Linux-{version}.tar.xz"
    with tarfile.open(archive, "w:xz") as tf:
        data = b"example\n"
        info = tarfile.TarInfo(f"DECnet-IV-Linux-{version}/README.md")
        info.mode = 0o644
        info.size = len(data)
        tf.addfile(info, BytesIO(data))
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    (root / (archive.name + ".sha256")).write_text(f"{checksum}  {archive.name}\n")
    extract = sh_example("## 4. Verify and extract")
    result = subprocess.run(
        ["bash", "-e", "-u", "-o", "pipefail", "-c", extract + "\npwd"],
        cwd=root, text=True, capture_output=True, timeout=10,
    )
    assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)
    assert result.stdout.splitlines()[-1] == str(root / f"DECnet-IV-Linux-{version}"), result.stdout
    assert (root / f"DECnet-IV-Linux-{version}" / "README.md").read_bytes() == b"example\n"

kernel_snippet = sh_example("Another installed kernel")
result = subprocess.run(["bash", "-n", "-c", kernel_snippet], text=True, capture_output=True, timeout=5)
assert result.returncode == 0, result.stderr
print("installation-manual source-extraction Bash examples passed")
