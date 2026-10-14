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

"""The actual MIRROR record-roundtrip source must detect a 4097-byte reply."""

from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tests/lab/dnmrr.c"


def probe(compiler: str) -> None:
    matches = re.findall(
        r"got = (recv|dniv_recv_record)\(fd, rx, sizeof\(rx\), 0\);",
        SOURCE.read_text(encoding="utf-8"),
    )
    if len(matches) != 1:
        raise AssertionError("dnmrr receive path unexpectedly changed")
    fixture = r'''#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>
#define main packaged_dnmrr_main
#include "SOURCE_FILE"
#undef main
int main(void) {
    int fds[2];
    unsigned char tx[4096], rx[4096], response[4097];
    ssize_t got;
    int good, false_green;
    if (socketpair(AF_UNIX, SOCK_SEQPACKET, 0, fds)) return 2;
    tx[0] = 0U;
    for (size_t i = 1; i < sizeof(tx); i++)
        tx[i] = (unsigned char)(i * 37U);
    response[0] = 1U;
    memcpy(response + 1U, tx + 1U, 4095U);
    response[4096] = 0xae;
    if (send(fds[1], response, 4096U, MSG_EOR) != 4096) return 3;
    got = RECEIVER(fds[0], rx, sizeof(rx), 0);
    good = (got == 4096 && rx[0] == 1U && !memcmp(rx + 1, tx + 1, 4095U));
    if (send(fds[1], response, 4097U, MSG_EOR) != 4097) return 3;
    got = RECEIVER(fds[0], rx, sizeof(rx), 0);
    false_green = (got == 4096 && rx[0] == 1U && !memcmp(rx + 1, tx + 1, 4095U));
    close(fds[0]);
    close(fds[1]);
    if (!good || false_green) {
        fprintf(stderr, "dnmrr: good=%d oversized_false_green=%d\n", good, false_green);
        return 1;
    }
    return 0;
}
''';
    fixture = fixture.replace("SOURCE_FILE", str(SOURCE)).replace("RECEIVER", matches[0]);
    with tempfile.TemporaryDirectory(prefix="dniv-mrr-") as tmp:
        directory = Path(tmp)
        (directory / "fixture.c").write_text(fixture, encoding="utf-8")
        subprocess.run(
            [compiler, "-std=c11", "-O1", "-Wall", "-Wextra", "-Werror",
             "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
             "-I", str(ROOT / "include/uapi"), str(directory / "fixture.c"),
             "-o", str(directory / "fixture")],
            check=True, capture_output=True, text=True,
        )
        result = subprocess.run([str(directory / "fixture")], capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(f"dnmrr {compiler} oversized reply: {result.stdout} {result.stderr}")


def main() -> None:
    for compiler in ("cc", "clang"):
        if compiler == "clang" and shutil.which(compiler) is None:
            continue
        probe(compiler)
    print("dnmrr exact MIRROR record length passed")


if __name__ == "__main__":
    main()
