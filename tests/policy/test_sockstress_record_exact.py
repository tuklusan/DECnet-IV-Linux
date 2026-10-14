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

"""The actual socket-stress source rejects oversized 128/4096-byte MIRROR echoes."""

from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tests/lab/dnsockstress.c"


def check(compiler: str, cap: int, receiver: str) -> None:
    fixture = r'''#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>
#define main packaged_sockstress_main
#include "SOURCE_FILE"
#undef main
#define CAP BUFFER_CAP
int main(void) {
    int fds[2];
    unsigned char tx[CAP], rx[CAP], response[CAP + 1U];
    ssize_t got;
    int good, false_green;
    if (socketpair(AF_UNIX, SOCK_SEQPACKET, 0, fds)) return 2;
    tx[0] = 0U;
    for (size_t i = 1; i < CAP; ++i) tx[i] = (unsigned char)(i * 31U);
    response[0] = 1U;
    memcpy(response + 1U, tx + 1U, CAP - 1U);
    response[CAP] = 0xbe;
    if (send(fds[1], response, CAP, MSG_EOR) != (ssize_t)CAP) return 3;
    got = RECEIVER(fds[0], rx, sizeof(rx), 0);
    good = (got == (ssize_t)CAP && rx[0] == 1U &&
            !memcmp(rx + 1U, tx + 1U, CAP - 1U));
    if (send(fds[1], response, CAP + 1U, MSG_EOR) != (ssize_t)(CAP + 1U)) return 3;
    got = RECEIVER(fds[0], rx, sizeof(rx), 0);
    false_green = (got == (ssize_t)CAP && rx[0] == 1U &&
                   !memcmp(rx + 1U, tx + 1U, CAP - 1U));
    close(fds[0]); close(fds[1]);
    if (!good || false_green) {
        fprintf(stderr, "sockstress cap=%zu good=%d oversized=%d\n", (size_t)CAP,
                good, false_green);
        return 1;
    }
    return 0;
}
''';
    fixture = (fixture.replace("SOURCE_FILE", str(SOURCE))
                      .replace("BUFFER_CAP", str(cap))
                      .replace("RECEIVER", receiver))
    with tempfile.TemporaryDirectory(prefix="dniv-sockstress-") as tmp:
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
            raise AssertionError(f"sockstress {cap} {compiler}: {result.stdout} {result.stderr}")


def main() -> None:
    data = SOURCE.read_text(encoding="utf-8")
    direct = re.findall(r"got = (recv|dniv_recv_record)\(fd, rx, sizeof\(rx\), 0\);", data)
    indexed = re.findall(r"got = (recv|dniv_recv_record)\(fds\[i\], rx, sizeof\(rx\), 0\);", data)
    if len(direct) != 1 or len(indexed) != 2 or not all(
        method == direct[0] for method in indexed
    ):
        raise AssertionError("sockstress three record receive paths changed")
    for compiler in ("cc", "clang"):
        if compiler == "clang" and shutil.which(compiler) is None:
            continue
        for cap in (128, 4096):
            check(compiler, cap, direct[0])
    print("socket stress exact 128/4096-byte replies passed")


if __name__ == "__main__":
    main()
