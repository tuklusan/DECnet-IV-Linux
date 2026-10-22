// ============================================================================
// Copyright (c) 2026 Supratim Sanyal of SANYALnet Labs.
// Proprietary rights reserved except as expressly licensed herein.
//
// DECnet-IV-Linux
// This file is governed by the SANYALnet Labs Non-Commercial License in the
// root LICENSE file. Non-Commercial use is permitted; Commercial Use and use
// for AI/ML model training are prohibited unless separately authorized.
//
// Attribution is required: "Based on original work by Supratim Sanyal of
// SANYALnet Labs." See LICENSE for full terms, warranty disclaimer, termination,
// patent, trademark, and governing-law provisions.
// ============================================================================

/* Source-derived fake transport proves a partial send cannot finish the
 * sequenced record before its LAST successful byte; the original helper did.
 * Compile: cc -std=c11 -Wall -Wextra -Werror -I. \
 *     tests/policy/test_record_io_partial_eor.c -o /tmp/dniv-record-test
 */
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/types.h>

static const unsigned char expected[] = "abcdefg";
static size_t delivered;
static unsigned int calls, terminal, zero_terminal;
static int violation;

static ssize_t fake_send(int fd, const void *buf, size_t len, int flags)
{
    size_t accepted;

    (void)fd;
    if (!len) {
        if (!(flags & MSG_EOR))
            violation = 1;
        zero_terminal++;
        return 0;
    }
    calls++;
    if (delivered + len > sizeof(expected) - 1U ||
        memcmp(buf, expected + delivered, len)) {
        violation = 1;
        errno = EIO;
        return -1;
    }
    accepted = calls == 1U && len > 2U ? 2U : len;
    if (flags & MSG_EOR) {
        terminal++;
        /* This syscall must send ONLY the final byte: a short send can
         * transmit a prefix but cannot retract an already emitted EOR. */
        if (len != 1U || delivered + accepted != sizeof(expected) - 1U)
            violation = 1;
    } else if (delivered + accepted == sizeof(expected) - 1U) {
        violation = 1;
    }
    delivered += accepted;
    return (ssize_t)accepted;
}

#define send fake_send
#include "userspace/common/record_io.h"
#undef send

static int check(int flags)
{
    int ret;

    delivered = calls = terminal = zero_terminal = 0U;
    violation = 0;
    ret = dniv_send_record(7, expected, sizeof(expected) - 1U, flags);
    if (ret || violation || delivered != sizeof(expected) - 1U ||
        terminal != 1U || calls < 2U) {
        fprintf(stderr,
                "early/missing EOR or lost bytes: ret=%d bad=%d bytes=%zu end=%u calls=%u\n",
                ret, violation, delivered, terminal, calls);
        return 1;
    }
    ret = dniv_send_record(7, expected, 0U, flags);
    if (ret || violation || zero_terminal != 1U) {
        fputs("empty record was not ended exactly once\n", stderr);
        return 1;
    }
    return 0;
}

int main(void)
{
    if (check(0) || check(MSG_EOR))
        return 1;
    puts("record send partial and zero-length MSG_EOR regression passed");
    return 0;
}
