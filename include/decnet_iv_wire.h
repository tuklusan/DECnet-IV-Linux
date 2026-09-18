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

#ifndef _DECNET_IV_WIRE_H
#define _DECNET_IV_WIRE_H

#include <linux/types.h>
#include <linux/decnet_iv.h>

#define DNIV_WIRE_ETH_ALEN 6U
#define DNIV_WIRE_ETH_LENGTH_LEN 2U
#define DNIV_WIRE_ROUTER_HELLO 0x0bU
#define DNIV_WIRE_ENDNODE_HELLO 0x0dU
#define DNIV_WIRE_L1_ROUTING 0x07U
#define DNIV_WIRE_L2_ROUTING 0x09U
#define DNIV_WIRE_VERSION_MAJOR 2U
#define DNIV_WIRE_VERSION_MINOR 0U
#define DNIV_WIRE_VERSION_ECO 0U
#define DNIV_WIRE_BLOCK_SIZE 1498U
#define DNIV_WIRE_ROUTER_FIXED_LEN 19U
#define DNIV_WIRE_ROUTER_MIN_ELIST_LEN 8U
#define DNIV_WIRE_ROUTER_MIN_LEN 27U
#define DNIV_WIRE_RS_ENTRY_LEN 7U
#define DNIV_WIRE_MAX_RS_ENTRIES 33U
#define DNIV_WIRE_ENDNODE_FIXED_LEN 32U
#define DNIV_WIRE_ENDNODE_TEST_LEN 50U
#define DNIV_WIRE_ENDNODE_TEST_MAX 128U
#define DNIV_WIRE_ENDNODE_LEN \
    (DNIV_WIRE_ENDNODE_FIXED_LEN + DNIV_WIRE_ENDNODE_TEST_LEN)
#define DNIV_WIRE_ROUTE_HEADER_LEN 4U
#define DNIV_WIRE_ROUTE_SEGMENT_HEADER_LEN 4U
#define DNIV_WIRE_ROUTE_CHECKSUM_LEN 2U
#define DNIV_WIRE_ROUTE_ENTRY_LEN 2U
#define DNIV_WIRE_ROUTE_L1_LIMIT 1024U
#define DNIV_WIRE_ROUTE_L2_LIMIT 64U
#define DNIV_WIRE_ROUTE_RESERVED_MASK 0x8000U

#define DNIV_WIRE_OK 0
#define DNIV_WIRE_NOT_HELLO 1
#define DNIV_WIRE_NOT_ROUTING 2
#define DNIV_WIRE_MALFORMED (-1)

struct dniv_wire_rs_entry {
    __u16 address;
    __u8 priority;
    __u8 twoway;
};

struct dniv_wire_route_segment {
    __u16 start;
    __u16 count;
    const __u16 *entries;
};

struct dniv_wire_route_message {
    __u16 source;
    __u8 level;
    __u16 segment_count;
    const __u8 *segments;
    __u32 segments_len;
};

struct dniv_wire_route_segment_view {
    __u16 start;
    __u16 count;
    const __u8 *entries;
};

struct dniv_wire_hello {
    __u16 address;
    __u16 block_size;
    __u16 timer;
    __u8 node_type;
    __u8 priority;
    __u8 is_router;
    __u8 rs_count;
    const __u8 *rslist;
    const __u8 *testdata;
    __u8 testdata_len;
};

static inline __u16 dniv_wire_get_le16(const __u8 *p)
{
    return (__u16)((__u16)p[0] | ((__u16)p[1] << 8));
}

static inline void dniv_wire_put_le16(__u8 *p, __u16 value)
{
    p[0] = (__u8)(value & 0xffU);
    p[1] = (__u8)(value >> 8);
}

static inline int dniv_wire_eth_payload(const __u8 *buf, __u32 len,
                                        const __u8 **payload,
                                        __u16 *payload_len)
{
    __u16 value;

    if (!buf || !payload || !payload_len || len < DNIV_WIRE_ETH_LENGTH_LEN)
        return -1;
    value = dniv_wire_get_le16(buf);
    if (value == 0U || value > DNIV_WIRE_BLOCK_SIZE ||
        len < DNIV_WIRE_ETH_LENGTH_LEN + (__u32)value)
        return -1;
    *payload = buf + DNIV_WIRE_ETH_LENGTH_LEN;
    *payload_len = value;
    return 0;
}

static inline int dniv_wire_address_valid(__u16 address)
{
    return DNIV_ADDR_AREA(address) >= 1U && DNIV_ADDR_AREA(address) <= 63U &&
           DNIV_ADDR_NODE(address) >= 1U && DNIV_ADDR_NODE(address) <= 1023U;
}

static inline void dniv_wire_mac_from_address(__u16 address,
                                               __u8 mac[DNIV_WIRE_ETH_ALEN])
{
    mac[0] = 0xaaU;
    mac[1] = 0x00U;
    mac[2] = 0x04U;
    mac[3] = 0x00U;
    mac[4] = (__u8)(address & 0xffU);
    mac[5] = (__u8)(address >> 8);
}

static inline int dniv_wire_address_from_mac(const __u8 mac[DNIV_WIRE_ETH_ALEN],
                                              __u16 *address)
{
    __u16 value;

    if (!mac || !address)
        return -1;
    if (mac[0] != 0xaaU || mac[1] != 0x00U ||
        mac[2] != 0x04U || mac[3] != 0x00U)
        return -1;
    value = dniv_wire_get_le16(mac + 4);
    if (!dniv_wire_address_valid(value))
        return -1;
    *address = value;
    return 0;
}

static inline int dniv_wire_node_type_valid(__u8 node_type)
{
    return node_type == DNIV_NODE_TYPE_L2_ROUTER ||
           node_type == DNIV_NODE_TYPE_L1_ROUTER ||
           node_type == DNIV_NODE_TYPE_ENDNODE;
}

static inline int dniv_wire_mac_equal(const __u8 left[DNIV_WIRE_ETH_ALEN],
                                      const __u8 right[DNIV_WIRE_ETH_ALEN])
{
    __u32 i;

    if (!left || !right)
        return 0;
    for (i = 0; i < DNIV_WIRE_ETH_ALEN; i++) {
        if (left[i] != right[i])
            return 0;
    }
    return 1;
}

static inline int dniv_wire_destination_valid(
    __u16 local_address, __u8 local_node_type,
    const __u8 destination[DNIV_WIRE_ETH_ALEN])
{
    static const __u8 all_routers[DNIV_WIRE_ETH_ALEN] = {
        0xabU, 0x00U, 0x00U, 0x03U, 0x00U, 0x00U
    };
    static const __u8 all_level2_routers[DNIV_WIRE_ETH_ALEN] = {
        0x09U, 0x00U, 0x2bU, 0x02U, 0x00U, 0x00U
    };
    static const __u8 all_endnodes[DNIV_WIRE_ETH_ALEN] = {
        0xabU, 0x00U, 0x00U, 0x04U, 0x00U, 0x00U
    };
    __u8 local_mac[DNIV_WIRE_ETH_ALEN];

    if (!destination || !dniv_wire_address_valid(local_address) ||
        !dniv_wire_node_type_valid(local_node_type))
        return 0;

    dniv_wire_mac_from_address(local_address, local_mac);
    if (dniv_wire_mac_equal(destination, local_mac))
        return 1;
    if (local_node_type == DNIV_NODE_TYPE_ENDNODE)
        return dniv_wire_mac_equal(destination, all_endnodes);
    if (dniv_wire_mac_equal(destination, all_routers))
        return 1;
    return local_node_type == DNIV_NODE_TYPE_L2_ROUTER &&
           dniv_wire_mac_equal(destination, all_level2_routers);
}

static inline void dniv_wire_zero(__u8 *buf, __u32 len)
{
    __u32 i;

    for (i = 0; i < len; i++)
        buf[i] = 0;
}

static inline int dniv_wire_build_router_hello(
    __u8 *buf, __u32 capacity, __u16 address, __u8 node_type,
    __u8 priority, __u16 timer, const struct dniv_wire_rs_entry *entries,
    __u8 entry_count)
{
    __u32 len;
    __u32 i;

    if (!buf || !dniv_wire_address_valid(address) ||
        (node_type != DNIV_NODE_TYPE_L1_ROUTER &&
         node_type != DNIV_NODE_TYPE_L2_ROUTER) ||
        priority > 127U || entry_count > DNIV_WIRE_MAX_RS_ENTRIES ||
        (entry_count && !entries))
        return 0;
    len = DNIV_WIRE_ROUTER_MIN_LEN +
          (__u32)entry_count * DNIV_WIRE_RS_ENTRY_LEN;
    if (capacity < len)
        return 0;

    dniv_wire_zero(buf, len);
    buf[0] = DNIV_WIRE_ROUTER_HELLO;
    buf[1] = DNIV_WIRE_VERSION_MAJOR;
    buf[2] = DNIV_WIRE_VERSION_MINOR;
    buf[3] = DNIV_WIRE_VERSION_ECO;
    dniv_wire_mac_from_address(address, buf + 4);
    buf[10] = node_type;
    dniv_wire_put_le16(buf + 11, DNIV_WIRE_BLOCK_SIZE);
    buf[13] = priority;
    dniv_wire_put_le16(buf + 15, timer);
    buf[18] = (__u8)(DNIV_WIRE_ROUTER_MIN_ELIST_LEN +
                     entry_count * DNIV_WIRE_RS_ENTRY_LEN);
    buf[26] = (__u8)(entry_count * DNIV_WIRE_RS_ENTRY_LEN);

    for (i = 0; i < entry_count; i++) {
        __u8 *entry = buf + DNIV_WIRE_ROUTER_MIN_LEN +
                      i * DNIV_WIRE_RS_ENTRY_LEN;

        if (!dniv_wire_address_valid(entries[i].address) ||
            entries[i].priority > 127U)
            return 0;
        dniv_wire_mac_from_address(entries[i].address, entry);
        entry[6] = (__u8)(entries[i].priority |
                          (entries[i].twoway ? 0x80U : 0x00U));
    }
    return (int)len;
}

static inline int dniv_wire_build_endnode_hello(
    __u8 *buf, __u32 capacity, __u16 address, __u16 timer,
    const __u8 neighbor[DNIV_WIRE_ETH_ALEN])
{
    __u32 i;

    if (!buf || !dniv_wire_address_valid(address) ||
        capacity < DNIV_WIRE_ENDNODE_LEN)
        return 0;

    dniv_wire_zero(buf, DNIV_WIRE_ENDNODE_LEN);
    buf[0] = DNIV_WIRE_ENDNODE_HELLO;
    buf[1] = DNIV_WIRE_VERSION_MAJOR;
    buf[2] = DNIV_WIRE_VERSION_MINOR;
    buf[3] = DNIV_WIRE_VERSION_ECO;
    dniv_wire_mac_from_address(address, buf + 4);
    buf[10] = DNIV_NODE_TYPE_ENDNODE;
    dniv_wire_put_le16(buf + 11, DNIV_WIRE_BLOCK_SIZE);
    if (neighbor) {
        for (i = 0; i < DNIV_WIRE_ETH_ALEN; i++)
            buf[22 + i] = neighbor[i];
    }
    dniv_wire_put_le16(buf + 28, timer);
    buf[31] = DNIV_WIRE_ENDNODE_TEST_LEN;
    for (i = 0; i < DNIV_WIRE_ENDNODE_TEST_LEN; i++)
        buf[32 + i] = 0xaaU;
    return (int)DNIV_WIRE_ENDNODE_LEN;
}

static inline int dniv_wire_parse_hello(const __u8 *buf, __u32 len,
                                         struct dniv_wire_hello *hello)
{
    __u8 flags;
    __u8 pad;
    __u8 elist_len;
    __u8 rslist_len;
    __u32 i;

    if (!buf || !hello || len == 0U)
        return DNIV_WIRE_MALFORMED;

    if (buf[0] & 0x80U) {
        pad = (__u8)(buf[0] & 0x7fU);
        if (pad == 0U || pad >= len)
            return DNIV_WIRE_MALFORMED;
        buf += pad;
        len -= pad;
        if (buf[0] & 0x80U)
            return DNIV_WIRE_MALFORMED;
    }

    flags = buf[0];
    if (flags != DNIV_WIRE_ROUTER_HELLO && flags != DNIV_WIRE_ENDNODE_HELLO)
        return DNIV_WIRE_NOT_HELLO;

    hello->address = 0;
    hello->block_size = 0;
    hello->timer = 0;
    hello->node_type = 0;
    hello->priority = 0;
    hello->is_router = 0;
    hello->rs_count = 0;
    hello->rslist = (const __u8 *)0;
    hello->testdata = (const __u8 *)0;
    hello->testdata_len = 0;

    if (flags == DNIV_WIRE_ROUTER_HELLO) {
        if (len < DNIV_WIRE_ROUTER_MIN_LEN || buf[1] < DNIV_WIRE_VERSION_MAJOR ||
            dniv_wire_address_from_mac(buf + 4, &hello->address) != 0)
            return DNIV_WIRE_MALFORMED;
        hello->node_type = (__u8)(buf[10] & 0x03U);
        if (hello->node_type != DNIV_NODE_TYPE_L1_ROUTER &&
            hello->node_type != DNIV_NODE_TYPE_L2_ROUTER)
            return DNIV_WIRE_MALFORMED;
        hello->block_size = dniv_wire_get_le16(buf + 11);
        hello->priority = buf[13];
        if (hello->priority > 127U)
            return DNIV_WIRE_MALFORMED;
        hello->timer = dniv_wire_get_le16(buf + 15);
        elist_len = buf[18];
        if (elist_len < DNIV_WIRE_ROUTER_MIN_ELIST_LEN ||
            (__u32)DNIV_WIRE_ROUTER_FIXED_LEN + elist_len > len)
            return DNIV_WIRE_MALFORMED;
        rslist_len = buf[26];
        if (elist_len != (__u8)(DNIV_WIRE_ROUTER_MIN_ELIST_LEN + rslist_len) ||
            rslist_len % DNIV_WIRE_RS_ENTRY_LEN != 0U)
            return DNIV_WIRE_MALFORMED;
        hello->rs_count = (__u8)(rslist_len / DNIV_WIRE_RS_ENTRY_LEN);
        if (hello->rs_count > DNIV_WIRE_MAX_RS_ENTRIES)
            return DNIV_WIRE_MALFORMED;
        hello->rslist = buf + DNIV_WIRE_ROUTER_MIN_LEN;
        for (i = 0; i < hello->rs_count; i++) {
            __u16 unused;
            const __u8 *entry = hello->rslist + i * DNIV_WIRE_RS_ENTRY_LEN;

            if (dniv_wire_address_from_mac(entry, &unused) != 0)
                return DNIV_WIRE_MALFORMED;
        }
        hello->is_router = 1;
        return DNIV_WIRE_OK;
    }

    if (len < DNIV_WIRE_ENDNODE_FIXED_LEN || buf[1] < DNIV_WIRE_VERSION_MAJOR ||
        dniv_wire_address_from_mac(buf + 4, &hello->address) != 0)
        return DNIV_WIRE_MALFORMED;
    hello->node_type = (__u8)(buf[10] & 0x03U);
    if (hello->node_type != DNIV_NODE_TYPE_ENDNODE)
        return DNIV_WIRE_MALFORMED;
    hello->block_size = dniv_wire_get_le16(buf + 11);
    hello->timer = dniv_wire_get_le16(buf + 28);
    hello->testdata_len = buf[31];
    if (hello->testdata_len > DNIV_WIRE_ENDNODE_TEST_MAX ||
        (__u32)DNIV_WIRE_ENDNODE_FIXED_LEN + hello->testdata_len > len)
        return DNIV_WIRE_MALFORMED;
    hello->testdata = buf + DNIV_WIRE_ENDNODE_FIXED_LEN;
    return DNIV_WIRE_OK;
}

static inline int dniv_wire_router_lists(const struct dniv_wire_hello *hello,
                                          __u16 address, __u8 *priority,
                                          __u8 *twoway)
{
    __u32 i;

    if (!hello || !hello->is_router)
        return 0;
    for (i = 0; i < hello->rs_count; i++) {
        const __u8 *entry = hello->rslist + i * DNIV_WIRE_RS_ENTRY_LEN;

        if (dniv_wire_get_le16(entry + 4) == address) {
            if (priority)
                *priority = (__u8)(entry[6] & 0x7fU);
            if (twoway)
                *twoway = (__u8)((entry[6] & 0x80U) != 0U);
            return 1;
        }
    }
    return 0;
}

static inline __u32 dniv_wire_listen_msecs(__u16 timer, __u16 fallback)
{
    __u32 interval = timer ? timer : fallback;

    return interval * 3100U;
}

static inline int dniv_wire_router_adjacency_state(
    const struct dniv_wire_hello *hello, __u16 local_address,
    __u8 local_priority, __u8 *state)
{
    __u8 listed_priority = 0;

    if (!hello || !hello->is_router || !state)
        return -1;
    if (dniv_wire_router_lists(hello, local_address, &listed_priority, 0)) {
        if (listed_priority != local_priority)
            return -1;
        *state = DNIV_ADJ_STATE_UP;
    } else {
        *state = DNIV_ADJ_STATE_INIT;
    }
    return 0;
}

static inline int dniv_wire_endnode_test_valid(const struct dniv_wire_hello *hello)
{
    __u32 i;

    if (!hello || hello->is_router)
        return 0;
    for (i = 0; i < hello->testdata_len; i++) {
        if (hello->testdata[i] != 0xaaU)
            return 0;
    }
    return 1;
}


static inline int dniv_wire_route_source_valid(__u16 source)
{
    return DNIV_ADDR_NODE(source) >= 1U;
}

static inline int dniv_wire_route_segment_bounds_valid(
    __u8 level, __u16 start, __u16 count)
{
    __u32 end = (__u32)start + (__u32)count;

    if (count == 0U)
        return 0;
    if (level == 1U)
        return end <= DNIV_WIRE_ROUTE_L1_LIMIT;
    if (level == 2U)
        return start >= 1U && end <= DNIV_WIRE_ROUTE_L2_LIMIT;
    return 0;
}

static inline int dniv_wire_route_entry_valid(__u16 entry)
{
    return (entry & DNIV_WIRE_ROUTE_RESERVED_MASK) == 0U;
}

static inline __u16 dniv_wire_route_checksum(const __u8 *data,
                                              __u32 word_count)
{
    __u32 sum = 1U;
    __u32 i;

    for (i = 0; i < word_count; i++)
        sum += dniv_wire_get_le16(data + i * 2U);
    sum = (sum & 0xffffU) + (sum >> 16);
    sum = (sum & 0xffffU) + (sum >> 16);
    return (__u16)sum;
}

static inline int dniv_wire_build_routing(
    __u8 *buf, __u32 capacity, __u16 source, __u8 level,
    const struct dniv_wire_route_segment *segments, __u16 segment_count)
{
    __u32 len = DNIV_WIRE_ROUTE_HEADER_LEN + DNIV_WIRE_ROUTE_CHECKSUM_LEN;
    __u32 off;
    __u16 i;

    if (!buf || !dniv_wire_route_source_valid(source) ||
        (level != 1U && level != 2U) || !segments || segment_count == 0U)
        return 0;

    for (i = 0; i < segment_count; i++) {
        __u32 seglen;
        __u16 j;

        if (!segments[i].entries ||
            !dniv_wire_route_segment_bounds_valid(
                level, segments[i].start, segments[i].count))
            return 0;
        seglen = DNIV_WIRE_ROUTE_SEGMENT_HEADER_LEN +
                 (__u32)segments[i].count * DNIV_WIRE_ROUTE_ENTRY_LEN;
        if (seglen > DNIV_WIRE_BLOCK_SIZE ||
            len > DNIV_WIRE_BLOCK_SIZE - seglen)
            return 0;
        for (j = 0; j < segments[i].count; j++) {
            if (!dniv_wire_route_entry_valid(segments[i].entries[j]))
                return 0;
        }
        len += seglen;
    }
    if (len > capacity || len > DNIV_WIRE_BLOCK_SIZE)
        return 0;

    dniv_wire_zero(buf, len);
    buf[0] = level == 1U ? DNIV_WIRE_L1_ROUTING : DNIV_WIRE_L2_ROUTING;
    dniv_wire_put_le16(buf + 1, source);

    off = DNIV_WIRE_ROUTE_HEADER_LEN;
    for (i = 0; i < segment_count; i++) {
        __u16 j;

        dniv_wire_put_le16(buf + off, segments[i].count);
        dniv_wire_put_le16(buf + off + 2U, segments[i].start);
        off += DNIV_WIRE_ROUTE_SEGMENT_HEADER_LEN;
        for (j = 0; j < segments[i].count; j++) {
            dniv_wire_put_le16(buf + off, segments[i].entries[j]);
            off += DNIV_WIRE_ROUTE_ENTRY_LEN;
        }
    }

    dniv_wire_put_le16(
        buf + off,
        dniv_wire_route_checksum(
            buf + DNIV_WIRE_ROUTE_HEADER_LEN,
            (off - DNIV_WIRE_ROUTE_HEADER_LEN) / 2U));
    return (int)len;
}

static inline int dniv_wire_parse_routing(
    const __u8 *buf, __u32 len, struct dniv_wire_route_message *message)
{
    __u8 flags;
    __u8 pad;
    __u8 level;
    __u32 off;
    __u32 end;
    __u16 segcount = 0;
    __u16 checksum;

    if (!buf || !message || len == 0U)
        return DNIV_WIRE_MALFORMED;

    if (buf[0] & 0x80U) {
        pad = (__u8)(buf[0] & 0x7fU);
        if (pad == 0U || pad >= len)
            return DNIV_WIRE_MALFORMED;
        buf += pad;
        len -= pad;
        if (buf[0] & 0x80U)
            return DNIV_WIRE_MALFORMED;
    }

    flags = buf[0];
    if (flags == DNIV_WIRE_L1_ROUTING)
        level = 1U;
    else if (flags == DNIV_WIRE_L2_ROUTING)
        level = 2U;
    else
        return DNIV_WIRE_NOT_ROUTING;

    if (len < DNIV_WIRE_ROUTE_HEADER_LEN +
              DNIV_WIRE_ROUTE_SEGMENT_HEADER_LEN +
              DNIV_WIRE_ROUTE_ENTRY_LEN +
              DNIV_WIRE_ROUTE_CHECKSUM_LEN ||
        ((len - DNIV_WIRE_ROUTE_HEADER_LEN) & 1U) != 0U ||
        buf[3] != 0U ||
        !dniv_wire_route_source_valid(dniv_wire_get_le16(buf + 1)))
        return DNIV_WIRE_MALFORMED;

    checksum = dniv_wire_get_le16(buf + len - DNIV_WIRE_ROUTE_CHECKSUM_LEN);
    if (checksum !=
        dniv_wire_route_checksum(
            buf + DNIV_WIRE_ROUTE_HEADER_LEN,
            (len - DNIV_WIRE_ROUTE_HEADER_LEN -
             DNIV_WIRE_ROUTE_CHECKSUM_LEN) / 2U))
        return DNIV_WIRE_MALFORMED;

    off = DNIV_WIRE_ROUTE_HEADER_LEN;
    end = len - DNIV_WIRE_ROUTE_CHECKSUM_LEN;
    while (off < end) {
        __u16 count;
        __u16 start;
        __u16 j;
        __u32 seglen;

        if (end - off < DNIV_WIRE_ROUTE_SEGMENT_HEADER_LEN)
            return DNIV_WIRE_MALFORMED;
        count = dniv_wire_get_le16(buf + off);
        start = dniv_wire_get_le16(buf + off + 2U);
        if (!dniv_wire_route_segment_bounds_valid(level, start, count))
            return DNIV_WIRE_MALFORMED;

        seglen = DNIV_WIRE_ROUTE_SEGMENT_HEADER_LEN +
                 (__u32)count * DNIV_WIRE_ROUTE_ENTRY_LEN;
        if (seglen > end - off)
            return DNIV_WIRE_MALFORMED;
        for (j = 0; j < count; j++) {
            if (!dniv_wire_route_entry_valid(
                    dniv_wire_get_le16(
                        buf + off + DNIV_WIRE_ROUTE_SEGMENT_HEADER_LEN +
                        (__u32)j * DNIV_WIRE_ROUTE_ENTRY_LEN)))
                return DNIV_WIRE_MALFORMED;
        }
        off += seglen;
        segcount++;
    }

    if (off != end || segcount == 0U)
        return DNIV_WIRE_MALFORMED;

    message->source = dniv_wire_get_le16(buf + 1);
    message->level = level;
    message->segment_count = segcount;
    message->segments = buf + DNIV_WIRE_ROUTE_HEADER_LEN;
    message->segments_len = end - DNIV_WIRE_ROUTE_HEADER_LEN;
    return DNIV_WIRE_OK;
}

static inline int dniv_wire_route_segment_at(
    const struct dniv_wire_route_message *message, __u16 index,
    struct dniv_wire_route_segment_view *segment)
{
    __u32 off = 0;
    __u16 i;

    if (!message || !segment || index >= message->segment_count)
        return -1;

    for (i = 0; i <= index; i++) {
        __u16 count;

        if (message->segments_len - off <
            DNIV_WIRE_ROUTE_SEGMENT_HEADER_LEN)
            return -1;
        count = dniv_wire_get_le16(message->segments + off);
        if (i == index) {
            segment->count = count;
            segment->start = dniv_wire_get_le16(message->segments + off + 2U);
            segment->entries =
                message->segments + off + DNIV_WIRE_ROUTE_SEGMENT_HEADER_LEN;
            return 0;
        }
        off += DNIV_WIRE_ROUTE_SEGMENT_HEADER_LEN +
               (__u32)count * DNIV_WIRE_ROUTE_ENTRY_LEN;
    }
    return -1;
}

static inline __u16 dniv_wire_route_entry(
    const struct dniv_wire_route_segment_view *segment, __u16 index)
{
    if (!segment || index >= segment->count)
        return 0xffffU;
    return dniv_wire_get_le16(
        segment->entries + (__u32)index * DNIV_WIRE_ROUTE_ENTRY_LEN);
}

#endif /* _DECNET_IV_WIRE_H */
