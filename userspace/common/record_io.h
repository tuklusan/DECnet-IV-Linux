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

#ifndef DNIV_RECORD_IO_H
#define DNIV_RECORD_IO_H

#include <errno.h>
#include <stddef.h>
#include <sys/socket.h>
#include <sys/types.h>

static inline int dniv_send_record(int fd, const void *buf, size_t len, int flags)
{
    const unsigned char *p = buf;
    size_t off = 0U;

    if (!len) {
        ssize_t sent;

        do {
            sent = send(fd, buf, 0U, flags | MSG_EOR | MSG_NOSIGNAL);
        } while (sent < 0 && errno == EINTR);
        if (sent < 0)
            return -1;
        if (sent != 0) {
            errno = EIO;
            return -1;
        }
        return 0;
    }

    while (off < len) {
        ssize_t sent = send(fd, p + off, len - off,
                            flags | MSG_EOR | MSG_NOSIGNAL);

        if (sent < 0) {
            if (errno == EINTR)
                continue;
            return -1;
        }
        if (!sent) {
            errno = EIO;
            return -1;
        }
        off += (size_t)sent;
    }
    return 0;
}

static inline ssize_t dniv_recv_record(int fd, void *buf, size_t cap, int flags)
{
    ssize_t got;

    got = recv(fd, buf, cap, flags | MSG_TRUNC);
    if (got < 0)
        return got;
    if ((size_t)got > cap) {
        errno = EMSGSIZE;
        return -1;
    }
    return got;
}

#endif
