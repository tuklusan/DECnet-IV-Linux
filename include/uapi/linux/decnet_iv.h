/* SPDX-License-Identifier: GPL-2.0 WITH Linux-syscall-note */
#ifndef _UAPI_LINUX_DECNET_IV_H
#define _UAPI_LINUX_DECNET_IV_H

#include <linux/ioctl.h>
#include <linux/types.h>

#define DNIV_UAPI_VERSION 1U
#define DNIV_NODE_NAME_MAX 6U
#define DNIV_NODE_NAME_BUFSZ (DNIV_NODE_NAME_MAX + 1U)

#define DNIV_ADDR(area, node) \
    ((__u16)((((__u16)(area) & 0x3fU) << 10) | ((__u16)(node) & 0x03ffU)))
#define DNIV_ADDR_AREA(address) (((__u16)(address) >> 10) & 0x3fU)
#define DNIV_ADDR_NODE(address) ((__u16)(address) & 0x03ffU)

struct dniv_identity {
    __u32 uapi_version;
    __u16 address;
    __u16 reserved0;
    char name[DNIV_NODE_NAME_BUFSZ];
    __u8 reserved1;
};

struct dniv_stats {
    __u32 uapi_version;
    __u32 reserved0;
    __u64 rx_frames;
    __u64 rx_bytes;
};

#define DNIV_IOC_MAGIC 0xd4
#define DNIV_IOC_GET_IDENTITY _IOR(DNIV_IOC_MAGIC, 0x00, struct dniv_identity)
#define DNIV_IOC_SET_IDENTITY _IOW(DNIV_IOC_MAGIC, 0x01, struct dniv_identity)
#define DNIV_IOC_GET_STATS _IOR(DNIV_IOC_MAGIC, 0x02, struct dniv_stats)
#define DNIV_IOC_RESET_STATS _IO(DNIV_IOC_MAGIC, 0x03)

#endif /* _UAPI_LINUX_DECNET_IV_H */
