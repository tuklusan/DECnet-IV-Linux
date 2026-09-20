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

int main(int argc, char **argv)
{
    unsigned char tx[4096], rx[4096], pair_tx[100], pair_rx[200];
    struct sockaddr_dn peer;
    struct timeval timeout = { .tv_sec = 20, .tv_usec = 0 };
    uint16_t address;
    size_t off, i;
    int fd;

    if (argc != 2 || parse_node(argv[1], &address)) {
        fprintf(stderr, "usage: %s AREA.NODE\n", argv[0]);
        return 2;
    }
    fd = socket(AF_DECnet, SOCK_STREAM, DNPROTO_NSP);
    if (fd < 0)
        return 1;
    if (setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)) ||
        setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout)))
        goto fail;
    memset(&peer, 0, sizeof(peer));
    peer.sdn_family = AF_DECnet;
    peer.sdn_objnum = 25U;
    peer.sdn_nodeaddrl = (__le16)2U;
    peer.sdn_nodeaddr[0] = (unsigned char)(address & 0xffU);
    peer.sdn_nodeaddr[1] = (unsigned char)(address >> 8);
    if (connect(fd, (struct sockaddr *)&peer, sizeof(peer)))
        goto fail;

    tx[0] = 0U;
    for (i = 1; i < sizeof(tx); i++)
        tx[i] = (unsigned char)((i * 29U) & 0xffU);
    if (send(fd, tx, sizeof(tx), MSG_NOSIGNAL) != (ssize_t)sizeof(tx))
        goto fail;
    off = 0U;
    while (off < sizeof(rx)) {
        size_t want = sizeof(rx) - off;
        ssize_t got;
        if (want > 257U)
            want = 257U;
        got = recv(fd, rx + off, want, 0);
        if (got <= 0)
            goto fail;
        off += (size_t)got;
    }
    if (rx[0] != 1U || memcmp(rx + 1U, tx + 1U, sizeof(tx) - 1U))
        goto fail;

    memset(pair_tx, 0x5a, sizeof(pair_tx));
    pair_tx[0] = 0U;
    if (send(fd, pair_tx, sizeof(pair_tx), MSG_NOSIGNAL) != (ssize_t)sizeof(pair_tx) ||
        send(fd, pair_tx, sizeof(pair_tx), MSG_NOSIGNAL) != (ssize_t)sizeof(pair_tx))
        goto fail;
    if (recv(fd, pair_rx, sizeof(pair_rx), MSG_WAITALL) != (ssize_t)sizeof(pair_rx))
        goto fail;
    for (i = 0; i < 2U; i++) {
        size_t base = i * sizeof(pair_tx);
        if (pair_rx[base] != 1U ||
            memcmp(pair_rx + base + 1U, pair_tx + 1U, sizeof(pair_tx) - 1U))
            goto fail;
    }
    close(fd);
    printf("dnstream: pass peer=%s partial=257 waitall=200\n", argv[1]);
    return 0;
fail:
    perror("dnstream");
    close(fd);
    return 1;
}
