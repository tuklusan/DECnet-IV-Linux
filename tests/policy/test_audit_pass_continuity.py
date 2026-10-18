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

"""A mid-pass defect must not erase exhaustive discovery coverage."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCES = {
    "docs/HANDOVER.md": ("The current release blocker", "The **final production deliverable"),
    "docs/PROJECT_STATE.md": ("### Current completion sequence", "## References and licensing"),
    "docs/ROADMAP.md": ("The current ordered completion path is:", "The Phase 9 product"),
    "docs/DELIVERY.md": ("## Release completion sequence", "Production publication is fail-closed"),
}


def validate(text: str) -> None:
    assert "SAME" in text, "discovery pass continuation missing"
    assert "next unreviewed file" in text, "lexical continuation missing"
    assert "only" in text.casefold() and "end" in text.casefold(), "end-of-pass adjudication missing"
    assert "NO clean credit" in text, "defect-bearing pass falsely certifiable"
    assert "0/3" in text, "formal count missing"
    assert "3/3" in text or "three independent" in text, "three clean scans missing"


def checkpoint_contract(section: str) -> None:
    lowered = section.casefold()
    assert "checkpoint only at the end" in lowered, "mid-pass requalification still required"
    assert "not after individual repairs" in lowered, "per-fix checkpoint rule remains"
    assert "four" in lowered, "all four mandatory source gates missing"
    assert "fresh" in lowered, "fresh exact-source artifact proof missing"


def main() -> int:
    for path, (start, stop) in SOURCES.items():
        data = (ROOT / path).read_text(encoding="utf-8")
        assert data.count(start) == 1, path
        assert data.count(stop) >= 1, path
        section = data.split(start, 1)[1].split(stop, 1)[0]
        validate(section)
        checkpoint_contract(section)

    # Source-derived negative: old per-fix gates must not be certifiable.
    old_rule = "SAME next unreviewed file ONLY at END NO clean credit 0/3 3/3; four gates and fresh artifact after every repair"
    try:
        checkpoint_contract(old_rule)
    except AssertionError:
        pass
    else:
        raise AssertionError("per-repair requalification falsely accepted")

    # An old immediate-restart instruction must not pass the same test.
    negative = "SAME pass next unreviewed file ONLY at END NO clean credit 0/3 3/3"
    validate(negative)
    for marker in ("SAME", "next unreviewed file", "ONLY", "END", "NO clean credit", "0/3", "3/3"):
        try:
            validate(negative.replace(marker, "", 1))
        except AssertionError:
            continue
        raise AssertionError("audit continuity negative fixture was accepted: " + marker)
    print("audit pass continuity: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
