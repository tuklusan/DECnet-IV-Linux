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

"""Compile exact Session Control CI decoder and reject invalid wire payloads."""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def extract_function(source: str, name: str) -> str:
    match = re.search(r"(?m)^static int " + re.escape(name) + r"\([^;]*?\)\s*\{", source, re.S)
    if not match:
        raise AssertionError("missing actual Session Control function: " + name)
    begin = match.start()
    index = match.end()
    depth = 1
    while depth:
        if index >= len(source):
            raise AssertionError("unbalanced source function: " + name)
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
        index += 1
    return source[begin:index]


HEADER = r"""
#include <errno.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <linux/dn.h>
#define cpu_to_le16(x) ((__le16)(x))
#define DNIV_SC_MENU_ACCESS 0x01U
#define DNIV_SC_MENU_USER 0x02U
"""

CASES = r"""
static int check(const unsigned char *buf, size_t n, bool permitted,
                 const char *name)
{
    struct sockaddr_dn dst, src;
    struct accessdata_dn access;
    struct optdata_dn data;
    int ret = dniv_ci_decode(buf, (__u16)n, &dst, &src, &access, &data);

    if ((ret == 0) != permitted) {
        fprintf(stderr, "%s: got %d but permitted=%d\n", name, ret, permitted);
        return 1;
    }
    return 0;
}
int main(void)
{
    /* Object 7 with generic Session Control source name LINUX. */
    const unsigned char valid[] = {0,7,1,0,5,'L','I','N','U','X',0};
    const unsigned char bad_destination_type[] = {1,6,4,'T','E','S','T',1,0,5,'L','I','N','U','X',0};
    const unsigned char bad_source_type[] = {0,7,1,6,5,'L','I','N','U','X',0};
    const unsigned char reserved_source_format4[] = {0,7,4,0,0,0,0,0,0,0,0,0,5,'L','I','N','U','X',0};
    const unsigned char user[] = {0,7,1,0,5,'L','I','N','U','X',2,1,'X'};
    const unsigned char access[] = {0,7,1,0,5,'L','I','N','U','X',1,1,'U',1,'P',1,'A'};
    const unsigned char both[] = {0,7,1,0,5,'L','I','N','U','X',3,1,'U',1,'P',1,'A',1,'X'};
    const unsigned char extra[] = {0,7,1,0,5,'L','I','N','U','X',0,0xaa};
    const unsigned char user_extra[] = {0,7,1,0,5,'L','I','N','U','X',2,1,'X',0xaa};
    const unsigned char reserved[] = {0,7,1,0,5,'L','I','N','U','X',4};
    const unsigned char reserved_version[] = {0,7,1,0,5,'L','I','N','U','X',32};
    const unsigned char unknown_high[] = {0,7,1,0,5,'L','I','N','U','X',128};
    const unsigned char short_access[] = {0,7,1,0,5,'L','I','N','U','X',1,1,'U'};
    const unsigned char short_user[] = {0,7,1,0,5,'L','I','N','U','X',2,4,'X'};
    const unsigned char both_extra[] = {0,7,1,0,5,'L','I','N','U','X',3,1,'U',1,'P',1,'A',1,'X',0xff};
    int failures = 0;

#define CHECK(b, ok) (failures += check((b), sizeof(b), (ok), #b))
    CHECK(valid, true);
    CHECK(bad_destination_type, false);
    CHECK(bad_source_type, false);
    CHECK(reserved_source_format4, false);
    CHECK(user, true);
    CHECK(access, true);
    CHECK(both, true);
    CHECK(extra, false);
    CHECK(user_extra, false);
    CHECK(reserved, false);
    CHECK(reserved_version, false);
    CHECK(unknown_high, false);
    CHECK(short_access, false);
    CHECK(short_user, false);
    CHECK(both_extra, false);
    if (!failures)
        puts("Session Control CI decoder accepted only fully framed v1 payloads");
    return failures ? 1 : 0;
}
"""


def main() -> int:
    source = (ROOT / "kernel/decnet/decnet_iv_socket.c").read_text(encoding="utf-8")
    functions = "\n\n".join(extract_function(source, name) for name in (
        "dniv_enduser_decode", "dniv_counted_field_validate", "dniv_ci_decode"))
    with tempfile.TemporaryDirectory(prefix="dniv-ci-regression-") as temporary:
        tmp = Path(temporary)
        (tmp / "test.c").write_text(HEADER + functions + CASES, encoding="utf-8")
        command = shlex.split(os.environ.get("CC", "cc")) + [
            "-std=gnu11", "-O1", "-Wall", "-Wextra", "-Werror",
            "-I" + str(ROOT / "include/uapi"),
            str(tmp / "test.c"), "-o", str(tmp / "test")]
        subprocess.run(command, check=True, timeout=60)
        subprocess.run([str(tmp / "test")], check=True, timeout=20)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
