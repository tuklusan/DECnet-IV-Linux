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

#define MAIL_OBJECT 27U
#define MAIL_BACKLOG 8

static int make_listener(void)
{
    struct sockaddr_dn local;
    int fd = socket(AF_DECnet, SOCK_SEQPACKET, DNPROTO_NSP);

    if (fd < 0)
        return -1;
    memset(&local, 0, sizeof(local));
    local.sdn_family = AF_DECnet;
    local.sdn_objnum = MAIL_OBJECT;
    if (bind(fd, (struct sockaddr *)&local, sizeof(local)) ||
        listen(fd, MAIL_BACKLOG)) {
        close(fd);
        return -1;
    }
    return fd;
}

static int recv_field(int fd, char *buf, size_t cap, int allow_empty)
{
    ssize_t got = recv(fd, buf, cap - 1U, 0);
    size_t i;

    if (got < 0 || (got == 0 && !allow_empty))
        return -1;
    for (i = 0; i < (size_t)got; i++) {
        if (buf[i] == '\0' || buf[i] == '\r' || buf[i] == '\n')
            return -1;
    }
    buf[got] = '\0';
    return (int)got;
}

static int send_ack(int fd)
{
    const unsigned char ack[4] = { 1U, 0U, 0U, 0U };

    return send(fd, ack, sizeof(ack), MSG_EOR | MSG_NOSIGNAL) ==
        (ssize_t)sizeof(ack) ? 0 : -1;
}

static int serve(int fd, const char *root)
{
    struct timeval timeout = { .tv_sec = 30, .tv_usec = 0 };
    unsigned char body[4096];
    char sender[256], recipient[256], full_user[256], subject[256], path[1024];
    FILE *out = NULL;
    ssize_t got;

    if (setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)) ||
        setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout)))
        return -1;
    if (recv_field(fd, sender, sizeof(sender), 0) < 0 ||
        recv_field(fd, recipient, sizeof(recipient), 0) < 0 ||
        send_ack(fd))
        return -1;

    got = recv(fd, body, sizeof(body), 0);
    if (got != 1 || body[0] != 0U)
        return -1;
    if (recv_field(fd, full_user, sizeof(full_user), 1) < 0 ||
        recv_field(fd, subject, sizeof(subject), 1) < 0)
        return -1;

    if (snprintf(path, sizeof(path), "%s/mailbox.log", root) >= (int)sizeof(path))
        return -1;
    out = fopen(path, "ab");
    if (!out)
        return -1;
    if (fprintf(out, "From: %s\nTo: %s\nX-VMSmail: %s\nSubject: %s\n\n",
                sender, recipient, full_user, subject) < 0)
        goto fail;

    for (;;) {
        got = recv(fd, body, sizeof(body), 0);
        if (got < 0)
            goto fail;
        if (got == 1 && body[0] == 0U)
            break;
        if (got == 0)
            goto fail;
        if (fwrite(body, 1, (size_t)got, out) != (size_t)got ||
            fputc('\n', out) == EOF)
            goto fail;
    }
    if (fputs("--\n", out) == EOF || fclose(out))
        return -1;
    out = NULL;
    return send_ack(fd);

fail:
    if (out)
        fclose(out);
    return -1;
}

static int selftest(void)
{
    if (MAIL_OBJECT != 27U)
        return 1;
    puts("dnmaild selftest passed");
    return 0;
}

int main(int argc, char **argv)
{
    const char *root = ".";
    int once = 0;
    int listener;
    int i;

    if (argc == 2 && !strcmp(argv[1], "--selftest"))
        return selftest();
    for (i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--once"))
            once = 1;
        else if (!strcmp(argv[i], "--root") && i + 1 < argc)
            root = argv[++i];
        else {
            fprintf(stderr, "usage: %s [--once] [--root DIR] | --selftest\n",
                    argv[0]);
            return 2;
        }
    }

    setvbuf(stdout, NULL, _IONBF, 0);
    listener = make_listener();
    if (listener < 0) {
        perror("dnmaild: listen");
        return 1;
    }
    printf("dnmaild: ready object=%u root=%s\n", MAIL_OBJECT, root);
    for (;;) {
        int fd = accept(listener, NULL, NULL);
        int rc;

        if (fd < 0) {
            if (errno == EINTR)
                continue;
            perror("dnmaild: accept");
            close(listener);
            return 1;
        }
        rc = serve(fd, root);
        close(fd);
        if (rc) {
            perror("dnmaild: session");
            close(listener);
            return 1;
        }
        if (once)
            break;
    }
    close(listener);
    return 0;
}
