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

"""Large sequence-wrap and post-signal MIRROR replies reject exact-prefix overflow."""

from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
CASES = (("dnseqwrap.c", "RECORD_SIZE", 1), ("dnsignal.c", "PAYLOAD", 2))


def check_source(compiler: str, name: str, capacity: str, count: int) -> None:
    source = ROOT / "tests" / "lab" / name
    text = source.read_text(encoding="utf-8")
    methods = re.findall(r"got = (recv|dniv_recv_record)\(fd, rx, sizeof\(rx\), 0\);", text)
    if len(methods) != count or (count == 2 and methods[0] != "recv"):
        raise AssertionError(f"{name}: signal/record receive structure unexpectedly changed")
    fixture = r'''#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>
#define main packaged_original_main
#include "SOURCE_FILE"
#undef main
#define TEST_CAP BUFFER_CAP
int main(void) {
    int fds[2];
    unsigned char tx[TEST_CAP], rx[TEST_CAP], response[TEST_CAP + 1U];
    ssize_t got;
    int good, false_green;
    if (socketpair(AF_UNIX, SOCK_SEQPACKET, 0, fds)) return 2;
    tx[0] = 0U;
    for (size_t i = 1U; i < TEST_CAP; ++i)
        tx[i] = (unsigned char)(i * 29U);
    response[0] = 1U;
    memcpy(response + 1U, tx + 1U, TEST_CAP - 1U);
    response[TEST_CAP] = 0xab;
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
        fprintf(stderr, "record: good=%d false_green=%d\n", good, false_green);
        return 1;
    }
    return 0;
}
''';
    fixture = (fixture.replace("SOURCE_FILE", str(source))
                      .replace("BUFFER_CAP", capacity)
                      .replace("RECEIVER", methods[-1]))
    with tempfile.TemporaryDirectory(prefix="dniv-record-overflow-") as directory:
        path = Path(directory)
        (path / "fixture.c").write_text(fixture, encoding="utf-8")
        subprocess.run(
            [compiler, "-std=c11", "-O1", "-Wall", "-Wextra", "-Werror",
             "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
             "-I", str(ROOT / "include/uapi"), str(path / "fixture.c"),
             "-o", str(path / "fixture")],
            check=True, text=True, capture_output=True,
        )
        result = subprocess.run([str(path / "fixture")], capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(f"{name} {compiler} oversized reply: {result.stdout} {result.stderr}")


def main() -> None:
    for compiler in ("cc", "clang"):
        if compiler == "clang" and shutil.which("clang") is None:
            continue
        for name, capacity, count in CASES:
            check_source(compiler, name, capacity, count)
    print("sequence-wrap and post-signal exact MIRROR record length passed")


if __name__ == "__main__":
    main()
