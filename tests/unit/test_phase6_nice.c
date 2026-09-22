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

    {
        const __u8 summary_request[] = { 0x14, 0x00, 0x00, 0x00, 0x00 };
        const __u8 status_request[] = { 0x14, 0x10, 0x00, 0x00, 0x00 };

        assert(dniv_nice_parse_read_node(summary_request,
                                         sizeof(summary_request),
                                         &request) == 0);
        assert(request.info == DNIV_NICE_INFO_SUMMARY);
        assert(dniv_nice_parse_read_node(status_request,
                                         sizeof(status_request),
                                         &request) == 0);
        assert(request.info == DNIV_NICE_INFO_STATUS);
        assert(dniv_nice_build_node_status_reply(
                   reply, sizeof(reply), &reply_len,
                   DNIV_ADDR(31, 70), "DN70", 7U) == 0);
        assert(reply_len == 20U);
        assert(reply[11] == 0U && reply[12] == 0U);
        assert(reply[13] == 0x81U && reply[14] == 0U);
        assert(reply[15] == 0x58U && reply[16] == 0x02U);
        assert(reply[17] == 0x02U && reply[18] == 7U && reply[19] == 0U);
    }

    {
        struct dniv_nice_node_reply parsed;

        assert(dniv_nice_parse_node_reply(reply, reply_len, &parsed) == 0);
        assert(parsed.address == DNIV_ADDR(31, 70));
        assert(strcmp(parsed.name, "DN70") == 0);
        assert(parsed.has_state && parsed.state == 0U);
        assert(parsed.has_active_links && parsed.active_links == 7U);
        assert(dniv_nice_parse_node_reply(reply, 9U, &parsed) != 0);
    }

    {
        const __u8 counters_request[] = {
            0x14U, 0x30U, 0x00U, 0x00U, 0x00U
        };

        assert(dniv_nice_parse_read_node(counters_request,
                                         sizeof(counters_request),
                                         &request) == 0);
        assert(request.info == DNIV_NICE_INFO_COUNTERS);
        assert(dniv_nice_build_node_counters_reply(
                   reply, sizeof(reply), &reply_len,
                   DNIV_ADDR(31, 70), "DN70",
                   0x01020304ULL, 0x11121314ULL,
                   0x05060708ULL, 0x15161718ULL) == 0);
        assert(reply_len == 35U);
        assert(reply[11] == 0x60U && reply[12] == 0xe2U);
        assert(reply[13] == 0x04U && reply[14] == 0x03U &&
               reply[15] == 0x02U && reply[16] == 0x01U);
        assert(reply[17] == 0x61U && reply[18] == 0xe2U);
        assert(reply[19] == 0x14U && reply[20] == 0x13U &&
               reply[21] == 0x12U && reply[22] == 0x11U);
        assert(reply[23] == 0x62U && reply[24] == 0xe2U);
        assert(reply[25] == 0x08U && reply[26] == 0x07U &&
               reply[27] == 0x06U && reply[28] == 0x05U);
        assert(reply[29] == 0x63U && reply[30] == 0xe2U);
        assert(reply[31] == 0x18U && reply[32] == 0x17U &&
               reply[33] == 0x16U && reply[34] == 0x15U);
        assert(dniv_nice_build_node_counters_reply(
                   reply, sizeof(reply), &reply_len,
                   DNIV_ADDR(31, 70), "DN70",
                   0x100000000ULL, 0x100000000ULL,
                   0x100000000ULL, 0x100000000ULL) == 0);
        assert(reply[13] == 0xffU && reply[14] == 0xffU &&
               reply[15] == 0xffU && reply[16] == 0xffU);
        assert(reply[19] == 0xffU && reply[20] == 0xffU &&
               reply[21] == 0xffU && reply[22] == 0xffU);
        assert(reply[25] == 0xffU && reply[26] == 0xffU &&
               reply[27] == 0xffU && reply[28] == 0xffU);
        assert(reply[31] == 0xffU && reply[32] == 0xffU &&
               reply[33] == 0xffU && reply[34] == 0xffU);
    }

    {
        const __u8 circuit_request[] = {
            0x14U, 0x13U, 0x05U, 'E', 'T', 'H', '-', '0'
        };
        struct dniv_nice_read_circuit circuit;

        assert(dniv_nice_parse_read_circuit(circuit_request,
                                             sizeof(circuit_request),
                                             &circuit) == 0);
        assert(circuit.info == DNIV_NICE_INFO_STATUS);
        assert(circuit.permanent == 0U);
        assert(strcmp(circuit.name, "ETH-0") == 0);
        assert(dniv_nice_build_circuit_status_reply(
                   reply, sizeof(reply), &reply_len, "ETH-0", 1498U) == 0);
        assert(reply_len == 19U);
        assert(reply[0] == 1U && reply[1] == 0xffU && reply[2] == 0xffU);
        assert(reply[3] == 0U && reply[4] == 5U);
        assert(memcmp(reply + 5U, "ETH-0", 5U) == 0);
        assert(reply[10] == 0U && reply[11] == 0U &&
               reply[12] == 0x81U && reply[13] == 0U);
        assert(reply[14] == 0x2aU && reply[15] == 0x03U &&
               reply[16] == 0x02U && reply[17] == 0xdaU &&
               reply[18] == 0x05U);

        {
            const __u8 counters_request[] = {
                0x14U, 0x33U, 0x05U, 'E', 'T', 'H', '-', '0'
            };

            assert(dniv_nice_parse_read_circuit(
                       counters_request, sizeof(counters_request),
                       &circuit) == 0);
            assert(circuit.info == DNIV_NICE_INFO_COUNTERS);
            assert(dniv_nice_build_circuit_counters_reply(
                       reply, sizeof(reply), &reply_len, "ETH-0",
                       0x01020304ULL, 0x11121314ULL,
                       0x05060708ULL, 0x15161718ULL) == 0);
            assert(reply_len == 34U);
            assert(reply[10] == 0xe8U && reply[11] == 0xe3U);
            assert(reply[12] == 0x04U && reply[13] == 0x03U &&
                   reply[14] == 0x02U && reply[15] == 0x01U);
            assert(reply[16] == 0xe9U && reply[17] == 0xe3U);
            assert(reply[18] == 0x14U && reply[19] == 0x13U &&
                   reply[20] == 0x12U && reply[21] == 0x11U);
            assert(reply[22] == 0xf2U && reply[23] == 0xe3U);
            assert(reply[24] == 0x08U && reply[25] == 0x07U &&
                   reply[26] == 0x06U && reply[27] == 0x05U);
            assert(reply[28] == 0xf3U && reply[29] == 0xe3U);
            assert(reply[30] == 0x18U && reply[31] == 0x17U &&
                   reply[32] == 0x16U && reply[33] == 0x15U);
        }
    }

    puts("Phase 6 NICE codec tests passed");
    return 0;
}
