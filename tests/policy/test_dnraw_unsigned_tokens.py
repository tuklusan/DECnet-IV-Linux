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

"""Reject sign/overflow aliases in actual dnraw DECnet and MAC arguments."""

from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
raw = root / "tests/lab/dnraw.c"
iface = "dniv-audit-not-real0"  # No socket, interface or remote node needed.
mac = "52:54:00:00:00:01"

with tempfile.TemporaryDirectory() as tmp:
    binary = Path(tmp) / "dnraw"
    subprocess.run(["cc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                    str(raw), "-o", str(binary)], check=True)

    def probe(args, expected):
        proc = subprocess.run([str(binary), *args], capture_output=True, text=True)
        assert proc.returncode == expected, (args, proc.returncode, proc.stderr)
        if expected == 2:
            assert "invalid" in proc.stderr or "payload" in proc.stderr, proc.stderr

    # A syntactically valid frame reaches interface lookup and returns 1.
    probe([iface, mac, "DATA"], 1)
    probe(["--short", iface, mac, "31.70", "31.71", "0", "DATA"], 1)
    probe(["--short-rqr", iface, "0x52:54:00:00:00:01", "01.00070", "31.71", "63", "DATA"], 1)

    for bad in ("-4294967295.1", "1.-4294967295", "4294967297.1",
                "1.4294967297", "-1.1", "1.+1", "1.1extra", "0.1", "31.1024"):
        probe(["--short", iface, mac, bad, "31.71", "0", "DATA"], 2)
        probe(["--short", iface, mac, "31.70", bad, "0", "DATA"], 2)

    for bad in ("-ffffffff:54:00:00:00:01", "52:+54:00:00:00:01",
                "100000052:54:00:00:00:01", "52:54:00:00:00:100000001",
                "52:54:00:00:00:gg", "52:54:00:00:00:01junk"):
        probe([iface, bad, "DATA"], 2)
        probe(["--short", iface, bad, "31.70", "31.71", "0", "DATA"], 2)

print("dnraw decimal/hex unsigned-token validation regression passed")
