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

"""Area-31 preflight must reject numerically identical padded node aliases."""

from pathlib import Path
import os
import subprocess


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tests/lab/prove-area31.sh"


def preflight(vax, gateway, linux, qcocal=""):
    env = os.environ.copy()
    env.update({
        "MULTINET_REMOTE_HOST": "example.invalid",
        "MULTINET_REMOTE_PORT": "60001",
        "VAX_ADDR": vax,
        "VAX_USERNAME": "TEST",
        "VAX_PASSWORD": "TEST",
        "DNIV_AREA31_GATEWAY_NODE": gateway,
        "DNIV_AREA31_GATEWAY_NAME": "DNIV31",
        "DNIV_AREA31_LINUX_NODE": linux,
        "DNIV_AREA31_LINUX_NAME": "DNIV32",
        "DNIV_QCOCAL_NODE": qcocal,
        "DNIV_AREA31_ARCH": "amd64",
    })
    return subprocess.run(["bash", str(SCRIPT), "--preflight-only"], env=env,
                          capture_output=True, text=True, timeout=5)


GUEST = ROOT / "tests/lab/dniv-area31-smoke.sh"


def guest_identity(linux, gateway, target, qcocal, guest_source=None):
    source = GUEST.read_text() if guest_source is None else guest_source
    start = source.index("parse_node() {")
    end = source.index("\nread_field() {", start)
    functions = source[start:end]
    start = source.index('parse_node "$linux_node" || fail bad-linux-node') if (
        'parse_node "$linux_node" || fail bad-linux-node' in source
    ) else source.index('linux_node=$(canonical_node "$linux_node") || fail bad-linux-node')
    end = source.index("\niface=", start)
    validation = source[start:end]
    fixture = ("set -eu\n" + functions +
               '\nfail() { echo "REJECT:$1" >&2; exit 2; }\n' +
               f"linux_node={linux}\nlinux_name=DNIV\n"
               f"gateway_node={gateway}\ntarget={target}\nqcocal={qcocal}\n" +
               validation +
               '\nprintf "PASS nodes=%s,%s,%s,%s\\n" "$linux_node" "$gateway_node" "$target" "$qcocal"\n')
    return subprocess.run(["sh", "-c", fixture], capture_output=True,
                          text=True, timeout=5)


def check_guest_identity():
    for args in (
        ("31.003", "31.3", "31.13", "31.14"),
        ("31.3", "31.004", "31.4", "31.14"),
        ("31.8", "31.9", "31.0004", "31.4"),
        ("31.8", "31.9", "31.10", "31.0010"),
    ):
        result = guest_identity(*args)
        assert result.returncode == 2 and "duplicate" in result.stderr, (
            args, result.returncode, result.stdout, result.stderr)
    result = guest_identity("31.0008", "31.0009", "31.0010", "31.0011")
    assert result.returncode == 0 and result.stdout.strip() == (
        "PASS nodes=31.8,31.9,31.10,31.11"), (
        result.returncode, result.stdout, result.stderr)


def check():
    for args in (
        ("31.0008", "31.8", "31.9", "31.10"),
        ("31.8", "31.0009", "31.9", "31.10"),
        ("31.8", "31.9", "31.10", "31.0009"),
        ("31.8", "31.9", "31.0010", "31.10"),
    ):
        result = preflight(*args)
        assert result.returncode == 2, (args, result.returncode, result.stdout, result.stderr)
        assert "distinct" in result.stderr, (args, result.stderr)
    for args in (
        ("31.8", "31.9", "31.10", "31.11"),
        ("31.0008", "31.0009", "31.0010", "31.0011"),
    ):
        result = preflight(*args)
        assert result.returncode == 0 and "preflight pass" in result.stdout, (
            args, result.returncode, result.stdout, result.stderr)
    check_guest_identity()
    print("Area-31 numeric identity preflight and guest source regressions passed")


if __name__ == "__main__":
    check()
