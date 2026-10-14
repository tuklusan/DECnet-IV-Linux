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

"""Partial remote SSH/socat markers must not bypass the declared timeout."""

import os
from pathlib import Path
import re
import select
import time

SOURCE = Path(__file__).resolve().parents[2] / "tests/lab/probe-socat-rendezvous.sh"


def run_probe(reader, data: bytes, timeout: float, *, close_write: bool = False):
    r, w = os.pipe()
    try:
        if data:
            os.write(w, data)
        if close_write:
            os.close(w)
            w = -1
        with os.fdopen(r, "rb", buffering=0) as pipe:
            r = -1
            start = time.monotonic()
            result = reader(pipe, timeout)
            elapsed = time.monotonic() - start
            return result, elapsed
    finally:
        if r >= 0:
            os.close(r)
        if w >= 0:
            os.close(w)


def main() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    snippets = re.findall(
        r"(?ms)^def read_marker\(stream, timeout\) -> str \| None:\n"
        r".*?(?=^cfg, sock, run_id = sys\.argv\[1:\])",
        source,
    )
    if len(snippets) != 2 or snippets[0] != snippets[1]:
        raise AssertionError("server/client bounded marker helper mismatch")
    if "read_marker(p.stdout, 75)" not in source or \
            "read_marker(p.stdout, 20)" not in source or \
            ".stdout.readline()" in source:
        raise AssertionError("server/client must use deadline-aware marker reads")
    namespace = {"os": os, "select": select, "time": time}
    exec(snippets[0], namespace)
    reader = namespace["read_marker"]
    result, elapsed = run_probe(reader, b"DNIV-SOCAT-SERV", 0.10)
    if result is not None or elapsed > 0.6:
        raise AssertionError(f"partial marker bypassed 100ms timeout: {result!r} {elapsed:.3f}")
    good = "DNIV-SOCAT-SERVER 100-1"
    result, elapsed = run_probe(reader, (good + "\n").encode(), 0.5)
    if result != good or elapsed > 0.5:
        raise AssertionError(f"valid complete marker rejected: {result!r} {elapsed:.3f}")
    result, _ = run_probe(reader, b"partial", 0.5, close_write=True)
    if result is not None:
        raise AssertionError("EOF accepted as complete marker")
    try:
        run_probe(reader, b"X" * 258 + b"\n", 0.5)
    except RuntimeError as exc:
        if "overlong remote marker" not in str(exc):
            raise
    else:
        raise AssertionError("overlong untrusted marker accepted")
    print("socat marker exact-timeout, partial line, EOF, valid and oversized negatives passed")


if __name__ == "__main__":
    main()
