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

"""Live install and uninstall must never follow a foreign PREFIX symlink parent."""

from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def check_script(script_name: str) -> None:
    data = (ROOT / script_name).read_text(encoding="utf-8")
    start = data.index("check_staged_parent() {")
    end = data.index("safe_default_module_path() {", start) if script_name == "uninstall.sh" else data.index('if [[ -z "$destdir" && -n ${MODULE_ROOT:-} ]]', start)
    func = data[start:end]
    with tempfile.TemporaryDirectory(prefix="dniv-live-prefix-parent-") as tmp:
        work = Path(tmp)
        prefix = work / "local"
        prefix.mkdir()
        foreign = work / "foreign"
        foreign.mkdir()
        (prefix / "bin").symlink_to(foreign, target_is_directory=True)
        arguments = [(prefix / "bin" / "dnmirror", False), (prefix / "sbin" / "dnctl", True)]
        for path, wanted in arguments:
            shell = (
                "set -eu\n"
                "destdir=''\n"
                + 'prefix="$2"\n'
                + func + "\n"
                + 'check_staged_parent "$1"\n'
            )
            result = subprocess.run(["bash", "-c", shell, "bash", str(path), str(prefix)], text=True, capture_output=True)
            if (result.returncode == 0) != wanted:
                raise AssertionError(f"{script_name} live prefix parent: {path}: rc={result.returncode} stderr={result.stderr}")


def main() -> None:
    for script in ("install.sh", "uninstall.sh"):
        check_script(script)
    print("Live PREFIX symlink parent refusal regression passed")


if __name__ == "__main__":
    main()
