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
#include <fcntl.h>
#include <linux/dn.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <unistd.h>

#include "../common/record_io.h"

#ifndef AF_DECnet
#define AF_DECnet 12
#endif
#ifndef DNPROTO_NSP
#define DNPROTO_NSP 2
#endif

#define DAP_FAL_OBJECT 17U
#define DAP_BUFFER_LIMIT 2048U
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
#define DAP_IO_TIMEOUT_SECONDS 30L
#define DAP_RFM_FIX 1U
#define DAP_RFM_VAR 2U
#define DAP_RFM_VFC 3U
#define DAP_RFM_STM 4U
#define DAP_RFM_STMLF 5U
#define DAP_RFM_SCR 6U

#define DAP_RAT_NONE 0U
#define DAP_RAT_FTN 0x01U
#define DAP_RAT_CR 0x02U
#define DAP_RAT_PRN 0x04U

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

    if (!s[0] || *end != '.' || area < 1 || area > 63)
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

/* dncopy is a single-operation CLI. Refresh this limit for each CONFIG
 * exchange, then apply it to every DAP frame on that connection. */
static size_t dap_send_limit = DAP_BUFFER_LIMIT;

static int negotiate_buffer_limit(const unsigned char *config, size_t len,
                                  size_t *limit)
{
    size_t peer;

    if (!limit || len < 12U || config[0] != DAP_CONFIG ||
        (config[1] & 0x7fU))
        return -1;
    peer = (size_t)config[2] | ((size_t)config[3] << 8U);
    if (peer && peer < 12U)
        return -1;
    *limit = !peer || peer > DAP_BUFFER_LIMIT ? DAP_BUFFER_LIMIT : peer;
    return 0;
}

static size_t make_config(unsigned char *buf, size_t cap)
{
    if (cap < 12U)
        return 0;
    buf[0] = DAP_CONFIG;
    buf[1] = 0U;
    buf[2] = 0x00U;
    buf[3] = 0x08U; /* 2048-byte maximum complete DAP message */
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
    size_t limit;

    return negotiate_buffer_limit(buf, len, &limit);
}

/* A connected but silent FAL peer must not hold an interactive copy
 * forever.  These are per-I/O inactivity bounds, not whole-file deadlines.
 */
static int set_dap_timeouts(int fd)
{
    const struct timeval limit = { .tv_sec = DAP_IO_TIMEOUT_SECONDS,
                                   .tv_usec = 0 };

    return setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO,
                      &limit, sizeof(limit)) ||
           setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO,
                      &limit, sizeof(limit)) ? -1 : 0;
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
    if (set_dap_timeouts(fd)) {
        perror("dncopy: socket timeout");
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
    if (len > dap_send_limit) {
        errno = EMSGSIZE;
        return -1;
    }
    return dniv_send_record(fd, buf, len, 0);
}

static ssize_t recv_record(int fd, void *buf, size_t cap, int flags)
{
    return dniv_recv_record(fd, buf,
                            cap < dap_send_limit ? cap : dap_send_limit, flags);
}

static int exchange_config(int fd)
{
    unsigned char config[32], reply[256];
    size_t config_len = make_config(config, sizeof(config));
    ssize_t got;

    dap_send_limit = DAP_BUFFER_LIMIT;
    if (!config_len || send_record(fd, config, config_len))
        return -1;
    got = recv_record(fd, reply, sizeof(reply), 0);
    return got > 0 ? negotiate_buffer_limit(reply, (size_t)got,
                                            &dap_send_limit) : -1;
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
    ssize_t got = recv_record(fd, buf, cap, 0);

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
        if (pos >= len || buf[pos] < DAP_RFM_FIX ||
            buf[pos] > DAP_RFM_SCR)
            return -1;
        *rfm = buf[pos];
    }
    return 0;
}

static int parse_store_rfm(const char *text, unsigned char *rfm)
{
    if (!strcmp(text, "fix"))
        *rfm = DAP_RFM_FIX;
    else if (!strcmp(text, "var"))
        *rfm = DAP_RFM_VAR;
    else if (!strcmp(text, "vfc"))
        *rfm = DAP_RFM_VFC;
    else if (!strcmp(text, "stm"))
        *rfm = DAP_RFM_STM;
    else if (!strcmp(text, "stmlf"))
        *rfm = DAP_RFM_STMLF;
    else if (!strcmp(text, "stmcr"))
        *rfm = DAP_RFM_SCR;
    else
        return -1;
    return 0;
}

static int parse_store_rat(const char *text, unsigned char *rat)
{
    if (!strcmp(text, "none"))
        *rat = DAP_RAT_NONE;
    else if (!strcmp(text, "ftn"))
        *rat = DAP_RAT_FTN;
    else if (!strcmp(text, "cr"))
        *rat = DAP_RAT_CR;
    else if (!strcmp(text, "prn"))
        *rat = DAP_RAT_PRN;
    else
        return -1;
    return 0;
}

static size_t make_store_attributes(unsigned char *buf, size_t cap,
                                    int include_metadata,
                                    unsigned char rfm, unsigned char rat)
{
    if (cap < 3U)
        return 0U;
    buf[0] = DAP_ATTRIBUTES;
    buf[1] = 0U;
    if (!include_metadata) {
        buf[2] = 0U;
        return 3U;
    }
    if (cap < 7U || rfm < DAP_RFM_FIX || rfm > DAP_RFM_SCR ||
        rat > (DAP_RAT_FTN | DAP_RAT_CR | DAP_RAT_PRN))
        return 0U;
    buf[2] = 0x0fU; /* DATATYPE, ORG, RFM, RAT */
    buf[3] = 0x01U; /* ASCII */
    buf[4] = 0U;    /* sequential organization */
    buf[5] = rfm;
    buf[6] = rat;
    return 7U;
}

static int apply_transfer_option(const char *name, const char *value,
                                 int *text_mode, unsigned char *store_rfm,
                                 unsigned char *store_rat,
                                 int *metadata_override)
{
    if (!strcmp(name, "-m")) {
        if (!strcmp(value, "record"))
            *text_mode = 1;
        else if (!strcmp(value, "block"))
            *text_mode = 0;
        else
            return -1;
        return 0;
    }
    if (!strcmp(name, "-r")) {
        if (parse_store_rfm(value, store_rfm))
            return -1;
        *metadata_override = 1;
        return 0;
    }
    if (!strcmp(name, "-c")) {
        if (parse_store_rat(value, store_rat))
            return -1;
        *metadata_override = 1;
        return 0;
    }
    return -1;
}

static int apply_transfer_env(const char *env, int *text_mode,
                              unsigned char *store_rfm,
                              unsigned char *store_rat,
                              int *metadata_override)
{
    char buf[512];
    char *save = NULL;
    char *tok;

    if (!env || !*env)
        return 0;
    if (strlen(env) >= sizeof(buf))
        return -1;
    strcpy(buf, env);
    tok = strtok_r(buf, " \t", &save);
    while (tok) {
        char name[3] = { 0 };
        const char *value;

        if (strlen(tok) < 2U || tok[0] != '-' ||
            (tok[1] != 'm' && tok[1] != 'r' && tok[1] != 'c'))
            return -1;
        name[0] = '-';
        name[1] = tok[1];
        if (tok[2]) {
            value = tok + 2;
        } else {
            tok = strtok_r(NULL, " \t", &save);
            if (!tok)
                return -1;
            value = tok;
        }
        if (apply_transfer_option(name, value, text_mode, store_rfm,
                                  store_rat, metadata_override))
            return -1;
        tok = strtok_r(NULL, " \t", &save);
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

/* Read one physical text record without treating embedded NUL as EOF.
 * A binary byte in record mode is an error, not a successful partial copy.
 * The bounded reader also handles an exact-size final line without a newline.
 * Return 1 for a record (including an empty line), 0 for clean EOF, -1
 * for an invalid or unreadable record.
 */
static int read_text_record(FILE *in, unsigned char *data, size_t cap,
                            size_t *record_len)
{
    size_t len = 0U;
    int ch;
    int newline = 0;

    if (!in || !data || !cap || !record_len) {
        errno = EINVAL;
        return -1;
    }
    for (;;) {
        ch = fgetc(in);
        if (ch == EOF) {
            if (ferror(in))
                return -1;
            if (!len)
                return 0;
            break;
        }
        if (ch == '\n') {
            newline = 1;
            break;
        }
        if (ch == 0) {
            errno = EILSEQ;
            return -1;
        }
        if (len == cap) {
            errno = E2BIG;
            return -1;
        }
        data[len++] = (unsigned char)ch;
    }
    if (newline && len && data[len - 1U] == '\r')
        len--;
    *record_len = len;
    return 1;
}

/* Publish a named download only after successful DAP completion and local
 * flush/close.  A failed or interrupted transfer must never truncate the
 * caller's existing local file.  Keep the stage under a private directory
 * on the destination filesystem so publication remains atomic.
 */
/* A download is staged in a private 0700 directory on the destination
 * filesystem. Setting the final 0644-style mode on a publicly named
 * mkstemp file would expose unacknowledged partial DAP data to bystanders.
 * Keeping the stage in a private directory also preserves same-filesystem
 * atomic rename semantics for intentional replacement of an existing file.
 */
static void remove_staged_path(char *path)
{
    char *leaf;

    if (!path)
        return;
    (void)unlink(path);
    leaf = strrchr(path, '/');
    if (leaf) {
        *leaf = '\0';
        (void)rmdir(path);
        *leaf = '/';
    }
    free(path);
}

static int begin_staged_output(const char *destination, FILE **out,
                               char **staged_path, int *existed)
{
    static const char pattern[] = ".dniv-dap-XXXXXX";
    static const char leaf[] = "/transfer";
    const char *slash = strrchr(destination, '/');
    size_t prefix_len = slash ? (size_t)(slash - destination + 1) : 0U;
    struct stat existing;
    mode_t mode;
    char *tmp;
    FILE *stream;
    int fd;
    int saved;

    if (!*destination || !existed ||
        prefix_len > SIZE_MAX - sizeof(pattern) - sizeof(leaf)) {
        errno = EINVAL;
        return -1;
    }
    tmp = malloc(prefix_len + sizeof(pattern) + sizeof(leaf));
    if (!tmp)
        return -1;
    memcpy(tmp, destination, prefix_len);
    memcpy(tmp + prefix_len, pattern, sizeof(pattern));
    if (!mkdtemp(tmp)) {
        free(tmp);
        return -1;
    }
    strcat(tmp, leaf);
    fd = open(tmp, O_CREAT | O_EXCL | O_WRONLY | O_NOFOLLOW, 0600);
    if (fd < 0) {
        saved = errno;
        remove_staged_path(tmp);
        errno = saved;
        return -1;
    }
    if (!lstat(destination, &existing)) {
        if (!S_ISREG(existing.st_mode)) {
            errno = EACCES;
            goto fail;
        }
        *existed = 1;
        mode = existing.st_mode & 0777;
    } else if (errno == ENOENT) {
        mode_t mask = umask(0);

        umask(mask);
        *existed = 0;
        mode = 0666 & ~mask;
    } else {
        goto fail;
    }
    if (fchmod(fd, mode))
        goto fail;
    stream = fdopen(fd, "wb");
    if (!stream)
        goto fail;
    *out = stream;
    *staged_path = tmp;
    return 0;
fail:
    saved = errno;
    close(fd);
    remove_staged_path(tmp);
    errno = saved;
    return -1;
}

static void abort_staged_output(FILE **out, char **staged_path)
{
    if (*out) {
        (void)fclose(*out);
        *out = NULL;
    }
    if (*staged_path) {
        remove_staged_path(*staged_path);
        *staged_path = NULL;
    }
}

static int publish_staged_output(FILE **out, char **staged_path,
                                 const char *destination, int existed)
{
    int saved = 0;

    if (fflush(*out) || fsync(fileno(*out)))
        saved = errno;
    if (fclose(*out) && !saved)
        saved = errno;
    *out = NULL;
    /* If the target did not exist when the transfer started, atomically
     * claim the name instead of overwriting an unrelated concurrent writer.
     * link() is atomic and the stage is on the same filesystem.
     */
    if (!saved && (existed ? rename(*staged_path, destination) :
                           link(*staged_path, destination)))
        saved = errno;
    remove_staged_path(*staged_path);
    *staged_path = NULL;
    if (saved) {
        errno = saved;
        return -1;
    }
    return 0;
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
    char *staged_output = NULL;
    int close_out = 0;
    int output_existed = 0;

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

    /* Remote OPEN/CONNECT succeeded.  Stage the named destination, but do
     * not replace the existing file until every DAP read and ACK succeeds.
     */
    if (local_path && strcmp(local_path, "-")) {
        if (begin_staged_output(local_path, &out, &staged_output,
                                &output_existed)) {
            perror("dncopy: stage local output");
            close(fd);
            return -1;
        }
        close_out = 1;
    }

    msg[0] = DAP_CONTROL;
    msg[1] = 0U;
    msg[2] = 1U; /* GET, sequential file mode selected by peer defaults */
    if (send_record(fd, msg, 3U))
        goto fail;

    for (;;) {
        got = recv_record(fd, reply, sizeof(reply), 0);
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
    if (close_out) {
        if (publish_staged_output(&out, &staged_output, local_path,
                                  output_existed))
            goto fail;
        close_out = 0;
    } else if (fflush(out)) {
        goto fail;
    }
    close(fd);
    return 0;

fail:
    fprintf(stderr, "dncopy: DAP retrieval failed\n");
    close(fd);
    if (close_out)
        abort_staged_output(&out, &staged_output);
    return -1;
}


static int store_file(const char *local_path, const char *node_text,
                      const char *filespec, int text_mode,
                      unsigned char store_rfm, unsigned char store_rat,
                      int metadata_override,
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
    if (fd < 0) {
        int saved_errno = errno;

        if (in != stdin)
            (void)fclose(in);
        errno = saved_errno;
        return -1;
    }
    if (exchange_config(fd))
        goto fail;

    {
        size_t attr_len = make_store_attributes(msg, sizeof(msg),
                                                text_mode || metadata_override,
                                                store_rfm, store_rat);

        if (!attr_len || send_record(fd, msg, attr_len))
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
        for (;;) {
            size_t len;
            size_t payload_cap = dap_send_limit - 3U;
            int read_rc = read_text_record(in, data,
                payload_cap < sizeof(data) ? payload_cap : sizeof(data), &len);

            if (!read_rc)
                break;
            if (read_rc < 0) {
                if (errno == EILSEQ)
                    fprintf(stderr, "dncopy: NUL in record-mode input; use -m block for binary data\n");
                else if (errno == E2BIG)
                    fprintf(stderr, "dncopy: text input exceeds negotiated record payload (%zu bytes)\n",
                            dap_send_limit - 3U);
                else
                    perror("dncopy: read text input");
                goto fail;
            }
            msg[0] = DAP_DATA;
            msg[1] = 0U;
            msg[2] = 0U;
            memcpy(msg + 3, data, len);
            if (send_record(fd, msg, len + 3U))
                goto fail;
        }
    } else {
        for (;;) {
            size_t payload_cap = dap_send_limit - 3U;
            if (payload_cap > sizeof(data))
                payload_cap = sizeof(data);
            data_len = fread(data, 1, payload_cap, in);
            if (data_len) {
                msg[0] = DAP_DATA;
                msg[1] = 0U;
                msg[2] = 0U; /* empty record number */
                memcpy(msg + 3, data, data_len);
                if (send_record(fd, msg, data_len + 3U))
                    goto fail;
            }
            if (data_len < payload_cap) {
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

static int rename_file(const char *node_text, const char *oldspec,
                       const char *newspec,
                       const struct access_options *options)
{
    unsigned char msg[512], reply[512];
    size_t oldn = strlen(oldspec);
    size_t newn = strlen(newspec);
    int fd;
    ssize_t got;

    if (!oldn || oldn > 128U || !newn || newn > 128U) {
        fprintf(stderr, "dnrename: invalid remote file specification\n");
        return -1;
    }
    fd = open_fal(node_text, options);
    if (fd < 0)
        return -1;
    if (exchange_config(fd))
        goto fail;

    msg[0] = DAP_ACCESS;
    msg[1] = 0U;
    msg[2] = 3U; /* RENAME */
    msg[3] = 0U; /* ACCOPT */
    msg[4] = (unsigned char)oldn;
    memcpy(msg + 5, oldspec, oldn);
    if (send_record(fd, msg, oldn + 5U))
        goto fail;

    msg[0] = DAP_NAME;
    msg[1] = 0U;
    msg[2] = 1U; /* FILESPEC */
    msg[3] = (unsigned char)newn;
    memcpy(msg + 4, newspec, newn);
    if (send_record(fd, msg, newn + 4U))
        goto fail;

    got = recv_record(fd, reply, sizeof(reply), 0);
    if (got < 3 || reply[0] != DAP_ACCESS_COMPLETE || reply[2] != 2U)
        goto fail;
    close(fd);
    return 0;

fail:
    fprintf(stderr, "dnrename: DAP rename failed\n");
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

    got = recv_record(fd, reply, sizeof(reply), 0);
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

static int print_file(const char *node_text, const char *filespec,
                      const struct access_options *options)
{
    unsigned char msg[512], reply[512];
    size_t n = strlen(filespec);
    int fd;

    if (!n || n > 128U) {
        fprintf(stderr, "dnprint: invalid remote file specification\n");
        return -1;
    }
    fd = open_fal(node_text, options);
    if (fd < 0)
        return -1;
    if (exchange_config(fd))
        goto fail;

    msg[0] = DAP_ATTRIBUTES;
    msg[1] = 0U;
    msg[2] = 0U;
    if (send_record(fd, msg, 3U))
        goto fail;

    msg[0] = DAP_ACCESS;
    msg[1] = 0U;
    msg[2] = 1U; /* OPEN */
    msg[3] = 0U; /* ACCOPT */
    msg[4] = (unsigned char)n;
    memcpy(msg + 5, filespec, n);
    if (send_record(fd, msg, n + 5U))
        goto fail;

    for (;;) {
        ssize_t got = recv_record(fd, reply, sizeof(reply), 0);

        if (got < 2)
            goto fail;
        if (reply[0] == DAP_STATUS) {
            report_status("print-open", reply, (size_t)got);
            goto fail;
        }
        if (reply[0] == DAP_ACK || reply[0] == DAP_ACCESS_COMPLETE)
            break;
        if (reply[0] == DAP_ATTRIBUTES || reply[0] == DAP_NAME)
            continue;
        goto fail;
    }

    msg[0] = DAP_ACCESS_COMPLETE;
    msg[1] = 0U;
    msg[2] = 1U;    /* CLOSE */
    msg[3] = 0x80U; /* FOP bit 20, EX continuation */
    msg[4] = 0x80U;
    msg[5] = 0x40U; /* FB$SPL */
    if (send_record(fd, msg, 6U))
        goto fail;

    for (;;) {
        ssize_t got = recv_record(fd, reply, sizeof(reply), 0);

        if (got < 2)
            goto fail;
        if (reply[0] == DAP_STATUS) {
            report_status("print-close", reply, (size_t)got);
            goto fail;
        }
        if (reply[0] == DAP_ACK || reply[0] == DAP_ACCESS_COMPLETE) {
            close(fd);
            return 0;
        }
        if (reply[0] == DAP_ATTRIBUTES || reply[0] == DAP_NAME)
            continue;
        goto fail;
    }

fail:
    fprintf(stderr, "dnprint: DAP print request failed\n");
    close(fd);
    return -1;
}

static int submit_file(const char *node_text, const char *filespec,
                       const struct access_options *options)
{
    unsigned char msg[512], reply[512];
    size_t n = strlen(filespec);
    int fd;

    if (!n || n > 128U) {
        fprintf(stderr, "dnsubmit: invalid remote file specification\n");
        return -1;
    }
    fd = open_fal(node_text, options);
    if (fd < 0)
        return -1;
    if (exchange_config(fd))
        goto fail;

    msg[0] = DAP_ATTRIBUTES;
    msg[1] = 0U;
    msg[2] = 0U;
    if (send_record(fd, msg, 3U))
        goto fail;

    msg[0] = DAP_ACCESS;
    msg[1] = 0U;
    msg[2] = 8U; /* SUBMIT */
    msg[3] = 0U; /* ACCOPT */
    msg[4] = (unsigned char)n;
    memcpy(msg + 5, filespec, n);
    if (send_record(fd, msg, n + 5U))
        goto fail;

    for (;;) {
        ssize_t got = recv_record(fd, reply, sizeof(reply), 0);

        if (got < 2)
            goto fail;
        if (reply[0] == DAP_STATUS) {
            report_status("submit", reply, (size_t)got);
            goto fail;
        }
        if (reply[0] == DAP_ACK || reply[0] == DAP_ACCESS_COMPLETE) {
            close(fd);
            return 0;
        }
        if (reply[0] == DAP_ATTRIBUTES || reply[0] == DAP_NAME)
            continue;
        goto fail;
    }

fail:
    fprintf(stderr, "dnsubmit: DAP submit failed\n");
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
        ssize_t got = recv_record(fd, reply, sizeof(reply), 0);

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

static int selftest_buffer_limit(void)
{
    unsigned char data[129];
    int pair[2] = { -1, -1 };
    ssize_t got;
    int rc = -1;

    memset(data, 0x5a, sizeof(data));
    if (socketpair(AF_UNIX, SOCK_SEQPACKET, 0, pair))
        return -1;
    dap_send_limit = 128U;
    if (send_record(pair[0], data, 128U) ||
        (got = recv_record(pair[1], data, 128U, 0)) != 128U)
        goto finish;
    errno = 0;
    if (send_record(pair[0], data, 129U) != -1 || errno != EMSGSIZE)
        goto finish;
    errno = 0;
    if (dniv_send_record(pair[0], data, 129U, 0) ||
        recv_record(pair[1], data, 129U, 0) != -1 ||
        errno != EMSGSIZE)
        goto finish;
    rc = 0;
finish:
    dap_send_limit = DAP_BUFFER_LIMIT;
    close(pair[0]);
    close(pair[1]);
    return rc;
}

static int selftest_socket_timeouts(void)
{
    int pair[2] = { -1, -1 };
    struct timeval actual;
    socklen_t length;
    int ok;

    if (socketpair(AF_UNIX, SOCK_SEQPACKET, 0, pair))
        return -1;
    if (set_dap_timeouts(pair[0])) {
        close(pair[0]);
        close(pair[1]);
        return -1;
    }
    length = sizeof(actual);
    ok = !getsockopt(pair[0], SOL_SOCKET, SO_RCVTIMEO,
                     &actual, &length) &&
         length == sizeof(actual) &&
         actual.tv_sec == DAP_IO_TIMEOUT_SECONDS && !actual.tv_usec;
    length = sizeof(actual);
    ok = ok && !getsockopt(pair[0], SOL_SOCKET, SO_SNDTIMEO,
                           &actual, &length) &&
         length == sizeof(actual) &&
         actual.tv_sec == DAP_IO_TIMEOUT_SECONDS && !actual.tv_usec;
    close(pair[0]);
    close(pair[1]);
    return ok ? 0 : -1;
}

static int selftest_text_records(void)
{
    static const unsigned char invalid[] = { 'a', 'b', 0U, 'c', 'd', '\n' };
    static const unsigned char line[] = { 'o', 'k', '\r', '\n', '\n', 'x' };
    unsigned char data[1024];
    size_t len = 0U;
    FILE *in = tmpfile();
    int rc = -1;

    if (!in)
        return -1;
    if (fwrite(invalid, 1, sizeof(invalid), in) != sizeof(invalid) ||
        fseek(in, 0, SEEK_SET))
        goto out;
    errno = 0;
    if (read_text_record(in, data, sizeof(data), &len) != -1 ||
        errno != EILSEQ)
        goto out;
    if (fclose(in))
        return -1;
    in = tmpfile();
    if (!in)
        return -1;
    if (fwrite(line, 1, sizeof(line), in) != sizeof(line) ||
        fseek(in, 0, SEEK_SET))
        goto out;
    if (read_text_record(in, data, sizeof(data), &len) != 1 ||
        len != 2U || memcmp(data, "ok", 2U) ||
        read_text_record(in, data, sizeof(data), &len) != 1 || len != 0U ||
        read_text_record(in, data, sizeof(data), &len) != 1 ||
        len != 1U || data[0] != 'x' ||
        read_text_record(in, data, sizeof(data), &len) != 0)
        goto out;
    if (fclose(in))
        return -1;
    in = tmpfile();
    if (!in)
        return -1;
    if (fwrite("x\r", 1, 2U, in) != 2U || fseek(in, 0, SEEK_SET) ||
        read_text_record(in, data, sizeof(data), &len) != 1 ||
        len != 2U || memcmp(data, "x\r", 2U) ||
        read_text_record(in, data, sizeof(data), &len) != 0)
        goto out;
    if (fclose(in))
        return -1;
    in = tmpfile();
    if (!in)
        return -1;
    memset(data, 'q', sizeof(data));
    if (fwrite(data, 1, sizeof(data), in) != sizeof(data) ||
        fseek(in, 0, SEEK_SET) ||
        read_text_record(in, data, sizeof(data), &len) != 1 ||
        len != sizeof(data) ||
        read_text_record(in, data, sizeof(data), &len) != 0)
        goto out;
    if (fseek(in, 0, SEEK_END) || fputc('z', in) == EOF ||
        fseek(in, 0, SEEK_SET))
        goto out;
    errno = 0;
    if (read_text_record(in, data, sizeof(data), &len) != -1 ||
        errno != E2BIG)
        goto out;
    rc = 0;
out:
    fclose(in);
    return rc;
}

static int selftest_staged_output(void)
{
    char directory[] = "/tmp/dncopy-staged.XXXXXX";
    char target[128], alias[128];
    char contents[32];
    FILE *out = NULL;
    char *staged = NULL;
    int fd = -1;
    int rc = -1;
    int existed = 0;

    if (!mkdtemp(directory))
        return -1;
    if (snprintf(target, sizeof(target), "%s/target", directory) >=
        (int)sizeof(target) ||
        snprintf(alias, sizeof(alias), "%s/alias", directory) >=
        (int)sizeof(alias))
        goto cleanup;
    fd = open(target, O_CREAT | O_EXCL | O_WRONLY, 0644);
    if (fd < 0 || write(fd, "ORIGINAL", 8U) != 8)
        goto cleanup;
    close(fd);
    fd = -1;
    if (begin_staged_output(target, &out, &staged, &existed) ||
        !existed || fwrite("PARTIAL", 1, 7U, out) != 7U)
        goto cleanup;
    abort_staged_output(&out, &staged);
    fd = open(target, O_RDONLY);
    if (fd < 0 || read(fd, contents, sizeof(contents)) != 8 ||
        memcmp(contents, "ORIGINAL", 8U))
        goto cleanup;
    close(fd);
    fd = -1;
    if (begin_staged_output(target, &out, &staged, &existed) ||
        !existed || fwrite("COMPLETED", 1, 9U, out) != 9U ||
        publish_staged_output(&out, &staged, target, existed))
        goto cleanup;
    fd = open(target, O_RDONLY);
    if (fd < 0 || read(fd, contents, sizeof(contents)) != 9 ||
        memcmp(contents, "COMPLETED", 9U))
        goto cleanup;
    close(fd);
    fd = -1;
    if (symlink(target, alias))
        goto cleanup;
    errno = 0;
    if (!begin_staged_output(alias, &out, &staged, &existed) || errno != EACCES)
        goto cleanup;
    rc = 0;
cleanup:
    if (fd >= 0)
        close(fd);
    abort_staged_output(&out, &staged);
    unlink(alias);
    unlink(target);
    rmdir(directory);
    return rc;
}

/* No in-progress text may be readable through a public staging path.
 * If the requested name appears while a new download is in flight, the
 * external writer's bytes must survive the failed publication unchanged.
 */
static int selftest_staged_private_collision(void)
{
    char directory[] = "/tmp/dncopy-private.XXXXXX";
    char destination[256], private_dir[256], data[32] = { 0 };
    char *stage = NULL;
    FILE *out = NULL;
    struct stat info;
    int existed = -1;
    int fd = -1;
    int rc = -1;
    int saved;
    char *leaf;

    if (!mkdtemp(directory))
        return -1;
    if (chmod(directory, 0755) ||
        snprintf(destination, sizeof(destination), "%s/dest", directory) >=
        (int)sizeof(destination))
        goto done;
    /* First, preserve a concurrent creator's name and content. */
    if (begin_staged_output(destination, &out, &stage, &existed) || existed ||
        fwrite("TRANSFER", 1, 8U, out) != 8U ||
        strlen(stage) >= sizeof(private_dir))
        goto done;
    strcpy(private_dir, stage);
    leaf = strrchr(private_dir, '/');
    if (!leaf)
        goto done;
    *leaf = '\0';
    if (stat(private_dir, &info) || !S_ISDIR(info.st_mode) ||
        (info.st_mode & 0777) != 0700)
        goto done;
    fd = open(destination, O_WRONLY | O_CREAT | O_EXCL, 0600);
    if (fd < 0 || write(fd, "OTHER_WRITER", 12U) != 12)
        goto done;
    close(fd);
    fd = -1;
    errno = 0;
    if (publish_staged_output(&out, &stage, destination, existed) != -1 ||
        errno != EEXIST || !stat(private_dir, &info) || errno != ENOENT)
        goto done;
    fd = open(destination, O_RDONLY);
    if (fd < 0 || read(fd, data, sizeof(data)) != 12 ||
        memcmp(data, "OTHER_WRITER", 12U))
        goto done;
    close(fd);
    fd = -1;
    if (unlink(destination))
        goto done;

    /* An uncontended new destination still publishes atomically. */
    if (begin_staged_output(destination, &out, &stage, &existed) || existed ||
        fwrite("TRANSFER", 1, 8U, out) != 8U ||
        publish_staged_output(&out, &stage, destination, existed))
        goto done;
    fd = open(destination, O_RDONLY);
    if (fd < 0 || read(fd, data, sizeof(data)) != 8 ||
        memcmp(data, "TRANSFER", 8U))
        goto done;
    rc = 0;
done:
    saved = errno;
    if (fd >= 0)
        close(fd);
    abort_staged_output(&out, &stage);
    unlink(destination);
    rmdir(directory);
    errno = saved;
    return rc;
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
    const unsigned char attr_rfm_zero[] = { DAP_ATTRIBUTES, 0U, 0x04U, 0U };
    const unsigned char attr_rfm_unsupported[] = { DAP_ATTRIBUTES, 0U, 0x04U, 0xffU };
    const unsigned char attr_bad_menu[] = {
        DAP_ATTRIBUTES, 0U, 0x80U, 0x80U, 0x80U, 0x80U, 0x80U, 0x80U
    };
    unsigned char attr[16];
    unsigned char parsed_rfm;
    unsigned char parsed_rat;
    size_t attr_len;
    uint16_t addr;
    uint16_t status;
    unsigned int mac;
    unsigned int mic;
    struct remote_spec remote;
    struct access_options parsed_options = { 0 };

    if (selftest_buffer_limit() || selftest_socket_timeouts() ||
        selftest_text_records() || selftest_staged_output() ||
        selftest_staged_private_collision())
        return 1;
    if (parse_node("31.70", &addr) || addr != (uint16_t)((31U << 10) | 70U))
        return 1;
    if (!parse_node("0.1", &addr) || !parse_node("64.1", &addr) ||
        !parse_node("31.0", &addr))
        return 1;
    if (make_config(config, sizeof(config)) != 12U ||
        config[0] != DAP_CONFIG || config[2] != 0 || config[3] != 8 ||
        config[6] != 4 || config[7] != 1 || validate_config(config, 12U))
        return 1;
    config[2] = 128U;
    config[3] = 0U;
    if (validate_config(config, 12U) ||
        negotiate_buffer_limit(config, 12U, &dap_send_limit) ||
        dap_send_limit != 128U)
        return 1;
    config[2] = 0U;
    if (validate_config(config, 12U) ||
        negotiate_buffer_limit(config, 12U, &dap_send_limit) ||
        dap_send_limit != DAP_BUFFER_LIMIT)
        return 1;
    config[2] = 11U;
    if (!validate_config(config, 12U))
        return 1;
    dap_send_limit = DAP_BUFFER_LIMIT;
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
            !parse_rfm(attr_rfm_zero, sizeof(attr_rfm_zero), &rfm) ||
            !parse_rfm(attr_rfm_unsupported, sizeof(attr_rfm_unsupported), &rfm) ||
            !parse_rfm(attr_bad_menu, sizeof(attr_bad_menu), &rfm))
            return 1;
    }
    {
        int env_text_mode = 1;
        int env_metadata = 0;
        unsigned char env_rfm = DAP_RFM_VAR;
        unsigned char env_rat = DAP_RAT_CR;

        if (apply_transfer_env("-mblock -rvfc -c none", &env_text_mode,
                               &env_rfm, &env_rat, &env_metadata) ||
            env_text_mode != 0 || env_rfm != DAP_RFM_VFC ||
            env_rat != DAP_RAT_NONE || env_metadata != 1 ||
            !apply_transfer_env("-mbogus", &env_text_mode, &env_rfm,
                                &env_rat, &env_metadata))
            return 1;
    }
    if (parse_store_rfm("vfc", &parsed_rfm) || parsed_rfm != DAP_RFM_VFC ||
        parse_store_rfm("stmlf", &parsed_rfm) || parsed_rfm != DAP_RFM_STMLF ||
        !parse_store_rfm("bogus", &parsed_rfm) ||
        parse_store_rat("none", &parsed_rat) || parsed_rat != DAP_RAT_NONE ||
        parse_store_rat("prn", &parsed_rat) || parsed_rat != DAP_RAT_PRN ||
        !parse_store_rat("bogus", &parsed_rat))
        return 1;
    attr_len = make_store_attributes(attr, sizeof(attr), 1,
                                     DAP_RFM_VFC, DAP_RAT_PRN);
    if (attr_len != 7U || memcmp(attr,
            (const unsigned char[]){ DAP_ATTRIBUTES, 0U, 0x0fU, 0x01U,
                                     0U, DAP_RFM_VFC, DAP_RAT_PRN }, 7U))
        return 1;
    attr_len = make_store_attributes(attr, sizeof(attr), 0,
                                     DAP_RFM_VAR, DAP_RAT_CR);
    if (attr_len != 3U || memcmp(attr,
            (const unsigned char[]){ DAP_ATTRIBUTES, 0U, 0U }, 3U))
        return 1;
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
    struct access_options options = {
        .user = getenv("DNACCESS_USER"),
        .password = getenv("DNACCESS_PASSWORD"),
        .account = getenv("DNACCESS_ACCOUNT")
    };
    const char *mode;
    const char *prog;
    struct remote_spec remote;
    unsigned char store_rfm = DAP_RFM_VAR;
    unsigned char store_rat = DAP_RAT_CR;
    int metadata_override = 0;
    int text_mode = 1;
    int arg = 1;
    const char *env_options;

    prog = strrchr(argv[0], '/');
    prog = prog ? prog + 1 : argv[0];

    if (options.user && !options.user[0])
        options.user = NULL;
    if (options.password && !options.password[0])
        options.password = NULL;
    if (options.account && !options.account[0])
        options.account = NULL;
    env_options = getenv("DNCOPY_OPTIONS");
    if (apply_transfer_env(env_options, &text_mode, &store_rfm, &store_rat,
                           &metadata_override)) {
        fprintf(stderr, "dncopy: invalid DNCOPY_OPTIONS\n");
        return 2;
    }

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
        if ((!strcmp(argv[arg], "-m") || !strcmp(argv[arg], "-r") ||
             !strcmp(argv[arg], "-c")) && arg + 1 < argc) {
            if (apply_transfer_option(argv[arg], argv[arg + 1], &text_mode,
                                      &store_rfm, &store_rat,
                                      &metadata_override))
                goto usage;
            arg += 2;
            continue;
        }
        if ((argv[arg][1] == 'm' || argv[arg][1] == 'r' ||
             argv[arg][1] == 'c') && argv[arg][2]) {
            char name[3] = { '-', argv[arg][1], '\0' };

            if (apply_transfer_option(name, argv[arg] + 2, &text_mode,
                                      &store_rfm, &store_rat,
                                      &metadata_override))
                goto usage;
            arg++;
            continue;
        }
        goto usage;
    }
    if (!strcmp(prog, "dntype")) {
        if (arg + 1 == argc && strstr(argv[arg], "::")) {
            if (parse_transparent_spec(argv[arg], &remote, &options) ||
                !remote.file[0])
                goto usage;
            return retrieve_file(remote.node, remote.file, NULL, text_mode,
                                 &options) ? 1 : 0;
        }
        if (arg + 2 == argc)
            return retrieve_file(argv[arg], argv[arg + 1], NULL, text_mode,
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
    if (!strcmp(prog, "dnprint")) {
        if (arg + 1 == argc && strstr(argv[arg], "::")) {
            if (parse_transparent_spec(argv[arg], &remote, &options) ||
                !remote.file[0])
                goto usage;
            return print_file(remote.node, remote.file, &options) ? 1 : 0;
        }
        if (arg + 2 == argc)
            return print_file(argv[arg], argv[arg + 1], &options) ? 1 : 0;
        goto usage;
    }
    if (!strcmp(prog, "dnsubmit")) {
        if (arg + 1 == argc && strstr(argv[arg], "::")) {
            if (parse_transparent_spec(argv[arg], &remote, &options) ||
                !remote.file[0])
                goto usage;
            return submit_file(remote.node, remote.file, &options) ? 1 : 0;
        }
        if (arg + 2 == argc)
            return submit_file(argv[arg], argv[arg + 1], &options) ? 1 : 0;
        goto usage;
    }
    if (!strcmp(prog, "dnrename")) {
        if (arg + 3 == argc)
            return rename_file(argv[arg], argv[arg + 1], argv[arg + 2],
                               &options) ? 1 : 0;
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
            return retrieve_file(remote.node, remote.file, argv[arg + 1],
                                 text_mode, &options) ? 1 : 0;
        }
        if (parse_transparent_spec(argv[arg + 1], &remote, &options) ||
            !remote.file[0])
            goto usage;
        return store_file(argv[arg], remote.node, remote.file, text_mode,
                          store_rfm, store_rat, metadata_override,
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
                          store_rfm, store_rat, metadata_override,
                          &options) ? 1 : 0;
    if (!strcmp(mode, "--put-text") && arg + 3 == argc)
        return store_file(argv[arg], argv[arg + 1], argv[arg + 2], 1,
                          store_rfm, store_rat, metadata_override,
                          &options) ? 1 : 0;
    if (!strcmp(mode, "--dir") && arg + 2 == argc)
        return list_directory(argv[arg], argv[arg + 1], &options) ? 1 : 0;
    if (!strcmp(mode, "--delete") && arg + 2 == argc)
        return delete_file(argv[arg], argv[arg + 1], &options) ? 1 : 0;
usage:
    if (!strcmp(prog, "dntype")) {
        fprintf(stderr, "usage: dntype [-u USER] [-p PASSWORD] [-a ACCOUNT] [-m record|block] AREA.NODE FILE | 'AREA.NODE[\"USER PASS ACCOUNT\"]::FILE'\n");
    } else if (!strcmp(prog, "dndir")) {
        fprintf(stderr, "usage: dndir [-u USER] [-p PASSWORD] [-a ACCOUNT] [-m record|block] AREA.NODE [SPEC] | 'AREA.NODE[\"USER PASS ACCOUNT\"]::[SPEC]'\n");
    } else if (!strcmp(prog, "dnprint")) {
        fprintf(stderr, "usage: dnprint [-u USER] [-p PASSWORD] [-a ACCOUNT] AREA.NODE FILE | AREA.NODE::FILE\n");
    } else if (!strcmp(prog, "dnsubmit")) {
        fprintf(stderr, "usage: dnsubmit [-u USER] [-p PASSWORD] [-a ACCOUNT] AREA.NODE FILE | AREA.NODE::FILE\n");
    } else if (!strcmp(prog, "dnrename")) {
        fprintf(stderr, "usage: dnrename [-u USER] [-p PASSWORD] [-a ACCOUNT] AREA.NODE OLD NEW\n");
    } else if (!strcmp(prog, "dndel")) {
        fprintf(stderr, "usage: dndel [-u USER] [-p PASSWORD] [-a ACCOUNT] [-m record|block] AREA.NODE FILE | 'AREA.NODE[\"USER PASS ACCOUNT\"]::FILE'\n");
    } else {
        fprintf(stderr,
                "usage: %s [-u USER] [-p PASSWORD] [-a ACCOUNT] [-m record|block] "
                "[-r fix|var|vfc|stm|stmlf|stmcr] [-c none|ftn|cr|prn] "
                "--selftest | --probe AREA.NODE | --get AREA.NODE FILE | "
                "--get-text AREA.NODE FILE | --get-to AREA.NODE FILE LOCAL | "
                "--put LOCAL AREA.NODE REMOTE | --put-text LOCAL AREA.NODE REMOTE | "
                "--dir AREA.NODE SPEC | --delete AREA.NODE FILE | "
                "SOURCE DEST (one transparent AREA.NODE::FILE)\n"
                "DNCOPY_OPTIONS may set default -m/-r/-c transfer options.\n"
                "DNACCESS_USER, DNACCESS_PASSWORD and DNACCESS_ACCOUNT provide "
                "non-command-line access defaults.\n",
                argv[0]);
    }
    return 2;
}
