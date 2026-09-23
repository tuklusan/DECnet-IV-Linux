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

#define INT_ONE "DNIV-IFLOW-1"
#define INT_TWO "DNIV-IFLOW-2"
#define INT_THREE "DNIV-IFLOW-3"
#define INT_FOUR "DNIV-IFLOW-4"
#define RECOVER_PAYLOAD "DNIV-IFLOW-DATA"

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

static int send_oob(int fd, const char *payload, int flags)
{
    size_t len = strlen(payload);
    ssize_t sent = send(fd, payload, len, MSG_OOB | MSG_NOSIGNAL | flags);

    if (sent == (ssize_t)len)
        return 0;
    if (sent >= 0)
        errno = EIO;
    return -1;
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
        perror("connect(MIRROR interrupt-flow probe)");
        close(fd);
        return 1;
    }

    printf("DNIV-INTEROP-INTFLOW-CONNECTED session=%s scenario=%s peer=%s\n",
           argv[2], argv[3], argv[1]);
    sleep(5);

    if (send_oob(fd, INT_ONE, 0)) {
        perror("send(first interrupt)");
        close(fd);
        return 1;
    }
    printf("DNIV-INTEROP-INTFLOW-FIRST session=%s scenario=%s peer=%s\n",
           argv[2], argv[3], argv[1]);

    /* ACK_OTHER is not interrupt credit. */
    sleep(4);
    errno = 0;
    if (!send_oob(fd, INT_TWO, MSG_DONTWAIT) ||
        (errno != EAGAIN && errno != EWOULDBLOCK)) {
        fprintf(stderr,
                "second interrupt was not blocked without interrupt credit: errno=%d\n",
                errno);
        close(fd);
        return 1;
    }
    printf("DNIV-INTEROP-INTFLOW-BLOCKED session=%s scenario=%s peer=%s\n",
           argv[2], argv[3], argv[1]);

    /*
     * The host has already queued a future credit grant.  Only the missing
     * in-order Link Service message may release this blocking send; closing
     * that sequence gap also applies the cached second grant.
     */
    if (send_oob(fd, INT_TWO, 0)) {
        perror("send(second interrupt after credit)");
        close(fd);
        return 1;
    }
    if (send_oob(fd, INT_THREE, MSG_DONTWAIT)) {
        perror("send(third interrupt from cached credit)");
        close(fd);
        return 1;
    }
    printf("DNIV-INTEROP-INTFLOW-BURST session=%s scenario=%s peer=%s\n",
           argv[2], argv[3], argv[1]);

    /*
     * The host now sends a stale duplicate grant with a large delta.
     * A duplicate Link Service packet must not restore credit.
     */
    sleep(3);
    errno = 0;
    if (!send_oob(fd, INT_FOUR, MSG_DONTWAIT) ||
        (errno != EAGAIN && errno != EWOULDBLOCK)) {
        fprintf(stderr,
                "stale duplicate interrupt grant changed credit: errno=%d\n",
                errno);
        close(fd);
        return 1;
    }
    printf("DNIV-INTEROP-INTFLOW-STALE-BLOCKED session=%s scenario=%s peer=%s\n",
           argv[2], argv[3], argv[1]);

    tx[0] = 0U;
    memcpy(tx + 1U, RECOVER_PAYLOAD, sizeof(RECOVER_PAYLOAD) - 1U);
    payload_len = sizeof(RECOVER_PAYLOAD);
    sent = send(fd, tx, payload_len, MSG_EOR | MSG_NOSIGNAL);
    if (sent != (ssize_t)payload_len) {
        if (sent < 0)
            perror("send(MIRROR interrupt-flow recovery)");
        else
            fprintf(stderr, "short interrupt-flow recovery send: %zd/%zu\n",
                    sent, payload_len);
        close(fd);
        return 1;
    }
    got = recv(fd, rx, sizeof(rx), 0);
    if (got != (ssize_t)payload_len || rx[0] != 1U ||
        memcmp(rx + 1U, tx + 1U, payload_len - 1U)) {
        if (got < 0)
            perror("recv(MIRROR interrupt-flow recovery)");
        else
            fprintf(stderr,
                    "bad interrupt-flow recovery reply: got=%zd expected=%zu\n",
                    got, payload_len);
        close(fd);
        return 1;
    }

    close(fd);
    printf("dnintflow: pass peer=%s credit-block+future-order+stale-ignore\n",
           argv[1]);
    return 0;
}
