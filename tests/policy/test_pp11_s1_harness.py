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

"""Lock PP-11 S1 reboot and reciprocal-actor harness invariants."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAB = (ROOT / "tests/lab/dniv_lab.py").read_text(encoding="utf-8")
SMOKE = (ROOT / "tests/lab/dniv-smoke.sh").read_text(encoding="utf-8")
CONTROL = (ROOT / "tests/lab/dniv_pp11_s1.py").read_text(encoding="utf-8")


def main() -> int:
    required_lab = (
        'if self.mode != "pp11s1":',
        'cmd.append("-no-reboot")',
    )
    for marker in required_lab:
        if marker not in LAB:
            raise SystemExit(f"pp11-s1 regression: missing reboot guard: {marker}")
    for marker in (
        'reset_ack = QmpClient(guest.qmp).execute("system_reset")',
        'qmp_ack={int(reset_ack)}',
        'match = pattern.search(line.strip())',
    ):
        if marker not in CONTROL:
            raise SystemExit(f"pp11-s1 regression: missing reboot/evidence guard: {marker}")
    if 'raise RuntimeError(f"pp11-s1: QMP reset failed' in CONTROL:
        raise SystemExit("pp11-s1 regression: reset reply ambiguity must defer to boot-effect proof")
    if CONTROL.count('match = pattern.search(line.strip())') != 3:
        raise SystemExit("pp11-s1 regression: serial evidence parsers must accept syslog prefixes")
    if 'MAX_ANY_LINKS = 32' not in CONTROL or 'peak_links > MAX_ANY_LINKS' not in CONTROL:
        raise SystemExit("pp11-s1 regression: missing transient NSP link bound")
    handoff = "pp11_observe 35\n            # The observer records the peer's final UP transition"
    if handoff not in SMOKE or "sleep 25\n            pp11_actor" not in SMOKE:
        raise SystemExit("pp11-s1 regression: missing reciprocal actor handoff gap")
    print("pp11-s1 regression passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
