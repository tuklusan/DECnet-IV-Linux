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

"""Compile and exercise actual endnode router-hello handler for DR priority/ties."""
import os
import re
import shlex
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "kernel/decnet/decnet_iv_ethernet.c").read_text(encoding="utf-8")


def extract(name):
    match = re.search(r"static\s+(?:bool|int|void|__u8)\s+" + re.escape(name) +
                      r"\s*\([^;]*?\)\s*\{", SOURCE, re.S)
    if not match:
        raise RuntimeError("missing source function: " + name)
    depth = 0
    for i in range(match.end() - 1, len(SOURCE)):
        if SOURCE[i] == "{":
            depth += 1
        elif SOURCE[i] == "}":
            depth -= 1
            if depth == 0:
                return SOURCE[match.start():i + 1]
    raise RuntimeError("unterminated source function: " + name)


mock = r'''
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t __u8;
typedef uint16_t __u16;
#define ETH_ALEN 6
#define DNIV_MAX_ADJACENCIES 64
#define DNIV_NODE_TYPE_L1_ROUTER 2
#define DNIV_NODE_TYPE_ENDNODE 3
#define DNIV_ADJ_STATE_UP 2
#define DNIV_ADDR_AREA(x) ((x)>>10)
#define spin_lock_irqsave(l, f) do {(void)(l); (f)=0;} while (0)
#define spin_unlock_irqrestore(l, f) do {(void)(l); (void)(f);} while (0)
#define atomic64_inc(x) (*(x))++
#define ether_addr_copy(d, s) memcpy((d),(s),ETH_ALEN)
struct dniv_adj_entry {bool used; int ifindex; __u16 address, block_size, hello_timer;
    __u8 node_type,state,priority,mac[ETH_ALEN]; unsigned long expires;};
struct dniv_wire_hello {__u16 address,block_size,timer; __u8 node_type,priority,is_router;};
static int dniv_adj_lock;
static __u16 dniv_local_address=(31<<10)|10;
static __u8 dniv_local_node_type=DNIV_NODE_TYPE_ENDNODE, dniv_local_priority=64;
static __u16 dniv_hello_interval=15;
static int dniv_hello_rx, dniv_hello_errors, dniv_adjacency_up, dniv_adjacency_down;
static struct dniv_adj_entry dniv_adjacencies[DNIV_MAX_ADJACENCIES];
static unsigned long jiffies=100;
static __attribute__((unused)) bool dniv_adj_usable(const struct dniv_adj_entry *a) {return a && a->used && jiffies < a->expires;}
static int dniv_wire_destination_valid(__u16 a,__u8 b,const __u8 *c) {(void)a;(void)b;(void)c;return 1;}
static bool dniv_area_compatible(__u16 peer,__u8 type) {(void)type;return DNIV_ADDR_AREA(peer)==DNIV_ADDR_AREA(dniv_local_address);}
static int dniv_wire_endnode_test_valid(const struct dniv_wire_hello *h) {(void)h;return 1;}
static int dniv_wire_router_adjacency_state(const struct dniv_wire_hello *h,__u16 a,__u8 pr,__u8 *s)
 {(void)h;(void)a;(void)pr;*s=DNIV_ADJ_STATE_UP;return 0;}
static struct dniv_adj_entry *dniv_find_adj_locked(int ifindex,__u16 addr)
 {for(int i=0;i<DNIV_MAX_ADJACENCIES;i++)if(dniv_adjacencies[i].used&&dniv_adjacencies[i].ifindex==ifindex&&dniv_adjacencies[i].address==addr)return &dniv_adjacencies[i];return NULL;}
static struct dniv_adj_entry *dniv_alloc_adj_locked(void)
 {for(int i=0;i<DNIV_MAX_ADJACENCIES;i++)if(!dniv_adjacencies[i].used)return &dniv_adjacencies[i];return NULL;}
static void dniv_drop_adj_locked(struct dniv_adj_entry *a)
 {if(!a||!a->used)return;if(a->state==DNIV_ADJ_STATE_UP)dniv_adjacency_down++;memset(a,0,sizeof(*a));}
static struct dniv_adj_entry *dniv_alloc_router_adj_locked(int ifindex,__u16 addr,__u8 pr,bool *rejected)
 {(void)ifindex;(void)addr;(void)pr;*rejected=false;return dniv_alloc_adj_locked();}
static unsigned long dniv_listen_expires(__u16 timer) {(void)timer;return jiffies+100;}
static void dniv_route_withdraw_adjacency(__u16 addr,int ifindex) {(void)addr;(void)ifindex;}
static void dniv_route_refresh_adjacency(__u16 addr,int ifindex,unsigned long expires)
 {(void)addr;(void)ifindex;(void)expires;}
static void dniv_refresh_direct_routes_locked(const struct dniv_adj_entry *a) {(void)a;}
'''

cases = r'''
static int selected(__u16 addr) {
  int count=0;__u16 found=0;
  for(int i=0;i<DNIV_MAX_ADJACENCIES;i++)if(dniv_adjacencies[i].used){count++;found=dniv_adjacencies[i].address;}
  return count==1&&found==addr;
}
static void reset(void) {memset(dniv_adjacencies,0,sizeof(dniv_adjacencies));}
static void hello(__u16 address,__u8 priority) {
  struct dniv_wire_hello h={.address=address,.priority=priority,.is_router=1,
                           .node_type=DNIV_NODE_TYPE_L1_ROUTER,.block_size=1498,.timer=15};
  __u8 mac[ETH_ALEN]={0xaa,0,4,0,1,2},dest[ETH_ALEN]={0xab,0,0,4,0,0};
  dniv_handle_valid_hello(7,mac,dest,&h);
}
int main(void) {
  const __u16 high=(31<<10)|20, low=(31<<10)|21, tie_high=(31<<10)|40;
  reset();hello(high,110);hello(low,20);
  if(!selected(high)){fprintf(stderr,"priority downgrade: lower-priority hello stole endnode router\n");return 1;}
  reset();hello(low,20);hello(high,110);
  if(!selected(high)){fprintf(stderr,"higher-priority takeover failed\n");return 2;}
  reset();hello(tie_high,90);hello(low,90);
  if(!selected(tie_high)){fprintf(stderr,"tie downgraded to lower node address\n");return 3;}
  reset();hello(low,90);hello(tie_high,90);
  if(!selected(tie_high)){fprintf(stderr,"higher-node tie takeover failed\n");return 4;}
  reset();hello(high,110);jiffies=201;hello(low,20);
  if(!selected(low)){fprintf(stderr,"expired designated router blocked replacement\n");return 5;}
  puts("endnode DR priority/tie/expiry source regression passed");return 0;
}
'''

with tempfile.TemporaryDirectory(prefix="dniv-endnode-dr-") as tmp:
    path = Path(tmp)
    (path / "test.c").write_text(mock + "\n" + extract("dniv_remove_other_endnode_router_locked") +
                                 "\n" + extract("dniv_handle_valid_hello") + "\n" + cases)
    cc = shlex.split(os.environ.get("CC", "cc"))
    subprocess.run(cc + ["-std=gnu11", "-Wall", "-Wextra", "-Werror", str(path / "test.c"),
                         "-o", str(path / "test")], check=True, timeout=60)
    subprocess.run([str(path / "test")], check=True, timeout=20)
