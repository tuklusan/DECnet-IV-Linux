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

"""Interrupted chroot submounts must be undone before image work is deleted."""

from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]
SOURCES = ("tests/lab/prepare-candidate-image.sh",
           "tests/lab/prepare-pp12-source-image.sh",
           "image/ubuntu-base/build-foundation.sh")


def check_source(source):
    src = source.read_text()
    func_start = src.index("cleanup() {\n")
    func_end = src.index("\n}\ntrap cleanup EXIT INT TERM", func_start) + len("\n}\n")
    cleanup = src[func_start:func_end]
    mount_start = src.index('sudo mount -t proc proc "$mnt/proc"\n')
    last_mount = 'sudo mount --make-rslave "$mnt/dev"\n'
    mount_end = src.index(last_mount, mount_start) + len(last_mount)
    if src[mount_end:].startswith("chroot_mounted=1\n"):
        mount_end += len("chroot_mounted=1\n")
    mount_steps = src[mount_start:mount_end]
    assert "chroot_mounted=1" in mount_steps

    for stage in ("sysfs", "rbind", "rslave"):
        with tempfile.TemporaryDirectory(prefix="dniv-candidate-mount-") as tmp:
            log = Path(tmp) / "mount.log"
            script = f'''set -euo pipefail
work="{tmp}/work"
mnt="$work/root"
mkdir -p "$mnt"
mounted=1
chroot_mounted=0
sudo() {{
    printf '%s\\n' "$*" >> "{log}"
    if [[ "$1" == mount ]]; then
        case "{stage}" in
            sysfs) [[ "$*" == *"mount -t sysfs"* ]] && return 23 ;;
            rbind) [[ "$*" == *"mount --rbind"* ]] && return 24 ;;
            rslave) [[ "$*" == *"mount --make-rslave"* ]] && return 25 ;;
        esac
    fi
    return 0
}}
make() {{ return 0; }}
{cleanup}
trap cleanup EXIT
{mount_steps}
'''
            proc = subprocess.run(["bash", "-c", script], capture_output=True,
                                  text=True, timeout=5)
            assert proc.returncode in (23, 24, 25), (stage, proc.returncode, proc.stderr)
            operations = log.read_text().splitlines()
            assert f"umount {tmp}/work/root/proc" in operations, (stage, operations)
            if stage != "sysfs":
                assert f"umount {tmp}/work/root/sys" in operations, (stage, operations)



def check():
    for name in SOURCES:
        check_source(ROOT / name)
    print("candidate, PP12 and foundation partial mount cleanup source regression passed")


if __name__ == "__main__":
    check()
