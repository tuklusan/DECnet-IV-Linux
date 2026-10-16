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

"""Never delete an unowned diagnostic-kernel output tree."""

from pathlib import Path
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tests/lab/build-diagnostic-kernel.sh"
MARKER = ".dniv-diagnostic-kernel-root"
VALUE = "DNIV-DIAGNOSTIC-KERNEL-OUTPUT-v1"


def run(source, output, env, cfg):
    return subprocess.run(["bash", str(source), "amd64", "kasan", str(cfg),
                           str(output)], env=env, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=8, check=False)


def check():
    with tempfile.TemporaryDirectory(prefix="dniv-diag-output-") as td:
        root = Path(td)
        bindir = root / "bin"
        bindir.mkdir()
        # All execution stops at the first git call. No kernel checkout/network.
        fake = bindir / "git"
        fake.write_text("#!/bin/sh\nexit 79\n")
        fake.chmod(0o755)
        env = {**os.environ, "PATH": str(bindir) + os.pathsep + os.environ["PATH"]}
        cfg = root / "config"
        cfg.write_text("CONFIG_MODULES=y\n")

        unrelated = root / "unrelated"
        unrelated.mkdir()
        victim = unrelated / "precious-file"
        victim.write_text("preserve me")
        result = run(SCRIPT, unrelated, env, cfg)
        assert result.returncode == 2, (result.returncode, result.stderr)
        assert victim.read_text() == "preserve me", "unowned tree was deleted"

        fresh = root / "fresh"
        result = run(SCRIPT, fresh, env, cfg)
        assert result.returncode == 79, (result.returncode, result.stderr)
        assert (fresh / MARKER).read_text().strip() == VALUE

        stale = fresh / "old"
        stale.write_text("obsolete")
        result = run(SCRIPT, fresh, env, cfg)
        assert result.returncode == 79, (result.returncode, result.stderr)
        assert not stale.exists() and (fresh / MARKER).is_file()

        target = root / "owned-target"
        target.mkdir()
        (target / MARKER).write_text(VALUE + "\n")
        link = root / "link"
        link.symlink_to(target, target_is_directory=True)
        result = run(SCRIPT, link, env, cfg)
        assert result.returncode == 2 and link.is_symlink()
        assert (target / MARKER).is_file(), "symlink target was modified"

        bad = root / "forged"
        bad.mkdir()
        (bad / MARKER).write_text("WRONG-VALUE\n")
        (bad / "untouched").write_text("yes")
        result = run(SCRIPT, bad, env, cfg)
        assert result.returncode == 2 and (bad / "untouched").read_text() == "yes"

    print("diagnostic kernel output ownership guard passed")


if __name__ == "__main__":
    check()
