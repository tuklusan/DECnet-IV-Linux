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

#include <arpa/inet.h>
#include <errno.h>
#include <linux/dn.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

#ifndef AF_DECnet
#define AF_DECnet 12
#endif
#ifndef DNPROTO_NSP
#define DNPROTO_NSP 2
#endif

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

struct access_options {
    const char *user;
    const char *password;
    const char *account;
};

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

static int parse_node(const char *s, uint16_t *addr)
{
    char *end;
    unsigned long area = strtoul(s, &end, 10);
    unsigned long node;

    if (!s[0] || *end != '.' || area > 63)
        return -1;
    node = strtoul(end + 1, &end, 10);
    if (*end || node == 0 || node > 1023)
        return -1;
    *addr = (uint16_t)((area << 10) | node);
    return 0;
}

static size_t make_config(unsigned char *buf, size_t cap)
{
    if (cap < 12U)
        return 0;
    buf[0] = DAP_CONFIG;
    buf[1] = 0U;
    buf[2] = 0x00U;
    buf[3] = 0x04U; /* 1024-byte DAP buffer */
    buf[4] = 128U;  /* user-defined OS: Linux */
    buf[5] = 128U;  /* user-defined file system */
    buf[6] = 4U;
    buf[7] = 1U;
    buf[8] = 0U;
    buf[9] = 0U;
    buf[10] = 0U;
    buf[11] = 0U;   /* no optional system capabilities yet */
    return 12U;
}

static int validate_config(const unsigned char *buf, size_t len)
{
    if (len < 12U || buf[0] != DAP_CONFIG)
        return -1;
    if (buf[1] & 0x7fU)
        return -1;
    return 0;
}

static int open_fal(const char *node_text, const struct access_options *options)
{
    struct sockaddr_dn peer;
    struct accessdata_dn access;
    uint16_t addr;
    int fd;

    if (parse_node(node_text, &addr)) {
        fprintf(stderr, "dncopy: invalid DECnet node %s\n", node_text);
        return -1;
    }
    fd = socket(AF_DECnet, SOCK_SEQPACKET, DNPROTO_NSP);
    if (fd < 0) {
        perror("dncopy: socket");
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
            fprintf(stderr, "dncopy: access field exceeds %u bytes\n", DN_MAXACCL);
            close(fd);
            return -1;
        }
        if (setsockopt(fd, DNPROTO_NSP, SO_CONACCESS, &access, sizeof(access))) {
            perror("dncopy: access data");
            close(fd);
            return -1;
        }
    }
    memset(&peer, 0, sizeof(peer));
    peer.sdn_family = AF_DECnet;
    peer.sdn_flags = 0;
    peer.sdn_objnum = DAP_FAL_OBJECT;
    peer.sdn_objnamel = 0;
    peer.sdn_add.a_len = 2;
    peer.sdn_add.a_addr[0] = (unsigned char)(addr & 0xffU);
    peer.sdn_add.a_addr[1] = (unsigned char)(addr >> 8);
    if (connect(fd, (struct sockaddr *)&peer, sizeof(peer))) {
        perror("dncopy: connect FAL");
        close(fd);
        return -1;
    }
    return fd;
}

static int send_record(int fd, const unsigned char *buf, size_t len)
{
    return send(fd, buf, len, MSG_EOR | MSG_NOSIGNAL) == (ssize_t)len ? 0 : -1;
}

static int exchange_config(int fd)
{
    unsigned char config[32], reply[256];
    size_t config_len = make_config(config, sizeof(config));
    ssize_t got;

    if (!config_len || send_record(fd, config, config_len))
        return -1;
    got = recv(fd, reply, sizeof(reply), 0);
    return got > 0 && !validate_config(reply, (size_t)got) ? 0 : -1;
}

static int connect_fal(const char *node_text, const struct access_options *options)
{
    int fd = open_fal(node_text, options);

    if (fd < 0)
        return -1;
    if (exchange_config(fd)) {
        fprintf(stderr, "dncopy: invalid DAP CONFIG exchange\n");
        close(fd);
        return -1;
    }
    printf("dncopy: DAP CONFIG exchange complete with %s object %u\n",
           node_text, DAP_FAL_OBJECT);
    close(fd);
    return 0;
}

static int recv_message(int fd, unsigned char *buf, size_t cap, unsigned char type)
{
    ssize_t got = recv(fd, buf, cap, 0);

    if (got < 2 || buf[0] != type)
        return -1;
    return (int)got;
}

static int retrieve_file(const char *node_text, const char *filespec,
                         const char *local_path,
                         const struct access_options *options)
{
    unsigned char msg[512], reply[2048];
    size_t n = strlen(filespec);
    int got;
    int fd;
    FILE *out = stdout;

    if (!n || n > 128U) {
        fprintf(stderr, "dncopy: invalid remote file specification\n");
        return -1;
    }
    if (local_path) {
        out = fopen(local_path, "wb");
        if (!out) {
            perror("dncopy: open local output");
            return -1;
        }
    }
    fd = open_fal(node_text, options);
    if (fd < 0) {
        if (local_path)
            fclose(out);
        return -1;
    }
    if (exchange_config(fd))
        goto fail;

    msg[0] = DAP_ACCESS;
    msg[1] = 0U;
    msg[2] = 1U; /* OPEN */
    msg[3] = 0U; /* ACCOPT */
    msg[4] = (unsigned char)n;
    memcpy(msg + 5, filespec, n);
    if (send_record(fd, msg, n + 5U))
        goto fail;

    got = recv_message(fd, reply, sizeof(reply), DAP_ATTRIBUTES);
    if (got < 3 || reply[2] != 0U)
        goto fail;
    if (recv_message(fd, reply, sizeof(reply), DAP_ACK) != 2)
        goto fail;

    msg[0] = DAP_CONTROL;
    msg[1] = 0U;
    msg[2] = 2U; /* CONNECT data stream */
    if (send_record(fd, msg, 3U) ||
        recv_message(fd, reply, sizeof(reply), DAP_ACK) != 2)
        goto fail;

    msg[0] = DAP_CONTROL;
    msg[1] = 0U;
    msg[2] = 1U; /* GET, sequential file mode selected by peer defaults */
    if (send_record(fd, msg, 3U))
        goto fail;

    for (;;) {
        got = recv(fd, reply, sizeof(reply), 0);
        if (got < 2)
            goto fail;
        if (reply[0] == DAP_DATA) {
            unsigned int recnum_len;
            size_t off;

            if (got < 3)
                goto fail;
            recnum_len = reply[2];
            off = 3U + recnum_len;
            if (off > (size_t)got)
                goto fail;
            if (fwrite(reply + off, 1, (size_t)got - off, out) !=
                (size_t)got - off)
                goto fail;
            continue;
        }
        if (reply[0] == DAP_STATUS) {
            uint16_t status;

            if (got < 4)
                goto fail;
            status = (uint16_t)reply[2] | ((uint16_t)reply[3] << 8);
            if (status != DAP_STATUS_EOF) {
                fprintf(stderr, "dncopy: DAP status 0x%04x\n", status);
                goto fail;
            }
            break;
        }
        goto fail;
    }

    msg[0] = DAP_ACCESS_COMPLETE;
    msg[1] = 0U;
    msg[2] = 1U; /* COMMAND */
    if (send_record(fd, msg, 3U))
        goto fail;
    got = recv_message(fd, reply, sizeof(reply), DAP_ACCESS_COMPLETE);
    if (got < 3 || reply[2] != 2U)
        goto fail;
    if (fflush(out))
        goto fail;
    close(fd);
    if (local_path && fclose(out))
        return -1;
    return 0;

fail:
    fprintf(stderr, "dncopy: DAP retrieval failed\n");
    close(fd);
    if (local_path)
        fclose(out);
    return -1;
}

static int selftest(void)
{
    unsigned char config[32];
    uint16_t addr;

    if (parse_node("31.70", &addr) || addr != (uint16_t)((31U << 10) | 70U))
        return 1;
    if (!parse_node("64.1", &addr) || !parse_node("31.0", &addr))
        return 1;
    if (make_config(config, sizeof(config)) != 12U ||
        config[0] != DAP_CONFIG || config[2] != 0 || config[3] != 4 ||
        config[6] != 4 || config[7] != 1 || validate_config(config, 12U))
        return 1;
    if (DAP_STATUS_EOF != 0x4027U)
        return 1;
    puts("dncopy DAP selftest passed");
    return 0;
}

int main(int argc, char **argv)
{
    struct access_options options = { 0 };
    const char *mode;
    int opt;

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
            goto usage;
        }
    }
    if (optind >= argc)
        goto usage;
    mode = argv[optind++];
    if (!strcmp(mode, "--selftest") && optind == argc)
        return selftest();
    if (!strcmp(mode, "--probe") && optind + 1 == argc)
        return connect_fal(argv[optind], &options) ? 1 : 0;
    if (!strcmp(mode, "--get") && optind + 2 == argc)
        return retrieve_file(argv[optind], argv[optind + 1], NULL, &options) ? 1 : 0;
    if (!strcmp(mode, "--get-to") && optind + 3 == argc)
        return retrieve_file(argv[optind], argv[optind + 1], argv[optind + 2],
                             &options) ? 1 : 0;
usage:
    fprintf(stderr,
            "usage: %s [-u USER] [-p PASSWORD] [-a ACCOUNT] "
            "--selftest | --probe AREA.NODE | --get AREA.NODE FILE | "
            "--get-to AREA.NODE FILE LOCAL\n", argv[0]);
    return 2;
}
