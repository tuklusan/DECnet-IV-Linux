// SPDX-License-Identifier: GPL-2.0
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

#include <decnet_iv_wire.h>
#include "decnet_iv_ethernet.h"

#define DNIV_MAX_ADJACENCIES 64U
#define DNIV_DR_DELAY_SECONDS 5U
#define DNIV_MAX_ROUTING_PAYLOAD 1500U

static const __u8 dniv_all_routers[ETH_ALEN] = {0xab, 0x00, 0x00, 0x03, 0x00, 0x00};
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

static DEFINE_SPINLOCK(dniv_adj_lock);
static struct dniv_adj_entry dniv_adjacencies[DNIV_MAX_ADJACENCIES];
static __u16 dniv_local_address;
static __u16 dniv_hello_interval;
static __u8 dniv_local_node_type;
static __u8 dniv_local_priority;
static unsigned long dniv_started;

static atomic64_t dniv_rx_frames = ATOMIC64_INIT(0);
static atomic64_t dniv_rx_bytes = ATOMIC64_INIT(0);
static atomic64_t dniv_hello_rx = ATOMIC64_INIT(0);
static atomic64_t dniv_hello_tx = ATOMIC64_INIT(0);
static atomic64_t dniv_hello_errors = ATOMIC64_INIT(0);
static atomic64_t dniv_adjacency_up = ATOMIC64_INIT(0);
static atomic64_t dniv_adjacency_down = ATOMIC64_INIT(0);

static void dniv_hello_workfn(struct work_struct *work);
static void dniv_age_workfn(struct work_struct *work);
static DECLARE_DELAYED_WORK(dniv_hello_work, dniv_hello_workfn);
static DECLARE_DELAYED_WORK(dniv_age_work, dniv_age_workfn);

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

static void dniv_drop_adj_locked(struct dniv_adj_entry *adj)
{
    if (!adj || !adj->used)
        return;
    if (adj->state == DNIV_ADJ_STATE_UP)
        atomic64_inc(&dniv_adjacency_down);
    memset(adj, 0, sizeof(*adj));
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
    const __u8 *group;
    int err;

    if (dev->type != ARPHRD_ETHER || (dev->flags & IFF_LOOPBACK))
        return 0;

    dniv_wire_mac_from_address(READ_ONCE(dniv_local_address), local_mac);
    if (!ether_addr_equal(local_mac, dev->dev_addr)) {
        err = dev_uc_add(dev, local_mac);
        if (err)
            return err;
    }

    group = dniv_local_node_type == DNIV_NODE_TYPE_ENDNODE ?
            dniv_all_endnodes : dniv_all_routers;
    err = dev_mc_add(dev, group);
    if (err && !ether_addr_equal(local_mac, dev->dev_addr))
        dev_uc_del(dev, local_mac);
    return err;
}

static void dniv_remove_dev_filters(struct net_device *dev, __u16 address)
{
    __u8 local_mac[ETH_ALEN];
    const __u8 *group;

    if (dev->type != ARPHRD_ETHER || (dev->flags & IFF_LOOPBACK))
        return;

    dniv_wire_mac_from_address(address, local_mac);
    if (!ether_addr_equal(local_mac, dev->dev_addr))
        dev_uc_del(dev, local_mac);
    group = dniv_local_node_type == DNIV_NODE_TYPE_ENDNODE ?
            dniv_all_endnodes : dniv_all_routers;
    dev_mc_del(dev, group);
}

static int dniv_netdev_event(struct notifier_block *nb, unsigned long event,
                             void *ptr)
{
    struct net_device *dev = netdev_notifier_info_to_dev(ptr);
    unsigned long flags;
    int err;

    (void)nb;
    if (event == NETDEV_UNREGISTER) {
        dniv_remove_dev_filters(dev, READ_ONCE(dniv_local_address));
        spin_lock_irqsave(&dniv_adj_lock, flags);
        dniv_drop_if_adjacencies_locked(dev->ifindex);
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

static int dniv_xmit_hello(struct net_device *dev, const __u8 dst[ETH_ALEN],
                           const __u8 *payload, unsigned int payload_len)
{
    struct sk_buff *skb;
    struct ethhdr *eth;
    __u8 src[ETH_ALEN];
    int ret;

    skb = alloc_skb(LL_RESERVED_SPACE(dev) + ETH_HLEN + payload_len,
                    GFP_KERNEL);
    if (!skb)
        return -ENOMEM;

    skb_reserve(skb, LL_RESERVED_SPACE(dev));
    skb_reset_mac_header(skb);
    eth = skb_put(skb, ETH_HLEN);
    dniv_wire_mac_from_address(READ_ONCE(dniv_local_address), src);
    ether_addr_copy(eth->h_dest, dst);
    ether_addr_copy(eth->h_source, src);
    eth->h_proto = cpu_to_be16(ETH_P_DNA_RT);
    memcpy(skb_put(skb, payload_len), payload, payload_len);
    skb->dev = dev;
    skb->protocol = eth->h_proto;
    skb_set_network_header(skb, ETH_HLEN);

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
    unsigned long flags;
    __u16 local = READ_ONCE(dniv_local_address);
    __u16 local_area = DNIV_ADDR_AREA(local);
    bool best = true;
    unsigned int i;

    if (time_before(jiffies, dniv_started + DNIV_DR_DELAY_SECONDS * HZ))
        return false;

    spin_lock_irqsave(&dniv_adj_lock, flags);
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
    spin_unlock_irqrestore(&dniv_adj_lock, flags);
    return best;
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
                                    const struct dniv_wire_hello *hello)
{
    struct dniv_adj_entry *adj;
    unsigned long flags;
    bool rejected = false;
    __u8 new_state;

    if (hello->address == READ_ONCE(dniv_local_address) ||
        !dniv_area_compatible(hello->address, hello->node_type))
        return;

    if (dniv_local_node_type == DNIV_NODE_TYPE_ENDNODE) {
        if (!hello->is_router)
            return;
        new_state = DNIV_ADJ_STATE_UP;
    } else if (!hello->is_router) {
        if (!dniv_wire_endnode_test_valid(hello)) {
            atomic64_inc(&dniv_hello_errors);
            spin_lock_irqsave(&dniv_adj_lock, flags);
            adj = dniv_find_adj_locked(ifindex, hello->address);
            dniv_drop_adj_locked(adj);
            spin_unlock_irqrestore(&dniv_adj_lock, flags);
            return;
        }
        new_state = DNIV_ADJ_STATE_UP;
    } else {
        if (dniv_wire_router_adjacency_state(
                hello, READ_ONCE(dniv_local_address), dniv_local_priority,
                &new_state) != 0) {
            atomic64_inc(&dniv_hello_errors);
            spin_lock_irqsave(&dniv_adj_lock, flags);
            adj = dniv_find_adj_locked(ifindex, hello->address);
            dniv_drop_adj_locked(adj);
            spin_unlock_irqrestore(&dniv_adj_lock, flags);
            return;
        }
    }

    spin_lock_irqsave(&dniv_adj_lock, flags);
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
            spin_unlock_irqrestore(&dniv_adj_lock, flags);
            if (!rejected)
                atomic64_inc(&dniv_hello_errors);
            return;
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
        if (adj->state == DNIV_ADJ_STATE_UP)
            atomic64_inc(&dniv_adjacency_down);
        if (new_state == DNIV_ADJ_STATE_UP)
            atomic64_inc(&dniv_adjacency_up);
        adj->state = new_state;
    }
    adj->block_size = hello->block_size;
    adj->hello_timer = hello->timer ? hello->timer : dniv_hello_interval;
    adj->expires = dniv_listen_expires(hello->timer);
    ether_addr_copy(adj->mac, source);
    spin_unlock_irqrestore(&dniv_adj_lock, flags);
}

static int dniv_packet_rcv(struct sk_buff *skb, struct net_device *dev,
                           struct packet_type *pt, struct net_device *orig_dev)
{
    struct dniv_wire_hello hello;
    struct ethhdr *eth;
    __u8 expected_source[ETH_ALEN];
    __u8 first;
    int parsed;

    (void)pt;
    (void)orig_dev;
    atomic64_inc(&dniv_rx_frames);
    atomic64_add(skb->len, &dniv_rx_bytes);

    if (skb->len == 0 || skb_copy_bits(skb, 0, &first, 1) != 0)
        goto out;
    if (first != DNIV_WIRE_ROUTER_HELLO &&
        first != DNIV_WIRE_ENDNODE_HELLO && !(first & 0x80U))
        goto out;
    if (skb->len > DNIV_MAX_ROUTING_PAYLOAD || !pskb_may_pull(skb, skb->len)) {
        atomic64_inc(&dniv_hello_errors);
        goto out;
    }

    parsed = dniv_wire_parse_hello(skb->data, skb->len, &hello);
    if (parsed == DNIV_WIRE_NOT_HELLO)
        goto out;
    if (parsed != DNIV_WIRE_OK) {
        atomic64_inc(&dniv_hello_errors);
        goto out;
    }

    eth = eth_hdr(skb);
    dniv_wire_mac_from_address(hello.address, expected_source);
    if (!ether_addr_equal(eth->h_source, expected_source)) {
        atomic64_inc(&dniv_hello_errors);
        goto out;
    }

    atomic64_inc(&dniv_hello_rx);
    dniv_handle_valid_hello(dev->ifindex, eth->h_source, &hello);

out:
    kfree_skb(skb);
    return NET_RX_SUCCESS;
}

static struct packet_type dniv_packet_type __read_mostly = {
    .type = cpu_to_be16(ETH_P_DNA_RT),
    .func = dniv_packet_rcv,
};

int dniv_eth_init(__u16 address, __u8 node_type, __u8 priority,
                  __u16 hello_interval)
{
    int err;

    dniv_local_address = address;
    dniv_local_node_type = node_type;
    dniv_local_priority = priority;
    dniv_hello_interval = hello_interval;
    dniv_started = jiffies;
    memset(dniv_adjacencies, 0, sizeof(dniv_adjacencies));

    err = register_netdevice_notifier_net(&init_net, &dniv_netdev_notifier);
    if (err)
        return err;
    dev_add_pack(&dniv_packet_type);
    schedule_delayed_work(&dniv_hello_work, 0);
    schedule_delayed_work(&dniv_age_work, HZ);
    return 0;
}

void dniv_eth_exit(void)
{
    cancel_delayed_work_sync(&dniv_hello_work);
    cancel_delayed_work_sync(&dniv_age_work);
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
    dniv_wire_mac_from_address(old, old_mac);
    dniv_wire_mac_from_address(address, new_mac);

    /* Install every new receive filter before publishing the new address. */
    rtnl_lock();
    for_each_netdev(&init_net, dev) {
        if (dev->type != ARPHRD_ETHER || (dev->flags & IFF_LOOPBACK) ||
            ether_addr_equal(new_mac, dev->dev_addr))
            continue;
        err = dev_uc_add(dev, new_mac);
        if (err) {
            failed_dev = dev;
            break;
        }
    }
    if (err) {
        /* Netdevice iteration order is stable while RTNL is held. */
        for_each_netdev(&init_net, dev) {
            if (dev == failed_dev)
                break;
            if (dev->type != ARPHRD_ETHER || (dev->flags & IFF_LOOPBACK) ||
                ether_addr_equal(new_mac, dev->dev_addr))
                continue;
            dev_uc_del(dev, new_mac);
        }
        rtnl_unlock();
        schedule_delayed_work(&dniv_hello_work, 0);
        return err;
    }

    spin_lock_irqsave(&dniv_adj_lock, flags);
    dniv_local_address = address;
    dniv_started = jiffies;
    dniv_clear_adjacencies_locked();
    spin_unlock_irqrestore(&dniv_adj_lock, flags);

    for_each_netdev(&init_net, dev) {
        if (dev->type != ARPHRD_ETHER || (dev->flags & IFF_LOOPBACK))
            continue;
        if (!ether_addr_equal(old_mac, dev->dev_addr))
            dev_uc_del(dev, old_mac);
    }
    rtnl_unlock();
    schedule_delayed_work(&dniv_hello_work, 0);
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
