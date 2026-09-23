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

required_smoke = (
    'probe_count=180',
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

if SMOKE.count('probe_count=180') != 1:
    raise SystemExit("E4-CONVERGENCE: endpoint probe window is ambiguous")

print("E4-CONVERGENCE: pass")
