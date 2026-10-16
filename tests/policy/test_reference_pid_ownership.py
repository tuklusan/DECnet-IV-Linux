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

"""Only a daemon owned by this reference VM launch may be signalled."""

from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tests/lab/dniv-reference-peer.sh"


def run_shell(script):
    return subprocess.run(["sh", "-eu", "-c", script], check=False,
                          text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=5)


def check():
    src = SOURCE.read_text()
    first = src.index("cleanup() {\n")
    last = src.index("\n}\ntrap cleanup EXIT INT TERM", first) + len("\n}\n")
    fn = src[first:last]
    between = src.index("EOF_ROUTE20\n", last) + len("EOF_ROUTE20\n")
    before_start = src.index('    "$route20_bin" /run/reference/route20.ini', between)
    startup = src[between:before_start]

    with tempfile.TemporaryDirectory(prefix="dniv-ref-pid-") as tmp:
        root = Path(tmp)
        pidfile = root / "route20.pid"
        log = root / "kills.log"
        # Substitute only the guest-global absolute pathname with private
        # fixture path before executing the actual source blocks.
        fn = fn.replace("/var/run/route20.pid", str(pidfile))
        startup = startup.replace("/var/run/route20.pid", str(pidfile))
        pidfile.write_text("9999\n")
        result = run_shell(f'session=test\nroute20_pidfile="{pidfile}"\n' + startup)
        assert result.returncode != 0, "preexisting pidfile accepted"
        assert pidfile.read_text() == "9999\n", "preexisting pidfile erased"

        def check_cleanup(reference, owned, pid, expected):
            pidfile.write_text(pid + "\n")
            log.write_text("")
            script = (f'reference={reference}\nprobe_pid=\n'
                      f'peer_pid={"4321" if reference == "pydecnet" else ""}\n'
                      f'route20_owned_pid={owned}\nroute20_pidfile="{pidfile}"\n'
                      f'kill() {{ printf "%s\\n" "$1" >>"{log}"; }}\n'
                      + fn + '\ncleanup\n')
            r = run_shell(script)
            assert r.returncode == 0, (reference, r.stderr)
            assert log.read_text().splitlines() == expected, (reference, owned, pid, log.read_text())

        check_cleanup("route20", "", "9999", [])
        check_cleanup("route20", "4321", "4321", ["4321"])
        check_cleanup("route20", "4321", "9999", [])
        check_cleanup("pydecnet", "", "9999", ["4321"])
        # An unowned PID file reached through a symlink must not be trusted.
        pidfile.unlink()
        pidfile.symlink_to(root / "target.pid")
        (root / "target.pid").write_text("4321\n")
        log.write_text("")
        script = (f'reference=route20\nprobe_pid=\npeer_pid=\n'
                  f'route20_owned_pid=4321\nroute20_pidfile="{pidfile}"\n'
                  f'kill() {{ printf "%s\\n" "$1" >>"{log}"; }}\n'
                  + fn + '\ncleanup\n')
        result = run_shell(script)
        assert result.returncode == 0 and log.read_text() == "", "symlink PID was signalled"
    print("Route20 reference PID ownership regression passed")


if __name__ == "__main__":
    check()
