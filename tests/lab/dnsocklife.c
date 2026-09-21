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
#include <fcntl.h>
#include <poll.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>

#include <linux/dn.h>

#define CHURN_CYCLES 16U

static int parse_node(const char *text, uint16_t *address)
{
    char *end;
    unsigned long area, node;

    errno = 0;
    area = strtoul(text, &end, 10);
    if (errno || end == text || *end != '.' || area < 1U || area > 63U)
        return -1;
    text = end + 1;
    errno = 0;
    node = strtoul(text, &end, 10);
    if (errno || end == text || *end || node < 1U || node > 1023U)
        return -1;
    *address = (uint16_t)((area << 10) | node);
    return 0;
}

static void fill_peer(struct sockaddr_dn *peer, uint16_t address)
{
    memset(peer, 0, sizeof(*peer));
    peer->sdn_family = AF_DECnet;
    peer->sdn_objnum = 25U;
    peer->sdn_nodeaddrl = (__le16)2U;
    peer->sdn_nodeaddr[0] = (unsigned char)(address & 0xffU);
    peer->sdn_nodeaddr[1] = (unsigned char)(address >> 8);
}

static int expect_errno_ssize(ssize_t rc, int wanted)
{
    return rc == -1 && errno == wanted ? 0 : -1;
}

static int expect_errno_int(int rc, int wanted)
{
    return rc == -1 && errno == wanted ? 0 : -1;
}

static int set_timeouts(int fd)
{
    struct timeval timeout = { .tv_sec = 20, .tv_usec = 0 };

    return setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)) ||
           setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout));
}

static int mirror_once(const struct sockaddr_dn *peer, unsigned int cycle)
{
    unsigned char tx[96], rx[96];
    size_t i;
    ssize_t got;
    int fd;

    fd = socket(AF_DECnet, SOCK_SEQPACKET, DNPROTO_NSP);
    if (fd < 0)
        return -1;
    if (set_timeouts(fd) || connect(fd, (const struct sockaddr *)peer, sizeof(*peer)))
        goto fail;

    tx[0] = 0U;
    for (i = 1U; i < sizeof(tx); i++)
        tx[i] = (unsigned char)((i * 17U + cycle) & 0xffU);
    if (send(fd, tx, sizeof(tx), MSG_EOR | MSG_NOSIGNAL) !=
        (ssize_t)sizeof(tx))
        goto fail;
    got = recv(fd, rx, sizeof(rx), 0);
    if (got != (ssize_t)sizeof(rx) || rx[0] != 1U ||
        memcmp(rx + 1U, tx + 1U, sizeof(tx) - 1U))
        goto fail;
    close(fd);
    return 0;

fail:
    close(fd);
    return -1;
}

static int local_negatives(void)
{
    struct sockaddr_dn local;
    unsigned char byte = 0;
    socklen_t peerlen = sizeof(local);
    int fd;

    errno = 0;
    fd = socket(AF_DECnet, SOCK_DGRAM, DNPROTO_NSP);
    if (fd >= 0 || errno != ESOCKTNOSUPPORT) {
        if (fd >= 0)
            close(fd);
        return -1;
    }

    errno = 0;
    fd = socket(AF_DECnet, SOCK_SEQPACKET, 255);
    if (fd >= 0 || errno != EPROTONOSUPPORT) {
        if (fd >= 0)
            close(fd);
        return -1;
    }

    fd = socket(AF_DECnet, SOCK_SEQPACKET, DNPROTO_NSP);
    if (fd < 0)
        return -1;
    errno = 0;
    if (expect_errno_ssize(send(fd, &byte, 1U, MSG_NOSIGNAL), ENOTCONN))
        goto fail;
    errno = 0;
    if (expect_errno_ssize(recv(fd, &byte, 1U, MSG_DONTWAIT), ENOTCONN))
        goto fail;
    errno = 0;
    if (expect_errno_int(getpeername(fd, (struct sockaddr *)&local, &peerlen),
                         ENOTCONN))
        goto fail;
    errno = 0;
    if (expect_errno_int(shutdown(fd, SHUT_RDWR), ENOTCONN))
        goto fail;
    errno = 0;
    if (expect_errno_int(listen(fd, 1), EINVAL))
        goto fail;
    close(fd);

    fd = socket(AF_DECnet, SOCK_SEQPACKET, DNPROTO_NSP);
    if (fd < 0)
        return -1;
    memset(&local, 0, sizeof(local));
    local.sdn_family = AF_DECnet;
    if (bind(fd, (struct sockaddr *)&local, sizeof(local)))
        goto fail;
    errno = 0;
    if (expect_errno_int(listen(fd, 1), EINVAL))
        goto fail;
    close(fd);
    return 0;

fail:
    close(fd);
    return -1;
}

static int syscall_negative_corpus(const struct sockaddr_dn *peer)
{
    struct sockaddr_dn addr;
    struct optdata_dn opt;
    struct accessdata_dn access;
    unsigned char byte = 0U;
    socklen_t optlen;
    int mode;
    int fd;

    fd = socket(AF_DECnet, SOCK_SEQPACKET, DNPROTO_NSP);
    if (fd < 0)
        return -1;

    addr = *peer;
    errno = 0;
    if (expect_errno_int(connect(fd, (const struct sockaddr *)&addr,
                                 sizeof(addr) - 1U), EINVAL))
        goto fail;

    memset(&addr, 0, sizeof(addr));
    addr.sdn_family = AF_UNSPEC;
    errno = 0;
    if (expect_errno_int(bind(fd, (const struct sockaddr *)&addr,
                              sizeof(addr)), EINVAL))
        goto fail;

    memset(&addr, 0, sizeof(addr));
    addr.sdn_family = AF_DECnet;
    addr.sdn_objnum = 7U;
    addr.sdn_objnamel = (__le16)1U;
    addr.sdn_objname[0] = 'X';
    errno = 0;
    if (expect_errno_int(bind(fd, (const struct sockaddr *)&addr,
                              sizeof(addr)), EINVAL))
        goto fail;

    memset(&addr, 0, sizeof(addr));
    addr.sdn_family = AF_DECnet;
    addr.sdn_flags = 1U;
    errno = 0;
    if (expect_errno_int(bind(fd, (const struct sockaddr *)&addr,
                              sizeof(addr)), EOPNOTSUPP))
        goto fail;

    memset(&addr, 0, sizeof(addr));
    addr.sdn_family = AF_DECnet;
    addr.sdn_nodeaddrl = (__le16)1U;
    errno = 0;
    if (expect_errno_int(bind(fd, (const struct sockaddr *)&addr,
                              sizeof(addr)), EINVAL))
        goto fail;

    memset(&addr, 0, sizeof(addr));
    addr.sdn_family = AF_DECnet;
    addr.sdn_objnum = 25U;
    errno = 0;
    if (expect_errno_int(connect(fd, (const struct sockaddr *)&addr,
                                 sizeof(addr)), EINVAL))
        goto fail;

    memset(&opt, 0, sizeof(opt));
    errno = 0;
    if (expect_errno_int(setsockopt(fd, DNPROTO_NSP, DSO_CONDATA,
                                    &opt, sizeof(opt) - 1U), EINVAL))
        goto fail;

    mode = 99;
    errno = 0;
    if (expect_errno_int(setsockopt(fd, DNPROTO_NSP, DSO_ACCEPTMODE,
                                    &mode, sizeof(mode)), EINVAL))
        goto fail;

    memset(&access, 0, sizeof(access));
    access.acc_userl = DN_MAXACCL + 1U;
    errno = 0;
    if (expect_errno_int(setsockopt(fd, DNPROTO_NSP, DSO_CONACCESS,
                                    &access, sizeof(access)), EINVAL))
        goto fail;

    errno = 0;
    if (expect_errno_int(setsockopt(fd, DNPROTO_NSP, 0x7fff,
                                    &mode, sizeof(mode)), ENOPROTOOPT))
        goto fail;

    optlen = sizeof(opt);
    errno = 0;
    if (expect_errno_int(getsockopt(fd, DNPROTO_NSP, 0x7fff,
                                    &opt, &optlen), ENOPROTOOPT))
        goto fail;

    errno = 0;
    if (expect_errno_ssize(send(fd, &byte, 1U, MSG_PEEK), EOPNOTSUPP))
        goto fail;

    close(fd);
    return 0;

fail:
    close(fd);
    return -1;
}

static int nonblocking_lifecycle(const struct sockaddr_dn *peer)
{
    struct pollfd pfd;
    unsigned char tx[64], rx[64];
    int flags;
    int rc;
    int fd;

    fd = socket(AF_DECnet, SOCK_SEQPACKET, DNPROTO_NSP);
    if (fd < 0 || set_timeouts(fd))
        goto fail;
    flags = fcntl(fd, F_GETFL, 0);
    if (flags < 0 || fcntl(fd, F_SETFL, flags | O_NONBLOCK))
        goto fail;

    errno = 0;
    rc = connect(fd, (const struct sockaddr *)peer, sizeof(*peer));
    if (rc && errno != EINPROGRESS)
        goto fail;
    if (rc) {
        memset(&pfd, 0, sizeof(pfd));
        pfd.fd = fd;
        pfd.events = POLLOUT | POLLERR | POLLHUP;
        rc = poll(&pfd, 1, 20000);
        if (rc != 1 || !(pfd.revents & POLLOUT) ||
            (pfd.revents & (POLLERR | POLLHUP)))
            goto fail;
        errno = 0;
        if (connect(fd, (const struct sockaddr *)peer, sizeof(*peer)))
            goto fail;
    }

    errno = 0;
    if (!expect_errno_int(connect(fd, (const struct sockaddr *)peer,
                                  sizeof(*peer)), EISCONN))
        ;
    else
        goto fail;

    if (fcntl(fd, F_SETFL, flags))
        goto fail;
    memset(tx, 0x3c, sizeof(tx));
    tx[0] = 0U;
    if (send(fd, tx, sizeof(tx), MSG_EOR | MSG_NOSIGNAL) !=
        (ssize_t)sizeof(tx))
        goto fail;
    if (recv(fd, rx, sizeof(rx), 0) != (ssize_t)sizeof(rx) ||
        rx[0] != 1U || memcmp(rx + 1U, tx + 1U, sizeof(tx) - 1U))
        goto fail;

    errno = 0;
    if (expect_errno_int(shutdown(fd, SHUT_RD), EOPNOTSUPP))
        goto fail;
    errno = 0;
    if (expect_errno_int(shutdown(fd, SHUT_WR), EOPNOTSUPP))
        goto fail;
    if (shutdown(fd, SHUT_RDWR))
        goto fail;
    errno = 0;
    if (expect_errno_ssize(send(fd, tx, sizeof(tx), MSG_NOSIGNAL), ENOTCONN))
        goto fail;
    errno = 0;
    if (expect_errno_ssize(recv(fd, rx, sizeof(rx), MSG_DONTWAIT), ENOTCONN))
        goto fail;
    close(fd);
    return 0;

fail:
    if (fd >= 0)
        close(fd);
    return -1;
}

static int stream_negatives(const struct sockaddr_dn *peer)
{
    unsigned char byte = 0U;
    int fd;

    fd = socket(AF_DECnet, SOCK_STREAM, DNPROTO_NSP);
    if (fd < 0 || set_timeouts(fd) ||
        connect(fd, (const struct sockaddr *)peer, sizeof(*peer)))
        goto fail;
    errno = 0;
    if (expect_errno_ssize(send(fd, &byte, 1U, MSG_EOR | MSG_NOSIGNAL), EINVAL))
        goto fail;
    errno = 0;
    if (expect_errno_ssize(recv(fd, &byte, 1U, MSG_TRUNC | MSG_DONTWAIT),
                           EOPNOTSUPP))
        goto fail;
    close(fd);
    return 0;

fail:
    if (fd >= 0)
        close(fd);
    return -1;
}

int main(int argc, char **argv)
{
    struct sockaddr_dn peer;
    uint16_t address;
    unsigned int i;

    if (argc != 2 || parse_node(argv[1], &address)) {
        fprintf(stderr, "usage: %s AREA.NODE\n", argv[0]);
        return 2;
    }
    fill_peer(&peer, address);

    if (local_negatives()) {
        fprintf(stderr, "dnsocklife: local negative failed errno=%d\n", errno);
        return 1;
    }
    if (syscall_negative_corpus(&peer)) {
        fprintf(stderr, "dnsocklife: syscall negative corpus failed errno=%d\n",
                errno);
        return 1;
    }
    if (nonblocking_lifecycle(&peer)) {
        fprintf(stderr, "dnsocklife: nonblocking lifecycle failed errno=%d\n",
                errno);
        return 1;
    }
    if (stream_negatives(&peer)) {
        fprintf(stderr, "dnsocklife: stream negative failed errno=%d\n", errno);
        return 1;
    }
    for (i = 0U; i < CHURN_CYCLES; i++) {
        if (mirror_once(&peer, i)) {
            fprintf(stderr, "dnsocklife: churn failed cycle=%u errno=%d\n",
                    i, errno);
            return 1;
        }
    }
    printf("dnsocklife: pass peer=%s cycles=%u nonblock=1 shutdown=1 syscall_negatives=1\n",
           argv[1], CHURN_CYCLES);
    return 0;
}
