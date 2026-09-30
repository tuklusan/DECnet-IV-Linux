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

#include <errno.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/uio.h>

#include <netdnet/dnetdb.h>

int dnet_recv(int fd, void *buf, int len, unsigned int flags)
{
    unsigned int recv_flags = flags & ~MSG_EOR;

    if (len < 0 || (len && !buf)) {
        errno = EINVAL;
        return -1;
    }
    if (!(flags & MSG_EOR))
        return (int)recv(fd, buf, (size_t)len, recv_flags);

    {
        struct iovec iov;
        struct msghdr msg;
        size_t offset = 0U;

        memset(&msg, 0, sizeof(msg));
        iov.iov_base = buf;
        iov.iov_len = (size_t)len;
        msg.msg_iov = &iov;
        msg.msg_iovlen = 1U;

        while (offset < (size_t)len) {
            ssize_t got = recvmsg(fd, &msg, recv_flags);

            if (got <= 0)
                return offset ? (int)offset : (int)got;
            offset += (size_t)got;
            if (msg.msg_flags & MSG_EOR)
                return (int)offset;
            iov.iov_base = (unsigned char *)buf + offset;
            iov.iov_len = (size_t)len - offset;
            msg.msg_flags = 0;
        }
        return (int)offset;
    }
}

int dnet_eof(int fd)
{
    struct linkinfo_dn link;
    socklen_t len = sizeof(link);

    memset(&link, 0, sizeof(link));
    if (getsockopt(fd, DNPROTO_NSP, DSO_LINKINFO, &link, &len))
        return -1;
    if (len < sizeof(link) || link.idn_linkstate == LL_DISCONNECTING ||
        link.idn_linkstate == LL_INACTIVE) {
        errno = ENOTCONN;
        return -1;
    }
    return 0;
}

int getnodename(char *name, size_t len)
{
    struct dn_naddr *addr;
    struct nodeent *node;
    size_t need;

    if (!name || !len) {
        errno = EINVAL;
        return -1;
    }
    addr = getnodeadd();
    if (!addr)
        return -1;
    node = getnodebyaddr((const char *)addr->a_addr, DN_ADDL, AF_DECnet);
    if (!node)
        return -1;
    need = strlen(node->n_name);
    if (need >= len) {
        errno = ENAMETOOLONG;
        return -1;
    }
    memcpy(name, node->n_name, need + 1U);
    return 0;
}
