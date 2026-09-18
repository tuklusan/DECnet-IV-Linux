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

#include <linux/capability.h>
#include <linux/ctype.h>
#include <linux/fs.h>
#include <linux/miscdevice.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/net.h>
#include <linux/string.h>
#include <linux/uaccess.h>

#include <linux/decnet_iv.h>
#include <decnet_iv_route_metric.h>
#include <decnet_iv_wire.h>
#include "decnet_iv_ethernet.h"
#include "decnet_iv_nsp.h"
#include "decnet_iv_route.h"

#define DNIV_DEVICE_NAME "decnet_iv"

static unsigned short default_area = 31;
module_param(default_area, ushort, 0444);
MODULE_PARM_DESC(default_area, "default DECnet area (1-63)");

static unsigned short default_node = 70;
module_param(default_node, ushort, 0444);
MODULE_PARM_DESC(default_node, "default DECnet node (1-1023)");

static char *default_name = "DN70";
module_param(default_name, charp, 0444);
MODULE_PARM_DESC(default_name, "default DECnet node name (1-6 alphanumeric characters)");

static unsigned short default_node_type = DNIV_NODE_TYPE_L1_ROUTER;
module_param(default_node_type, ushort, 0444);
MODULE_PARM_DESC(default_node_type, "DECnet node type (1=L2 router, 2=L1 router, 3=endnode)");

static unsigned short router_priority = 64;
module_param(router_priority, ushort, 0444);
MODULE_PARM_DESC(router_priority, "DECnet Ethernet router priority (0-127)");

static unsigned short hello_interval = 10;
module_param(hello_interval, ushort, 0444);
MODULE_PARM_DESC(hello_interval, "DECnet Ethernet hello interval in seconds (1-65535)");

static unsigned short ethernet_cost = 4;
module_param(ethernet_cost, ushort, 0444);
MODULE_PARM_DESC(ethernet_cost, "DECnet Ethernet circuit cost (1-1022)");

static DEFINE_MUTEX(dniv_identity_lock);
static struct dniv_identity dniv_identity;

static bool dniv_address_valid(__u16 address)
{
    return dniv_wire_address_valid(address);
}

static bool dniv_name_valid(const char *name)
{
    size_t len;
    size_t i;

    if (!name)
        return false;

    len = strnlen(name, DNIV_NODE_NAME_BUFSZ);
    if (len == 0 || len > DNIV_NODE_NAME_MAX)
        return false;

    for (i = 0; i < len; i++) {
        if (!isalnum((unsigned char)name[i]))
            return false;
    }

    return true;
}

static void dniv_identity_normalize(struct dniv_identity *identity)
{
    size_t len;
    size_t i;

    identity->uapi_version = DNIV_UAPI_VERSION;
    identity->reserved0 = 0;
    identity->reserved1 = 0;
    identity->name[DNIV_NODE_NAME_MAX] = '\0';
    len = strnlen(identity->name, DNIV_NODE_NAME_BUFSZ);

    for (i = 0; i < len; i++)
        identity->name[i] = toupper((unsigned char)identity->name[i]);
    memset(identity->name + len, 0, sizeof(identity->name) - len);
}

static long dniv_ioctl(struct file *file, unsigned int cmd, unsigned long arg)
{
    struct dniv_adjacency adjacency;
    struct dniv_identity identity;
    struct dniv_stats stats;
    int err;

    (void)file;
    switch (cmd) {
    case DNIV_IOC_GET_IDENTITY:
        mutex_lock(&dniv_identity_lock);
        identity = dniv_identity;
        mutex_unlock(&dniv_identity_lock);
        if (copy_to_user((void __user *)arg, &identity, sizeof(identity)))
            return -EFAULT;
        return 0;

    case DNIV_IOC_SET_IDENTITY:
        if (!capable(CAP_NET_ADMIN))
            return -EPERM;
        if (copy_from_user(&identity, (void __user *)arg, sizeof(identity)))
            return -EFAULT;
        if (identity.uapi_version != DNIV_UAPI_VERSION)
            return -EPROTO;
        if (!dniv_address_valid(identity.address) || !dniv_name_valid(identity.name))
            return -EINVAL;
        dniv_identity_normalize(&identity);
        mutex_lock(&dniv_identity_lock);
        err = dniv_eth_set_address(identity.address);
        if (!err) {
            dniv_route_reset();
            dniv_nsp_reset();
            dniv_identity = identity;
        }
        mutex_unlock(&dniv_identity_lock);
        return err;

    case DNIV_IOC_GET_STATS:
        memset(&stats, 0, sizeof(stats));
        dniv_eth_get_stats(&stats);
        if (copy_to_user((void __user *)arg, &stats, sizeof(stats)))
            return -EFAULT;
        return 0;

    case DNIV_IOC_RESET_STATS:
        if (!capable(CAP_NET_ADMIN))
            return -EPERM;
        dniv_eth_reset_stats();
        return 0;

    case DNIV_IOC_GET_ADJACENCY:
        if (copy_from_user(&adjacency, (void __user *)arg, sizeof(adjacency)))
            return -EFAULT;
        if (adjacency.uapi_version != DNIV_UAPI_VERSION)
            return -EPROTO;
        err = dniv_eth_get_adjacency(adjacency.index, &adjacency);
        if (err)
            return err;
        if (copy_to_user((void __user *)arg, &adjacency, sizeof(adjacency)))
            return -EFAULT;
        return 0;

    default:
        return -ENOTTY;
    }
}

static const struct file_operations dniv_fops = {
    .owner = THIS_MODULE,
    .unlocked_ioctl = dniv_ioctl,
#ifdef CONFIG_COMPAT
    .compat_ioctl = dniv_ioctl,
#endif
};

static struct miscdevice dniv_miscdev = {
    .minor = MISC_DYNAMIC_MINOR,
    .name = DNIV_DEVICE_NAME,
    .fops = &dniv_fops,
    .mode = 0600,
};

static int __init dniv_init(void)
{
    int err;

    if (default_area < 1 || default_area > 63 ||
        default_node < 1 || default_node > 1023 ||
        !dniv_name_valid(default_name) ||
        !dniv_wire_node_type_valid(default_node_type) ||
        router_priority > 127 || hello_interval == 0 ||
        ethernet_cost == 0 || ethernet_cost > DNIV_ROUTE_MAX_COST) {
        pr_err("decnet_iv: invalid default configuration\n");
        return -EINVAL;
    }

    memset(&dniv_identity, 0, sizeof(dniv_identity));
    dniv_identity.uapi_version = DNIV_UAPI_VERSION;
    dniv_identity.address = DNIV_ADDR(default_area, default_node);
    strscpy(dniv_identity.name, default_name, sizeof(dniv_identity.name));
    dniv_identity_normalize(&dniv_identity);

    err = misc_register(&dniv_miscdev);
    if (err)
        return err;

    err = dniv_route_init();
    if (err) {
        misc_deregister(&dniv_miscdev);
        return err;
    }

    err = dniv_nsp_init();
    if (err) {
        dniv_route_exit();
        misc_deregister(&dniv_miscdev);
        return err;
    }

    err = dniv_eth_init(dniv_identity.address, (__u8)default_node_type,
                        (__u8)router_priority, (__u16)hello_interval,
                        (__u16)ethernet_cost);
    if (err) {
        dniv_nsp_exit();
        dniv_route_exit();
        misc_deregister(&dniv_miscdev);
        return err;
    }

    pr_info("decnet_iv: loaded as %u.%u (%s), type %u, UAPI %u\n",
            DNIV_ADDR_AREA(dniv_identity.address),
            DNIV_ADDR_NODE(dniv_identity.address), dniv_identity.name,
            default_node_type, DNIV_UAPI_VERSION);
    return 0;
}

static void __exit dniv_exit(void)
{
    dniv_eth_exit();
    dniv_nsp_exit();
    dniv_route_exit();
    misc_deregister(&dniv_miscdev);
    pr_info("decnet_iv: unloaded\n");
}

module_init(dniv_init);
module_exit(dniv_exit);

MODULE_DESCRIPTION("DECnet Phase IV native Ethernet initialization");
MODULE_LICENSE("Proprietary");
MODULE_ALIAS_NETPROTO(PF_DECnet);
