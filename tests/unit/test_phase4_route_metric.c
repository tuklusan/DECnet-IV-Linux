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
#include <decnet_iv_route_metric.h>
#include <stdio.h>

int main(void)
{
    struct dniv_route_metric metric;

    assert(dniv_route_metric_add(6, 2, 5, &metric) == 0);
    assert(metric.cost == 11);
    assert(metric.hops == 3);

    assert(dniv_route_metric_add(0, 0, 1, &metric) == 0);
    assert(metric.cost == 1);
    assert(metric.hops == 1);

    assert(dniv_route_metric_add(DNIV_ROUTE_MAX_COST, 29, 0, &metric) < 0);
    assert(dniv_route_metric_add(DNIV_ROUTE_INFINITY_COST, 1, 1, &metric) < 0);
    assert(dniv_route_metric_add(1, DNIV_ROUTE_INFINITY_HOPS, 1, &metric) < 0);
    assert(dniv_route_metric_add(DNIV_ROUTE_MAX_COST, 1, 1, &metric) < 0);
    assert(dniv_route_metric_add(1, DNIV_ROUTE_MAX_HOPS, 1, &metric) < 0);
    assert(dniv_route_metric_add(1, 1, 1, NULL) < 0);

    assert(dniv_route_metric_valid(DNIV_ROUTE_MAX_COST, DNIV_ROUTE_MAX_HOPS));
    assert(!dniv_route_metric_valid(DNIV_ROUTE_INFINITY_COST, 1));
    assert(!dniv_route_metric_valid(1, DNIV_ROUTE_INFINITY_HOPS));

    assert(dniv_route_candidate_better(10, 100, 2, 11, 200, 1));
    assert(!dniv_route_candidate_better(11, 200, 1, 10, 100, 2));
    assert(dniv_route_candidate_better(10, 200, 2, 10, 100, 1));
    assert(!dniv_route_candidate_better(10, 100, 1, 10, 200, 2));
    assert(dniv_route_candidate_better(10, 100, 1, 10, 100, 2));

    assert(dniv_route_advertisement_is_self_destination(
        1U, 71U, (__u16)((31U << 10) | 71U)));
    assert(!dniv_route_advertisement_is_self_destination(
        1U, 70U, (__u16)((31U << 10) | 71U)));
    assert(dniv_route_advertisement_is_self_destination(
        2U, 31U, (__u16)((31U << 10) | 71U)));
    assert(!dniv_route_advertisement_is_self_destination(
        2U, 32U, (__u16)((31U << 10) | 71U)));
    assert(!dniv_route_advertisement_is_self_destination(
        3U, 71U, (__u16)((31U << 10) | 71U)));

    puts("phase4 route metric tests passed");
    return 0;
}
