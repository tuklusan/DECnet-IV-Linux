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

#define TEST_OBJECT 240U
#define TEST_NAME "DNIVTEST"
#define SOURCE_NAME "PYDNIV"

static uint16_t dniv_le16_to_cpu(__le16 value)
{
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
    return (uint16_t)value;
#else
    return __builtin_bswap16((uint16_t)value);
#endif
}

static __le16 dniv_cpu_to_le16(uint16_t value)
{
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
    return (__le16)value;
#else
    return (__le16)__builtin_bswap16(value);
#endif
}

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
    if (errno || end == text || *end || node < 1U || node > 1023U)
        return -1;
    *address = (uint16_t)((area << 10) | node);
    return 0;
}

static int make_listener(int named)
{
    struct sockaddr_dn local;
    struct timeval timeout = { .tv_sec = 30, .tv_usec = 0 };
    int fd;

    fd = socket(AF_DECnet, SOCK_SEQPACKET, DNPROTO_NSP);
    if (fd < 0)
        return -1;
    if (setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)))
        goto fail;

    memset(&local, 0, sizeof(local));
    local.sdn_family = AF_DECnet;
    if (named) {
        local.sdn_objnamel = dniv_cpu_to_le16(sizeof(TEST_NAME) - 1U);
        memcpy(local.sdn_objname, TEST_NAME, sizeof(TEST_NAME) - 1U);
    } else {
        local.sdn_objnum = TEST_OBJECT;
    }
    if (bind(fd, (struct sockaddr *)&local, sizeof(local)) || listen(fd, 2))
        goto fail;
    return fd;

fail:
    close(fd);
    return -1;
}

static int serve_one(int listener, uint16_t expected_node,
                     const char *payload)
{
    struct sockaddr_dn peer;
    socklen_t peer_len = sizeof(peer);
    struct timeval timeout = { .tv_sec = 30, .tv_usec = 0 };
    unsigned char buf[128];
    uint16_t node;
    size_t expected = strlen(payload);
    ssize_t got;
    int fd;

    fd = accept(listener, NULL, NULL);
    if (fd < 0)
        return -1;
    if (setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)) ||
        setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout)))
        goto fail;

    memset(&peer, 0, sizeof(peer));
    if (getpeername(fd, (struct sockaddr *)&peer, &peer_len) ||
        peer_len != sizeof(peer) || peer.sdn_family != AF_DECnet ||
        dniv_le16_to_cpu(peer.sdn_nodeaddrl) != 2U)
        goto fail;
    node = (uint16_t)(peer.sdn_nodeaddr[0] |
                      ((uint16_t)peer.sdn_nodeaddr[1] << 8));
    if (node != expected_node || peer.sdn_objnum ||
        dniv_le16_to_cpu(peer.sdn_objnamel) != sizeof(SOURCE_NAME) - 1U ||
        memcmp(peer.sdn_objname, SOURCE_NAME, sizeof(SOURCE_NAME) - 1U))
        goto fail;

    got = recv(fd, buf, sizeof(buf), 0);
    if (got != (ssize_t)expected || memcmp(buf, payload, expected))
        goto fail;
    if (send(fd, buf, expected, MSG_EOR | MSG_NOSIGNAL) != (ssize_t)expected)
        goto fail;

    got = recv(fd, buf, sizeof(buf), 0);
    if (got != 0)
        goto fail;
    close(fd);
    return 0;

fail:
    close(fd);
    return -1;
}

int main(int argc, char **argv)
{
    uint16_t expected_node;
    int numeric;
    int named;

    setvbuf(stdout, NULL, _IONBF, 0);
    if (argc != 4 || parse_node(argv[1], &expected_node)) {
        fprintf(stderr, "usage: %s PEER-AREA.NODE SESSION SCENARIO\n", argv[0]);
        return 2;
    }

    numeric = make_listener(0);
    if (numeric < 0) {
        perror("numeric listener");
        return 1;
    }
    named = make_listener(1);
    if (named < 0) {
        perror("named listener");
        close(numeric);
        return 1;
    }

    printf("DNIV-INTEROP-LISTEN-READY session=%s scenario=%s\n",
           argv[2], argv[3]);
    if (serve_one(numeric, expected_node, "numeric-inbound") ||
        serve_one(named, expected_node, "named-inbound")) {
        fprintf(stderr, "dnaccept: inbound listener exchange failed\n");
        close(named);
        close(numeric);
        return 1;
    }

    close(named);
    close(numeric);
    printf("DNIV-INTEROP-LISTEN-SERVER-PASS session=%s scenario=%s\n",
           argv[2], argv[3]);
    return 0;
}
