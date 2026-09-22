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
#define DNIV_NICE_ENTITY_CIRCUIT 3U
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



struct dniv_nice_read_circuit {
    __u8 info;
    __u8 permanent;
    char name[128];
};

static inline int
dniv_nice_parse_read_circuit(const __u8 *buf, size_t length,
                             struct dniv_nice_read_circuit *request)
{
    size_t name_len;
    __u8 selector;

    if (!buf || !request || length < 4U)
        return -1;
    if (buf[0] != DNIV_NICE_FUNC_READ_INFO)
        return -1;

    selector = buf[1];
    if ((selector & 0x08U) != 0U ||
        (selector & 0x07U) != DNIV_NICE_ENTITY_CIRCUIT)
        return -1;
    name_len = buf[2];
    if (!name_len || name_len >= sizeof(request->name) ||
        length != 3U + name_len)
        return -1;

    memset(request, 0, sizeof(*request));
    request->info = (__u8)((selector >> 4) & 0x07U);
    request->permanent = (__u8)((selector >> 7) & 0x01U);
    memcpy(request->name, buf + 3U, name_len);
    request->name[name_len] = '\0';
    return 0;
}

static inline int
dniv_nice_build_circuit_status_reply(__u8 *buf, size_t capacity,
                                     size_t *used, const char *name,
                                     __u16 adjacent_node,
                                     __u16 block_size)
{
    size_t name_len;
    size_t needed;
    size_t off = 0U;

    if (!buf || !used || !name)
        return -1;
    name_len = strlen(name);
    if (!name_len || name_len > 127U)
        return -1;
    needed = 4U + 1U + name_len + 4U + 6U + 5U;
    if (capacity < needed)
        return -1;

    buf[off++] = (__u8)DNIV_NICE_RET_SUCCESS;
    buf[off++] = 0xffU;
    buf[off++] = 0xffU;
    buf[off++] = 0U;
    buf[off++] = (__u8)name_len;
    memcpy(buf + off, name, name_len);
    off += name_len;

    /* Circuit state, parameter 0, coded one-byte value: On. */
    buf[off++] = 0U;
    buf[off++] = 0U;
    buf[off++] = 0x81U;
    buf[off++] = 0U;

    /* Adjacent node, parameter 800, CM-1 containing a two-byte node. */
    buf[off++] = (__u8)(800U & 0xffU);
    buf[off++] = (__u8)(800U >> 8);
    buf[off++] = 0xc1U;
    buf[off++] = 0x02U;
    buf[off++] = (__u8)(adjacent_node & 0xffU);
    buf[off++] = (__u8)(adjacent_node >> 8);

    /* Block size, parameter 810, unsigned two-byte value. */
    buf[off++] = (__u8)(810U & 0xffU);
    buf[off++] = (__u8)(810U >> 8);
    buf[off++] = 0x02U;
    buf[off++] = (__u8)(block_size & 0xffU);
    buf[off++] = (__u8)(block_size >> 8);

    *used = off;
    return 0;
}

static inline __u32
dniv_nice_counter32(__u64 value)
{
    return value > 0xffffffffULL ? 0xffffffffU : (__u32)value;
}

static inline void
dniv_nice_put_counter32(__u8 *buf, size_t *off, __u16 number, __u64 value)
{
    __u32 counter = dniv_nice_counter32(value);
    __u16 pnum = (__u16)(number | 0xe000U);

    buf[(*off)++] = (__u8)(pnum & 0xffU);
    buf[(*off)++] = (__u8)(pnum >> 8);
    buf[(*off)++] = (__u8)(counter & 0xffU);
    buf[(*off)++] = (__u8)((counter >> 8) & 0xffU);
    buf[(*off)++] = (__u8)((counter >> 16) & 0xffU);
    buf[(*off)++] = (__u8)(counter >> 24);
}

static inline int
dniv_nice_build_node_counters_reply(__u8 *buf, size_t capacity, size_t *used,
                                    __u16 address, const char *name,
                                    __u64 total_bytes_received,
                                    __u64 total_bytes_sent,
                                    __u64 total_messages_received,
                                    __u64 total_messages_sent)
{
    size_t name_len;
    size_t needed;
    size_t off = 0U;

    if (!buf || !used || !name)
        return -1;
    name_len = strlen(name);
    if (!name_len || name_len > 127U)
        return -1;
    needed = 1U + 2U + 1U + 2U + 1U + name_len + 4U * 6U;
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

    dniv_nice_put_counter32(buf, &off, 608U, total_bytes_received);
    dniv_nice_put_counter32(buf, &off, 609U, total_bytes_sent);
    dniv_nice_put_counter32(buf, &off, 610U, total_messages_received);
    dniv_nice_put_counter32(buf, &off, 611U, total_messages_sent);

    *used = off;
    return 0;
}

static inline int
dniv_nice_build_circuit_counters_reply(__u8 *buf, size_t capacity,
                                       size_t *used, const char *name,
                                       __u64 bytes_received,
                                       __u64 bytes_sent,
                                       __u64 blocks_received,
                                       __u64 blocks_sent)
{
    size_t name_len;
    size_t needed;
    size_t off = 0U;

    if (!buf || !used || !name)
        return -1;
    name_len = strlen(name);
    if (!name_len || name_len > 127U)
        return -1;
    needed = 4U + 1U + name_len + 4U * 6U;
    if (capacity < needed)
        return -1;

    buf[off++] = (__u8)DNIV_NICE_RET_SUCCESS;
    buf[off++] = 0xffU;
    buf[off++] = 0xffU;
    buf[off++] = 0U;
    buf[off++] = (__u8)name_len;
    memcpy(buf + off, name, name_len);
    off += name_len;

    dniv_nice_put_counter32(buf, &off, 1000U, bytes_received);
    dniv_nice_put_counter32(buf, &off, 1001U, bytes_sent);
    dniv_nice_put_counter32(buf, &off, 1010U, blocks_received);
    dniv_nice_put_counter32(buf, &off, 1011U, blocks_sent);

    *used = off;
    return 0;
}

struct dniv_nice_node_reply {
    __u16 address;
    __u16 active_links;
    __u8 state;
    __u8 has_state;
    __u8 has_active_links;
    char name[128];
};

static inline int
dniv_nice_parse_node_reply(const __u8 *buf, size_t length,
                           struct dniv_nice_node_reply *reply)
{
    size_t off;
    size_t name_len;

    if (!buf || !reply || length < 7U || buf[0] != DNIV_NICE_RET_SUCCESS)
        return -1;
    memset(reply, 0, sizeof(*reply));

    off = 3U;
    if (off >= length || length - off < (size_t)buf[off] + 1U)
        return -1;
    off += (size_t)buf[off] + 1U;
    if (length - off < 3U)
        return -1;

    reply->address = (__u16)((__u16)buf[off] |
                             ((__u16)buf[off + 1U] << 8));
    off += 2U;
    if ((buf[off] & 0x80U) == 0U)
        return -1;
    name_len = buf[off++] & 0x7fU;
    if (!name_len || name_len >= sizeof(reply->name) ||
        length - off < name_len)
        return -1;
    memcpy(reply->name, buf + off, name_len);
    reply->name[name_len] = '\0';
    off += name_len;

    while (length - off >= 3U) {
        __u16 param = (__u16)((__u16)buf[off] |
                              ((__u16)buf[off + 1U] << 8));
        __u8 type = buf[off + 2U];

        off += 3U;
        if (param == 0U && type == 0x81U) {
            if (length - off < 1U)
                return -1;
            reply->state = buf[off++];
            reply->has_state = 1U;
            continue;
        }
        if (param == 600U && type == 0x02U) {
            if (length - off < 2U)
                return -1;
            reply->active_links = (__u16)((__u16)buf[off] |
                                          ((__u16)buf[off + 1U] << 8));
            reply->has_active_links = 1U;
            off += 2U;
            continue;
        }
        if (param > 600U)
            break;
        if (type == 0x20U || type == 0x40U) {
            size_t value_len;

            if (off >= length)
                return -1;
            value_len = buf[off];
            if (length - off < value_len + 1U)
                return -1;
            off += value_len + 1U;
            continue;
        }
        if ((type >= 0x01U && type <= 0x1fU) ||
            (type >= 0x81U && type <= 0x9fU)) {
            size_t value_len = type & 0x1fU;

            if (!value_len || length - off < value_len)
                return -1;
            off += value_len;
            continue;
        }
        break;
    }
    return 0;
}

static inline int
dniv_nice_build_node_status_reply(__u8 *buf, size_t capacity, size_t *used,
                                  __u16 address, const char *name,
                                  __u16 active_links)
{
    size_t name_len;
    size_t needed;
    size_t off = 0U;

    if (!buf || !used || !name)
        return -1;
    name_len = strlen(name);
    if (!name_len || name_len > 127U)
        return -1;

    needed = 1U + 2U + 1U + 2U + 1U + name_len + 4U + 5U;
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

    /* Node state, parameter 0, coded one-byte value: On. */
    buf[off++] = 0U;
    buf[off++] = 0U;
    buf[off++] = 0x81U;
    buf[off++] = 0U;

    /* Active links, parameter 600, unsigned two-byte value. */
    buf[off++] = (__u8)(600U & 0xffU);
    buf[off++] = (__u8)(600U >> 8);
    buf[off++] = 0x02U;
    buf[off++] = (__u8)(active_links & 0xffU);
    buf[off++] = (__u8)(active_links >> 8);

    *used = off;
    return 0;
}

#endif
