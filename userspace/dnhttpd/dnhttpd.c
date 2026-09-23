// ============================================================================
// Copyright (c) 2026 Supratim Sanyal of SANYALnet Labs.
// Proprietary rights reserved except as expressly licensed herein.
//
// DECnet-IV-Linux
// This file is governed by the SANYALnet Labs Non-Commercial License in the
// root LICENSE file.
// ============================================================================

#include <errno.h>
#include <linux/dn.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>

#define DNHTTP_OBJECT "HTTP"
#define DNHTTP_BACKLOG 8

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
    struct sockaddr_dn local;
    int fd = socket(AF_DECnet, SOCK_SEQPACKET, DNPROTO_NSP);
    size_t n = strlen(DNHTTP_OBJECT);

    if (fd < 0)
        return -1;
    memset(&local, 0, sizeof(local));
    local.sdn_family = AF_DECnet;
    local.sdn_objnamel = cpu_to_le16_u((uint16_t)n);
    memcpy(local.sdn_objname, DNHTTP_OBJECT, n);
    if (bind(fd, (struct sockaddr *)&local, sizeof(local)) ||
        listen(fd, DNHTTP_BACKLOG)) {
        close(fd);
        return -1;
    }
    return fd;
}

static int safe_path(const char *uri, char *name, size_t cap)
{
    size_t n;

    if (!strcmp(uri, "/")) {
        uri = "/index.html";
    }
    if (uri[0] != '/' || strstr(uri, "..") || strchr(uri, '\\') ||
        strchr(uri, ':') || strchr(uri, '?') || strchr(uri, '#'))
        return -1;
    uri++;
    n = strlen(uri);
    if (!n || n >= cap || strchr(uri, '/'))
        return -1;
    memcpy(name, uri, n + 1U);
    return 0;
}

static int serve(int fd, const char *root)
{
    struct timeval timeout = { .tv_sec = 30, .tv_usec = 0 };
    unsigned char request[2048];
    char method[16], uri[512], version[32], path[1024], name[512];
    unsigned char body[8192];
    char header[512];
    FILE *in;
    ssize_t got;
    size_t n;
    int code = 200;
    const char *reason = "OK";

    if (setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)) ||
        setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout)))
        return -1;
    got = recv(fd, request, sizeof(request) - 1U, 0);
    if (got <= 0)
        return -1;
    request[got] = 0;
    if (sscanf((char *)request, "%15s %511s %31s", method, uri, version) != 3 ||
        strcmp(method, "GET") || strncmp(version, "HTTP/", 5) ||
        safe_path(uri, name, sizeof(name))) {
        code = 400;
        reason = "Bad Request";
        n = (size_t)snprintf((char *)body, sizeof(body), "Bad Request\n");
    } else {
        if (snprintf(path, sizeof(path), "%s/%s", root, name) >=
            (int)sizeof(path))
            return -1;
        in = fopen(path, "rb");
        if (!in) {
            code = 404;
            reason = "Not Found";
            n = (size_t)snprintf((char *)body, sizeof(body), "Not Found\n");
        } else {
            n = fread(body, 1, sizeof(body), in);
            if (ferror(in) || !feof(in)) {
                fclose(in);
                return -1;
            }
            fclose(in);
        }
    }
    {
        int h = snprintf(header, sizeof(header),
                         "HTTP/1.0 %d %s\r\n"
                         "Content-Length: %zu\r\n"
                         "Content-Type: text/html\r\n"
                         "Connection: close\r\n\r\n",
                         code, reason, n);
        if (h < 0 || (size_t)h >= sizeof(header))
            return -1;
        if (send(fd, header, (size_t)h, MSG_EOR | MSG_NOSIGNAL) != h)
            return -1;
    }
    if (n && send(fd, body, n, MSG_EOR | MSG_NOSIGNAL) != (ssize_t)n)
        return -1;
    return 0;
}

static int selftest(void)
{
    char name[64];

    if (safe_path("/", name, sizeof(name)) || strcmp(name, "index.html") ||
        safe_path("/hello.html", name, sizeof(name)) ||
        strcmp(name, "hello.html") ||
        !safe_path("/../secret", name, sizeof(name)) ||
        !safe_path("/sub/file", name, sizeof(name)))
        return 1;
    puts("dnhttpd selftest passed");
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
        perror("dnhttpd: listen");
        return 1;
    }
    printf("dnhttpd: ready object=%s root=%s\n", DNHTTP_OBJECT, root);
    for (;;) {
        int fd = accept(listener, NULL, NULL);
        int rc;

        if (fd < 0) {
            if (errno == EINTR)
                continue;
            perror("dnhttpd: accept");
            close(listener);
            return 1;
        }
        rc = serve(fd, root);
        close(fd);
        if (rc) {
            perror("dnhttpd: session");
            close(listener);
            return 1;
        }
        if (once)
            break;
    }
    close(listener);
    return 0;
}
