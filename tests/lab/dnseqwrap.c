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

#define _POSIX_C_SOURCE 200809L

#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>

#include <linux/dn.h>

#define RECORD_SIZE 4096U
#define RECORDS 130U
#define PRESSURE_RECORDS 650U
#define PRESSURE_PAUSE_NS 250000000L

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
    unsigned char tx[RECORD_SIZE];
    unsigned char rx[RECORD_SIZE];
    struct sockaddr_dn peer;
    struct timeval timeout = { .tv_sec = 30, .tv_usec = 0 };
    uint16_t address;
    unsigned int record;
    unsigned int records = RECORDS;
    unsigned long round = 0;
    int pressure = 0;
    int fd;

    setvbuf(stdout, NULL, _IONBF, 0);
    if (parse_node(argc > 1 ? argv[1] : "", &address)) {
        fprintf(stderr, "usage: %s AREA.NODE [pressure ROUND]\n", argv[0]);
        return 2;
    }
    if (argc == 4 && !strcmp(argv[2], "pressure")) {
        char *end;

        errno = 0;
        round = strtoul(argv[3], &end, 10);
        if (errno || end == argv[3] || *end || round < 1UL || round > 3UL) {
            fprintf(stderr, "invalid pressure round: %s\n", argv[3]);
            return 2;
        }
        pressure = 1;
        records = PRESSURE_RECORDS;
    } else if (argc != 2) {
        fprintf(stderr, "usage: %s AREA.NODE [pressure ROUND]\n", argv[0]);
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
        perror("connect(MIRROR seqwrap)");
        close(fd);
        return 1;
    }

    if (pressure)
        printf("DNIV-PP11-SEQWRAP-START round=%lu records=%u pause_ms=250\n",
               round, records);

    for (record = 0; record < records; record++) {
        size_t i;
        ssize_t sent, got;

        tx[0] = 0U;
        tx[1] = (unsigned char)(record & 0xffU);
        tx[2] = (unsigned char)(record >> 8);
        for (i = 3U; i < sizeof(tx); i++)
            tx[i] = (unsigned char)((i * 29U + record * 17U) & 0xffU);

        sent = send(fd, tx, sizeof(tx), MSG_EOR | MSG_NOSIGNAL);
        if (sent != (ssize_t)sizeof(tx)) {
            if (sent < 0)
                perror("send(MIRROR seqwrap)");
            else
                fprintf(stderr, "short seqwrap send: %zd/%zu\n",
                        sent, sizeof(tx));
            close(fd);
            return 1;
        }

        got = recv(fd, rx, sizeof(rx), 0);
        if (got != (ssize_t)sizeof(tx) || rx[0] != 1U ||
            memcmp(rx + 1U, tx + 1U, sizeof(tx) - 1U)) {
            if (got < 0)
                perror("recv(MIRROR seqwrap)");
            else
                fprintf(stderr,
                        "bad seqwrap reply: record=%u got=%zd expected=%zu\n",
                        record, got, sizeof(tx));
            close(fd);
            return 1;
        }
        if (pressure) {
            struct timespec pause = { .tv_sec = 0, .tv_nsec = PRESSURE_PAUSE_NS };

            if ((record + 1U) % 25U == 0U)
                printf("DNIV-PP11-SEQWRAP-LIVE round=%lu records=%u\n",
                       round, record + 1U);
            while (nanosleep(&pause, &pause) && errno == EINTR)
                ;
        }
    }

    close(fd);
    if (pressure)
        printf("DNIV-PP11-SEQWRAP-PASS round=%lu records=%u bytes=%u\n",
               round, records, records * RECORD_SIZE);
    printf("dnseqwrap: pass peer=%s records=%u bytes=%u\n",
           argv[1], records, records * RECORD_SIZE);
    return 0;
}
