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
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>

#include <linux/dn.h>

#define DNIV_MIRROR_OBJECT 25U
#define DNIV_MIRROR_BACKLOG 8

static __le16 cpu_to_le16_u(uint16_t value)
{
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
    return (__le16)value;
#else
    return (__le16)__builtin_bswap16(value);
#endif
}

static int make_listener(void)
{
    static const unsigned char accept_data[] = { 0xffU, 0xffU };
    struct optdata_dn conndata;
    struct sockaddr_dn local;
    int fd;

    fd = socket(AF_DECnet, SOCK_SEQPACKET, DNPROTO_NSP);
    if (fd < 0)
        return -1;

    memset(&conndata, 0, sizeof(conndata));
    conndata.opt_optl = cpu_to_le16_u(sizeof(accept_data));
    memcpy(conndata.opt_data, accept_data, sizeof(accept_data));
    if (setsockopt(fd, DNPROTO_NSP, DSO_CONDATA,
                   &conndata, sizeof(conndata)) < 0)
        goto fail;

    memset(&local, 0, sizeof(local));
    local.sdn_family = AF_DECnet;
    local.sdn_objnum = DNIV_MIRROR_OBJECT;
    if (bind(fd, (struct sockaddr *)&local, sizeof(local)) < 0 ||
        listen(fd, DNIV_MIRROR_BACKLOG) < 0)
        goto fail;
    return fd;

fail:
    close(fd);
    return -1;
}

static int serve_connection(int fd)
{
    struct timeval timeout = { .tv_sec = 30, .tv_usec = 0 };
    unsigned char in[65535];
    unsigned char out[65535];

    if (setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO,
                   &timeout, sizeof(timeout)) < 0 ||
        setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO,
                   &timeout, sizeof(timeout)) < 0)
        return -1;

    for (;;) {
        ssize_t got = recv(fd, in, sizeof(in), 0);
        size_t out_len;

        if (got == 0)
            return 0;
        if (got < 0)
            return -1;

        if (in[0] == 0U) {
            out[0] = 1U;
            if (got > 1)
                memcpy(out + 1U, in + 1U, (size_t)got - 1U);
            out_len = (size_t)got;
        } else {
            out[0] = 0xffU;
            out_len = 1U;
        }

        if (send(fd, out, out_len, MSG_EOR | MSG_NOSIGNAL) !=
            (ssize_t)out_len)
            return -1;
    }
}

int main(int argc, char **argv)
{
    int once = 0;
    int listener;

    if (argc == 2 && strcmp(argv[1], "--once") == 0)
        once = 1;
    else if (argc != 1) {
        fprintf(stderr, "usage: %s [--once]\n", argv[0]);
        return 2;
    }

    listener = make_listener();
    if (listener < 0) {
        perror("dnmirror: listen");
        return 1;
    }

    for (;;) {
        int fd = accept(listener, NULL, NULL);
        int rc;

        if (fd < 0) {
            if (errno == EINTR)
                continue;
            perror("dnmirror: accept");
            close(listener);
            return 1;
        }

        rc = serve_connection(fd);
        close(fd);
        if (rc) {
            perror("dnmirror: session");
            close(listener);
            return 1;
        }
        if (once)
            break;
    }

    close(listener);
    return 0;
}
