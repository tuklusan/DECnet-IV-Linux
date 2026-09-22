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

#ifndef _DECNET_IV_NICE_H
#define _DECNET_IV_NICE_H

#include <linux/types.h>
#include <stddef.h>
#include <string.h>

#define DNIV_NICE_FUNC_READ_INFO 20U
#define DNIV_NICE_ENTITY_NODE 0U
#define DNIV_NICE_INFO_SUMMARY 0U
#define DNIV_NICE_INFO_STATUS 1U
#define DNIV_NICE_INFO_CHARACTERISTICS 2U
#define DNIV_NICE_INFO_COUNTERS 3U

#define DNIV_NICE_RET_SUCCESS 1
#define DNIV_NICE_PARAM_IDENTIFICATION 100U
#define DNIV_NICE_TYPE_ASCII 0x40U

struct dniv_nice_read_node {
    __u16 node;
    __u8 info;
    __u8 permanent;
};

static inline int
dniv_nice_parse_read_node(const __u8 *buf, size_t length,
                          struct dniv_nice_read_node *request)
{
    __u8 selector;

    if (!buf || !request || length != 5U)
        return -1;
    if (buf[0] != DNIV_NICE_FUNC_READ_INFO)
        return -1;

    selector = buf[1];
    if ((selector & 0x08U) != 0U ||
        (selector & 0x07U) != DNIV_NICE_ENTITY_NODE)
        return -1;
    if (buf[2] != 0U)
        return -1;

    request->info = (__u8)((selector >> 4) & 0x07U);
    request->permanent = (__u8)((selector >> 7) & 0x01U);
    request->node = (__u16)((__u16)buf[3] | ((__u16)buf[4] << 8));
    return 0;
}

static inline int
dniv_nice_build_node_reply(__u8 *buf, size_t capacity, size_t *used,
                           __u16 address, const char *name,
                           const char *identification)
{
    size_t name_len;
    size_t ident_len;
    size_t needed;
    size_t off = 0U;

    if (!buf || !used || !name || !identification)
        return -1;
    name_len = strlen(name);
    ident_len = strlen(identification);
    if (!name_len || name_len > 127U || ident_len > 255U)
        return -1;

    needed = 1U + 2U + 1U + 2U + 1U + name_len;
    if (ident_len)
        needed += 2U + 1U + 1U + ident_len;
    if (capacity < needed)
        return -1;

    buf[off++] = (__u8)DNIV_NICE_RET_SUCCESS;
    buf[off++] = 0xffU;
    buf[off++] = 0xffU;
    buf[off++] = 0U;

    buf[off++] = (__u8)(address & 0xffU);
    buf[off++] = (__u8)(address >> 8);
    buf[off++] = (__u8)(0x80U | (__u8)name_len);
    memcpy(buf + off, name, name_len);
    off += name_len;

    if (ident_len) {
        buf[off++] = (__u8)(DNIV_NICE_PARAM_IDENTIFICATION & 0xffU);
        buf[off++] = (__u8)(DNIV_NICE_PARAM_IDENTIFICATION >> 8);
        buf[off++] = DNIV_NICE_TYPE_ASCII;
        buf[off++] = (__u8)ident_len;
        memcpy(buf + off, identification, ident_len);
        off += ident_len;
    }

    *used = off;
    return 0;
}

#endif
