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

"""Compile the shipped dnping source and verify -w sets send and receive deadlines."""

import os
import shlex
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROGRAM = ROOT / "userspace/dnping/dnping.c"
STUB = r"""
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>

static int desired_timeout = 0;
static int held_peer = -1;

int dnet_conn(char *node, char *obj, int type, unsigned char *opt_out,
              int opt_outl, unsigned char *opt_in, int *opt_inl)
{
    int pair[2];
    (void)node;(void)obj;(void)type;(void)opt_out;
    (void)opt_outl;(void)opt_in;(void)opt_inl;
    if (socketpair(AF_UNIX, SOCK_SEQPACKET, 0, pair)) return -1;
    held_peer = pair[1];
    return pair[0];
}

ssize_t recv(int fd, void *buffer, size_t cap, int flags)
{
    struct timeval receive = { 0, 0 }, send_time = { 0, 0 };
    socklen_t n = sizeof(receive);
    unsigned char *bytes = buffer;
    size_t i;
    (void)flags;
    if (getsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &receive, &n) ||
        n != sizeof(receive) ||
        getsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &send_time, &n) ||
        n != sizeof(send_time)) _exit(61);
    if (receive.tv_sec != desired_timeout || receive.tv_usec != 0 ||
        send_time.tv_sec != desired_timeout || send_time.tv_usec != 0)
        _exit(62);
    if (cap < 40) _exit(63);
    bytes[0] = 1;
    bytes[1] = 0;
    for (i = 2; i < 40; i++) bytes[i] = 0x85;
    return 40;
}

/* Set the requested timeout from argv without depending on a DECnet module.
 * This is a local AF_UNIX socket and no remote host is contacted. */
__attribute__((constructor)) static void expected(void)
{
    const char *value = getenv("DNIV_EXPECT_TIMEOUT");
    if (!value) _exit(64);
    desired_timeout = atoi(value);
}
"""


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="dniv-dnping-timeout-") as directory:
        work = Path(directory)
        source = work / "socket_stub.c"
        executable = work / "dnping"
        source.write_text(STUB, encoding="utf-8")
        subprocess.run(shlex.split(os.environ.get("CC", "cc")) + [
            "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
            "-I" + str(ROOT / "userspace/libdnet/include"),
            "-I" + str(ROOT / "include/uapi"),
            str(PROGRAM), str(source), "-o", str(executable)
        ], check=True, timeout=60)
        for seconds in (1, 2):
            env = dict(os.environ, DNIV_EXPECT_TIMEOUT=str(seconds))
            result = subprocess.run([
                str(executable), "-c", "1", "-w", str(seconds), "NODE"
            ], env=env, capture_output=True, text=True, timeout=8)
            if result.returncode or "Received 1 packets" not in result.stdout:
                raise SystemExit(
                    f"dnping -w {seconds} failed, rc={result.returncode}, "
                    f"stdout={result.stdout!r}, stderr={result.stderr!r}"
                )
    print("dnping -w applies to both send and receive timeouts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
