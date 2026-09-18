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

static void test_short_data(void)
{
    __u8 buf[] = {0x02,0x03,0x04,0x01,0x08,0x11,'a','b','c'};
    struct dniv_wire_data data;

    assert(dniv_wire_parse_data(buf, sizeof(buf), &data) == DNIV_WIRE_OK);
    assert(data.destination == DNIV_ADDR(1, 3));
    assert(data.source == DNIV_ADDR(2, 1));
    assert(data.visit == 17);
    assert(data.payload_len == 3);
    assert(memcmp(data.payload, "abc", 3) == 0);
    assert(dniv_wire_data_increment_visit(buf, sizeof(buf), &data) == 0);
    assert((buf[5] & 0x3fU) == 18U);
}

static void test_long_data(void)
{
    __u8 buf[] = {
        0x26,0x00,0x00,0xaa,0x00,0x04,0x00,0x03,0x04,
        0x00,0x00,0xaa,0x00,0x04,0x00,0x01,0x08,0x00,
        0x11,0x00,0x00,'x'
    };
    struct dniv_wire_data data;

    assert(dniv_wire_parse_data(buf, sizeof(buf), &data) == DNIV_WIRE_OK);
    assert(data.destination == DNIV_ADDR(1, 3));
    assert(data.source == DNIV_ADDR(2, 1));
    assert(data.visit == 17);
    assert(data.is_long == 1U);
    assert(data.payload_len == 1U && data.payload[0] == 'x');
    assert(dniv_wire_data_increment_visit(buf, sizeof(buf), &data) == 0);
    assert(buf[18] == 18U);
}

static void test_padding_and_limit(void)
{
    __u8 padded[] = {0x82,0x00,0x02,0x03,0x04,0x01,0x08,0x1f};
    __u8 bad_addr[] = {0x02,0x00,0x00,0x01,0x08,0x01};
    struct dniv_wire_data data;

    assert(dniv_wire_parse_data(padded, sizeof(padded), &data) == DNIV_WIRE_OK);
    assert(data.visit == DNIV_WIRE_MAX_VISIT);
    assert(data.visit_offset == 7U);
    assert(dniv_wire_data_increment_visit(padded, sizeof(padded), &data) < 0);
    assert(dniv_wire_parse_data(bad_addr, sizeof(bad_addr), &data) ==
           DNIV_WIRE_MALFORMED);
}

int main(void)
{
    test_short_data();
    test_long_data();
    test_padding_and_limit();
    puts("phase4 data packet tests passed");
    return 0;
}
