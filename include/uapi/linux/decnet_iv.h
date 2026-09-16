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

#ifndef _UAPI_LINUX_DECNET_IV_H
#define _UAPI_LINUX_DECNET_IV_H

#include <linux/ioctl.h>
#include <linux/types.h>

#define DNIV_UAPI_VERSION 2U
#define DNIV_NODE_NAME_MAX 6U
#define DNIV_NODE_NAME_BUFSZ (DNIV_NODE_NAME_MAX + 1U)

#define DNIV_ADDR(area, node) \
    ((__u16)((((__u16)(area) & 0x3fU) << 10) | ((__u16)(node) & 0x03ffU)))
#define DNIV_ADDR_AREA(address) (((__u16)(address) >> 10) & 0x3fU)
#define DNIV_ADDR_NODE(address) ((__u16)(address) & 0x03ffU)

#define DNIV_NODE_TYPE_L2_ROUTER 1U
#define DNIV_NODE_TYPE_L1_ROUTER 2U
#define DNIV_NODE_TYPE_ENDNODE 3U

#define DNIV_ADJ_STATE_INIT 1U
#define DNIV_ADJ_STATE_UP 2U

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
    __u64 hello_rx;
    __u64 hello_tx;
    __u64 hello_errors;
    __u64 adjacency_up;
    __u64 adjacency_down;
};

struct dniv_adjacency {
    __u32 uapi_version;
    __u32 index;
    __s32 ifindex;
    __u16 address;
    __u8 node_type;
    __u8 state;
    __u16 block_size;
    __u16 hello_timer;
    __u8 priority;
    __u8 reserved0;
    __u8 mac[6];
    __u32 expires_ms;
};

#define DNIV_IOC_MAGIC 0xd4
#define DNIV_IOC_GET_IDENTITY _IOR(DNIV_IOC_MAGIC, 0x00, struct dniv_identity)
#define DNIV_IOC_SET_IDENTITY _IOW(DNIV_IOC_MAGIC, 0x01, struct dniv_identity)
#define DNIV_IOC_GET_STATS _IOR(DNIV_IOC_MAGIC, 0x02, struct dniv_stats)
#define DNIV_IOC_RESET_STATS _IO(DNIV_IOC_MAGIC, 0x03)
#define DNIV_IOC_GET_ADJACENCY _IOWR(DNIV_IOC_MAGIC, 0x04, struct dniv_adjacency)

#endif /* _UAPI_LINUX_DECNET_IV_H */
