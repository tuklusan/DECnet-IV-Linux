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
#define DAP_NAME 15U
#define DAP_STATUS_EOF 0x4027U
#define DAP_RFM_FIX 1U
#define DAP_RFM_VAR 2U
#define DAP_RFM_STM 4U
#define DAP_RFM_SCR 6U

struct access_options {
    const char *user;
    const char *password;
    const char *account;
};

struct remote_spec {
    char node[16];
    char file[256];
    char user[64];
    char password[64];
    char account[64];
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

static int copy_span(char *dst, size_t cap, const char *start,
                     const char *end)
{
    size_t n;

    if (end < start)
        return -1;
    n = (size_t)(end - start);
    if (!n || n >= cap)
        return -1;
    memcpy(dst, start, n);
    dst[n] = '\0';
    return 0;
}

static int parse_transparent_spec(const char *text, struct remote_spec *spec,
                                  struct access_options *options)
{
    const char *sep = strstr(text, "::");
    const char *quote;
    uint16_t addr;

    memset(spec, 0, sizeof(*spec));
    if (!sep || strstr(sep + 2, "::"))
        return -1;
    quote = memchr(text, '"', (size_t)(sep - text));
    if (quote) {
        const char *close = memchr(quote + 1, '"', (size_t)(sep - quote - 1));
        char creds[192];
        char *save = NULL;
        char *part;
        unsigned int field = 0U;
        size_t n;

        if (!close || close != sep - 1 ||
            copy_span(spec->node, sizeof(spec->node), text, quote))
            return -1;
        n = (size_t)(close - quote - 1);
        if (n >= sizeof(creds))
            return -1;
        memcpy(creds, quote + 1, n);
        creds[n] = '\0';
        for (part = strtok_r(creds, " ", &save); part;
             part = strtok_r(NULL, " ", &save)) {
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
        }
        if (!options->user && spec->user[0])
            options->user = spec->user;
        if (!options->password && spec->password[0])
            options->password = spec->password;
        if (!options->account && spec->account[0])
            options->account = spec->account;
    } else if (copy_span(spec->node, sizeof(spec->node), text, sep)) {
        return -1;
    }
    if (strlen(sep + 2) >= sizeof(spec->file))
        return -1;
    strcpy(spec->file, sep + 2);
    return parse_node(spec->node, &addr);
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

static const char *dap_status_class_name(unsigned int mac)
{
    switch (mac) {
    case 0U: return "pending";
    case 1U: return "success";
    case 2U: return "unsupported";
    case 4U: return "open error";
    case 5U: return "transfer error";
    case 6U: return "transfer warning";
    case 7U: return "close error";
    case 8U: return "message format error";
    case 9U: return "invalid field";
    case 10U: return "out of sync";
    default: return "unknown";
    }
}

static int decode_status(const unsigned char *buf, size_t len,
                         uint16_t *raw, unsigned int *mac,
                         unsigned int *mic)
{
    uint16_t value;

    if (len < 4U || buf[0] != DAP_STATUS)
        return -1;
    value = (uint16_t)buf[2] | ((uint16_t)buf[3] << 8);
    *raw = value;
    *mic = value & 0x0fffU;
    *mac = (value >> 12) & 0x0fU;
    return 0;
}

static void report_status(const char *where, const unsigned char *buf, size_t len)
{
    uint16_t raw;
    unsigned int mac;
    unsigned int mic;

    if (decode_status(buf, len, &raw, &mac, &mic)) {
        fprintf(stderr, "dncopy: malformed DAP %s STATUS\n", where);
        return;
    }
    fprintf(stderr,
            "dncopy: DAP %s status mac=%u (%s) mic=0x%03x raw=0x%04x\n",
            where, mac, dap_status_class_name(mac), mic, raw);
}

static int decode_ex(const unsigned char *buf, size_t len, size_t *pos,
                     unsigned int max_bytes, uint64_t *value)
{
    uint64_t result = 0U;
    unsigned int i;

    for (i = 0U; i < max_bytes; i++) {
        unsigned char byte;

        if (*pos >= len)
            return -1;
        byte = buf[(*pos)++];
        result |= (uint64_t)(byte & 0x7fU) << (7U * i);
        if (!(byte & 0x80U)) {
            *value = result;
            return 0;
        }
    }
    return -1;
}

static int parse_rfm(const unsigned char *buf, size_t len,
                     unsigned char *rfm)
{
    uint64_t menu;
    uint64_t ignored;
    size_t pos = 2U;

    *rfm = DAP_RFM_FIX;
    if (len < 3U || buf[0] != DAP_ATTRIBUTES ||
        decode_ex(buf, len, &pos, 6U, &menu))
        return -1;
    if (!menu)
        return pos == len ? 0 : -1;
    if ((menu & 0x01U) &&
        decode_ex(buf, len, &pos, 2U, &ignored))
        return -1;
    if (menu & 0x02U) {
        if (pos >= len)
            return -1;
        pos++; /* ORG */
    }
    if (menu & 0x04U) {
        if (pos >= len)
            return -1;
        *rfm = buf[pos];
    }
    return 0;
}

static int write_text_payload(FILE *out, const unsigned char *data, size_t len,
                              unsigned char rfm)
{
    size_t i;

    if (rfm == DAP_RFM_VAR) {
        if (len && fwrite(data, 1, len, out) != len)
            return -1;
        return fputc('\n', out) == EOF ? -1 : 0;
    }
    if (rfm == DAP_RFM_STM || rfm == DAP_RFM_SCR) {
        for (i = 0; i < len; i++) {
            if (data[i] == '\r') {
                if (i + 1U < len && data[i + 1U] == '\n')
                    i++;
                if (fputc('\n', out) == EOF)
                    return -1;
            } else if (fputc(data[i], out) == EOF) {
                return -1;
            }
        }
        return 0;
    }
    return len && fwrite(data, 1, len, out) != len ? -1 : 0;
}

static int retrieve_file(const char *node_text, const char *filespec,
                         const char *local_path, int text_mode,
                         const struct access_options *options)
{
    unsigned char msg[512], reply[2048];
    size_t n = strlen(filespec);
    int got;
    int fd;
    unsigned char rfm = 0U;
    FILE *out = stdout;

    if (!n || n > 128U) {
        fprintf(stderr, "dncopy: invalid remote file specification\n");
        return -1;
    }
    if (local_path && strcmp(local_path, "-")) {
        out = fopen(local_path, "wb");
        if (!out) {
            perror("dncopy: open local output");
            return -1;
        }
    }
    fd = open_fal(node_text, options);
    if (fd < 0) {
        if (local_path && strcmp(local_path, "-"))
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
    if (got < 3 || parse_rfm(reply, (size_t)got, &rfm))
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
            if (text_mode) {
                if (write_text_payload(out, reply + off, (size_t)got - off, rfm))
                    goto fail;
            } else if (fwrite(reply + off, 1, (size_t)got - off, out) !=
                       (size_t)got - off) {
                goto fail;
            }
            continue;
        }
        if (reply[0] == DAP_STATUS) {
            uint16_t status;
            unsigned int mac;
            unsigned int mic;

            if (decode_status(reply, (size_t)got, &status, &mac, &mic))
                goto fail;
            if (status != DAP_STATUS_EOF) {
                report_status("retrieval", reply, (size_t)got);
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
    if (local_path && strcmp(local_path, "-") && fclose(out))
        return -1;
    return 0;

fail:
    fprintf(stderr, "dncopy: DAP retrieval failed\n");
    close(fd);
    if (local_path && strcmp(local_path, "-"))
        fclose(out);
    return -1;
}


static int store_file(const char *local_path, const char *node_text,
                      const char *filespec, int text_mode,
                      const struct access_options *options)
{
    unsigned char msg[2048], reply[512], data[1024];
    FILE *in;
    size_t n = strlen(filespec);
    size_t data_len;
    int fd;
    int got;

    if (!n || n > 128U) {
        fprintf(stderr, "dncopy: invalid remote file specification\n");
        return -1;
    }
    if (!strcmp(local_path, "-")) {
        in = stdin;
    } else {
        in = fopen(local_path, "rb");
        if (!in) {
            perror("dncopy: open local input");
            return -1;
        }
    }
    fd = open_fal(node_text, options);
    if (fd < 0)
        return -1;
    if (exchange_config(fd))
        goto fail;

    msg[0] = DAP_ATTRIBUTES;
    msg[1] = 0U;
    if (text_mode) {
        msg[2] = 0x0fU; /* DATATYPE, ORG, RFM, RAT */
        msg[3] = 0x01U; /* ASCII */
        msg[4] = 0U;    /* sequential organization */
        msg[5] = DAP_RFM_VAR;
        msg[6] = 0x02U; /* implied carriage return */
        if (send_record(fd, msg, 7U))
            goto fail;
    } else {
        msg[2] = 0U;
        if (send_record(fd, msg, 3U))
            goto fail;
    }

    msg[0] = DAP_ACCESS;
    msg[1] = 0U;
    msg[2] = 2U; /* CREATE */
    msg[3] = 0U; /* ACCOPT */
    msg[4] = (unsigned char)n;
    memcpy(msg + 5, filespec, n);
    if (send_record(fd, msg, n + 5U))
        goto fail;

    got = recv_message(fd, reply, sizeof(reply), DAP_ATTRIBUTES);
    if (got < 3) {
        goto fail;
    } else {
        unsigned char remote_rfm;

        if (parse_rfm(reply, (size_t)got, &remote_rfm))
            goto fail;
    }
    if (recv_message(fd, reply, sizeof(reply), DAP_ACK) != 2)
        goto fail;

    msg[0] = DAP_CONTROL;
    msg[1] = 0U;
    msg[2] = 2U; /* CONNECT */
    if (send_record(fd, msg, 3U) ||
        recv_message(fd, reply, sizeof(reply), DAP_ACK) != 2)
        goto fail;

    msg[0] = DAP_CONTROL;
    msg[1] = 0U;
    msg[2] = 4U; /* PUT */
    if (send_record(fd, msg, 3U))
        goto fail;

    if (text_mode) {
        while (fgets((char *)data, sizeof(data), in)) {
            size_t len = strlen((char *)data);

            if (len && data[len - 1U] == '\n') {
                len--;
                if (len && data[len - 1U] == '\r')
                    len--;
            } else if (!feof(in)) {
                fprintf(stderr, "dncopy: text input line exceeds %zu bytes\n",
                        sizeof(data) - 2U);
                goto fail;
            }
            msg[0] = DAP_DATA;
            msg[1] = 0U;
            msg[2] = 0U;
            memcpy(msg + 3, data, len);
            if (send_record(fd, msg, len + 3U))
                goto fail;
        }
        if (ferror(in))
            goto fail;
    } else {
        for (;;) {
            data_len = fread(data, 1, sizeof(data), in);
            if (data_len) {
                msg[0] = DAP_DATA;
                msg[1] = 0U;
                msg[2] = 0U; /* empty record number */
                memcpy(msg + 3, data, data_len);
                if (send_record(fd, msg, data_len + 3U))
                    goto fail;
            }
            if (data_len < sizeof(data)) {
                if (ferror(in))
                    goto fail;
                break;
            }
        }
    }
    if (in != stdin && fclose(in))
        goto fail_closed;
    in = NULL;

    msg[0] = DAP_ACCESS_COMPLETE;
    msg[1] = 0U;
    msg[2] = 1U; /* CLOSE */
    if (send_record(fd, msg, 3U))
        goto fail;
    got = recv_message(fd, reply, sizeof(reply), DAP_ACCESS_COMPLETE);
    if (got < 3 || reply[2] != 2U)
        goto fail;
    close(fd);
    return 0;

fail:
    if (in && in != stdin)
        fclose(in);
fail_closed:
    fprintf(stderr, "dncopy: DAP store failed\n");
    close(fd);
    return -1;
}

static int delete_file(const char *node_text, const char *filespec,
                       const struct access_options *options)
{
    unsigned char msg[512], reply[512];
    size_t n = strlen(filespec);
    int fd;
    ssize_t got;

    if (!n || n > 128U) {
        fprintf(stderr, "dncopy: invalid remote file specification\n");
        return -1;
    }
    fd = open_fal(node_text, options);
    if (fd < 0)
        return -1;
    if (exchange_config(fd))
        goto fail;

    msg[0] = DAP_ACCESS;
    msg[1] = 0U;
    msg[2] = 4U; /* ERASE */
    msg[3] = 0U; /* ACCOPT */
    msg[4] = (unsigned char)n;
    memcpy(msg + 5, filespec, n);
    if (send_record(fd, msg, n + 5U))
        goto fail;

    got = recv(fd, reply, sizeof(reply), 0);
    if (got < 2)
        goto fail;
    if (reply[0] == DAP_STATUS) {
        report_status("erase", reply, (size_t)got);
        goto fail;
    }
    if (reply[0] != DAP_ACCESS_COMPLETE || got < 3 || reply[2] != 2U)
        goto fail;
    close(fd);
    return 0;

fail:
    fprintf(stderr, "dncopy: DAP erase failed\n");
    close(fd);
    return -1;
}

static int list_directory(const char *node_text, const char *filespec,
                          const struct access_options *options)
{
    unsigned char msg[512], reply[2048];
    size_t n = strlen(filespec);
    int fd;

    if (n > 128U) {
        fprintf(stderr, "dncopy: invalid remote directory specification\n");
        return -1;
    }
    fd = open_fal(node_text, options);
    if (fd < 0)
        return -1;
    if (exchange_config(fd))
        goto fail;

    msg[0] = DAP_ACCESS;
    msg[1] = 0U;
    msg[2] = 6U; /* DIRECTORY LIST */
    msg[3] = 0U; /* ACCOPT */
    msg[4] = (unsigned char)n;
    memcpy(msg + 5, filespec, n);
    if (send_record(fd, msg, n + 5U))
        goto fail;

    for (;;) {
        ssize_t got = recv(fd, reply, sizeof(reply), 0);

        if (got < 2)
            goto fail;
        if (reply[0] == DAP_ACCESS_COMPLETE) {
            if (got < 3 || reply[2] != 2U)
                goto fail;
            break;
        }
        if (reply[0] == DAP_NAME) {
            unsigned int name_type;
            unsigned int name_len;

            if (got < 4)
                goto fail;
            name_type = reply[2] & 0x7fU;
            name_len = reply[3];
            if ((size_t)got != 4U + name_len)
                goto fail;
            if (name_type == 1U || name_type == 2U) {
                if (fwrite(reply + 4U, 1, name_len, stdout) != name_len ||
                    fputc('\n', stdout) == EOF)
                    goto fail;
            }
            continue;
        }
        if (reply[0] == DAP_ATTRIBUTES || reply[0] == 13U ||
            reply[0] == 14U)
            continue;
        if (reply[0] == DAP_STATUS) {
            report_status("directory", reply, (size_t)got);
            goto fail;
        }
        goto fail;
    }
    if (fflush(stdout))
        goto fail;
    close(fd);
    return 0;

fail:
    fprintf(stderr, "dncopy: DAP directory listing failed\n");
    close(fd);
    return -1;
}

static int selftest(void)
{
    unsigned char config[32];
    const unsigned char eof_status[] = { DAP_STATUS, 0U, 0x27U, 0x40U };
    const unsigned char attr_rfm[] = { DAP_ATTRIBUTES, 0U, 0x04U, DAP_RFM_VAR };
    const unsigned char attr_rich[] = {
        DAP_ATTRIBUTES, 0U, 0x87U, 0x01U, 0x01U, 0x00U, DAP_RFM_STM, 0x20U
    };
    const unsigned char attr_default[] = { DAP_ATTRIBUTES, 0U, 0x00U };
    const unsigned char attr_bad_menu[] = {
        DAP_ATTRIBUTES, 0U, 0x80U, 0x80U, 0x80U, 0x80U, 0x80U, 0x80U
    };
    uint16_t addr;
    uint16_t status;
    unsigned int mac;
    unsigned int mic;
    struct remote_spec remote;
    struct access_options parsed_options = { 0 };

    if (parse_node("31.70", &addr) || addr != (uint16_t)((31U << 10) | 70U))
        return 1;
    if (!parse_node("64.1", &addr) || !parse_node("31.0", &addr))
        return 1;
    if (make_config(config, sizeof(config)) != 12U ||
        config[0] != DAP_CONFIG || config[2] != 0 || config[3] != 4 ||
        config[6] != 4 || config[7] != 1 || validate_config(config, 12U))
        return 1;
    if (DAP_STATUS_EOF != 0x4027U ||
        decode_status(eof_status, sizeof(eof_status), &status, &mac, &mic) ||
        status != DAP_STATUS_EOF || mac != 4U || mic != 0x027U ||
        strcmp(dap_status_class_name(4U), "open error") ||
        strcmp(dap_status_class_name(15U), "unknown"))
        return 1;
    {
        unsigned char rfm;

        if (parse_rfm(attr_rfm, sizeof(attr_rfm), &rfm) ||
            rfm != DAP_RFM_VAR ||
            parse_rfm(attr_rich, sizeof(attr_rich), &rfm) ||
            rfm != DAP_RFM_STM ||
            parse_rfm(attr_default, sizeof(attr_default), &rfm) ||
            rfm != DAP_RFM_FIX ||
            !parse_rfm(attr_bad_menu, sizeof(attr_bad_menu), &rfm))
            return 1;
    }
    if (parse_transparent_spec(
            "31.70\"USER PASS ACCT\"::[DIR]FILE.TXT", &remote,
            &parsed_options) ||
        strcmp(remote.node, "31.70") ||
        strcmp(remote.file, "[DIR]FILE.TXT") ||
        !parsed_options.user || strcmp(parsed_options.user, "USER") ||
        !parsed_options.password || strcmp(parsed_options.password, "PASS") ||
        !parsed_options.account || strcmp(parsed_options.account, "ACCT"))
        return 1;
    parsed_options.user = parsed_options.password = parsed_options.account = NULL;
    if (parse_transparent_spec("31.70::", &remote, &parsed_options) ||
        strcmp(remote.node, "31.70") || remote.file[0] ||
        !parse_transparent_spec("31.70\"TOO MANY FIELDS HERE\"::X",
                                &remote, &parsed_options))
        return 1;
    puts("dncopy DAP selftest passed");
    return 0;
}

int main(int argc, char **argv)
{
    struct access_options options = { 0 };
    const char *mode;
    const char *prog;
    struct remote_spec remote;
    int arg = 1;

    prog = strrchr(argv[0], '/');
    prog = prog ? prog + 1 : argv[0];

    while (arg < argc && argv[arg][0] == '-' && argv[arg][1] &&
           argv[arg][1] != '-') {
        if ((!strcmp(argv[arg], "-u") || !strcmp(argv[arg], "-p") ||
             !strcmp(argv[arg], "-a")) && arg + 1 < argc) {
            const char *value = argv[arg + 1];

            if (!strcmp(argv[arg], "-u"))
                options.user = value;
            else if (!strcmp(argv[arg], "-p"))
                options.password = value;
            else
                options.account = value;
            arg += 2;
            continue;
        }
        goto usage;
    }
    if (!strcmp(prog, "dntype")) {
        if (arg + 1 == argc && strstr(argv[arg], "::")) {
            if (parse_transparent_spec(argv[arg], &remote, &options) ||
                !remote.file[0])
                goto usage;
            return retrieve_file(remote.node, remote.file, NULL, 1,
                                 &options) ? 1 : 0;
        }
        if (arg + 2 == argc)
            return retrieve_file(argv[arg], argv[arg + 1], NULL, 1,
                                 &options) ? 1 : 0;
        goto usage;
    }
    if (!strcmp(prog, "dndir")) {
        if (arg + 1 == argc && strstr(argv[arg], "::")) {
            if (parse_transparent_spec(argv[arg], &remote, &options))
                goto usage;
            return list_directory(remote.node,
                                  remote.file[0] ? remote.file : "*.*;*",
                                  &options) ? 1 : 0;
        }
        if (arg + 1 == argc)
            return list_directory(argv[arg], "*.*;*", &options) ? 1 : 0;
        if (arg + 2 == argc)
            return list_directory(argv[arg], argv[arg + 1], &options) ? 1 : 0;
        goto usage;
    }
    if (!strcmp(prog, "dndel")) {
        if (arg + 1 == argc && strstr(argv[arg], "::")) {
            if (parse_transparent_spec(argv[arg], &remote, &options) ||
                !remote.file[0])
                goto usage;
            return delete_file(remote.node, remote.file, &options) ? 1 : 0;
        }
        if (arg + 2 == argc)
            return delete_file(argv[arg], argv[arg + 1], &options) ? 1 : 0;
        goto usage;
    }
    if (arg + 2 == argc &&
        (strstr(argv[arg], "::") || strstr(argv[arg + 1], "::"))) {
        int src_remote = strstr(argv[arg], "::") != NULL;
        int dst_remote = strstr(argv[arg + 1], "::") != NULL;

        if (src_remote == dst_remote)
            goto usage;
        if (src_remote) {
            if (parse_transparent_spec(argv[arg], &remote, &options) ||
                !remote.file[0])
                goto usage;
            return retrieve_file(remote.node, remote.file, argv[arg + 1], 1,
                                 &options) ? 1 : 0;
        }
        if (parse_transparent_spec(argv[arg + 1], &remote, &options) ||
            !remote.file[0])
            goto usage;
        return store_file(argv[arg], remote.node, remote.file, 1,
                          &options) ? 1 : 0;
    }
    if (arg >= argc)
        goto usage;
    mode = argv[arg++];
    if (!strcmp(mode, "--selftest") && arg == argc)
        return selftest();
    if (!strcmp(mode, "--probe") && arg + 1 == argc)
        return connect_fal(argv[arg], &options) ? 1 : 0;
    if (!strcmp(mode, "--get") && arg + 2 == argc)
        return retrieve_file(argv[arg], argv[arg + 1], NULL, 0, &options) ? 1 : 0;
    if (!strcmp(mode, "--get-text") && arg + 2 == argc)
        return retrieve_file(argv[arg], argv[arg + 1], NULL, 1, &options) ? 1 : 0;
    if (!strcmp(mode, "--get-to") && arg + 3 == argc)
        return retrieve_file(argv[arg], argv[arg + 1], argv[arg + 2], 0,
                             &options) ? 1 : 0;
    if (!strcmp(mode, "--put") && arg + 3 == argc)
        return store_file(argv[arg], argv[arg + 1], argv[arg + 2], 0,
                          &options) ? 1 : 0;
    if (!strcmp(mode, "--put-text") && arg + 3 == argc)
        return store_file(argv[arg], argv[arg + 1], argv[arg + 2], 1,
                          &options) ? 1 : 0;
    if (!strcmp(mode, "--dir") && arg + 2 == argc)
        return list_directory(argv[arg], argv[arg + 1], &options) ? 1 : 0;
    if (!strcmp(mode, "--delete") && arg + 2 == argc)
        return delete_file(argv[arg], argv[arg + 1], &options) ? 1 : 0;
usage:
    if (!strcmp(prog, "dntype")) {
        fprintf(stderr, "usage: dntype [-u USER] [-p PASSWORD] [-a ACCOUNT] AREA.NODE FILE | 'AREA.NODE[\"USER PASS ACCOUNT\"]::FILE'\n");
    } else if (!strcmp(prog, "dndir")) {
        fprintf(stderr, "usage: dndir [-u USER] [-p PASSWORD] [-a ACCOUNT] AREA.NODE [SPEC] | 'AREA.NODE[\"USER PASS ACCOUNT\"]::[SPEC]'\n");
    } else if (!strcmp(prog, "dndel")) {
        fprintf(stderr, "usage: dndel [-u USER] [-p PASSWORD] [-a ACCOUNT] AREA.NODE FILE | 'AREA.NODE[\"USER PASS ACCOUNT\"]::FILE'\n");
    } else {
        fprintf(stderr,
                "usage: %s [-u USER] [-p PASSWORD] [-a ACCOUNT] "
                "--selftest | --probe AREA.NODE | --get AREA.NODE FILE | "
                "--get-text AREA.NODE FILE | --get-to AREA.NODE FILE LOCAL | "
                "--put LOCAL AREA.NODE REMOTE | --put-text LOCAL AREA.NODE REMOTE | "
                "--dir AREA.NODE SPEC | --delete AREA.NODE FILE | "
                "SOURCE DEST (one transparent AREA.NODE::FILE)\n", argv[0]);
    }
    return 2;
}
