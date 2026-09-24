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

#include <errno.h>
#include <linux/dn.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <sys/time.h>
#include <unistd.h>

#define MAIL_OBJECT 27U
#define MAIL_BACKLOG 8
#define MAIL11_V3_LEN 16U

static __le16 cpu_to_le16_u(uint16_t value)
{
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
    return (__le16)value;
#else
    return (__le16)__builtin_bswap16(value);
#endif
}

static uint16_t le16_to_cpu_u(__le16 value)
{
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
    return (uint16_t)value;
#else
    return __builtin_bswap16((uint16_t)value);
#endif
}

static int make_listener(void)
{
    struct sockaddr_dn local;
    int mode = ACC_DEFER;
    int fd = socket(AF_DECnet, SOCK_SEQPACKET, DNPROTO_NSP);

    if (fd < 0)
        return -1;
    if (setsockopt(fd, DNPROTO_NSP, DSO_ACCEPTMODE, &mode, sizeof(mode))) {
        close(fd);
        return -1;
    }
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

static int accept_mail_session(int fd)
{
    static const unsigned char reply[MAIL11_V3_LEN] = {
        3U, 1U, 0U, 18U, 0U, 0U, 0U, 0U,
        0xa0U, 0x02U, 0U, 0U, 1U, 0U, 0U, 0U
    };
    struct optdata_dn incoming;
    struct optdata_dn outgoing;
    socklen_t len = sizeof(incoming);
    uint16_t n;

    memset(&incoming, 0, sizeof(incoming));
    if (getsockopt(fd, DNPROTO_NSP, DSO_CONDATA, &incoming, &len) ||
        len != sizeof(incoming))
        return -1;
    n = le16_to_cpu_u(incoming.opt_optl);
    if (n && (n != MAIL11_V3_LEN || incoming.opt_data[0] != 3U))
        return -1;
    if (n) {
        memset(&outgoing, 0, sizeof(outgoing));
        outgoing.opt_optl = cpu_to_le16_u(MAIL11_V3_LEN);
        memcpy(outgoing.opt_data, reply, sizeof(reply));
        if (setsockopt(fd, DNPROTO_NSP, DSO_CONDATA,
                       &outgoing, sizeof(outgoing)))
            return -1;
    }
    return setsockopt(fd, DNPROTO_NSP, DSO_CONACCEPT, NULL, 0);
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

static int start_sendmail(const char *path, int *input_fd, pid_t *child)
{
    int pipefd[2];
    pid_t pid;

    if (pipe(pipefd))
        return -1;
    pid = fork();
    if (pid < 0) {
        close(pipefd[0]);
        close(pipefd[1]);
        return -1;
    }
    if (!pid) {
        close(pipefd[1]);
        if (dup2(pipefd[0], STDIN_FILENO) < 0)
            _exit(127);
        close(pipefd[0]);
        execl(path, path, "-i", "-t", (char *)NULL);
        _exit(127);
    }
    close(pipefd[0]);
    *input_fd = pipefd[1];
    *child = pid;
    return 0;
}

static void abort_sendmail(int input_fd, pid_t child)
{
    int status;

    if (input_fd >= 0)
        close(input_fd);
    if (child <= 0)
        return;
    kill(child, SIGKILL);
    while (waitpid(child, &status, 0) < 0 && errno == EINTR)
        ;
}

static int finish_sendmail(int input_fd, pid_t child)
{
    static const struct timespec delay = { .tv_sec = 0, .tv_nsec = 100000000L };
    int status;
    int i;

    if (close(input_fd))
        return -1;
    for (i = 0; i < 300; i++) {
        pid_t rc = waitpid(child, &status, WNOHANG);

        if (rc == child)
            return WIFEXITED(status) && WEXITSTATUS(status) == 0 ? 0 : -1;
        if (rc < 0 && errno != EINTR)
            return -1;
        nanosleep(&delay, NULL);
    }
    kill(child, SIGKILL);
    while (waitpid(child, &status, 0) < 0 && errno == EINTR)
        ;
    errno = ETIMEDOUT;
    return -1;
}

static int serve(int fd, const char *root, const char *sendmail_path)
{
    struct timeval timeout = { .tv_sec = 30, .tv_usec = 0 };
    unsigned char body[4096];
    char sender[256], recipient[256], recipients[1024];
    char full_user[256], subject[256], path[1024], header[4096];
    FILE *out = NULL;
    int mail_fd = -1;
    pid_t mail_child = -1;
    ssize_t got;

    if (setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)) ||
        setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout)))
        return -1;
    if (recv_field(fd, sender, sizeof(sender), 0) < 0)
        return -1;
    recipients[0] = '\0';
    for (;;) {
        got = recv(fd, recipient, sizeof(recipient) - 1U, 0);
        if (got < 0)
            return -1;
        if (got == 1 && recipient[0] == '\0')
            break;
        if (got <= 0 || (size_t)got >= sizeof(recipient))
            return -1;
        recipient[got] = '\0';
        if (strchr(recipient, '\r') || strchr(recipient, '\n') ||
            strchr(recipient, '\0') != recipient + got)
            return -1;
        {
            size_t used = strlen(recipients);
            size_t add = strlen(recipient);
            size_t need = used + (used ? 1U : 0U) + add + 1U;

            if (need > sizeof(recipients))
                return -1;
            if (used)
                recipients[used++] = ',';
            memcpy(recipients + used, recipient, add + 1U);
        }
        if (send_ack(fd))
            return -1;
    }
    if (!recipients[0])
        return -1;
    if (recv_field(fd, full_user, sizeof(full_user), 1) < 0 ||
        recv_field(fd, subject, sizeof(subject), 1) < 0)
        return -1;

    if (snprintf(path, sizeof(path), "%s/mailbox.log", root) >= (int)sizeof(path))
        return -1;
    out = fopen(path, "ab");
    if (!out)
        return -1;
    {
        int header_len = snprintf(
            header, sizeof(header),
            "From: %s\nTo: %s\nX-VMSmail: %s\nSubject: %s\n\n",
            sender, recipients, full_user, subject);

        if (header_len < 0 || (size_t)header_len >= sizeof(header))
            goto fail;
        if (fwrite(header, 1, (size_t)header_len, out) !=
            (size_t)header_len)
            goto fail;
        if (sendmail_path) {
            if (start_sendmail(sendmail_path, &mail_fd, &mail_child) ||
                write_all(mail_fd, header, (size_t)header_len))
                goto fail;
        }
    }

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
        if (mail_fd >= 0 &&
            (write_all(mail_fd, body, (size_t)got) ||
             write_all(mail_fd, "\n", 1U)))
            goto fail;
    }
    if (fputs("--\n", out) == EOF || fclose(out))
        goto fail;
    out = NULL;
    if (mail_fd >= 0) {
        int finish_rc = finish_sendmail(mail_fd, mail_child);

        mail_fd = -1;
        mail_child = -1;
        if (finish_rc)
            return -1;
    }
    return send_ack(fd);

fail:
    if (out)
        fclose(out);
    abort_sendmail(mail_fd, mail_child);
    return -1;
}

static int selftest(void)
{
    if (MAIL_OBJECT != 27U || MAIL11_V3_LEN != 16U)
        return 1;
    puts("dnmaild selftest passed");
    return 0;
}

int main(int argc, char **argv)
{
    const char *root = ".";
    const char *sendmail_path = NULL;
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
        else if (!strcmp(argv[i], "--sendmail") && i + 1 < argc)
            sendmail_path = argv[++i];
        else {
            fprintf(stderr,
                    "usage: %s [--once] [--root DIR] [--sendmail PATH] | --selftest\n",
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
        rc = accept_mail_session(fd);
        if (!rc)
            rc = serve(fd, root, sendmail_path);
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
