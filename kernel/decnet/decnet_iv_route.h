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

#ifndef _DECNET_IV_ROUTE_H
#define _DECNET_IV_ROUTE_H

#include <linux/types.h>

struct dniv_route_result {
    __u16 destination;
    __u16 next_hop;
    __u16 cost;
    __s32 ifindex;
    __u8 level;
    __u8 hops;
};

int dniv_route_init(void);
void dniv_route_exit(void);
void dniv_route_reset(void);
int dniv_route_update(__u8 level, __u16 destination, __u16 next_hop,
                      __s32 ifindex, __u16 cost, __u8 hops,
                      unsigned long expires);
void dniv_route_withdraw(__u8 level, __u16 destination, __u16 next_hop,
                         __s32 ifindex);
void dniv_route_refresh_adjacency(__u16 next_hop, __s32 ifindex,
                                  unsigned long expires);
void dniv_route_withdraw_adjacency(__u16 next_hop, __s32 ifindex);
int dniv_route_lookup(__u8 level, __u16 destination,
                      struct dniv_route_result *result);
int dniv_route_get_index(__u32 index, struct dniv_route_result *result);
unsigned int dniv_route_age(unsigned long now);
__u64 dniv_route_get_generation(void);
int dniv_route_snapshot(__u8 level, __u16 local_destination,
                        __u16 *entries, __u16 count);
bool dniv_route_area_attached(__u16 local_area);

#endif /* _DECNET_IV_ROUTE_H */
