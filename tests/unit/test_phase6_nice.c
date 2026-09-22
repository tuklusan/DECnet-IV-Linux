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
#include <decnet_iv_nice.h>
#include <linux/decnet_iv.h>
#include <stdio.h>
#include <string.h>

int main(void)
{
    const __u8 request_bytes[] = { 0x14, 0x20, 0x00, 0x00, 0x00 };
    struct dniv_nice_read_node request;
    __u8 reply[128];
    size_t reply_len = 0U;
    size_t entity_off;

    assert(dniv_nice_parse_read_node(request_bytes, sizeof(request_bytes),
                                     &request) == 0);
    assert(request.node == 0U);
    assert(request.info == DNIV_NICE_INFO_CHARACTERISTICS);
    assert(request.permanent == 0U);

    {
        __u8 bad[sizeof(request_bytes)];

        memcpy(bad, request_bytes, sizeof(bad));
        bad[0] = 0x13;
        assert(dniv_nice_parse_read_node(bad, sizeof(bad), &request) != 0);
        memcpy(bad, request_bytes, sizeof(bad));
        bad[1] |= 0x08U;
        assert(dniv_nice_parse_read_node(bad, sizeof(bad), &request) != 0);
        assert(dniv_nice_parse_read_node(request_bytes,
                                         sizeof(request_bytes) - 1U,
                                         &request) != 0);
    }

    assert(dniv_nice_build_node_reply(reply, sizeof(reply), &reply_len,
                                      DNIV_ADDR(31, 70), "DN70",
                                      "DECnet-IV-Linux") == 0);
    assert(reply_len == 30U);
    assert(reply[0] == 1U);
    assert(reply[1] == 0xffU && reply[2] == 0xffU);
    assert(reply[3] == 0U);
    assert(reply[4] == 0x46U && reply[5] == 0x7cU);
    assert(reply[6] == 0x84U);
    assert(memcmp(reply + 7U, "DN70", 4U) == 0);

    entity_off = 11U;
    assert(reply[entity_off] == 100U && reply[entity_off + 1U] == 0U);
    assert(reply[entity_off + 2U] == DNIV_NICE_TYPE_ASCII);
    assert(reply[entity_off + 3U] == 15U);
    assert(memcmp(reply + entity_off + 4U, "DECnet-IV-Linux", 15U) == 0);

    assert(dniv_nice_build_node_reply(reply, 8U, &reply_len,
                                      DNIV_ADDR(31, 70), "DN70",
                                      "DECnet-IV-Linux") != 0);
    puts("Phase 6 NICE codec tests passed");
    return 0;
}
