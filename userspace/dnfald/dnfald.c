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
#include <sys/xattr.h>
#include <unistd.h>

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

static size_t make_config(unsigned char *buf, size_t cap)
{
    if (cap < 12U)
        return 0U;
    buf[0] = DAP_CONFIG;
    buf[1] = 0U;
    buf[2] = 0U;
    buf[3] = 4U;
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
    return len >= 12U && buf[0] == DAP_CONFIG && !(buf[1] & 0x7fU) ? 0 : -1;
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
    return send(fd, buf, len, MSG_EOR | MSG_NOSIGNAL) == (ssize_t)len ? 0 : -1;
}

static int parse_attributes(const unsigned char *buf, size_t len,
                            unsigned char *rfm, unsigned char *rat)
{
    unsigned char menu;
    size_t pos = 3U;

    *rfm = DAP_RFM_FIX;
    *rat = 0U;
    if (len < 3U || buf[0] != DAP_ATTRIBUTES)
        return -1;
    menu = buf[2];
    if (!menu)
        return len == 3U ? 0 : -1;
    if (menu & 0x01U) { if (pos >= len) return -1; pos++; }
    if (menu & 0x02U) { if (pos >= len) return -1; pos++; }
    if (menu & 0x04U) {
        if (pos >= len) return -1;
        *rfm = buf[pos++];
        if (*rfm < DAP_RFM_FIX || *rfm > DAP_RFM_STMCR)
            return -1;
    }
    if (menu & 0x08U) {
        if (pos >= len) return -1;
        *rat = buf[pos++];
        if (*rat > DAP_RAT_MAX)
            return -1;
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
    return 0;
}

static int save_metadata(int fd, unsigned char rfm, unsigned char rat)
{
    return fsetxattr(fd, DNFAL_XATTR_RFM, &rfm, 1U, 0) ||
           fsetxattr(fd, DNFAL_XATTR_RAT, &rat, 1U, 0) ? -1 : 0;
}

static int open_regular_at(int rootfd, const char *name, int write_file)
{
    struct stat st;
    int flags = O_NOFOLLOW | O_CLOEXEC | O_NONBLOCK;
    int fd;

    if (write_file)
        flags |= O_WRONLY | O_CREAT;
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

        if (load_metadata(fileno(in), &rfm, &rat))
            goto fail;
        attr_len = make_attributes(attributes, sizeof(attributes), rfm, rat);
        if (!attr_len || send_record(fd, attributes, attr_len) ||
            send_record(fd, ack, sizeof(ack)))
            goto fail;
    }

    got = recv(fd, request, sizeof(request), 0);
    if (got != 3 || request[0] != DAP_CONTROL || request[2] != DAP_CONTROL_CONNECT)
        goto fail;
    {
        const unsigned char ack[] = { DAP_ACK, 0U };
        if (send_record(fd, ack, sizeof(ack)))
            goto fail;
    }

    got = recv(fd, request, sizeof(request), 0);
    if (got != 3 || request[0] != DAP_CONTROL || request[2] != DAP_CONTROL_GET)
        goto fail;

    for (;;) {
        size_t count = fread(reply + 3U, 1, sizeof(reply) - 3U, in);

        if (count) {
            reply[0] = DAP_DATA;
            reply[1] = 0U;
            reply[2] = 0U;
            if (send_record(fd, reply, count + 3U))
                goto fail;
        }
        if (count < sizeof(reply) - 3U) {
            if (ferror(in))
                goto fail;
            break;
        }
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
    got = recv(fd, request, sizeof(request), 0);
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
    file_fd = open_regular_at(rootfd, name, 1);
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

        if (save_metadata(fileno(out), requested_rfm, requested_rat))
            goto fail;
        attr_len = make_attributes(attributes, sizeof(attributes),
                                   requested_rfm, requested_rat);
        if (!attr_len || send_record(fd, attributes, attr_len) ||
            send_record(fd, ack, sizeof(ack)))
            goto fail;
    }

    got = recv(fd, request, sizeof(request), 0);
    if (got != 3 || request[0] != DAP_CONTROL ||
        request[2] != DAP_CONTROL_CONNECT)
        goto fail;
    {
        const unsigned char ack[] = { DAP_ACK, 0U };
        if (send_record(fd, ack, sizeof(ack)))
            goto fail;
    }

    got = recv(fd, request, sizeof(request), 0);
    if (got != 3 || request[0] != DAP_CONTROL ||
        request[2] != DAP_CONTROL_PUT)
        goto fail;

    for (;;) {
        size_t off;

        got = recv(fd, request, sizeof(request), 0);
        if (got < 2)
            goto fail;
        if (request[0] == DAP_DATA) {
            if (got < 3)
                goto fail;
            off = 3U + request[2];
            if (off > (size_t)got)
                goto fail;
            if ((size_t)got > off &&
                fwrite(request + off, 1, (size_t)got - off, out) !=
                    (size_t)got - off)
                goto fail;
            continue;
        }
        if (request[0] == DAP_ACCESS_COMPLETE &&
            got == 3 && request[2] == DAP_ACCOMP_CLOSE)
            break;
        goto fail;
    }
    if (fclose(out))
        return -1;
    out = NULL;
    {
        const unsigned char complete[] = {
            DAP_ACCESS_COMPLETE, 0U, DAP_ACCOMP_RESPONSE
        };
        return send_record(fd, complete, sizeof(complete));
    }

fail:
    if (out)
        fclose(out);
    unlinkat(rootfd, name, 0);
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
    got = recv(fd, request, sizeof(request), 0);
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
    while ((ent = readdir(dir)) != NULL) {
        size_t len;

        if (!strcmp(ent->d_name, ".") || !strcmp(ent->d_name, "..") ||
            ent->d_name[0] == '.' || fnmatch(pattern, ent->d_name, 0))
            continue;
        len = strlen(ent->d_name);
        if (len > 127U || len + 4U > sizeof(msg)) {
            closedir(dir);
            return -1;
        }
        msg[0] = 15U;
        msg[1] = 0U;
        msg[2] = 1U;
        msg[3] = (unsigned char)len;
        memcpy(msg + 4U, ent->d_name, len);
        if (send_record(fd, msg, len + 4U)) {
            closedir(dir);
            return -1;
        }
    }
    closedir(dir);
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
    got = recv(fd, request, sizeof(request), 0);
    if (got < 0 || validate_config(request, (size_t)got))
        return -1;
    reply_len = make_config(reply, sizeof(reply));
    if (!reply_len || send_record(fd, reply, reply_len))
        return -1;
    if (!root)
        return 0;
    rootfd = open(root, O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    if (rootfd < 0)
        return -1;

    got = recv(fd, request, sizeof(request), 0);
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
        got = recv(fd, request, sizeof(request), 0);
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
        config[3] != 4U || config[4] != 128U || config[5] != 128U ||
        config[6] != 4U || config[7] != 1U)
        return 1;
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
    file_fd = open_regular_at(rootfd, "GOOD.TXT", 0);
    if (file_fd < 0)
        goto out;
    close(file_fd);
    file_fd = -1;
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
