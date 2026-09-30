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

"""Guard the E4 convergence harness against endpoint boot-skew false failures."""

from pathlib import Path

SMOKE = Path("tests/lab/dniv-smoke.sh").read_text(encoding="utf-8")
E4 = Path("tests/lab/dniv_e4.py").read_text(encoding="utf-8")
SCALE = Path("tests/lab/dniv_scale.py").read_text(encoding="utf-8")
LAB = Path("tests/lab/dniv_lab.py").read_text(encoding="utf-8")

required_smoke = (
    'probe_count=${probe_override:-180}',
    'reason=l1-not-ready',
    'reason=local-l1-not-ready',
    'reason=remote-l2-not-ready',
    'wait_any_adjacency_up "$peer_node" 640',
    'wait_any_adjacency_up "$dest_node" 640',
)
for marker in required_smoke:
    if marker not in SMOKE:
        raise SystemExit(f"E4-CONVERGENCE: missing smoke guard: {marker}")

required_controller = (
    'l1a_mac, "31.72", "32.73")',
    'l1b_mac, "32.72", "31.73")',
)
for marker in required_controller:
    if marker not in E4:
        raise SystemExit(f"E4-CONVERGENCE: missing controller guard: {marker}")

if SMOKE.count('probe_count=${probe_override:-180}') != 1:
    raise SystemExit("E4-CONVERGENCE: endpoint probe window is ambiguous")

required_scale = (
    'hold_endpoints = args.nodes >= 8',
    'endpoint_probes = 30 if args.nodes == 16 else 0',
    'scale-8: 8 simultaneous independent guests live',
    'hold_after_pass=hold_endpoints, probe_count=endpoint_probes',
    'scale-16: 16 simultaneous independent guests live',
    'lab.pause(a)',
    'lab.resume(endpoint)',
    'DNIV_SCALE_CMA_ZERO',
    'virtio-balloon-pci,id=balloon0',
    'lab.balloon(a, balloon_target)',
)
for marker in required_scale:
    if marker not in SCALE:
        raise SystemExit(f"E4-CONVERGENCE: missing scale16 guard: {marker}")

required_lab = (
    'guest_cpus = host_cpus[1:]',
    'len(guest_cpus) >= 2 * self.vcpus',
    'len(guest_cpus) >= self.vcpus + 1',
    'guest_cpus[-self.vcpus:]',
    '"arm64 diagnostic TCG requires one reserved host CPU plus "',
)
for marker in required_lab:
    if marker not in LAB:
        raise SystemExit(f"E4-CONVERGENCE: missing diagnostic host-CPU guard: {marker}")

print("E4-CONVERGENCE: pass")
