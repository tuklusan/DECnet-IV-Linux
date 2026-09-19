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
    unsigned long area;
    unsigned long node;

    if (!text || !address)
        return -1;

    errno = 0;
    area = strtoul(text, &end, 10);
    if (errno || end == text || *end != '.' || area < 1U || area > 63U)
        return -1;

    text = end + 1;
    errno = 0;
    node = strtoul(text, &end, 10);
    if (errno || end == text || *end != '\0' || node < 1U || node > 1023U)
        return -1;

    *address = (uint16_t)((area << 10) | node);
    return 0;
}

int main(int argc, char **argv)
{
    static const size_t sizes[] = { 1U, 16U, 563U, 564U, 4096U };
    unsigned char tx[4096];
    unsigned char rx[4096];
    struct sockaddr_dn peer;
    struct timeval timeout = { .tv_sec = 20, .tv_usec = 0 };
    uint16_t address;
    size_t test;
    int fd;

    if (argc != 2 || parse_node(argv[1], &address)) {
        fprintf(stderr, "usage: %s AREA.NODE\n", argv[0]);
        return 2;
    }

    fd = socket(AF_DECnet, SOCK_SEQPACKET, DNPROTO_NSP);
    if (fd < 0) {
        perror("socket(AF_DECnet)");
        return 1;
    }

    if (setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)) ||
        setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout))) {
        perror("setsockopt(timeout)");
        close(fd);
        return 1;
    }

    memset(&peer, 0, sizeof(peer));
    peer.sdn_family = AF_DECnet;
    peer.sdn_objnum = 25U;
    peer.sdn_nodeaddrl = (__le16)2U;
    peer.sdn_nodeaddr[0] = (unsigned char)(address & 0xffU);
    peer.sdn_nodeaddr[1] = (unsigned char)(address >> 8);

    if (connect(fd, (struct sockaddr *)&peer, sizeof(peer))) {
        perror("connect(MIRROR)");
        close(fd);
        return 1;
    }

    for (test = 0; test < sizeof(sizes) / sizeof(sizes[0]); test++) {
        size_t size = sizes[test];
        size_t i;
        ssize_t sent;
        ssize_t got;

        tx[0] = 0U;
        for (i = 1; i < size; i++)
            tx[i] = (unsigned char)((i * 37U + test * 19U) & 0xffU);

        sent = send(fd, tx, size, MSG_EOR | MSG_NOSIGNAL);
        if (sent != (ssize_t)size) {
            if (sent < 0)
                perror("send(MIRROR)");
            else
                fprintf(stderr, "short MIRROR send: %zd/%zu\n", sent, size);
            close(fd);
            return 1;
        }

        got = recv(fd, rx, sizeof(rx), 0);
        if (got != (ssize_t)size || rx[0] != 1U ||
            (size > 1U && memcmp(rx + 1, tx + 1, size - 1U))) {
            if (got < 0)
                perror("recv(MIRROR)");
            else
                fprintf(stderr, "bad MIRROR reply: got=%zd expected=%zu\n",
                        got, size);
            close(fd);
            return 1;
        }
    }

    close(fd);
    printf("dnmrr: pass peer=%s records=%zu\n", argv[1],
           sizeof(sizes) / sizeof(sizes[0]));
    return 0;
}
