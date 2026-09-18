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

#include <linux/errno.h>
#include <linux/jiffies.h>
#include <linux/list.h>
#include <linux/slab.h>
#include <linux/spinlock.h>
#include <linux/string.h>

#include <decnet_iv_nsp_wire.h>
#include "decnet_iv_ethernet.h"
#include "decnet_iv_nsp.h"

struct dniv_nsp_retransmit {
    struct list_head link;
    __u16 sequence;
    __u16 wire_len;
    unsigned long deadline;
    __u8 wire[];
};

struct dniv_nsp_connection {
    bool used;
    __u16 local_link;
    __u16 remote_link;
    __u16 remote_node;
    __u16 tx_next;
    __u16 rx_next;
    __u16 retransmit_count;
    enum dniv_nsp_conn_state state;
    struct list_head retransmit;
};

static DEFINE_SPINLOCK(dniv_nsp_lock);
static struct dniv_nsp_connection dniv_nsp_connections[DNIV_NSP_MAX_CONNECTIONS];
static __u16 dniv_nsp_next_link[DNIV_NSP_MAX_CONNECTIONS];

static struct dniv_nsp_connection *dniv_nsp_find_locked(__u16 local_link)
{
    unsigned int i;

    if (!local_link)
        return NULL;
    for (i = 0; i < DNIV_NSP_MAX_CONNECTIONS; i++) {
        if (dniv_nsp_connections[i].used &&
            dniv_nsp_connections[i].local_link == local_link)
            return &dniv_nsp_connections[i];
    }
    return NULL;
}

static struct dniv_nsp_connection *
dniv_nsp_find_remote_locked(__u16 remote_node, __u16 remote_link)
{
    unsigned int i;

    if (!remote_node || !remote_link)
        return NULL;
    for (i = 0; i < DNIV_NSP_MAX_CONNECTIONS; i++) {
        if (dniv_nsp_connections[i].used &&
            dniv_nsp_connections[i].remote_node == remote_node &&
            dniv_nsp_connections[i].remote_link == remote_link)
            return &dniv_nsp_connections[i];
    }
    return NULL;
}

static bool dniv_nsp_link_in_use_locked(__u16 local_link)
{
    return dniv_nsp_find_locked(local_link) != NULL;
}

static __u16 dniv_nsp_take_link_locked(unsigned int slot)
{
    unsigned int tries;

    for (tries = 0; tries < 65535U; tries++) {
        __u16 candidate = dniv_nsp_next_link[slot];
        __u32 next;

        next = (__u32)candidate + DNIV_NSP_MAX_CONNECTIONS + 1U;
        dniv_nsp_next_link[slot] = (__u16)next;
        if (!dniv_nsp_next_link[slot])
            dniv_nsp_next_link[slot] = (__u16)(slot + 1U);
        if (candidate && !dniv_nsp_link_in_use_locked(candidate))
            return candidate;
    }
    return 0U;
}

static void dniv_nsp_purge_locked(struct dniv_nsp_connection *conn)
{
    struct dniv_nsp_retransmit *entry;
    struct dniv_nsp_retransmit *tmp;

    list_for_each_entry_safe(entry, tmp, &conn->retransmit, link) {
        list_del(&entry->link);
        kfree(entry);
    }
    conn->retransmit_count = 0U;
}

int dniv_nsp_init(void)
{
    unsigned long flags;
    unsigned int i;

    spin_lock_irqsave(&dniv_nsp_lock, flags);
    memset(dniv_nsp_connections, 0, sizeof(dniv_nsp_connections));
    for (i = 0; i < DNIV_NSP_MAX_CONNECTIONS; i++) {
        INIT_LIST_HEAD(&dniv_nsp_connections[i].retransmit);
        dniv_nsp_next_link[i] = (__u16)(i + 1U);
    }
    spin_unlock_irqrestore(&dniv_nsp_lock, flags);
    return 0;
}

void dniv_nsp_reset(void)
{
    unsigned long flags;
    unsigned int i;

    spin_lock_irqsave(&dniv_nsp_lock, flags);
    for (i = 0; i < DNIV_NSP_MAX_CONNECTIONS; i++) {
        struct dniv_nsp_connection *conn = &dniv_nsp_connections[i];

        if (conn->used)
            dniv_nsp_purge_locked(conn);
        memset(conn, 0, sizeof(*conn));
        INIT_LIST_HEAD(&conn->retransmit);
    }
    spin_unlock_irqrestore(&dniv_nsp_lock, flags);
}

void dniv_nsp_exit(void)
{
    dniv_nsp_reset();
}

int dniv_nsp_conn_alloc(__u16 remote_node, __u16 remote_link,
                        enum dniv_nsp_conn_state initial_state,
                        __u16 *local_link)
{
    struct dniv_nsp_connection *conn = NULL;
    unsigned long flags;
    unsigned int i;
    __u16 link;

    if (!local_link ||
        !dniv_nsp_state_transition_valid(DNIV_NSP_ST_CLOSED, initial_state))
        return -EINVAL;

    spin_lock_irqsave(&dniv_nsp_lock, flags);
    for (i = 0; i < DNIV_NSP_MAX_CONNECTIONS; i++) {
        if (!dniv_nsp_connections[i].used) {
            conn = &dniv_nsp_connections[i];
            break;
        }
    }
    if (!conn) {
        spin_unlock_irqrestore(&dniv_nsp_lock, flags);
        return -ENOSPC;
    }

    link = dniv_nsp_take_link_locked(i);
    if (!link) {
        spin_unlock_irqrestore(&dniv_nsp_lock, flags);
        return -ENOSPC;
    }

    memset(conn, 0, sizeof(*conn));
    INIT_LIST_HEAD(&conn->retransmit);
    conn->used = true;
    conn->local_link = link;
    conn->remote_link = remote_link;
    conn->remote_node = remote_node;
    conn->state = initial_state;
    *local_link = link;
    spin_unlock_irqrestore(&dniv_nsp_lock, flags);
    return 0;
}

int dniv_nsp_conn_release(__u16 local_link)
{
    struct dniv_nsp_connection *conn;
    unsigned long flags;

    spin_lock_irqsave(&dniv_nsp_lock, flags);
    conn = dniv_nsp_find_locked(local_link);
    if (!conn) {
        spin_unlock_irqrestore(&dniv_nsp_lock, flags);
        return -ENOENT;
    }
    dniv_nsp_purge_locked(conn);
    memset(conn, 0, sizeof(*conn));
    INIT_LIST_HEAD(&conn->retransmit);
    spin_unlock_irqrestore(&dniv_nsp_lock, flags);
    return 0;
}

int dniv_nsp_conn_transition(__u16 local_link,
                             enum dniv_nsp_conn_state new_state)
{
    struct dniv_nsp_connection *conn;
    unsigned long flags;

    spin_lock_irqsave(&dniv_nsp_lock, flags);
    conn = dniv_nsp_find_locked(local_link);
    if (!conn) {
        spin_unlock_irqrestore(&dniv_nsp_lock, flags);
        return -ENOENT;
    }
    if (!dniv_nsp_state_transition_valid(conn->state, new_state)) {
        spin_unlock_irqrestore(&dniv_nsp_lock, flags);
        return -EINVAL;
    }
    conn->state = new_state;
    spin_unlock_irqrestore(&dniv_nsp_lock, flags);
    return 0;
}

int dniv_nsp_conn_set_remote(__u16 local_link, __u16 remote_node,
                             __u16 remote_link)
{
    struct dniv_nsp_connection *conn;
    unsigned long flags;

    if (!remote_node || !remote_link)
        return -EINVAL;

    spin_lock_irqsave(&dniv_nsp_lock, flags);
    conn = dniv_nsp_find_locked(local_link);
    if (!conn) {
        spin_unlock_irqrestore(&dniv_nsp_lock, flags);
        return -ENOENT;
    }
    conn->remote_node = remote_node;
    conn->remote_link = remote_link;
    spin_unlock_irqrestore(&dniv_nsp_lock, flags);
    return 0;
}

int dniv_nsp_conn_snapshot(__u16 local_link,
                           struct dniv_nsp_conn_snapshot *snapshot)
{
    struct dniv_nsp_connection *conn;
    unsigned long flags;

    if (!snapshot)
        return -EINVAL;

    spin_lock_irqsave(&dniv_nsp_lock, flags);
    conn = dniv_nsp_find_locked(local_link);
    if (!conn) {
        spin_unlock_irqrestore(&dniv_nsp_lock, flags);
        return -ENOENT;
    }
    snapshot->local_link = conn->local_link;
    snapshot->remote_link = conn->remote_link;
    snapshot->remote_node = conn->remote_node;
    snapshot->tx_next = conn->tx_next;
    snapshot->rx_next = conn->rx_next;
    snapshot->retransmit_count = conn->retransmit_count;
    snapshot->state = conn->state;
    spin_unlock_irqrestore(&dniv_nsp_lock, flags);
    return 0;
}

int dniv_nsp_retransmit_queue(__u16 local_link, __u16 sequence,
                              const __u8 *wire, __u16 wire_len,
                              unsigned long deadline)
{
    struct dniv_nsp_retransmit *entry;
    struct dniv_nsp_connection *conn;
    unsigned long flags;

    if (!wire || !wire_len)
        return -EINVAL;

    entry = kmalloc(sizeof(*entry) + wire_len, GFP_ATOMIC);
    if (!entry)
        return -ENOMEM;
    entry->sequence = dniv_nsp_seq_norm(sequence);
    entry->wire_len = wire_len;
    entry->deadline = deadline;
    memcpy(entry->wire, wire, wire_len);

    spin_lock_irqsave(&dniv_nsp_lock, flags);
    conn = dniv_nsp_find_locked(local_link);
    if (!conn) {
        spin_unlock_irqrestore(&dniv_nsp_lock, flags);
        kfree(entry);
        return -ENOENT;
    }
    if (conn->retransmit_count >= DNIV_NSP_MAX_RETRANSMIT) {
        spin_unlock_irqrestore(&dniv_nsp_lock, flags);
        kfree(entry);
        return -ENOSPC;
    }
    if (entry->sequence != conn->tx_next) {
        spin_unlock_irqrestore(&dniv_nsp_lock, flags);
        kfree(entry);
        return -EINVAL;
    }
    list_add_tail(&entry->link, &conn->retransmit);
    conn->retransmit_count++;
    conn->tx_next = dniv_nsp_seq_next(entry->sequence);
    spin_unlock_irqrestore(&dniv_nsp_lock, flags);
    return 0;
}

unsigned int dniv_nsp_retransmit_ack(__u16 local_link, __u16 ack)
{
    struct dniv_nsp_retransmit *entry;
    struct dniv_nsp_retransmit *tmp;
    struct dniv_nsp_connection *conn;
    unsigned long flags;
    unsigned int removed = 0U;

    spin_lock_irqsave(&dniv_nsp_lock, flags);
    conn = dniv_nsp_find_locked(local_link);
    if (!conn) {
        spin_unlock_irqrestore(&dniv_nsp_lock, flags);
        return 0U;
    }
    list_for_each_entry_safe(entry, tmp, &conn->retransmit, link) {
        if (!dniv_nsp_seq_acked(entry->sequence, ack))
            break;
        list_del(&entry->link);
        kfree(entry);
        conn->retransmit_count--;
        removed++;
    }
    spin_unlock_irqrestore(&dniv_nsp_lock, flags);
    return removed;
}

int dniv_nsp_retransmit_due(__u16 local_link, unsigned long now,
                            __u16 *sequence, __u8 *wire, __u16 capacity,
                            __u16 *wire_len)
{
    struct dniv_nsp_retransmit *entry;
    struct dniv_nsp_connection *conn;
    unsigned long flags;
    int ret = -EAGAIN;

    if (!sequence || !wire || !wire_len)
        return -EINVAL;

    spin_lock_irqsave(&dniv_nsp_lock, flags);
    conn = dniv_nsp_find_locked(local_link);
    if (!conn) {
        ret = -ENOENT;
        goto out;
    }
    list_for_each_entry(entry, &conn->retransmit, link) {
        if (time_before(now, entry->deadline))
            continue;
        if (entry->wire_len > capacity) {
            ret = -EMSGSIZE;
            goto out;
        }
        *sequence = entry->sequence;
        *wire_len = entry->wire_len;
        memcpy(wire, entry->wire, entry->wire_len);
        ret = 0;
        goto out;
    }
out:
    spin_unlock_irqrestore(&dniv_nsp_lock, flags);
    return ret;
}


int dniv_nsp_receive(__u16 remote_node, const __u8 *wire, __u16 wire_len)
{
    struct dniv_nsp_packet pkt;
    struct dniv_nsp_connection *conn;
    unsigned long flags;
    enum dniv_nsp_rx_order order;

    if (!remote_node || !wire || !wire_len ||
        dniv_nsp_parse(wire, wire_len, &pkt) != DNIV_NSP_OK)
        return -EINVAL;

    spin_lock_irqsave(&dniv_nsp_lock, flags);

    if (pkt.type == DNIV_NSP_CI || pkt.type == DNIV_NSP_RCI) {
        unsigned int i;
        __u16 link;

        if (!pkt.src) {
            spin_unlock_irqrestore(&dniv_nsp_lock, flags);
            return -EINVAL;
        }
        conn = dniv_nsp_find_remote_locked(remote_node, pkt.src);
        if (conn) {
            spin_unlock_irqrestore(&dniv_nsp_lock, flags);
            return 0;
        }
        conn = NULL;
        for (i = 0; i < DNIV_NSP_MAX_CONNECTIONS; i++) {
            if (!dniv_nsp_connections[i].used) {
                conn = &dniv_nsp_connections[i];
                break;
            }
        }
        if (!conn) {
            spin_unlock_irqrestore(&dniv_nsp_lock, flags);
            return -ENOSPC;
        }
        link = dniv_nsp_take_link_locked(i);
        if (!link) {
            spin_unlock_irqrestore(&dniv_nsp_lock, flags);
            return -ENOSPC;
        }
        memset(conn, 0, sizeof(*conn));
        INIT_LIST_HEAD(&conn->retransmit);
        conn->used = true;
        conn->local_link = link;
        conn->remote_link = pkt.src;
        conn->remote_node = remote_node;
        conn->state = DNIV_NSP_ST_CR;
        spin_unlock_irqrestore(&dniv_nsp_lock, flags);
        return 0;
    }

    conn = dniv_nsp_find_locked(pkt.dst);
    if (!conn || conn->remote_node != remote_node ||
        (pkt.type != DNIV_NSP_ACK_CONN && conn->remote_link != pkt.src)) {
        spin_unlock_irqrestore(&dniv_nsp_lock, flags);
        return -ENOENT;
    }

    switch (pkt.type) {
    case DNIV_NSP_ACK_CONN:
        if (conn->state != DNIV_NSP_ST_CI) {
            spin_unlock_irqrestore(&dniv_nsp_lock, flags);
            return -EINVAL;
        }
        conn->state = DNIV_NSP_ST_CD;
        break;
    case DNIV_NSP_CC:
        if (conn->state != DNIV_NSP_ST_CI &&
            conn->state != DNIV_NSP_ST_CD) {
            spin_unlock_irqrestore(&dniv_nsp_lock, flags);
            return -EINVAL;
        }
        conn->state = DNIV_NSP_ST_RUN;
        break;
    case DNIV_NSP_DI:
        if (!dniv_nsp_state_transition_valid(conn->state, DNIV_NSP_ST_DI)) {
            spin_unlock_irqrestore(&dniv_nsp_lock, flags);
            return -EINVAL;
        }
        conn->state = DNIV_NSP_ST_DI;
        break;
    case DNIV_NSP_DC:
        dniv_nsp_purge_locked(conn);
        memset(conn, 0, sizeof(*conn));
        INIT_LIST_HEAD(&conn->retransmit);
        break;
    case DNIV_NSP_DATA:
    case DNIV_NSP_INT:
    case DNIV_NSP_LINK_SVC:
    case DNIV_NSP_ACK_DATA:
    case DNIV_NSP_ACK_OTHER:
        if (conn->state == DNIV_NSP_ST_CC)
            conn->state = DNIV_NSP_ST_RUN;
        if (conn->state != DNIV_NSP_ST_RUN) {
            spin_unlock_irqrestore(&dniv_nsp_lock, flags);
            return -EINVAL;
        }
        if (pkt.ack1.present && !dniv_nsp_ack_cross(&pkt.ack1)) {
            struct dniv_nsp_retransmit *entry;
            struct dniv_nsp_retransmit *tmp;

            list_for_each_entry_safe(entry, tmp, &conn->retransmit, link) {
                if (!dniv_nsp_seq_acked(entry->sequence, pkt.ack1.num))
                    break;
                list_del(&entry->link);
                kfree(entry);
                conn->retransmit_count--;
            }
        }
        if (pkt.type == DNIV_NSP_DATA || pkt.type == DNIV_NSP_INT ||
            pkt.type == DNIV_NSP_LINK_SVC) {
            order = dniv_nsp_seq_order(conn->rx_next, pkt.segnum);
            if (order == DNIV_NSP_RX_EXPECTED)
                conn->rx_next = dniv_nsp_seq_next(conn->rx_next);
        }
        break;
    default:
        spin_unlock_irqrestore(&dniv_nsp_lock, flags);
        return -EINVAL;
    }

    spin_unlock_irqrestore(&dniv_nsp_lock, flags);
    return 0;
}


int dniv_nsp_transmit(__u16 remote_node, const __u8 *wire, __u16 wire_len)
{
    struct dniv_nsp_packet pkt;

    if (!remote_node || !wire || !wire_len ||
        dniv_nsp_parse(wire, wire_len, &pkt) != DNIV_NSP_OK)
        return -EINVAL;
    return dniv_eth_send_payload(remote_node, wire, wire_len);
}
