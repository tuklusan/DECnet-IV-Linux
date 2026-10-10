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

#include <ctype.h>
#include <errno.h>
#include <linux/dn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/wait.h>
#include <signal.h>
#include <sys/time.h>
#include <unistd.h>

#include "../common/record_io.h"

#define PHONE_OBJECT 29U
#define PHONE_REPLYOK 0x01U
#define PHONE_REPLYNOUSER 0x06U
#define PHONE_CONNECT 0x07U
#define PHONE_DIAL 0x08U
#define PHONE_HANGUP 0x09U
#define PHONE_GOODBYE 0x0dU
#define PHONE_DATA 0x0eU
#define PHONE_DIRECTORY 0x0fU
#define PHONE_HOLD 0x12U
#define PHONE_UNHOLD 0x13U
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

static size_t bounded_strlen(const char *text, size_t cap)
{
    size_t n = 0U;

    while (n < cap && text[n])
        n++;
    return n;
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
    return dniv_send_record(fd, &code, 1U, 0);
}

static int serve(int fd, const char *user)
{
    struct timeval timeout = { .tv_sec = 30, .tv_usec = 0 };
    unsigned char buf[2048];
    ssize_t got;

    if (setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)) ||
        setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout)))
        return -1;

    got = dniv_recv_record(fd, buf, sizeof(buf) - 1U, 0);
    if (got == 1 && buf[0] == PHONE_DIRECTORY) {
        char line[192];
        int len = snprintf(line, sizeof(line),
                           "%-15s %-15s %-15s Available",
                           user, user, "LOCAL");

        if (len < 0 || (size_t)len >= sizeof(line))
            return -1;
        return dniv_send_record(fd, line, (size_t)len, 0);
    }
    if (got < 4 || buf[0] != PHONE_CONNECT)
        return -1;
    buf[got] = 0;
    {
        size_t first = bounded_strlen((char *)buf + 1, (size_t)got - 1U);
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

    got = dniv_recv_record(fd, buf, sizeof(buf), 0);
    if (got < 3 || buf[0] != PHONE_DIAL)
        return -1;
    if (send_code(fd, PHONE_REPLYOK))
        return -1;

    {
        for (;;) {
            size_t source_len;

            got = dniv_recv_record(fd, buf, sizeof(buf) - 1U, 0);
            if (!got)
                return -1;
            if (got < 0)
                return -1;
            if (got < 2)
                return -1;
            buf[got] = 0;
            source_len = bounded_strlen((char *)buf + 1U,
                                        (size_t)got - 1U);
            if (source_len >= (size_t)got - 1U)
                return -1;

            switch (buf[0]) {
            case PHONE_DATA:
                printf("dnphoned: data from=%s text=%s\n",
                       buf + 1U, buf + 1U + source_len + 1U);
                break;
            case PHONE_HOLD:
                printf("dnphoned: hold from=%s\n", buf + 1U);
                break;
            case PHONE_UNHOLD:
                printf("dnphoned: unhold from=%s\n", buf + 1U);
                break;
            case PHONE_HANGUP:
                printf("dnphoned: hangup from=%s\n", buf + 1U);
                break;
            case PHONE_GOODBYE:
                printf("dnphoned: goodbye from=%s\n", buf + 1U);
                return 0;
            default:
                return -1;
            }
        }
    }
}

/* A valid phone client may transmit 1800 text bytes in one DATA record.
 * Rejecting this frame at the receiver silently breaks local interoperability. */
static int selftest_large_data(void)
{
    const unsigned char connect_msg[] = {
        PHONE_CONNECT, 'N', 0U, '1', '.', '2', '3', ':', ':',
        'A', 'L', 'I', 'C', 'E', 0U
    };
    const unsigned char dial_msg[] = { PHONE_DIAL, 'N', 0U, 1U };
    const unsigned char goodbye[] = { PHONE_GOODBYE, 'N', 0U };
    unsigned char data[1803];
    unsigned char reply;
    struct timeval timeout = { .tv_sec = 5, .tv_usec = 0 };
    int fds[2], status;
    pid_t child;

    if (socketpair(AF_UNIX, SOCK_SEQPACKET, 0, fds))
        return -1;
    if (setsockopt(fds[0], SOL_SOCKET, SO_RCVTIMEO,
                   &timeout, sizeof(timeout))) {
        close(fds[0]);
        close(fds[1]);
        return -1;
    }
    child = fork();
    if (child < 0) {
        close(fds[0]);
        close(fds[1]);
        return -1;
    }
    if (!child) {
        int result;

        close(fds[0]);
        result = serve(fds[1], "ALICE");
        close(fds[1]);
        _exit(result ? 1 : 0);
    }
    close(fds[1]);
    memset(data, 'x', sizeof(data));
    data[0] = PHONE_DATA;
    data[1] = 'N';
    data[2] = 0U;
    if (dniv_send_record(fds[0], connect_msg, sizeof(connect_msg), 0) ||
        dniv_recv_record(fds[0], &reply, 1U, 0) != 1 ||
        reply != PHONE_REPLYOK ||
        dniv_send_record(fds[0], dial_msg, sizeof(dial_msg), 0) ||
        dniv_recv_record(fds[0], &reply, 1U, 0) != 1 ||
        reply != PHONE_REPLYOK ||
        dniv_send_record(fds[0], data, sizeof(data), 0) ||
        dniv_send_record(fds[0], goodbye, sizeof(goodbye), 0)) {
        close(fds[0]);
        (void)kill(child, SIGKILL);
        (void)waitpid(child, &status, 0);
        return -1;
    }
    close(fds[0]);
    if (waitpid(child, &status, 0) != child ||
        !WIFEXITED(status) || WEXITSTATUS(status))
        return -1;
    return 0;
}

/* EOF is not a PHONE_GOODBYE, even after previously accepted DATA. */
static int selftest_termination(int send_data, int send_goodbye, int success)
{
    const unsigned char connect_msg[] = {
        PHONE_CONNECT, 'N', 0U, '1', '.', '2', '3', ':', ':',
        'A', 'L', 'I', 'C', 'E', 0U
    };
    const unsigned char dial_msg[] = { PHONE_DIAL, 'N', 0U, 1U };
    const unsigned char data[] = { PHONE_DATA, 'N', 0U, 'h', 'i', 0U };
    const unsigned char goodbye[] = { PHONE_GOODBYE, 'N', 0U };
    struct timeval timeout = { .tv_sec = 5, .tv_usec = 0 };
    unsigned char reply;
    int fds[2], status;
    pid_t child;

    if (socketpair(AF_UNIX, SOCK_SEQPACKET, 0, fds))
        return -1;
    if (setsockopt(fds[0], SOL_SOCKET, SO_RCVTIMEO,
                   &timeout, sizeof(timeout))) {
        close(fds[0]);
        close(fds[1]);
        return -1;
    }
    child = fork();
    if (child < 0) {
        close(fds[0]);
        close(fds[1]);
        return -1;
    }
    if (!child) {
        int result;

        close(fds[0]);
        result = serve(fds[1], "ALICE");
        close(fds[1]);
        _exit(result ? 1 : 0);
    }
    close(fds[1]);
    if (dniv_send_record(fds[0], connect_msg, sizeof(connect_msg), 0) ||
        dniv_recv_record(fds[0], &reply, 1U, 0) != 1 ||
        reply != PHONE_REPLYOK ||
        dniv_send_record(fds[0], dial_msg, sizeof(dial_msg), 0) ||
        dniv_recv_record(fds[0], &reply, 1U, 0) != 1 ||
        reply != PHONE_REPLYOK ||
        (send_data && dniv_send_record(fds[0], data, sizeof(data), 0)) ||
        (send_goodbye && dniv_send_record(fds[0], goodbye,
                                         sizeof(goodbye), 0))) {
        close(fds[0]);
        (void)kill(child, SIGKILL);
        (void)waitpid(child, &status, 0);
        return -1;
    }
    close(fds[0]);
    if (waitpid(child, &status, 0) != child ||
        !WIFEXITED(status) || WEXITSTATUS(status) != (success ? 0 : 1))
        return -1;
    return 0;
}

static int selftest(void)
{
    if (selftest_large_data() ||
        selftest_termination(0, 1, 1) ||
        selftest_termination(1, 0, 0) ||
        selftest_termination(0, 0, 0) ||
        !user_match("DN70::ALICE", "alice") ||
        user_match("DN70::BOB", "alice") ||
        user_match("ALICE", "alice"))
        return 1;
    puts("dnphoned selftest passed");
    return 0;
}

int main(int argc, char **argv)
{
    const char *user = NULL;
    int sessions = 0;
    int failed = 0;
    int listener;
    int i;

    if (argc == 2 && !strcmp(argv[1], "--selftest"))
        return selftest();
    for (i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--once"))
            sessions = 1;
        else if (!strcmp(argv[i], "--sessions") && i + 1 < argc) {
            char *end;
            long value;

            errno = 0;
            value = strtol(argv[++i], &end, 10);
            if (errno || !*argv[i] || *end || value < 1 || value > 64)
                return 2;
            sessions = (int)value;
        } else if (!strcmp(argv[i], "--user") && i + 1 < argc)
            user = argv[++i];
        else {
            fprintf(stderr,
                    "usage: %s --user USER [--once | --sessions N] | --selftest\n",
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
            failed = 1;
            if (sessions > 0 && --sessions == 0)
                break;
            continue;
        }
        if (sessions > 0 && --sessions == 0)
            break;
    }
    close(listener);
    return failed ? 1 : 0;
}
