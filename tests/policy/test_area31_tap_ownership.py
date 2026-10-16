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

"""Source-derived no-root Area-31 bridge/TAP ownership and cleanup regression."""

from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tests/lab/prove-area31.sh"


def scenario(source: str, failure: str) -> None:
    prefix = source[source.index('work=$(mktemp -d /tmp/dniv-area31.XXXXXX)\n'):
                    source.index('trap cleanup EXIT INT TERM\n')]
    setup = source[source.index('    tap_suffix=$(printf'):
                   source.index('    vde_plug2tap -s "$sock"', source.index('    tap_suffix=$(printf'))]
    assert 'sudo ip link add name "$bridge_name" type bridge' in setup
    assert 'sudo ip tuntap add dev "$vde_tap_name"' in setup
    with tempfile.TemporaryDirectory(prefix="dniv-area31-tap-") as temp:
        events = Path(temp) / "events"
        program = (
            'set -euo pipefail\n'
            'EVENTS="$1"\nFAIL="$2"\n'
            'sudo() {\n'
            '  printf "%s\\n" "$*" >>"$EVENTS"\n'
            '  case "$*" in\n'
            '    "ip link add name "*) [[ "$FAIL" != bridge ]] || return 19 ;;\n'
            '    "ip tuntap add dev dnq"*) [[ "$FAIL" != qemu ]] || return 19 ;;\n'
            '    "ip tuntap add dev dnv"*) [[ "$FAIL" != vde ]] || return 19 ;;\n'
            '  esac\n'
            '  return 0\n'
            '}\n'
            + prefix + '\ntrap cleanup EXIT\n' + setup + '\n'
        )
        script = Path(temp) / "test.sh"
        script.write_text(program)
        subprocess.run(["bash", "-n", str(script)], check=True)
        finished = subprocess.run(["bash", str(script), str(events), failure],
                                  text=True, capture_output=True, timeout=8)
        assert (finished.returncode != 0) == (failure != "none"), finished
        calls = events.read_text().splitlines()
        adds = [x for x in calls if x.startswith("ip link add ") or
                x.startswith("ip tuntap add ")]
        deletes = [x for x in calls if x.startswith("ip link del ") or
                   x.startswith("ip tuntap del ")]
        if failure == "bridge":
            assert len(adds) == 1 and deletes == [], calls
        elif failure == "qemu":
            assert len(adds) == 2 and len(deletes) == 1, calls
            assert deletes[0].startswith("ip link del "), calls
        elif failure == "vde":
            assert len(adds) == 3 and len(deletes) == 2, calls
            assert deletes[0].startswith("ip tuntap del dev dnq"), calls
            assert deletes[1].startswith("ip link del "), calls
        else:
            assert len(adds) == 3 and len(deletes) == 3, calls
            assert sum(x.startswith("ip tuntap del dev ") for x in deletes) == 2
            assert sum(x.startswith("ip link del ") for x in deletes) == 1


def main() -> None:
    source = SOURCE.read_text()
    for failure in ("bridge", "qemu", "vde", "none"):
        scenario(source, failure)
    print("Area-31 bridge/TAP cleanup never removes resources whose creation failed")


if __name__ == "__main__":
    main()
