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

"""Inspect real socket-lifecycle source: 96/64-byte MIRROR echoes must reject overflow."""

from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tests/lab/dnsocklife.c"


def check_one(compiler: str, cap: int, receiver: str) -> None:
    fixture = r'''#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>
#define main packaged_socklife_main
#include "SOURCE_FILE"
#undef main
#define TEST_CAP CAPACITY
int main(void) {
    int fds[2];
    unsigned char tx[TEST_CAP], rx[TEST_CAP], response[TEST_CAP + 1U];
    ssize_t got;
    int good, false_green;
    if (socketpair(AF_UNIX, SOCK_SEQPACKET, 0, fds)) return 2;
    tx[0] = 0U;
    for (size_t i = 1U; i < TEST_CAP; i++) tx[i] = (unsigned char)(i * 17U);
    response[0] = 1U;
    memcpy(response + 1U, tx + 1U, TEST_CAP - 1U);
    response[TEST_CAP] = 0xb7;
    if (send(fds[1], response, TEST_CAP, MSG_EOR) != (ssize_t)TEST_CAP) return 3;
    got = RECEIVER(fds[0], rx, sizeof(rx), 0);
    good = (got == (ssize_t)TEST_CAP && rx[0] == 1U &&
            !memcmp(rx + 1U, tx + 1U, TEST_CAP - 1U));
    if (send(fds[1], response, TEST_CAP + 1U, MSG_EOR) !=
        (ssize_t)(TEST_CAP + 1U)) return 3;
    got = RECEIVER(fds[0], rx, sizeof(rx), 0);
    false_green = (got == (ssize_t)TEST_CAP && rx[0] == 1U &&
                   !memcmp(rx + 1U, tx + 1U, TEST_CAP - 1U));
    close(fds[0]);
    close(fds[1]);
    if (!good || false_green) {
        fprintf(stderr, "dnsocklife: cap=%u good=%d false_green=%d\n",
                (unsigned)TEST_CAP, good, false_green);
        return 1;
    }
    return 0;
}
''';
    fixture = (fixture.replace("SOURCE_FILE", str(SOURCE))
                      .replace("CAPACITY", str(cap))
                      .replace("RECEIVER", receiver))
    with tempfile.TemporaryDirectory(prefix="dniv-socklife-") as tmp:
        path = Path(tmp)
        (path / "fixture.c").write_text(fixture, encoding="utf-8")
        subprocess.run(
            [compiler, "-std=c11", "-O1", "-Wall", "-Wextra", "-Werror",
             "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
             "-I", str(ROOT / "include/uapi"), str(path / "fixture.c"),
             "-o", str(path / "fixture")],
            check=True, capture_output=True, text=True,
        )
        result = subprocess.run([str(path / "fixture")], capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(f"dnsocklife {cap} {compiler}: {result.stdout} {result.stderr}")


def main() -> None:
    data = SOURCE.read_text(encoding="utf-8")
    mirror = re.search(
        r"static int mirror_once\(.*?got = (recv|dniv_recv_record)\(fd, rx, sizeof\(rx\), 0\);",
        data, re.DOTALL,
    )
    nonblock = re.search(
        r"static int nonblocking_lifecycle\(.*?if \((recv|dniv_recv_record)\(fd, rx, sizeof\(rx\), 0\) !=",
        data, re.DOTALL,
    )
    if not mirror or not nonblock:
        raise AssertionError("dnsocklife MIRROR receive paths changed")
    for compiler in ("cc", "clang"):
        if compiler == "clang" and shutil.which(compiler) is None:
            continue
        for cap, receiver in ((96, mirror.group(1)), (64, nonblock.group(1))):
            check_one(compiler, cap, receiver)
    print("socket lifecycle MIRROR 96/64 exact record lengths passed")


if __name__ == "__main__":
    main()
