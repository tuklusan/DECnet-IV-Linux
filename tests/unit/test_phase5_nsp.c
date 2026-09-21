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
#include <string.h>

#include "decnet_iv_nsp_wire.h"
#include "decnet_iv_nsp_state.h"

static void roundtrip(const unsigned char *wire, unsigned int len)
{
    struct dniv_nsp_packet p;
    unsigned char out[128];
    int n;

    assert(dniv_nsp_parse(wire, len, &p) == DNIV_NSP_OK);
    n = dniv_nsp_build(out, sizeof(out), &p);
    assert(n == (int)len);
    assert(memcmp(out, wire, len) == 0);
}

static void test_ack(void)
{
    const unsigned char a1[] = {0x04,0x03,0x00,0x05,0x01,0x02,0x80};
    const unsigned char a2[] = {
        0x04,0x03,0x00,0x05,0x01,0x02,0x80,0x05,0xb0
    };
    struct dniv_nsp_packet p;

    assert(dniv_nsp_parse(a1, sizeof(a1), &p) == DNIV_NSP_OK);
    assert(p.type == DNIV_NSP_ACK_DATA);
    assert(p.dst == 3U && p.src == 261U);
    assert(p.ack1.present && p.ack1.num == 2U &&
           p.ack1.qual == DNIV_NSP_ACK);
    assert(!p.ack2.present);
    roundtrip(a1, sizeof(a1));

    assert(dniv_nsp_parse(a2, sizeof(a2), &p) == DNIV_NSP_OK);
    assert(p.ack2.present && p.ack2.num == 5U &&
           p.ack2.qual == DNIV_NSP_XNAK);
    roundtrip(a2, sizeof(a2));
}

static void test_data(void)
{
    const unsigned char d[] = {
        0x60,0x03,0x00,0x05,0x01,0x07,0x00,
        'p','a','y','l','o','a','d'
    };
    const unsigned char d2[] = {
        0x40,0x03,0x00,0x05,0x01,0x09,0x80,0x06,0xa0,0x07,0x00,
        'p','a','y','l','o','a','d'
    };
    struct dniv_nsp_packet p;

    assert(dniv_nsp_parse(d, sizeof(d), &p) == DNIV_NSP_OK);
    assert(p.type == DNIV_NSP_DATA && p.bom == 1U && p.eom == 1U);
    assert(p.segnum == 7U && p.payload_len == 7U);
    roundtrip(d, sizeof(d));

    assert(dniv_nsp_parse(d2, sizeof(d2), &p) == DNIV_NSP_OK);
    assert(p.ack1.present && p.ack1.num == 9U);
    assert(p.ack2.present && p.ack2.qual == DNIV_NSP_XACK);
    roundtrip(d2, sizeof(d2));
}

static void test_control(void)
{
    const unsigned char ci[] = {
        0x18,0x00,0x00,0x03,0x00,0x05,0x02,0x04,0x02,
        'p','a','y','l','o','a','d'
    };
    const unsigned char rci[] = {
        0x68,0x00,0x00,0x03,0x00,0x05,0x02,0x04,0x02,
        'p','a','y','l','o','a','d'
    };
    const unsigned char cc[] = {
        0x28,0x0b,0x00,0x03,0x00,0x05,0x02,0x04,0x02,0x07,
        'p','a','y','l','o','a','d'
    };
    const unsigned char di[] = {
        0x38,0x0b,0x00,0x03,0x00,0x05,0x00,0x07,
        'p','a','y','l','o','a','d'
    };
    const unsigned char dc[] = {0x48,0x0b,0x00,0x03,0x00,0x2a,0x00};
    const unsigned char ca[] = {0x24,0x03,0x00};
    struct dniv_nsp_packet p;

    assert(dniv_nsp_parse(ci, sizeof(ci), &p) == DNIV_NSP_OK);
    assert(p.type == DNIV_NSP_CI && p.dst == 0U && p.src == 3U);
    assert(p.fcopt == 1U && p.info == 2U && p.segsize == 516U);
    roundtrip(ci, sizeof(ci));
    roundtrip(rci, sizeof(rci));
    roundtrip(cc, sizeof(cc));
    roundtrip(di, sizeof(di));
    roundtrip(dc, sizeof(dc));
    roundtrip(ca, sizeof(ca));
}

static void test_interrupt_and_link_service(void)
{
    const unsigned char intr[] = {
        0x30,0x03,0x00,0x05,0x01,0x07,0x00,
        'p','a','y','l','o','a','d'
    };
    const unsigned char ls[] = {
        0x10,0x03,0x00,0x05,0x01,0x07,0x00,0x06,0xfd
    };
    const unsigned char intr_hi[] = {
        0x30,0x03,0x00,0x05,0x01,0x07,0x70,'x'
    };
    const unsigned char ls_hi[] = {
        0x10,0x03,0x00,0x05,0x01,0x07,0x70,0x06,0xfd
    };
    unsigned char out[32];
    struct dniv_nsp_packet p;
    int n;

    roundtrip(intr, sizeof(intr));
    assert(dniv_nsp_parse(intr_hi, sizeof(intr_hi), &p) == DNIV_NSP_OK);
    assert(p.segnum == 7U && p.dly == 0U);
    n = dniv_nsp_build(out, sizeof(out), &p);
    assert(n == (int)sizeof(intr_hi) && out[6] == 0x00U);
    assert(dniv_nsp_parse(ls_hi, sizeof(ls_hi), &p) == DNIV_NSP_OK);
    assert(p.segnum == 7U && p.dly == 0U);
    n = dniv_nsp_build(out, sizeof(out), &p);
    assert(n == (int)sizeof(ls_hi) && out[6] == 0x00U);
    assert(dniv_nsp_parse(ls, sizeof(ls), &p) == DNIV_NSP_OK);
    assert(p.type == DNIV_NSP_LINK_SVC);
    assert(p.fcmod == 2U && p.fcval_int == 1U && p.fcval == -3);
    roundtrip(ls, sizeof(ls));
}

static void test_negative(void)
{
    const unsigned char bad_ack[] = {0x04,0x03,0x00,0x05,0x01};
    const unsigned char empty_intr[] = {
        0x30,0x03,0x00,0x05,0x01,0x01,0x00
    };
    const unsigned char long_intr[] = {
        0x30,0x03,0x00,0x05,0x01,0x01,0x00,
        0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16
    };
    const unsigned char bad_cross[] = {
        0x04,0x03,0x00,0x05,0x01,0x02,0x80,0x05,0x90
    };
    const unsigned char bad_ack_trailing[] = {
        0x04,0x03,0x00,0x05,0x01,0x05,0x80,0x00,0x00
    };
    const unsigned char ignored_bad_optional_ack[] = {
        0x04,0x03,0x00,0x05,0x01,0x05,0x80,0x07,0xc0
    };
    const unsigned char bad_ci_dst[] = {
        0x18,0x01,0x00,0x03,0x00,0x05,0x02,0x04,0x02
    };
    const unsigned char bad_ls[] = {
        0x10,0x03,0x00,0x05,0x01,0x07,0x00,0x03,0x01
    };
    const unsigned char bad_cc_trailing[] = {
        0x28,0x0b,0x00,0x03,0x00,0x05,0x02,0x04,0x02,0x00,0xaa
    };
    const unsigned char bad_di_trailing[] = {
        0x38,0x0b,0x00,0x03,0x00,0x05,0x00,0x00,0xaa
    };
    const unsigned char bad_dc_trailing[] = {
        0x48,0x0b,0x00,0x03,0x00,0x2a,0x00,0xaa
    };
    struct dniv_nsp_packet p;

    assert(dniv_nsp_parse(NULL, 0, &p) == DNIV_NSP_MALFORMED);
    assert(dniv_nsp_parse(bad_ack, sizeof(bad_ack), &p) ==
           DNIV_NSP_MALFORMED);
    assert(dniv_nsp_parse(bad_cross, sizeof(bad_cross), &p) ==
           DNIV_NSP_MALFORMED);
    assert(dniv_nsp_parse(bad_ack_trailing, sizeof(bad_ack_trailing), &p) ==
           DNIV_NSP_MALFORMED);
    assert(dniv_nsp_parse(ignored_bad_optional_ack,
                          sizeof(ignored_bad_optional_ack), &p) ==
           DNIV_NSP_OK);
    assert(p.ack1.present && !p.ack2.present);
    assert(dniv_nsp_parse(bad_ci_dst, sizeof(bad_ci_dst), &p) ==
           DNIV_NSP_MALFORMED);
    assert(dniv_nsp_parse(bad_ls, sizeof(bad_ls), &p) ==
           DNIV_NSP_MALFORMED);
    assert(dniv_nsp_parse(bad_cc_trailing, sizeof(bad_cc_trailing), &p) ==
           DNIV_NSP_MALFORMED);
    assert(dniv_nsp_parse(bad_di_trailing, sizeof(bad_di_trailing), &p) ==
           DNIV_NSP_MALFORMED);
    assert(dniv_nsp_parse(bad_dc_trailing, sizeof(bad_dc_trailing), &p) ==
           DNIV_NSP_MALFORMED);
    assert(dniv_nsp_parse(empty_intr, sizeof(empty_intr), &p) ==
           DNIV_NSP_MALFORMED);
    assert(dniv_nsp_parse(long_intr, sizeof(long_intr), &p) ==
           DNIV_NSP_MALFORMED);
}

static void test_retransmit_flow(void)
{
    assert(!dniv_nsp_retransmit_allowed(DNIV_NSP_CH_DATA, 0));
    assert(dniv_nsp_retransmit_allowed(DNIV_NSP_CH_DATA, 1));
    assert(dniv_nsp_retransmit_allowed(DNIV_NSP_CH_OTHER, 0));
    assert(dniv_nsp_retransmit_allowed(DNIV_NSP_CH_OTHER, 1));
}

static void test_ack_holdoff(void)
{
    assert(dniv_nsp_ack_holdoff_deadline(0, 0UL, 100UL, 3UL) == 103UL);
    assert(dniv_nsp_ack_holdoff_deadline(1, 103UL, 101UL, 3UL) == 103UL);
    assert(dniv_nsp_ack_holdoff_deadline(1, 103UL, 104UL, 3UL) == 103UL);
}

static void test_duplicate_ci_state(void)
{
    assert(dniv_nsp_duplicate_ci_reack_allowed(DNIV_NSP_ST_CR));
    assert(dniv_nsp_duplicate_ci_reack_allowed(DNIV_NSP_ST_CC));
    assert(!dniv_nsp_duplicate_ci_reack_allowed(DNIV_NSP_ST_CLOSED));
    assert(!dniv_nsp_duplicate_ci_reack_allowed(DNIV_NSP_ST_CI));
    assert(!dniv_nsp_duplicate_ci_reack_allowed(DNIV_NSP_ST_CD));
    assert(!dniv_nsp_duplicate_ci_reack_allowed(DNIV_NSP_ST_RUN));
    assert(!dniv_nsp_duplicate_ci_reack_allowed(DNIV_NSP_ST_DI));
}

static void test_ack_conn_state(void)
{
    assert(dniv_nsp_ack_conn_expected(DNIV_NSP_ST_CI));
    assert(!dniv_nsp_ack_conn_expected(DNIV_NSP_ST_CLOSED));
    assert(!dniv_nsp_ack_conn_expected(DNIV_NSP_ST_CD));
    assert(!dniv_nsp_ack_conn_expected(DNIV_NSP_ST_CR));
    assert(!dniv_nsp_ack_conn_expected(DNIV_NSP_ST_CC));
    assert(!dniv_nsp_ack_conn_expected(DNIV_NSP_ST_RUN));
    assert(!dniv_nsp_ack_conn_expected(DNIV_NSP_ST_DI));
}

static void test_cc_receive_state(void)
{
    assert(dniv_nsp_cc_receive_action(DNIV_NSP_ST_CI) ==
           DNIV_NSP_CC_RX_ACCEPT);
    assert(dniv_nsp_cc_receive_action(DNIV_NSP_ST_CD) ==
           DNIV_NSP_CC_RX_ACCEPT);
    assert(dniv_nsp_cc_receive_action(DNIV_NSP_ST_RUN) ==
           DNIV_NSP_CC_RX_REACK);
    assert(dniv_nsp_cc_receive_action(DNIV_NSP_ST_CLOSED) ==
           DNIV_NSP_CC_RX_INVALID);
    assert(dniv_nsp_cc_receive_action(DNIV_NSP_ST_CR) ==
           DNIV_NSP_CC_RX_INVALID);
    assert(dniv_nsp_cc_receive_action(DNIV_NSP_ST_CC) ==
           DNIV_NSP_CC_RX_INVALID);
    assert(dniv_nsp_cc_receive_action(DNIV_NSP_ST_DI) ==
           DNIV_NSP_CC_RX_INVALID);
}

static void test_sequence(void)
{
    assert(dniv_nsp_seq_norm(4096U) == 0U);
    assert(dniv_nsp_seq_next(4095U) == 0U);
    assert(dniv_nsp_seq_order(10U, 10U) == DNIV_NSP_RX_EXPECTED);
    assert(dniv_nsp_seq_order(10U, 11U) == DNIV_NSP_RX_FUTURE);
    assert(dniv_nsp_seq_order(0U, 4095U) == DNIV_NSP_RX_DUPLICATE);
    assert(dniv_nsp_seq_order(0U, 2047U) == DNIV_NSP_RX_FUTURE);
    assert(dniv_nsp_seq_order(0U, 2048U) == DNIV_NSP_RX_DUPLICATE);
    assert(dniv_nsp_seq_order(0U, 2049U) == DNIV_NSP_RX_DUPLICATE);
    assert(dniv_nsp_seq_order(4095U, 0U) == DNIV_NSP_RX_FUTURE);
    assert(dniv_nsp_seq_acked(0U, 2047U));
    assert(!dniv_nsp_seq_acked(0U, 2048U));
    assert(dniv_nsp_seq_in_window(10U, 20U, 10U));
    assert(dniv_nsp_seq_in_window(10U, 20U, 15U));
    assert(dniv_nsp_seq_in_window(10U, 20U, 20U));
    assert(!dniv_nsp_seq_in_window(10U, 20U, 21U));
    assert(dniv_nsp_seq_in_window(4094U, 2U, 0U));
    assert(!dniv_nsp_seq_in_window(4094U, 2U, 3U));
    assert(dniv_nsp_seq_in_window(4095U, 1U, 0U));
    assert(!dniv_nsp_seq_in_window(4095U, 1U, 2U));
    assert(!dniv_nsp_seq_in_window(2048U, 0U, 2048U));
    assert(DNIV_NSP_INITIAL_SEQUENCE == 1U);
    assert(DNIV_NSP_REASON_NO_RESOURCES == 1U);
    assert(DNIV_NSP_REASON_OBJECT_FAILED == 38U);
    assert(DNIV_NSP_DEFAULT_RESPONSE_SECONDS == 5U);
    assert(DNIV_NSP_CONNECT_TIMEOUT_SECONDS == 30U);
    assert(DNIV_NSP_INACTIVITY_SECONDS == 300U);
    assert(DNIV_NSP_REASON_NODE_UNREACHABLE == 39U);
    assert(DNIV_NSP_REASON_NO_LINK == 41U);
    assert(DNIV_NSP_REASON_DISCONNECT_COMPLETE == 42U);
}

int main(void)
{
    test_ack();
    test_data();
    test_control();
    test_interrupt_and_link_service();
    test_negative();
    test_retransmit_flow();
    test_ack_holdoff();
    test_duplicate_ci_state();
    test_ack_conn_state();
    test_cc_receive_state();
    test_sequence();
    return 0;
}
