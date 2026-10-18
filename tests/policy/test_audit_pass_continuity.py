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
    # A run of the four mandatory hosted gates belongs AFTER all three
    # complete semantic scans of one frozen, byte-identical archive.
    lowered = section.casefold()
    pos = lowered.find("checkpoint")
    assert pos >= 0 and (
        "after all three complete zero-defect passes" in lowered[pos:pos + 110]
    ), "four-gate checkpoint must follow all three whole-source scans"
    assert (
        "no four-gate qualification after" in lowered
        or "do not run full four-gate requalification after" in lowered
    ), "per-repair/per-discovery gate dispatch still required"
    assert ("four green" in lowered or "four mandatory" in lowered), "mandatory four-gate source qualification lost"
    assert "provisional" in lowered, "pre-gate reviews falsely certified"
    assert "sha-256" in lowered, "archive byte identity proof missing"
    assert "artifact" in lowered and "download" in lowered, "post-gate artifact verification missing"


def main() -> int:
    for path, (start, stop) in SOURCES.items():
        data = (ROOT / path).read_text(encoding="utf-8")
        assert data.count(start) == 1, path
        assert data.count(stop) >= 1, path
        section = data.split(start, 1)[1].split(stop, 1)[0]
        validate(section)
        checkpoint_contract(section)

    # RED old policy (end-of-discovery checkpoints) is forbidden.
    old_rule = (
        "SAME next unreviewed file ONLY at END NO clean credit 0/3 3/3; "
        "the four-gate checkpoint is after each completed discovery pass, "
        "not after individual repairs. Fresh artifact."
    )
    try:
        checkpoint_contract(old_rule)
    except AssertionError:
        pass
    else:
        raise AssertionError("end-of-discovery requalification falsely accepted")

    # Positive fixture, with adversarial removal of independent safeguards.
    clean_rule = (
        "The four-gate CHECKPOINT is AFTER ALL THREE complete zero-defect passes. "
        "NO four-gate qualification after individual repairs OR after a discovery pass. "
        "All scans are PROVISIONAL until FOUR green gates. Match the exact SHA-256 "
        "of the fresh downloaded artifact against all three scanned archives."
    )
    checkpoint_contract(clean_rule)
    for marker in (
        "AFTER ALL THREE complete zero-defect passes",
        "NO four-gate qualification after",
        "FOUR green gates",
        "PROVISIONAL",
        "SHA-256",
        "artifact",
        "downloaded",
    ):
        try:
            checkpoint_contract(clean_rule.replace(marker, "", 1))
        except AssertionError:
            continue
        raise AssertionError("audit checkpoint negative fixture was accepted: " + marker)

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
