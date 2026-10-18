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

"""Require historical PP proof survives GC only if originally verified/recorded."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
led = (ROOT / 'docs/PP_EVIDENCE.md').read_text()
plan = (ROOT / 'docs/PRE_PRODUCTION_TEST.md').read_text()
hand = (ROOT / 'docs/HANDOVER.md').read_text()
rel = (ROOT / 'docs/DELIVERY.md').read_text()
lab = (ROOT / 'docs/TEST_LAB.md').read_text()

assert 'must actually have existed and been checked' in led
assert 'before** routine Actions-history/cache cleanup' in led
assert 'missing, incomplete, unverified, stale or mismatched proof never counts' in led
assert 'durably recorded before any cleanup' in led
assert 'never actually produced, verified and recorded invalidates the run' in plan
assert 'later routine removal of already-verified actions artifacts/logs' in plan.lower()
assert 'active unverified gate or a fresh-download requirement still needs the actual exact artifact' in plan
assert 'later housekeeping' in plan
assert 'recorded proof lineage survives routine Actions artifact/log/cache expiry' in plan
assert 'historical closure remains valid' in hand
assert 'historical closure remains valid after authorized deletion' in lab.lower()
assert 'independently checked at original closure' in lab.lower()
assert 'originally unverified proof never counts' in lab.lower()
assert 'active new exact-SHA gate still needs its actual fresh-download artifact' in lab
assert 'unverified, stale, failed, skipped or missing original evidence' in hand
assert 'each clean scan freshly downloads that identical accepted tarball' in rel.lower()
print('historical PP evidence closure and Actions cleanup policy passed')
