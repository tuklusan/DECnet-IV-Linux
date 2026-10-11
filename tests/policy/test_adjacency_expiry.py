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

"""Check that expired adjacency peers are excluded before the aging pass."""

import os
import re
import shlex
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
source = (ROOT / "kernel/decnet/decnet_iv_ethernet.c").read_text(encoding="utf-8")


def function(name):
    match = re.search(
        r"static\s+(?:bool|int|void|__u8|struct dniv_adj_entry \*)\s*" +
        re.escape(name) + r"\s*\([^;]*?\)\s*\{", source, re.S)
    if not match:
        raise SystemExit("missing Ethernet source function: " + name)
    depth = 0
    for pos in range(match.end() - 1, len(source)):
        if source[pos] == "{":
            depth += 1
        elif source[pos] == "}":
            depth -= 1
            if depth == 0:
                return source[match.start():pos + 1]
    raise SystemExit("unterminated Ethernet function: " + name)


# Keep all ingress, election and forwarding consumers consistent.
for name in (
    "dniv_alloc_router_adj_locked", "dniv_collect_router_entries",
    "dniv_local_is_dr", "dniv_endnode_neighbor",
    "dniv_routing_source_allowed", "dniv_data_source_allowed",
    "dniv_endnode_route",
):
    if "dniv_adj_usable(adj)" not in function(name):
        raise SystemExit("adjacency expiry not enforced by " + name)

mock = r"""
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
typedef uint8_t __u8;
typedef uint16_t __u16;
#define DNIV_MAX_ADJACENCIES 64
#define DNIV_NODE_TYPE_ENDNODE 1
#define DNIV_NODE_TYPE_L2_ROUTER 3
#define DNIV_ADJ_STATE_UP 2
#define DNIV_ADDR_AREA(x) ((x)>>10)
#define READ_ONCE(x) (x)
#define time_before(a,b) ((long)((a)-(b))<0)
#define spin_lock_irqsave(l,f) do {(void)(l);(f)=0;}while(0)
#define spin_unlock_irqrestore(l,f) do {(void)(l);(void)(f);}while(0)
struct dniv_adj_entry {
  bool used;
  int ifindex;
  __u16 address;
  __u8 node_type, state;
  unsigned long expires;
};
static unsigned long jiffies=106;
static int dniv_adj_lock;
static __u16 dniv_local_address=(31<<10)|2;
static struct dniv_adj_entry dniv_adjacencies[DNIV_MAX_ADJACENCIES];
"""
check = r"""
int main(void) {
    struct dniv_adj_entry *adj=&dniv_adjacencies[0];
    adj->used=true;
    adj->ifindex=5;
    adj->address=(31<<10)|4;
    adj->node_type=DNIV_NODE_TYPE_L2_ROUTER;
    adj->state=DNIV_ADJ_STATE_UP;
    adj->expires=105;
    if (dniv_has_up_router_adjacency(5,1)) return 1;
    jiffies=104;
    if (!dniv_has_up_router_adjacency(5,1)) return 2;
    jiffies=105;
    if (dniv_has_up_router_adjacency(5,1)) return 3;
    puts("Ethernet adjacency expiry regression passed");
    return 0;
}
"""
with tempfile.TemporaryDirectory(prefix="dniv-adjacency-") as tmp:
    path = Path(tmp)
    (path / "test.c").write_text(
        mock + "\n" + function("dniv_adj_usable") + "\n" +
        function("dniv_has_up_router_adjacency") + "\n" + check,
        encoding="utf-8",
    )
    binary = path / "test"
    compiler = shlex.split(os.environ.get("CC", "cc"))
    subprocess.run(
        compiler + ["-std=gnu11", "-Wall", "-Wextra", "-Werror",
                    str(path / "test.c"), "-o", str(binary)],
        check=True, timeout=60,
    )
    subprocess.run([str(binary)], check=True, timeout=20)
