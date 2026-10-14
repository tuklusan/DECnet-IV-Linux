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

"""Real dn-fairness source must reject an exact-prefix oversized MIRROR reply."""

from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
FAIR = ROOT / "tests/lab/dnfair.c"


def compile_and_probe(compiler: str) -> None:
    source_text = FAIR.read_text()
    # Verify BOTH the survivor and the stalled logical-link receive path.
    names = re.findall(
        r"check_reply\(tx, rx, (recv|dniv_recv_record)\("
        r"(?:survivor|stalled), rx, sizeof\(rx\), 0\)\)", source_text
    )
    if len(names) != 2 or names[0] != names[1]:
        raise AssertionError("dnfair survivor/stalled receive coverage changed")
    fixture = r'''#include <sys/socket.h>
#include <unistd.h>
#include <stdio.h>
#include <string.h>
#define main packaged_dnfair_main
#include "SOURCE_FILE"
#undef main
int main(void) {
    int fds[2];
    unsigned char tx[PAYLOAD], rx[PAYLOAD], response[PAYLOAD + 1U];
    int good, malformed;
    if (socketpair(AF_UNIX, SOCK_SEQPACKET, 0, fds)) return 2;
    make_payload(tx, 999U);
    response[0] = 1U;
    memcpy(response + 1U, tx + 1U, PAYLOAD - 1U);
    response[PAYLOAD] = 0xae;
    if (send(fds[1], response, PAYLOAD, MSG_EOR) != (ssize_t)PAYLOAD)
        return 3;
    good = check_reply(tx, rx, RECEIVER(fds[0], rx, sizeof(rx), 0));
    if (send(fds[1], response, PAYLOAD + 1U, MSG_EOR) !=
        (ssize_t)(PAYLOAD + 1U)) return 3;
    malformed = check_reply(tx, rx,
                             RECEIVER(fds[0], rx, sizeof(rx), 0));
    close(fds[0]);
    close(fds[1]);
    if (good != 0 || malformed == 0) {
        fprintf(stderr, "dnfair MIRROR: good=%d overlong=%d\n",
                good, malformed);
        return 1;
    }
    return 0;
}
'''
    fixture = fixture.replace("SOURCE_FILE", str(FAIR)).replace("RECEIVER", names[0])
    with tempfile.TemporaryDirectory(prefix="dniv-fairness-") as tmp:
        path = Path(tmp)
        (path / "fixture.c").write_text(fixture)
        cmd = [compiler, "-std=c11", "-O1", "-Wall", "-Wextra", "-Werror",
               "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
               "-I", str(ROOT / "include/uapi"), str(path / "fixture.c"),
               "-o", str(path / "fixture")]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        result = subprocess.run([str(path / "fixture")],
                                capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(f"dnfair {compiler} malformed-record proof: "
                                 f"{result.stdout} {result.stderr}")


def main() -> None:
    for compiler in ("cc", "clang"):
        if compiler == "clang" and shutil.which("clang") is None:
            continue
        compile_and_probe(compiler)
    print("dnfair exact MIRROR record-length proof passed")


if __name__ == "__main__":
    main()
