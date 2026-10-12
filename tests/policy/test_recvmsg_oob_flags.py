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

"""Compile the actual kernel recvmsg result-flag path with pending OOB data."""

import os
import shlex
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOCKET_SOURCE = ROOT / "kernel/decnet/decnet_iv_socket.c"
START_MARKER = "    if (flags & MSG_OOB) {\n        msg->msg_flags |= MSG_OOB;"
END_MARKER = "    if (msg->msg_name)"


STUB_PREFIX = r"""
#define _GNU_SOURCE
#include <stdbool.h>
#include <stdio.h>
#include <sys/socket.h>

struct dniv_sock { unsigned short local_link; };

static int dniv_nsp_rx_ready(unsigned short local_link,
                             bool *normal, bool *interrupt)
{
    (void)local_link;
    *normal = true;
    *interrupt = true; /* An OOB record is pending, not being consumed. */
    return 0;
}

static int classify(int flags)
{
    struct dniv_sock sock = { .local_link = 1 };
    struct dniv_sock *dsk = &sock;
    struct msghdr message = {0};
    struct msghdr *msg = &message;

    (void)dsk;
    (void)dniv_nsp_rx_ready;
"""

STUB_SUFFIX = r"""
    return msg->msg_flags;
}

int main(void)
{
    int normal = classify(0);
    int urgent = classify(MSG_OOB);

    if (!(normal & MSG_EOR) || (normal & MSG_OOB) ||
        !(urgent & MSG_OOB) || (urgent & MSG_EOR)) {
        fprintf(stderr, "unexpected recvmsg flags: normal=%x urgent=%x\n",
                normal, urgent);
        return 1;
    }
    puts("recvmsg OOB flags match the received record, not pending data");
    return 0;
}
"""


def main() -> int:
    source = SOCKET_SOURCE.read_text(encoding="utf-8")
    region = source[source.index("static int dniv_sock_recvmsg(") :]
    if region.count(START_MARKER) != 1:
        raise SystemExit("cannot isolate one exact kernel recvmsg flag path")
    begin = region.index(START_MARKER)
    end = region.index(END_MARKER, begin)
    fragment = region[begin:end]
    if "msg->msg_flags |= MSG_EOR" not in fragment:
        raise SystemExit("kernel recvmsg no longer reports message boundaries")

    with tempfile.TemporaryDirectory(prefix="dniv-recv-oob-flags-") as directory:
        work = Path(directory)
        c_file = work / "recvmsg_flags.c"
        executable = work / "recvmsg_flags"
        c_file.write_text(STUB_PREFIX + fragment + STUB_SUFFIX, encoding="utf-8")
        subprocess.run(
            shlex.split(os.environ.get("CC", "cc"))
            + ["-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
               str(c_file), "-o", str(executable)],
            check=True,
            timeout=60,
        )
        result = subprocess.run(
            [str(executable)], capture_output=True, text=True, timeout=10
        )
        if result.returncode:
            raise SystemExit(
                f"kernel recvmsg MSG_OOB regression: rc={result.returncode}, "
                f"stdout={result.stdout!r}, stderr={result.stderr!r}"
            )
    print("kernel recvmsg OOB flag regression passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
