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
#include <poll.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>

#include <linux/dn.h>

#define PRE_PAYLOAD "DNIV-DI-EXHAUST-PRE"
#define RECOVER_PAYLOAD "DNIV-DI-EXHAUST-RECOVER"
#define NODE_UNREACHABLE 39U

static uint16_t dniv_le16_to_cpu(__le16 value)
{
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
    return (uint16_t)value;
#else
    return __builtin_bswap16((uint16_t)value);
#endif
}

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

static int open_mirror(const struct sockaddr_dn *peer)
{
    struct timeval timeout = { .tv_sec = 40, .tv_usec = 0 };
    int fd = socket(AF_DECnet, SOCK_SEQPACKET, DNPROTO_NSP);

    if (fd < 0)
        return -1;
    if (setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)) ||
        setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout)) ||
        connect(fd, (const struct sockaddr *)peer, sizeof(*peer))) {
        close(fd);
        return -1;
    }
    return fd;
}

static int mirror_exchange(int fd, const char *payload)
{
    unsigned char tx[96];
    unsigned char rx[96];
    size_t len = strlen(payload) + 1U;
    ssize_t got;

    tx[0] = 0U;
    memcpy(tx + 1U, payload, len - 1U);
    if (send(fd, tx, len, MSG_EOR | MSG_NOSIGNAL) != (ssize_t)len)
        return -1;
    got = recv(fd, rx, sizeof(rx), 0);
    if (got != (ssize_t)len || rx[0] != 1U ||
        memcmp(rx + 1U, tx + 1U, len - 1U)) {
        errno = EPROTO;
        return -1;
    }
    return 0;
}

int main(int argc, char **argv)
{
    struct sockaddr_dn peer;
    struct optdata_dn discdata;
    struct pollfd pfd;
    socklen_t optlen;
    uint16_t address;
    int fd = -1;
    int recovery = -1;
    int pret;

    setvbuf(stdout, NULL, _IONBF, 0);
    if (argc != 4 || parse_node(argv[1], &address)) {
        fprintf(stderr, "usage: %s AREA.NODE SESSION SCENARIO\n", argv[0]);
        return 2;
    }
    fill_peer(&peer, address);

    fd = open_mirror(&peer);
    if (fd < 0 || mirror_exchange(fd, PRE_PAYLOAD))
        goto fail;

    printf("DNIV-INTEROP-DIEXHAUST-READY session=%s scenario=%s peer=%s\n",
           argv[2], argv[3], argv[1]);
    sleep(4);
    if (shutdown(fd, SHUT_RDWR))
        goto fail;
    printf("DNIV-INTEROP-DIEXHAUST-SENT session=%s scenario=%s peer=%s\n",
           argv[2], argv[3], argv[1]);

    /*
     * Five total control transmissions at a five-second response interval
     * reach terminal timeout shortly after 25 seconds.  Keep the socket and
     * fault alive long enough to observe the terminal reason rather than
     * releasing the NSP connection early.
     */
    sleep(28);

    memset(&discdata, 0, sizeof(discdata));
    optlen = sizeof(discdata);
    if (getsockopt(fd, DNPROTO_NSP, DSO_DISDATA, &discdata, &optlen) ||
        optlen != sizeof(discdata) ||
        dniv_le16_to_cpu(discdata.opt_status) != NODE_UNREACHABLE ||
        dniv_le16_to_cpu(discdata.opt_optl) != 0U) {
        fprintf(stderr,
                "DI exhaustion DSO_DISDATA mismatch status=%u len=%u optlen=%u\n",
                (unsigned int)dniv_le16_to_cpu(discdata.opt_status),
                (unsigned int)dniv_le16_to_cpu(discdata.opt_optl),
                (unsigned int)optlen);
        goto fail;
    }

    memset(&pfd, 0, sizeof(pfd));
    pfd.fd = fd;
    pfd.events = POLLIN | POLLOUT;
    pret = poll(&pfd, 1, 0);
    if (pret != 1 || !(pfd.revents & POLLERR) || !(pfd.revents & POLLHUP)) {
        fprintf(stderr, "DI exhaustion poll mismatch ret=%d revents=0x%x\n",
                pret, pfd.revents);
        goto fail;
    }

    close(fd);
    fd = -1;
    printf("DNIV-INTEROP-DIEXHAUSTED session=%s scenario=%s errno=%d\n",
           argv[2], argv[3], EHOSTUNREACH);

    sleep(3);
    recovery = open_mirror(&peer);
    if (recovery < 0 || mirror_exchange(recovery, RECOVER_PAYLOAD))
        goto fail;
    close(recovery);
    printf("dndiexhaust: pass peer=%s reason=%u recovery=1\n",
           argv[1], NODE_UNREACHABLE);
    return 0;

fail:
    fprintf(stderr, "dndiexhaust: failed errno=%d (%s)\n", errno, strerror(errno));
    if (fd >= 0)
        close(fd);
    if (recovery >= 0)
        close(recovery);
    return 1;
}
