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

#define INT_PAYLOAD "DNIV-INT-LOSS"
#define RECOVER_PAYLOAD "DNIV-INT-RECOVER"

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
    unsigned char tx[64];
    unsigned char rx[64];
    struct sockaddr_dn peer;
    struct timeval timeout = { .tv_sec = 30, .tv_usec = 0 };
    uint16_t address;
    size_t payload_len;
    ssize_t sent, got;
    int fd;

    setvbuf(stdout, NULL, _IONBF, 0);
    if (argc != 4 || parse_node(argv[1], &address)) {
        fprintf(stderr, "usage: %s AREA.NODE SESSION SCENARIO\n", argv[0]);
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
        perror("connect(MIRROR interrupt-loss probe)");
        close(fd);
        return 1;
    }

    printf("DNIV-INTEROP-INTLOSS-CONNECTED session=%s scenario=%s peer=%s\n",
           argv[2], argv[3], argv[1]);
    sleep(5);

    payload_len = sizeof(INT_PAYLOAD) - 1U;
    sent = send(fd, INT_PAYLOAD, payload_len, MSG_OOB | MSG_NOSIGNAL);
    if (sent != (ssize_t)payload_len) {
        if (sent < 0)
            perror("send(MSG_OOB interrupt-loss probe)");
        else
            fprintf(stderr, "short interrupt-loss send: %zd/%zu\n",
                    sent, payload_len);
        close(fd);
        return 1;
    }
    printf("DNIV-INTEROP-INTLOSS-SENT session=%s scenario=%s peer=%s\n",
           argv[2], argv[3], argv[1]);

    /*
     * The host proof drops the real ACK_OTHER, observes the timer
     * retransmission, injects a valid ACK_OTHER, and then watches through
     * another response interval.  Keep this connection alive throughout.
     */
    sleep(15);

    tx[0] = 0U;
    memcpy(tx + 1U, RECOVER_PAYLOAD, sizeof(RECOVER_PAYLOAD) - 1U);
    payload_len = sizeof(RECOVER_PAYLOAD);
    sent = send(fd, tx, payload_len, MSG_EOR | MSG_NOSIGNAL);
    if (sent != (ssize_t)payload_len) {
        if (sent < 0)
            perror("send(MIRROR interrupt-loss recovery)");
        else
            fprintf(stderr, "short interrupt-loss recovery send: %zd/%zu\n",
                    sent, payload_len);
        close(fd);
        return 1;
    }
    got = recv(fd, rx, sizeof(rx), 0);
    if (got != (ssize_t)payload_len || rx[0] != 1U ||
        memcmp(rx + 1U, tx + 1U, payload_len - 1U)) {
        if (got < 0)
            perror("recv(MIRROR interrupt-loss recovery)");
        else
            fprintf(stderr,
                    "bad interrupt-loss recovery reply: got=%zd expected=%zu\n",
                    got, payload_len);
        close(fd);
        return 1;
    }

    close(fd);
    printf("dnintloss: pass peer=%s timer-retransmit+ack-recovery\n", argv[1]);
    return 0;
}
