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

#include <ctype.h>
#include <errno.h>
#include <linux/dn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>

#define PHONE_OBJECT 29U
#define PHONE_REPLYOK 0x01U
#define PHONE_REPLYNOUSER 0x06U
#define PHONE_CONNECT 0x07U
#define PHONE_DIAL 0x08U
#define PHONE_DIRECTORY 0x0fU
#define PHONE_BACKLOG 8

static int make_listener(void)
{
    struct sockaddr_dn local;
    int fd = socket(AF_DECnet, SOCK_SEQPACKET, DNPROTO_NSP);

    if (fd < 0)
        return -1;
    memset(&local, 0, sizeof(local));
    local.sdn_family = AF_DECnet;
    local.sdn_objnum = PHONE_OBJECT;
    if (bind(fd, (struct sockaddr *)&local, sizeof(local)) ||
        listen(fd, PHONE_BACKLOG)) {
        close(fd);
        return -1;
    }
    return fd;
}

static int user_match(const char *target, const char *user)
{
    const char *sep = strstr(target, "::");

    if (!sep || !sep[2])
        return 0;
    target = sep + 2;
    while (*target && *user) {
        if (toupper((unsigned char)*target) != toupper((unsigned char)*user))
            return 0;
        target++;
        user++;
    }
    return !*target && !*user;
}

static int send_code(int fd, unsigned char code)
{
    return send(fd, &code, 1U, MSG_EOR | MSG_NOSIGNAL) == 1 ? 0 : -1;
}

static int serve(int fd, const char *user)
{
    struct timeval timeout = { .tv_sec = 30, .tv_usec = 0 };
    unsigned char buf[1024];
    ssize_t got;

    if (setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)) ||
        setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout)))
        return -1;

    got = recv(fd, buf, sizeof(buf) - 1U, 0);
    if (got < 4 || buf[0] != PHONE_CONNECT)
        return -1;
    buf[got] = 0;
    {
        size_t first = strnlen((char *)buf + 1, (size_t)got - 1U);
        const char *target;

        if (first >= (size_t)got - 1U)
            return -1;
        target = (char *)buf + 1U + first + 1U;
        if (target >= (char *)buf + got || !memchr(target, '\0',
            (size_t)((char *)buf + got - target)))
            return -1;
        if (!user_match(target, user))
            return send_code(fd, PHONE_REPLYNOUSER);
    }
    if (send_code(fd, PHONE_REPLYOK))
        return -1;

    got = recv(fd, buf, sizeof(buf), 0);
    if (got < 3 || buf[0] != PHONE_DIAL)
        return -1;
    return send_code(fd, PHONE_REPLYOK);
}

static int selftest(void)
{
    if (!user_match("DN70::ALICE", "alice") ||
        user_match("DN70::BOB", "alice") ||
        user_match("ALICE", "alice"))
        return 1;
    puts("dnphoned selftest passed");
    return 0;
}

int main(int argc, char **argv)
{
    const char *user = NULL;
    int once = 0;
    int listener;
    int i;

    if (argc == 2 && !strcmp(argv[1], "--selftest"))
        return selftest();
    for (i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--once"))
            once = 1;
        else if (!strcmp(argv[i], "--user") && i + 1 < argc)
            user = argv[++i];
        else {
            fprintf(stderr, "usage: %s --user USER [--once] | --selftest\n",
                    argv[0]);
            return 2;
        }
    }
    if (!user || !*user || strlen(user) > 40U)
        return 2;

    setvbuf(stdout, NULL, _IONBF, 0);
    listener = make_listener();
    if (listener < 0) {
        perror("dnphoned: listen");
        return 1;
    }
    printf("dnphoned: ready object=%u user=%s\n", PHONE_OBJECT, user);
    for (;;) {
        int fd = accept(listener, NULL, NULL);
        int rc;

        if (fd < 0) {
            if (errno == EINTR)
                continue;
            perror("dnphoned: accept");
            close(listener);
            return 1;
        }
        rc = serve(fd, user);
        close(fd);
        if (rc) {
            perror("dnphoned: session");
            close(listener);
            return 1;
        }
        if (once)
            break;
    }
    close(listener);
    return 0;
}
