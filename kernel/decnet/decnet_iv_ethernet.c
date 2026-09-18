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

#include <linux/atomic.h>
#include <linux/errno.h>
#include <linux/etherdevice.h>
#include <linux/if_arp.h>
#include <linux/if_ether.h>
#include <linux/jiffies.h>
#include <linux/netdevice.h>
#include <linux/notifier.h>
#include <linux/rtnetlink.h>
#include <linux/skbuff.h>
#include <linux/spinlock.h>
#include <linux/workqueue.h>
#include <net/net_namespace.h>

#include <decnet_iv_route_metric.h>
#include <decnet_iv_wire.h>
#include "decnet_iv_ethernet.h"
#include "decnet_iv_route.h"

#define DNIV_MAX_ADJACENCIES 64U
#define DNIV_MAX_DR_STATES 64U
#define DNIV_DR_DELAY_SECONDS 5U
#define DNIV_ETH_LENGTH_LEN 2U
#define DNIV_ROUTE_L1_BATCH_SIZE 64U
#define DNIV_ROUTE_TRIGGER_SECONDS 1U
#define DNIV_ROUTE_PERIOD_SECONDS 180U

static const __u8 dniv_all_routers[ETH_ALEN] = {0xab, 0x00, 0x00, 0x03, 0x00, 0x00};
static const __u8 dniv_all_level2_routers[ETH_ALEN] = {0x09, 0x00, 0x2b, 0x02, 0x00, 0x00};
static const __u8 dniv_all_endnodes[ETH_ALEN] = {0xab, 0x00, 0x00, 0x04, 0x00, 0x00};

struct dniv_adj_entry {
    bool used;
    int ifindex;
    __u16 address;
    __u16 block_size;
    __u16 hello_timer;
    __u8 node_type;
    __u8 state;
    __u8 priority;
    __u8 mac[ETH_ALEN];
    unsigned long expires;
};

struct dniv_dr_state {
    bool used;
    bool local_candidate;
    int ifindex;
    unsigned long candidate_since;
};

static DEFINE_SPINLOCK(dniv_adj_lock);
static struct dniv_adj_entry dniv_adjacencies[DNIV_MAX_ADJACENCIES];
static struct dniv_dr_state dniv_dr_states[DNIV_MAX_DR_STATES];
static __u16 dniv_local_address;
static __u16 dniv_hello_interval;
static __u16 dniv_eth_cost;
static __u8 dniv_local_node_type;
static __u8 dniv_local_priority;

static atomic64_t dniv_rx_frames = ATOMIC64_INIT(0);
static atomic64_t dniv_rx_bytes = ATOMIC64_INIT(0);
static atomic64_t dniv_hello_rx = ATOMIC64_INIT(0);
static atomic64_t dniv_hello_tx = ATOMIC64_INIT(0);
static atomic64_t dniv_hello_errors = ATOMIC64_INIT(0);
static atomic64_t dniv_adjacency_up = ATOMIC64_INIT(0);
static atomic64_t dniv_adjacency_down = ATOMIC64_INIT(0);

static void dniv_hello_workfn(struct work_struct *work);
static void dniv_age_workfn(struct work_struct *work);
static void dniv_route_workfn(struct work_struct *work);
static DECLARE_DELAYED_WORK(dniv_hello_work, dniv_hello_workfn);
static DECLARE_DELAYED_WORK(dniv_age_work, dniv_age_workfn);
static DECLARE_DELAYED_WORK(dniv_route_work, dniv_route_workfn);
static __u64 dniv_last_route_generation;
static unsigned long dniv_last_route_full;

static struct dniv_adj_entry *dniv_find_adj_locked(int ifindex, __u16 address)
{
    unsigned int i;

    for (i = 0; i < DNIV_MAX_ADJACENCIES; i++) {
        if (dniv_adjacencies[i].used &&
            dniv_adjacencies[i].ifindex == ifindex &&
            dniv_adjacencies[i].address == address)
            return &dniv_adjacencies[i];
    }
    return NULL;
}

static struct dniv_adj_entry *dniv_alloc_adj_locked(void)
{
    unsigned int i;

    for (i = 0; i < DNIV_MAX_ADJACENCIES; i++) {
        if (!dniv_adjacencies[i].used)
            return &dniv_adjacencies[i];
    }
    return NULL;
}

static struct dniv_dr_state *dniv_find_dr_state_locked(int ifindex)
{
    unsigned int i;

    for (i = 0; i < DNIV_MAX_DR_STATES; i++) {
        if (dniv_dr_states[i].used && dniv_dr_states[i].ifindex == ifindex)
            return &dniv_dr_states[i];
    }
    return NULL;
}

static struct dniv_dr_state *dniv_alloc_dr_state_locked(int ifindex)
{
    struct dniv_dr_state *state;
    unsigned int i;

    state = dniv_find_dr_state_locked(ifindex);
    if (state)
        return state;
    for (i = 0; i < DNIV_MAX_DR_STATES; i++) {
        if (!dniv_dr_states[i].used) {
            state = &dniv_dr_states[i];
            memset(state, 0, sizeof(*state));
            state->used = true;
            state->ifindex = ifindex;
            return state;
        }
    }
    return NULL;
}

static void dniv_drop_dr_state_locked(int ifindex)
{
    struct dniv_dr_state *state = dniv_find_dr_state_locked(ifindex);

    if (state)
        memset(state, 0, sizeof(*state));
}

static void dniv_clear_dr_states_locked(void)
{
    memset(dniv_dr_states, 0, sizeof(dniv_dr_states));
}

static void dniv_drop_adj_locked(struct dniv_adj_entry *adj)
{
    if (!adj || !adj->used)
        return;
    dniv_route_withdraw_adjacency(adj->address, adj->ifindex);
    if (adj->state == DNIV_ADJ_STATE_UP)
        atomic64_inc(&dniv_adjacency_down);
    memset(adj, 0, sizeof(*adj));
}

static void dniv_refresh_direct_routes_locked(const struct dniv_adj_entry *adj)
{
    __u16 local_area;

    if (!adj || !adj->used || adj->state != DNIV_ADJ_STATE_UP ||
        dniv_local_node_type == DNIV_NODE_TYPE_ENDNODE)
        return;

    local_area = DNIV_ADDR_AREA(dniv_local_address);
    if (DNIV_ADDR_AREA(adj->address) == local_area) {
        dniv_route_update(1U, DNIV_ADDR_NODE(adj->address), adj->address,
                          adj->ifindex, dniv_eth_cost, 1U, adj->expires);
    } else if (dniv_local_node_type == DNIV_NODE_TYPE_L2_ROUTER &&
               adj->node_type == DNIV_NODE_TYPE_L2_ROUTER) {
        dniv_route_update(2U, DNIV_ADDR_AREA(adj->address), adj->address,
                          adj->ifindex, dniv_eth_cost, 1U, adj->expires);
    }
}

static struct dniv_adj_entry *dniv_alloc_router_adj_locked(
    int ifindex, __u16 address, __u8 priority, bool *rejected)
{
    struct dniv_adj_entry *lowest = NULL;
    unsigned int count = 0;
    unsigned int i;

    *rejected = false;
    for (i = 0; i < DNIV_MAX_ADJACENCIES; i++) {
        struct dniv_adj_entry *adj = &dniv_adjacencies[i];

        if (!adj->used || adj->ifindex != ifindex ||
            adj->node_type == DNIV_NODE_TYPE_ENDNODE)
            continue;
        count++;
        if (!lowest || adj->priority < lowest->priority ||
            (adj->priority == lowest->priority &&
             adj->address < lowest->address))
            lowest = adj;
    }

    if (count < DNIV_WIRE_MAX_RS_ENTRIES)
        return dniv_alloc_adj_locked();

    if (!lowest || priority < lowest->priority ||
        (priority == lowest->priority && address <= lowest->address)) {
        *rejected = true;
        return NULL;
    }

    dniv_drop_adj_locked(lowest);
    return lowest;
}

static void dniv_clear_adjacencies_locked(void)
{
    unsigned int i;

    for (i = 0; i < DNIV_MAX_ADJACENCIES; i++)
        dniv_drop_adj_locked(&dniv_adjacencies[i]);
}

static void dniv_drop_if_adjacencies_locked(int ifindex)
{
    unsigned int i;

    for (i = 0; i < DNIV_MAX_ADJACENCIES; i++) {
        if (dniv_adjacencies[i].used &&
            dniv_adjacencies[i].ifindex == ifindex)
            dniv_drop_adj_locked(&dniv_adjacencies[i]);
    }
}

static unsigned long dniv_listen_expires(__u16 timer)
{
    __u32 milliseconds = dniv_wire_listen_msecs(timer, dniv_hello_interval);

    return jiffies + msecs_to_jiffies(milliseconds);
}

static bool dniv_area_compatible(__u16 peer, __u8 peer_type)
{
    __u16 local = READ_ONCE(dniv_local_address);

    if (DNIV_ADDR_AREA(peer) == DNIV_ADDR_AREA(local))
        return true;
    return dniv_local_node_type == DNIV_NODE_TYPE_L2_ROUTER &&
           peer_type == DNIV_NODE_TYPE_L2_ROUTER;
}

static int dniv_add_dev_filters(struct net_device *dev)
{
    __u8 local_mac[ETH_ALEN];
    int err;

    if (dev->type != ARPHRD_ETHER || (dev->flags & IFF_LOOPBACK))
        return 0;

    /* Own one secondary-unicast-list reference even when it matches the
     * device's primary address.  That makes the DECnet receive address
     * independent of later NETDEV_CHANGEADDR events and gives teardown an
     * exact reference to release.
     */
    dniv_wire_mac_from_address(READ_ONCE(dniv_local_address), local_mac);
    err = dev_uc_add(dev, local_mac);
    if (err)
        return err;

    if (dniv_local_node_type == DNIV_NODE_TYPE_ENDNODE) {
        err = dev_mc_add(dev, dniv_all_endnodes);
        if (err)
            dev_uc_del(dev, local_mac);
        return err;
    }

    err = dev_mc_add(dev, dniv_all_routers);
    if (err) {
        dev_uc_del(dev, local_mac);
        return err;
    }

    if (dniv_local_node_type == DNIV_NODE_TYPE_L2_ROUTER) {
        err = dev_mc_add(dev, dniv_all_level2_routers);
        if (err) {
            dev_mc_del(dev, dniv_all_routers);
            dev_uc_del(dev, local_mac);
            return err;
        }
    }
    return 0;
}

static void dniv_remove_dev_filters(struct net_device *dev, __u16 address)
{
    __u8 local_mac[ETH_ALEN];

    if (dev->type != ARPHRD_ETHER || (dev->flags & IFF_LOOPBACK))
        return;

    dniv_wire_mac_from_address(address, local_mac);
    dev_uc_del(dev, local_mac);
    if (dniv_local_node_type == DNIV_NODE_TYPE_ENDNODE) {
        dev_mc_del(dev, dniv_all_endnodes);
        return;
    }

    dev_mc_del(dev, dniv_all_routers);
    if (dniv_local_node_type == DNIV_NODE_TYPE_L2_ROUTER)
        dev_mc_del(dev, dniv_all_level2_routers);
}

static int dniv_netdev_event(struct notifier_block *nb, unsigned long event,
                             void *ptr)
{
    struct net_device *dev = netdev_notifier_info_to_dev(ptr);
    unsigned long flags;
    int err;

    (void)nb;
    if (event == NETDEV_DOWN || event == NETDEV_UNREGISTER) {
        if (event == NETDEV_UNREGISTER)
            dniv_remove_dev_filters(dev, READ_ONCE(dniv_local_address));
        spin_lock_irqsave(&dniv_adj_lock, flags);
        dniv_drop_if_adjacencies_locked(dev->ifindex);
        dniv_drop_dr_state_locked(dev->ifindex);
        spin_unlock_irqrestore(&dniv_adj_lock, flags);
        return NOTIFY_DONE;
    }
    if (event != NETDEV_REGISTER)
        return NOTIFY_DONE;
    err = dniv_add_dev_filters(dev);
    if (err) {
        pr_warn("decnet_iv: failed to add Ethernet filters on %s: %d\n",
                dev->name, err);
        return notifier_from_errno(err);
    }
    return NOTIFY_DONE;
}

static struct notifier_block dniv_netdev_notifier = {
    .notifier_call = dniv_netdev_event,
};


static int dniv_xmit_routing(struct net_device *dev,
                             const __u8 dst[ETH_ALEN],
                             const __u8 *payload, unsigned int payload_len)
{
    struct sk_buff *skb;
    struct ethhdr *eth;
    __u8 src[ETH_ALEN];
    __u8 *length;
    int ret;

    if (!dev || !dst || !payload || payload_len == 0U ||
        payload_len > DNIV_WIRE_BLOCK_SIZE)
        return -EINVAL;

    skb = alloc_skb(LL_RESERVED_SPACE(dev) + ETH_HLEN +
                    DNIV_ETH_LENGTH_LEN + payload_len, GFP_KERNEL);
    if (!skb)
        return -ENOMEM;

    skb_reserve(skb, LL_RESERVED_SPACE(dev));
    skb_reset_mac_header(skb);
    eth = skb_put(skb, ETH_HLEN);
    dniv_wire_mac_from_address(READ_ONCE(dniv_local_address), src);
    ether_addr_copy(eth->h_dest, dst);
    ether_addr_copy(eth->h_source, src);
    eth->h_proto = cpu_to_be16(ETH_P_DNA_RT);
    length = skb_put(skb, DNIV_ETH_LENGTH_LEN);
    dniv_wire_put_le16(length, (__u16)payload_len);
    memcpy(skb_put(skb, payload_len), payload, payload_len);
    skb->dev = dev;
    skb->protocol = eth->h_proto;
    skb_set_network_header(skb, ETH_HLEN + DNIV_ETH_LENGTH_LEN);

    ret = dev_queue_xmit(skb);
    return ret == NET_XMIT_SUCCESS || ret == NET_XMIT_CN ? 0 : -EIO;
}

static bool dniv_has_up_router_adjacency(int ifindex, __u8 level)
{
    unsigned long flags;
    __u16 local_area;
    bool found = false;
    unsigned int i;

    local_area = DNIV_ADDR_AREA(READ_ONCE(dniv_local_address));
    spin_lock_irqsave(&dniv_adj_lock, flags);
    for (i = 0; i < DNIV_MAX_ADJACENCIES; i++) {
        const struct dniv_adj_entry *adj = &dniv_adjacencies[i];

        if (!adj->used || adj->ifindex != ifindex ||
            adj->state != DNIV_ADJ_STATE_UP ||
            adj->node_type == DNIV_NODE_TYPE_ENDNODE)
            continue;
        if (level == 1U && DNIV_ADDR_AREA(adj->address) == local_area) {
            found = true;
            break;
        }
        if (level == 2U && adj->node_type == DNIV_NODE_TYPE_L2_ROUTER) {
            found = true;
            break;
        }
    }
    spin_unlock_irqrestore(&dniv_adj_lock, flags);
    return found;
}

static void dniv_send_l1_updates(struct net_device *dev,
                                 const __u16 *entries)
{
    __u8 payload[DNIV_WIRE_ROUTE_HEADER_LEN +
                 DNIV_WIRE_ROUTE_SEGMENT_HEADER_LEN +
                 DNIV_ROUTE_L1_BATCH_SIZE * DNIV_WIRE_ROUTE_ENTRY_LEN +
                 DNIV_WIRE_ROUTE_CHECKSUM_LEN];
    struct dniv_wire_route_segment segment;
    __u16 start;

    if (!dniv_has_up_router_adjacency(dev->ifindex, 1U))
        return;

    for (start = 0U; start < 1024U; start += DNIV_ROUTE_L1_BATCH_SIZE) {
        int len;

        segment.start = start;
        segment.count = DNIV_ROUTE_L1_BATCH_SIZE;
        segment.entries = entries + start;
        len = dniv_wire_build_routing(
            payload, sizeof(payload), READ_ONCE(dniv_local_address), 1U,
            &segment, 1U);
        if (len > 0)
            dniv_xmit_routing(dev, dniv_all_routers, payload,
                              (unsigned int)len);
    }
}

static void dniv_send_l2_updates(struct net_device *dev,
                                 const __u16 *entries)
{
    __u8 payload[DNIV_WIRE_ROUTE_HEADER_LEN +
                 DNIV_WIRE_ROUTE_SEGMENT_HEADER_LEN +
                 63U * DNIV_WIRE_ROUTE_ENTRY_LEN +
                 DNIV_WIRE_ROUTE_CHECKSUM_LEN];
    struct dniv_wire_route_segment segment;
    int len;

    if (dniv_local_node_type != DNIV_NODE_TYPE_L2_ROUTER ||
        !dniv_has_up_router_adjacency(dev->ifindex, 2U))
        return;

    segment.start = 1U;
    segment.count = 63U;
    segment.entries = entries + 1U;
    len = dniv_wire_build_routing(
        payload, sizeof(payload), READ_ONCE(dniv_local_address), 2U,
        &segment, 1U);
    if (len <= 0)
        return;

    dniv_xmit_routing(dev, dniv_all_routers, payload, (unsigned int)len);
    dniv_xmit_routing(dev, dniv_all_level2_routers, payload,
                      (unsigned int)len);
}

static void dniv_route_workfn(struct work_struct *work)
{
    __u16 l1[1024];
    __u16 l2[64];
    struct net_device *dev;
    __u64 generation;
    unsigned long now = jiffies;
    bool periodic;

    (void)work;
    if (dniv_local_node_type == DNIV_NODE_TYPE_ENDNODE)
        goto out_schedule;

    generation = dniv_route_get_generation();
    periodic = dniv_last_route_full == 0U ||
               time_after_eq(now, dniv_last_route_full +
                                  DNIV_ROUTE_PERIOD_SECONDS * HZ);
    if (!periodic && generation == dniv_last_route_generation)
        goto out_schedule;

    if (dniv_route_snapshot(1U, DNIV_ADDR_NODE(dniv_local_address),
                            l1, ARRAY_SIZE(l1)) != 0)
        goto out_schedule;
    if (dniv_local_node_type == DNIV_NODE_TYPE_L2_ROUTER) {
        __u16 local_area = DNIV_ADDR_AREA(dniv_local_address);

        if (dniv_route_snapshot(2U, local_area, l2, ARRAY_SIZE(l2)) != 0)
            goto out_schedule;
        if (dniv_route_area_attached(local_area))
            l1[0] = 0U;
    }

    rtnl_lock();
    for_each_netdev(&init_net, dev) {
        if (dev->type != ARPHRD_ETHER || (dev->flags & IFF_LOOPBACK) ||
            !(dev->flags & IFF_UP) || !netif_running(dev))
            continue;
        dniv_send_l1_updates(dev, l1);
        if (dniv_local_node_type == DNIV_NODE_TYPE_L2_ROUTER)
            dniv_send_l2_updates(dev, l2);
    }
    rtnl_unlock();

    dniv_last_route_generation = generation;
    if (periodic)
        dniv_last_route_full = now;

out_schedule:
    schedule_delayed_work(&dniv_route_work,
                          DNIV_ROUTE_TRIGGER_SECONDS * HZ);
}

static int dniv_xmit_hello(struct net_device *dev, const __u8 dst[ETH_ALEN],
                           const __u8 *payload, unsigned int payload_len)
{
    struct sk_buff *skb;
    struct ethhdr *eth;
    __u8 src[ETH_ALEN];
    __u8 *length;
    int ret;

    if (payload_len > DNIV_WIRE_BLOCK_SIZE)
        return -EMSGSIZE;

    skb = alloc_skb(LL_RESERVED_SPACE(dev) + ETH_HLEN +
                    DNIV_ETH_LENGTH_LEN + payload_len, GFP_KERNEL);
    if (!skb)
        return -ENOMEM;

    skb_reserve(skb, LL_RESERVED_SPACE(dev));
    skb_reset_mac_header(skb);
    eth = skb_put(skb, ETH_HLEN);
    dniv_wire_mac_from_address(READ_ONCE(dniv_local_address), src);
    ether_addr_copy(eth->h_dest, dst);
    ether_addr_copy(eth->h_source, src);
    eth->h_proto = cpu_to_be16(ETH_P_DNA_RT);
    length = skb_put(skb, DNIV_ETH_LENGTH_LEN);
    dniv_wire_put_le16(length, (__u16)payload_len);
    memcpy(skb_put(skb, payload_len), payload, payload_len);
    skb->dev = dev;
    skb->protocol = eth->h_proto;
    skb_set_network_header(skb, ETH_HLEN + DNIV_ETH_LENGTH_LEN);

    ret = dev_queue_xmit(skb);
    if (ret == NET_XMIT_SUCCESS || ret == NET_XMIT_CN) {
        atomic64_inc(&dniv_hello_tx);
        return 0;
    }
    return -EIO;
}

static __u8 dniv_collect_router_entries(int ifindex,
                                         struct dniv_wire_rs_entry *entries)
{
    unsigned long flags;
    __u8 count = 0;
    unsigned int i;

    spin_lock_irqsave(&dniv_adj_lock, flags);
    for (i = 0; i < DNIV_MAX_ADJACENCIES &&
                count < DNIV_WIRE_MAX_RS_ENTRIES; i++) {
        const struct dniv_adj_entry *adj = &dniv_adjacencies[i];

        if (!adj->used || adj->ifindex != ifindex ||
            adj->node_type == DNIV_NODE_TYPE_ENDNODE)
            continue;
        entries[count].address = adj->address;
        entries[count].priority = adj->priority;
        entries[count].twoway = adj->state == DNIV_ADJ_STATE_UP;
        count++;
    }
    spin_unlock_irqrestore(&dniv_adj_lock, flags);
    return count;
}

static bool dniv_local_is_dr(int ifindex)
{
    struct dniv_dr_state *state;
    unsigned long flags;
    unsigned long now = jiffies;
    __u16 local;
    __u16 local_area;
    bool best = true;
    bool ready = false;
    unsigned int i;

    spin_lock_irqsave(&dniv_adj_lock, flags);
    local = dniv_local_address;
    local_area = DNIV_ADDR_AREA(local);
    for (i = 0; i < DNIV_MAX_ADJACENCIES; i++) {
        const struct dniv_adj_entry *adj = &dniv_adjacencies[i];

        if (!adj->used || adj->ifindex != ifindex ||
            adj->node_type == DNIV_NODE_TYPE_ENDNODE ||
            DNIV_ADDR_AREA(adj->address) != local_area)
            continue;
        if (adj->priority > dniv_local_priority ||
            (adj->priority == dniv_local_priority && adj->address > local)) {
            best = false;
            break;
        }
    }

    state = dniv_find_dr_state_locked(ifindex);
    if (!best) {
        if (state) {
            state->local_candidate = false;
            state->candidate_since = 0;
        }
    } else {
        if (!state)
            state = dniv_alloc_dr_state_locked(ifindex);
        if (state && !state->local_candidate) {
            state->local_candidate = true;
            state->candidate_since = now;
        } else if (state && time_after_eq(
                       now, state->candidate_since +
                            DNIV_DR_DELAY_SECONDS * HZ)) {
            ready = true;
        }
    }
    spin_unlock_irqrestore(&dniv_adj_lock, flags);
    return ready;
}

static void dniv_endnode_neighbor(int ifindex, __u8 neighbor[ETH_ALEN])
{
    unsigned long flags;
    unsigned int i;

    eth_zero_addr(neighbor);
    spin_lock_irqsave(&dniv_adj_lock, flags);
    for (i = 0; i < DNIV_MAX_ADJACENCIES; i++) {
        const struct dniv_adj_entry *adj = &dniv_adjacencies[i];

        if (adj->used && adj->ifindex == ifindex &&
            adj->node_type != DNIV_NODE_TYPE_ENDNODE &&
            adj->state == DNIV_ADJ_STATE_UP) {
            ether_addr_copy(neighbor, adj->mac);
            break;
        }
    }
    spin_unlock_irqrestore(&dniv_adj_lock, flags);
}

static void dniv_send_hello_on_dev(struct net_device *dev)
{
    __u8 payload[DNIV_WIRE_ROUTER_MIN_LEN +
                 DNIV_WIRE_MAX_RS_ENTRIES * DNIV_WIRE_RS_ENTRY_LEN];
    __u16 local = READ_ONCE(dniv_local_address);
    int len;

    if (dev->type != ARPHRD_ETHER || (dev->flags & IFF_LOOPBACK) ||
        !(dev->flags & IFF_UP) || !netif_running(dev))
        return;

    if (dniv_local_node_type == DNIV_NODE_TYPE_ENDNODE) {
        __u8 neighbor[ETH_ALEN];

        dniv_endnode_neighbor(dev->ifindex, neighbor);
        len = dniv_wire_build_endnode_hello(payload, sizeof(payload), local,
                                             dniv_hello_interval, neighbor);
        if (len > 0)
            dniv_xmit_hello(dev, dniv_all_routers, payload, len);
        return;
    }

    {
        struct dniv_wire_rs_entry entries[DNIV_WIRE_MAX_RS_ENTRIES];
        __u8 count = dniv_collect_router_entries(dev->ifindex, entries);

        len = dniv_wire_build_router_hello(payload, sizeof(payload), local,
                                            dniv_local_node_type,
                                            dniv_local_priority,
                                            dniv_hello_interval,
                                            entries, count);
    }
    if (len <= 0)
        return;
    dniv_xmit_hello(dev, dniv_all_routers, payload, len);
    if (dniv_local_node_type == DNIV_NODE_TYPE_L2_ROUTER)
        dniv_xmit_hello(dev, dniv_all_level2_routers, payload, len);
    if (dniv_local_is_dr(dev->ifindex))
        dniv_xmit_hello(dev, dniv_all_endnodes, payload, len);
}

static void dniv_hello_workfn(struct work_struct *work)
{
    struct net_device *dev;

    (void)work;
    rtnl_lock();
    for_each_netdev(&init_net, dev)
        dniv_send_hello_on_dev(dev);
    rtnl_unlock();
    schedule_delayed_work(&dniv_hello_work,
                          msecs_to_jiffies((unsigned long)dniv_hello_interval *
                                          1000UL));
}

static void dniv_age_workfn(struct work_struct *work)
{
    unsigned long flags;
    unsigned int i;

    (void)work;
    spin_lock_irqsave(&dniv_adj_lock, flags);
    for (i = 0; i < DNIV_MAX_ADJACENCIES; i++) {
        struct dniv_adj_entry *adj = &dniv_adjacencies[i];

        if (adj->used && time_after_eq(jiffies, adj->expires))
            dniv_drop_adj_locked(adj);
    }
    spin_unlock_irqrestore(&dniv_adj_lock, flags);
    schedule_delayed_work(&dniv_age_work, HZ);
}

static void dniv_remove_other_endnode_router_locked(int ifindex,
                                                     __u16 keep_address)
{
    unsigned int i;

    for (i = 0; i < DNIV_MAX_ADJACENCIES; i++) {
        struct dniv_adj_entry *adj = &dniv_adjacencies[i];

        if (adj->used && adj->ifindex == ifindex &&
            adj->address != keep_address &&
            adj->node_type != DNIV_NODE_TYPE_ENDNODE)
            dniv_drop_adj_locked(adj);
    }
}

static void dniv_handle_valid_hello(int ifindex, const __u8 source[ETH_ALEN],
                                    const __u8 destination[ETH_ALEN],
                                    const struct dniv_wire_hello *hello)
{
    struct dniv_adj_entry *adj;
    unsigned long flags;
    bool rejected = false;
    __u8 new_state;

    /* Serialize validation that depends on the local DECnet address with the
     * address publish/adjacency-clear transaction. An in-flight hello must be
     * evaluated wholly against either the old identity or the new one; it
     * must not repopulate an old-identity adjacency after a runtime change.
     */
    spin_lock_irqsave(&dniv_adj_lock, flags);
    if (!dniv_wire_destination_valid(dniv_local_address,
                                     dniv_local_node_type, destination))
        goto out_unlock;
    atomic64_inc(&dniv_hello_rx);
    if (hello->address == dniv_local_address ||
        !dniv_area_compatible(hello->address, hello->node_type))
        goto out_unlock;

    if (dniv_local_node_type == DNIV_NODE_TYPE_ENDNODE) {
        if (!hello->is_router)
            goto out_unlock;
        new_state = DNIV_ADJ_STATE_UP;
    } else if (!hello->is_router) {
        if (!dniv_wire_endnode_test_valid(hello)) {
            atomic64_inc(&dniv_hello_errors);
            adj = dniv_find_adj_locked(ifindex, hello->address);
            dniv_drop_adj_locked(adj);
            goto out_unlock;
        }
        new_state = DNIV_ADJ_STATE_UP;
    } else {
        if (dniv_wire_router_adjacency_state(
                hello, dniv_local_address, dniv_local_priority,
                &new_state) != 0) {
            atomic64_inc(&dniv_hello_errors);
            adj = dniv_find_adj_locked(ifindex, hello->address);
            dniv_drop_adj_locked(adj);
            goto out_unlock;
        }
    }

    if (dniv_local_node_type == DNIV_NODE_TYPE_ENDNODE)
        dniv_remove_other_endnode_router_locked(ifindex, hello->address);

    adj = dniv_find_adj_locked(ifindex, hello->address);
    if (adj && (adj->node_type != hello->node_type ||
                adj->priority != hello->priority)) {
        dniv_drop_adj_locked(adj);
        adj = NULL;
    }
    if (!adj) {
        if (hello->is_router)
            adj = dniv_alloc_router_adj_locked(ifindex, hello->address,
                                               hello->priority, &rejected);
        else
            adj = dniv_alloc_adj_locked();
        if (!adj) {
            if (!rejected)
                atomic64_inc(&dniv_hello_errors);
            goto out_unlock;
        }
        memset(adj, 0, sizeof(*adj));
        adj->used = true;
        adj->ifindex = ifindex;
        adj->address = hello->address;
        adj->node_type = hello->node_type;
        adj->priority = hello->priority;
        ether_addr_copy(adj->mac, source);
    }

    if (adj->state != new_state) {
        if (adj->state == DNIV_ADJ_STATE_UP) {
            dniv_route_withdraw_adjacency(adj->address, adj->ifindex);
            atomic64_inc(&dniv_adjacency_down);
        }
        if (new_state == DNIV_ADJ_STATE_UP)
            atomic64_inc(&dniv_adjacency_up);
        adj->state = new_state;
    }
    adj->block_size = hello->block_size;
    adj->hello_timer = hello->timer ? hello->timer : dniv_hello_interval;
    adj->expires = dniv_listen_expires(hello->timer);
    ether_addr_copy(adj->mac, source);
    dniv_route_refresh_adjacency(adj->address, adj->ifindex, adj->expires);
    dniv_refresh_direct_routes_locked(adj);

out_unlock:
    spin_unlock_irqrestore(&dniv_adj_lock, flags);
}

static int dniv_routing_destination_valid(
    __u8 level, const __u8 destination[ETH_ALEN])
{
    __u8 local_mac[ETH_ALEN];

    dniv_wire_mac_from_address(READ_ONCE(dniv_local_address), local_mac);
    if (ether_addr_equal(destination, local_mac))
        return 1;
    if (level == 1U)
        return ether_addr_equal(destination, dniv_all_routers);
    if (level == 2U)
        return ether_addr_equal(destination, dniv_all_routers) ||
               ether_addr_equal(destination, dniv_all_level2_routers);
    return 0;
}

static int dniv_routing_source_allowed(int ifindex, __u16 source, __u8 level,
                                       unsigned long *expires)
{
    struct dniv_adj_entry *adj;
    unsigned long flags;
    int allowed = 0;

    spin_lock_irqsave(&dniv_adj_lock, flags);
    adj = dniv_find_adj_locked(ifindex, source);
    if (!adj || adj->state != DNIV_ADJ_STATE_UP ||
        adj->node_type == DNIV_NODE_TYPE_ENDNODE)
        goto out;
    if (level == 1U) {
        allowed = DNIV_ADDR_AREA(source) ==
                  DNIV_ADDR_AREA(dniv_local_address);
    } else if (level == 2U) {
        allowed = dniv_local_node_type == DNIV_NODE_TYPE_L2_ROUTER &&
                  adj->node_type == DNIV_NODE_TYPE_L2_ROUTER;
    }
    if (allowed && expires)
        *expires = adj->expires;
out:
    spin_unlock_irqrestore(&dniv_adj_lock, flags);
    return allowed;
}

static void dniv_handle_valid_routing(int ifindex,
                                      unsigned long expires,
                                      const struct dniv_wire_route_message *msg)
{
    struct dniv_wire_route_segment_view seg;
    struct dniv_route_metric metric;
    __u16 local = READ_ONCE(dniv_local_address);
    __u16 si;

    if (!msg)
        return;

    for (si = 0; si < msg->segment_count; si++) {
        __u16 ei;

        if (dniv_wire_route_segment_at(msg, si, &seg) != 0)
            return;
        for (ei = 0; ei < seg.count; ei++) {
            __u16 raw = dniv_wire_route_entry(&seg, ei);
            __u16 destination = (__u16)(seg.start + ei);
            __u16 cost = (__u16)(raw & 0x03ffU);
            __u8 hops = (__u8)(raw >> 10);

            if ((msg->level == 1U &&
                 destination == DNIV_ADDR_NODE(local)) ||
                (msg->level == 2U &&
                 destination == DNIV_ADDR_AREA(local)))
                continue;

            if (cost >= DNIV_ROUTE_INFINITY_COST ||
                hops >= DNIV_ROUTE_INFINITY_HOPS) {
                dniv_route_withdraw(msg->level, destination, msg->source,
                                    ifindex);
                continue;
            }

            if (dniv_route_metric_add(cost, hops, dniv_eth_cost, &metric) != 0) {
                dniv_route_withdraw(msg->level, destination, msg->source,
                                    ifindex);
                continue;
            }
            dniv_route_update(msg->level, destination, msg->source, ifindex,
                              metric.cost, metric.hops, expires);
        }
    }
}


static int dniv_data_source_allowed(int ifindex,
                                    const __u8 source[ETH_ALEN])
{
    struct dniv_adj_entry *adj;
    unsigned long flags;
    __u16 address;
    int allowed = 0;

    if (dniv_wire_address_from_mac(source, &address) != 0)
        return 0;

    spin_lock_irqsave(&dniv_adj_lock, flags);
    adj = dniv_find_adj_locked(ifindex, address);
    if (adj && adj->state == DNIV_ADJ_STATE_UP)
        allowed = 1;
    spin_unlock_irqrestore(&dniv_adj_lock, flags);
    return allowed;
}

static int dniv_xmit_data(struct net_device *dev, __u16 next_hop,
                          const __u8 *payload, __u16 payload_len)
{
    struct sk_buff *skb;
    struct ethhdr *eth;
    __u8 src[ETH_ALEN];
    __u8 dst[ETH_ALEN];
    __u8 *length;
    int ret;

    if (!dev || !payload || payload_len == 0U ||
        payload_len > DNIV_WIRE_BLOCK_SIZE)
        return -EINVAL;

    skb = alloc_skb(LL_RESERVED_SPACE(dev) + ETH_HLEN +
                    DNIV_ETH_LENGTH_LEN + payload_len, GFP_ATOMIC);
    if (!skb)
        return -ENOMEM;

    skb_reserve(skb, LL_RESERVED_SPACE(dev));
    skb_reset_mac_header(skb);
    eth = skb_put(skb, ETH_HLEN);
    dniv_wire_mac_from_address(READ_ONCE(dniv_local_address), src);
    dniv_wire_mac_from_address(next_hop, dst);
    ether_addr_copy(eth->h_dest, dst);
    ether_addr_copy(eth->h_source, src);
    eth->h_proto = cpu_to_be16(ETH_P_DNA_RT);
    length = skb_put(skb, DNIV_ETH_LENGTH_LEN);
    dniv_wire_put_le16(length, payload_len);
    memcpy(skb_put(skb, payload_len), payload, payload_len);
    skb->dev = dev;
    skb->protocol = eth->h_proto;
    skb_set_network_header(skb, ETH_HLEN + DNIV_ETH_LENGTH_LEN);

    ret = dev_queue_xmit(skb);
    return ret == NET_XMIT_SUCCESS || ret == NET_XMIT_CN ? 0 : -EIO;
}

static void dniv_handle_valid_data(int input_ifindex,
                                   const struct dniv_wire_data *data)
{
    struct dniv_wire_data packet;
    struct dniv_route_result route;
    struct net_device *output;
    __u16 local = READ_ONCE(dniv_local_address);
    __u16 destination;
    __u8 level;
    __u8 *payload;
    bool generated_return = false;
    int forwarded_len;

    if (!data || dniv_local_node_type == DNIV_NODE_TYPE_ENDNODE)
        return;

    packet = *data;

retry:
    if (packet.destination == local)
        return;

    if (DNIV_ADDR_AREA(packet.destination) == DNIV_ADDR_AREA(local)) {
        level = 1U;
        destination = DNIV_ADDR_NODE(packet.destination);
    } else if (dniv_local_node_type == DNIV_NODE_TYPE_L2_ROUTER) {
        level = 2U;
        destination = DNIV_ADDR_AREA(packet.destination);
    } else if (dniv_local_node_type == DNIV_NODE_TYPE_L1_ROUTER) {
        level = 1U;
        destination = 0U;
    } else {
        return;
    }

    if (dniv_route_lookup(level, destination, &route) != 0 ||
        route.ifindex <= 0 || route.next_hop == 0U)
        goto return_to_sender;

    output = dev_get_by_index(&init_net, route.ifindex);
    if (!output)
        goto return_to_sender;
    if (output->type != ARPHRD_ETHER || !(output->flags & IFF_UP) ||
        !netif_running(output)) {
        dev_put(output);
        goto return_to_sender;
    }

    if (packet.visit >= dniv_wire_data_visit_limit(&packet)) {
        dev_put(output);
        goto return_to_sender;
    }
    if (packet.payload_len >
        DNIV_WIRE_BLOCK_SIZE - DNIV_WIRE_LONG_DATA_LEN) {
        dev_put(output);
        return;
    }

    payload = kmalloc(DNIV_WIRE_BLOCK_SIZE, GFP_ATOMIC);
    if (!payload) {
        dev_put(output);
        return;
    }
    forwarded_len = dniv_wire_build_forwarded_long(
        payload, DNIV_WIRE_BLOCK_SIZE, &packet,
        generated_return ? 0U :
        dniv_wire_data_forward_ie(&packet,
                                  route.ifindex == input_ifindex ? 1U : 0U));
    if (forwarded_len > 0)
        dniv_xmit_data(output, route.next_hop, payload,
                       (__u16)forwarded_len);
    kfree(payload);
    dev_put(output);
    return;

return_to_sender:
    if (dniv_wire_data_make_return(&packet) == 0) {
        generated_return = true;
        goto retry;
    }
}

static int dniv_packet_rcv(struct sk_buff *skb, struct net_device *dev,
                           struct packet_type *pt, struct net_device *orig_dev)
{
    struct dniv_wire_data data;
    struct dniv_wire_hello hello;
    struct dniv_wire_route_message route;
    struct ethhdr *eth;
    __u8 expected_source[ETH_ALEN];
    __u8 length[DNIV_ETH_LENGTH_LEN];
    __u8 first;
    __u16 payload_len;
    unsigned long route_expires = 0;
    int parsed;

    (void)pt;
    (void)orig_dev;
    if (!net_eq(dev_net(dev), &init_net))
        goto out;
    atomic64_inc(&dniv_rx_frames);
    atomic64_add(skb->len, &dniv_rx_bytes);

    if (skb->len < DNIV_ETH_LENGTH_LEN ||
        skb_copy_bits(skb, 0, length, DNIV_ETH_LENGTH_LEN) != 0)
        goto out;
    payload_len = dniv_wire_get_le16(length);
    if (payload_len == 0 || payload_len > DNIV_WIRE_BLOCK_SIZE ||
        skb->len < (unsigned int)payload_len + DNIV_ETH_LENGTH_LEN)
        goto out;
    if (skb_copy_bits(skb, DNIV_ETH_LENGTH_LEN, &first, 1) != 0)
        goto out;
    if (first != DNIV_WIRE_ROUTER_HELLO &&
        first != DNIV_WIRE_ENDNODE_HELLO &&
        first != DNIV_WIRE_L1_ROUTING &&
        first != DNIV_WIRE_L2_ROUTING &&
        !dniv_wire_is_data_flag(first) && !(first & 0x80U))
        goto out;
    if (!pskb_may_pull(skb, (unsigned int)payload_len + DNIV_ETH_LENGTH_LEN)) {
        atomic64_inc(&dniv_hello_errors);
        goto out;
    }

    eth = eth_hdr(skb);

    parsed = dniv_wire_parse_routing(skb->data + DNIV_ETH_LENGTH_LEN,
                                     payload_len, &route);
    if (parsed == DNIV_WIRE_OK) {
        if (!dniv_wire_address_valid(route.source) ||
            !dniv_routing_destination_valid(route.level, eth->h_dest))
            goto out;
        dniv_wire_mac_from_address(route.source, expected_source);
        if (!ether_addr_equal(eth->h_source, expected_source))
            goto out;
        if (!dniv_routing_source_allowed(dev->ifindex, route.source,
                                         route.level, &route_expires))
            goto out;
        dniv_handle_valid_routing(dev->ifindex, route_expires, &route);
        goto out;
    }
    if (parsed == DNIV_WIRE_MALFORMED)
        goto out;

    parsed = dniv_wire_parse_hello(skb->data + DNIV_ETH_LENGTH_LEN,
                                   payload_len, &hello);
    if (parsed == DNIV_WIRE_OK) {
        dniv_wire_mac_from_address(hello.address, expected_source);
        if (!ether_addr_equal(eth->h_source, expected_source)) {
            atomic64_inc(&dniv_hello_errors);
            goto out;
        }
        dniv_handle_valid_hello(dev->ifindex, eth->h_source, eth->h_dest,
                                &hello);
        goto out;
    }
    if (parsed == DNIV_WIRE_MALFORMED) {
        atomic64_inc(&dniv_hello_errors);
        goto out;
    }

    parsed = dniv_wire_parse_data(skb->data + DNIV_ETH_LENGTH_LEN,
                                  payload_len, &data);
    if (parsed != DNIV_WIRE_OK)
        goto out;
    if (!dniv_data_source_allowed(dev->ifindex, eth->h_source))
        goto out;
    dniv_handle_valid_data(dev->ifindex, &data);

out:
    kfree_skb(skb);
    return NET_RX_SUCCESS;
}

static struct packet_type dniv_packet_type __read_mostly = {
    .type = cpu_to_be16(ETH_P_DNA_RT),
    .func = dniv_packet_rcv,
};

int dniv_eth_init(__u16 address, __u8 node_type, __u8 priority,
                  __u16 hello_interval, __u16 ethernet_cost)
{
    int err;

    dniv_local_address = address;
    dniv_local_node_type = node_type;
    dniv_local_priority = priority;
    dniv_hello_interval = hello_interval;
    dniv_eth_cost = ethernet_cost;
    memset(dniv_adjacencies, 0, sizeof(dniv_adjacencies));
    memset(dniv_dr_states, 0, sizeof(dniv_dr_states));
    dniv_last_route_generation = 0U;
    dniv_last_route_full = 0U;

    err = register_netdevice_notifier_net(&init_net, &dniv_netdev_notifier);
    if (err)
        return err;
    dev_add_pack(&dniv_packet_type);
    schedule_delayed_work(&dniv_hello_work, 0);
    schedule_delayed_work(&dniv_age_work, HZ);
    schedule_delayed_work(&dniv_route_work, HZ);
    return 0;
}

void dniv_eth_exit(void)
{
    cancel_delayed_work_sync(&dniv_hello_work);
    cancel_delayed_work_sync(&dniv_age_work);
    cancel_delayed_work_sync(&dniv_route_work);
    dev_remove_pack(&dniv_packet_type);
    unregister_netdevice_notifier_net(&init_net, &dniv_netdev_notifier);
}

int dniv_eth_set_address(__u16 address)
{
    struct net_device *dev;
    struct net_device *failed_dev = NULL;
    unsigned long flags;
    __u16 old = READ_ONCE(dniv_local_address);
    __u8 old_mac[ETH_ALEN];
    __u8 new_mac[ETH_ALEN];
    int err = 0;

    if (old == address)
        return 0;

    cancel_delayed_work_sync(&dniv_hello_work);
    cancel_delayed_work_sync(&dniv_route_work);
    dniv_wire_mac_from_address(old, old_mac);
    dniv_wire_mac_from_address(address, new_mac);

    rtnl_lock();
    for_each_netdev(&init_net, dev) {
        if (dev->type != ARPHRD_ETHER || (dev->flags & IFF_LOOPBACK))
            continue;
        err = dev_uc_add(dev, new_mac);
        if (err) {
            failed_dev = dev;
            break;
        }
    }
    if (err) {
        for_each_netdev(&init_net, dev) {
            if (dev == failed_dev)
                break;
            if (dev->type != ARPHRD_ETHER || (dev->flags & IFF_LOOPBACK))
                continue;
            dev_uc_del(dev, new_mac);
        }
        rtnl_unlock();
        schedule_delayed_work(&dniv_hello_work, 0);
        schedule_delayed_work(&dniv_route_work, HZ);
        return err;
    }

    spin_lock_irqsave(&dniv_adj_lock, flags);
    dniv_local_address = address;
    dniv_clear_adjacencies_locked();
    dniv_clear_dr_states_locked();
    spin_unlock_irqrestore(&dniv_adj_lock, flags);

    for_each_netdev(&init_net, dev) {
        if (dev->type != ARPHRD_ETHER || (dev->flags & IFF_LOOPBACK))
            continue;
        dev_uc_del(dev, old_mac);
    }
    rtnl_unlock();
    schedule_delayed_work(&dniv_hello_work, 0);
    schedule_delayed_work(&dniv_route_work, HZ);
    return 0;
}

void dniv_eth_get_stats(struct dniv_stats *stats)
{
    stats->uapi_version = DNIV_UAPI_VERSION;
    stats->rx_frames = atomic64_read(&dniv_rx_frames);
    stats->rx_bytes = atomic64_read(&dniv_rx_bytes);
    stats->hello_rx = atomic64_read(&dniv_hello_rx);
    stats->hello_tx = atomic64_read(&dniv_hello_tx);
    stats->hello_errors = atomic64_read(&dniv_hello_errors);
    stats->adjacency_up = atomic64_read(&dniv_adjacency_up);
    stats->adjacency_down = atomic64_read(&dniv_adjacency_down);
}

void dniv_eth_reset_stats(void)
{
    atomic64_set(&dniv_rx_frames, 0);
    atomic64_set(&dniv_rx_bytes, 0);
    atomic64_set(&dniv_hello_rx, 0);
    atomic64_set(&dniv_hello_tx, 0);
    atomic64_set(&dniv_hello_errors, 0);
    atomic64_set(&dniv_adjacency_up, 0);
    atomic64_set(&dniv_adjacency_down, 0);
}

int dniv_eth_get_adjacency(__u32 index, struct dniv_adjacency *out)
{
    unsigned long flags;
    __u32 seen = 0;
    unsigned int i;

    spin_lock_irqsave(&dniv_adj_lock, flags);
    for (i = 0; i < DNIV_MAX_ADJACENCIES; i++) {
        const struct dniv_adj_entry *adj = &dniv_adjacencies[i];

        if (!adj->used)
            continue;
        if (seen++ != index)
            continue;

        memset(out, 0, sizeof(*out));
        out->uapi_version = DNIV_UAPI_VERSION;
        out->index = index;
        out->ifindex = adj->ifindex;
        out->address = adj->address;
        out->node_type = adj->node_type;
        out->state = adj->state;
        out->block_size = adj->block_size;
        out->hello_timer = adj->hello_timer;
        out->priority = adj->priority;
        ether_addr_copy(out->mac, adj->mac);
        if (time_after(adj->expires, jiffies))
            out->expires_ms = jiffies_to_msecs(adj->expires - jiffies);
        spin_unlock_irqrestore(&dniv_adj_lock, flags);
        return 0;
    }
    spin_unlock_irqrestore(&dniv_adj_lock, flags);
    return -ENOENT;
}
