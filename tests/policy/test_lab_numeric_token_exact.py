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

"""Actual source programs reject unsigned strtoul sign/wrap aliases offline."""

from pathlib import Path
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
CFLAGS = ["-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", "-I", str(ROOT / "include/uapi")]

with tempfile.TemporaryDirectory() as tmp:
    directory = Path(tmp)
    shim = directory / "no-socket.c"
    shim.write_text("""#include <errno.h>
#include <sys/socket.h>
int socket(int domain, int type, int protocol) {
    (void)domain; (void)type; (void)protocol;
    errno = EAFNOSUPPORT; return -1;
}
""")
    so = directory / "no-socket.so"
    subprocess.run(["cc", "-shared", "-fPIC", str(shim), "-o", str(so)], check=True)
    env = dict(os.environ, LD_PRELOAD=str(so))

    cases = {
        "dnreset.c": lambda peer: [peer, "SESSION", "SCENARIO"],
        "dnseqwrap.c": lambda peer: [peer],
        "dnsignal.c": lambda peer: [peer],
        "dnsocklife.c": lambda peer: [peer],
        "dnsockstress.c": lambda peer: [peer],
        "dnstream.c": lambda peer: [peer],
        "dntermrace.c": lambda peer: [peer, "SESSION", "SCENARIO"],
        "dntimeout.c": lambda peer: [peer, "SESSION", "SCENARIO"],
        "dnwindow.c": lambda peer: [peer, "SESSION", "SCENARIO"],
    }
    malformed = ["-18446744073709551615.1", "1.-18446744073709551615",
                 "+1.1", "1.+1", " 1.1", "1. 1", "64.1", "31.1024",
                 "18446744073709551617.1", "1.18446744073709551617"]

    for name, args in cases.items():
        exe = directory / name.replace(".c", "")
        subprocess.run(["cc", *CFLAGS, str(ROOT / "tests/lab" / name), "-o", str(exe)], check=True)
        for value, code in [("31.70", 1), ("01.00070", 1)] + [(x, 2) for x in malformed]:
            run = subprocess.run([str(exe), *args(value)], capture_output=True, text=True, env=env, timeout=3)
            assert run.returncode == code, (name, value, code, run.returncode, run.stderr)

    # The optional cycle count is also a decimal unsigned token, not a C sign alias.
    life = directory / "dnsocklife"
    for value in ["-18446744073709551615", "+1", " 1", "10001",
                  "18446744073709551617"]:
        run = subprocess.run([str(life), "31.70", value], capture_output=True, text=True, env=env, timeout=3)
        assert run.returncode == 2, ("dnsocklife cycles", value, run.returncode, run.stderr)

    smtp = directory / "dnsmtpfake"
    subprocess.run(["cc", *CFLAGS, str(ROOT / "tests/lab/dnsmtpfake.c"), "-o", str(smtp)], check=True)
    for value, code in [("2525", 1), ("65535", 1), ("-18446744073709551615", 2),
                        ("+1", 2), (" 1", 2), ("65536", 2), ("18446744073709551617", 2)]:
        run = subprocess.run([str(smtp), value, str(directory / "output")], capture_output=True, text=True, env=env, timeout=3)
        assert run.returncode == code, ("dnsmtpfake", value, code, run.returncode, run.stderr)

print("lab DECnet/socket port strict unsigned-token regression passed")
