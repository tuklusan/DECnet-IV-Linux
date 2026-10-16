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

"""Only remove cross-runner VDE sockets owned by this invocation."""

from pathlib import Path
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tests/lab/prove-vde2-cross-runner.sh"


def run_case(script: str, work: Path, log: Path) -> tuple[int, list[str]]:
    env = os.environ.copy()
    env["DNIV_VDE_LOG"] = str(log)
    p = subprocess.run(["bash", "-c", script], env=env, check=False,
                       text=True, capture_output=True, timeout=5)
    return p.returncode, log.read_text().splitlines() if log.exists() else []


def main() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    cleanup = source.split("\ncleanup() {\n", 1)[1].split("\n}\ntrap cleanup EXIT", 1)[0]
    cleanup = "cleanup() {\n" + cleanup + "\n}\n"
    start = source.split("\nstart_switch() {\n", 1)[1].split("\n}\n\nif [[ \"$1\" == \"--server\" ]]", 1)[0]
    start = "start_switch() {\n" + start + "\n}\n"
    with tempfile.TemporaryDirectory(prefix="dniv-vde-ownership-") as td:
        root = Path(td)
        server = root / "server.ctl"
        server.mkdir()
        for owned in (False, True):
            log = root / f"cleanup-{int(owned)}.log"
            script = (
                'set -euo pipefail\n'
                f'work="{root}/work"\n'
                f'server_sock="{server}"\n'
                f'switch_sock_owned={"$server_sock" if owned else ""}\n'
                'switch_pid=\nbridge_pid=\npy_pid=\necho_pid=\nroute20_pid=\n'
                'stop_pid() { :; }\nstop_process_tree() { :; }\n'
                'rm() { printf "rm:%s\\n" "$*" >> "$DNIV_VDE_LOG"; }\n'
                + cleanup + 'cleanup\n'
            )
            rc, operations = run_case(script, root, log)
            removed_server = any(str(server) in line for line in operations)
            if rc or removed_server != owned:
                raise AssertionError(
                    f"cleanup owned={owned}: rc={rc} actions={operations}"
                )

        log = root / "preexisting.log"
        script = (
            'set -euo pipefail\n'
            f'sock="{server}"\n'
            'switch_sock_owned=\n'
            'vde_switch_bin=false\n'
            'rm() { printf "rm:%s\\n" "$*" >> "$DNIV_VDE_LOG"; }\n'
            'pgrep() { return 1; }\nsleep() { :; }\n'
            + start + 'start_switch "$sock"\n'
        )
        rc, operations = run_case(script, root, log)
        if rc == 0 or operations:
            raise AssertionError(
                f"pre-existing socket directory must be refused intact: rc={rc} actions={operations}"
            )
        if not server.is_dir():
            raise AssertionError("existing VDE socket directory damaged")

    print("cross-runner VDE socket ownership regression passed")


if __name__ == "__main__":
    main()
