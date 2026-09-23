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
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>

#define DAP_FAL_OBJECT 17U
#define DAP_CONFIG 1U
#define DAP_ATTRIBUTES 2U
#define DAP_ACCESS 3U
#define DAP_CONTROL 4U
#define DAP_ACK 6U
#define DAP_ACCESS_COMPLETE 7U
#define DAP_DATA 8U
#define DAP_STATUS 9U
#define DAP_STATUS_EOF 0x4027U
#define DAP_RFM_FIX 1U
#define DAP_ACCESS_OPEN 1U
#define DAP_ACCESS_CREATE 2U
#define DAP_CONTROL_GET 1U
#define DAP_CONTROL_CONNECT 2U
#define DAP_CONTROL_PUT 4U
#define DAP_ACCOMP_CLOSE 1U
#define DAP_ACCOMP_RESPONSE 2U
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

static int send_record(int fd, const unsigned char *buf, size_t len)
{
    return send(fd, buf, len, MSG_EOR | MSG_NOSIGNAL) == (ssize_t)len ? 0 : -1;
}

static int safe_filespec(const unsigned char *text, size_t len,
                         char *out, size_t cap)
{
    size_t i;

    if (!len || len >= cap)
        return -1;
    for (i = 0; i < len; i++) {
        unsigned char c = text[i];

        if (c == '/' || c == '\\' || c == ':' || c == '[' || c == ']' ||
            c == ';' || c == '*' || c == '?' || c < 0x20U)
            return -1;
    }
    if ((len == 1U && text[0] == '.') ||
        (len == 2U && text[0] == '.' && text[1] == '.'))
        return -1;
    memcpy(out, text, len);
    out[len] = '\0';
    return 0;
}

static int make_path(const char *root, const unsigned char *request,
                     size_t len, unsigned char function,
                     char *path, size_t path_cap)
{
    char filespec[256];
    size_t n;

    if (len < 5U || request[0] != DAP_ACCESS || request[2] != function)
        return -1;
    n = request[4];
    if (len != n + 5U ||
        safe_filespec(request + 5U, n, filespec, sizeof(filespec)))
        return -1;
    if (snprintf(path, path_cap, "%s/%s", root, filespec) >= (int)path_cap)
        return -1;
    return 0;
}

static int serve_get(int fd, const char *root,
                     const unsigned char *access, size_t access_len)
{
    unsigned char request[2048];
    unsigned char reply[2048];
    char path[1024];
    FILE *in = NULL;
    ssize_t got;

    if (make_path(root, access, access_len, DAP_ACCESS_OPEN,
                  path, sizeof(path)))
        return -1;
    in = fopen(path, "rb");
    if (!in)
        return -1;

    {
        const unsigned char attributes[] = {
            DAP_ATTRIBUTES, 0U, 0x04U, DAP_RFM_FIX
        };
        const unsigned char ack[] = { DAP_ACK, 0U };

        if (send_record(fd, attributes, sizeof(attributes)) ||
            send_record(fd, ack, sizeof(ack)))
            goto fail;
    }

    got = recv(fd, request, sizeof(request), 0);
    if (got != 3 || request[0] != DAP_CONTROL || request[2] != DAP_CONTROL_CONNECT)
        goto fail;
    {
        const unsigned char ack[] = { DAP_ACK, 0U };
        if (send_record(fd, ack, sizeof(ack)))
            goto fail;
    }

    got = recv(fd, request, sizeof(request), 0);
    if (got != 3 || request[0] != DAP_CONTROL || request[2] != DAP_CONTROL_GET)
        goto fail;

    for (;;) {
        size_t count = fread(reply + 3U, 1, sizeof(reply) - 3U, in);

        if (count) {
            reply[0] = DAP_DATA;
            reply[1] = 0U;
            reply[2] = 0U;
            if (send_record(fd, reply, count + 3U))
                goto fail;
        }
        if (count < sizeof(reply) - 3U) {
            if (ferror(in))
                goto fail;
            break;
        }
    }
    fclose(in);
    in = NULL;

    {
        const unsigned char eof[] = {
            DAP_STATUS, 0U,
            (unsigned char)(DAP_STATUS_EOF & 0xffU),
            (unsigned char)(DAP_STATUS_EOF >> 8)
        };
        if (send_record(fd, eof, sizeof(eof)))
            return -1;
    }
    got = recv(fd, request, sizeof(request), 0);
    if (got != 3 || request[0] != DAP_ACCESS_COMPLETE || request[2] != DAP_ACCOMP_CLOSE)
        return -1;
    {
        const unsigned char complete[] = {
            DAP_ACCESS_COMPLETE, 0U, DAP_ACCOMP_RESPONSE
        };
        return send_record(fd, complete, sizeof(complete));
    }

fail:
    if (in)
        fclose(in);
    return -1;
}

static int serve_create(int fd, const char *root,
                        const unsigned char *access, size_t access_len)
{
    unsigned char request[2048];
    char path[1024];
    FILE *out = NULL;
    ssize_t got;

    if (make_path(root, access, access_len, DAP_ACCESS_CREATE,
                  path, sizeof(path)))
        return -1;
    out = fopen(path, "wb");
    if (!out)
        return -1;

    {
        const unsigned char attributes[] = {
            DAP_ATTRIBUTES, 0U, 0x04U, DAP_RFM_FIX
        };
        const unsigned char ack[] = { DAP_ACK, 0U };

        if (send_record(fd, attributes, sizeof(attributes)) ||
            send_record(fd, ack, sizeof(ack)))
            goto fail;
    }

    got = recv(fd, request, sizeof(request), 0);
    if (got != 3 || request[0] != DAP_CONTROL ||
        request[2] != DAP_CONTROL_CONNECT)
        goto fail;
    {
        const unsigned char ack[] = { DAP_ACK, 0U };
        if (send_record(fd, ack, sizeof(ack)))
            goto fail;
    }

    got = recv(fd, request, sizeof(request), 0);
    if (got != 3 || request[0] != DAP_CONTROL ||
        request[2] != DAP_CONTROL_PUT)
        goto fail;

    for (;;) {
        size_t off;

        got = recv(fd, request, sizeof(request), 0);
        if (got < 2)
            goto fail;
        if (request[0] == DAP_DATA) {
            if (got < 3)
                goto fail;
            off = 3U + request[2];
            if (off > (size_t)got)
                goto fail;
            if ((size_t)got > off &&
                fwrite(request + off, 1, (size_t)got - off, out) !=
                    (size_t)got - off)
                goto fail;
            continue;
        }
        if (request[0] == DAP_ACCESS_COMPLETE &&
            got == 3 && request[2] == DAP_ACCOMP_CLOSE)
            break;
        goto fail;
    }
    if (fclose(out))
        return -1;
    out = NULL;
    {
        const unsigned char complete[] = {
            DAP_ACCESS_COMPLETE, 0U, DAP_ACCOMP_RESPONSE
        };
        return send_record(fd, complete, sizeof(complete));
    }

fail:
    if (out)
        fclose(out);
    unlink(path);
    return -1;
}

static int serve_session(int fd, const char *root)
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
    if (!reply_len || send_record(fd, reply, reply_len))
        return -1;
    if (!root)
        return 0;

    got = recv(fd, request, sizeof(request), 0);
    if (got < 0)
        return -1;
    if (got >= 3 && request[0] == DAP_ATTRIBUTES) {
        got = recv(fd, request, sizeof(request), 0);
        if (got < 0)
            return -1;
    }
    if (got < 5 || request[0] != DAP_ACCESS)
        return -1;
    if (request[2] == DAP_ACCESS_OPEN)
        return serve_get(fd, root, request, (size_t)got);
    if (request[2] == DAP_ACCESS_CREATE)
        return serve_create(fd, root, request, (size_t)got);
    return -1;
}

static int selftest(void)
{
    unsigned char config[16];
    char name[32];

    if (make_config(config, sizeof(config)) != 12U ||
        validate_config(config, 12U) ||
        config[3] != 4U || config[4] != 128U || config[5] != 128U ||
        config[6] != 4U || config[7] != 1U)
        return 1;
    config[0] = 2U;
    if (!validate_config(config, 12U) ||
        safe_filespec((const unsigned char *)"SERVER.TXT", 10U,
                      name, sizeof(name)) || strcmp(name, "SERVER.TXT") ||
        !safe_filespec((const unsigned char *)"../BAD", 6U,
                       name, sizeof(name)))
        return 1;
    puts("dnfald selftest passed");
    return 0;
}

int main(int argc, char **argv)
{
    const char *root = NULL;
    int sessions = 0;
    int served = 0;
    int listener;
    int i;

    if (argc == 2 && !strcmp(argv[1], "--selftest"))
        return selftest();
    for (i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--once")) {
            sessions = 1;
        } else if (!strcmp(argv[i], "--sessions") && i + 1 < argc) {
            char *end = NULL;
            long value;

            errno = 0;
            value = strtol(argv[++i], &end, 10);
            if (errno || end == argv[i] || *end || value < 1 || value > 32) {
                fprintf(stderr, "dnfald: invalid session count\n");
                return 2;
            }
            sessions = (int)value;
        } else if (!strcmp(argv[i], "--root") && i + 1 < argc) {
            root = argv[++i];
        } else {
            fprintf(stderr,
                    "usage: %s [--once|--sessions N] [--root DIR] | --selftest\n",
                    argv[0]);
            return 2;
        }
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
        rc = serve_session(fd, root);
        close(fd);
        if (rc) {
            perror("dnfald: session");
            close(listener);
            return 1;
        }
        served++;
        if (sessions && served >= sessions)
            break;
    }
    close(listener);
    return 0;
}
