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
#include <linux/workqueue.h>

#include <decnet_iv_route_metric.h>
#include "decnet_iv_route.h"

#define DNIV_ROUTE_L1_BUCKETS 1024U
#define DNIV_ROUTE_L2_BUCKETS 64U

struct dniv_route_candidate {
    struct hlist_node node;
    __u16 next_hop;
    __u16 cost;
    __s32 ifindex;
    __u8 hops;
    unsigned long expires;
};

static DEFINE_SPINLOCK(dniv_route_lock);
static struct hlist_head dniv_l1_routes[DNIV_ROUTE_L1_BUCKETS];
static struct hlist_head dniv_l2_routes[DNIV_ROUTE_L2_BUCKETS];

static void dniv_route_age_workfn(struct work_struct *work);
static DECLARE_DELAYED_WORK(dniv_route_age_work, dniv_route_age_workfn);

static int dniv_route_destination_valid(__u8 level, __u16 destination)
{
    if (level == 1U)
        return destination < DNIV_ROUTE_L1_BUCKETS;
    if (level == 2U)
        return destination >= 1U && destination < DNIV_ROUTE_L2_BUCKETS;
    return 0;
}

static struct hlist_head *dniv_route_bucket(__u8 level, __u16 destination)
{
    if (!dniv_route_destination_valid(level, destination))
        return NULL;
    return level == 1U ? &dniv_l1_routes[destination]
                       : &dniv_l2_routes[destination];
}

static struct dniv_route_candidate *dniv_route_find_locked(
    struct hlist_head *head, __u16 next_hop, __s32 ifindex)
{
    struct dniv_route_candidate *candidate;

    hlist_for_each_entry(candidate, head, node) {
        if (candidate->next_hop == next_hop &&
            candidate->ifindex == ifindex)
            return candidate;
    }
    return NULL;
}

static void dniv_route_clear_table_locked(struct hlist_head *table,
                                           unsigned int count)
{
    unsigned int i;

    for (i = 0; i < count; i++) {
        struct dniv_route_candidate *candidate;
        struct hlist_node *tmp;

        hlist_for_each_entry_safe(candidate, tmp, &table[i], node) {
            hlist_del(&candidate->node);
            kfree(candidate);
        }
    }
}

int dniv_route_init(void)
{
    unsigned int i;

    for (i = 0; i < DNIV_ROUTE_L1_BUCKETS; i++)
        INIT_HLIST_HEAD(&dniv_l1_routes[i]);
    for (i = 0; i < DNIV_ROUTE_L2_BUCKETS; i++)
        INIT_HLIST_HEAD(&dniv_l2_routes[i]);

    schedule_delayed_work(&dniv_route_age_work, HZ);
    return 0;
}

void dniv_route_exit(void)
{
    cancel_delayed_work_sync(&dniv_route_age_work);
    dniv_route_reset();
}

void dniv_route_reset(void)
{
    unsigned long flags;

    spin_lock_irqsave(&dniv_route_lock, flags);
    dniv_route_clear_table_locked(dniv_l1_routes, DNIV_ROUTE_L1_BUCKETS);
    dniv_route_clear_table_locked(dniv_l2_routes, DNIV_ROUTE_L2_BUCKETS);
    spin_unlock_irqrestore(&dniv_route_lock, flags);
}

int dniv_route_update(__u8 level, __u16 destination, __u16 next_hop,
                      __s32 ifindex, __u16 cost, __u8 hops,
                      unsigned long expires)
{
    struct dniv_route_candidate *candidate;
    struct dniv_route_candidate *allocated;
    struct hlist_head *head;
    unsigned long flags;

    head = dniv_route_bucket(level, destination);
    if (!head || next_hop == 0U || ifindex <= 0 ||
        !dniv_route_metric_valid(cost, hops))
        return -EINVAL;

    spin_lock_irqsave(&dniv_route_lock, flags);
    candidate = dniv_route_find_locked(head, next_hop, ifindex);
    if (candidate) {
        candidate->cost = cost;
        candidate->hops = hops;
        candidate->expires = expires;
        spin_unlock_irqrestore(&dniv_route_lock, flags);
        return 0;
    }
    spin_unlock_irqrestore(&dniv_route_lock, flags);

    allocated = kmalloc(sizeof(*allocated), GFP_ATOMIC);
    if (!allocated)
        return -ENOMEM;

    spin_lock_irqsave(&dniv_route_lock, flags);
    candidate = dniv_route_find_locked(head, next_hop, ifindex);
    if (!candidate) {
        candidate = allocated;
        allocated = NULL;
        candidate->next_hop = next_hop;
        candidate->ifindex = ifindex;
        hlist_add_head(&candidate->node, head);
    }
    candidate->cost = cost;
    candidate->hops = hops;
    candidate->expires = expires;
    spin_unlock_irqrestore(&dniv_route_lock, flags);

    kfree(allocated);
    return 0;
}

void dniv_route_withdraw(__u8 level, __u16 destination, __u16 next_hop,
                         __s32 ifindex)
{
    struct dniv_route_candidate *candidate;
    struct hlist_head *head;
    unsigned long flags;

    head = dniv_route_bucket(level, destination);
    if (!head)
        return;

    spin_lock_irqsave(&dniv_route_lock, flags);
    candidate = dniv_route_find_locked(head, next_hop, ifindex);
    if (candidate) {
        hlist_del(&candidate->node);
        kfree(candidate);
    }
    spin_unlock_irqrestore(&dniv_route_lock, flags);
}


void dniv_route_refresh_adjacency(__u16 next_hop, __s32 ifindex,
                                  unsigned long expires)
{
    unsigned long flags;
    unsigned int i;

    if (next_hop == 0U || ifindex <= 0)
        return;

    spin_lock_irqsave(&dniv_route_lock, flags);
    for (i = 0; i < DNIV_ROUTE_L1_BUCKETS; i++) {
        struct dniv_route_candidate *candidate;

        hlist_for_each_entry(candidate, &dniv_l1_routes[i], node) {
            if (candidate->next_hop == next_hop &&
                candidate->ifindex == ifindex)
                candidate->expires = expires;
        }
    }
    for (i = 1; i < DNIV_ROUTE_L2_BUCKETS; i++) {
        struct dniv_route_candidate *candidate;

        hlist_for_each_entry(candidate, &dniv_l2_routes[i], node) {
            if (candidate->next_hop == next_hop &&
                candidate->ifindex == ifindex)
                candidate->expires = expires;
        }
    }
    spin_unlock_irqrestore(&dniv_route_lock, flags);
}

void dniv_route_withdraw_adjacency(__u16 next_hop, __s32 ifindex)
{
    unsigned long flags;
    unsigned int i;

    spin_lock_irqsave(&dniv_route_lock, flags);
    for (i = 0; i < DNIV_ROUTE_L1_BUCKETS; i++) {
        struct dniv_route_candidate *candidate;
        struct hlist_node *tmp;

        hlist_for_each_entry_safe(candidate, tmp, &dniv_l1_routes[i], node) {
            if (candidate->next_hop == next_hop &&
                candidate->ifindex == ifindex) {
                hlist_del(&candidate->node);
                kfree(candidate);
            }
        }
    }
    for (i = 1; i < DNIV_ROUTE_L2_BUCKETS; i++) {
        struct dniv_route_candidate *candidate;
        struct hlist_node *tmp;

        hlist_for_each_entry_safe(candidate, tmp, &dniv_l2_routes[i], node) {
            if (candidate->next_hop == next_hop &&
                candidate->ifindex == ifindex) {
                hlist_del(&candidate->node);
                kfree(candidate);
            }
        }
    }
    spin_unlock_irqrestore(&dniv_route_lock, flags);
}

int dniv_route_lookup(__u8 level, __u16 destination,
                      struct dniv_route_result *result)
{
    struct dniv_route_candidate *candidate;
    struct dniv_route_candidate *best = NULL;
    struct hlist_head *head;
    unsigned long flags;

    if (!result)
        return -EINVAL;
    head = dniv_route_bucket(level, destination);
    if (!head)
        return -EINVAL;

    spin_lock_irqsave(&dniv_route_lock, flags);
    hlist_for_each_entry(candidate, head, node) {
        if (candidate->expires &&
            time_after_eq(jiffies, candidate->expires))
            continue;
        if (!best ||
            dniv_route_candidate_better(
                candidate->cost, candidate->next_hop, candidate->ifindex,
                best->cost, best->next_hop, best->ifindex))
            best = candidate;
    }
    if (!best) {
        spin_unlock_irqrestore(&dniv_route_lock, flags);
        return -ENOENT;
    }

    result->destination = destination;
    result->next_hop = best->next_hop;
    result->cost = best->cost;
    result->ifindex = best->ifindex;
    result->level = level;
    result->hops = best->hops;
    spin_unlock_irqrestore(&dniv_route_lock, flags);
    return 0;
}

unsigned int dniv_route_age(unsigned long now)
{
    unsigned long flags;
    unsigned int removed = 0;
    unsigned int i;

    spin_lock_irqsave(&dniv_route_lock, flags);
    for (i = 0; i < DNIV_ROUTE_L1_BUCKETS; i++) {
        struct dniv_route_candidate *candidate;
        struct hlist_node *tmp;

        hlist_for_each_entry_safe(candidate, tmp, &dniv_l1_routes[i], node) {
            if (candidate->expires &&
                time_after_eq(now, candidate->expires)) {
                hlist_del(&candidate->node);
                kfree(candidate);
                removed++;
            }
        }
    }
    for (i = 1; i < DNIV_ROUTE_L2_BUCKETS; i++) {
        struct dniv_route_candidate *candidate;
        struct hlist_node *tmp;

        hlist_for_each_entry_safe(candidate, tmp, &dniv_l2_routes[i], node) {
            if (candidate->expires &&
                time_after_eq(now, candidate->expires)) {
                hlist_del(&candidate->node);
                kfree(candidate);
                removed++;
            }
        }
    }
    spin_unlock_irqrestore(&dniv_route_lock, flags);
    return removed;
}

static void dniv_route_age_workfn(struct work_struct *work)
{
    (void)work;
    dniv_route_age(jiffies);
    schedule_delayed_work(&dniv_route_age_work, HZ);
}
