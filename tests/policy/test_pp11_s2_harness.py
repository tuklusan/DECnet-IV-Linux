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

"""Lock fail-closed PP-11 S2 production requirements."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTROL = (ROOT / "tests/lab/dniv_pp11_s2.py").read_text(encoding="utf-8")
INJECT = (ROOT / "tests/lab/inject-pp11-s2.py").read_text(encoding="utf-8")
SMOKE = (ROOT / "tests/lab/dniv-smoke.sh").read_text(encoding="utf-8")
VM = (ROOT / ".github/workflows/vm-lab.yml").read_text(encoding="utf-8")
DISPATCH = (ROOT / ".github/workflows/repository-policy.yml").read_text(encoding="utf-8")


def main() -> int:
    for marker in (
        "FAULT_EVENTS = 10000",
        "FAULT_DURATION = 3600.0",
        "VALID_PROBES = 1200",
        '"VM_COUNT=4"',
        "captured_faults < FAULT_EVENTS",
        "float(duration_match.group(1)) < FAULT_DURATION",
        "MIN_RESOURCE_SAMPLES = 50",
        "MAX_SLAB_GROWTH_KB = 65536",
        "MAX_LINKS = 32",
        "MIN_FORWARDED = 1000",
        "MIN_TRAFFIC_SPAN_SECONDS = FAULT_DURATION - 10.0",
        "MAX_VALID_GAP_SECONDS = 30.0",
        "span < MIN_TRAFFIC_SPAN_SECONDS",
        "max_gap > MAX_VALID_GAP_SECONDS",
        "magic = data[:4].hex()",
        '"d4c3b2a1"',
        '"a1b23c4d"',
        'frame[12:14].hex() != "6003"',
        '"DN70": require_forwarded',
        '"DN73": require_forwarded',
        '"DN71": require_forwarded',
    ):
        if marker not in CONTROL:
            raise SystemExit(f"pp11-s2 regression: missing controller guard: {marker}")
    for marker in (
        "default=10000",
        "default=3600.0",
        "args.events < 10000",
        "args.duration < 3600.0",
        "EVENTS_SENT={sent}",
        "DURATION_ACTUAL={elapsed:.3f}",
        "DNIV-S2-FAULT-",
    ):
        if marker not in INJECT:
            raise SystemExit(f"pp11-s2 regression: missing injector guard: {marker}")
    for marker in (
        "DNIV-PP11-S2-TRAFFIC-READY",
        "DNIV-PP11-S2-VALID-",
        "DNIV-PP11-S2-RESOURCE",
        "DNIV-PP11-S2-PASS",
        "pp11-s2-valid-hold-send",
        'pp11_s2_resource "hold-$i"',
        "sleep 2",
        "i % 20",
        "sleep 45",
    ):
        if marker not in SMOKE:
            raise SystemExit(f"pp11-s2 regression: missing guest guard: {marker}")
    for marker in (
        "          - pp11s2",
        '[[ "${DNIV_LAB_MODE}" == pp11s2 ]]',
        "tests/lab/dniv_pp11_s2.py",
        "    timeout-minutes: 75",
    ):
        if marker not in VM:
            raise SystemExit(f"pp11-s2 regression: missing VM workflow guard: {marker}")
    for marker in (
        "all|socket|routing|pp11-pressure|pp11-s2|pp12|post-timing|source-release",
        'scope" != pp11-s2',
        "VM_LAB_PP11_S2=vm-lab.yml:pp11s2:virtio-net-pci:1vcpu",
        "-f lab_mode=pp11s2 -f nic_model=virtio-net-pci -f vcpus=1",
    ):
        if marker not in DISPATCH:
            raise SystemExit(f"pp11-s2 regression: missing acceptance dispatch guard: {marker}")
    print("pp11-s2 regression passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
