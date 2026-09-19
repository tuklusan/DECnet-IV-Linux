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

#ifndef _DECNET_IV_ROUTE_METRIC_H
#define _DECNET_IV_ROUTE_METRIC_H

#include <linux/types.h>

#define DNIV_ROUTE_MAX_COST 1022U
#define DNIV_ROUTE_INFINITY_COST 1023U
#define DNIV_ROUTE_MAX_HOPS 30U
#define DNIV_ROUTE_INFINITY_HOPS 31U

struct dniv_route_metric {
    __u16 cost;
    __u8 hops;
};

static inline int dniv_route_metric_add(__u16 advertised_cost,
                                        __u8 advertised_hops,
                                        __u16 circuit_cost,
                                        struct dniv_route_metric *metric)
{
    __u32 cost;
    __u32 hops;

    if (!metric || circuit_cost == 0U ||
        advertised_cost >= DNIV_ROUTE_INFINITY_COST ||
        advertised_hops >= DNIV_ROUTE_INFINITY_HOPS)
        return -1;

    cost = (__u32)advertised_cost + circuit_cost;
    hops = (__u32)advertised_hops + 1U;
    if (cost > DNIV_ROUTE_MAX_COST || hops > DNIV_ROUTE_MAX_HOPS)
        return -1;

    metric->cost = (__u16)cost;
    metric->hops = (__u8)hops;
    return 0;
}

static inline int dniv_route_metric_valid(__u16 cost, __u8 hops)
{
    return cost <= DNIV_ROUTE_MAX_COST && hops <= DNIV_ROUTE_MAX_HOPS;
}

/*
 * A broadcast-router adjacency supplies the direct route to that router.
 * The peer's own vector slot is learned state and must not replace or
 * withdraw that separately maintained direct adjacency route.
 */
static inline int dniv_route_advertisement_is_self_destination(
    __u8 level, __u16 destination, __u16 source)
{
    if (level == 1U)
        return destination == (source & 0x03ffU);
    if (level == 2U)
        return destination == ((source >> 10) & 0x003fU);
    return 0;
}

/*
 * DNA routing minimizes path cost.  For equal costs, the DEC routing
 * decision algorithm selects the adjacency with the higher node address.
 * ifindex is only a final deterministic tie-break for duplicate next hops.
 */
static inline int dniv_route_candidate_better(
    __u16 cost, __u16 next_hop, __s32 ifindex,
    __u16 best_cost, __u16 best_next_hop, __s32 best_ifindex)
{
    if (cost != best_cost)
        return cost < best_cost;
    if (next_hop != best_next_hop)
        return next_hop > best_next_hop;
    return ifindex < best_ifindex;
}

#endif /* _DECNET_IV_ROUTE_METRIC_H */
