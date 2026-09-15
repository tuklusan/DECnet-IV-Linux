// SPDX-License-Identifier: GPL-2.0
#include <linux/atomic.h>
#include <linux/capability.h>
#include <linux/ctype.h>
#include <linux/fs.h>
#include <linux/if_ether.h>
#include <linux/miscdevice.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/netdevice.h>
#include <linux/skbuff.h>
#include <linux/string.h>
#include <linux/uaccess.h>

#include <linux/decnet_iv.h>

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

static DEFINE_MUTEX(dniv_identity_lock);
static struct dniv_identity dniv_identity;
static atomic64_t dniv_rx_frames = ATOMIC64_INIT(0);
static atomic64_t dniv_rx_bytes = ATOMIC64_INIT(0);

static bool dniv_address_valid(__u16 address)
{
    __u16 area = DNIV_ADDR_AREA(address);
    __u16 node = DNIV_ADDR_NODE(address);

    return area >= 1 && area <= 63 && node >= 1 && node <= 1023;
}

static bool dniv_name_valid(const char *name)
{
    size_t len = strnlen(name, DNIV_NODE_NAME_BUFSZ);
    size_t i;

    if (len == 0 || len > DNIV_NODE_NAME_MAX)
        return false;

    for (i = 0; i < len; i++) {
        if (!isalnum(name[i]))
            return false;
    }

    return true;
}

static void dniv_identity_normalize(struct dniv_identity *identity)
{
    size_t i;

    identity->uapi_version = DNIV_UAPI_VERSION;
    identity->reserved0 = 0;
    identity->reserved1 = 0;
    identity->name[DNIV_NODE_NAME_MAX] = '\0';

    for (i = 0; identity->name[i] != '\0'; i++)
        identity->name[i] = toupper(identity->name[i]);
}

static long dniv_ioctl(struct file *file, unsigned int cmd, unsigned long arg)
{
    struct dniv_identity identity;
    struct dniv_stats stats;

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
        identity.name[DNIV_NODE_NAME_MAX] = '\0';
        if (!dniv_address_valid(identity.address) || !dniv_name_valid(identity.name))
            return -EINVAL;
        dniv_identity_normalize(&identity);
        mutex_lock(&dniv_identity_lock);
        dniv_identity = identity;
        mutex_unlock(&dniv_identity_lock);
        return 0;

    case DNIV_IOC_GET_STATS:
        memset(&stats, 0, sizeof(stats));
        stats.uapi_version = DNIV_UAPI_VERSION;
        stats.rx_frames = atomic64_read(&dniv_rx_frames);
        stats.rx_bytes = atomic64_read(&dniv_rx_bytes);
        if (copy_to_user((void __user *)arg, &stats, sizeof(stats)))
            return -EFAULT;
        return 0;

    case DNIV_IOC_RESET_STATS:
        if (!capable(CAP_NET_ADMIN))
            return -EPERM;
        atomic64_set(&dniv_rx_frames, 0);
        atomic64_set(&dniv_rx_bytes, 0);
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

static int dniv_packet_rcv(struct sk_buff *skb, struct net_device *dev,
                           struct packet_type *pt, struct net_device *orig_dev)
{
    atomic64_inc(&dniv_rx_frames);
    atomic64_add(skb->len, &dniv_rx_bytes);
    kfree_skb(skb);
    return NET_RX_SUCCESS;
}

static struct packet_type dniv_packet_type __read_mostly = {
    .type = cpu_to_be16(ETH_P_DNA_RT),
    .func = dniv_packet_rcv,
};

static int __init dniv_init(void)
{
    int err;

    memset(&dniv_identity, 0, sizeof(dniv_identity));
    dniv_identity.uapi_version = DNIV_UAPI_VERSION;
    dniv_identity.address = DNIV_ADDR(default_area, default_node);
    strscpy(dniv_identity.name, default_name, sizeof(dniv_identity.name));
    dniv_identity_normalize(&dniv_identity);

    if (!dniv_address_valid(dniv_identity.address) || !dniv_name_valid(dniv_identity.name)) {
        pr_err("decnet_iv: invalid default identity\n");
        return -EINVAL;
    }

    err = misc_register(&dniv_miscdev);
    if (err)
        return err;

    dev_add_pack(&dniv_packet_type);
    pr_info("decnet_iv: loaded as %u.%u (%s), UAPI %u\n",
            DNIV_ADDR_AREA(dniv_identity.address),
            DNIV_ADDR_NODE(dniv_identity.address),
            dniv_identity.name, DNIV_UAPI_VERSION);
    return 0;
}

static void __exit dniv_exit(void)
{
    dev_remove_pack(&dniv_packet_type);
    misc_deregister(&dniv_miscdev);
    pr_info("decnet_iv: unloaded\n");
}

module_init(dniv_init);
module_exit(dniv_exit);

MODULE_DESCRIPTION("DECnet Phase IV networking bootstrap");
MODULE_LICENSE("GPL");
MODULE_ALIAS_NETPROTO(PF_DECnet);
