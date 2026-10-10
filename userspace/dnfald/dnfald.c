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

#include <dirent.h>
#include <fcntl.h>
#include <errno.h>
#include <fnmatch.h>
#include <linux/dn.h>
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <sys/wait.h>
#include <sys/xattr.h>
#include <unistd.h>

#include "../common/record_io.h"

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
#define DAP_RFM_VAR 2U
#define DAP_RFM_VFC 3U
#define DAP_RFM_STM 4U
#define DAP_RFM_STMLF 5U
#define DAP_RFM_STMCR 6U
#define DAP_RAT_MAX 7U
#define DNFAL_XATTR_RFM "user.decnet.rfm"
#define DNFAL_XATTR_RAT "user.decnet.rat"
/* Internal on-disk framing for variable-length DAP logical records.
 * Version 1 stores each complete record as uint16 little-endian length
 * followed by its exact bytes, including zero-length records. */
#define DNFAL_XATTR_RECORD_FRAMING "user.decnet.record-framing"
#define DNFAL_RECORD_FRAMING_V1 '1' 
#define DAP_ACCESS_OPEN 1U
#define DAP_ACCESS_CREATE 2U
#define DAP_ACCESS_RENAME 3U
#define DAP_ACCESS_ERASE 4U
#define DAP_ACCESS_DIRECTORY 6U
#define DAP_CONTROL_GET 1U
#define DAP_CONTROL_CONNECT 2U
#define DAP_CONTROL_PUT 4U
#define DAP_ACCOMP_CLOSE 1U
#define DAP_ACCOMP_RESPONSE 2U
#define DNFAL_BACKLOG 8
#define DAP_BUFFER_LIMIT 2048U

/* dnfald handles one accepted session at a time (no per-session threads).
 * Every outbound DAP frame is bounded by the negotiated peer buffer size. */
static size_t dap_send_limit = DAP_BUFFER_LIMIT;

static int negotiate_buffer_limit(const unsigned char *config, size_t len,
                                  size_t *limit)
{
    size_t peer;

    if (!limit || len < 12U || config[0] != DAP_CONFIG ||
        (config[1] & 0x7fU))
        return -1;
    peer = (size_t)config[2] | ((size_t)config[3] << 8U);
    /* The protocol defines zero as unlimited, not as no room to send. */
    if (peer && peer < 12U)
        return -1;
    *limit = !peer || peer > DAP_BUFFER_LIMIT ? DAP_BUFFER_LIMIT : peer;
    return 0;
}

static size_t make_config(unsigned char *buf, size_t cap)
{
    if (cap < 12U)
        return 0U;
    buf[0] = DAP_CONFIG;
    buf[1] = 0U;
    buf[2] = 0U;
    buf[3] = 8U; /* 2048-byte maximum complete DAP message */
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
    size_t limit;

    return negotiate_buffer_limit(buf, len, &limit);
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

/* DAP ATTRIBUTES ATTMENU and DATATYPE/RAT are extensible bitmaps.
 * Decode the well-defined first eight attributes in protocol field order.
 * Higher menu fields are not implemented; reject them rather than treating
 * their wire values as lower-field offsets or silently misparsing RFM. */
static int parse_attr_ex(const unsigned char *buf, size_t len,
                         size_t *pos, unsigned int max_bytes,
                         uint64_t *value)
{
    uint64_t bits = 0U;
    unsigned int i;

    for (i = 0; i < max_bytes; i++) {
        unsigned char byte;

        if (*pos >= len)
            return -1;
        byte = buf[(*pos)++];
        bits |= (uint64_t)(byte & 0x7fU) << (7U * i);
        if (!(byte & 0x80U)) {
            *value = bits;
            return 0;
        }
    }
    return -1;
}

static int parse_attributes(const unsigned char *buf, size_t len,
                            unsigned char *rfm, unsigned char *rat)
{
    uint64_t menu, value;
    size_t pos = 2U;

    *rfm = DAP_RFM_FIX;
    *rat = 0U;
    if (len < 3U || buf[0] != DAP_ATTRIBUTES || buf[1] != 0U ||
        parse_attr_ex(buf, len, &pos, 6U, &menu) || (menu & ~0xffULL))
        return -1;
    if ((menu & 0x01U) &&
        parse_attr_ex(buf, len, &pos, 2U, &value)) /* DATATYPE */
        return -1;
    if (menu & 0x02U) { /* ORG */
        if (pos >= len)
            return -1;
        pos++;
    }
    if (menu & 0x04U) { /* RFM */
        if (pos >= len)
            return -1;
        *rfm = buf[pos++];
        if (*rfm < DAP_RFM_FIX || *rfm > DAP_RFM_STMCR)
            return -1;
    }
    if (menu & 0x08U) { /* RAT is EX-3, not a fixed byte. */
        if (parse_attr_ex(buf, len, &pos, 3U, &value) ||
            value > DAP_RAT_MAX)
            return -1;
        *rat = (unsigned char)value;
    }
    if (menu & 0x10U) { /* BLS(2) */
        if (len - pos < 2U)
            return -1;
        pos += 2U;
    }
    if (menu & 0x20U) { /* MRS(2) */
        if (len - pos < 2U)
            return -1;
        pos += 2U;
    }
    if (menu & 0x40U) { /* ALQ(I-5) */
        size_t n;

        if (pos >= len)
            return -1;
        n = buf[pos++];
        if (n > 5U || n > len - pos)
            return -1;
        pos += n;
    }
    if (menu & 0x80U) { /* BKS(1), following the EX continuation */
        if (pos >= len)
            return -1;
        pos++;
    }
    return pos == len ? 0 : -1;
}

static size_t make_attributes(unsigned char *buf, size_t cap,
                              unsigned char rfm, unsigned char rat)
{
    if (rfm == DAP_RFM_FIX && rat == 0U) {
        if (cap < 4U)
            return 0U;
        buf[0] = DAP_ATTRIBUTES;
        buf[1] = 0U;
        buf[2] = 0x04U;
        buf[3] = DAP_RFM_FIX;
        return 4U;
    }
    if (cap < 7U)
        return 0U;
    buf[0] = DAP_ATTRIBUTES;
    buf[1] = 0U;
    buf[2] = 0x0fU;
    buf[3] = 1U;
    buf[4] = 0U;
    buf[5] = rfm;
    buf[6] = rat;
    return 7U;
}

static int load_metadata(int fd, unsigned char *rfm, unsigned char *rat)
{
    ssize_t got;

    *rfm = DAP_RFM_FIX;
    *rat = 0U;
    got = fgetxattr(fd, DNFAL_XATTR_RFM, rfm, 1U);
    if (got < 0 && errno != ENODATA && errno != ENOTSUP)
        return -1;
    if (got > 0 && got != 1)
        return -1;
    got = fgetxattr(fd, DNFAL_XATTR_RAT, rat, 1U);
    if (got < 0 && errno != ENODATA && errno != ENOTSUP)
        return -1;
    if (got > 0 && got != 1)
        return -1;
    /* xattrs are local storage, not trusted DAP wire values. Reject
     * corrupted/forged metadata before advertising an illegal RFM or RAT. */
    if (*rfm < DAP_RFM_FIX || *rfm > DAP_RFM_STMCR || *rat > DAP_RAT_MAX) {
        errno = EPROTO;
        return -1;
    }
    return 0;
}

static int save_metadata(int fd, unsigned char rfm, unsigned char rat)
{
    return fsetxattr(fd, DNFAL_XATTR_RFM, &rfm, 1U, 0) ||
           fsetxattr(fd, DNFAL_XATTR_RAT, &rat, 1U, 0) ? -1 : 0;
}

static int record_oriented_rfm(unsigned char rfm)
{
    return rfm == DAP_RFM_VAR || rfm == DAP_RFM_VFC;
}

static int interpret_record_framing(ssize_t len, int xattr_errno,
                                    const unsigned char *value,
                                    unsigned char rfm, int *framed)
{
    *framed = 0;
    if (len < 0 && (xattr_errno == ENODATA ||
                    xattr_errno == EOPNOTSUPP)) {
        /* A VAR/VFC file without the private frame marker has no known
         * logical DATA boundaries. Serving arbitrary raw read chunks while
         * advertising VAR/VFC fabricates record boundaries and corrupts
         * record-mode downloads. Never guess: reject ambiguous metadata. */
        if (record_oriented_rfm(rfm)) {
            errno = EPROTO;
            return -1;
        }
        return 0;
    }
    if (len != 1 || value[0] != DNFAL_RECORD_FRAMING_V1 ||
        !record_oriented_rfm(rfm)) {
        errno = EPROTO;
        return -1;
    }
    *framed = 1;
    return 0;
}

static int load_record_framing(int fd, unsigned char rfm, int *framed)
{
    unsigned char value[2];
    ssize_t len = fgetxattr(fd, DNFAL_XATTR_RECORD_FRAMING,
                            value, sizeof(value));
    int error = errno;

    return interpret_record_framing(len, error, value, rfm, framed);
}

static int save_record_framing(int fd, unsigned char rfm)
{
    const unsigned char value = DNFAL_RECORD_FRAMING_V1;

    return !record_oriented_rfm(rfm) ? 0 :
        fsetxattr(fd, DNFAL_XATTR_RECORD_FRAMING, &value, 1U, 0);
}

static int write_framed_payload(FILE *out, const unsigned char *payload,
                                size_t len)
{
    unsigned char prefix[2];

    if (len > UINT16_MAX) {
        errno = EOVERFLOW;
        return -1;
    }
    prefix[0] = (unsigned char)len;
    prefix[1] = (unsigned char)(len >> 8U);
    if (fwrite(prefix, 1, sizeof(prefix), out) != sizeof(prefix) ||
        (len && fwrite(payload, 1, len, out) != len))
        return -1;
    return 0;
}

/* 1: record, 0: clean EOF, -1: truncated/corrupted/oversize record. */
static int read_framed_payload(FILE *in, unsigned char *payload, size_t cap,
                               size_t *len)
{
    unsigned char prefix[2];
    size_t n = fread(prefix, 1, sizeof(prefix), in);

    if (!n)
        return ferror(in) ? -1 : 0;
    if (n != sizeof(prefix)) {
        errno = EPROTO;
        return -1;
    }
    *len = (size_t)prefix[0] | ((size_t)prefix[1] << 8U);
    if (*len > cap) {
        errno = EMSGSIZE;
        return -1;
    }
    if (*len && fread(payload, 1, *len, in) != *len) {
        errno = EPROTO;
        return -1;
    }
    return 1;
}

static int open_regular_at(int rootfd, const char *name, int write_file)
{
    struct stat st;
    int flags = O_NOFOLLOW | O_CLOEXEC | O_NONBLOCK;
    int fd;

    if (write_file)
        flags |= O_WRONLY | O_CREAT | O_EXCL;
    else
        flags |= O_RDONLY;
    fd = openat(rootfd, name, flags, 0666);
    if (fd < 0)
        return -1;
    if (fstat(fd, &st)) {
        int saved = errno;

        close(fd);
        errno = saved;
        return -1;
    }
    if (!S_ISREG(st.st_mode) || st.st_nlink != 1) {
        close(fd);
        errno = EACCES;
        return -1;
    }
    if (write_file && ftruncate(fd, 0)) {
        int saved = errno;

        close(fd);
        errno = saved;
        return -1;
    }
    return fd;
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

static int access_name(const unsigned char *request, size_t len,
                       unsigned char function, char *name, size_t name_cap)
{
    size_t n;

    if (len < 5U || request[0] != DAP_ACCESS || request[2] != function)
        return -1;
    n = request[4];
    if (len != n + 5U ||
        safe_filespec(request + 5U, n, name, name_cap))
        return -1;
    return 0;
}

static int serve_get(int fd, int rootfd,
                     const unsigned char *access, size_t access_len)
{
    unsigned char request[2048];
    unsigned char reply[2048];
    char name[256];
    FILE *in = NULL;
    int file_fd;
    unsigned char rfm;
    unsigned char rat;
    int framed;
    ssize_t got;

    if (access_name(access, access_len, DAP_ACCESS_OPEN,
                    name, sizeof(name)))
        return -1;
    file_fd = open_regular_at(rootfd, name, 0);
    if (file_fd < 0)
        return -1;
    in = fdopen(file_fd, "rb");
    if (!in) {
        close(file_fd);
        return -1;
    }

    {
        unsigned char attributes[16];
        const unsigned char ack[] = { DAP_ACK, 0U };
        size_t attr_len;

        if (load_metadata(fileno(in), &rfm, &rat) ||
            load_record_framing(fileno(in), rfm, &framed))
            goto fail;
        attr_len = make_attributes(attributes, sizeof(attributes), rfm, rat);
        if (!attr_len || send_record(fd, attributes, attr_len) ||
            send_record(fd, ack, sizeof(ack)))
            goto fail;
    }

    got = recv_record(fd, request, sizeof(request), 0);
    if (got != 3 || request[0] != DAP_CONTROL || request[2] != DAP_CONTROL_CONNECT)
        goto fail;
    {
        const unsigned char ack[] = { DAP_ACK, 0U };
        if (send_record(fd, ack, sizeof(ack)))
            goto fail;
    }

    got = recv_record(fd, request, sizeof(request), 0);
    if (got != 3 || request[0] != DAP_CONTROL || request[2] != DAP_CONTROL_GET)
        goto fail;

    for (;;) {
        size_t payload_cap = (sizeof(reply) < dap_send_limit ?
                              sizeof(reply) : dap_send_limit) - 3U;
        size_t count;

        if (framed) {
            int record = read_framed_payload(in, reply + 3U,
                                             payload_cap, &count);

            if (record < 0)
                goto fail;
            if (!record)
                break;
        } else {
            count = fread(reply + 3U, 1, payload_cap, in);
            if (!count && ferror(in))
                goto fail;
            if (!count)
                break;
        }
        reply[0] = DAP_DATA;
        reply[1] = 0U;
        reply[2] = 0U;
        if (send_record(fd, reply, count + 3U))
            goto fail;
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
    got = recv_record(fd, request, sizeof(request), 0);
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

static int serve_create(int fd, int rootfd,
                        const unsigned char *access, size_t access_len,
                        unsigned char requested_rfm,
                        unsigned char requested_rat)
{
    unsigned char request[2048];
    char name[256];
    FILE *out = NULL;
    int file_fd;
    ssize_t got;

    if (access_name(access, access_len, DAP_ACCESS_CREATE,
                    name, sizeof(name)))
        return -1;
    /* Stage privately. A named CREATE target can be renamed/replaced by a
     * concurrent writer before an aborted transfer tries to unlink it.
     * O_TMPFILE avoids exposing any partial name; link only after close.
     * Fail closed on filesystems without O_TMPFILE support.
     */
    file_fd = openat(rootfd, ".", O_TMPFILE | O_RDWR | O_CLOEXEC, 0666);
    if (file_fd < 0)
        return -1;
    out = fdopen(file_fd, "wb");
    if (!out) {
        close(file_fd);
        return -1;
    }

    {
        unsigned char attributes[16];
        const unsigned char ack[] = { DAP_ACK, 0U };
        size_t attr_len;

        if (save_metadata(fileno(out), requested_rfm, requested_rat) ||
            save_record_framing(fileno(out), requested_rfm))
            goto fail;
        attr_len = make_attributes(attributes, sizeof(attributes),
                                   requested_rfm, requested_rat);
        if (!attr_len || send_record(fd, attributes, attr_len) ||
            send_record(fd, ack, sizeof(ack)))
            goto fail;
    }

    got = recv_record(fd, request, sizeof(request), 0);
    if (got != 3 || request[0] != DAP_CONTROL ||
        request[2] != DAP_CONTROL_CONNECT)
        goto fail;
    {
        const unsigned char ack[] = { DAP_ACK, 0U };
        if (send_record(fd, ack, sizeof(ack)))
            goto fail;
    }

    got = recv_record(fd, request, sizeof(request), 0);
    if (got != 3 || request[0] != DAP_CONTROL ||
        request[2] != DAP_CONTROL_PUT)
        goto fail;

    for (;;) {
        size_t off;

        got = recv_record(fd, request, sizeof(request), 0);
        if (got < 2)
            goto fail;
        if (request[0] == DAP_DATA) {
            if (got < 3)
                goto fail;
            off = 3U + request[2];
            if (off > (size_t)got)
                goto fail;
            if (record_oriented_rfm(requested_rfm)) {
                if (write_framed_payload(out, request + off,
                                         (size_t)got - off))
                    goto fail;
            } else if ((size_t)got > off &&
                       fwrite(request + off, 1, (size_t)got - off, out) !=
                           (size_t)got - off) {
                goto fail;
            }
            continue;
        }
        if (request[0] == DAP_ACCESS_COMPLETE &&
            got == 3 && request[2] == DAP_ACCOMP_CLOSE)
            break;
        goto fail;
    }
    /* Keep the anonymous inode referenced across fclose() so that close
     * errors are known before atomic publication. An existing destination,
     * including one introduced during the upload, cannot be replaced.
     */
    if (fflush(out) || fsync(fileno(out)))
        goto fail;
    file_fd = fcntl(fileno(out), F_DUPFD_CLOEXEC, 0);
    if (file_fd < 0)
        goto fail;
    if (fclose(out)) {
        out = NULL;
        close(file_fd);
        return -1;
    }
    out = NULL;
    if (linkat(file_fd, "", rootfd, name, AT_EMPTY_PATH)) {
        close(file_fd);
        return -1;
    }
    /* The inode was synced and the stream closed before publishing. */
    close(file_fd);
    {
        const unsigned char complete[] = {
            DAP_ACCESS_COMPLETE, 0U, DAP_ACCOMP_RESPONSE
        };
        return send_record(fd, complete, sizeof(complete));
    }

fail:
    if (out)
        fclose(out);
    return -1;
}

static int serve_rename(int fd, int rootfd,
                        const unsigned char *access, size_t access_len)
{
    unsigned char request[512];
    char oldname[256];
    char newname[256];
    size_t n;
    ssize_t got;

    if (access_name(access, access_len, DAP_ACCESS_RENAME,
                    oldname, sizeof(oldname)))
        return -1;
    got = recv_record(fd, request, sizeof(request), 0);
    if (got < 4 || request[0] != 15U || request[2] != 1U)
        return -1;
    n = request[3];
    if ((size_t)got != n + 4U ||
        safe_filespec(request + 4U, n, newname, sizeof(newname)))
        return -1;
    if (renameat(rootfd, oldname, rootfd, newname))
        return -1;
    {
        const unsigned char complete[] = {
            DAP_ACCESS_COMPLETE, 0U, DAP_ACCOMP_RESPONSE
        };
        return send_record(fd, complete, sizeof(complete));
    }
}

static int safe_pattern(const unsigned char *text, size_t len,
                        char *out, size_t cap)
{
    size_t i;

    if (len >= cap)
        return -1;
    if (!len) {
        strcpy(out, "*");
        return 0;
    }
    for (i = 0; i < len; i++) {
        unsigned char c = text[i];

        if (c == '/' || c == '\\' || c == ':' || c == '[' || c == ']' ||
            c == ';' || c == '?' || c < 0x20U)
            return -1;
    }
    if (memmem(text, len, "..", 2U))
        return -1;
    memcpy(out, text, len);
    out[len] = '\0';
    if (!strcmp(out, "*.*"))
        strcpy(out, "*");
    return 0;
}

static int serve_directory(int fd, int rootfd,
                           const unsigned char *access, size_t access_len)
{
    unsigned char msg[512];
    char pattern[256];
    DIR *dir;
    struct dirent *ent;
    size_t n;

    if (access_len < 5U || access[0] != DAP_ACCESS ||
        access[2] != DAP_ACCESS_DIRECTORY)
        return -1;
    n = access[4];
    if (access_len != n + 5U ||
        safe_pattern(access + 5U, n, pattern, sizeof(pattern)))
        return -1;
    {
        int dirfd = dup(rootfd);

        if (dirfd < 0)
            return -1;
        dir = fdopendir(dirfd);
        if (!dir) {
            close(dirfd);
            return -1;
        }
    }
    for (;;) {
        size_t len;

        errno = 0;
        ent = readdir(dir);
        if (!ent) {
            int read_errno = errno;
            int close_rc = closedir(dir);

            if (read_errno) {
                errno = read_errno;
                return -1;
            }
            if (close_rc)
                return -1;
            break;
        }
        if (!strcmp(ent->d_name, ".") || !strcmp(ent->d_name, "..") ||
            ent->d_name[0] == '.' || fnmatch(pattern, ent->d_name, 0))
            continue;
        len = strlen(ent->d_name);
        if (len > 127U || len + 4U > sizeof(msg)) {
            (void)closedir(dir);
            errno = ENAMETOOLONG;
            return -1;
        }
        msg[0] = 15U;
        msg[1] = 0U;
        msg[2] = 1U;
        msg[3] = (unsigned char)len;
        memcpy(msg + 4U, ent->d_name, len);
        if (send_record(fd, msg, len + 4U)) {
            int saved_errno = errno;

            (void)closedir(dir);
            errno = saved_errno;
            return -1;
        }
    }
    {
        const unsigned char complete[] = {
            DAP_ACCESS_COMPLETE, 0U, DAP_ACCOMP_RESPONSE
        };
        return send_record(fd, complete, sizeof(complete));
    }
}

static int serve_erase(int fd, int rootfd,
                       const unsigned char *access, size_t access_len)
{
    char name[256];

    if (access_name(access, access_len, DAP_ACCESS_ERASE,
                    name, sizeof(name)))
        return -1;
    if (unlinkat(rootfd, name, 0))
        return -1;
    {
        const unsigned char complete[] = {
            DAP_ACCESS_COMPLETE, 0U, DAP_ACCOMP_RESPONSE
        };
        return send_record(fd, complete, sizeof(complete));
    }
}

static int serve_session(int fd, const char *root)
{
    struct timeval timeout = { .tv_sec = 30, .tv_usec = 0 };
    unsigned char request[256];
    unsigned char reply[32];
    unsigned char requested_rfm = DAP_RFM_FIX;
    unsigned char requested_rat = 0U;
    size_t reply_len;
    ssize_t got;
    int rootfd;
    int rc;

    if (setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)) < 0 ||
        setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout)) < 0)
        return -1;
    dap_send_limit = DAP_BUFFER_LIMIT;
    got = recv_record(fd, request, sizeof(request), 0);
    if (got < 0 ||
        negotiate_buffer_limit(request, (size_t)got, &dap_send_limit))
        return -1;
    reply_len = make_config(reply, sizeof(reply));
    if (!reply_len || send_record(fd, reply, reply_len))
        return -1;
    if (!root)
        return 0;
    rootfd = open(root, O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    if (rootfd < 0)
        return -1;

    got = recv_record(fd, request, sizeof(request), 0);
    if (got < 0) {
        rc = -1;
        goto out;
    }
    if (got >= 3 && request[0] == DAP_ATTRIBUTES) {
        if (parse_attributes(request, (size_t)got,
                             &requested_rfm, &requested_rat)) {
            rc = -1;
            goto out;
        }
        got = recv_record(fd, request, sizeof(request), 0);
        if (got < 0) {
            rc = -1;
            goto out;
        }
    }
    if (got < 5 || request[0] != DAP_ACCESS) {
        rc = -1;
        goto out;
    }
    if (request[2] == DAP_ACCESS_OPEN)
        rc = serve_get(fd, rootfd, request, (size_t)got);
    else if (request[2] == DAP_ACCESS_CREATE)
        rc = serve_create(fd, rootfd, request, (size_t)got,
                          requested_rfm, requested_rat);
    else if (request[2] == DAP_ACCESS_RENAME)
        rc = serve_rename(fd, rootfd, request, (size_t)got);
    else if (request[2] == DAP_ACCESS_DIRECTORY)
        rc = serve_directory(fd, rootfd, request, (size_t)got);
    else if (request[2] == DAP_ACCESS_ERASE)
        rc = serve_erase(fd, rootfd, request, (size_t)got);
    else
        rc = -1;
out:
    close(rootfd);
    return rc;
}

/* Exercise the real GET path against a peer advertising only 128 bytes, not
 * merely the static frame-construction helper. The original implementation
 * put 2048 bytes in one DATA record despite advertising only 1024. */
static int selftest_get_buffer_limit(int rootfd)
{
    const char *name = "CAP.TXT";
    const unsigned char access[] = {
        DAP_ACCESS, 0U, DAP_ACCESS_OPEN, 0U, 7U,
        'C', 'A', 'P', '.', 'T', 'X', 'T'
    };
    const unsigned char connect[] = { DAP_CONTROL, 0U, DAP_CONTROL_CONNECT };
    const unsigned char get[] = { DAP_CONTROL, 0U, DAP_CONTROL_GET };
    const unsigned char finish[] = { DAP_ACCESS_COMPLETE, 0U, DAP_ACCOMP_CLOSE };
    unsigned char fill[4096], record[256];
    struct timeval timeout = { .tv_sec = 4, .tv_usec = 0 };
    int pair[2] = { -1, -1 }, fd = -1, status, rc = -1;
    pid_t child = -1;
    size_t total = 0U, frames = 0U;
    ssize_t got;

    memset(fill, 'Q', sizeof(fill));
    fd = openat(rootfd, name, O_CREAT | O_EXCL | O_WRONLY | O_CLOEXEC, 0600);
    if (fd < 0)
        return -1;
    if (write(fd, fill, sizeof(fill)) != (ssize_t)sizeof(fill))
        goto cleanup;
    if (close(fd)) {
        fd = -1;
        goto cleanup;
    }
    fd = -1;
    if (socketpair(AF_UNIX, SOCK_SEQPACKET, 0, pair))
        goto cleanup;
    if (setsockopt(pair[0], SOL_SOCKET, SO_RCVTIMEO,
                   &timeout, sizeof(timeout)))
        goto cleanup;
    dap_send_limit = 128U;
    child = fork();
    if (child < 0)
        goto cleanup;
    if (!child) {
        int result;
        close(pair[0]);
        result = serve_get(pair[1], rootfd, access, sizeof(access));
        close(pair[1]);
        _exit(result ? 1 : 0);
    }
    close(pair[1]);
    pair[1] = -1;
    got = dniv_recv_record(pair[0], record, sizeof(record), 0);
    if (got < 4 || got > 128 || record[0] != DAP_ATTRIBUTES)
        goto cleanup;
    got = dniv_recv_record(pair[0], record, sizeof(record), 0);
    if (got != 2 || record[0] != DAP_ACK ||
        dniv_send_record(pair[0], connect, sizeof(connect), 0))
        goto cleanup;
    got = dniv_recv_record(pair[0], record, sizeof(record), 0);
    if (got != 2 || record[0] != DAP_ACK ||
        dniv_send_record(pair[0], get, sizeof(get), 0))
        goto cleanup;
    for (;;) {
        got = dniv_recv_record(pair[0], record, sizeof(record), 0);
        if (got < 0 || got > 128)
            goto cleanup;
        if (got == 4 && record[0] == DAP_STATUS)
            break;
        if (got < 4 || record[0] != DAP_DATA ||
            record[1] != 0U || record[2] != 0U)
            goto cleanup;
        for (size_t i = 3U; i < (size_t)got; i++)
            if (record[i] != 'Q')
                goto cleanup;
        total += (size_t)got - 3U;
        frames++;
        if (frames > 40U)
            goto cleanup;
    }
    if (total != sizeof(fill) || frames < 30U ||
        dniv_send_record(pair[0], finish, sizeof(finish), 0))
        goto cleanup;
    got = dniv_recv_record(pair[0], record, sizeof(record), 0);
    if (got != 3 || record[0] != DAP_ACCESS_COMPLETE ||
        record[2] != DAP_ACCOMP_RESPONSE)
        goto cleanup;
    rc = 0;
cleanup:
    if (fd >= 0)
        close(fd);
    if (pair[0] >= 0)
        close(pair[0]);
    if (pair[1] >= 0)
        close(pair[1]);
    if (child > 0) {
        if (rc)
            (void)kill(child, SIGKILL);
        if (waitpid(child, &status, 0) != child ||
            !WIFEXITED(status) || WEXITSTATUS(status))
            rc = -1;
    }
    dap_send_limit = DAP_BUFFER_LIMIT;
    (void)unlinkat(rootfd, name, 0);
    return rc;
}

/* Exercise the failed DAP CREATE path without a DECnet transport or remote peer. */
static int selftest_abort_create(int rootfd, const char *name)
{
    unsigned char access[5U + 255U] = {
        DAP_ACCESS, 0U, DAP_ACCESS_CREATE, 0U, 0U
    };
    size_t len = strlen(name);
    int pair[2];
    int rc;

    if (!len || len > 255U || socketpair(AF_UNIX, SOCK_SEQPACKET, 0, pair))
        return -1;
    access[4] = (unsigned char)len;
    memcpy(access + 5U, name, len);
    close(pair[1]);
    rc = serve_create(pair[0], rootfd, access, 5U + len,
                      DAP_RFM_FIX, 0U);
    close(pair[0]);
    return rc == -1 ? 0 : -1;
}

/* A peer can rename the just-created path, then put an unrelated file under
 * that name before transport failure. Aborted CREATE must preserve it.
 * This race regression requires neither a live DECnet socket nor privilege.
 */
static int selftest_create_swap(int rootfd)
{
    const char *name = "RACE.TXT";
    const unsigned char access[] = {
        DAP_ACCESS, 0U, DAP_ACCESS_CREATE, 0U, 8U,
        'R', 'A', 'C', 'E', '.', 'T', 'X', 'T'
    };
    unsigned char reply[32];
    struct timeval timeout = { .tv_sec = 5, .tv_usec = 0 };
    int pair[2] = { -1, -1 };
    int new_fd = -1;
    int read_fd = -1;
    int rc = -1;
    int status;
    pid_t child;

    if (socketpair(AF_UNIX, SOCK_SEQPACKET, 0, pair))
        return -1;
    if (setsockopt(pair[0], SOL_SOCKET, SO_RCVTIMEO,
                   &timeout, sizeof(timeout)))
        goto out;
    child = fork();
    if (child < 0)
        goto out;
    if (!child) {
        int result;

        close(pair[0]);
        result = serve_create(pair[1], rootfd, access, sizeof(access),
                              DAP_RFM_FIX, 0U);
        close(pair[1]);
        _exit(result == -1 ? 0 : 15);
    }
    close(pair[1]);
    pair[1] = -1;
    if (dniv_recv_record(pair[0], reply, sizeof(reply), 0) <= 0 ||
        dniv_recv_record(pair[0], reply, sizeof(reply), 0) <= 0)
        goto wait_child;
    /* Earlier CREATE exposed RACE.TXT before the transfer was complete. */
    if (faccessat(rootfd, name, F_OK, 0) == 0 &&
        renameat(rootfd, name, rootfd, "MOVED.TXT"))
        goto wait_child;
    new_fd = openat(rootfd, name,
                    O_CREAT | O_EXCL | O_WRONLY | O_CLOEXEC, 0600);
    if (new_fd < 0 || write(new_fd, "keep!", 5U) != 5)
        goto wait_child;
    close(new_fd);
    new_fd = -1;
    close(pair[0]);
    pair[0] = -1;
    if (waitpid(child, &status, 0) < 0 ||
        !WIFEXITED(status) || WEXITSTATUS(status))
        goto out;
    read_fd = openat(rootfd, name, O_RDONLY | O_NOFOLLOW | O_CLOEXEC);
    if (read_fd < 0 || read(read_fd, reply, 5U) != 5 ||
        memcmp(reply, "keep!", 5U))
        goto out;
    rc = 0;
    goto out;

wait_child:
    close(pair[0]);
    pair[0] = -1;
    (void)waitpid(child, &status, 0);
out:
    if (read_fd >= 0)
        close(read_fd);
    if (new_fd >= 0)
        close(new_fd);
    if (pair[0] >= 0)
        close(pair[0]);
    if (pair[1] >= 0)
        close(pair[1]);
    (void)unlinkat(rootfd, name, 0);
    (void)unlinkat(rootfd, "MOVED.TXT", 0);
    return rc;
}

/* A fully acknowledged upload must publish its complete bytes exactly once. */
static int selftest_create_success(int rootfd)
{
    const char *name = "COMMIT.TXT";
    const unsigned char access[] = {
        DAP_ACCESS, 0U, DAP_ACCESS_CREATE, 0U, 10U,
        'C', 'O', 'M', 'M', 'I', 'T', '.', 'T', 'X', 'T'
    };
    const unsigned char connect[] = { DAP_CONTROL, 0U, DAP_CONTROL_CONNECT };
    const unsigned char put[] = { DAP_CONTROL, 0U, DAP_CONTROL_PUT };
    const unsigned char data[] = { DAP_DATA, 0U, 0U, 'o', 'k', '!' };
    const unsigned char complete[] = {
        DAP_ACCESS_COMPLETE, 0U, DAP_ACCOMP_CLOSE
    };
    unsigned char reply[32];
    struct timeval timeout = { .tv_sec = 5, .tv_usec = 0 };
    int pair[2] = { -1, -1 };
    int read_fd = -1;
    int rc = -1;
    int status;
    pid_t child;

    if (socketpair(AF_UNIX, SOCK_SEQPACKET, 0, pair))
        return -1;
    if (setsockopt(pair[0], SOL_SOCKET, SO_RCVTIMEO,
                   &timeout, sizeof(timeout)))
        goto out;
    child = fork();
    if (child < 0)
        goto out;
    if (!child) {
        int result;

        close(pair[0]);
        result = serve_create(pair[1], rootfd, access, sizeof(access),
                              DAP_RFM_FIX, 0U);
        close(pair[1]);
        _exit(result == 0 ? 0 : 15);
    }
    close(pair[1]);
    pair[1] = -1;
    if (dniv_recv_record(pair[0], reply, sizeof(reply), 0) <= 0 ||
        dniv_recv_record(pair[0], reply, sizeof(reply), 0) <= 0 ||
        faccessat(rootfd, name, F_OK, 0) == 0 || errno != ENOENT ||
        dniv_send_record(pair[0], connect, sizeof(connect), 0) ||
        dniv_recv_record(pair[0], reply, sizeof(reply), 0) <= 0 ||
        dniv_send_record(pair[0], put, sizeof(put), 0) ||
        dniv_send_record(pair[0], data, sizeof(data), 0) ||
        dniv_send_record(pair[0], complete, sizeof(complete), 0) ||
        dniv_recv_record(pair[0], reply, sizeof(reply), 0) != 3 ||
        reply[0] != DAP_ACCESS_COMPLETE || reply[2] != DAP_ACCOMP_RESPONSE)
        goto wait_child;
    close(pair[0]);
    pair[0] = -1;
    if (waitpid(child, &status, 0) < 0 ||
        !WIFEXITED(status) || WEXITSTATUS(status))
        goto out;
    read_fd = openat(rootfd, name, O_RDONLY | O_NOFOLLOW | O_CLOEXEC);
    if (read_fd < 0 || read(read_fd, reply, sizeof(reply)) != 3 ||
        memcmp(reply, "ok!", 3U))
        goto out;
    rc = 0;
    goto out;

wait_child:
    close(pair[0]);
    pair[0] = -1;
    (void)waitpid(child, &status, 0);
out:
    if (read_fd >= 0)
        close(read_fd);
    if (pair[0] >= 0)
        close(pair[0]);
    if (pair[1] >= 0)
        close(pair[1]);
    (void)unlinkat(rootfd, name, 0);
    return rc;
}

/* A DATA message is a logical variable record, not an arbitrary piece of a
 * byte stream. Reopen the published inode through real FAL GET and assert
 * exact individual records (including the empty record) and EOF order. */
static int selftest_framed_records(int rootfd, unsigned char rfm)
{
    const char *name = "RECORD.DAT";
    const unsigned char create_access[] = {
        DAP_ACCESS, 0U, DAP_ACCESS_CREATE, 0U, 10U,
        'R', 'E', 'C', 'O', 'R', 'D', '.', 'D', 'A', 'T'
    };
    const unsigned char open_access[] = {
        DAP_ACCESS, 0U, DAP_ACCESS_OPEN, 0U, 10U,
        'R', 'E', 'C', 'O', 'R', 'D', '.', 'D', 'A', 'T'
    };
    const unsigned char connect[] = { DAP_CONTROL, 0U, DAP_CONTROL_CONNECT };
    const unsigned char put[] = { DAP_CONTROL, 0U, DAP_CONTROL_PUT };
    const unsigned char get[] = { DAP_CONTROL, 0U, DAP_CONTROL_GET };
    const unsigned char data1[] = { DAP_DATA, 0U, 0U, 'a', 'b', 'c' };
    const unsigned char data2[] = { DAP_DATA, 0U, 0U };
    const unsigned char data3[] = { DAP_DATA, 0U, 0U, 'd', 'e', 'f' };
    const unsigned char encoded[] = {
        3U, 0U, 'a', 'b', 'c', 0U, 0U, 3U, 0U, 'd', 'e', 'f'
    };
    const unsigned char finish[] = {
        DAP_ACCESS_COMPLETE, 0U, DAP_ACCOMP_CLOSE
    };
    const unsigned char eof[] = { DAP_STATUS, 0U, 0x27U, 0x40U };
    unsigned char reply[64];
    unsigned char bytes[sizeof(encoded)];
    unsigned char format[2];
    struct timeval timeout = { .tv_sec = 5, .tv_usec = 0 };
    int pair[2] = { -1, -1 };
    int file_fd = -1;
    pid_t child = -1;
    int status, rc = -1;
    int phase;

    for (phase = 0; phase < 2; phase++) {
        if (socketpair(AF_UNIX, SOCK_SEQPACKET, 0, pair))
            goto out;
        if (setsockopt(pair[0], SOL_SOCKET, SO_RCVTIMEO,
                       &timeout, sizeof(timeout)) ||
            setsockopt(pair[0], SOL_SOCKET, SO_SNDTIMEO,
                       &timeout, sizeof(timeout)))
            goto out;
        child = fork();
        if (child < 0)
            goto out;
        if (!child) {
            int result;

            close(pair[0]);
            result = phase == 0 ?
                serve_create(pair[1], rootfd, create_access,
                             sizeof(create_access), rfm, 2U) :
                serve_get(pair[1], rootfd, open_access,
                          sizeof(open_access));
            close(pair[1]);
            _exit(result == 0 ? 0 : 15);
        }
        close(pair[1]);
        pair[1] = -1;
        if (dniv_recv_record(pair[0], reply, sizeof(reply), 0) != 7 ||
            reply[0] != DAP_ATTRIBUTES || reply[5] != rfm ||
            dniv_recv_record(pair[0], reply, sizeof(reply), 0) != 2 ||
            reply[0] != DAP_ACK ||
            dniv_send_record(pair[0], connect, sizeof(connect), 0) ||
            dniv_recv_record(pair[0], reply, sizeof(reply), 0) != 2 ||
            reply[0] != DAP_ACK)
            goto out;
        if (phase == 0) {
            if (dniv_send_record(pair[0], put, sizeof(put), 0) ||
                dniv_send_record(pair[0], data1, sizeof(data1), 0) ||
                dniv_send_record(pair[0], data2, sizeof(data2), 0) ||
                dniv_send_record(pair[0], data3, sizeof(data3), 0) ||
                dniv_send_record(pair[0], finish, sizeof(finish), 0) ||
                dniv_recv_record(pair[0], reply, sizeof(reply), 0) != 3 ||
                reply[0] != DAP_ACCESS_COMPLETE ||
                reply[2] != DAP_ACCOMP_RESPONSE)
                goto out;
        } else {
            if (dniv_send_record(pair[0], get, sizeof(get), 0) ||
                dniv_recv_record(pair[0], reply, sizeof(reply), 0) !=
                    (ssize_t)sizeof(data1) ||
                memcmp(reply, data1, sizeof(data1)) ||
                dniv_recv_record(pair[0], reply, sizeof(reply), 0) !=
                    (ssize_t)sizeof(data2) ||
                memcmp(reply, data2, sizeof(data2)) ||
                dniv_recv_record(pair[0], reply, sizeof(reply), 0) !=
                    (ssize_t)sizeof(data3) ||
                memcmp(reply, data3, sizeof(data3)) ||
                dniv_recv_record(pair[0], reply, sizeof(reply), 0) !=
                    (ssize_t)sizeof(eof) ||
                memcmp(reply, eof, sizeof(eof)) ||
                dniv_send_record(pair[0], finish, sizeof(finish), 0) ||
                dniv_recv_record(pair[0], reply, sizeof(reply), 0) != 3 ||
                reply[0] != DAP_ACCESS_COMPLETE ||
                reply[2] != DAP_ACCOMP_RESPONSE)
                goto out;
        }
        close(pair[0]);
        pair[0] = -1;
        if (waitpid(child, &status, 0) != child ||
            !WIFEXITED(status) || WEXITSTATUS(status))
            goto out;
        child = -1;
        if (phase == 0) {
            file_fd = open_regular_at(rootfd, name, 0);
            if (file_fd < 0 ||
                read(file_fd, bytes, sizeof(bytes)) !=
                    (ssize_t)sizeof(bytes) ||
                memcmp(bytes, encoded, sizeof(encoded)) ||
                read(file_fd, bytes, sizeof(bytes)) != 0 ||
                fgetxattr(file_fd, DNFAL_XATTR_RECORD_FRAMING,
                          format, sizeof(format)) != 1 ||
                format[0] != DNFAL_RECORD_FRAMING_V1)
                goto out;
            close(file_fd);
            file_fd = -1;
        }
    }
    /* Malformed/incomplete serialized records must never become EOF. */
    {
        FILE *bad = tmpfile();
        size_t len;
        unsigned char payload[8];

        if (!bad)
            goto out;
        if (fwrite((const unsigned char[]){ 4U, 0U, 'X' }, 1, 3U,
                   bad) != 3U || fseek(bad, 0, SEEK_SET) ||
            read_framed_payload(bad, payload, sizeof(payload), &len) != -1) {
            fclose(bad);
            goto out;
        }
        fclose(bad);
    }
    rc = 0;
out:
    if (file_fd >= 0)
        close(file_fd);
    if (pair[0] >= 0)
        close(pair[0]);
    if (pair[1] >= 0)
        close(pair[1]);
    if (child > 0) {
        if (rc)
            (void)kill(child, SIGKILL);
        (void)waitpid(child, &status, 0);
    }
    (void)unlinkat(rootfd, name, 0);
    return rc;
}

/* A record-oriented xattr without the corresponding on-disk framing
 * marker is not a readable record stream, and bad local xattr values must
 * not be sent as a malformed DAP ATTR to the remote peer. */
static int selftest_record_framing_xattr_errors(void)
{
    const unsigned char valid[] = { DNFAL_RECORD_FRAMING_V1 };
    const unsigned char invalid[] = { 0xffU };
    int framed = -1;

    /* Filesystems without user xattrs may serve ordinary fixed/stream
     * files, but cannot certify VAR/VFC boundaries without the marker. */
    if (interpret_record_framing(-1, ENODATA, valid, DAP_RFM_FIX, &framed) || framed ||
        interpret_record_framing(-1, EOPNOTSUPP, valid, DAP_RFM_FIX, &framed) || framed ||
        interpret_record_framing(-1, EOPNOTSUPP, valid, DAP_RFM_STM, &framed) || framed)
        return -1;
    errno = 0;
    if (!interpret_record_framing(-1, ENODATA, valid, DAP_RFM_VAR, &framed) ||
        errno != EPROTO)
        return -1;
    errno = 0;
    if (!interpret_record_framing(-1, EOPNOTSUPP, valid, DAP_RFM_VFC, &framed) ||
        errno != EPROTO)
        return -1;
    if (interpret_record_framing(1, 0, valid, DAP_RFM_VAR, &framed) || !framed)
        return -1;
    errno = 0;
    if (!interpret_record_framing(1, 0, invalid, DAP_RFM_VAR, &framed) ||
        errno != EPROTO)
        return -1;
    errno = 0;
    if (!interpret_record_framing(1, 0, valid, DAP_RFM_FIX, &framed) ||
        errno != EPROTO)
        return -1;
    return 0;
}

static int selftest_unframed_metadata(int rootfd)
{
    const char name[] = "UNFRAMED.TXT";
    int fd = -1;
    unsigned char rfm, rat, bad;
    int framed;
    int rc = -1;

    fd = openat(rootfd, name, O_CREAT | O_EXCL | O_RDWR | O_CLOEXEC, 0600);
    if (fd < 0)
        return -1;
    if (write(fd, "AABB", 4U) != 4 ||
        load_metadata(fd, &rfm, &rat) ||
        rfm != DAP_RFM_FIX || rat != 0U ||
        load_record_framing(fd, rfm, &framed) || framed)
        goto out;
    if (save_metadata(fd, DAP_RFM_VAR, 0U) ||
        load_metadata(fd, &rfm, &rat) ||
        !load_record_framing(fd, rfm, &framed) || errno != EPROTO)
        goto out;
    if (save_metadata(fd, DAP_RFM_VFC, 0U) ||
        load_metadata(fd, &rfm, &rat) ||
        !load_record_framing(fd, rfm, &framed) || errno != EPROTO)
        goto out;
    bad = 255U;
    if (fsetxattr(fd, DNFAL_XATTR_RFM, &bad, 1U, 0) ||
        !load_metadata(fd, &rfm, &rat) || errno != EPROTO)
        goto out;
    bad = DAP_RFM_FIX;
    if (fsetxattr(fd, DNFAL_XATTR_RFM, &bad, 1U, 0))
        goto out;
    bad = 255U;
    if (fsetxattr(fd, DNFAL_XATTR_RAT, &bad, 1U, 0) ||
        !load_metadata(fd, &rfm, &rat) || errno != EPROTO)
        goto out;
    rc = 0;
out:
    close(fd);
    (void)unlinkat(rootfd, name, 0);
    return rc;
}

static int selftest(void)
{
    unsigned char config[16];
    char name[32];
    char pattern[32];
    unsigned char attrs[16];
    unsigned char rfm;
    unsigned char rat;
    char directory[] = "/tmp/dnfald-selftest.XXXXXX";
    char victim[] = "/tmp/dnfald-victim.XXXXXX";
    char good[256];
    char escape[256];
    char hardlink_path[256];
    char fifo_path[256];
    char victim_buf[16];
    int rootfd = -1;
    int victim_fd = -1;
    int file_fd = -1;
    int rc = 1;

    if (make_config(config, sizeof(config)) != 12U ||
        validate_config(config, 12U) ||
        config[3] != 8U || config[4] != 128U || config[5] != 128U ||
        config[6] != 4U || config[7] != 1U)
        return 1;
    config[3] = 0U;
    config[2] = 128U;
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
    config[0] = 2U;
    if (!validate_config(config, 12U) ||
        safe_filespec((const unsigned char *)"SERVER.TXT", 10U,
                      name, sizeof(name)) || strcmp(name, "SERVER.TXT") ||
        !safe_filespec((const unsigned char *)"../BAD", 6U,
                       name, sizeof(name)) ||
        safe_pattern((const unsigned char *)"*.TXT", 5U,
                     pattern, sizeof(pattern)) ||
        strcmp(pattern, "*.TXT") ||
        !safe_pattern((const unsigned char *)"../*", 4U,
                      pattern, sizeof(pattern)))
        return 1;
    if (parse_attributes(
            (const unsigned char[]){ DAP_ATTRIBUTES, 0U, 0x0fU,
                                     1U, 0U, DAP_RFM_VFC, 4U },
            7U, &rfm, &rat) ||
        rfm != DAP_RFM_VFC || rat != 4U ||
        make_attributes(attrs, sizeof(attrs), rfm, rat) != 7U ||
        memcmp(attrs, (const unsigned char[]){ DAP_ATTRIBUTES, 0U, 0x0fU,
                                               1U, 0U, DAP_RFM_VFC, 4U },
               7U) ||
        make_attributes(attrs, sizeof(attrs), DAP_RFM_FIX, 0U) != 4U ||
        memcmp(attrs, (const unsigned char[]){ DAP_ATTRIBUTES, 0U,
                                               0x04U, DAP_RFM_FIX }, 4U))
        return 1;

    /* The EX-6 ATTMENU must not be mistaken for a single menu octet.
     * The second menu octet here advertises BKS after RFM. */
    if (parse_attributes((const unsigned char[]){
            DAP_ATTRIBUTES, 0U, 0x87U, 0x01U, 1U, 0U,
            DAP_RFM_VAR, 0x20U }, 8U, &rfm, &rat) ||
        rfm != DAP_RFM_VAR || rat != 0U ||
        !parse_attributes((const unsigned char[]){
            DAP_ATTRIBUTES, 0U, 0x87U, 0x01U, 1U, 0U,
            DAP_RFM_VAR }, 7U, &rfm, &rat) ||
        !parse_attributes((const unsigned char[]){
            DAP_ATTRIBUTES, 0U, 0x87U, 0x80U },
            4U, &rfm, &rat) ||
        !parse_attributes((const unsigned char[]){
            DAP_ATTRIBUTES, 0U, 0x04U, 0xffU },
            4U, &rfm, &rat))
        return 1;

    if (!mkdtemp(directory))
        return 1;
    victim_fd = mkstemp(victim);
    if (victim_fd < 0 || write(victim_fd, "secret\n", 7U) != 7)
        goto out;
    close(victim_fd);
    victim_fd = -1;
    if (snprintf(good, sizeof(good), "%s/GOOD.TXT", directory) >=
            (int)sizeof(good) ||
        snprintf(escape, sizeof(escape), "%s/ESCAPE.TXT", directory) >=
            (int)sizeof(escape) ||
        snprintf(hardlink_path, sizeof(hardlink_path), "%s/HARD.TXT", directory) >=
            (int)sizeof(hardlink_path) ||
        snprintf(fifo_path, sizeof(fifo_path), "%s/FIFO.TXT", directory) >=
            (int)sizeof(fifo_path))
        goto out;
    file_fd = open(good, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0600);
    if (file_fd < 0 || write(file_fd, "ok\n", 3U) != 3)
        goto out;
    close(file_fd);
    file_fd = -1;
    if (symlink(victim, escape) || link(victim, hardlink_path) ||
        mkfifo(fifo_path, 0600))
        goto out;
    rootfd = open(directory, O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    if (rootfd < 0)
        goto out;
    /* Non-xattr filesystems still support ordinary fixed/stream files. */
    if (selftest_record_framing_xattr_errors())
        goto out;
    /* Unframed VAR/VFC and invalid local metadata must fail closed. */
    if (selftest_unframed_metadata(rootfd))
        goto out;
    /* Aborting CREATE must never truncate or unlink an existing file. */
    if (selftest_abort_create(rootfd, "GOOD.TXT"))
        goto out;
    file_fd = open_regular_at(rootfd, "GOOD.TXT", 0);
    if (file_fd < 0 || read(file_fd, victim_buf, 3U) != 3 ||
        memcmp(victim_buf, "ok\n", 3U))
        goto out;
    close(file_fd);
    file_fd = -1;
    /* Both complete DATA frames and payload bytes must respect negotiation. */
    if (selftest_get_buffer_limit(rootfd))
        goto out;
    /* Newly created incomplete files must still be removed on failure. */
    if (selftest_abort_create(rootfd, "PARTIAL.TXT") ||
        faccessat(rootfd, "PARTIAL.TXT", F_OK, 0) == 0 || errno != ENOENT ||
        selftest_create_swap(rootfd) || selftest_create_success(rootfd) ||
        selftest_framed_records(rootfd, DAP_RFM_VAR) ||
        selftest_framed_records(rootfd, DAP_RFM_VFC))
        goto out;
    file_fd = open_regular_at(rootfd, "ESCAPE.TXT", 0);
    if (file_fd >= 0)
        goto out;
    file_fd = open_regular_at(rootfd, "HARD.TXT", 0);
    if (file_fd >= 0)
        goto out;
    file_fd = open_regular_at(rootfd, "ESCAPE.TXT", 1);
    if (file_fd >= 0)
        goto out;
    file_fd = open_regular_at(rootfd, "HARD.TXT", 1);
    if (file_fd >= 0)
        goto out;
    file_fd = open_regular_at(rootfd, "FIFO.TXT", 0);
    if (file_fd >= 0)
        goto out;
    file_fd = open_regular_at(rootfd, "FIFO.TXT", 1);
    if (file_fd >= 0)
        goto out;
    victim_fd = open(victim, O_RDONLY | O_CLOEXEC);
    if (victim_fd < 0 || read(victim_fd, victim_buf, sizeof(victim_buf)) != 7 ||
        memcmp(victim_buf, "secret\n", 7U))
        goto out;
    rc = 0;

out:
    if (file_fd >= 0)
        close(file_fd);
    if (victim_fd >= 0)
        close(victim_fd);
    if (rootfd >= 0)
        close(rootfd);
    unlink(fifo_path);
    unlink(hardlink_path);
    unlink(escape);
    unlink(good);
    unlink(victim);
    rmdir(directory);
    if (rc)
        return 1;
    puts("dnfald selftest passed");
    return 0;
}

static int access_field_match(const unsigned char *data, unsigned int len,
                              const char *expected)
{
    size_t n;

    if (!expected)
        return 1;
    n = strlen(expected);
    return n == len && !memcmp(data, expected, n);
}

static int authenticate_session(int fd, const char *user,
                                const char *password, const char *account)
{
    struct accessdata_dn access;
    socklen_t len = sizeof(access);

    if (!user && !password && !account)
        return 0;
    memset(&access, 0, sizeof(access));
    if (getsockopt(fd, DNPROTO_NSP, DSO_CONACCESS, &access, &len))
        return -1;
    if (len != sizeof(access)) {
        errno = EPROTO;
        return -1;
    }
    if (!access_field_match(access.acc_user, access.acc_userl, user) ||
        !access_field_match(access.acc_pass, access.acc_passl, password) ||
        !access_field_match(access.acc_acc, access.acc_accl, account)) {
        errno = EACCES;
        return -1;
    }
    return 0;
}

int main(int argc, char **argv)
{
    const char *root = NULL;
    const char *user = NULL;
    const char *password = NULL;
    const char *account = NULL;
    int sessions = 0;
    int served = 0;
    int failed = 0;
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
        } else if (!strcmp(argv[i], "--user") && i + 1 < argc) {
            user = argv[++i];
        } else if (!strcmp(argv[i], "--password") && i + 1 < argc) {
            password = argv[++i];
        } else if (!strcmp(argv[i], "--account") && i + 1 < argc) {
            account = argv[++i];
        } else {
            fprintf(stderr,
                    "usage: %s [--once|--sessions N] [--root DIR] [--user USER] [--password PASSWORD] [--account ACCOUNT] | --selftest\n",
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
        rc = authenticate_session(fd, user, password, account);
        if (rc && errno == EACCES) {
            fprintf(stderr, "dnfald: access denied\n");
            close(fd);
            served++;
            if (sessions && served >= sessions)
                break;
            continue;
        }
        if (!rc)
            rc = serve_session(fd, root);
        close(fd);
        if (rc) {
            perror("dnfald: session");
            failed = 1;
            served++;
            if (sessions && served >= sessions)
                break;
            continue;
        }
        served++;
        if (sessions && served >= sessions)
            break;
    }
    close(listener);
    return failed ? 1 : 0;
}
