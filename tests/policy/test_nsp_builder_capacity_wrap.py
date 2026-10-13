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

"""Reject 32-bit NSP packet lengths before arithmetic wraps output capacity."""

import os
import shlex
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

HARNESS = r"""
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "decnet_iv_nsp_wire.h"

int main(void)
{
    unsigned char out[32] = {0}, value = 0x41;
    struct dniv_nsp_packet pkt = {0};
    int size;

    pkt.type = DNIV_NSP_DATA;
    pkt.payload = &value;
    pkt.payload_len = UINT32_MAX;
    if (dniv_nsp_build(out, sizeof(out), &pkt) != -1)
        return 1;
    pkt.payload_len = UINT32_MAX - 6U;
    if (dniv_nsp_build(out, sizeof(out), &pkt) != -1)
        return 2;

    pkt.type = DNIV_NSP_CI;
    pkt.payload_len = UINT32_MAX;
    if (dniv_nsp_build(out, sizeof(out), &pkt) != -1)
        return 3;

    pkt.type = DNIV_NSP_DATA;
    pkt.payload_len = 1U;
    size = dniv_nsp_build(out, sizeof(out), &pkt);
    if (size != 8 || out[7] != value)
        return 4;

    pkt.type = DNIV_NSP_DI;
    pkt.payload_len = UINT32_MAX;
    if (dniv_nsp_build(out, sizeof(out), &pkt) != -1)
        return 5;
    puts("NSP builder capacity arithmetic rejects wraparound");
    return 0;
}
"""


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="dniv-nsp-wrap-") as directory:
        src = Path(directory) / "check.c"
        binary = Path(directory) / "check"
        src.write_text(HARNESS, encoding="utf-8")
        subprocess.run(shlex.split(os.environ.get("CC", "cc")) + [
            "-std=c11", "-O0", "-Wall", "-Wextra", "-Werror",
            "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
            "-I" + str(ROOT / "include"),
            str(src), "-o", str(binary)
        ], check=True, timeout=60)
        subprocess.run([str(binary)], check=True, timeout=10)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
