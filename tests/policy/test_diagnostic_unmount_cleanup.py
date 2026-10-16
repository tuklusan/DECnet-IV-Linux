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

"""Preserve a diagnostic image work tree if its guest filesystem fails to unmount."""

from pathlib import Path
import os
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tests/lab/install-diagnostic-module.sh"


def check_case(mounted: int, fail_umount: int, exit_status: int = 0) -> None:
    shell = SOURCE.read_text(encoding="utf-8")
    if ("trap cleanup EXIT\n" not in shell or
            "trap 'exit 130' INT\n" not in shell or
            "trap 'exit 143' TERM\n" not in shell):
        raise AssertionError("missing fail-closed signal/exit trap contract")
    start = shell.index("cleanup() {\n")
    end = shell.index("\n}\ntrap ", start) + len("\n}\n")
    cleanup = shell[start:end]
    with tempfile.TemporaryDirectory(prefix="dniv-diagnostic-umount-") as td:
        log = Path(td) / "operations.log"
        script = (
            "set -euo pipefail\n"
            + 'work="$DNIV_TEST_DIR/work"\n'
            + 'mnt="$work/root"\n'
            + 'repo_root="$DNIV_TEST_DIR"\n'
            + 'kdir="$DNIV_TEST_DIR/kdir"\n'
            + f'mounted={mounted}\n'
            + 'sudo() { printf "sudo:%s\\n" "$*" >> "$DNIV_LOG";\n'
            + '  if [[ "$1" == umount ]]; then return "$DNIV_FAIL_UNMOUNT"; fi; }\n'
            + 'make() { :; }\n'
            + 'rm() { printf "rm:%s\\n" "$*" >> "$DNIV_LOG"; }\n'
            + cleanup
            + "trap cleanup EXIT\n"
            + f"exit {exit_status}\n"
        )
        env = os.environ.copy()
        env.update(DNIV_TEST_DIR=td, DNIV_LOG=str(log),
                   DNIV_FAIL_UNMOUNT=str(fail_umount))
        p = subprocess.run(["bash", "-c", script], env=env,
                           text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           timeout=5, check=False)
        operations = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
        wanted_umount = bool(mounted)
        has_umount = any(v.startswith("sudo:umount ") for v in operations)
        has_rm = any(v.startswith("rm:-rf ") for v in operations)
        if has_umount != wanted_umount:
            raise AssertionError(f"wrong unmount calls: {operations}")
        if mounted and fail_umount:
            if p.returncode == 0 or has_rm:
                raise AssertionError(
                    f"mounted work tree deleted or reported success after umount failure: "
                    f"rc={p.returncode} log={operations} stderr={p.stderr!r}"
                )
        elif p.returncode != exit_status or not has_rm:
            raise AssertionError(
                f"successful/unmounted cleanup failed: rc={p.returncode} log={operations}"
            )


def main() -> None:
    for mounted, fail_umount, status in ((1, 1, 0), (1, 0, 0), (0, 0, 0),
                                          (1, 0, 7), (0, 0, 9)):
        check_case(mounted, fail_umount, status)
    print("diagnostic mounted work-tree cleanup regression passed")


if __name__ == "__main__":
    main()
