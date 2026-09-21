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

#ifndef _DECNET_IV_NSP_WIRE_H
#define _DECNET_IV_NSP_WIRE_H

#include <linux/types.h>

#define DNIV_NSP_OK 0
#define DNIV_NSP_MALFORMED (-1)
#define DNIV_NSP_SEQ_MASK 0x0fffU
#define DNIV_NSP_ACK_PRESENT 0x8000U
#define DNIV_NSP_ACK_QUAL_SHIFT 12U
#define DNIV_NSP_MAX_CTL_DATA 16U

#define DNIV_NSP_F_ACK_DATA  0x04U
#define DNIV_NSP_F_LINK_SVC  0x10U
#define DNIV_NSP_F_ACK_OTHER 0x14U
#define DNIV_NSP_F_CI        0x18U
#define DNIV_NSP_F_ACK_CONN  0x24U
#define DNIV_NSP_F_CC        0x28U
#define DNIV_NSP_F_INT       0x30U
#define DNIV_NSP_F_DI        0x38U
#define DNIV_NSP_F_DC        0x48U
#define DNIV_NSP_F_RCI       0x68U

enum dniv_nsp_type {
    DNIV_NSP_DATA = 1,
    DNIV_NSP_ACK_DATA,
    DNIV_NSP_ACK_OTHER,
    DNIV_NSP_ACK_CONN,
    DNIV_NSP_INT,
    DNIV_NSP_LINK_SVC,
    DNIV_NSP_CI,
    DNIV_NSP_RCI,
    DNIV_NSP_CC,
    DNIV_NSP_DI,
    DNIV_NSP_DC,
};

enum dniv_nsp_ack_qual {
    DNIV_NSP_ACK = 0,
    DNIV_NSP_NAK = 1,
    DNIV_NSP_XACK = 2,
    DNIV_NSP_XNAK = 3,
};

struct dniv_nsp_ack {
    __u16 num;
    __u8 qual;
    __u8 present;
};

struct dniv_nsp_packet {
    enum dniv_nsp_type type;
    __u8 flags;
    __u16 dst;
    __u16 src;
    struct dniv_nsp_ack ack1;
    struct dniv_nsp_ack ack2;
    __u16 segnum;
    __u8 dly;
    __u8 bom;
    __u8 eom;
    __u8 fcopt;
    __u8 info;
    __u16 segsize;
    __u8 fcmod;
    __u8 fcval_int;
    __s8 fcval;
    __u16 reason;
    const __u8 *payload;
    __u32 payload_len;
};

static inline __u16 dniv_nsp_get_le16(const __u8 *p)
{
    return (__u16)((__u16)p[0] | ((__u16)p[1] << 8));
}

static inline void dniv_nsp_put_le16(__u8 *p, __u16 v)
{
    p[0] = (__u8)(v & 0xffU);
    p[1] = (__u8)(v >> 8);
}

static inline void dniv_nsp_zero(void *p, __u32 n)
{
    __u8 *b = p;
    __u32 i;
    for (i = 0; i < n; i++)
        b[i] = 0;
}

static inline int dniv_nsp_ack_cross(const struct dniv_nsp_ack *ack)
{
    return ack && ack->present && ack->qual >= DNIV_NSP_XACK;
}

static inline __u16 dniv_nsp_ack_word(__u16 num, __u8 qual)
{
    return (__u16)(DNIV_NSP_ACK_PRESENT |
                   ((__u16)(qual & 3U) << DNIV_NSP_ACK_QUAL_SHIFT) |
                   (num & DNIV_NSP_SEQ_MASK));
}

static inline void dniv_nsp_decode_ack(const __u8 *buf, __u32 len,
                                       __u32 *off, struct dniv_nsp_ack *ack)
{
    __u16 v;
    __u8 qual;

    ack->present = 0U;
    ack->num = 0U;
    ack->qual = 0U;
    if (*off + 2U > len)
        return;
    v = dniv_nsp_get_le16(buf + *off);
    if (!(v & DNIV_NSP_ACK_PRESENT))
        return;
    *off += 2U;
    qual = (__u8)((v >> DNIV_NSP_ACK_QUAL_SHIFT) & 7U);
    if (qual > 3U)
        return;
    ack->present = 1U;
    ack->qual = qual;
    ack->num = (__u16)(v & DNIV_NSP_SEQ_MASK);
}

static inline int dniv_nsp_parse(const __u8 *buf, __u32 len,
                                 struct dniv_nsp_packet *pkt)
{
    __u32 off = 1U;
    __u16 v;

    if (!buf || !pkt || len < 1U)
        return DNIV_NSP_MALFORMED;
    dniv_nsp_zero(pkt, sizeof(*pkt));
    pkt->flags = buf[0];
    if (buf[0] & 0x83U)
        return DNIV_NSP_MALFORMED;

    if ((buf[0] & 0x9fU) == 0U) {
        pkt->type = DNIV_NSP_DATA;
        pkt->bom = (__u8)((buf[0] >> 5) & 1U);
        pkt->eom = (__u8)((buf[0] >> 6) & 1U);
    } else {
        switch (buf[0]) {
        case DNIV_NSP_F_ACK_DATA: pkt->type = DNIV_NSP_ACK_DATA; break;
        case DNIV_NSP_F_ACK_OTHER: pkt->type = DNIV_NSP_ACK_OTHER; break;
        case DNIV_NSP_F_ACK_CONN: pkt->type = DNIV_NSP_ACK_CONN; break;
        case DNIV_NSP_F_INT: pkt->type = DNIV_NSP_INT; break;
        case DNIV_NSP_F_LINK_SVC: pkt->type = DNIV_NSP_LINK_SVC; break;
        case DNIV_NSP_F_CI: pkt->type = DNIV_NSP_CI; break;
        case DNIV_NSP_F_RCI: pkt->type = DNIV_NSP_RCI; break;
        case DNIV_NSP_F_CC: pkt->type = DNIV_NSP_CC; break;
        case DNIV_NSP_F_DI: pkt->type = DNIV_NSP_DI; break;
        case DNIV_NSP_F_DC: pkt->type = DNIV_NSP_DC; break;
        default: return DNIV_NSP_MALFORMED;
        }
    }

    if (pkt->type == DNIV_NSP_ACK_CONN) {
        if (len < 3U)
            return DNIV_NSP_MALFORMED;
        pkt->dst = dniv_nsp_get_le16(buf + 1U);
        return DNIV_NSP_OK;
    }

    if (len < 5U)
        return DNIV_NSP_MALFORMED;
    pkt->dst = dniv_nsp_get_le16(buf + 1U);
    pkt->src = dniv_nsp_get_le16(buf + 3U);
    off = 5U;

    if (pkt->type == DNIV_NSP_CI || pkt->type == DNIV_NSP_RCI ||
        pkt->type == DNIV_NSP_CC) {
        __u8 svc;
        if (len < 9U || (pkt->type != DNIV_NSP_CC && pkt->dst != 0U))
            return DNIV_NSP_MALFORMED;
        svc = buf[5];
        if ((svc & 0xf3U) != 1U)
            return DNIV_NSP_MALFORMED;
        pkt->fcopt = (__u8)((svc >> 2) & 3U);
        pkt->info = buf[6];
        pkt->segsize = dniv_nsp_get_le16(buf + 7U);
        off = 9U;
        if (pkt->type == DNIV_NSP_CC) {
            __u8 n;
            if (off >= len)
                return DNIV_NSP_MALFORMED;
            n = buf[off++];
            if (n > DNIV_NSP_MAX_CTL_DATA || off + n != len)
                return DNIV_NSP_MALFORMED;
            pkt->payload = buf + off;
            pkt->payload_len = n;
        } else {
            pkt->payload = buf + off;
            pkt->payload_len = len - off;
        }
        return DNIV_NSP_OK;
    }

    if (pkt->type == DNIV_NSP_DI) {
        __u8 n;
        if (len < 8U)
            return DNIV_NSP_MALFORMED;
        pkt->reason = dniv_nsp_get_le16(buf + 5U);
        off = 7U;
        n = buf[off++];
        if (n > DNIV_NSP_MAX_CTL_DATA || off + n != len)
            return DNIV_NSP_MALFORMED;
        pkt->payload = buf + off;
        pkt->payload_len = n;
        return DNIV_NSP_OK;
    }
    if (pkt->type == DNIV_NSP_DC) {
        if (len != 7U)
            return DNIV_NSP_MALFORMED;
        pkt->reason = dniv_nsp_get_le16(buf + 5U);
        return DNIV_NSP_OK;
    }

    dniv_nsp_decode_ack(buf, len, &off, &pkt->ack1);
    dniv_nsp_decode_ack(buf, len, &off, &pkt->ack2);
    if (pkt->ack1.present && pkt->ack2.present &&
        dniv_nsp_ack_cross(&pkt->ack1) == dniv_nsp_ack_cross(&pkt->ack2))
        return DNIV_NSP_MALFORMED;

    if (pkt->type == DNIV_NSP_ACK_DATA || pkt->type == DNIV_NSP_ACK_OTHER) {
        if (!pkt->ack1.present || off != len)
            return DNIV_NSP_MALFORMED;
        return DNIV_NSP_OK;
    }

    if (off + 2U > len)
        return DNIV_NSP_MALFORMED;
    v = dniv_nsp_get_le16(buf + off);
    pkt->segnum = (__u16)(v & DNIV_NSP_SEQ_MASK);
    pkt->dly = pkt->type == DNIV_NSP_DATA ?
               (__u8)((v >> 12) & 1U) : 0U;
    off += 2U;

    if (pkt->type == DNIV_NSP_LINK_SVC) {
        __u8 ls;
        if (off + 2U > len)
            return DNIV_NSP_MALFORMED;
        ls = buf[off++];
        pkt->fcmod = (__u8)(ls & 3U);
        pkt->fcval_int = (__u8)((ls >> 2) & 3U);
        pkt->fcval = (__s8)buf[off++];
        if (pkt->fcmod == 3U || pkt->fcval_int > 1U)
            return DNIV_NSP_MALFORMED;
        return DNIV_NSP_OK;
    }

    pkt->payload = buf + off;
    pkt->payload_len = len - off;
    if (pkt->type == DNIV_NSP_INT &&
        (!pkt->payload_len || pkt->payload_len > DNIV_NSP_MAX_CTL_DATA))
        return DNIV_NSP_MALFORMED;
    return DNIV_NSP_OK;
}

static inline int dniv_nsp_emit_ack(__u8 *buf, __u32 cap, __u32 *off,
                                    const struct dniv_nsp_ack *ack)
{
    if (!ack || !ack->present)
        return 0;
    if (ack->qual > 3U || *off + 2U > cap)
        return -1;
    dniv_nsp_put_le16(buf + *off, dniv_nsp_ack_word(ack->num, ack->qual));
    *off += 2U;
    return 0;
}

static inline int dniv_nsp_build(__u8 *buf, __u32 cap,
                                 const struct dniv_nsp_packet *pkt)
{
    __u32 off = 0U;
    __u8 flag;

    if (!buf || !pkt || cap == 0U)
        return -1;
    switch (pkt->type) {
    case DNIV_NSP_DATA:
        flag = (__u8)((pkt->bom ? 0x20U : 0U) | (pkt->eom ? 0x40U : 0U));
        break;
    case DNIV_NSP_ACK_DATA: flag = DNIV_NSP_F_ACK_DATA; break;
    case DNIV_NSP_ACK_OTHER: flag = DNIV_NSP_F_ACK_OTHER; break;
    case DNIV_NSP_ACK_CONN: flag = DNIV_NSP_F_ACK_CONN; break;
    case DNIV_NSP_INT: flag = DNIV_NSP_F_INT; break;
    case DNIV_NSP_LINK_SVC: flag = DNIV_NSP_F_LINK_SVC; break;
    case DNIV_NSP_CI: flag = DNIV_NSP_F_CI; break;
    case DNIV_NSP_RCI: flag = DNIV_NSP_F_RCI; break;
    case DNIV_NSP_CC: flag = DNIV_NSP_F_CC; break;
    case DNIV_NSP_DI: flag = DNIV_NSP_F_DI; break;
    case DNIV_NSP_DC: flag = DNIV_NSP_F_DC; break;
    default: return -1;
    }
    buf[off++] = flag;
    if (pkt->type == DNIV_NSP_ACK_CONN) {
        if (cap < 3U)
            return -1;
        dniv_nsp_put_le16(buf + off, pkt->dst);
        return 3;
    }
    if (cap < 5U)
        return -1;
    dniv_nsp_put_le16(buf + off, pkt->dst); off += 2U;
    dniv_nsp_put_le16(buf + off, pkt->src); off += 2U;

    if (pkt->type == DNIV_NSP_CI || pkt->type == DNIV_NSP_RCI ||
        pkt->type == DNIV_NSP_CC) {
        if (pkt->fcopt > 3U || off + 4U > cap)
            return -1;
        buf[off++] = (__u8)(1U | (pkt->fcopt << 2));
        buf[off++] = pkt->info;
        dniv_nsp_put_le16(buf + off, pkt->segsize); off += 2U;
        if (pkt->type == DNIV_NSP_CC) {
            if (pkt->payload_len > DNIV_NSP_MAX_CTL_DATA ||
                off + 1U + pkt->payload_len > cap)
                return -1;
            buf[off++] = (__u8)pkt->payload_len;
        } else if (off + pkt->payload_len > cap) {
            return -1;
        }
        if (pkt->payload_len) {
            __u32 i;
            if (!pkt->payload)
                return -1;
            for (i = 0; i < pkt->payload_len; i++)
                buf[off + i] = pkt->payload[i];
            off += pkt->payload_len;
        }
        return (int)off;
    }

    if (pkt->type == DNIV_NSP_DI) {
        __u32 i;
        if (pkt->payload_len > DNIV_NSP_MAX_CTL_DATA ||
            off + 3U + pkt->payload_len > cap)
            return -1;
        dniv_nsp_put_le16(buf + off, pkt->reason); off += 2U;
        buf[off++] = (__u8)pkt->payload_len;
        if (pkt->payload_len && !pkt->payload)
            return -1;
        for (i = 0; i < pkt->payload_len; i++)
            buf[off + i] = pkt->payload[i];
        off += pkt->payload_len;
        return (int)off;
    }
    if (pkt->type == DNIV_NSP_DC) {
        if (off + 2U > cap)
            return -1;
        dniv_nsp_put_le16(buf + off, pkt->reason);
        return (int)(off + 2U);
    }

    if (dniv_nsp_emit_ack(buf, cap, &off, &pkt->ack1) ||
        dniv_nsp_emit_ack(buf, cap, &off, &pkt->ack2))
        return -1;
    if (pkt->ack1.present && pkt->ack2.present &&
        dniv_nsp_ack_cross(&pkt->ack1) == dniv_nsp_ack_cross(&pkt->ack2))
        return -1;
    if (pkt->type == DNIV_NSP_ACK_DATA || pkt->type == DNIV_NSP_ACK_OTHER)
        return pkt->ack1.present ? (int)off : -1;

    if (off + 2U > cap)
        return -1;
    dniv_nsp_put_le16(buf + off,
        (__u16)((pkt->segnum & DNIV_NSP_SEQ_MASK) |
                ((pkt->type == DNIV_NSP_DATA && pkt->dly) ?
                 0x1000U : 0U)));
    off += 2U;
    if (pkt->type == DNIV_NSP_LINK_SVC) {
        if (pkt->fcmod > 2U || pkt->fcval_int > 1U || off + 2U > cap)
            return -1;
        buf[off++] = (__u8)(pkt->fcmod | (pkt->fcval_int << 2));
        buf[off++] = (__u8)pkt->fcval;
        return (int)off;
    }
    if (pkt->type == DNIV_NSP_INT &&
        (!pkt->payload_len || pkt->payload_len > DNIV_NSP_MAX_CTL_DATA))
        return -1;
    if (off + pkt->payload_len > cap || (pkt->payload_len && !pkt->payload))
        return -1;
    if (pkt->payload_len) {
        __u32 i;
        for (i = 0; i < pkt->payload_len; i++)
            buf[off + i] = pkt->payload[i];
        off += pkt->payload_len;
    }
    return (int)off;
}

#endif
