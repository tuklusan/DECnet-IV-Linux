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
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

#include <netdnet/dnetdb.h>

static struct optdata_dn default_optdata;
static int have_default_optdata;

static __le16 cpu_to_le16_u(unsigned short value)
{
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
    return (__le16)value;
#else
    return (__le16)__builtin_bswap16(value);
#endif
}

static int bind_object(int fd, int object, const char *name)
{
    struct sockaddr_dn local;
    size_t len;

    memset(&local, 0, sizeof(local));
    local.sdn_family = AF_DECnet;
    if (object > 0 && object <= 255) {
        local.sdn_objnum = (__u8)object;
    } else if (name && *name) {
        len = strlen(name);
        if (len > DN_MAXOBJL) {
            errno = ENAMETOOLONG;
            return -1;
        }
        local.sdn_objnamel = cpu_to_le16_u((unsigned short)len);
        memcpy(local.sdn_objname, name, len);
    } else if (object == 0) {
        local.sdn_flags = SDF_WILD;
    } else {
        errno = EINVAL;
        return -1;
    }
    return bind(fd, (struct sockaddr *)&local, sizeof(local));
}

int dnet_daemon(int object, char *named_object, int verbosity, int do_fork)
{
    struct sockaddr_dn existing;
    socklen_t existing_len = sizeof(existing);
    int mode = ACC_DEFER;
    int listener;
    int fd;

    (void)verbosity;
    memset(&existing, 0, sizeof(existing));
    if (!getsockname(STDIN_FILENO, (struct sockaddr *)&existing, &existing_len) &&
        existing.sdn_family == AF_DECnet)
        return STDIN_FILENO;

    if (do_fork) {
        pid_t pid = fork();

        if (pid < 0)
            return -1;
        if (pid > 0)
            _exit(0);
        if (setsid() < 0)
            return -1;
        if (chdir("/"))
            return -1;
    }

    listener = socket(AF_DECnet, SOCK_SEQPACKET, DNPROTO_NSP);
    if (listener < 0)
        return -1;
    if (setsockopt(listener, DNPROTO_NSP, DSO_ACCEPTMODE,
                   &mode, sizeof(mode)))
        goto fail;
    if (have_default_optdata &&
        setsockopt(listener, DNPROTO_NSP, DSO_CONDATA,
                   &default_optdata, sizeof(default_optdata)))
        goto fail;
    if (bind_object(listener, object, named_object) || listen(listener, 5))
        goto fail;

    do {
        fd = accept(listener, NULL, NULL);
    } while (fd < 0 && errno == EINTR);
    if (fd < 0)
        goto fail;
    close(listener);
    return fd;

fail:
    {
        int saved_errno = errno;
        close(listener);
        errno = saved_errno;
        return -1;
    }
}

void dnet_accept(int fd, short status, char *data, int len)
{
    struct optdata_dn opt;

    if (len < 0 || len > DN_MAXOPTL || (len && !data)) {
        errno = EINVAL;
        return;
    }
    if (status || len) {
        memset(&opt, 0, sizeof(opt));
        opt.opt_status = cpu_to_le16_u((unsigned short)status);
        opt.opt_optl = cpu_to_le16_u((unsigned short)len);
        if (len)
            memcpy(opt.opt_data, data, (size_t)len);
        if (setsockopt(fd, DNPROTO_NSP, DSO_CONDATA, &opt, sizeof(opt)))
            return;
    }
    (void)setsockopt(fd, DNPROTO_NSP, DSO_CONACCEPT, NULL, 0);
}

void dnet_reject(int fd, short status, char *data, int len)
{
    struct optdata_dn opt;

    if (len < 0 || len > DN_MAXOPTL || (len && !data)) {
        errno = EINVAL;
        close(fd);
        return;
    }
    memset(&opt, 0, sizeof(opt));
    opt.opt_status = cpu_to_le16_u((unsigned short)status);
    opt.opt_optl = cpu_to_le16_u((unsigned short)len);
    if (len)
        memcpy(opt.opt_data, data, (size_t)len);
    if (status || len)
        (void)setsockopt(fd, DNPROTO_NSP, DSO_DISDATA, &opt, sizeof(opt));
    (void)setsockopt(fd, DNPROTO_NSP, DSO_CONREJECT, NULL, 0);
    close(fd);
}

void dnet_set_optdata(char *data, int len)
{
    if (len < 0 || len > DN_MAXOPTL || (len && !data)) {
        errno = EINVAL;
        return;
    }
    memset(&default_optdata, 0, sizeof(default_optdata));
    default_optdata.opt_optl = cpu_to_le16_u((unsigned short)len);
    if (len)
        memcpy(default_optdata.opt_data, data, (size_t)len);
    have_default_optdata = 1;
}

char *dnet_daemon_name(void)
{
    return NULL;
}
