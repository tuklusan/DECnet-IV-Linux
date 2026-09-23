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
#include <decnet_iv_nsp_wire.h>

#define DNIV_NSP_MAX_CONNECTIONS 256U
#define DNIV_NSP_MAX_RETRANSMIT 64U
#define DNIV_NSP_MAX_RETRANSMITS 5U
#define DNIV_NSP_MAX_WIRE 1477U
#define DNIV_NSP_MSS 563U
#define DNIV_NSP_MAX_RX_QUEUED 32U
#define DNIV_NSP_MAX_WINDOW 20U
#define DNIV_NSP_MAX_INTERRUPT 16U
#define DNIV_NSP_ACK_HOLDOFF_SECONDS 3U
#define DNIV_NSP_MAX_MESSAGE 65023U
#define DNIV_NSP_MAX_CI_PAYLOAD (DNIV_NSP_MAX_WIRE - 9U)

struct dniv_nsp_rx_meta {
    enum dniv_nsp_channel channel;
    enum dniv_nsp_type type;
    __u16 sequence;
    __u16 payload_len;
    __u8 bom;
    __u8 eom;
};

typedef void (*dniv_nsp_notify_fn)(__u16 local_link);

struct dniv_nsp_ci_snapshot {
    __u16 local_link;
    __u16 remote_link;
    __u16 remote_node;
    __u16 payload_len;
};

struct dniv_nsp_conn_snapshot {
    __u16 local_link;
    __u16 remote_link;
    __u16 remote_node;
    __u16 data_tx_next;
    __u16 data_rx_next;
    __u16 other_tx_next;
    __u16 other_rx_next;
    __u16 retransmit_count;
    __u16 data_retransmit_count;
    __u16 other_retransmit_count;
    __u16 rx_queued;
    __u16 interrupt_credit;
    __u16 segment_size;
    __u16 disconnect_reason;
    __u8 data_xon;
    __u8 shutdown_pending;
    unsigned long connect_deadline;
    unsigned long inactivity_deadline;
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
int dniv_nsp_conn_get_index(__u32 index,
                            struct dniv_nsp_conn_snapshot *snapshot);
int dniv_nsp_ci_snapshot(__u16 local_link,
                         struct dniv_nsp_ci_snapshot *snapshot,
                         __u8 *payload, __u16 capacity);
int dniv_nsp_accept_data_snapshot(__u16 local_link, __u8 *payload,
                                  __u16 capacity, __u16 *payload_len);
int dniv_nsp_disconnect_data_snapshot(__u16 local_link, __u16 *reason,
                                      __u8 *payload, __u16 capacity,
                                      __u16 *payload_len);
int dniv_nsp_rx_ready(__u16 local_link, bool *normal, bool *interrupt);
void dniv_nsp_set_notify(dniv_nsp_notify_fn notify);
int dniv_nsp_retransmit_queue(__u16 local_link,
                              enum dniv_nsp_channel channel,
                              __u16 sequence, const __u8 *wire,
                              __u16 wire_len, unsigned long deadline);
unsigned int dniv_nsp_retransmit_ack(__u16 local_link,
                                     enum dniv_nsp_channel channel,
                                     __u16 ack);
int dniv_nsp_retransmit_due(__u16 local_link,
                            enum dniv_nsp_channel channel,
                            unsigned long now, __u16 *sequence,
                            __u8 *wire, __u16 capacity, __u16 *wire_len);
int dniv_nsp_receive(__u16 remote_node, const __u8 *wire, __u16 wire_len);
int dniv_nsp_transmit(__u16 remote_node, const __u8 *wire, __u16 wire_len);
int dniv_nsp_connect(__u16 remote_node, const __u8 *payload,
                     __u16 payload_len, __u16 *local_link);
int dniv_nsp_accept(__u16 local_link, const __u8 *payload, __u16 payload_len);
int dniv_nsp_reject(__u16 local_link, __u16 reason,
                    const __u8 *payload, __u16 payload_len);
int dniv_nsp_disconnect(__u16 local_link, __u16 reason,
                        const __u8 *payload, __u16 payload_len);
int dniv_nsp_send_data(__u16 local_link, const __u8 *payload,
                       __u16 payload_len, __u8 bom, __u8 eom);
int dniv_nsp_send_interrupt(__u16 local_link, const __u8 *payload,
                            __u16 payload_len);
int dniv_nsp_recv(__u16 local_link, struct dniv_nsp_rx_meta *meta,
                  __u8 *payload, __u16 capacity);
int dniv_nsp_recv_interrupt(__u16 local_link, __u8 *payload, __u16 capacity,
                            __u16 *payload_len);
int dniv_nsp_recv_message(__u16 local_link, __u8 *payload, __u32 capacity,
                          __u32 *payload_len);

#endif
