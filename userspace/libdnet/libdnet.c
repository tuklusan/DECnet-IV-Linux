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
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>

#include <netdnet/dnetdb.h>

static struct dn_naddr static_addr;
static char static_text[DNET_ADDRSTRLEN];

static __le16 cpu_to_le16_u(unsigned short value)
{
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
    return (__le16)value;
#else
    return (__le16)__builtin_bswap16(value);
#endif
}

static unsigned short le16_to_cpu_u(__le16 value)
{
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
    return (unsigned short)value;
#else
    return __builtin_bswap16((unsigned short)value);
#endif
}

static int parse_numeric(const char *text, struct dn_naddr *out)
{
    char *end;
    unsigned long area;
    unsigned long node;

    if (!text || !out) {
        errno = EINVAL;
        return -1;
    }
    errno = 0;
    area = strtoul(text, &end, 10);
    if (errno || end == text || *end != '.' || area > 63U) {
        errno = EINVAL;
        return -1;
    }
    text = end + 1;
    errno = 0;
    node = strtoul(text, &end, 10);
    if (errno || end == text || *end || node > 1023U) {
        errno = EINVAL;
        return -1;
    }

    memset(out, 0, sizeof(*out));
    out->a_len = cpu_to_le16_u(DN_ADDL);
    out->a_addr[0] = (unsigned char)(node & 0xffU);
    out->a_addr[1] = (unsigned char)((area << 2) | ((node >> 8) & 0x03U));
    return 0;
}

struct dn_naddr *dnet_addr(const char *text)
{
    if (parse_numeric(text, &static_addr))
        return NULL;
    return &static_addr;
}

int dnet_pton(int family, const char *src, void *addr)
{
    if (family != AF_DECnet || !src || !addr) {
        errno = EAFNOSUPPORT;
        return -1;
    }
    return parse_numeric(src, addr) ? 0 : 1;
}

const char *dnet_ntop(int family, const void *addr, char *dst, size_t len)
{
    const struct dn_naddr *node_addr = addr;
    unsigned int area;
    unsigned int node;
    int needed;

    if (family != AF_DECnet || !node_addr || !dst) {
        errno = EAFNOSUPPORT;
        return NULL;
    }
    if (le16_to_cpu_u(node_addr->a_len) != DN_ADDL) {
        errno = EINVAL;
        return NULL;
    }
    area = node_addr->a_addr[1] >> 2;
    node = ((unsigned int)(node_addr->a_addr[1] & 0x03U) << 8) |
        node_addr->a_addr[0];
    needed = snprintf(dst, len, "%u.%u", area, node);
    if (needed < 0 || (size_t)needed >= len) {
        errno = ENOSPC;
        return NULL;
    }
    return dst;
}

char *dnet_ntoa(struct dn_naddr *addr)
{
    return dnet_ntop(AF_DECnet, addr, static_text, sizeof(static_text)) ?
        static_text : NULL;
}

char *dnet_htoa(struct dn_naddr *addr)
{
    return dnet_ntoa(addr);
}


static int copy_access_field(unsigned char *dst, __u8 *dst_len,
                             const char *src, size_t len)
{
    if (len > DN_MAXACCL) {
        errno = ENAMETOOLONG;
        return -1;
    }
    if (len)
        memcpy(dst, src, len);
    *dst_len = (__u8)len;
    return 0;
}

static int parse_host(const char *host, char *node, size_t node_cap,
                      struct accessdata_dn *access)
{
    const char *slash;
    const char *next;
    size_t len;

    if (!host || !*host || !node || !node_cap || !access) {
        errno = EINVAL;
        return -1;
    }

    slash = strchr(host, '/');
    len = slash ? (size_t)(slash - host) : strlen(host);
    if (!len) {
        errno = EINVAL;
        return -1;
    }
    if (len >= node_cap) {
        errno = ENAMETOOLONG;
        return -1;
    }
    memcpy(node, host, len);
    node[len] = '\0';

    if (!slash)
        return 0;

    host = slash + 1;
    next = strchr(host, '/');
    if (!next) {
        errno = EINVAL;
        return -1;
    }
    if (copy_access_field(access->acc_user, &access->acc_userl,
                          host, (size_t)(next - host)))
        return -1;

    host = next + 1;
    next = strchr(host, '/');
    if (!next) {
        errno = EINVAL;
        return -1;
    }
    if (copy_access_field(access->acc_pass, &access->acc_passl,
                          host, (size_t)(next - host)))
        return -1;

    host = next + 1;
    if (copy_access_field(access->acc_acc, &access->acc_accl,
                          host, strlen(host)))
        return -1;
    return 0;
}

static int set_object(struct sockaddr_dn *peer, const char *object)
{
    size_t len;

    if (!peer || !object || !*object) {
        errno = EINVAL;
        return -1;
    }

    if (*object == '#') {
        const unsigned char *p = (const unsigned char *)object + 1;
        unsigned long value = 0;

        if (!*p) {
            errno = EINVAL;
            return -1;
        }
        while (*p) {
            if (*p < '0' || *p > '9') {
                errno = EINVAL;
                return -1;
            }
            value = value * 10U + (unsigned long)(*p - '0');
            if (value > 255U) {
                errno = EINVAL;
                return -1;
            }
            p++;
        }
        peer->sdn_objnum = (__u8)value;
        return 0;
    }

    len = strlen(object);
    if (len > DN_MAXOBJL) {
        errno = ENAMETOOLONG;
        return -1;
    }
    peer->sdn_objnamel = cpu_to_le16_u((unsigned short)len);
    memcpy(peer->sdn_objname, object, len);
    return 0;
}

int dnet_conn(char *host, char *object, int type,
              unsigned char *opt_out, int opt_outl,
              unsigned char *opt_in, int *opt_inl)
{
    struct sockaddr_dn peer;
    struct accessdata_dn access;
    struct optdata_dn data;
    struct timeval timeout = { 60, 0 };
    char node[DN_MAXNODEL + 1U];
    socklen_t data_len;
    unsigned int incoming;
    int fd;
    int saved_errno;

    if (!host || !object) {
        errno = EINVAL;
        return -1;
    }
    if (type != SOCK_SEQPACKET && type != SOCK_STREAM) {
        errno = EPROTONOSUPPORT;
        return -1;
    }
    if (opt_outl < 0 || opt_outl > DN_MAXOPTL ||
        (opt_outl && !opt_out) || (opt_inl && *opt_inl < 0)) {
        errno = EINVAL;
        return -1;
    }

    memset(&access, 0, sizeof(access));
    if (parse_host(host, node, sizeof(node), &access))
        return -1;

    memset(&peer, 0, sizeof(peer));
    peer.sdn_family = AF_DECnet;
    if (dnet_pton(AF_DECnet, node, &peer.sdn_add) != 1) {
        struct nodeent *entry = getnodebyname(node);

        if (!entry || entry->n_addrtype != AF_DECnet ||
            entry->n_length != DN_ADDL || !entry->n_addr) {
            errno = EADDRNOTAVAIL;
            return -1;
        }
        peer.sdn_nodeaddrl = cpu_to_le16_u(DN_ADDL);
        memcpy(peer.sdn_nodeaddr, entry->n_addr, DN_ADDL);
    }
    if (set_object(&peer, object))
        return -1;

    fd = socket(AF_DECnet, type, DNPROTO_NSP);
    if (fd < 0)
        return -1;

    if (setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout)) ||
        setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)))
        goto fail;

    if (access.acc_userl || access.acc_passl || access.acc_accl) {
        if (setsockopt(fd, DNPROTO_NSP, DSO_CONACCESS,
                       &access, sizeof(access)))
            goto fail;
    }

    if (opt_outl) {
        memset(&data, 0, sizeof(data));
        data.opt_optl = cpu_to_le16_u((unsigned short)opt_outl);
        memcpy(data.opt_data, opt_out, (size_t)opt_outl);
        if (setsockopt(fd, DNPROTO_NSP, DSO_CONDATA, &data, sizeof(data)))
            goto fail;
    }

    if (connect(fd, (struct sockaddr *)&peer, sizeof(peer)))
        goto fail;

    if (opt_in && opt_inl) {
        memset(&data, 0, sizeof(data));
        data_len = sizeof(data);
        if (getsockopt(fd, DNPROTO_NSP, DSO_CONDATA, &data, &data_len))
            goto fail;
        if (data_len != sizeof(data)) {
            errno = EPROTO;
            goto fail;
        }
        incoming = le16_to_cpu_u(data.opt_optl);
        if (incoming > DN_MAXOPTL) {
            errno = EPROTO;
            goto fail;
        }
        if ((unsigned int)*opt_inl < incoming) {
            errno = EMSGSIZE;
            goto fail;
        }
        if (incoming)
            memcpy(opt_in, data.opt_data, incoming);
        *opt_inl = (int)incoming;
    }

    errno = 0;
    return fd;

fail:
    saved_errno = errno;
    close(fd);
    errno = saved_errno;
    return -1;
}
