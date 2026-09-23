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

int main(void)
{
    __u8 buf[DNIV_WIRE_ENDNODE_FIXED_LEN + DNIV_WIRE_ENDNODE_TEST_MAX + 1U];
    struct dniv_wire_hello hello;
    unsigned int i;
    int len;

    len = dniv_wire_build_endnode_hello(buf, sizeof(buf), DNIV_ADDR(31, 71),
                                        10, NULL);
    assert(len == (int)DNIV_WIRE_ENDNODE_LEN);

    buf[31] = DNIV_WIRE_ENDNODE_TEST_MAX;
    for (i = DNIV_WIRE_ENDNODE_FIXED_LEN;
         i < DNIV_WIRE_ENDNODE_FIXED_LEN + DNIV_WIRE_ENDNODE_TEST_MAX; i++)
        buf[i] = 0xaaU;
    assert(dniv_wire_parse_hello(
               buf, DNIV_WIRE_ENDNODE_FIXED_LEN + DNIV_WIRE_ENDNODE_TEST_MAX,
               &hello) == DNIV_WIRE_OK);
    assert(hello.testdata_len == DNIV_WIRE_ENDNODE_TEST_MAX);
    assert(dniv_wire_endnode_test_valid(&hello));

    buf[31] = DNIV_WIRE_ENDNODE_TEST_MAX + 1U;
    buf[DNIV_WIRE_ENDNODE_FIXED_LEN + DNIV_WIRE_ENDNODE_TEST_MAX] = 0xaaU;
    assert(dniv_wire_parse_hello(
               buf, DNIV_WIRE_ENDNODE_FIXED_LEN + DNIV_WIRE_ENDNODE_TEST_MAX + 1U,
               &hello) == DNIV_WIRE_MALFORMED);

    puts("Endnode test-data boundary tests passed");
    return 0;
}
