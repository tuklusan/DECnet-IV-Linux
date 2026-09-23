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

#ifndef _DECNET_IV_ETHERNET_H
#define _DECNET_IV_ETHERNET_H

#include <linux/types.h>
#include <linux/decnet_iv.h>

int dniv_eth_init(__u16 address, __u8 node_type, __u8 priority,
                  __u16 hello_interval, __u16 ethernet_cost);
void dniv_eth_exit(void);
int dniv_eth_set_address(__u16 address);
__u16 dniv_eth_get_address(void);
void dniv_eth_get_stats(struct dniv_stats *stats);
int dniv_eth_get_traffic_stats(int ifindex, struct dniv_traffic_stats *stats);
void dniv_eth_reset_stats(void);
int dniv_eth_get_adjacency(__u32 index, struct dniv_adjacency *adjacency);
int dniv_eth_send_payload(__u16 destination, const __u8 *payload,
                          __u16 payload_len);

#endif /* _DECNET_IV_ETHERNET_H */
