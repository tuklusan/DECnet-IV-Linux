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
#include <poll.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>

struct task_spec {
    uint16_t addr;
    char object[DN_MAXOBJL + 1];
    char user[DN_MAXACCL + 1];
    char password[DN_MAXACCL + 1];
    char account[DN_MAXACCL + 1];
};

static __le16 cpu_to_le16_u(uint16_t value)
{
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
    return (__le16)value;
#else
    return (__le16)__builtin_bswap16(value);
#endif
}

static int parse_node(const char *text, uint16_t *addr)
{
    char *end;
    unsigned long area;
    unsigned long node;

    errno = 0;
    area = strtoul(text, &end, 10);
    if (errno || end == text || *end != '.' || area > 63U)
        return -1;
    node = strtoul(end + 1, &end, 10);
    if (errno || *end || node == 0U || node > 1023U)
        return -1;
    *addr = (uint16_t)((area << 10) | node);
    return 0;
}

static int copy_field(char *dst, size_t cap, const char *start, size_t len)
{
    if (len >= cap)
        return -1;
    memcpy(dst, start, len);
    dst[len] = '\0';
    return 0;
}

static int parse_spec(const char *text, struct task_spec *spec)
{
    const char *sep = strstr(text, "::");
    const char *quote;
    char node[16];

    memset(spec, 0, sizeof(*spec));
    if (!sep || strstr(sep + 2, "::"))
        return -1;
    quote = memchr(text, '"', (size_t)(sep - text));
    if (quote) {
        const char *close = memchr(quote + 1, '"', (size_t)(sep - quote - 1));
        char auth[(DN_MAXACCL + 1) * 3];
        char *save = NULL;
        char *part;
        unsigned int field = 0U;
        size_t n;

        if (!close || close != sep - 1 ||
            copy_field(node, sizeof(node), text, (size_t)(quote - text)))
            return -1;
        n = (size_t)(close - quote - 1);
        if (n >= sizeof(auth))
            return -1;
        memcpy(auth, quote + 1, n);
        auth[n] = '\0';
        part = strtok_r(auth, " ", &save);
        while (part) {
            char *dst;
            size_t cap;

            if (field == 0U) {
                dst = spec->user;
                cap = sizeof(spec->user);
            } else if (field == 1U) {
                dst = spec->password;
                cap = sizeof(spec->password);
            } else if (field == 2U) {
                dst = spec->account;
                cap = sizeof(spec->account);
            } else {
                return -1;
            }
            if (strlen(part) >= cap)
                return -1;
            strcpy(dst, part);
            field++;
            part = strtok_r(NULL, " ", &save);
        }
    } else {
        if (copy_field(node, sizeof(node), text, (size_t)(sep - text)))
            return -1;
    }
    if (parse_node(node, &spec->addr))
        return -1;
    if (!sep[2])
        strcpy(spec->object, "TASK");
    else if (strlen(sep + 2) > DN_MAXOBJL)
        return -1;
    else
        strcpy(spec->object, sep + 2);
    return 0;
}

static int set_access_field(unsigned char *dst, size_t cap, __u8 *len,
                            const char *text)
{
    size_t n = text ? strlen(text) : 0U;

    if (n > cap)
        return -1;
    if (n)
        memcpy(dst, text, n);
    *len = (__u8)n;
    return 0;
}

static int apply_access_defaults(struct task_spec *spec)
{
    const char *value;

    if (!spec->user[0] && (value = getenv("DNACCESS_USER")) && value[0] &&
        copy_field(spec->user, sizeof(spec->user), value, strlen(value)))
        return -1;
    if (!spec->password[0] && (value = getenv("DNACCESS_PASSWORD")) && value[0] &&
        copy_field(spec->password, sizeof(spec->password), value, strlen(value)))
        return -1;
    if (!spec->account[0] && (value = getenv("DNACCESS_ACCOUNT")) && value[0] &&
        copy_field(spec->account, sizeof(spec->account), value, strlen(value)))
        return -1;
    return 0;
}

static int connect_task(const struct task_spec *spec, int timeout_seconds)
{
    struct sockaddr_dn peer;
    struct accessdata_dn access;
    struct timeval timeout;
    int fd;

    fd = socket(AF_DECnet, SOCK_SEQPACKET, DNPROTO_NSP);
    if (fd < 0)
        return -1;
    timeout.tv_sec = timeout_seconds;
    timeout.tv_usec = 0;
    if (timeout_seconds > 0 &&
        setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout)) < 0)
        goto fail;

    memset(&access, 0, sizeof(access));
    if (set_access_field(access.acc_user, sizeof(access.acc_user),
                         &access.acc_userl, spec->user) ||
        set_access_field(access.acc_pass, sizeof(access.acc_pass),
                         &access.acc_passl, spec->password) ||
        set_access_field(access.acc_acc, sizeof(access.acc_acc),
                         &access.acc_accl, spec->account))
        goto fail;
    if ((access.acc_userl || access.acc_passl || access.acc_accl) &&
        setsockopt(fd, DNPROTO_NSP, SO_CONACCESS,
                   &access, sizeof(access)) < 0)
        goto fail;

    memset(&peer, 0, sizeof(peer));
    peer.sdn_family = AF_DECnet;
    peer.sdn_objnamel = cpu_to_le16_u((uint16_t)strlen(spec->object));
    memcpy(peer.sdn_objname, spec->object, strlen(spec->object));
    peer.sdn_add.a_len = cpu_to_le16_u(2U);
    peer.sdn_add.a_addr[0] = (unsigned char)(spec->addr & 0xffU);
    peer.sdn_add.a_addr[1] = (unsigned char)(spec->addr >> 8);
    if (connect(fd, (struct sockaddr *)&peer, sizeof(peer)) < 0)
        goto fail;
    return fd;

fail:
    close(fd);
    return -1;
}

static int output_record(const unsigned char *buf, size_t len, int binary)
{
    if (len && fwrite(buf, 1, len, stdout) != len)
        return -1;
    if (!binary && (!len || buf[len - 1U] != '\n') && fputc('\n', stdout) == EOF)
        return -1;
    return fflush(stdout);
}

static int run_output(int fd, int binary)
{
    unsigned char buf[DNBUFSIZE];

    for (;;) {
        ssize_t got = recv(fd, buf, sizeof(buf), 0);

        if (got == 0)
            return 0;
        if (got < 0)
            return -1;
        if (output_record(buf, (size_t)got, binary))
            return -1;
    }
}

static int run_interactive(int fd, int binary, int timeout_seconds)
{
    unsigned char buf[DNBUFSIZE];

    for (;;) {
        struct pollfd fds[2] = {
            { .fd = fd, .events = POLLIN },
            { .fd = STDIN_FILENO, .events = POLLIN }
        };
        int timeout_ms = timeout_seconds ? timeout_seconds * 1000 : -1;
        int rc = poll(fds, 2, timeout_ms);

        if (rc == 0) {
            fprintf(stderr, "dntask: inactivity timeout\n");
            return -1;
        }
        if (rc < 0) {
            if (errno == EINTR)
                continue;
            return -1;
        }
        if (fds[0].revents & POLLIN) {
            ssize_t got = recv(fd, buf, sizeof(buf), 0);

            if (got == 0)
                return 0;
            if (got < 0 || output_record(buf, (size_t)got, binary))
                return -1;
        }
        if (fds[1].revents & POLLIN) {
            ssize_t got = read(STDIN_FILENO, buf, sizeof(buf));

            if (got == 0)
                return 0;
            if (got < 0)
                return -1;
            if (!binary && buf[got - 1] == '\n')
                got--;
            if (got && send(fd, buf, (size_t)got,
                            MSG_EOR | MSG_NOSIGNAL) != got)
                return -1;
        }
        if (fds[0].revents & (POLLERR | POLLHUP | POLLNVAL))
            return 0;
    }
}

static int selftest(void)
{
    struct task_spec spec;

    if (parse_spec("31.71::", &spec) ||
        spec.addr != (uint16_t)((31U << 10) | 71U) ||
        strcmp(spec.object, "TASK"))
        return 1;
    if (parse_spec("31.71\"USER PASS ACCT\"::SHOW_SYSTEM", &spec) ||
        strcmp(spec.object, "SHOW_SYSTEM") || strcmp(spec.user, "USER") ||
        strcmp(spec.password, "PASS") || strcmp(spec.account, "ACCT"))
        return 1;
    if (!parse_spec("64.1::TASK", &spec) ||
        !parse_spec("31.0::TASK", &spec) ||
        !parse_spec("31.71::THIS_OBJECT_NAME_IS_TOO_LONG", &spec))
        return 1;
    puts("dntask selftest passed");
    return 0;
}

int main(int argc, char **argv)
{
    struct task_spec spec;
    int interactive = 0;
    int binary = 0;
    int timeout_seconds = 60;
    int connect_timeout = 60;
    int arg = 1;
    int fd;

    while (arg < argc && argv[arg][0] == '-' && argv[arg][1]) {
        if (!strcmp(argv[arg], "--selftest") && arg + 1 == argc)
            return selftest();
        if (!strcmp(argv[arg], "-i")) {
            interactive = 1;
            arg++;
            continue;
        }
        if (!strcmp(argv[arg], "-b")) {
            binary = 1;
            arg++;
            continue;
        }
        if ((!strcmp(argv[arg], "-t") || !strcmp(argv[arg], "-T")) &&
            arg + 1 < argc) {
            char *end = NULL;
            long value;

            errno = 0;
            value = strtol(argv[arg + 1], &end, 10);
            if (errno || end == argv[arg + 1] || *end ||
                value < 0 || value > 86400)
                goto usage;
            if (argv[arg][1] == 't')
                timeout_seconds = (int)value;
            else
                connect_timeout = (int)value;
            arg += 2;
            continue;
        }
        goto usage;
    }
    if (arg + 1 != argc || parse_spec(argv[arg], &spec))
        goto usage;
    if (apply_access_defaults(&spec)) {
        fprintf(stderr, "dntask: DNACCESS field exceeds %u bytes\n", DN_MAXACCL);
        return 2;
    }

    fd = connect_task(&spec, connect_timeout);
    if (fd < 0) {
        perror("dntask: connect");
        return 1;
    }
    if (interactive) {
        if (run_interactive(fd, binary, timeout_seconds)) {
            perror("dntask: session");
            close(fd);
            return 1;
        }
    } else if (run_output(fd, binary)) {
        perror("dntask: receive");
        close(fd);
        return 1;
    }
    close(fd);
    return 0;

usage:
    fprintf(stderr,
            "usage: %s [-i] [-b] [-t SECONDS] [-T SECONDS] "
            "'AREA.NODE[\"USER PASS ACCOUNT\"]::[TASK]'\n"
            "DNACCESS_USER, DNACCESS_PASSWORD and DNACCESS_ACCOUNT provide "
            "non-command-line access defaults.\n",
            argv[0]);
    return 2;
}
