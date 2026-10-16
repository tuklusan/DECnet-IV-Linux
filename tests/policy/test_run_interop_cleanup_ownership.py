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

"""Never remove a pre-existing interop session's TAP, bridge or API socket."""

from pathlib import Path
import subprocess

SOURCE = Path(__file__).resolve().parents[2] / "tests/lab/run-interop.sh"


def exercise(owned: bool) -> None:
    source = SOURCE.read_text(encoding="utf-8")
    start = source.index("terminate_pid() {")
    end = source.index("trap cleanup EXIT", start)
    # Exercise the actual production cleanup functions, with no privileged calls.
    shell = f"""set -eu
bridge=bi-test
tap_candidate=ci-test
tap_reference=ri-test
host_pydecnet_api=/tmp/dniv-test-preexisting.sock
bridge_owned={int(owned)}
tap_candidate_owned={int(owned)}
tap_reference_owned={int(owned)}
host_pydecnet_api_owned={int(owned)}
MOCK_LOG=$(mktemp)
sudo() {{ printf 'sudo:%s\\n' "$*" >> "$MOCK_LOG"; }}
rm() {{ printf 'rm:%s\\n' "$*" >> "$MOCK_LOG"; }}
{source[start:end]}
cleanup
cat "$MOCK_LOG"
command rm -f "$MOCK_LOG"
"""
    result = subprocess.run(["bash", "-c", shell], text=True, capture_output=True)
    if result.returncode:
        raise AssertionError(f"cleanup failed: {result.stderr}")
    actual = result.stdout.strip().splitlines()
    wanted = (
        [
            "rm:-f /tmp/dniv-test-preexisting.sock",
            "sudo:ip link del ci-test",
            "sudo:ip link del ri-test",
            "sudo:ip link del bi-test",
        ]
        if owned else []
    )
    if actual != wanted:
        raise AssertionError(f"owned={owned}, actual={actual}, expected={wanted}")


def main() -> None:
    exercise(False)
    exercise(True)
    source = SOURCE.read_text(encoding="utf-8")
    start = source.index("start_reference() {")
    end = source.index("wait_marker() {", start)
    if 'rm -f "$host_pydecnet_api"' in source[start:end]:
        raise AssertionError("reference child still unlinks an unowned API socket")
    if 'mkdir "$work"' not in source:
        raise AssertionError("pre-existing session directory is silently reused")
    print("Interop per-session network and socket ownership regression passed")


if __name__ == "__main__":
    main()
