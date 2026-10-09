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
#include <linux/dn.h>
#include <stdint.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <sys/time.h>
#include <unistd.h>

#include "../common/record_io.h"

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

static FILE *open_root_file(const char *root, const char *name)
{
    struct stat st;
    FILE *stream;
    int rootfd;
    int fd;

    rootfd = open(root, O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    if (rootfd < 0)
        return NULL;
    fd = openat(rootfd, name,
                O_RDONLY | O_NOFOLLOW | O_CLOEXEC | O_NONBLOCK);
    close(rootfd);
    if (fd < 0)
        return NULL;
    if (fstat(fd, &st)) {
        int saved = errno;

        close(fd);
        errno = saved;
        return NULL;
    }
    if (!S_ISREG(st.st_mode) || st.st_nlink != 1) {
        close(fd);
        errno = EACCES;
        return NULL;
    }
    stream = fdopen(fd, "rb");
    if (!stream)
        close(fd);
    return stream;
}

static int read_bounded_file(FILE *in, unsigned char *body,
                             size_t cap, size_t *len)
{
    size_t n;

    if (!in || !body || !cap || !len)
        return -1;
    n = fread(body, 1, cap, in);
    if (ferror(in))
        return -1;
    if (n == cap) {
        int extra = fgetc(in);

        if (extra != EOF || ferror(in))
            return -1;
    } else if (!feof(in)) {
        return -1;
    }
    *len = n;
    return 0;
}

/* Only the first HTTP request line determines the method and target.
 * A fourth token, a malformed protocol version, or a hidden embedded NUL
 * must never be accepted as a valid request prefix.
 */
static int parse_request_line(const unsigned char *request, size_t length,
                              char *name, size_t cap)
{
    const unsigned char *newline = memchr(request, '\n', length);
    size_t line_len = newline ? (size_t)(newline - request) : length;
    char line[1024], method[16], uri[512], version[32], extra;

    if (memchr(request, '\0', length))
        return -1;
    if (newline && line_len && request[line_len - 1U] == '\r')
        line_len--;
    if (!line_len || line_len >= sizeof(line))
        return -1;
    memcpy(line, request, line_len);
    line[line_len] = '\0';
    if (sscanf(line, "%15s %511s %31s %c",
               method, uri, version, &extra) != 3 ||
        strcmp(method, "GET") ||
        (strcmp(version, "HTTP/1.0") && strcmp(version, "HTTP/1.1")) ||
        safe_path(uri, name, cap))
        return -1;
    return 0;
}

static int serve(int fd, const char *root)
{
    struct timeval timeout = { .tv_sec = 30, .tv_usec = 0 };
    unsigned char request[2048];
    char name[512];
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
    got = dniv_recv_record(fd, request, sizeof(request) - 1U, 0);
    if (got <= 0)
        return -1;
    if (parse_request_line(request, (size_t)got, name, sizeof(name))) {
        code = 400;
        reason = "Bad Request";
        n = (size_t)snprintf((char *)body, sizeof(body), "Bad Request\n");
    } else {
        in = open_root_file(root, name);
        if (!in) {
            code = 404;
            reason = "Not Found";
            n = (size_t)snprintf((char *)body, sizeof(body), "Not Found\n");
        } else {
            if (read_bounded_file(in, body, sizeof(body), &n)) {
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
        if (dniv_send_record(fd, header, (size_t)h, 0))
            return -1;
    }
    if (n && dniv_send_record(fd, body, n, 0))
        return -1;
    return 0;
}

/* A NUL in a record is not a terminator for HTTP. Reject the complete
 * record, including any hidden trailing bytes, rather than serving a valid
 * prefix as an authorized request.
 */
static int selftest_bad_request(const char *root, const unsigned char *bad,
                                size_t bad_len)
{
    unsigned char reply[256];
    struct timeval timeout = { .tv_sec = 5, .tv_usec = 0 };
    int pair[2] = { -1, -1 };
    pid_t child;
    int status;
    int rc = -1;
    ssize_t got;

    if (socketpair(AF_UNIX, SOCK_SEQPACKET, 0, pair))
        return -1;
    if (setsockopt(pair[0], SOL_SOCKET, SO_RCVTIMEO,
                   &timeout, sizeof(timeout))) {
        close(pair[0]);
        close(pair[1]);
        return -1;
    }
    child = fork();
    if (child < 0) {
        close(pair[0]);
        close(pair[1]);
        return -1;
    }
    if (!child) {
        int result;

        close(pair[0]);
        result = serve(pair[1], root);
        close(pair[1]);
        _exit(result ? 1 : 0);
    }
    close(pair[1]);
    if (dniv_send_record(pair[0], bad, bad_len, 0))
        goto finish;
    got = dniv_recv_record(pair[0], reply, sizeof(reply) - 1U, 0);
    if (got < 0)
        goto finish;
    reply[got] = 0;
    if (strncmp((char *)reply, "HTTP/1.0 400 Bad Request\r\n", 26U))
        goto finish;
    got = dniv_recv_record(pair[0], reply, sizeof(reply), 0);
    if (got != 12 || memcmp(reply, "Bad Request\n", 12U))
        goto finish;
    rc = 0;
finish:
    close(pair[0]);
    if (rc)
        (void)kill(child, SIGKILL);
    if (waitpid(child, &status, 0) != child ||
        !WIFEXITED(status) || WEXITSTATUS(status))
        return -1;
    return rc;
}

static int selftest(void)
{
    char directory[] = "/tmp/dnhttpd-selftest.XXXXXX";
    char victim[] = "/tmp/dnhttpd-victim.XXXXXX";
    char good[256];
    char link[256];
    char hardlink_path[256];
    char fifo_path[256];
    char name[64];
    unsigned char boundary[8192];
    size_t boundary_len = 0U;
    FILE *file = NULL;
    int victim_fd = -1;
    int good_fd = -1;
    int rc = 1;

    if (safe_path("/", name, sizeof(name)) || strcmp(name, "index.html") ||
        safe_path("/hello.html", name, sizeof(name)) ||
        strcmp(name, "hello.html") ||
        !safe_path("/../secret", name, sizeof(name)) ||
        !safe_path("/sub/file", name, sizeof(name)))
        return 1;
    if (!mkdtemp(directory))
        return 1;
    victim_fd = mkstemp(victim);
    if (victim_fd < 0)
        goto out;
    close(victim_fd);
    victim_fd = -1;
    if (snprintf(good, sizeof(good), "%s/index.html", directory) >=
            (int)sizeof(good) ||
        snprintf(link, sizeof(link), "%s/escape.html", directory) >=
            (int)sizeof(link) ||
        snprintf(hardlink_path, sizeof(hardlink_path), "%s/hard.html", directory) >=
            (int)sizeof(hardlink_path) ||
        snprintf(fifo_path, sizeof(fifo_path), "%s/pipe.html", directory) >=
            (int)sizeof(fifo_path))
        goto out;
    file = fopen(good, "wb");
    if (!file)
        goto out;
    if (fputs("ok\n", file) == EOF)
        goto out;
    if (fclose(file)) {
        file = NULL;
        goto out;
    }
    file = NULL;
    {
        static const unsigned char hidden_nul[] = {
            'G', 'E', 'T', ' ', '/', ' ', 'H', 'T', 'T', 'P', '/',
            '1', '.', '0', '\0', 'H', 'I', 'D', 'D', 'E', 'N'
        };
        static const unsigned char invalid_version[] =
            "GET / HTTP/garbage\r\n";
        static const unsigned char extra_token[] =
            "GET / HTTP/1.0 MORE\r\n";

        if (selftest_bad_request(directory, hidden_nul,
                                 sizeof(hidden_nul)) ||
            selftest_bad_request(directory, invalid_version,
                                 sizeof(invalid_version) - 1U) ||
            selftest_bad_request(directory, extra_token,
                                 sizeof(extra_token) - 1U))
            goto out;
    }
    if (symlink(victim, link) ||
        linkat(AT_FDCWD, victim, AT_FDCWD, hardlink_path, 0) ||
        mkfifo(fifo_path, 0600))
        goto out;
    file = open_root_file(directory, "index.html");
    if (!file)
        goto out;
    fclose(file);
    file = NULL;
    file = open_root_file(directory, "escape.html");
    if (file)
        goto out;
    file = open_root_file(directory, "hard.html");
    if (file)
        goto out;
    file = open_root_file(directory, "pipe.html");
    if (file)
        goto out;
    good_fd = open(good, O_WRONLY | O_CLOEXEC);
    if (good_fd < 0 || ftruncate(good_fd, (off_t)sizeof(boundary)))
        goto out;
    close(good_fd);
    good_fd = -1;
    file = open_root_file(directory, "index.html");
    if (!file || read_bounded_file(file, boundary, sizeof(boundary),
                                   &boundary_len) ||
        boundary_len != sizeof(boundary))
        goto out;
    fclose(file);
    file = NULL;
    good_fd = open(good, O_WRONLY | O_CLOEXEC);
    if (good_fd < 0 ||
        ftruncate(good_fd, (off_t)sizeof(boundary) + 1))
        goto out;
    close(good_fd);
    good_fd = -1;
    file = open_root_file(directory, "index.html");
    if (!file || !read_bounded_file(file, boundary, sizeof(boundary),
                                    &boundary_len))
        goto out;
    fclose(file);
    file = NULL;
    rc = 0;

out:
    if (file)
        fclose(file);
    if (victim_fd >= 0)
        close(victim_fd);
    if (good_fd >= 0)
        close(good_fd);
    unlink(fifo_path);
    unlink(hardlink_path);
    unlink(link);
    unlink(good);
    unlink(victim);
    rmdir(directory);
    if (rc)
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
            if (once) {
                close(listener);
                return 1;
            }
            continue;
        }
        if (once)
            break;
    }
    close(listener);
    return 0;
}
