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
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>

#include <linux/dn.h>

#define STALLED_RECORDS 20U
#define PAYLOAD 128U

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
    struct timeval timeout = { .tv_sec = 20, .tv_usec = 0 };
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

static void make_payload(unsigned char *buf, unsigned int tag)
{
    size_t i;

    buf[0] = 0U;
    for (i = 1U; i < PAYLOAD; i++)
        buf[i] = (unsigned char)((i * 19U + tag * 23U) & 0xffU);
}

static int check_reply(const unsigned char *tx, const unsigned char *rx,
                       ssize_t got)
{
    return got == (ssize_t)PAYLOAD && rx[0] == 1U &&
           !memcmp(rx + 1U, tx + 1U, PAYLOAD - 1U) ? 0 : -1;
}

int main(int argc, char **argv)
{
    struct sockaddr_dn peer;
    unsigned char tx[PAYLOAD], rx[PAYLOAD];
    uint16_t address;
    unsigned int i;
    int stalled = -1;
    int survivor = -1;

    if (argc != 2 || parse_node(argv[1], &address)) {
        fprintf(stderr, "usage: %s AREA.NODE\n", argv[0]);
        return 2;
    }
    fill_peer(&peer, address);

    stalled = open_mirror(&peer);
    if (stalled < 0)
        goto fail;

    for (i = 0U; i < STALLED_RECORDS; i++) {
        make_payload(tx, 100U + i);
        if (send(stalled, tx, sizeof(tx), MSG_EOR | MSG_NOSIGNAL) !=
            (ssize_t)sizeof(tx))
            goto fail;
    }

    /*
     * Leave all replies queued on this socket.  A receiver-stalled logical
     * link must not prevent a separate valid session from making progress.
     */
    sleep(1);
    survivor = open_mirror(&peer);
    if (survivor < 0)
        goto fail;
    make_payload(tx, 999U);
    if (send(survivor, tx, sizeof(tx), MSG_EOR | MSG_NOSIGNAL) !=
        (ssize_t)sizeof(tx) ||
        check_reply(tx, rx, recv(survivor, rx, sizeof(rx), 0)))
        goto fail;
    close(survivor);
    survivor = -1;

    for (i = 0U; i < STALLED_RECORDS; i++) {
        make_payload(tx, 100U + i);
        if (check_reply(tx, rx, recv(stalled, rx, sizeof(rx), 0)))
            goto fail;
    }
    close(stalled);
    printf("dnfair: pass peer=%s stalled_records=%u survivor=1 drain=1\n",
           argv[1], STALLED_RECORDS);
    return 0;

fail:
    fprintf(stderr, "dnfair: failed errno=%d (%s)\n", errno, strerror(errno));
    if (survivor >= 0)
        close(survivor);
    if (stalled >= 0)
        close(stalled);
    return 1;
}
