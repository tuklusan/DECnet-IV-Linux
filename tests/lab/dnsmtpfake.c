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
#include <netinet/in.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>

static int write_all(int fd, const void *data, size_t len)
{
    const unsigned char *p = data;

    while (len) {
        ssize_t done = write(fd, p, len);
        if (done < 0) {
            if (errno == EINTR)
                continue;
            return -1;
        }
        if (!done)
            return -1;
        p += done;
        len -= (size_t)done;
    }
    return 0;
}

static int read_line(int fd, char *buf, size_t cap)
{
    size_t used = 0U;

    while (used + 1U < cap) {
        char ch;
        ssize_t got = read(fd, &ch, 1U);
        if (got < 0) {
            if (errno == EINTR)
                continue;
            return -1;
        }
        if (!got)
            return -1;
        buf[used++] = ch;
        if (ch == '\n')
            break;
    }
    if (!used || buf[used - 1U] != '\n')
        return -1;
    buf[used] = '\0';
    return 0;
}

static int expect_line(int fd, const char *expected)
{
    char line[2048];

    return read_line(fd, line, sizeof(line)) || strcmp(line, expected);
}

int main(int argc, char **argv)
{
    struct sockaddr_in addr;
    struct timeval timeout = { .tv_sec = 30, .tv_usec = 0 };
    char line[4096];
    char *end;
    unsigned long port;
    FILE *out = NULL;
    int listener = -1;
    int fd = -1;
    int one = 1;
    int rc = 1;

    if (argc != 3) {
        fprintf(stderr, "usage: %s PORT OUTPUT\n", argv[0]);
        return 2;
    }
    errno = 0;
    port = strtoul(argv[1], &end, 10);
    if (errno || !*argv[1] || *end || !port || port > 65535U)
        return 2;
    listener = socket(AF_INET, SOCK_STREAM, 0);
    if (listener < 0)
        goto out;
    (void)setsockopt(listener, SOL_SOCKET, SO_REUSEADDR, &one, sizeof(one));
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port = htons((unsigned short)port);
    addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    if (bind(listener, (struct sockaddr *)&addr, sizeof(addr)) ||
        listen(listener, 1))
        goto out;
    printf("dnsmtpfake: ready port=%lu\n", port);
    fflush(stdout);
    fd = accept(listener, NULL, NULL);
    if (fd < 0)
        goto out;
    (void)setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
    (void)setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout));
    if (write_all(fd, "220 dniv smtp\r\n", 15U) ||
        expect_line(fd, "HELO decnet-iv-linux\r\n") ||
        write_all(fd, "250 dniv\r\n", 10U) ||
        expect_line(fd, "MAIL FROM:<mail11@localhost>\r\n") ||
        write_all(fd, "250 ok\r\n", 8U) ||
        expect_line(fd, "RCPT TO:<TEST>\r\n") ||
        write_all(fd, "250 ok\r\n", 8U) ||
        expect_line(fd, "RCPT TO:<SECOND>\r\n") ||
        write_all(fd, "250 ok\r\n", 8U) ||
        expect_line(fd, "DATA\r\n") ||
        write_all(fd, "354 go\r\n", 8U))
        goto out;
    out = fopen(argv[2], "wb");
    if (!out)
        goto out;
    for (;;) {
        if (read_line(fd, line, sizeof(line)))
            goto out;
        if (!strcmp(line, ".\r\n"))
            break;
        if (line[0] == '.' && line[1] == '.')
            memmove(line, line + 1, strlen(line));
        if (fputs(line, out) == EOF)
            goto out;
    }
    if (fclose(out))
        goto out;
    out = NULL;
    if (write_all(fd, "250 stored\r\n", 12U) ||
        expect_line(fd, "QUIT\r\n") ||
        write_all(fd, "221 bye\r\n", 9U))
        goto out;
    rc = 0;
out:
    if (out)
        fclose(out);
    if (fd >= 0)
        close(fd);
    if (listener >= 0)
        close(listener);
    return rc;
}
