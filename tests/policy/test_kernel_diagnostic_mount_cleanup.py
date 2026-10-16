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

"""Diagnostic foundation never touches unowned or still-mounted paths."""

from pathlib import Path
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / ".github/workflows/kernel-diagnostics.yml"


def exercise(mode: str) -> None:
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    begin = next(i for i, line in enumerate(lines) if line.strip() == 'raw="$RUNNER_TEMP/foundation-${{ matrix.arch }}.raw"')
    end = next(i for i in range(begin, len(lines)) if "grep -q '^CONFIG_MODULES=y$'" in lines[i])
    body = "\n".join(line[10:] for line in lines[begin:end + 1]).replace("${{ matrix.arch }}", "amd64")
    with tempfile.TemporaryDirectory() as d:
        base = Path(d)
        tempdir = base / "tmp"
        tempdir.mkdir()
        scratch = base / "scratch"
        scratch.mkdir()
        (scratch / "production-kernel.config").write_text("CONFIG_MODULES=y\n", encoding="utf-8")
        raw = tempdir / "foundation-amd64.raw"
        mount = tempdir / "foundation-amd64-mnt"
        if mode == "preexisting":
            mount.mkdir()
            (mount / "foreign").write_text("FOREIGN", encoding="utf-8")
        mock = base / "bin"
        mock.mkdir()
        for command, script in {
            "qemu-img": "#!/bin/bash\ntouch \"${@: -1}\"\n",
            "sudo": '''#!/bin/bash
case "$1" in
 mount) mkdir -p "${@: -1}/boot"; echo 'CONFIG_MODULES=y' > "${@: -1}/boot/config-linux"; touch "${@: -1}/.mounted";;
 umount) if [[ "${MODE}" == umountfail ]]; then exit 1; fi; rm -f "$2/.mounted"; rm -rf "$2/boot";;
 cp) if [[ "${MODE}" == copyfail ]]; then exit 1; fi; command cp "$2" "$3";;
 chown) :;;
esac
''',
            "mountpoint": "#!/bin/bash\nexit 1\n",
        }.items():
            path = mock / command
            path.write_text(script, encoding="utf-8")
            path.chmod(0o755)
        env = dict(os.environ, RUNNER_TEMP=str(tempdir), DNIV_OUTER_BASE_DIR=str(base),
                   DNIV_SCRATCH_DIR=str(scratch), MODE=mode, PATH=str(mock)+":"+os.environ["PATH"])
        bash = "set -euo pipefail\n"+body
        result = subprocess.run(["bash", "-c", bash], env=env, capture_output=True, text=True)
        if mode in ("preexisting", "copyfail", "umountfail") and result.returncode == 0:
            raise AssertionError(f"{mode}: failure not propagated")
        if mode == "preexisting" and (mount / "foreign").read_text() != "FOREIGN":
            raise AssertionError("preexisting mount destroyed")
        if mode == "umountfail" and (not (mount / ".mounted").exists() or not raw.exists()):
            raise AssertionError("failed unmount erased mounted disk evidence")
        if mode == "copyfail" and (mount.exists() or raw.exists()):
            raise AssertionError("copy failure failed to clean owned mount")
        if mode == "ok" and (result.returncode or mount.exists() or raw.exists()):
            raise AssertionError(f"successful mount cleanup failed: {result.stderr}")


def main() -> None:
    for mode in ("preexisting", "copyfail", "umountfail", "ok"):
        exercise(mode)
    print("Diagnostic foundation mounted-resource ownership PASS")


if __name__ == "__main__":
    main()
