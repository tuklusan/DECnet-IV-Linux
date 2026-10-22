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
"""Actual-source FAL daemon positive decimal CLI must reject signed aliases.

Build with a socket link-wrap to prevent any live DECnet activity. A valid
number deliberately reaches the socket stub and exits 1; invalid input exits
2 before any attempt to allocate a socket.
"""

from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "userspace/dnfald/dnfald.c"
WRAPPER = r"""
#include <errno.h>
#include <sys/socket.h>
int __wrap_socket(int family, int type, int protocol) {
    (void)family; (void)type; (void)protocol;
    errno = EAFNOSUPPORT;
    return -1;
}
"""


def check():
    with tempfile.TemporaryDirectory(prefix="dniv-fal-cli-") as directory:
        path = Path(directory)
        stub = path / "socket.c"
        exe = path / "dnfald"
        stub.write_text(WRAPPER)
        subprocess.run([
            "cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
            "-I" + str(ROOT / "include/uapi"),
            str(SOURCE), str(stub), "-Wl,--wrap=socket", "-o", str(exe)
        ], check=True, capture_output=True, text=True)

        for value in ("+1", "+32", "-1", " 1", "1 ", "", "0", "33",
                      "18446744073709551617", "nope"):
            run = subprocess.run([str(exe), "--sessions", value],
                                 text=True, capture_output=True, timeout=5)
            assert run.returncode == 2 and "invalid session count" in run.stderr, (
                value, run.returncode, run.stderr)
        for value in ("1", "32", "01"):
            run = subprocess.run([str(exe), "--sessions", value],
                                 text=True, capture_output=True, timeout=5)
            assert run.returncode == 1 and "listen" in run.stderr, (
                value, run.returncode, run.stderr)
    print("FAL daemon strict positive unsigned --sessions regression passed")


if __name__ == "__main__":
    check()
