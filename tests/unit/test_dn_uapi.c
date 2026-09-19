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
#include <stddef.h>

#include <linux/dn.h>

int main(void)
{
    assert(DNPROTO_NSP == 2);
    assert(DNBUFSIZE == 65023);
    assert(DN_MAXOBJL == 16);
    assert(DN_MAXACCL == 40);
    assert(DSO_CONDATA == 1);
    assert(DSO_CONREJECT == 6);
    assert(DSO_LINKINFO == 7);
    assert(DSO_MAXWINDOW == 11);
    assert(DSO_INFO == 15);
    assert(sizeof(struct dn_naddr) == 4U);
    assert(sizeof(struct sockaddr_dn) == 26U);
    assert(offsetof(struct sockaddr_dn, sdn_add) == 22U);
    assert(sizeof(struct optdata_dn) == 20U);
    assert(sizeof(struct accessdata_dn) == 123U);
    return 0;
}
