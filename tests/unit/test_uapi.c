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
#include <linux/decnet_iv.h>
#include <stdio.h>

_Static_assert(sizeof(struct dniv_identity) == 16, "dniv_identity UAPI size changed");
_Static_assert(sizeof(struct dniv_stats) == 64, "dniv_stats UAPI size changed");
_Static_assert(sizeof(struct dniv_adjacency) == 32, "dniv_adjacency UAPI size changed");
_Static_assert(sizeof(struct dniv_route) == 20, "dniv_route UAPI size changed");

int main(void)
{
    __u16 first = DNIV_ADDR(31, 70);
    __u16 last = DNIV_ADDR(31, 79);

    assert(DNIV_UAPI_VERSION == 2U);
    assert(_IOC_NR(DNIV_IOC_GET_ROUTE) == 0x05U);
    assert(first == 0x7c46);
    assert(last == 0x7c4f);
    assert(DNIV_ADDR_AREA(first) == 31);
    assert(DNIV_ADDR_NODE(first) == 70);
    assert(DNIV_ADDR_AREA(last) == 31);
    assert(DNIV_ADDR_NODE(last) == 79);
    puts("UAPI address tests passed");
    return 0;
}
