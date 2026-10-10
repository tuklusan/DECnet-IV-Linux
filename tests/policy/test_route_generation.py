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

"""Compile the exact kernel route implementation using deterministic mock jiffies."""
import os
import shlex
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MOCK = "\n#include <stddef.h>\n#include <stdint.h>\n#include <stdbool.h>\n#include <stdlib.h>\ntypedef uint8_t __u8; typedef uint16_t __u16; typedef uint32_t __u32;\ntypedef uint64_t __u64; typedef int32_t __s32;\n#define EINVAL 22\n#define ENOMEM 12\n#define ENOENT 2\nextern unsigned long jiffies;\n#define HZ 100U\n#define time_before(a,b) ((long)((a)-(b)) < 0)\n#define time_after_eq(a,b) ((long)((a)-(b)) >= 0)\n#define DEFINE_SPINLOCK(name) int name\n#define spin_lock_irqsave(lock,f) do { (void)(lock); (f)=0; } while(0)\n#define spin_unlock_irqrestore(lock,f) do { (void)(lock); (void)(f); } while(0)\n#define GFP_ATOMIC 0\n#define kmalloc(size,flags) malloc(size)\n#define kfree(ptr) free(ptr)\nstruct work_struct { int unused; };\n#define DECLARE_DELAYED_WORK(name,cb) struct work_struct name; \\\n    static void *const name##_cb __attribute__((unused)) = (void*)&cb\n#define schedule_delayed_work(work,d) ((void)(work),(void)(d))\n#define cancel_delayed_work_sync(work) ((void)(work))\nstruct hlist_node { struct hlist_node *next, **pprev; };\nstruct hlist_head { struct hlist_node *first; };\n#define INIT_HLIST_HEAD(h) ((h)->first=NULL)\nstatic inline void hlist_add_head(struct hlist_node*n,struct hlist_head*h){\n n->next=h->first;if(h->first)h->first->pprev=&n->next;\n h->first=n;n->pprev=&h->first;\n}\nstatic inline void hlist_del(struct hlist_node*n){\n if(n->next) n->next->pprev=n->pprev;\n *n->pprev=n->next;\n}\n#define entry(p,t,m) ((t*)((char*)(p)-offsetof(t,m)))\n#define hlist_for_each_entry(pos,head,member) \\\n for(struct hlist_node*_n=(head)->first; \\\n _n&&(((pos)=entry(_n,__typeof__(*(pos)),member)),1);_n=_n->next)\n#define hlist_for_each_entry_safe(pos,tmp,head,member) \\\n for(struct hlist_node*_n=(head)->first; \\\n _n&&(((pos)=entry(_n,__typeof__(*(pos)),member)),(tmp=_n->next),1);_n=tmp)\n"
TEST = "\n#include <assert.h>\n#include <stdio.h>\nunsigned long jiffies=100;\n#include \"decnet_iv_route.c\"\nint main(void){\n struct dniv_route_result r;\n __u64 g;\n assert(dniv_route_init()==0);\n assert(dniv_route_update(1,42,51,2,12,2,105)==0);\n g=dniv_route_get_generation();\n assert(dniv_route_lookup(1,42,&r)==0);\n jiffies=106;\n assert(dniv_route_lookup(1,42,&r)==-ENOENT);\n assert(dniv_route_update(1,42,51,2,12,2,116)==0);\n assert(dniv_route_lookup(1,42,&r)==0);\n assert(dniv_route_get_generation()==g+1);\n g=dniv_route_get_generation();\n assert(dniv_route_update(1,42,51,2,12,2,115)==0);\n assert(dniv_route_get_generation()==g);\n assert(dniv_route_update(1,42,51,2,12,2,104)==0);\n assert(dniv_route_lookup(1,42,&r)==-ENOENT);\n assert(dniv_route_get_generation()==g+1);\n g=dniv_route_get_generation();\n dniv_route_refresh_adjacency(51,2,120);\n assert(dniv_route_lookup(1,42,&r)==0);\n assert(dniv_route_get_generation()==g+1);\n g=dniv_route_get_generation();\n dniv_route_refresh_adjacency(51,2,130);\n assert(dniv_route_get_generation()==g);\n assert(dniv_route_update(2,3,51,2,40,4,107)==0);\n g=dniv_route_get_generation();jiffies=108;\n assert(dniv_route_lookup(2,3,&r)==-ENOENT);\n dniv_route_refresh_adjacency(51,2,140);\n assert(dniv_route_lookup(2,3,&r)==0);\n assert(dniv_route_get_generation()==g+1);\n dniv_route_exit();\n puts(\"route generation visibility regression passed\");\n return 0;\n}\n"

def main():
    with tempfile.TemporaryDirectory(prefix="dniv-route-") as path:
        root = Path(path)
        (root / "linux").mkdir()
        for name in ("errno.h", "jiffies.h", "list.h", "slab.h", "spinlock.h", "types.h", "workqueue.h"):
            (root / "linux" / name).write_text("/* mocked by mock.h */\n")
        (root / "mock.h").write_text(MOCK)
        (root / "test.c").write_text(TEST)
        cmd = shlex.split(os.environ.get("CC", "cc")) + [
            "-std=gnu11", "-Wall", "-Wextra", "-Werror", "-O1",
            "-include", str(root / "mock.h"), "-I", str(root),
            "-I", str(ROOT / "include"), "-I", str(ROOT / "kernel/decnet"),
            str(root / "test.c"), "-o", str(root / "test")]
        subprocess.run(cmd, check=True, timeout=60)
        subprocess.run([str(root / "test")], check=True, timeout=20)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
