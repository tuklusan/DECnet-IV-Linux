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

#define RETRY_OBJECT 248U
#define RETRY_PAYLOAD "DNIV-CC-RETRY"

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

static int peer_is(int fd, uint16_t expected)
{
    struct sockaddr_dn peer;
    socklen_t length = sizeof(peer);
    uint16_t node;

    memset(&peer, 0, sizeof(peer));
    if (getpeername(fd, (struct sockaddr *)&peer, &length) ||
        length != sizeof(peer) || peer.sdn_family != AF_DECnet ||
        dniv_le16_to_cpu(peer.sdn_nodeaddrl) != 2U)
        return -1;
    node = (uint16_t)(peer.sdn_nodeaddr[0] |
                      ((uint16_t)peer.sdn_nodeaddr[1] << 8));
    return node == expected ? 0 : -1;
}

int main(int argc, char **argv)
{
    struct sockaddr_dn local;
    struct timeval timeout = { .tv_sec = 30, .tv_usec = 0 };
    unsigned char buffer[128];
    uint16_t expected_node;
    int acceptmode = ACC_DEFER;
    ssize_t got;
    int listener = -1;
    int fd = -1;

    setvbuf(stdout, NULL, _IONBF, 0);
    if (argc != 4 || parse_node(argv[1], &expected_node)) {
        fprintf(stderr, "usage: %s PEER-AREA.NODE SESSION SCENARIO\n", argv[0]);
        return 2;
    }

    listener = socket(AF_DECnet, SOCK_SEQPACKET, DNPROTO_NSP);
    if (listener < 0)
        goto fail;
    if (setsockopt(listener, SOL_SOCKET, SO_RCVTIMEO,
                   &timeout, sizeof(timeout)) ||
        setsockopt(listener, DNPROTO_NSP, DSO_ACCEPTMODE,
                   &acceptmode, sizeof(acceptmode)))
        goto fail;

    memset(&local, 0, sizeof(local));
    local.sdn_family = AF_DECnet;
    local.sdn_objnum = RETRY_OBJECT;
    if (bind(listener, (struct sockaddr *)&local, sizeof(local)) ||
        listen(listener, 1))
        goto fail;

    printf("DNIV-INTEROP-CCRETRY-READY session=%s scenario=%s object=%u\n",
           argv[2], argv[3], RETRY_OBJECT);

    fd = accept(listener, NULL, NULL);
    if (fd < 0 || peer_is(fd, expected_node))
        goto fail;
    if (setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)) ||
        setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout)))
        goto fail;

    printf("DNIV-INTEROP-CCRETRY-ACCEPTED session=%s scenario=%s peer=%s\n",
           argv[2], argv[3], argv[1]);

    /* Give the host time to arm its ACK-loss filter and CC observer. */
    sleep(4);
    if (setsockopt(fd, DNPROTO_NSP, DSO_CONACCEPT, NULL, 0))
        goto fail;
    printf("DNIV-INTEROP-CCRETRY-CONFIRM-SENT session=%s scenario=%s peer=%s\n",
           argv[2], argv[3], argv[1]);

    got = recv(fd, buffer, sizeof(buffer), 0);
    if (got != (ssize_t)(sizeof(RETRY_PAYLOAD) - 1U) ||
        memcmp(buffer, RETRY_PAYLOAD, sizeof(RETRY_PAYLOAD) - 1U))
        goto fail;
    if (send(fd, buffer, (size_t)got, MSG_EOR | MSG_NOSIGNAL) != got)
        goto fail;
    got = recv(fd, buffer, sizeof(buffer), 0);
    if (got != 0)
        goto fail;

    close(fd);
    close(listener);
    printf("dnccretry: pass peer=%s duplicate-confirm-recovery=1\n", argv[1]);
    return 0;

fail:
    fprintf(stderr, "dnccretry: failed errno=%d (%s)\n", errno, strerror(errno));
    if (fd >= 0)
        close(fd);
    if (listener >= 0)
        close(listener);
    return 1;
}
