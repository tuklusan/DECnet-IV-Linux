/* SPDX-License-Identifier: GPL-2.0 */
#ifndef _DECNET_IV_WIRE_H
#define _DECNET_IV_WIRE_H

#include <linux/types.h>
#include <linux/decnet_iv.h>

#define DNIV_WIRE_ETH_ALEN 6U
#define DNIV_WIRE_ROUTER_HELLO 0x0bU
#define DNIV_WIRE_ENDNODE_HELLO 0x0dU
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
#define DNIV_WIRE_ENDNODE_LEN \
    (DNIV_WIRE_ENDNODE_FIXED_LEN + DNIV_WIRE_ENDNODE_TEST_LEN)

#define DNIV_WIRE_OK 0
#define DNIV_WIRE_NOT_HELLO 1
#define DNIV_WIRE_MALFORMED (-1)

struct dniv_wire_rs_entry {
    __u16 address;
    __u8 priority;
    __u8 twoway;
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
    if ((__u32)DNIV_WIRE_ENDNODE_FIXED_LEN + hello->testdata_len > len)
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

#endif /* _DECNET_IV_WIRE_H */
