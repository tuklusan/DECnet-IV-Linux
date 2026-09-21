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

#include <linux/compiler.h>
#include <linux/errno.h>
#include <linux/jiffies.h>
#include <linux/list.h>
#include <linux/slab.h>
#include <linux/spinlock.h>
#include <linux/string.h>
#include <linux/workqueue.h>

#include <decnet_iv_nsp_wire.h>
#include "decnet_iv_ethernet.h"
#include "decnet_iv_nsp.h"

struct dniv_nsp_retransmit {
    struct list_head link;
    __u16 sequence;
    __u16 wire_len;
    enum dniv_nsp_channel channel;
    unsigned long deadline;
    __u8 tries;
    __u8 wire[];
};

struct dniv_nsp_rx_entry {
    struct list_head link;
    enum dniv_nsp_channel channel;
    enum dniv_nsp_type type;
    __u16 sequence;
    __u16 payload_len;
    __u8 bom;
    __u8 eom;
    __u8 fcmod;
    __u8 fcval_int;
    __s8 fcval;
    __u8 payload[];
};

struct dniv_nsp_control_retransmit {
    __u16 wire_len;
    unsigned long deadline;
    __u8 tries;
    __u8 wire[];
};

struct dniv_nsp_connection {
    bool used;
    __u16 local_link;
    __u16 remote_link;
    __u16 remote_node;
    __u16 tx_next[DNIV_NSP_CH_COUNT];
    __u16 rx_next[DNIV_NSP_CH_COUNT];
    __u16 retransmit_count;
    __u16 rx_queued;
    __u16 rx_queued_channel[DNIV_NSP_CH_COUNT];
    __u16 interrupt_credit;
    bool data_xon;
    bool ack_pending[DNIV_NSP_CH_COUNT];
    unsigned long ack_deadline[DNIV_NSP_CH_COUNT];
    unsigned long connect_deadline;
    unsigned long inactivity_deadline;
    enum dniv_nsp_conn_state state;
    __u16 ci_payload_len;
    __u8 ci_payload[DNIV_NSP_MAX_CI_PAYLOAD];
    __u16 accept_payload_len;
    __u8 accept_payload[DNIV_NSP_MAX_CTL_DATA];
    __u16 disconnect_reason;
    __u16 disconnect_payload_len;
    __u8 disconnect_payload[DNIV_NSP_MAX_CTL_DATA];
    struct dniv_nsp_control_retransmit *control;
    struct list_head retransmit;
    struct list_head rx_pending[DNIV_NSP_CH_COUNT];
    struct list_head rx_ready;
};

static DEFINE_SPINLOCK(dniv_nsp_lock);
static struct dniv_nsp_connection dniv_nsp_connections[DNIV_NSP_MAX_CONNECTIONS];
static __u16 dniv_nsp_next_link[DNIV_NSP_MAX_CONNECTIONS];
static dniv_nsp_notify_fn dniv_nsp_notify;

static void dniv_nsp_notify_link(__u16 local_link)
{
    dniv_nsp_notify_fn notify = READ_ONCE(dniv_nsp_notify);

    if (notify)
        notify(local_link);
}

void dniv_nsp_set_notify(dniv_nsp_notify_fn notify)
{
    WRITE_ONCE(dniv_nsp_notify, notify);
}

static void dniv_nsp_timer_workfn(struct work_struct *work);
static DECLARE_DELAYED_WORK(dniv_nsp_timer_work, dniv_nsp_timer_workfn);

static void dniv_nsp_init_conn_lists(struct dniv_nsp_connection *conn)
{
    unsigned int i;

    INIT_LIST_HEAD(&conn->retransmit);
    for (i = 0; i < DNIV_NSP_CH_COUNT; i++)
        INIT_LIST_HEAD(&conn->rx_pending[i]);
    INIT_LIST_HEAD(&conn->rx_ready);
    conn->data_xon = true;
    conn->interrupt_credit = 1U;
}

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

static void dniv_nsp_set_state_locked(struct dniv_nsp_connection *conn,
                                      enum dniv_nsp_conn_state state,
                                      unsigned long now)
{
    conn->state = state;
    switch (state) {
    case DNIV_NSP_ST_CI:
    case DNIV_NSP_ST_CR:
        conn->connect_deadline =
            now + DNIV_NSP_CONNECT_TIMEOUT_SECONDS * HZ;
        conn->inactivity_deadline = 0U;
        break;
    case DNIV_NSP_ST_CD:
    case DNIV_NSP_ST_CC:
        if (!conn->connect_deadline)
            conn->connect_deadline =
                now + DNIV_NSP_CONNECT_TIMEOUT_SECONDS * HZ;
        conn->inactivity_deadline = 0U;
        break;
    case DNIV_NSP_ST_RUN:
        conn->connect_deadline = 0U;
        conn->inactivity_deadline =
            now + DNIV_NSP_INACTIVITY_SECONDS * HZ;
        break;
    case DNIV_NSP_ST_DI:
    case DNIV_NSP_ST_CLOSED:
    default:
        conn->connect_deadline = 0U;
        conn->inactivity_deadline = 0U;
        break;
    }
}

static int dniv_nsp_queue_locked(struct dniv_nsp_connection *conn,
                                 enum dniv_nsp_channel channel,
                                 __u16 sequence, const __u8 *wire,
                                 __u16 wire_len, unsigned long deadline)
{
    struct dniv_nsp_retransmit *entry;

    if (!conn || channel >= DNIV_NSP_CH_COUNT || !wire || !wire_len ||
        wire_len > DNIV_NSP_MAX_WIRE)
        return -EINVAL;
    if (conn->retransmit_count >= DNIV_NSP_MAX_RETRANSMIT)
        return -ENOSPC;
    sequence = dniv_nsp_seq_norm(sequence);
    if (sequence != conn->tx_next[channel])
        return -EINVAL;

    entry = kmalloc(sizeof(*entry) + wire_len, GFP_ATOMIC);
    if (!entry)
        return -ENOMEM;
    entry->sequence = sequence;
    entry->wire_len = wire_len;
    entry->channel = channel;
    entry->deadline = deadline;
    entry->tries = 1U;
    memcpy(entry->wire, wire, wire_len);
    list_add_tail(&entry->link, &conn->retransmit);
    conn->retransmit_count++;
    conn->tx_next[channel] = dniv_nsp_seq_next(sequence);
    return 0;
}

static unsigned int dniv_nsp_ack_locked(struct dniv_nsp_connection *conn,
                                         enum dniv_nsp_channel channel,
                                         __u16 ack)
{
    struct dniv_nsp_retransmit *entry;
    struct dniv_nsp_retransmit *tmp;
    struct dniv_nsp_retransmit *first = NULL;
    struct dniv_nsp_retransmit *last = NULL;
    unsigned int removed = 0U;

    if (!conn || channel >= DNIV_NSP_CH_COUNT)
        return 0U;

    list_for_each_entry(entry, &conn->retransmit, link) {
        if (entry->channel != channel)
            continue;
        if (!first)
            first = entry;
        last = entry;
    }
    if (!first || !dniv_nsp_seq_in_window(first->sequence,
                                           last->sequence, ack))
        return 0U;

    list_for_each_entry_safe(entry, tmp, &conn->retransmit, link) {
        __u16 sequence;

        if (entry->channel != channel)
            continue;
        sequence = entry->sequence;
        list_del(&entry->link);
        kfree(entry);
        conn->retransmit_count--;
        removed++;
        if (sequence == ack)
            break;
    }
    return removed;
}

static struct dniv_nsp_rx_entry *
dniv_nsp_rx_alloc(const struct dniv_nsp_packet *pkt,
                  enum dniv_nsp_channel channel)
{
    struct dniv_nsp_rx_entry *entry;

    if (!pkt || channel >= DNIV_NSP_CH_COUNT ||
        pkt->payload_len > DNIV_NSP_MSS)
        return NULL;

    entry = kmalloc(sizeof(*entry) + pkt->payload_len, GFP_ATOMIC);
    if (!entry)
        return NULL;
    entry->channel = channel;
    entry->type = pkt->type;
    entry->sequence = pkt->segnum;
    entry->payload_len = (__u16)pkt->payload_len;
    entry->bom = pkt->bom;
    entry->eom = pkt->eom;
    entry->fcmod = pkt->fcmod;
    entry->fcval_int = pkt->fcval_int;
    entry->fcval = pkt->fcval;
    if (pkt->payload_len)
        memcpy(entry->payload, pkt->payload, pkt->payload_len);
    return entry;
}

static void dniv_nsp_rx_apply_locked(struct dniv_nsp_connection *conn,
                                     struct dniv_nsp_rx_entry *entry)
{
    if (entry->type == DNIV_NSP_LINK_SVC) {
        if (entry->fcval_int == 0U) {
            if (entry->fcmod)
                conn->data_xon = entry->fcmod == 2U;
        } else if (entry->fcval >= 0) {
            unsigned int credit =
                (unsigned int)conn->interrupt_credit +
                (unsigned int)entry->fcval;

            conn->interrupt_credit = (__u16)(credit > 127U ? 127U : credit);
        }
        conn->rx_queued--;
        conn->rx_queued_channel[entry->channel]--;
        kfree(entry);
        return;
    }
    list_add_tail(&entry->link, &conn->rx_ready);
}

static struct dniv_nsp_rx_entry *
dniv_nsp_rx_pending_find_locked(struct dniv_nsp_connection *conn,
                                enum dniv_nsp_channel channel,
                                __u16 sequence)
{
    struct dniv_nsp_rx_entry *entry;

    list_for_each_entry(entry, &conn->rx_pending[channel], link) {
        if (entry->sequence == sequence)
            return entry;
    }
    return NULL;
}

static bool
dniv_nsp_rx_reclaim_future_locked(struct dniv_nsp_connection *conn,
                                  enum dniv_nsp_channel channel)
{
    struct dniv_nsp_rx_entry *entry;
    struct dniv_nsp_rx_entry *victim = NULL;
    __u16 victim_delta = 0U;

    list_for_each_entry(entry, &conn->rx_pending[channel], link) {
        __u16 delta = dniv_nsp_seq_norm(
            (__u32)entry->sequence - conn->rx_next[channel]);

        if (!victim || delta > victim_delta) {
            victim = entry;
            victim_delta = delta;
        }
    }
    if (!victim)
        return false;

    list_del(&victim->link);
    conn->rx_queued--;
    conn->rx_queued_channel[channel]--;
    kfree(victim);
    return true;
}

static int dniv_nsp_rx_sequence_locked(
    struct dniv_nsp_connection *conn, const struct dniv_nsp_packet *pkt,
    enum dniv_nsp_channel channel, enum dniv_nsp_rx_order *rx_order)
{
    struct dniv_nsp_rx_entry *entry;
    enum dniv_nsp_rx_order order;

    if (!rx_order)
        return -EINVAL;
    order = dniv_nsp_seq_order(conn->rx_next[channel], pkt->segnum);
    *rx_order = order;
    if (order == DNIV_NSP_RX_DUPLICATE)
        return 0;

    if (order == DNIV_NSP_RX_FUTURE) {
        if (dniv_nsp_rx_pending_find_locked(conn, channel, pkt->segnum))
            return 0;
        /*
         * Phase IV cache buffers are optional.  If this subchannel's
         * bounded cache is full, leave the future segment unacknowledged
         * so the sender can retransmit it after the sequence gap closes.
         */
        if (conn->rx_queued_channel[channel] >= DNIV_NSP_MAX_RX_QUEUED)
            return 0;
        entry = dniv_nsp_rx_alloc(pkt, channel);
        if (!entry)
            return -ENOMEM;
        list_add_tail(&entry->link, &conn->rx_pending[channel]);
        conn->rx_queued++;
        conn->rx_queued_channel[channel]++;
        return 0;
    }

    /*
     * Never discard the missing lower-numbered segment while a higher
     * segment is cached.  Reclaim the farthest cached future segment first;
     * it was never acknowledged and remains eligible for peer retransmit.
     */
    if (conn->rx_queued_channel[channel] >= DNIV_NSP_MAX_RX_QUEUED &&
        !dniv_nsp_rx_reclaim_future_locked(conn, channel))
        return -ENOSPC;
    entry = dniv_nsp_rx_alloc(pkt, channel);
    if (!entry)
        return -ENOMEM;
    conn->rx_queued++;
    conn->rx_queued_channel[channel]++;
    dniv_nsp_rx_apply_locked(conn, entry);
    conn->rx_next[channel] = dniv_nsp_seq_next(conn->rx_next[channel]);

    for (;;) {
        entry = dniv_nsp_rx_pending_find_locked(
            conn, channel, conn->rx_next[channel]);
        if (!entry)
            break;
        list_del(&entry->link);
        dniv_nsp_rx_apply_locked(conn, entry);
        conn->rx_next[channel] = dniv_nsp_seq_next(conn->rx_next[channel]);
    }
    return 0;
}

static void dniv_nsp_clear_control_locked(struct dniv_nsp_connection *conn)
{
    if (!conn)
        return;
    kfree(conn->control);
    conn->control = NULL;
}

static int dniv_nsp_set_control_locked(struct dniv_nsp_connection *conn,
                                       const __u8 *wire, __u16 wire_len,
                                       unsigned long deadline)
{
    struct dniv_nsp_control_retransmit *control;

    if (!conn || !wire || !wire_len || wire_len > DNIV_NSP_MAX_WIRE)
        return -EINVAL;

    control = kmalloc(sizeof(*control) + wire_len, GFP_ATOMIC);
    if (!control)
        return -ENOMEM;
    control->wire_len = wire_len;
    control->deadline = deadline;
    control->tries = 1U;
    memcpy(control->wire, wire, wire_len);

    dniv_nsp_clear_control_locked(conn);
    conn->control = control;
    return 0;
}

static struct dniv_nsp_retransmit *
dniv_nsp_first_retransmit_locked(struct dniv_nsp_connection *conn,
                                 enum dniv_nsp_channel channel)
{
    struct dniv_nsp_retransmit *entry;

    list_for_each_entry(entry, &conn->retransmit, link) {
        if (entry->channel == channel)
            return entry;
    }
    return NULL;
}

static void dniv_nsp_process_ack_locked(
    struct dniv_nsp_connection *conn, enum dniv_nsp_channel channel,
    const struct dniv_nsp_ack *ack)
{
    struct dniv_nsp_retransmit *first;
    bool nak;

    if (!conn || !ack || !ack->present)
        return;

    if (dniv_nsp_ack_cross(ack))
        channel = channel == DNIV_NSP_CH_DATA ?
                  DNIV_NSP_CH_OTHER : DNIV_NSP_CH_DATA;

    first = dniv_nsp_first_retransmit_locked(conn, channel);
    if (!first)
        return;

    nak = ack->qual == DNIV_NSP_NAK || ack->qual == DNIV_NSP_XNAK;
    if (nak &&
        ack->num == dniv_nsp_seq_norm((__u32)first->sequence - 1U)) {
        first->deadline = jiffies;
        return;
    }

    if (dniv_nsp_ack_locked(conn, channel, ack->num) && nak) {
        first = dniv_nsp_first_retransmit_locked(conn, channel);
        if (first)
            first->deadline = jiffies;
    }
}

static void dniv_nsp_purge_locked(struct dniv_nsp_connection *conn)
{
    struct dniv_nsp_retransmit *entry;
    struct dniv_nsp_retransmit *tmp;
    struct dniv_nsp_rx_entry *rx;
    struct dniv_nsp_rx_entry *rxtmp;
    unsigned int i;

    dniv_nsp_clear_control_locked(conn);
    list_for_each_entry_safe(entry, tmp, &conn->retransmit, link) {
        list_del(&entry->link);
        kfree(entry);
    }
    for (i = 0; i < DNIV_NSP_CH_COUNT; i++) {
        list_for_each_entry_safe(rx, rxtmp, &conn->rx_pending[i], link) {
            list_del(&rx->link);
            kfree(rx);
        }
    }
    list_for_each_entry_safe(rx, rxtmp, &conn->rx_ready, link) {
        list_del(&rx->link);
        kfree(rx);
    }
    conn->retransmit_count = 0U;
    conn->rx_queued = 0U;
    memset(conn->rx_queued_channel, 0, sizeof(conn->rx_queued_channel));
}

int dniv_nsp_init(void)
{
    unsigned long flags;
    unsigned int i;

    spin_lock_irqsave(&dniv_nsp_lock, flags);
    memset(dniv_nsp_connections, 0, sizeof(dniv_nsp_connections));
    for (i = 0; i < DNIV_NSP_MAX_CONNECTIONS; i++) {
        dniv_nsp_init_conn_lists(&dniv_nsp_connections[i]);
        dniv_nsp_next_link[i] = (__u16)(i + 1U);
    }
    spin_unlock_irqrestore(&dniv_nsp_lock, flags);
    schedule_delayed_work(&dniv_nsp_timer_work, HZ);
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
        dniv_nsp_init_conn_lists(conn);
    }
    spin_unlock_irqrestore(&dniv_nsp_lock, flags);
    dniv_nsp_notify_link(0U);
}

void dniv_nsp_exit(void)
{
    cancel_delayed_work_sync(&dniv_nsp_timer_work);
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
    dniv_nsp_init_conn_lists(conn);
    conn->used = true;
    conn->local_link = link;
    conn->remote_link = remote_link;
    conn->remote_node = remote_node;
    conn->tx_next[DNIV_NSP_CH_DATA] = DNIV_NSP_INITIAL_SEQUENCE;
    conn->rx_next[DNIV_NSP_CH_DATA] = DNIV_NSP_INITIAL_SEQUENCE;
    conn->tx_next[DNIV_NSP_CH_OTHER] = DNIV_NSP_INITIAL_SEQUENCE;
    conn->rx_next[DNIV_NSP_CH_OTHER] = DNIV_NSP_INITIAL_SEQUENCE;
    dniv_nsp_set_state_locked(conn, initial_state, jiffies);
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
    dniv_nsp_init_conn_lists(conn);
    spin_unlock_irqrestore(&dniv_nsp_lock, flags);
    dniv_nsp_notify_link(local_link);
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
    dniv_nsp_set_state_locked(conn, new_state, jiffies);
    spin_unlock_irqrestore(&dniv_nsp_lock, flags);
    dniv_nsp_notify_link(local_link);
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
    snapshot->data_tx_next = conn->tx_next[DNIV_NSP_CH_DATA];
    snapshot->data_rx_next = conn->rx_next[DNIV_NSP_CH_DATA];
    snapshot->other_tx_next = conn->tx_next[DNIV_NSP_CH_OTHER];
    snapshot->other_rx_next = conn->rx_next[DNIV_NSP_CH_OTHER];
    snapshot->retransmit_count = conn->retransmit_count;
    snapshot->rx_queued = conn->rx_queued;
    snapshot->interrupt_credit = conn->interrupt_credit;
    snapshot->disconnect_reason = conn->disconnect_reason;
    snapshot->data_xon = conn->data_xon ? 1U : 0U;
    snapshot->connect_deadline = conn->connect_deadline;
    snapshot->inactivity_deadline = conn->inactivity_deadline;
    snapshot->state = conn->state;
    spin_unlock_irqrestore(&dniv_nsp_lock, flags);
    return 0;
}

int dniv_nsp_ci_snapshot(__u16 local_link,
                         struct dniv_nsp_ci_snapshot *snapshot,
                         __u8 *payload, __u16 capacity)
{
    struct dniv_nsp_connection *conn;
    unsigned long flags;
    int ret = 0;

    if (!snapshot || !payload)
        return -EINVAL;

    spin_lock_irqsave(&dniv_nsp_lock, flags);
    conn = dniv_nsp_find_locked(local_link);
    if (!conn) {
        ret = -ENOENT;
        goto out;
    }
    if (conn->state != DNIV_NSP_ST_CR) {
        ret = -EINVAL;
        goto out;
    }
    if (conn->ci_payload_len > capacity) {
        ret = -EMSGSIZE;
        goto out;
    }

    snapshot->local_link = conn->local_link;
    snapshot->remote_link = conn->remote_link;
    snapshot->remote_node = conn->remote_node;
    snapshot->payload_len = conn->ci_payload_len;
    if (conn->ci_payload_len)
        memcpy(payload, conn->ci_payload, conn->ci_payload_len);
out:
    spin_unlock_irqrestore(&dniv_nsp_lock, flags);
    return ret;
}

int dniv_nsp_accept_data_snapshot(__u16 local_link, __u8 *payload,
                                  __u16 capacity, __u16 *payload_len)
{
    struct dniv_nsp_connection *conn;
    unsigned long flags;
    int ret = 0;

    if (!payload || !payload_len)
        return -EINVAL;

    spin_lock_irqsave(&dniv_nsp_lock, flags);
    conn = dniv_nsp_find_locked(local_link);
    if (!conn) {
        ret = -ENOENT;
        goto out;
    }
    if (conn->accept_payload_len > capacity) {
        ret = -EMSGSIZE;
        goto out;
    }
    *payload_len = conn->accept_payload_len;
    if (conn->accept_payload_len)
        memcpy(payload, conn->accept_payload, conn->accept_payload_len);
out:
    spin_unlock_irqrestore(&dniv_nsp_lock, flags);
    return ret;
}

int dniv_nsp_disconnect_data_snapshot(__u16 local_link, __u16 *reason,
                                      __u8 *payload, __u16 capacity,
                                      __u16 *payload_len)
{
    struct dniv_nsp_connection *conn;
    unsigned long flags;
    int ret = 0;

    if (!reason || !payload || !payload_len)
        return -EINVAL;

    spin_lock_irqsave(&dniv_nsp_lock, flags);
    conn = dniv_nsp_find_locked(local_link);
    if (!conn) {
        ret = -ENOENT;
        goto out;
    }
    if (conn->disconnect_payload_len > capacity) {
        ret = -EMSGSIZE;
        goto out;
    }
    *reason = conn->disconnect_reason;
    *payload_len = conn->disconnect_payload_len;
    if (conn->disconnect_payload_len)
        memcpy(payload, conn->disconnect_payload,
               conn->disconnect_payload_len);
out:
    spin_unlock_irqrestore(&dniv_nsp_lock, flags);
    return ret;
}

int dniv_nsp_rx_ready(__u16 local_link, bool *normal, bool *interrupt)
{
    struct dniv_nsp_connection *conn;
    struct dniv_nsp_rx_entry *entry;
    unsigned long flags;
    bool started = false;
    int ret = 0;

    if (!normal || !interrupt)
        return -EINVAL;
    *normal = false;
    *interrupt = false;

    spin_lock_irqsave(&dniv_nsp_lock, flags);
    conn = dniv_nsp_find_locked(local_link);
    if (!conn) {
        ret = -ENOENT;
        goto out;
    }

    list_for_each_entry(entry, &conn->rx_ready, link) {
        if (entry->channel == DNIV_NSP_CH_OTHER &&
            entry->type == DNIV_NSP_INT) {
            *interrupt = true;
            continue;
        }
        if (entry->channel != DNIV_NSP_CH_DATA ||
            entry->type != DNIV_NSP_DATA)
            continue;
        if (!started) {
            if (!entry->bom) {
                *normal = true;
                break;
            }
            started = true;
        } else if (entry->bom) {
            *normal = true;
            break;
        }
        if (entry->eom) {
            *normal = true;
            break;
        }
    }

out:
    spin_unlock_irqrestore(&dniv_nsp_lock, flags);
    return ret;
}

int dniv_nsp_retransmit_queue(__u16 local_link,
                              enum dniv_nsp_channel channel,
                              __u16 sequence, const __u8 *wire,
                              __u16 wire_len, unsigned long deadline)
{
    struct dniv_nsp_connection *conn;
    unsigned long flags;
    int ret;

    if (channel >= DNIV_NSP_CH_COUNT || !wire || !wire_len ||
        wire_len > DNIV_NSP_MAX_WIRE)
        return -EINVAL;

    spin_lock_irqsave(&dniv_nsp_lock, flags);
    conn = dniv_nsp_find_locked(local_link);
    if (!conn)
        ret = -ENOENT;
    else
        ret = dniv_nsp_queue_locked(conn, channel, sequence, wire,
                                    wire_len, deadline);
    spin_unlock_irqrestore(&dniv_nsp_lock, flags);
    return ret;
}

unsigned int dniv_nsp_retransmit_ack(__u16 local_link,
                                     enum dniv_nsp_channel channel,
                                     __u16 ack)
{
    struct dniv_nsp_connection *conn;
    unsigned long flags;
    unsigned int removed = 0U;

    if (channel >= DNIV_NSP_CH_COUNT)
        return 0U;

    spin_lock_irqsave(&dniv_nsp_lock, flags);
    conn = dniv_nsp_find_locked(local_link);
    if (!conn) {
        spin_unlock_irqrestore(&dniv_nsp_lock, flags);
        return 0U;
    }
    removed = dniv_nsp_ack_locked(conn, channel, ack);
    spin_unlock_irqrestore(&dniv_nsp_lock, flags);
    return removed;
}

int dniv_nsp_retransmit_due(__u16 local_link,
                            enum dniv_nsp_channel channel,
                            unsigned long now, __u16 *sequence,
                            __u8 *wire, __u16 capacity, __u16 *wire_len)
{
    struct dniv_nsp_retransmit *entry;
    struct dniv_nsp_connection *conn;
    unsigned long flags;
    int ret = -EAGAIN;

    if (channel >= DNIV_NSP_CH_COUNT || !sequence || !wire || !wire_len)
        return -EINVAL;

    spin_lock_irqsave(&dniv_nsp_lock, flags);
    conn = dniv_nsp_find_locked(local_link);
    if (!conn) {
        ret = -ENOENT;
        goto out;
    }
    list_for_each_entry(entry, &conn->retransmit, link) {
        if (entry->channel != channel ||
            time_before(now, entry->deadline))
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


static int dniv_nsp_send_dc_reply(__u16 remote_node, __u16 dst, __u16 src,
                                  __u16 reason)
{
    struct dniv_nsp_packet reply;
    __u8 wire[DNIV_NSP_MAX_WIRE];
    int len;

    memset(&reply, 0, sizeof(reply));
    reply.type = DNIV_NSP_DC;
    reply.dst = dst;
    reply.src = src;
    reply.reason = reason;
    len = dniv_nsp_build(wire, sizeof(wire), &reply);
    if (len <= 0)
        return -EINVAL;
    return dniv_nsp_transmit(remote_node, wire, (__u16)len);
}

int dniv_nsp_receive(__u16 remote_node, const __u8 *wire, __u16 wire_len)
{
    struct dniv_nsp_packet pkt;
    struct dniv_nsp_connection *conn;
    unsigned long flags;
    struct dniv_nsp_packet reply;
    __u8 reply_wire[DNIV_NSP_MAX_WIRE];
    __u16 reply_node = 0U;
    __u16 notify_link = 0U;
    int reply_len = 0;

    if (!remote_node || !wire || !wire_len ||
        dniv_nsp_parse(wire, wire_len, &pkt) != DNIV_NSP_OK)
        return -EINVAL;

    spin_lock_irqsave(&dniv_nsp_lock, flags);

    if (pkt.type == DNIV_NSP_CI || pkt.type == DNIV_NSP_RCI) {
        unsigned int i;
        __u16 link;

        if (!pkt.src || pkt.payload_len > DNIV_NSP_MAX_CI_PAYLOAD) {
            spin_unlock_irqrestore(&dniv_nsp_lock, flags);
            return -EINVAL;
        }
        conn = dniv_nsp_find_remote_locked(remote_node, pkt.src);
        if (conn) {
            int ret;

            link = conn->local_link;
            spin_unlock_irqrestore(&dniv_nsp_lock, flags);
            memset(&reply, 0, sizeof(reply));
            reply.type = DNIV_NSP_ACK_CONN;
            reply.dst = pkt.src;
            reply_len = dniv_nsp_build(reply_wire, sizeof(reply_wire), &reply);
            if (reply_len <= 0)
                return -EINVAL;
            ret = dniv_nsp_transmit(remote_node, reply_wire,
                                    (__u16)reply_len);
            return ret;
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
            return dniv_nsp_send_dc_reply(
                remote_node, pkt.src, 0U, DNIV_NSP_REASON_NO_RESOURCES);
        }
        link = dniv_nsp_take_link_locked(i);
        if (!link) {
            spin_unlock_irqrestore(&dniv_nsp_lock, flags);
            return dniv_nsp_send_dc_reply(
                remote_node, pkt.src, 0U, DNIV_NSP_REASON_NO_RESOURCES);
        }
        memset(conn, 0, sizeof(*conn));
        dniv_nsp_init_conn_lists(conn);
        conn->used = true;
        conn->local_link = link;
        conn->remote_link = pkt.src;
        conn->remote_node = remote_node;
        conn->ci_payload_len = (__u16)pkt.payload_len;
        if (pkt.payload_len)
            memcpy(conn->ci_payload, pkt.payload, pkt.payload_len);
        conn->tx_next[DNIV_NSP_CH_DATA] = DNIV_NSP_INITIAL_SEQUENCE;
        conn->rx_next[DNIV_NSP_CH_DATA] = DNIV_NSP_INITIAL_SEQUENCE;
        conn->tx_next[DNIV_NSP_CH_OTHER] = DNIV_NSP_INITIAL_SEQUENCE;
        conn->rx_next[DNIV_NSP_CH_OTHER] = DNIV_NSP_INITIAL_SEQUENCE;
        dniv_nsp_set_state_locked(conn, DNIV_NSP_ST_CR, jiffies);
        spin_unlock_irqrestore(&dniv_nsp_lock, flags);

        memset(&reply, 0, sizeof(reply));
        reply.type = DNIV_NSP_ACK_CONN;
        reply.dst = pkt.src;
        reply_len = dniv_nsp_build(reply_wire, sizeof(reply_wire), &reply);
        if (reply_len > 0) {
            int ret = dniv_nsp_transmit(remote_node, reply_wire,
                                        (__u16)reply_len);

            if (!ret)
                dniv_nsp_notify_link(link);
            return ret;
        }
        return -EINVAL;
    }

    conn = dniv_nsp_find_locked(pkt.dst);
    if (!conn || conn->remote_node != remote_node) {
        bool no_link = pkt.type == DNIV_NSP_CC ||
                       pkt.type == DNIV_NSP_DI ||
                       pkt.type == DNIV_NSP_DATA ||
                       pkt.type == DNIV_NSP_INT ||
                       pkt.type == DNIV_NSP_LINK_SVC;

        spin_unlock_irqrestore(&dniv_nsp_lock, flags);
        if (no_link && pkt.src)
            return dniv_nsp_send_dc_reply(
                remote_node, pkt.src, pkt.dst, DNIV_NSP_REASON_NO_LINK);
        return -ENOENT;
    }
    if (pkt.type != DNIV_NSP_ACK_CONN) {
        if (!conn->remote_link &&
            (conn->state == DNIV_NSP_ST_CI ||
             conn->state == DNIV_NSP_ST_CD) &&
            (pkt.type == DNIV_NSP_CC || pkt.type == DNIV_NSP_DI ||
             pkt.type == DNIV_NSP_DC)) {
            if (!pkt.src && pkt.type != DNIV_NSP_DC) {
                spin_unlock_irqrestore(&dniv_nsp_lock, flags);
                return -EINVAL;
            }
            conn->remote_link = pkt.src;
        } else if (conn->remote_link != pkt.src) {
            bool no_link = pkt.type == DNIV_NSP_CC ||
                           pkt.type == DNIV_NSP_DI ||
                           pkt.type == DNIV_NSP_DATA ||
                           pkt.type == DNIV_NSP_INT ||
                           pkt.type == DNIV_NSP_LINK_SVC;

            spin_unlock_irqrestore(&dniv_nsp_lock, flags);
            if (no_link && pkt.src)
                return dniv_nsp_send_dc_reply(
                    remote_node, pkt.src, pkt.dst, DNIV_NSP_REASON_NO_LINK);
            return -ENOENT;
        }
    }

    notify_link = conn->local_link;
    switch (pkt.type) {
    case DNIV_NSP_ACK_CONN:
        if (conn->state != DNIV_NSP_ST_CI) {
            spin_unlock_irqrestore(&dniv_nsp_lock, flags);
            return -EINVAL;
        }
        dniv_nsp_clear_control_locked(conn);
        dniv_nsp_set_state_locked(conn, DNIV_NSP_ST_CD, jiffies);
        break;
    case DNIV_NSP_CC:
        if (conn->state != DNIV_NSP_ST_CI &&
            conn->state != DNIV_NSP_ST_CD) {
            spin_unlock_irqrestore(&dniv_nsp_lock, flags);
            return -EINVAL;
        }
        dniv_nsp_clear_control_locked(conn);
        conn->accept_payload_len = (__u16)pkt.payload_len;
        if (pkt.payload_len)
            memcpy(conn->accept_payload, pkt.payload, pkt.payload_len);
        dniv_nsp_set_state_locked(conn, DNIV_NSP_ST_RUN, jiffies);
        memset(&reply, 0, sizeof(reply));
        reply.type = DNIV_NSP_ACK_DATA;
        reply.dst = conn->remote_link;
        reply.src = conn->local_link;
        reply.ack1.present = 1U;
        reply.ack1.qual = DNIV_NSP_ACK;
        reply.ack1.num = 0U;
        reply_len = dniv_nsp_build(reply_wire, sizeof(reply_wire), &reply);
        reply_node = conn->remote_node;
        break;
    case DNIV_NSP_DI:
        if (!dniv_nsp_state_transition_valid(conn->state, DNIV_NSP_ST_DI)) {
            spin_unlock_irqrestore(&dniv_nsp_lock, flags);
            return -EINVAL;
        }
        memset(&reply, 0, sizeof(reply));
        reply.type = DNIV_NSP_DC;
        reply.dst = conn->remote_link;
        reply.src = conn->local_link;
        reply.reason = DNIV_NSP_REASON_DISCONNECT_COMPLETE;
        reply_len = dniv_nsp_build(reply_wire, sizeof(reply_wire), &reply);
        reply_node = conn->remote_node;
        conn->disconnect_reason = pkt.reason;
        conn->disconnect_payload_len = (__u16)pkt.payload_len;
        if (pkt.payload_len)
            memcpy(conn->disconnect_payload, pkt.payload, pkt.payload_len);
        dniv_nsp_purge_locked(conn);
        dniv_nsp_set_state_locked(conn, DNIV_NSP_ST_CLOSED, jiffies);
        break;
    case DNIV_NSP_DC:
        conn->disconnect_reason = pkt.reason;
        dniv_nsp_purge_locked(conn);
        dniv_nsp_set_state_locked(conn, DNIV_NSP_ST_CLOSED, jiffies);
        break;
    case DNIV_NSP_DATA:
    case DNIV_NSP_INT:
    case DNIV_NSP_LINK_SVC:
    case DNIV_NSP_ACK_DATA:
    case DNIV_NSP_ACK_OTHER: {
        enum dniv_nsp_channel channel;
        if (conn->state == DNIV_NSP_ST_CC) {
            dniv_nsp_clear_control_locked(conn);
            dniv_nsp_set_state_locked(conn, DNIV_NSP_ST_RUN, jiffies);
        }
        if (conn->state != DNIV_NSP_ST_RUN) {
            spin_unlock_irqrestore(&dniv_nsp_lock, flags);
            return -EINVAL;
        }

        if (pkt.type == DNIV_NSP_DATA || pkt.type == DNIV_NSP_ACK_DATA)
            channel = DNIV_NSP_CH_DATA;
        else
            channel = DNIV_NSP_CH_OTHER;

        conn->inactivity_deadline =
            jiffies + DNIV_NSP_INACTIVITY_SECONDS * HZ;

        dniv_nsp_process_ack_locked(conn, channel, &pkt.ack1);
        dniv_nsp_process_ack_locked(conn, channel, &pkt.ack2);

        if (pkt.type == DNIV_NSP_DATA || pkt.type == DNIV_NSP_INT ||
            pkt.type == DNIV_NSP_LINK_SVC) {
            enum dniv_nsp_rx_order rx_order;
            __u16 acknum;
            int rxret;

            rxret = dniv_nsp_rx_sequence_locked(
                conn, &pkt, channel, &rx_order);
            if (rxret) {
                spin_unlock_irqrestore(&dniv_nsp_lock, flags);
                return rxret;
            }

            /*
             * Future packets remain cached without acknowledging missing
             * sequence space. Duplicate traffic gets an explicit cumulative
             * ACK. In-order Phase IV traffic may request the ACK holdoff.
             */
            if (rx_order == DNIV_NSP_RX_FUTURE)
                break;

            acknum = dniv_nsp_seq_norm((__u32)conn->rx_next[channel] - 1U);
            if (rx_order == DNIV_NSP_RX_EXPECTED && pkt.dly) {
                conn->ack_pending[channel] = true;
                conn->ack_deadline[channel] =
                    jiffies + DNIV_NSP_ACK_HOLDOFF_SECONDS * HZ;
                break;
            }

            conn->ack_pending[channel] = false;
            conn->ack_deadline[channel] = 0U;
            memset(&reply, 0, sizeof(reply));
            reply.type = channel == DNIV_NSP_CH_DATA ?
                         DNIV_NSP_ACK_DATA : DNIV_NSP_ACK_OTHER;
            reply.dst = conn->remote_link;
            reply.src = conn->local_link;
            reply.ack1.present = 1U;
            reply.ack1.qual = DNIV_NSP_ACK;
            reply.ack1.num = acknum;
            reply_len = dniv_nsp_build(reply_wire, sizeof(reply_wire), &reply);
            reply_node = conn->remote_node;
        }
        break;
    }
    default:
        spin_unlock_irqrestore(&dniv_nsp_lock, flags);
        return -EINVAL;
    }

    spin_unlock_irqrestore(&dniv_nsp_lock, flags);
    dniv_nsp_notify_link(notify_link);
    if (reply_len > 0)
        return dniv_nsp_transmit(reply_node, reply_wire, (__u16)reply_len);
    return 0;
}


static int dniv_nsp_prepare_ack_locked(
    struct dniv_nsp_connection *conn, unsigned long now,
    __u16 *remote_node, __u8 *wire, __u16 *wire_len)
{
    struct dniv_nsp_packet pkt;
    unsigned int channel;

    if (!conn || conn->state != DNIV_NSP_ST_RUN || !conn->remote_link)
        return -EAGAIN;

    for (channel = 0; channel < DNIV_NSP_CH_COUNT; channel++) {
        int len;

        if (!conn->ack_pending[channel] ||
            time_before(now, conn->ack_deadline[channel]))
            continue;

        memset(&pkt, 0, sizeof(pkt));
        pkt.type = channel == DNIV_NSP_CH_DATA ?
                   DNIV_NSP_ACK_DATA : DNIV_NSP_ACK_OTHER;
        pkt.dst = conn->remote_link;
        pkt.src = conn->local_link;
        pkt.ack1.present = 1U;
        pkt.ack1.qual = DNIV_NSP_ACK;
        pkt.ack1.num =
            dniv_nsp_seq_norm((__u32)conn->rx_next[channel] - 1U);
        len = dniv_nsp_build(wire, DNIV_NSP_MAX_WIRE, &pkt);
        if (len <= 0)
            return -EINVAL;

        conn->ack_pending[channel] = false;
        conn->ack_deadline[channel] = 0U;
        *remote_node = conn->remote_node;
        *wire_len = (__u16)len;
        return 0;
    }
    return -EAGAIN;
}

static int dniv_nsp_prepare_keepalive_locked(
    struct dniv_nsp_connection *conn, unsigned long now,
    __u16 *remote_node, __u8 *wire, __u16 *wire_len)
{
    struct dniv_nsp_packet pkt;
    __u16 sequence;
    int len;
    int ret;

    if (!conn || conn->state != DNIV_NSP_ST_RUN || !conn->remote_link ||
        !conn->inactivity_deadline ||
        time_before(now, conn->inactivity_deadline))
        return -EAGAIN;

    memset(&pkt, 0, sizeof(pkt));
    sequence = conn->tx_next[DNIV_NSP_CH_OTHER];
    pkt.type = DNIV_NSP_LINK_SVC;
    pkt.dst = conn->remote_link;
    pkt.src = conn->local_link;
    pkt.segnum = sequence;
    pkt.fcmod = 0U;
    pkt.fcval_int = 0U;
    pkt.fcval = 0;
    len = dniv_nsp_build(wire, DNIV_NSP_MAX_WIRE, &pkt);
    if (len <= 0)
        return -EINVAL;

    ret = dniv_nsp_queue_locked(
        conn, DNIV_NSP_CH_OTHER, sequence, wire, (__u16)len,
        now + DNIV_NSP_DEFAULT_RESPONSE_SECONDS * HZ);
    if (ret)
        return ret;

    conn->inactivity_deadline =
        now + DNIV_NSP_INACTIVITY_SECONDS * HZ;
    *remote_node = conn->remote_node;
    *wire_len = (__u16)len;
    return 0;
}

static int dniv_nsp_prepare_retransmit_locked(
    struct dniv_nsp_connection *conn, unsigned long now,
    __u16 *remote_node, __u8 *wire, __u16 *wire_len)
{
    struct dniv_nsp_retransmit *entry;

    if (!conn)
        return -EINVAL;
    if (conn->control && time_after_eq(now, conn->control->deadline)) {
        if (conn->control->tries >= DNIV_NSP_MAX_RETRANSMITS)
            return -ETIMEDOUT;
        memcpy(wire, conn->control->wire, conn->control->wire_len);
        if (conn->state == DNIV_NSP_ST_CI &&
            wire[0] == DNIV_NSP_F_CI)
            wire[0] = DNIV_NSP_F_RCI;
        *wire_len = conn->control->wire_len;
        *remote_node = conn->remote_node;
        conn->control->tries++;
        conn->control->deadline =
            now + DNIV_NSP_DEFAULT_RESPONSE_SECONDS * HZ;
        return 0;
    }
    list_for_each_entry(entry, &conn->retransmit, link) {
        if (time_before(now, entry->deadline))
            continue;
        if (!dniv_nsp_retransmit_allowed(entry->channel, conn->data_xon))
            continue;
        if (entry->tries >= DNIV_NSP_MAX_RETRANSMITS)
            return -ETIMEDOUT;
        memcpy(wire, entry->wire, entry->wire_len);
        *wire_len = entry->wire_len;
        *remote_node = conn->remote_node;
        entry->tries++;
        entry->deadline =
            now + DNIV_NSP_DEFAULT_RESPONSE_SECONDS * HZ;
        return 0;
    }
    return -EAGAIN;
}

static void dniv_nsp_timer_workfn(struct work_struct *work)
{
    unsigned long now = jiffies;
    unsigned int i;

    (void)work;
    for (i = 0; i < DNIV_NSP_MAX_CONNECTIONS; i++) {
        __u8 wire[DNIV_NSP_MAX_WIRE];
        __u16 remote_node = 0U;
        __u16 wire_len = 0U;
        __u16 notify_link = 0U;
        unsigned long flags;
        struct dniv_nsp_connection *conn;
        int ret;

        spin_lock_irqsave(&dniv_nsp_lock, flags);
        conn = &dniv_nsp_connections[i];
        if (!conn->used) {
            spin_unlock_irqrestore(&dniv_nsp_lock, flags);
            continue;
        }

        if (conn->connect_deadline &&
            time_after_eq(now, conn->connect_deadline) &&
            conn->state == DNIV_NSP_ST_CR) {
            struct dniv_nsp_packet pkt;
            int len;

            /*
             * Session Control did not answer the inbound CI.  Reject the
             * request with reason 38 and use the normal DI retransmission
             * path.  Keep the CR alive if the control buffer cannot be
             * allocated so a later timer pass can retry without silently
             * dropping the remote request.
             */
            memset(&pkt, 0, sizeof(pkt));
            pkt.type = DNIV_NSP_DI;
            pkt.dst = conn->remote_link;
            pkt.src = conn->local_link;
            pkt.reason = DNIV_NSP_REASON_OBJECT_FAILED;
            len = dniv_nsp_build(wire, sizeof(wire), &pkt);
            if (len > 0 &&
                !dniv_nsp_set_control_locked(
                    conn, wire, (__u16)len,
                    now + DNIV_NSP_DEFAULT_RESPONSE_SECONDS * HZ)) {
                notify_link = conn->local_link;
                remote_node = conn->remote_node;
                wire_len = (__u16)len;
                dniv_nsp_set_state_locked(conn, DNIV_NSP_ST_DI, now);
                spin_unlock_irqrestore(&dniv_nsp_lock, flags);
                dniv_nsp_notify_link(notify_link);
                (void)dniv_nsp_transmit(remote_node, wire, wire_len);
                continue;
            }
            spin_unlock_irqrestore(&dniv_nsp_lock, flags);
            continue;
        }

        if (conn->connect_deadline &&
            time_after_eq(now, conn->connect_deadline) &&
            conn->state == DNIV_NSP_ST_CD) {
            /*
             * The remote NSP acknowledged our CI but its Session Control
             * never accepted or rejected it.  Preserve reason 38 locally
             * instead of erasing the connection so the socket waiter sees
             * a deterministic terminal state.
             */
            notify_link = conn->local_link;
            dniv_nsp_purge_locked(conn);
            conn->disconnect_reason = DNIV_NSP_REASON_OBJECT_FAILED;
            conn->disconnect_payload_len = 0U;
            dniv_nsp_set_state_locked(conn, DNIV_NSP_ST_CLOSED, now);
            spin_unlock_irqrestore(&dniv_nsp_lock, flags);
            dniv_nsp_notify_link(notify_link);
            continue;
        }

        ret = dniv_nsp_prepare_ack_locked(
            conn, now, &remote_node, wire, &wire_len);
        if (ret == -EAGAIN)
            ret = dniv_nsp_prepare_retransmit_locked(
                conn, now, &remote_node, wire, &wire_len);
        if (ret == -ETIMEDOUT) {
            notify_link = conn->local_link;
            dniv_nsp_purge_locked(conn);
            conn->disconnect_reason = DNIV_NSP_REASON_NODE_UNREACHABLE;
            conn->disconnect_payload_len = 0U;
            dniv_nsp_set_state_locked(conn, DNIV_NSP_ST_CLOSED, now);
            spin_unlock_irqrestore(&dniv_nsp_lock, flags);
            dniv_nsp_notify_link(notify_link);
            continue;
        }
        if (ret == -EAGAIN)
            ret = dniv_nsp_prepare_keepalive_locked(
                conn, now, &remote_node, wire, &wire_len);
        spin_unlock_irqrestore(&dniv_nsp_lock, flags);

        if (!ret)
            dniv_nsp_transmit(remote_node, wire, wire_len);
    }

    schedule_delayed_work(&dniv_nsp_timer_work, HZ);
}


static int dniv_nsp_send_control(__u16 local_link,
                                 enum dniv_nsp_conn_state required_state,
                                 enum dniv_nsp_conn_state next_state,
                                 enum dniv_nsp_type type, __u16 reason,
                                 const __u8 *payload, __u16 payload_len)
{
    struct dniv_nsp_connection *conn;
    struct dniv_nsp_packet pkt;
    __u8 wire[DNIV_NSP_MAX_WIRE];
    unsigned long flags;
    __u16 remote_node;
    int len;
    int ret;

    if (payload_len > DNIV_NSP_MAX_CTL_DATA || (payload_len && !payload))
        return -EINVAL;

    spin_lock_irqsave(&dniv_nsp_lock, flags);
    conn = dniv_nsp_find_locked(local_link);
    if (!conn || conn->state != required_state || !conn->remote_link) {
        spin_unlock_irqrestore(&dniv_nsp_lock, flags);
        return -EINVAL;
    }

    memset(&pkt, 0, sizeof(pkt));
    pkt.type = type;
    pkt.dst = conn->remote_link;
    pkt.src = conn->local_link;
    pkt.reason = reason;
    pkt.payload = payload;
    pkt.payload_len = payload_len;
    if (type == DNIV_NSP_CC) {
        pkt.fcopt = 0U;
        pkt.info = 2U;
        pkt.segsize = DNIV_NSP_MSS;
    }
    len = dniv_nsp_build(wire, sizeof(wire), &pkt);
    if (len <= 0) {
        spin_unlock_irqrestore(&dniv_nsp_lock, flags);
        return -EINVAL;
    }

    ret = dniv_nsp_set_control_locked(
        conn, wire, (__u16)len,
        jiffies + DNIV_NSP_DEFAULT_RESPONSE_SECONDS * HZ);
    if (ret) {
        spin_unlock_irqrestore(&dniv_nsp_lock, flags);
        return ret;
    }
    remote_node = conn->remote_node;
    dniv_nsp_set_state_locked(conn, next_state, jiffies);
    spin_unlock_irqrestore(&dniv_nsp_lock, flags);

    ret = dniv_nsp_transmit(remote_node, wire, (__u16)len);
    dniv_nsp_notify_link(local_link);
    return ret;
}

int dniv_nsp_connect(__u16 remote_node, const __u8 *payload,
                     __u16 payload_len, __u16 *local_link)
{
    struct dniv_nsp_connection *conn;
    struct dniv_nsp_packet pkt;
    __u8 wire[DNIV_NSP_MAX_WIRE];
    unsigned long flags;
    __u16 link;
    int len;
    int ret;

    if (!remote_node || !local_link || (payload_len && !payload))
        return -EINVAL;

    ret = dniv_nsp_conn_alloc(remote_node, 0U, DNIV_NSP_ST_CI, &link);
    if (ret)
        return ret;

    memset(&pkt, 0, sizeof(pkt));
    pkt.type = DNIV_NSP_CI;
    pkt.src = link;
    pkt.fcopt = 0U;
    pkt.info = 2U;
    pkt.segsize = DNIV_NSP_MSS;
    pkt.payload = payload;
    pkt.payload_len = payload_len;
    len = dniv_nsp_build(wire, sizeof(wire), &pkt);
    if (len <= 0) {
        dniv_nsp_conn_release(link);
        return -EINVAL;
    }

    spin_lock_irqsave(&dniv_nsp_lock, flags);
    conn = dniv_nsp_find_locked(link);
    ret = conn ? dniv_nsp_set_control_locked(
        conn, wire, (__u16)len,
        jiffies + DNIV_NSP_DEFAULT_RESPONSE_SECONDS * HZ) : -ENOENT;
    spin_unlock_irqrestore(&dniv_nsp_lock, flags);
    if (ret) {
        dniv_nsp_conn_release(link);
        return ret;
    }

    ret = dniv_nsp_transmit(remote_node, wire, (__u16)len);
    if (ret) {
        dniv_nsp_conn_release(link);
        return ret;
    }
    *local_link = link;
    return 0;
}

int dniv_nsp_accept(__u16 local_link, const __u8 *payload, __u16 payload_len)
{
    return dniv_nsp_send_control(local_link, DNIV_NSP_ST_CR,
                                 DNIV_NSP_ST_CC, DNIV_NSP_CC, 0U,
                                 payload, payload_len);
}

int dniv_nsp_reject(__u16 local_link, __u16 reason,
                    const __u8 *payload, __u16 payload_len)
{
    return dniv_nsp_send_control(local_link, DNIV_NSP_ST_CR,
                                 DNIV_NSP_ST_DI, DNIV_NSP_DI, reason,
                                 payload, payload_len);
}

int dniv_nsp_disconnect(__u16 local_link, __u16 reason,
                        const __u8 *payload, __u16 payload_len)
{
    return dniv_nsp_send_control(local_link, DNIV_NSP_ST_RUN,
                                 DNIV_NSP_ST_DI, DNIV_NSP_DI, reason,
                                 payload, payload_len);
}

int dniv_nsp_send_data(__u16 local_link, const __u8 *payload,
                       __u16 payload_len, __u8 bom, __u8 eom)
{
    struct dniv_nsp_connection *conn;
    struct dniv_nsp_packet pkt;
    __u8 wire[DNIV_NSP_MAX_WIRE];
    unsigned long flags;
    __u16 remote_node;
    __u16 sequence;
    int len;
    int ret;

    if (!payload || !payload_len || payload_len > DNIV_NSP_MSS)
        return -EINVAL;

    spin_lock_irqsave(&dniv_nsp_lock, flags);
    conn = dniv_nsp_find_locked(local_link);
    if (!conn || conn->state != DNIV_NSP_ST_RUN || !conn->remote_link) {
        spin_unlock_irqrestore(&dniv_nsp_lock, flags);
        return -ENOTCONN;
    }
    if (!conn->data_xon) {
        spin_unlock_irqrestore(&dniv_nsp_lock, flags);
        return -EAGAIN;
    }
    {
        struct dniv_nsp_retransmit *queued;
        unsigned int in_flight = 0U;

        list_for_each_entry(queued, &conn->retransmit, link) {
            if (queued->channel == DNIV_NSP_CH_DATA)
                in_flight++;
        }
        if (in_flight >= DNIV_NSP_MAX_WINDOW) {
            spin_unlock_irqrestore(&dniv_nsp_lock, flags);
            return -EAGAIN;
        }
    }

    sequence = conn->tx_next[DNIV_NSP_CH_DATA];
    memset(&pkt, 0, sizeof(pkt));
    pkt.type = DNIV_NSP_DATA;
    pkt.dst = conn->remote_link;
    pkt.src = conn->local_link;
    pkt.segnum = sequence;
    pkt.bom = bom ? 1U : 0U;
    pkt.eom = eom ? 1U : 0U;
    pkt.payload = payload;
    pkt.payload_len = payload_len;
    len = dniv_nsp_build(wire, sizeof(wire), &pkt);
    if (len <= 0) {
        spin_unlock_irqrestore(&dniv_nsp_lock, flags);
        return -EINVAL;
    }

    ret = dniv_nsp_queue_locked(
        conn, DNIV_NSP_CH_DATA, sequence, wire, (__u16)len,
        jiffies + DNIV_NSP_DEFAULT_RESPONSE_SECONDS * HZ);
    if (ret) {
        spin_unlock_irqrestore(&dniv_nsp_lock, flags);
        return ret;
    }
    remote_node = conn->remote_node;
    spin_unlock_irqrestore(&dniv_nsp_lock, flags);

    return dniv_nsp_transmit(remote_node, wire, (__u16)len);
}


static int dniv_nsp_queue_interrupt_grant_locked(
    struct dniv_nsp_connection *conn, __u8 *wire, __u16 *wire_len,
    __u16 *remote_node)
{
    struct dniv_nsp_packet pkt;
    __u16 sequence;
    int len;
    int ret;

    if (!conn || !wire || !wire_len || !remote_node ||
        conn->state != DNIV_NSP_ST_RUN || !conn->remote_link)
        return -ENOTCONN;

    sequence = conn->tx_next[DNIV_NSP_CH_OTHER];
    memset(&pkt, 0, sizeof(pkt));
    pkt.type = DNIV_NSP_LINK_SVC;
    pkt.dst = conn->remote_link;
    pkt.src = conn->local_link;
    pkt.segnum = sequence;
    pkt.fcmod = 0U;
    pkt.fcval_int = 1U;
    pkt.fcval = 1;
    len = dniv_nsp_build(wire, DNIV_NSP_MAX_WIRE, &pkt);
    if (len <= 0)
        return -EINVAL;

    ret = dniv_nsp_queue_locked(
        conn, DNIV_NSP_CH_OTHER, sequence, wire, (__u16)len,
        jiffies + DNIV_NSP_DEFAULT_RESPONSE_SECONDS * HZ);
    if (ret)
        return ret;

    *wire_len = (__u16)len;
    *remote_node = conn->remote_node;
    return 0;
}

int dniv_nsp_send_interrupt(__u16 local_link, const __u8 *payload,
                            __u16 payload_len)
{
    struct dniv_nsp_connection *conn;
    struct dniv_nsp_packet pkt;
    __u8 wire[DNIV_NSP_MAX_WIRE];
    unsigned long flags;
    __u16 remote_node;
    __u16 sequence;
    int len;
    int ret;

    if (!payload || !payload_len || payload_len > DNIV_NSP_MAX_INTERRUPT)
        return -EINVAL;

    spin_lock_irqsave(&dniv_nsp_lock, flags);
    conn = dniv_nsp_find_locked(local_link);
    if (!conn || conn->state != DNIV_NSP_ST_RUN || !conn->remote_link) {
        spin_unlock_irqrestore(&dniv_nsp_lock, flags);
        return -ENOTCONN;
    }
    if (!conn->interrupt_credit) {
        spin_unlock_irqrestore(&dniv_nsp_lock, flags);
        return -EAGAIN;
    }

    sequence = conn->tx_next[DNIV_NSP_CH_OTHER];
    memset(&pkt, 0, sizeof(pkt));
    pkt.type = DNIV_NSP_INT;
    pkt.dst = conn->remote_link;
    pkt.src = conn->local_link;
    pkt.segnum = sequence;
    pkt.payload = payload;
    pkt.payload_len = payload_len;
    len = dniv_nsp_build(wire, sizeof(wire), &pkt);
    if (len <= 0) {
        spin_unlock_irqrestore(&dniv_nsp_lock, flags);
        return -EINVAL;
    }

    ret = dniv_nsp_queue_locked(
        conn, DNIV_NSP_CH_OTHER, sequence, wire, (__u16)len,
        jiffies + DNIV_NSP_DEFAULT_RESPONSE_SECONDS * HZ);
    if (ret) {
        spin_unlock_irqrestore(&dniv_nsp_lock, flags);
        return ret;
    }
    conn->interrupt_credit--;
    remote_node = conn->remote_node;
    spin_unlock_irqrestore(&dniv_nsp_lock, flags);

    return dniv_nsp_transmit(remote_node, wire, (__u16)len);
}

int dniv_nsp_recv(__u16 local_link, struct dniv_nsp_rx_meta *meta,
                  __u8 *payload, __u16 capacity)
{
    struct dniv_nsp_connection *conn;
    struct dniv_nsp_rx_entry *entry;
    unsigned long flags;
    int ret = 0;

    if (!meta || !payload)
        return -EINVAL;

    spin_lock_irqsave(&dniv_nsp_lock, flags);
    conn = dniv_nsp_find_locked(local_link);
    if (!conn) {
        ret = -ENOENT;
        goto out;
    }
    if (list_empty(&conn->rx_ready)) {
        ret = -EAGAIN;
        goto out;
    }

    entry = list_first_entry(&conn->rx_ready,
                             struct dniv_nsp_rx_entry, link);
    if (entry->payload_len > capacity) {
        ret = -EMSGSIZE;
        goto out;
    }

    meta->channel = entry->channel;
    meta->type = entry->type;
    meta->sequence = entry->sequence;
    meta->payload_len = entry->payload_len;
    meta->bom = entry->bom;
    meta->eom = entry->eom;
    if (entry->payload_len)
        memcpy(payload, entry->payload, entry->payload_len);
    list_del(&entry->link);
    conn->rx_queued--;
    conn->rx_queued_channel[entry->channel]--;
    kfree(entry);
out:
    spin_unlock_irqrestore(&dniv_nsp_lock, flags);
    return ret;
}


int dniv_nsp_recv_interrupt(__u16 local_link, __u8 *payload,
                            __u16 capacity, __u16 *payload_len)
{
    struct dniv_nsp_connection *conn;
    struct dniv_nsp_rx_entry *entry;
    struct dniv_nsp_rx_entry *found = NULL;
    __u8 wire[DNIV_NSP_MAX_WIRE];
    unsigned long flags;
    __u16 remote_node = 0U;
    __u16 wire_len = 0U;
    int ret = 0;

    if (!payload || !payload_len || !capacity)
        return -EINVAL;

    spin_lock_irqsave(&dniv_nsp_lock, flags);
    conn = dniv_nsp_find_locked(local_link);
    if (!conn) {
        ret = -ENOENT;
        goto out;
    }

    list_for_each_entry(entry, &conn->rx_ready, link) {
        if (entry->channel == DNIV_NSP_CH_OTHER &&
            entry->type == DNIV_NSP_INT) {
            found = entry;
            break;
        }
    }
    if (!found) {
        ret = -EAGAIN;
        goto out;
    }
    if (!found->payload_len ||
        found->payload_len > DNIV_NSP_MAX_INTERRUPT) {
        ret = -EPROTO;
        goto out;
    }
    if (found->payload_len > capacity) {
        ret = -EMSGSIZE;
        goto out;
    }

    /*
     * Queue the replacement interrupt credit before exposing the message to
     * userspace.  If the other-data retransmit queue is temporarily full,
     * leave the interrupt queued so a later recv can retry without losing
     * flow-control state.
     */
    ret = dniv_nsp_queue_interrupt_grant_locked(
        conn, wire, &wire_len, &remote_node);
    if (ret)
        goto out;

    memcpy(payload, found->payload, found->payload_len);
    *payload_len = found->payload_len;
    list_del(&found->link);
    conn->rx_queued--;
    conn->rx_queued_channel[found->channel]--;
    kfree(found);

out:
    spin_unlock_irqrestore(&dniv_nsp_lock, flags);
    if (!ret && wire_len)
        (void)dniv_nsp_transmit(remote_node, wire, wire_len);
    return ret;
}


int dniv_nsp_recv_message(__u16 local_link, __u8 *payload, __u32 capacity,
                          __u32 *payload_len)
{
    struct dniv_nsp_connection *conn;
    struct dniv_nsp_rx_entry *entry;
    struct dniv_nsp_rx_entry *tmp;
    unsigned long flags;
    __u32 total = 0U;
    __u32 copied = 0U;
    bool started = false;
    bool complete = false;
    int ret = 0;

    if (!payload || !payload_len)
        return -EINVAL;

    spin_lock_irqsave(&dniv_nsp_lock, flags);
    conn = dniv_nsp_find_locked(local_link);
    if (!conn) {
        ret = -ENOENT;
        goto out;
    }

    list_for_each_entry(entry, &conn->rx_ready, link) {
        if (entry->channel != DNIV_NSP_CH_DATA ||
            entry->type != DNIV_NSP_DATA)
            continue;

        if (!started) {
            if (!entry->bom) {
                ret = -EPROTO;
                goto out;
            }
            started = true;
        } else if (entry->bom) {
            ret = -EPROTO;
            goto out;
        }

        if (entry->payload_len > DNIV_NSP_MAX_MESSAGE - total) {
            ret = -EMSGSIZE;
            goto out;
        }
        total += entry->payload_len;
        if (entry->eom) {
            complete = true;
            break;
        }
    }

    if (!started || !complete) {
        ret = -EAGAIN;
        goto out;
    }
    if (total > capacity) {
        ret = -EMSGSIZE;
        goto out;
    }

    list_for_each_entry_safe(entry, tmp, &conn->rx_ready, link) {
        if (entry->channel != DNIV_NSP_CH_DATA ||
            entry->type != DNIV_NSP_DATA)
            continue;

        if (entry->payload_len) {
            memcpy(payload + copied, entry->payload, entry->payload_len);
            copied += entry->payload_len;
        }
        complete = entry->eom;
        list_del(&entry->link);
        conn->rx_queued--;
        conn->rx_queued_channel[entry->channel]--;
        kfree(entry);
        if (complete)
            break;
    }
    *payload_len = copied;

out:
    spin_unlock_irqrestore(&dniv_nsp_lock, flags);
    return ret;
}


int dniv_nsp_transmit(__u16 remote_node, const __u8 *wire, __u16 wire_len)
{
    struct dniv_nsp_packet pkt;

    if (!remote_node || !wire || !wire_len ||
        dniv_nsp_parse(wire, wire_len, &pkt) != DNIV_NSP_OK)
        return -EINVAL;
    return dniv_eth_send_payload(remote_node, wire, wire_len);
}
