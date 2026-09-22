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

#define _DEFAULT_SOURCE
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <linux/dn.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <termios.h>
#include <unistd.h>

#ifndef AF_DECnet
#define AF_DECnet 12
#endif

#define DNLOGIN_CTERM_OBJECT 42U
#define FOUND_BIND 1U
#define FOUND_UNBIND 2U
#define FOUND_BIND_ACCEPT 4U
#define FOUND_COMMON_DATA 9U

#define CTERM_INITIATE 1U
#define CTERM_START_READ 2U
#define CTERM_READ_DATA 3U
#define CTERM_WRITE 7U
#define CTERM_WRITE_COMPLETE 8U
#define CTERM_READ_CHARACTERISTICS 10U
#define CTERM_CHARACTERISTICS 11U
#define CTERM_CHECK_INPUT 12U
#define CTERM_INPUT_COUNT 13U

struct terminal_state {
    struct termios saved;
    int active;
};

struct login_options {
    const char *user;
    const char *password;
    const char *account;
};

static uint16_t get_le16(const unsigned char *p)
{
    return (uint16_t)p[0] | ((uint16_t)p[1] << 8);
}

static void put_le16(unsigned char *p, uint16_t v)
{
    p[0] = (unsigned char)(v & 0xffU);
    p[1] = (unsigned char)(v >> 8);
}

static int parse_node(const char *text, uint16_t *address)
{
    char *end;
    unsigned long area;
    unsigned long node;

    errno = 0;
    area = strtoul(text, &end, 10);
    if (errno || end == text || *end != '.' || area > 63U)
        return -1;
    text = end + 1;
    errno = 0;
    node = strtoul(text, &end, 10);
    if (errno || end == text || *end != '\0' || node == 0U || node > 1023U)
        return -1;
    *address = (uint16_t)((area << 10) | node);
    return 0;
}

static size_t make_bind_accept(unsigned char out[17])
{
    memset(out, 0, 17);
    out[0] = FOUND_BIND_ACCEPT;
    out[1] = 2U;
    out[2] = 4U;
    out[3] = 0U;
    put_le16(out + 4, 193U);
    return 17U;
}

static size_t make_cterm_initiate(unsigned char *out, size_t cap)
{
    static const unsigned char body[] = {
        CTERM_INITIATE, 0x00, 0x01, 0x04, 0x00,
        'd','n','l','o','g','i','n',' ',
        0x01,0x02,0x00,0x02,
        0x02,0x02,0xf4,0x03,
        0x03,0x04,0xfe,0x7f,0x00,0x00,
        0x00
    };
    size_t need = 4U + sizeof(body);

    if (cap < need)
        return 0U;
    out[0] = FOUND_COMMON_DATA;
    out[1] = 0U;
    put_le16(out + 2, (uint16_t)sizeof(body));
    memcpy(out + 4, body, sizeof(body));
    return need;
}

static int validate_bind(const unsigned char *buf, size_t len)
{
    return len >= 5U && buf[0] == FOUND_BIND;
}

static int validate_cterm_initiate(const unsigned char *buf, size_t len)
{
    uint16_t inner;

    if (len < 5U || buf[0] != FOUND_COMMON_DATA)
        return -1;
    inner = get_le16(buf + 2);
    if ((size_t)inner + 4U > len || inner < 1U)
        return -1;
    return buf[4] == CTERM_INITIATE ? 0 : -1;
}

static int set_access_field(unsigned char *dst, size_t cap, __u8 *len,
                            const char *text)
{
    size_t n;

    if (!text) {
        *len = 0U;
        return 0;
    }
    n = strlen(text);
    if (n > cap)
        return -1;
    memcpy(dst, text, n);
    *len = (__u8)n;
    return 0;
}

static int connect_cterm(const char *node_text, const struct login_options *options)
{
    struct sockaddr_dn peer;
    struct accessdata_dn access;
    struct timeval tv = { 15, 0 };
    uint16_t address;
    int fd;

    if (parse_node(node_text, &address)) {
        fprintf(stderr, "dnlogin: invalid DECnet node %s\n", node_text);
        return -2;
    }
    fd = socket(AF_DECnet, SOCK_SEQPACKET, DNPROTO_NSP);
    if (fd < 0) {
        perror("dnlogin: socket");
        return -1;
    }
    if (setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv)) ||
        setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof(tv))) {
        perror("dnlogin: timeout");
        close(fd);
        return -1;
    }
    if (options && (options->user || options->password || options->account)) {
        memset(&access, 0, sizeof(access));
        if (set_access_field(access.acc_user, sizeof(access.acc_user),
                             &access.acc_userl, options->user) ||
            set_access_field(access.acc_pass, sizeof(access.acc_pass),
                             &access.acc_passl, options->password) ||
            set_access_field(access.acc_acc, sizeof(access.acc_acc),
                             &access.acc_accl, options->account)) {
            fprintf(stderr, "dnlogin: access field exceeds %u bytes\n", DN_MAXACCL);
            close(fd);
            return -2;
        }
        if (setsockopt(fd, DNPROTO_NSP, SO_CONACCESS, &access, sizeof(access))) {
            perror("dnlogin: access data");
            close(fd);
            return -1;
        }
    }
    memset(&peer, 0, sizeof(peer));
    peer.sdn_family = AF_DECnet;
    peer.sdn_objnum = DNLOGIN_CTERM_OBJECT;
    peer.sdn_nodeaddrl = (__le16)2U;
    peer.sdn_nodeaddr[0] = (unsigned char)(address & 0xffU);
    peer.sdn_nodeaddr[1] = (unsigned char)(address >> 8);
    if (connect(fd, (struct sockaddr *)&peer, sizeof(peer))) {
        perror("dnlogin: connect");
        close(fd);
        return -1;
    }
    return fd;
}

static int perform_handshake(int fd)
{
    unsigned char buf[1024];
    unsigned char out[64];
    ssize_t got;
    size_t len;

    got = recv(fd, buf, sizeof(buf), 0);
    if (got <= 0 || !validate_bind(buf, (size_t)got)) {
        fprintf(stderr, "dnlogin: invalid Foundation bind\n");
        return -1;
    }
    len = make_bind_accept(out);
    if (send(fd, out, len, MSG_EOR | MSG_NOSIGNAL) != (ssize_t)len) {
        perror("dnlogin: bind accept");
        return -1;
    }
    got = recv(fd, buf, sizeof(buf), 0);
    if (got <= 0 || validate_cterm_initiate(buf, (size_t)got)) {
        fprintf(stderr, "dnlogin: missing CTERM initiate\n");
        return -1;
    }
    len = make_cterm_initiate(out, sizeof(out));
    if (!len || send(fd, out, len, MSG_EOR | MSG_NOSIGNAL) != (ssize_t)len) {
        perror("dnlogin: CTERM initiate");
        return -1;
    }
    return 0;
}

static int terminal_enter(struct terminal_state *state)
{
    struct termios raw;

    memset(state, 0, sizeof(*state));
    if (!isatty(STDIN_FILENO))
        return 0;
    if (tcgetattr(STDIN_FILENO, &state->saved))
        return -1;
    raw = state->saved;
    cfmakeraw(&raw);
    if (tcsetattr(STDIN_FILENO, TCSANOW, &raw))
        return -1;
    state->active = 1;
    return 0;
}

static void terminal_leave(struct terminal_state *state)
{
    if (state->active)
        (void)tcsetattr(STDIN_FILENO, TCSANOW, &state->saved);
}

static int send_common(int fd, const unsigned char *body, size_t body_len)
{
    unsigned char record[2048];
    size_t total = body_len + 4U;

    if (body_len > UINT16_MAX || total > sizeof(record))
        return -1;
    record[0] = FOUND_COMMON_DATA;
    record[1] = 0U;
    put_le16(record + 2, (uint16_t)body_len);
    memcpy(record + 4, body, body_len);
    return send(fd, record, total, MSG_EOR | MSG_NOSIGNAL) == (ssize_t)total ? 0 : -1;
}

static int is_terminator(unsigned char c)
{
    return c == '\r' || c == '\n' || c == 0x03U || c == 0x1bU || c == 0x1aU;
}

static int read_terminal(unsigned char *out, size_t cap, size_t requested,
                         int echo, uint16_t *term_pos, size_t *out_len)
{
    size_t limit = requested && requested < cap ? requested : cap;
    size_t used = 0;
    unsigned char ch;
    ssize_t got;

    if (!limit)
        return -1;
    while (used < limit) {
        got = read(STDIN_FILENO, &ch, 1);
        if (got == 0)
            break;
        if (got < 0) {
            if (errno == EINTR)
                continue;
            return -1;
        }
        out[used++] = ch;
        if (echo && isatty(STDIN_FILENO)) {
            if (ch == '\r') {
                if (write(STDOUT_FILENO, "\r\n", 2) != 2)
                    return -1;
            } else if (write(STDOUT_FILENO, &ch, 1) != 1) {
                return -1;
            }
        }
        if (is_terminator(ch))
            break;
    }
    *term_pos = (uint16_t)(used && is_terminator(out[used - 1U]) ? used - 1U : used);
    *out_len = used;
    return 0;
}

static int handle_start_read(int fd, const unsigned char *body, size_t len)
{
    unsigned char input[1024];
    unsigned char reply[1032];
    uint32_t flags;
    uint16_t maximum;
    uint16_t term_pos;
    size_t input_len;
    int echo;

    if (len < 17U)
        return -1;
    flags = (uint32_t)body[1] | ((uint32_t)body[2] << 8) |
            ((uint32_t)body[3] << 16);
    maximum = get_le16(body + 4);
    echo = (flags & 0x800U) == 0U;
    if (read_terminal(input, sizeof(input), maximum, echo, &term_pos, &input_len))
        return -1;
    reply[0] = CTERM_READ_DATA;
    reply[1] = 0U;
    reply[2] = 0U;
    reply[3] = 0U;
    reply[4] = 0U;
    reply[5] = 0U;
    put_le16(reply + 6, term_pos);
    memcpy(reply + 8, input, input_len);
    return send_common(fd, reply, input_len + 8U);
}

static int handle_write(int fd, const unsigned char *body, size_t len)
{
    unsigned char complete[6] = { CTERM_WRITE_COMPLETE, 0, 0, 0, 0, 0 };
    uint16_t flags;

    if (len < 5U)
        return -1;
    flags = get_le16(body + 1);
    if (len > 5U && fwrite(body + 5, 1, len - 5U, stdout) != len - 5U)
        return -1;
    if (fflush(stdout))
        return -1;
    if (flags & 0x0400U)
        return send_common(fd, complete, sizeof(complete));
    return 0;
}

static int handle_check_input(int fd)
{
    unsigned char reply[4] = { CTERM_INPUT_COUNT, 0, 0, 0 };
    int available = 0;
    uint16_t count;

    if (ioctl(STDIN_FILENO, FIONREAD, &available) < 0)
        return -1;
    if (available < 0)
        available = 0;
    count = available > UINT16_MAX ? UINT16_MAX : (uint16_t)available;
    put_le16(reply + 2, count);
    return send_common(fd, reply, sizeof(reply));
}

static int append_characteristic(unsigned char *out, size_t cap,
                                 size_t *used, uint16_t selector)
{
    struct winsize ws;
    struct termios tio;
    unsigned int value = 0U;
    size_t width = 0U;

    if (*used + 2U > cap)
        return -1;
    out[(*used)++] = (unsigned char)(selector & 0xffU);
    out[(*used)++] = (unsigned char)((selector >> 8) & 0x03U);

    switch (selector) {
    case 0x0003U:
        value = 8U;
        width = 2U;
        break;
    case 0x0109U:
        value = 80U;
        if (!ioctl(STDIN_FILENO, TIOCGWINSZ, &ws) && ws.ws_col)
            value = ws.ws_col;
        width = 2U;
        break;
    case 0x010aU:
        value = 24U;
        if (!ioctl(STDIN_FILENO, TIOCGWINSZ, &ws) && ws.ws_row)
            value = ws.ws_row;
        width = 2U;
        break;
    case 0x0205U:
        value = 1U;
        if (isatty(STDIN_FILENO) && !tcgetattr(STDIN_FILENO, &tio))
            value = (tio.c_lflag & ECHO) ? 1U : 0U;
        width = 1U;
        break;
    default:
        return -1;
    }

    if (*used + width > cap)
        return -1;
    out[(*used)++] = (unsigned char)(value & 0xffU);
    if (width == 2U)
        out[(*used)++] = (unsigned char)((value >> 8) & 0xffU);
    return 0;
}

static int handle_read_characteristics(int fd, const unsigned char *body,
                                       size_t len)
{
    unsigned char reply[128];
    size_t used = 2U;
    size_t off = 2U;

    if (len < 2U)
        return -1;
    reply[0] = CTERM_CHARACTERISTICS;
    reply[1] = 0U;
    while (off + 1U < len) {
        uint16_t selector = get_le16(body + off);

        if (append_characteristic(reply, sizeof(reply), &used, selector))
            return -1;
        off += 2U;
    }
    if (off != len)
        return -1;
    return send_common(fd, reply, used);
}

static int handle_common(int fd, const unsigned char *record, size_t len)
{
    const unsigned char *body;
    uint16_t inner;

    if (len < 5U || record[0] != FOUND_COMMON_DATA)
        return -1;
    inner = get_le16(record + 2);
    if ((size_t)inner + 4U != len || inner < 1U)
        return -1;
    body = record + 4;
    switch (body[0]) {
    case CTERM_WRITE:
        return handle_write(fd, body, inner);
    case CTERM_START_READ:
        return handle_start_read(fd, body, inner);
    case CTERM_CHECK_INPUT:
        return handle_check_input(fd);
    case CTERM_READ_CHARACTERISTICS:
        return handle_read_characteristics(fd, body, inner);
    default:
        fprintf(stderr, "dnlogin: unsupported CTERM message %u\n", body[0]);
        return -1;
    }
}

static int selftest(void)
{
    unsigned char bind[17];
    unsigned char init[64];
    unsigned char read_data[16];
    unsigned char peer_bind[] = { FOUND_BIND, 2, 4, 0, 7 };
    unsigned char peer_init[] = { FOUND_COMMON_DATA, 0, 1, 0, CTERM_INITIATE };
    uint16_t addr;

    if (parse_node("31.70", &addr) || addr != (uint16_t)((31U << 10) | 70U))
        return 1;
    if (!parse_node("64.1", &addr) || !parse_node("31.0", &addr))
        return 1;
    if (make_bind_accept(bind) != sizeof(bind) || bind[0] != FOUND_BIND_ACCEPT ||
        get_le16(bind + 4) != 193U)
        return 1;
    if (!make_cterm_initiate(init, sizeof(init)) ||
        init[0] != FOUND_COMMON_DATA || get_le16(init + 2) != 28U ||
        init[4] != CTERM_INITIATE)
        return 1;
    if (!validate_bind(peer_bind, sizeof(peer_bind)) ||
        validate_cterm_initiate(peer_init, sizeof(peer_init)))
        return 1;
    memset(read_data, 0, sizeof(read_data));
    read_data[0] = CTERM_READ_DATA;
    put_le16(read_data + 6, 6U);
    memcpy(read_data + 8, "phase7\r", 7);
    if (read_data[0] != CTERM_READ_DATA || get_le16(read_data + 6) != 6U ||
        memcmp(read_data + 8, "phase7\r", 7))
        return 1;
    puts("dnlogin protocol selftest passed");
    return 0;
}

static int probe(const char *node_text)
{
    int fd = connect_cterm(node_text, NULL);

    if (fd == -2)
        return 2;
    if (fd < 0)
        return 1;
    if (perform_handshake(fd)) {
        close(fd);
        return 1;
    }
    printf("dnlogin: CTERM Foundation handshake complete with %s\n", node_text);
    close(fd);
    return 0;
}

static int session(const char *node_text, const struct login_options *options)
{
    struct terminal_state terminal;
    struct timeval none = { 0, 0 };
    unsigned char buf[2048];
    ssize_t got;
    int fd = connect_cterm(node_text, options);
    int rc = 1;

    if (fd == -2)
        return 2;
    if (fd < 0)
        return 1;
    if (perform_handshake(fd))
        goto out;
    if (setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &none, sizeof(none))) {
        perror("dnlogin: clear receive timeout");
        goto out;
    }
    if (terminal_enter(&terminal)) {
        perror("dnlogin: terminal mode");
        goto out;
    }
    for (;;) {
        got = recv(fd, buf, sizeof(buf), 0);
        if (got == 0) {
            rc = 0;
            break;
        }
        if (got < 0) {
            if (errno == EINTR)
                continue;
            perror("dnlogin: receive");
            break;
        }
        if (buf[0] == FOUND_UNBIND) {
            rc = 0;
            break;
        }
        if (handle_common(fd, buf, (size_t)got)) {
            fprintf(stderr, "dnlogin: invalid CTERM/Foundation record\n");
            break;
        }
    }
    terminal_leave(&terminal);
out:
    close(fd);
    return rc;
}

int main(int argc, char **argv)
{
    struct login_options options = { 0 };
    const char *node = NULL;
    int opt;

    if (argc == 2 && strcmp(argv[1], "--selftest") == 0)
        return selftest();
    if (argc == 3 && strcmp(argv[1], "--probe") == 0)
        return probe(argv[2]);

    opterr = 0;
    while ((opt = getopt(argc, argv, "u:p:a:")) != -1) {
        switch (opt) {
        case 'u':
            options.user = optarg;
            break;
        case 'p':
            options.password = optarg;
            break;
        case 'a':
            options.account = optarg;
            break;
        default:
            fprintf(stderr, "dnlogin: invalid option\n");
            return 2;
        }
    }
    if (optind + 1 == argc)
        node = argv[optind];
    if (node)
        return session(node, &options);
    fprintf(stderr,
            "usage: %s [-u USER] [-p PASSWORD] [-a ACCOUNT] AREA.NODE\n"
            "       %s --probe AREA.NODE\n"
            "       %s --selftest\n",
            argv[0], argv[0], argv[0]);
    return 2;
}
