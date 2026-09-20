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

#ifndef _DECNET_IV_NSP_STATE_H
#define _DECNET_IV_NSP_STATE_H

#include <linux/types.h>

#define DNIV_NSP_SEQ_MODULUS 4096U
#define DNIV_NSP_SEQ_HALF 2048U
#define DNIV_NSP_DEFAULT_RESPONSE_SECONDS 5U
#define DNIV_NSP_CONNECT_TIMEOUT_SECONDS 30U
#define DNIV_NSP_INACTIVITY_SECONDS 300U
#define DNIV_NSP_INITIAL_SEQUENCE 1U
#define DNIV_NSP_REASON_NODE_UNREACHABLE 39U

enum dniv_nsp_channel {
    DNIV_NSP_CH_DATA = 0,
    DNIV_NSP_CH_OTHER = 1,
    DNIV_NSP_CH_COUNT = 2,
};

static inline int
dniv_nsp_retransmit_allowed(enum dniv_nsp_channel channel, int data_xon)
{
    return channel != DNIV_NSP_CH_DATA || data_xon;
}

enum dniv_nsp_rx_order {
    DNIV_NSP_RX_EXPECTED = 0,
    DNIV_NSP_RX_FUTURE = 1,
    DNIV_NSP_RX_DUPLICATE = 2,
};

enum dniv_nsp_conn_state {
    DNIV_NSP_ST_CLOSED = 0,
    DNIV_NSP_ST_CI,
    DNIV_NSP_ST_CD,
    DNIV_NSP_ST_CR,
    DNIV_NSP_ST_CC,
    DNIV_NSP_ST_RUN,
    DNIV_NSP_ST_DI,
};

static inline __u16 dniv_nsp_seq_norm(__u32 v)
{
    return (__u16)(v & 0x0fffU);
}

static inline __u16 dniv_nsp_seq_next(__u16 v)
{
    return dniv_nsp_seq_norm((__u32)v + 1U);
}

static inline enum dniv_nsp_rx_order
dniv_nsp_seq_order(__u16 expected, __u16 received)
{
    __u16 delta = dniv_nsp_seq_norm((__u32)received - expected);

    if (delta == 0U)
        return DNIV_NSP_RX_EXPECTED;
    if (delta < DNIV_NSP_SEQ_HALF)
        return DNIV_NSP_RX_FUTURE;
    return DNIV_NSP_RX_DUPLICATE;
}

static inline int dniv_nsp_seq_acked(__u16 sequence, __u16 ack)
{
    return dniv_nsp_seq_norm((__u32)ack - sequence) < DNIV_NSP_SEQ_HALF;
}

static inline int dniv_nsp_seq_in_window(__u16 first, __u16 last, __u16 value)
{
    __u16 span = dniv_nsp_seq_norm((__u32)last - first);
    __u16 offset = dniv_nsp_seq_norm((__u32)value - first);

    return span < DNIV_NSP_SEQ_HALF && offset <= span;
}

static inline int
dniv_nsp_state_transition_valid(enum dniv_nsp_conn_state from,
                                enum dniv_nsp_conn_state to)
{
    if (from == to)
        return 1;

    switch (from) {
    case DNIV_NSP_ST_CLOSED:
        return to == DNIV_NSP_ST_CI || to == DNIV_NSP_ST_CR;
    case DNIV_NSP_ST_CI:
        return to == DNIV_NSP_ST_CD || to == DNIV_NSP_ST_RUN ||
               to == DNIV_NSP_ST_DI || to == DNIV_NSP_ST_CLOSED;
    case DNIV_NSP_ST_CD:
        return to == DNIV_NSP_ST_RUN || to == DNIV_NSP_ST_DI ||
               to == DNIV_NSP_ST_CLOSED;
    case DNIV_NSP_ST_CR:
        return to == DNIV_NSP_ST_CC || to == DNIV_NSP_ST_DI ||
               to == DNIV_NSP_ST_CLOSED;
    case DNIV_NSP_ST_CC:
        return to == DNIV_NSP_ST_RUN || to == DNIV_NSP_ST_DI ||
               to == DNIV_NSP_ST_CLOSED;
    case DNIV_NSP_ST_RUN:
        return to == DNIV_NSP_ST_DI || to == DNIV_NSP_ST_CLOSED;
    case DNIV_NSP_ST_DI:
        return to == DNIV_NSP_ST_CLOSED;
    default:
        return 0;
    }
}

#endif
