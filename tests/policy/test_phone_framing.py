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

"""Compile the actual PHONE server and reject hidden control records."""

import os
import shlex
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

HARNESS = r'''
#define main original_dnphoned_main
#include "dnphoned.c"
#undef main

static int probe(int mode)
{
    static const unsigned char connect_good[] = {
        PHONE_CONNECT, 'N', 0, '1', '.', '2', '3', ':', ':',
        'A', 'L', 'I', 'C', 'E', 0
    };
    static const unsigned char connect_hidden[] = {
        PHONE_CONNECT, 'N', 0, '1', '.', '2', '3', ':', ':',
        'A', 'L', 'I', 'C', 'E', 0, 'H', 'I', 'D', 'D', 'E', 'N'
    };
    static const unsigned char dial_good[] = { PHONE_DIAL, 'N', 0, 1 };
    static const unsigned char dial_hidden[] = {
        PHONE_DIAL, 'N', 0, 1, 'H', 'I', 'D', 'D', 'E', 'N'
    };
    static const unsigned char goodbye_good[] = { PHONE_GOODBYE, 'N', 0 };
    static const unsigned char goodbye_hidden[] = {
        PHONE_GOODBYE, 'N', 0, 'H', 'I', 'D', 'D', 'E', 'N'
    };
    struct timeval timeout = { .tv_sec = 5, .tv_usec = 0 };
    int fds[2], status, failed = 0;
    unsigned char reply = 0;
    ssize_t got;
    pid_t child;

    if (socketpair(AF_UNIX, SOCK_SEQPACKET, 0, fds))
        return 1;
    if (setsockopt(fds[0], SOL_SOCKET, SO_RCVTIMEO,
                   &timeout, sizeof(timeout)))
        return 1;
    child = fork();
    if (child < 0)
        return 1;
    if (!child) {
        int rc;
        close(fds[0]);
        rc = serve(fds[1], "ALICE");
        close(fds[1]);
        _exit(rc ? 1 : 0);
    }
    close(fds[1]);
    failed = dniv_send_record(fds[0], mode == 1 ? connect_hidden :
                              connect_good, mode == 1 ?
                              sizeof(connect_hidden) : sizeof(connect_good), 0);
    got = failed ? -1 : dniv_recv_record(fds[0], &reply, 1, 0);
    if (mode == 1) {
        failed = (got == 1 && reply == PHONE_REPLYOK);
        goto done;
    }
    if (got != 1 || reply != PHONE_REPLYOK) {
        failed = 1;
        goto done;
    }
    failed = dniv_send_record(fds[0], mode == 2 ? dial_hidden : dial_good,
                              mode == 2 ? sizeof(dial_hidden) :
                              sizeof(dial_good), 0);
    got = failed ? -1 : dniv_recv_record(fds[0], &reply, 1, 0);
    if (mode == 2) {
        failed = (got == 1 && reply == PHONE_REPLYOK);
        goto done;
    }
    if (got != 1 || reply != PHONE_REPLYOK) {
        failed = 1;
        goto done;
    }
    failed = dniv_send_record(fds[0], mode == 3 ? goodbye_hidden :
                              goodbye_good, mode == 3 ?
                              sizeof(goodbye_hidden) : sizeof(goodbye_good), 0);

done:
    close(fds[0]);
    if (waitpid(child, &status, 0) != child || !WIFEXITED(status) ||
        WEXITSTATUS(status) != (mode ? 1 : 0))
        failed = 1;
    if (failed)
        fprintf(stderr, "PHONE framing mode %d failed\n", mode);
    return failed;
}

int main(void)
{
    int i, failed = 0;

    for (i = 0; i < 4; i++)
        failed |= probe(i);
    return failed ? 1 : 0;
}
'''


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="dniv-phone-framing-") as directory:
        source = Path(directory) / "check.c"
        binary = Path(directory) / "check"
        source.write_text(HARNESS, encoding="utf-8")
        subprocess.run(shlex.split(os.environ.get("CC", "cc")) + [
            "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
            "-I" + str(ROOT / "userspace/dnphone"),
            "-I" + str(ROOT / "include/uapi"),
            str(source), "-o", str(binary),
        ], check=True, timeout=60)
        subprocess.run([str(binary)], check=True, timeout=15)
    print("dnphoned rejects hidden control-record suffixes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
