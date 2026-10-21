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

"""Sign and modulo aliases must not become valid unsigned CLI options.

Compile each actual delivered C CLI with a linker-only socket stub. This
prevents accidental network listeners during positive controls and verifies
the REAL startup/parser rather than a duplicated Python approximation.
"""

from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SHIM = """
#include <errno.h>
int __wrap_socket(int family, int type, int protocol)
{
    (void)family;
    (void)type;
    (void)protocol;
    errno = EAFNOSUPPORT;
    return -1;
}
"""
TARGETS = (
    ("userspace/dnobject/dnobject.c", "--number", ("1", "0241", "255")),
    ("userspace/dnnml/dnnml.c", "--sessions", ("1", "01", "32")),
    ("userspace/dnmail/dnmaild.c", "--smtp-port", ("1", "025", "65535")),
)
BAD = ("+1", "-18446744073709551615", " 1", "1 ", "1x",
       "0", "65536", "18446744073709551617", "")

with tempfile.TemporaryDirectory() as temp:
    directory = Path(temp)
    stub = directory / "socket_stub.c"
    stub.write_text(SHIM, encoding="utf-8")
    for index, (source, option, valid) in enumerate(TARGETS):
        exe = directory / f"program{index}"
        subprocess.run(
            ["cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
             "-I" + str(ROOT / "include/uapi"),
             "-I" + str(ROOT / "include"),
             str(ROOT / source), str(stub), "-Wl,--wrap=socket",
             "-o", str(exe)],
            check=True, timeout=30,
        )
        for value in valid:
            result = subprocess.run(
                [str(exe), option, value], capture_output=True, timeout=3
            )
            assert result.returncode == 1, (source, value, result.returncode)
        for value in BAD:
            result = subprocess.run(
                [str(exe), option, value], capture_output=True, timeout=3
            )
            assert result.returncode == 2, (source, value, result.returncode)

print("canonical unsigned CLI options regression passed")
