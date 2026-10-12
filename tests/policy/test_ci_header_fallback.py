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

"""Hosted ARM kernel header mirror skew must not skip a real module build."""

import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "tools/install-ci-kernel-headers.sh"


def main() -> int:
    for workflow in ("build.yml", "source-release.yml"):
        text = (ROOT / ".github/workflows" / workflow).read_text(encoding="utf-8")
        if "bash tools/install-ci-kernel-headers.sh" not in text:
            raise AssertionError(f"{workflow} bypasses guarded matching header install")

    subprocess.run(["bash", "-n", str(HELPER)], check=True)
    with tempfile.TemporaryDirectory(prefix="dniv-ci-headers-") as tmp:
        base = Path(tmp)
        fake = base / "bin"
        fake.mkdir()
        (fake / "sudo").write_text('#!/bin/sh\nexec "$@"\n', encoding="utf-8")
        (fake / "apt-cache").write_text(
            '#!/bin/sh\nprintf "%s\\n" linux-headers-6.8.0-147-generic '
            'linux-headers-6.8.0-146-generic\n',
            encoding="utf-8",
        )
        (fake / "apt-get").write_text(
            '#!/bin/bash\n'
            'echo "$*" >> "$FAKE_LOG"\n'
            'if [[ "$*" == *"linux-headers-generic"* ]]; then exit 100; fi\n'
            'if [[ "$*" == *"linux-headers-6.8.0-147-generic"* ]]; then exit 100; fi\n'
            'if [[ "$*" == *"linux-headers-6.8.0-146-generic"* ]]; then '
            '[[ "$FAKE_MODE" != fail ]]; exit; fi\n'
            'exit 100\n',
            encoding="utf-8",
        )
        for item in fake.iterdir():
            item.chmod(0o755)
        for mode, success in (("usable", True), ("fail", False)):
            log = base / f"{mode}.log"
            env = dict(os.environ, PATH=f"{fake}:{os.environ['PATH']}",
                       FAKE_MODE=mode, FAKE_LOG=str(log))
            done = subprocess.run(["bash", str(HELPER)], env=env,
                                  capture_output=True, text=True, timeout=10)
            if (done.returncode == 0) != success:
                raise AssertionError(f"header mode {mode}: {done.returncode}: {done.stderr}")
            cmds = log.read_text(encoding="utf-8")
            if "linux-headers-generic" not in cmds:
                raise AssertionError("missing standard meta package attempt")
            if "linux-headers-6.8.0-147-generic" not in cmds:
                raise AssertionError("did not verify newer un-installable headers")
            if "linux-headers-6.8.0-146-generic" not in cmds:
                raise AssertionError("did not attempt installable version fallback")
            if success and not any(
                line.endswith("-y linux-headers-6.8.0-146-generic")
                for line in cmds.splitlines()
            ):
                raise AssertionError("never installed the simulated complete headers")
            if not success and "refusing a false-green build" not in done.stderr:
                raise AssertionError("failed all headers without a fail-closed diagnostic")
    print("CI generic-header mirror-skew install/fail-closed regression passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
