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

struct nodeent {
    char *n_name;
    unsigned short n_addrtype;
    unsigned short n_length;
    unsigned char *n_addr;
    unsigned char *n_params;
    unsigned char n_reserved[16];
};

#define DNOBJ_SEARCH_ENV "DECNET_OBJPROTO"
#define DNOBJ_SEARCH_DEF "decnet"
#define DNOBJ_HINUM_ENV "DECNET_OBJHINUM"
#define DNOBJ_HINUM_DEF "error"

#define DNOBJHINUM_RESET      -128
#define DNOBJHINUM_ERROR      -1
#define DNOBJHINUM_RETURN      0
#define DNOBJHINUM_ZERO        1
#define DNOBJHINUM_ALWAYSZERO  2

struct dn_naddr *dnet_addr(const char *text);
char *dnet_ntoa(struct dn_naddr *addr);
char *dnet_htoa(struct dn_naddr *addr);
int dnet_pton(int family, const char *src, void *addr);
const char *dnet_ntop(int family, const void *addr, char *dst, size_t len);
int dnet_conn(char *node, char *object, int type,
              unsigned char *opt_out, int opt_outl,
              unsigned char *opt_in, int *opt_inl);
struct dn_naddr *getnodeadd(void);
struct nodeent *getnodebyaddr(const char *addr, int len, int type);
struct nodeent *getnodebyname(const char *name);
char *getexecdev(void);
void setnodeent(int stayopen);
void *dnet_getnode(void);
char *dnet_nextnode(void *handle);
void dnet_endnode(void *handle);

int dnet_setobjhinum_handling(int handling, int min);
int dnet_checkobjectnumber(int number);
int getobjectbyname(const char *name);
int getobjectbynumber(int number, char *name, size_t name_len);
int dnet_recv(int fd, void *buf, int len, unsigned int flags);
int dnet_eof(int fd);
int getnodename(char *name, size_t len);

#define DNOBJECT_FAL    (getobjectbyname("FAL"))
#define DNOBJECT_NICE   (getobjectbyname("NICE"))
#define DNOBJECT_DTERM  (getobjectbyname("DTERM"))
#define DNOBJECT_MIRROR (getobjectbyname("MIRROR"))
#define DNOBJECT_EVR    (getobjectbyname("EVR"))
#define DNOBJECT_MAIL11 (getobjectbyname("MAIL11"))
#define DNOBJECT_PHONE  (getobjectbyname("PHONE"))
#define DNOBJECT_CTERM  (getobjectbyname("CTERM"))
#define DNOBJECT_DTR    (getobjectbyname("DTR"))

#ifdef __cplusplus
}
#endif

#endif
