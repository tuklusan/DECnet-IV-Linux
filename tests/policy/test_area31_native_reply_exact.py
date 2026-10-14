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

"""Compile the real Area-31 MIRROR probe; reject an oversized perfect prefix."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tests/lab/area31-native.c"


def check(compiler: str) -> None:
    # Keep the actual production source and MIRROR loop; mock only the remote
    # connector. A local UNIX SEQPACKET reply with one hidden extra byte must
    # never qualify as a successful remote MIRROR proof.
    source = r'''
#include <sys/socket.h>
#include <string.h>
#include <unistd.h>
#include <stdint.h>
#include <stdio.h>
#include <errno.h>
#include <sys/wait.h>
static int fixture_variant;
static pid_t children[2];
static int child_count;
int fixture_conn(char *, char *, int, unsigned char *, int, unsigned char *, int *);
int fixture_recv(int, void *, int, unsigned int);
#define dnet_conn fixture_conn
#define dnet_recv fixture_recv
#define main packaged_area31_main
#include "SOURCE_FILE"
#undef main
#undef dnet_conn
#undef dnet_recv
int fixture_conn(char *node, char *object, int type, unsigned char *out,
                 int outl, unsigned char *in, int *inl)
{
    int pair[2]; pid_t pid;
    (void)node; (void)object; (void)type; (void)out; (void)outl;
    (void)in; (void)inl;
    if (socketpair(AF_UNIX, SOCK_SEQPACKET, 0, pair))
        return -1;
    pid = fork();
    if (pid < 0)
        return -1;
    if (pid == 0) {
        unsigned char request[512], reply[513];
        ssize_t got;
        close(pair[0]);
        got = recv(pair[1], request, sizeof(request), 0);
        if (got < 1)
            _exit(2);
        reply[0] = 1;
        memcpy(reply + 1, request + 1, (size_t)got - 1U);
        reply[got] = 0xaa;
        if (send(pair[1], reply, (size_t)got +
                 (fixture_variant ? 1U : 0U), MSG_EOR) < 0)
            _exit(3);
        close(pair[1]);
        _exit(0);
    }
    children[child_count++] = pid;
    close(pair[1]);
    return pair[0];
}
int fixture_recv(int fd, void *buf, int len, unsigned int flags)
{
    return (int)recv(fd, buf, (size_t)len, flags & ~MSG_EOR);
}
static int check_nice(int oversize)
{
    int pair[2];
    int rc;
    const uint16_t target = (uint16_t)((31U << 10) | 123U);
    unsigned char frame[513];
    size_t used = oversize ? sizeof(frame) : 11U;

    memset(frame, 0, sizeof(frame));
    frame[0] = DNIV_NICE_RET_SUCCESS;
    frame[1] = 0xffU;
    frame[2] = 0xffU;
    frame[4] = (unsigned char)(target & 0xffU);
    frame[5] = (unsigned char)(target >> 8);
    frame[6] = 0x84U;
    memcpy(frame + 7, "DN70", 4U);
    if (socketpair(AF_UNIX, SOCK_SEQPACKET, 0, pair))
        return 1;
    if (send(pair[1], frame, used, MSG_EOR) != (ssize_t)used)
        return 1;
    rc = nice_read_executor_reply(pair[0], target, DNIV_NICE_INFO_SUMMARY);
    close(pair[0]);
    close(pair[1]);
    return oversize ? (rc == 0) : (rc != 0);
}

static int check_nice_control(int which, int expect_success)
{
    int pair[2], rc;
    const uint16_t target = (uint16_t)((31U << 10) | 123U);
    unsigned char item[11] = {0};
    unsigned char accepted[4] = {2U, 0U, 0U, 0U};
    unsigned char done[4] = {0x80U, 0U, 0U, 0U};
    item[0] = DNIV_NICE_RET_SUCCESS;
    item[1] = item[2] = 0xffU;
    item[4] = (unsigned char)(target & 0xffU);
    item[5] = (unsigned char)(target >> 8);
    item[6] = 0x84U;
    memcpy(item + 7, "DN70", 4U);
    if (socketpair(AF_UNIX, SOCK_SEQPACKET, 0, pair)) return 1;
    if (which == 0) { // compact valid control
        if (send(pair[1], accepted, 1U, MSG_EOR) != 1) return 1;
    } else if (which == 1) { // malformed two-byte ACCEPTED
        if (send(pair[1], accepted, 2U, MSG_EOR) != 2) return 1;
    } else if (which == 2) { // accepted header with trailing bytes
        accepted[3] = 3U;
        if (send(pair[1], accepted, 4U, MSG_EOR) != 4) return 1;
    } else { // extended valid control
        if (send(pair[1], accepted, 4U, MSG_EOR) != 4) return 1;
    }
    if (send(pair[1], item, sizeof(item), MSG_EOR) != (ssize_t)sizeof(item)) return 1;
    if (which == 4) { // malformed 2-byte terminator
        if (send(pair[1], done, 2U, MSG_EOR) != 2) return 1;
    } else if (which == 5) { // malformed counted terminator
        done[3] = 1U;
        if (send(pair[1], done, 4U, MSG_EOR) != 4) return 1;
    } else {
        if (send(pair[1], done, 1U, MSG_EOR) != 1) return 1;
    }
    rc = nice_read_executor_reply(pair[0], target, DNIV_NICE_INFO_SUMMARY);
    close(pair[0]); close(pair[1]);
    return expect_success ? (rc != 0) : (rc == 0);
}

int main(void)
{
    int good, malformed;
    fixture_variant = 0;
    good = mirror_query("31.123", 0);
    fixture_variant = 1;
    malformed = mirror_query("31.123", 0);
    for (int i = 0; i < child_count; i++) {
        int status;
        if (waitpid(children[i], &status, 0) < 0 || !WIFEXITED(status) ||
            WEXITSTATUS(status) != 0)
            return 2;
    }
    if (good != 0 || malformed == 0) {
        fprintf(stderr, "area31-MIRROR exact record: good=%d oversize=%d\n",
                good, malformed);
        return 1;
    }
    if (check_nice_control(0, 1) || check_nice_control(3, 1) ||
        check_nice_control(1, 0) || check_nice_control(2, 0) ||
        check_nice_control(4, 0) || check_nice_control(5, 0)) {
        fprintf(stderr, "area31-NICE invalid accepted/done control passed\n");
        return 5;
    }
    if (check_nice(0) || check_nice(1)) {
        fprintf(stderr, "area31-NICE exact record: overlong reply falsely accepted\n");
        return 4;
    }
    return 0;
}
'''
    source = source.replace("SOURCE_FILE", str(SOURCE))
    with tempfile.TemporaryDirectory(prefix="dniv-area31-mirror-") as td:
        path = Path(td)
        (path / "test.c").write_text(source)
        cmd = [compiler, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
               "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
               "-I", str(ROOT / "userspace/libdnet/include"),
               "-I", str(ROOT / "include/uapi"), "-I", str(ROOT / "include"),
               str(path / "test.c"), "-o", str(path / "test")]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        result = subprocess.run([str(path / "test")], capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(f"{compiler} false-green MIRROR acceptance: "
                               f"{result.stdout}{result.stderr}")


def main() -> None:
    for compiler in ("cc", "clang"):
        if compiler != "cc" and shutil.which(compiler) is None:
            continue
        check(compiler)
    print("Area-31 native MIRROR exact reply-length regression passed")


if __name__ == "__main__":
    main()
