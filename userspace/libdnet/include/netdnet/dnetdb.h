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

#ifndef DNIV_NETDNET_DNETDB_H
#define DNIV_NETDNET_DNETDB_H

#include <stddef.h>
#include <netdnet/dn.h>

#ifdef __cplusplus
extern "C" {
#endif

#define DNET_ADDRSTRLEN 8

struct dn_naddr *dnet_addr(const char *text);
char *dnet_ntoa(struct dn_naddr *addr);
char *dnet_htoa(struct dn_naddr *addr);
int dnet_pton(int family, const char *src, void *addr);
const char *dnet_ntop(int family, const void *addr, char *dst, size_t len);
int dnet_conn(char *node, char *object, int type,
              unsigned char *opt_out, int opt_outl,
              unsigned char *opt_in, int *opt_inl);

#ifdef __cplusplus
}
#endif

#endif
