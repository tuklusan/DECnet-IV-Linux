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

    /* AF_UNIX SOCK_SEQPACKET ends a record on every send(2), even when
     * MSG_EOR is absent. The native DECnet split-send scheme below would
     * make two records from one local test frame. Send one atomic record. */
    {
        struct sockaddr_storage local = { 0 };
        socklen_t local_len = sizeof(local);
        int type = 0;
        socklen_t optlen = sizeof(type);

        if (!getsockname(fd, (struct sockaddr *)&local, &local_len) &&
            local_len >= sizeof(local.ss_family) &&
            local.ss_family == AF_UNIX) {
            if (!getsockopt(fd, SOL_SOCKET, SO_TYPE, &type, &optlen) &&
                optlen == sizeof(type) && type == SOCK_SEQPACKET) {
                ssize_t sent;

                do {
                    sent = send(fd, buf, len,
                                flags | MSG_EOR | MSG_NOSIGNAL);
                } while (sent < 0 && errno == EINTR);
                if (sent == (ssize_t)len)
                    return 0;
                if (sent >= 0)
                    errno = EIO;
                return -1;
            }
        }
    }

    while (off < len) {
        /* A partial send must not end the DECnet record early. Reserve the
         * final byte for the one send that actually carries MSG_EOR. */
        size_t remaining = len - off;
        size_t requested = remaining == 1U ? 1U : remaining - 1U;
        int send_flags = (flags & ~MSG_EOR) | MSG_NOSIGNAL;
        ssize_t sent;

        if (remaining == 1U)
            send_flags |= MSG_EOR;
        sent = send(fd, p + off, requested, send_flags);

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
