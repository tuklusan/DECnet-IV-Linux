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

#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <linux/decnet_iv.h>
#include <linux/dn.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <unistd.h>

#ifndef AF_DECnet
#define AF_DECnet 12
#endif

static int must_fail(int rc, const char *what)
{
    if (rc >= 0) {
        fprintf(stderr, "dnhostile: unexpected success: %s\n", what);
        return -1;
    }
    return 0;
}

int main(int argc, char **argv)
{
    unsigned long iterations = 4096;
    struct dniv_identity identity;
    struct sockaddr_dn addr;
    unsigned char *oversize;
    uint32_t state = 0x6d2b79f5U;
    unsigned long i;
    int dev;
    int fd;
    int one = 1;

    if (argc == 2) {
        char *end = NULL;
        errno = 0;
        iterations = strtoul(argv[1], &end, 10);
        if (errno || !end || *end || iterations < 256 || iterations > 100000) {
            fprintf(stderr, "usage: %s [ITERATIONS(256..100000)]\n", argv[0]);
            return 2;
        }
    } else if (argc != 1) {
        fprintf(stderr, "usage: %s [ITERATIONS(256..100000)]\n", argv[0]);
        return 2;
    }

    dev = open("/dev/decnet_iv", O_RDWR | O_CLOEXEC);
    if (dev < 0) {
        perror("open /dev/decnet_iv");
        return 1;
    }

    if (must_fail(ioctl(dev, DNIV_IOC_GET_IDENTITY, NULL),
                  "GET_IDENTITY null") ||
        must_fail(ioctl(dev, DNIV_IOC_SET_IDENTITY, NULL),
                  "SET_IDENTITY null") ||
        must_fail(ioctl(dev, DNIV_IOC_GET_STATS, NULL),
                  "GET_STATS null") ||
        must_fail(ioctl(dev, DNIV_IOC_GET_ADJACENCY, NULL),
                  "GET_ADJACENCY null") ||
        must_fail(ioctl(dev, DNIV_IOC_GET_ROUTE, NULL),
                  "GET_ROUTE null") ||
        must_fail(ioctl(dev, DNIV_IOC_GET_LINK, NULL),
                  "GET_LINK null") ||
        must_fail(ioctl(dev, DNIV_IOC_GET_TRAFFIC_STATS, NULL),
                  "GET_TRAFFIC_STATS null")) {
        close(dev);
        return 1;
    }

    memset(&identity, 0, sizeof(identity));
    identity.uapi_version = 0;
    identity.address = 0;
    if (must_fail(ioctl(dev, DNIV_IOC_SET_IDENTITY, &identity),
                  "SET_IDENTITY invalid version/address")) {
        close(dev);
        return 1;
    }

    for (i = 0; i < iterations; i++) {
        unsigned int nr;
        unsigned long cmd;

        state = state * 1664525U + 1013904223U;
        nr = 0x80U + ((state >> 24) & 0x7fU);
        cmd = _IOC(_IOC_NONE, DNIV_IOC_MAGIC, nr, 0);
        if (ioctl(dev, cmd, 0UL) >= 0) {
            fprintf(stderr, "dnhostile: unknown ioctl 0x%lx succeeded\n", cmd);
            close(dev);
            return 1;
        }
    }
    close(dev);

    fd = socket(AF_DECnet, SOCK_SEQPACKET, DNPROTO_NSP);
    if (fd < 0) {
        perror("socket AF_DECnet");
        return 1;
    }

    memset(&addr, 0, sizeof(addr));
    addr.sdn_family = 0;
    if (must_fail(bind(fd, (struct sockaddr *)&addr, sizeof(addr)),
                  "bind wrong family"))
        goto fail;

    memset(&addr, 0, sizeof(addr));
    addr.sdn_family = AF_DECnet;
    addr.sdn_objnamel = DN_MAXOBJL + 1U;
    if (must_fail(bind(fd, (struct sockaddr *)&addr, sizeof(addr)),
                  "bind overlong object name"))
        goto fail;

    memset(&addr, 0, sizeof(addr));
    addr.sdn_family = AF_DECnet;
    addr.sdn_objnum = 25;
    if (must_fail(bind(fd, (struct sockaddr *)&addr, sizeof(addr) - 1U),
                  "bind short sockaddr"))
        goto fail;

    if (must_fail(connect(fd, (struct sockaddr *)&addr, sizeof(addr) - 1U),
                  "connect short sockaddr"))
        goto fail;

    if (must_fail(setsockopt(fd, DNPROTO_NSP, DSO_MAX + 100, &one, sizeof(one)),
                  "setsockopt unknown option"))
        goto fail;

    if (must_fail(send(fd, "x", 1, MSG_DONTROUTE),
                  "send unsupported flag"))
        goto fail;

    oversize = malloc((size_t)DNBUFSIZE + 1U);
    if (!oversize) {
        perror("malloc");
        goto fail;
    }
    memset(oversize, 0xa5, (size_t)DNBUFSIZE + 1U);
    if (must_fail(send(fd, oversize, (size_t)DNBUFSIZE + 1U, MSG_EOR),
                  "send oversized sequenced record")) {
        free(oversize);
        goto fail;
    }
    free(oversize);

    for (i = 0; i < iterations; i++) {
        int optname;

        state = state * 1664525U + 1013904223U;
        optname = 0x100 + (int)((state >> 16) & 0x7fffU);
        if (setsockopt(fd, DNPROTO_NSP, optname, &state, sizeof(state)) >= 0) {
            fprintf(stderr, "dnhostile: unknown setsockopt %d succeeded\n", optname);
            goto fail;
        }
    }

    close(fd);
    printf("DNIV-HOSTILE-PASS iterations=%lu\n", iterations);
    return 0;

fail:
    close(fd);
    return 1;
}
