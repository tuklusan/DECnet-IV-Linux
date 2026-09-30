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

#define DNIV_OBJECT_BACKLOG 8

static __le16 cpu_to_le16_u(uint16_t value)
{
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
    return (__le16)value;
#else
    return (__le16)__builtin_bswap16(value);
#endif
}

static int make_listener(const char *name, unsigned int number)
{
    struct sockaddr_dn local;
    int fd;

    fd = socket(AF_DECnet, SOCK_SEQPACKET, DNPROTO_NSP);
    if (fd < 0)
        return -1;

    memset(&local, 0, sizeof(local));
    local.sdn_family = AF_DECnet;
    if (name) {
        size_t len = strlen(name);

        local.sdn_objnamel = cpu_to_le16_u((uint16_t)len);
        memcpy(local.sdn_objname, name, len);
    } else {
        local.sdn_objnum = (unsigned char)number;
    }

    if (bind(fd, (struct sockaddr *)&local, sizeof(local)) < 0 ||
        listen(fd, DNIV_OBJECT_BACKLOG) < 0) {
        close(fd);
        return -1;
    }
    return fd;
}

static int serve_connection(int fd)
{
    struct timeval timeout = { .tv_sec = 30, .tv_usec = 0 };
    unsigned char buffer[DNBUFSIZE];

    if (setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO,
                   &timeout, sizeof(timeout)) < 0 ||
        setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO,
                   &timeout, sizeof(timeout)) < 0)
        return -1;

    for (;;) {
        ssize_t got = recv(fd, buffer, sizeof(buffer), 0);

        if (got == 0)
            return 0;
        if (got < 0)
            return -1;
        if (send(fd, buffer, (size_t)got, MSG_EOR | MSG_NOSIGNAL) != got)
            return -1;
    }
}

int main(int argc, char **argv)
{
    const char *name = NULL;
    unsigned int number = 0U;
    int once = 0;
    int listener;
    int i;

    for (i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--once") == 0) {
            once = 1;
        } else if (strcmp(argv[i], "--name") == 0 && i + 1 < argc) {
            size_t len;

            name = argv[++i];
            len = strlen(name);
            if (!len || len > DN_MAXOBJL) {
                fprintf(stderr, "dnobject: invalid object name\n");
                return 2;
            }
        } else if (strcmp(argv[i], "--number") == 0 && i + 1 < argc) {
            char *end = NULL;
            unsigned long parsed;

            errno = 0;
            parsed = strtoul(argv[++i], &end, 10);
            if (errno || end == argv[i] || *end || !parsed || parsed > 255U) {
                fprintf(stderr, "dnobject: invalid object number\n");
                return 2;
            }
            number = (unsigned int)parsed;
        } else {
            fprintf(stderr,
                    "usage: %s (--name NAME | --number NUMBER) [--once]\n",
                    argv[0]);
            return 2;
        }
    }

    if (!!name == !!number) {
        fprintf(stderr, "dnobject: select exactly one object name or number\n");
        return 2;
    }

    setvbuf(stdout, NULL, _IONBF, 0);
    listener = make_listener(name, number);
    if (listener < 0) {
        perror("dnobject: listen");
        return 1;
    }

    if (name)
        printf("dnobject: ready name=%s\n", name);
    else
        printf("dnobject: ready number=%u\n", number);

    for (;;) {
        int fd = accept(listener, NULL, NULL);
        int rc;

        if (fd < 0) {
            if (errno == EINTR)
                continue;
            perror("dnobject: accept");
            close(listener);
            return 1;
        }
        rc = serve_connection(fd);
        close(fd);
        if (rc) {
            perror("dnobject: session");
            close(listener);
            return 1;
        }
        if (once)
            break;
    }

    close(listener);
    return 0;
}
