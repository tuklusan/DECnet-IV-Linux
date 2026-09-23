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

#ifndef _UAPI_LINUX_DN_H
#define _UAPI_LINUX_DN_H

#include <linux/types.h>

#define DNPROTO_NSP  2
#define DNPROTO_ROU  3
#define DNPROTO_NML  4
#define DNPROTO_EVL  5
#define DNPROTO_EVR  6
#define DNPROTO_NSPT 7

#define DN_ADDL       2
#define DN_MAXADDL    2
#define DN_MAXOPTL   16
#define DN_MAXOBJL   16
#define DN_MAXACCL   40
#define DN_MAXALIASL 128
#define DN_MAXNODEL  256
#define DNBUFSIZE    65023

#define SO_CONDATA   1
#define SO_CONACCESS 2
#define SO_PROXYUSR  3
#define SO_LINKINFO  7

#define DSO_CONDATA    1
#define DSO_CONACCESS  2
#define DSO_ACCEPTMODE 4
#define DSO_CONACCEPT  5
#define DSO_CONREJECT  6
#define DSO_LINKINFO   7
#define DSO_STREAM     8
#define DSO_SEQPACKET  9
#define DSO_DISDATA   10
#define DSO_MAXWINDOW 11
#define DSO_NODELAY   12
#define DSO_CORK      13
#define DSO_SERVICES  14
#define DSO_INFO      15
#define DSO_MAX       15

#define LL_INACTIVE      0
#define LL_CONNECTING    1
#define LL_RUNNING       2
#define LL_DISCONNECTING 3

#define ACC_IMMED 0
#define ACC_DEFER 1

#define SDF_WILD     1
#define SDF_PROXY    2
#define SDF_UICPROXY 4

struct dn_naddr {
    __le16 a_len;
    __u8 a_addr[DN_MAXADDL];
};

struct sockaddr_dn {
    __u16 sdn_family;
    __u8 sdn_flags;
    __u8 sdn_objnum;
    __le16 sdn_objnamel;
    __u8 sdn_objname[DN_MAXOBJL];
    struct dn_naddr sdn_add;
};

#define sdn_nodeaddrl sdn_add.a_len
#define sdn_nodeaddr  sdn_add.a_addr

struct optdata_dn {
    __le16 opt_status;
    __le16 opt_optl;
    __u8 opt_data[DN_MAXOPTL];
};

#define opt_sts opt_status

struct accessdata_dn {
    __u8 acc_accl;
    __u8 acc_acc[DN_MAXACCL];
    __u8 acc_passl;
    __u8 acc_pass[DN_MAXACCL];
    __u8 acc_userl;
    __u8 acc_user[DN_MAXACCL];
};

struct linkinfo_dn {
    __u16 idn_segsize;
    __u8 idn_linkstate;
};

#endif
