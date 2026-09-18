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

#include <assert.h>
#include <decnet_iv_wire.h>
#include <stdio.h>
#include <string.h>

static void test_l1_vector(void)
{
    static const __u8 vector[] = {
        0x07, 0x03, 0x00, 0x00, 0x02, 0x00, 0x05, 0x00,
        0xff, 0x7f, 0x06, 0x08, 0x0d, 0x88
    };
    struct dniv_wire_route_message msg;
    struct dniv_wire_route_segment_view seg;

    assert(dniv_wire_parse_routing(vector, sizeof(vector), &msg) ==
           DNIV_WIRE_OK);
    assert(msg.level == 1);
    assert(msg.source == 3);
    assert(msg.segment_count == 1);
    assert(dniv_wire_route_segment_at(&msg, 0, &seg) == 0);
    assert(seg.start == 5);
    assert(seg.count == 2);
    assert(dniv_wire_route_entry(&seg, 0) == 0x7fff);
    assert(dniv_wire_route_entry(&seg, 1) == 0x0806);
    assert(dniv_wire_route_segment_at(&msg, 1, &seg) < 0);
}

static void test_exact_encodings(void)
{
    static const __u8 l1_expected[] = {
        0x07, 0x04, 0x00, 0x00, 0x02, 0x00, 0x03, 0x00,
        0x05, 0x04, 0x63, 0x14, 0x6e, 0x18
    };
    static const __u8 l2_expected[] = {
        0x09, 0x04, 0x00, 0x00, 0x02, 0x00, 0x03, 0x00,
        0x05, 0x04, 0x63, 0x14, 0x6e, 0x18
    };
    __u16 entries[] = {0x0405, 0x1463};
    struct dniv_wire_route_segment seg = {
        .start = 3, .count = 2, .entries = entries
    };
    __u8 buf[64];
    int len;

    len = dniv_wire_build_routing(buf, sizeof(buf), 4, 1, &seg, 1);
    assert(len == (int)sizeof(l1_expected));
    assert(memcmp(buf, l1_expected, sizeof(l1_expected)) == 0);

    len = dniv_wire_build_routing(buf, sizeof(buf), 4, 2, &seg, 1);
    assert(len == (int)sizeof(l2_expected));
    assert(memcmp(buf, l2_expected, sizeof(l2_expected)) == 0);
}

static void test_multiple_segments(void)
{
    __u16 a[] = {0x0401, 0x0802};
    __u16 b[] = {0x0c03};
    struct dniv_wire_route_segment segs[] = {
        {.start = 0, .count = 2, .entries = a},
        {.start = 1023, .count = 1, .entries = b}
    };
    struct dniv_wire_route_message msg;
    struct dniv_wire_route_segment_view seg;
    __u8 buf[64];
    int len;

    len = dniv_wire_build_routing(buf, sizeof(buf), DNIV_ADDR(31, 70),
                                  1, segs, 2);
    assert(len > 0);
    assert(dniv_wire_parse_routing(buf, (__u32)len, &msg) == DNIV_WIRE_OK);
    assert(msg.segment_count == 2);
    assert(dniv_wire_route_segment_at(&msg, 1, &seg) == 0);
    assert(seg.start == 1023);
    assert(seg.count == 1);
    assert(dniv_wire_route_entry(&seg, 0) == 0x0c03);
}

static void test_boundaries(void)
{
    __u16 entry = 0;
    struct dniv_wire_route_segment seg = {
        .start = 0, .count = 1, .entries = &entry
    };
    __u8 buf[64];

    assert(dniv_wire_build_routing(buf, sizeof(buf), 1, 1, &seg, 1) > 0);
    seg.start = 1023;
    assert(dniv_wire_build_routing(buf, sizeof(buf), 1, 1, &seg, 1) > 0);
    seg.start = 1024;
    assert(dniv_wire_build_routing(buf, sizeof(buf), 1, 1, &seg, 1) == 0);
    seg.start = 1023;
    seg.count = 2;
    assert(dniv_wire_build_routing(buf, sizeof(buf), 1, 1, &seg, 1) == 0);
    seg.count = 0;
    assert(dniv_wire_build_routing(buf, sizeof(buf), 1, 1, &seg, 1) == 0);

    seg.start = 1;
    seg.count = 1;
    assert(dniv_wire_build_routing(buf, sizeof(buf), 1, 2, &seg, 1) > 0);
    seg.start = 63;
    assert(dniv_wire_build_routing(buf, sizeof(buf), 1, 2, &seg, 1) > 0);
    seg.start = 0;
    assert(dniv_wire_build_routing(buf, sizeof(buf), 1, 2, &seg, 1) == 0);
    seg.start = 63;
    seg.count = 2;
    assert(dniv_wire_build_routing(buf, sizeof(buf), 1, 2, &seg, 1) == 0);
}

static void test_malformed(void)
{
    static const __u8 good[] = {
        0x07, 0x03, 0x00, 0x00, 0x02, 0x00, 0x05, 0x00,
        0xff, 0x7f, 0x06, 0x08, 0x0d, 0x88
    };
    struct dniv_wire_route_message msg;
    __u8 buf[32];

    assert(dniv_wire_parse_routing(NULL, sizeof(good), &msg) ==
           DNIV_WIRE_MALFORMED);
    assert(dniv_wire_parse_routing(good, sizeof(good), NULL) ==
           DNIV_WIRE_MALFORMED);
    assert(dniv_wire_parse_routing(good, sizeof(good) - 1U, &msg) ==
           DNIV_WIRE_MALFORMED);

    memcpy(buf, good, sizeof(good));
    buf[3] = 1;
    assert(dniv_wire_parse_routing(buf, sizeof(good), &msg) ==
           DNIV_WIRE_MALFORMED);

    memcpy(buf, good, sizeof(good));
    buf[4] = 0;
    buf[5] = 0;
    dniv_wire_put_le16(buf + sizeof(good) - 2U,
                       dniv_wire_route_checksum(
                           buf + DNIV_WIRE_ROUTE_HEADER_LEN,
                           (sizeof(good) - DNIV_WIRE_ROUTE_HEADER_LEN -
                            DNIV_WIRE_ROUTE_CHECKSUM_LEN) / 2U));
    assert(dniv_wire_parse_routing(buf, sizeof(good), &msg) ==
           DNIV_WIRE_MALFORMED);

    memcpy(buf, good, sizeof(good));
    buf[6] = 0x00;
    buf[7] = 0x04;
    dniv_wire_put_le16(buf + sizeof(good) - 2U,
                       dniv_wire_route_checksum(
                           buf + DNIV_WIRE_ROUTE_HEADER_LEN,
                           (sizeof(good) - DNIV_WIRE_ROUTE_HEADER_LEN -
                            DNIV_WIRE_ROUTE_CHECKSUM_LEN) / 2U));
    assert(dniv_wire_parse_routing(buf, sizeof(good), &msg) ==
           DNIV_WIRE_MALFORMED);

    memcpy(buf, good, sizeof(good));
    buf[9] |= 0x80;
    dniv_wire_put_le16(buf + sizeof(good) - 2U,
                       dniv_wire_route_checksum(
                           buf + DNIV_WIRE_ROUTE_HEADER_LEN,
                           (sizeof(good) - DNIV_WIRE_ROUTE_HEADER_LEN -
                            DNIV_WIRE_ROUTE_CHECKSUM_LEN) / 2U));
    assert(dniv_wire_parse_routing(buf, sizeof(good), &msg) ==
           DNIV_WIRE_MALFORMED);

    memcpy(buf, good, sizeof(good));
    buf[sizeof(good) - 1U] ^= 1U;
    assert(dniv_wire_parse_routing(buf, sizeof(good), &msg) ==
           DNIV_WIRE_MALFORMED);

    memcpy(buf + 1, good, sizeof(good));
    buf[0] = 0x81;
    assert(dniv_wire_parse_routing(buf, sizeof(good) + 1U, &msg) ==
           DNIV_WIRE_OK);
    buf[0] = 0x80;
    assert(dniv_wire_parse_routing(buf, sizeof(good) + 1U, &msg) ==
           DNIV_WIRE_MALFORMED);

    buf[0] = DNIV_WIRE_ROUTER_HELLO;
    assert(dniv_wire_parse_routing(buf, 1, &msg) == DNIV_WIRE_NOT_ROUTING);
}

int main(void)
{
    test_l1_vector();
    test_exact_encodings();
    test_multiple_segments();
    test_boundaries();
    test_malformed();
    puts("phase4 routing codec tests passed");
    return 0;
}
