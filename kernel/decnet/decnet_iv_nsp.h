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

#ifndef _DECNET_IV_NSP_H
#define _DECNET_IV_NSP_H

#include <linux/types.h>
#include <decnet_iv_nsp_state.h>

#define DNIV_NSP_MAX_CONNECTIONS 256U
#define DNIV_NSP_MAX_RETRANSMIT 64U

struct dniv_nsp_conn_snapshot {
    __u16 local_link;
    __u16 remote_link;
    __u16 remote_node;
    __u16 tx_next;
    __u16 rx_next;
    __u16 retransmit_count;
    enum dniv_nsp_conn_state state;
};

int dniv_nsp_init(void);
void dniv_nsp_exit(void);
void dniv_nsp_reset(void);
int dniv_nsp_conn_alloc(__u16 remote_node, __u16 remote_link,
                        enum dniv_nsp_conn_state initial_state,
                        __u16 *local_link);
int dniv_nsp_conn_release(__u16 local_link);
int dniv_nsp_conn_transition(__u16 local_link,
                             enum dniv_nsp_conn_state new_state);
int dniv_nsp_conn_set_remote(__u16 local_link, __u16 remote_node,
                             __u16 remote_link);
int dniv_nsp_conn_snapshot(__u16 local_link,
                           struct dniv_nsp_conn_snapshot *snapshot);
int dniv_nsp_retransmit_queue(__u16 local_link, __u16 sequence,
                              const __u8 *wire, __u16 wire_len,
                              unsigned long deadline);
unsigned int dniv_nsp_retransmit_ack(__u16 local_link, __u16 ack);
int dniv_nsp_retransmit_due(__u16 local_link, unsigned long now,
                            __u16 *sequence, __u8 *wire, __u16 capacity,
                            __u16 *wire_len);

#endif
