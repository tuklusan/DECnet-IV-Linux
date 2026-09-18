// ============================================================================
// Copyright (c) 2026 Supratim Sanyal of SANYALnet Labs.
// Proprietary rights reserved except as expressly licensed herein.
//
// DECnet-IV-Linux
// This file is governed by the SANYALnet Labs Non-Commercial License in the
// root LICENSE file. Non-Commercial use is permitted; Commercial Use and use
// for AI/ML model training are prohibited unless separately authorized.
// ============================================================================

#ifndef _DECNET_IV_NSP_STATE_H
#define _DECNET_IV_NSP_STATE_H

#include <linux/types.h>

#define DNIV_NSP_SEQ_MODULUS 4096U
#define DNIV_NSP_SEQ_HALF 2048U
#define DNIV_NSP_DEFAULT_RESPONSE_SECONDS 5U
#define DNIV_NSP_CONNECT_TIMEOUT_SECONDS 30U
#define DNIV_NSP_INACTIVITY_SECONDS 300U

enum dniv_nsp_rx_order {
    DNIV_NSP_RX_EXPECTED = 0,
    DNIV_NSP_RX_FUTURE = 1,
    DNIV_NSP_RX_DUPLICATE = 2,
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

#endif
