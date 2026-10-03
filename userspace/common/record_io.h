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
