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

"""Reject HTTP requests with an early header terminator and hidden suffix."""

import os
import shlex
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

HARNESS = r'''
#define main original_dnhttpd_main
#include "dnhttpd.c"
#undef main

int main(void)
{
    char name[512];
    static const unsigned char valid[] =
        "GET / HTTP/1.1\r\nHost: DNIV\r\n\r\n";
    static const unsigned char valid_empty[] =
        "GET / HTTP/1.0\r\n\r\n";
    static const unsigned char hidden_header[] =
        "GET / HTTP/1.0\r\n\r\nHIDDEN\r\n\r\n";
    static const unsigned char hidden_second_request[] =
        "GET / HTTP/1.0\r\nHost: DNIV\r\n\r\n"
        "GET /private HTTP/1.0\r\n\r\n";
    static const unsigned char repeated_terminator[] =
        "GET / HTTP/1.0\r\n\r\n\r\n";

    if (parse_request_line(valid, sizeof(valid) - 1U, name,
                           sizeof(name)) || strcmp(name, "index.html"))
        return 1;
    if (parse_request_line(valid_empty, sizeof(valid_empty) - 1U, name,
                           sizeof(name)))
        return 2;
    if (!parse_request_line(hidden_header, sizeof(hidden_header) - 1U,
                            name, sizeof(name)))
        return 3;
    if (!parse_request_line(hidden_second_request,
                            sizeof(hidden_second_request) - 1U,
                            name, sizeof(name)))
        return 4;
    if (!parse_request_line(repeated_terminator,
                            sizeof(repeated_terminator) - 1U,
                            name, sizeof(name)))
        return 5;
    return 0;
}
'''


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="dniv-http-framing-") as directory:
        source = Path(directory) / "check.c"
        binary = Path(directory) / "check"
        source.write_text(HARNESS, encoding="utf-8")
        subprocess.run(shlex.split(os.environ.get("CC", "cc")) + [
            "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
            "-I" + str(ROOT / "userspace/dnhttpd"),
            "-I" + str(ROOT / "include/uapi"),
            str(source), "-o", str(binary)
        ], check=True, timeout=60)
        subprocess.run([str(binary)], check=True, timeout=10)
    print("dnhttpd rejects early HTTP header terminators")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
