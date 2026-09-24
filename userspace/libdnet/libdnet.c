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
