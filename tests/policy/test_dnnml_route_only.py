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

"""Compile actual dnnml read_node_state: routed nodes need a live router next hop."""

import os
from pathlib import Path
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "userspace/dnnml/dnnml.c"
PREFIX = r"""
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <stdarg.h>
#include <stddef.h>
typedef uint16_t __u16;
typedef uint8_t __u8;
typedef uint32_t __u32;
typedef int32_t __s32;
#define DNIV_UAPI_VERSION 2U
#define DNIV_ADJ_STATE_UP 2U
#define DNIV_ADJ_STATE_INIT 1U
#define DNIV_NODE_TYPE_L2_ROUTER 1U
#define DNIV_NODE_TYPE_L1_ROUTER 2U
#define DNIV_NODE_TYPE_ENDNODE 3U
#define DNIV_ADDR(area,node) ((uint16_t)(((area)<<10)|(node)))
#define DNIV_ADDR_AREA(x) (((x)>>10)&63)
#define DNIV_ADDR_NODE(x) ((x)&1023)
#define DNIV_DEVICE "/dev/decnet_iv"
#define DNIV_IOC_GET_ADJACENCY 1
#define DNIV_IOC_GET_ROUTE 2
#define O_RDONLY 0
struct dniv_adjacency {
    __u32 uapi_version, index;
    __s32 ifindex;
    __u16 address;
    __u8 state, node_type;
};
struct dniv_route {
    __u32 uapi_version, index;
    __s32 ifindex;
    __u16 destination, next_hop, cost;
    __u8 level, hops;
};
static const struct dniv_adjacency adjs[] = {
    { .ifindex=5, .address=DNIV_ADDR(31,71), .state=DNIV_ADJ_STATE_UP,
      .node_type=DNIV_NODE_TYPE_L1_ROUTER },
    { .ifindex=6, .address=DNIV_ADDR(31,73), .state=DNIV_ADJ_STATE_UP,
      .node_type=DNIV_NODE_TYPE_ENDNODE },
    { .ifindex=7, .address=DNIV_ADDR(31,70), .state=DNIV_ADJ_STATE_INIT,
      .node_type=DNIV_NODE_TYPE_L1_ROUTER },
};
static const struct dniv_route routes[] = {
    { .level=1, .destination=72, .next_hop=DNIV_ADDR(31,71),
      .ifindex=5, .cost=3, .hops=2 },
    { .level=1, .destination=74, .next_hop=DNIV_ADDR(31,71),
      .ifindex=9, .cost=3, .hops=2 },
    { .level=1, .destination=76, .next_hop=DNIV_ADDR(31,70),
      .ifindex=7, .cost=3, .hops=2 },
    { .level=2, .destination=32, .next_hop=DNIV_ADDR(31,71),
      .ifindex=5, .cost=8, .hops=4 },
};
static int open(const char *p,int f) { (void)p; (void)f; return 3; }
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
        __u32 index=p->index;
        if (index>=sizeof(adjs)/sizeof(adjs[0])) {
            errno=ENOENT;
            return -1;
        }
        *p=adjs[index];
        p->index=index;
        p->uapi_version=DNIV_UAPI_VERSION;
        return 0;
    }
    if (req == DNIV_IOC_GET_ROUTE) {
        struct dniv_route *p=ptr;
        __u32 index=p->index;
        if (index>=sizeof(routes)/sizeof(routes[0])) {
            errno=ENOENT;
            return -1;
        }
        *p=routes[index];
        p->index=index;
        p->uapi_version=DNIV_UAPI_VERSION;
        return 0;
    }
    return -1;
}
"""
SUFFIX = r"""
static int check(__u16 address,int reachable,__u8 ty,__u16 cost,
                 __u8 hops,const char *circuit,__u16 next) {
    __u8 outtype=0,outhops=0;
    __u16 outcost=0,outnext=0;
    char outcirc[16]={0};
    int rc=read_node_state(address,&outtype,&outcost,&outhops,
                           outcirc,sizeof(outcirc),&outnext);
    if ((!reachable && rc!=0) ||
        (reachable && rc==0 && outtype==ty && outcost==cost &&
         outhops==hops && outnext==next && strcmp(outcirc,circuit)==0))
        return 0;
    fprintf(stderr,"address=%u rc=%d type=%u cost=%u hops=%u "
            "next=%u circuit=%s\n",address,rc,outtype,outcost,
            outhops,outnext,outcirc);
    return 1;
}
int main(void) {
    int bad=0;
    bad+=check(DNIV_ADDR(31,71),1,4,1,1,"ETH-0",DNIV_ADDR(31,71));
    bad+=check(DNIV_ADDR(31,73),1,5,1,1,"ETH-1",DNIV_ADDR(31,73));
    bad+=check(DNIV_ADDR(31,72),1,4,3,2,"ETH-0",DNIV_ADDR(31,71));
    bad+=check(DNIV_ADDR(31,74),0,0,0,0,"",0);
    bad+=check(DNIV_ADDR(31,76),0,0,0,0,"",0);
    bad+=check(DNIV_ADDR(32,10),0,0,0,0,"",0);
    bad+=check(DNIV_ADDR(31,79),0,0,0,0,"",0);
    return bad ? 1 : 0;
}
"""


def main() -> None:
    raw = SOURCE.read_text(encoding="utf-8")
    start = raw.index("static int read_node_state(__u16 address")
    end = raw.index("\nstruct dniv_nml_node_status {", start)
    body = raw[start:end]
    with tempfile.TemporaryDirectory(prefix="dniv-nml-route-") as tmp:
        path = Path(tmp)
        source = path / "check.c"
        binary = path / "check"
        source.write_text(PREFIX + body + SUFFIX, encoding="utf-8")
        subprocess.run(shlex.split(os.environ.get("CC", "cc")) + [
            "-std=c11", "-Wall", "-Wextra", "-Werror",
            str(source), "-o", str(binary)
        ], check=True, timeout=60)
        result = subprocess.run([str(binary)], capture_output=True,
                                text=True, timeout=10)
        if result.returncode:
            raise AssertionError(
                f"NML source route-only vs direct neighbor: {result.stderr!r}"
            )
    print("NML recognizes live indirect L1 nodes and rejects unreachable routes")


if __name__ == "__main__":
    main()
