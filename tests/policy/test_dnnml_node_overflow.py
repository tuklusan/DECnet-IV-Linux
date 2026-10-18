#!/usr/bin/env python3
# ============================================================================
# Copyright (c) 2026 Supratim Sanyal of SANYALnet Labs.
# Proprietary rights reserved except as expressly licensed herein.
#
# DECnet-IV-Linux
# This file is governed by the SANYALnet Labs Non-Commercial License in the
# root LICENSE file. Non-Commercial use is permitted; Commercial Use and use
# for AI/ML model training are prohibited unless separately authorized.
#
# Attribution is required: "Based on original work by Supratim Sanyal of
# SANYALnet Labs." See LICENSE for full terms, warranty disclaimer, termination,
# patent, trademark, and governing-law provisions.
# ============================================================================

"""Compile real DNNML collector: excess distinct nodes must reject, never truncate."""

import os
from pathlib import Path
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "userspace/dnnml/dnnml.c"
PREFIX = r"""
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <stdarg.h>
typedef uint8_t __u8;
typedef int8_t __s8;
typedef uint16_t __u16;
typedef uint32_t __u32;
#define DNIV_UAPI_VERSION 2U
#define DNIV_ADJ_STATE_UP 2U
#define DNIV_ADDR(a,n) ((__u16)((((a)&63)<<10)|((n)&1023)))
#define DNIV_ADDR_AREA(a) (((a)>>10)&63)
#define DNIV_DEVICE "/dev/decnet_iv"
#define DNIV_IOC_GET_ADJACENCY 1
#define DNIV_IOC_GET_ROUTE 2
#define O_RDONLY 0
struct dniv_adjacency {
    __u32 uapi_version, index;
    int ifindex;
    __u16 address;
    __u8 state;
};
struct dniv_route {
    __u32 uapi_version, index;
    int ifindex;
    __u16 destination, next_hop, cost;
    __u8 level, hops;
};
static __u32 route_limit;
static int open(const char *p,int f) { (void)p; (void)f; return 4; }
static int close(int fd) { (void)fd; return 0; }
static int ioctl(int fd,unsigned long req,...) {
    va_list ap;
    void *ptr;
    (void)fd;
    va_start(ap,req);
    ptr=va_arg(ap,void*);
    va_end(ap);
    if (req == DNIV_IOC_GET_ADJACENCY) {
        struct dniv_adjacency *p=ptr;
        if (p->index != 0U) { errno=ENOENT; return -1; }
        p->address=DNIV_ADDR(31,71);
        p->ifindex=5;
        p->state=DNIV_ADJ_STATE_UP;
        return 0;
    }
    if (req == DNIV_IOC_GET_ROUTE) {
        struct dniv_route *p=ptr;
        if (p->index>=route_limit) { errno=ENOENT; return -1; }
        p->destination=(__u16)(p->index+1U);
        p->next_hop=DNIV_ADDR(31,71);
        p->level=1U;
        p->ifindex=5;
        return 0;
    }
    return -1;
}
static int read_node_state(__u16 address, __u8 *node_type,
                           __u16 *cost, __u8 *hops, char *circuit,
                           size_t circuit_size, __u16 *next_node) {
    (void)address;
    *node_type=4U;
    *cost=2U;
    *hops=2U;
    *next_node=DNIV_ADDR(31,71);
    if (circuit_size<6U) return -1;
    memcpy(circuit,"ETH-0",6U);
    return 0;
}
"""
SUFFIX = r"""
int main(void) {
    struct dniv_nml_node_status nodes[256];
    size_t count=0U;
    route_limit=255U;
    if (collect_node_status(-1,nodes,256,&count) || count!=255U) return 1;
    route_limit=256U;
    if (collect_node_status(-1,nodes,256,&count) || count!=256U) return 2;
    route_limit=257U;
    if (collect_node_status(-1,nodes,256,&count) == 0) return 3;
    if (collect_node_status(-4,nodes,256,&count) || count!=1U) return 4;
    return 0;
}
"""


def main() -> None:
    text = SOURCE.read_text(encoding="utf-8")
    start = text.index("struct dniv_nml_node_status {")
    end = text.index("\nstatic int send_nice_code(", start)
    fragment = text[start:end]
    with tempfile.TemporaryDirectory(prefix="dniv-nml-overflow-") as tmp:
        path = Path(tmp)
        c_file = path / "check.c"
        binary = path / "check"
        c_file.write_text(PREFIX + fragment + SUFFIX, encoding="utf-8")
        subprocess.run(shlex.split(os.environ.get("CC", "cc")) + [
            "-std=c11", "-Wall", "-Wextra", "-Werror",
            str(c_file), "-o", str(binary)
        ], check=True, timeout=60)
        result = subprocess.run([str(binary)], capture_output=True,
                                text=True, timeout=10)
        if result.returncode:
            raise AssertionError(
                f"NML accepted silently truncated source enumeration: "
                f"status={result.returncode} stderr={result.stderr!r}"
            )
    print("NML rejects 257 distinct nodes rather than claiming a complete 256-node reply")


if __name__ == "__main__":
    main()
