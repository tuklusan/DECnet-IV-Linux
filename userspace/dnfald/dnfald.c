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
#include <linux/dn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>

#define DAP_FAL_OBJECT 17U
#define DAP_CONFIG 1U
#define DNFAL_BACKLOG 8

static size_t make_config(unsigned char *buf, size_t cap)
{
    if (cap < 12U)
        return 0U;
    buf[0] = DAP_CONFIG;
    buf[1] = 0U;
    buf[2] = 0U;
    buf[3] = 4U;
    buf[4] = 128U;
    buf[5] = 128U;
    buf[6] = 4U;
    buf[7] = 1U;
    buf[8] = 0U;
    buf[9] = 0U;
    buf[10] = 0U;
    buf[11] = 0U;
    return 12U;
}

static int validate_config(const unsigned char *buf, size_t len)
{
    return len >= 12U && buf[0] == DAP_CONFIG && !(buf[1] & 0x7fU) ? 0 : -1;
}

static int make_listener(void)
{
    struct sockaddr_dn local;
    int fd;

    fd = socket(AF_DECnet, SOCK_SEQPACKET, DNPROTO_NSP);
    if (fd < 0)
        return -1;
    memset(&local, 0, sizeof(local));
    local.sdn_family = AF_DECnet;
    local.sdn_objnum = DAP_FAL_OBJECT;
    if (bind(fd, (struct sockaddr *)&local, sizeof(local)) < 0 ||
        listen(fd, DNFAL_BACKLOG) < 0) {
        close(fd);
        return -1;
    }
    return fd;
}

static int serve_config(int fd)
{
    struct timeval timeout = { .tv_sec = 30, .tv_usec = 0 };
    unsigned char request[256];
    unsigned char reply[32];
    size_t reply_len;
    ssize_t got;

    if (setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)) < 0 ||
        setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout)) < 0)
        return -1;
    got = recv(fd, request, sizeof(request), 0);
    if (got < 0 || validate_config(request, (size_t)got))
        return -1;
    reply_len = make_config(reply, sizeof(reply));
    if (!reply_len ||
        send(fd, reply, reply_len, MSG_EOR | MSG_NOSIGNAL) != (ssize_t)reply_len)
        return -1;
    return 0;
}

static int selftest(void)
{
    unsigned char config[16];

    if (make_config(config, sizeof(config)) != 12U ||
        validate_config(config, 12U) ||
        config[3] != 4U || config[4] != 128U || config[5] != 128U ||
        config[6] != 4U || config[7] != 1U)
        return 1;
    config[0] = 2U;
    if (!validate_config(config, 12U))
        return 1;
    puts("dnfald selftest passed");
    return 0;
}

int main(int argc, char **argv)
{
    int once = 0;
    int listener;

    if (argc == 2 && !strcmp(argv[1], "--selftest"))
        return selftest();
    if (argc == 2 && !strcmp(argv[1], "--once"))
        once = 1;
    else if (argc != 1) {
        fprintf(stderr, "usage: %s [--once|--selftest]\n", argv[0]);
        return 2;
    }

    setvbuf(stdout, NULL, _IONBF, 0);
    listener = make_listener();
    if (listener < 0) {
        perror("dnfald: listen");
        return 1;
    }
    printf("dnfald: ready object=%u\n", DAP_FAL_OBJECT);

    for (;;) {
        int fd = accept(listener, NULL, NULL);
        int rc;

        if (fd < 0) {
            if (errno == EINTR)
                continue;
            perror("dnfald: accept");
            close(listener);
            return 1;
        }
        rc = serve_config(fd);
        close(fd);
        if (rc) {
            perror("dnfald: session");
            close(listener);
            return 1;
        }
        if (once)
            break;
    }
    close(listener);
    return 0;
}
