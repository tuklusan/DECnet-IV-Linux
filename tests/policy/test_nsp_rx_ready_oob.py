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

"""Compile actual NSP readiness scanner: normal data must not mask later OOB."""

import os
import shlex
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOCKET_SOURCE = ROOT / "kernel/decnet/decnet_iv_nsp.c"
START = "int dniv_nsp_rx_ready(__u16 local_link, bool *normal, bool *interrupt)"
END = "int dniv_nsp_retransmit_queue(__u16 local_link,"

PREFIX = r"""
#include <stdbool.h>
#include <stddef.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>

typedef unsigned short __u16;
struct list_head { struct list_head *next, *prev; };
struct dniv_nsp_rx_entry {
    struct list_head link;
    int channel, type;
    unsigned char bom, eom;
};
struct dniv_nsp_connection { struct list_head rx_ready; };
#define DNIV_NSP_CH_DATA 0
#define DNIV_NSP_CH_OTHER 1
#define DNIV_NSP_DATA 2
#define DNIV_NSP_INT 3
#define list_for_each_entry(pos,head,member) \
    for (struct list_head *_iter=(head)->next; \
         _iter!=(head) && ((pos)=(void *)((char *)_iter- \
            offsetof(struct dniv_nsp_rx_entry,member)),1); \
         _iter=_iter->next)
#define spin_lock_irqsave(lock,flags) ((void)(lock),(void)(flags))
#define spin_unlock_irqrestore(lock,flags) ((void)(lock),(void)(flags))
static int dniv_nsp_lock;
static struct dniv_nsp_connection conn;
static struct dniv_nsp_connection *dniv_nsp_find_locked(__u16 id)
{ return id == 7 ? &conn : NULL; }
static void reset(void)
{
    conn.rx_ready.next = &conn.rx_ready;
    conn.rx_ready.prev = &conn.rx_ready;
}
static void append(struct dniv_nsp_rx_entry *e)
{
    struct list_head *head = &conn.rx_ready;
    struct list_head *p = &e->link;
    p->next=head; p->prev=head->prev;
    head->prev->next=p; head->prev=p;
}
"""

SUFFIX = r"""
static int check(const char *label, bool want_normal, bool want_interrupt)
{
    bool normal = false, interrupt = false;
    int rc = dniv_nsp_rx_ready(7, &normal, &interrupt);
    if (rc || normal != want_normal || interrupt != want_interrupt) {
        fprintf(stderr,"%s: ready=%d normal=%d interrupt=%d expected=%d/%d\n",
                label,rc,normal,interrupt,want_normal,want_interrupt);
        return 1;
    }
    return 0;
}
int main(void)
{
    struct dniv_nsp_rx_entry full = { .channel=DNIV_NSP_CH_DATA,
                                      .type=DNIV_NSP_DATA, .bom=1,.eom=1};
    struct dniv_nsp_rx_entry intr = { .channel=DNIV_NSP_CH_OTHER,
                                      .type=DNIV_NSP_INT };
    struct dniv_nsp_rx_entry first = { .channel=DNIV_NSP_CH_DATA,
                                      .type=DNIV_NSP_DATA, .bom=1,.eom=0};
    struct dniv_nsp_rx_entry last = { .channel=DNIV_NSP_CH_DATA,
                                     .type=DNIV_NSP_DATA, .bom=0,.eom=1};
    reset(); append(&full); append(&intr);
    if (check("normal-then-interrupt", true, true)) return 1;
    reset(); append(&intr); append(&full);
    if (check("interrupt-then-normal", true, true)) return 1;
    reset(); append(&first); append(&intr);
    if (check("unfinished-normal-then-interrupt", false, true)) return 1;
    reset(); append(&first); append(&intr); append(&last);
    if (check("segmented-normal-and-interrupt", true, true)) return 1;
    reset(); append(&full);
    if (check("normal-only", true, false)) return 1;
    reset(); append(&intr);
    if (check("interrupt-only", false, true)) return 1;
    puts("NSP independent normal/interrupt readiness passed");
    return 0;
}
"""


def main() -> int:
    text = SOCKET_SOURCE.read_text(encoding="utf-8")
    if text.count(START) != 1 or text.count(END) != 1:
        raise SystemExit("NSP rx readiness source structure changed")
    region = text[text.index(START): text.index(END)]
    with tempfile.TemporaryDirectory(prefix="dniv-nsp-ready-") as directory:
        root = Path(directory)
        source = root / "ready.c"
        executable = root / "ready"
        source.write_text(PREFIX + region + SUFFIX, encoding="utf-8")
        subprocess.run(shlex.split(os.environ.get("CC", "cc")) + [
            "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
            str(source), "-o", str(executable)
        ], timeout=60, check=True)
        result = subprocess.run([str(executable)], capture_output=True,
                                text=True, timeout=10)
        if result.returncode:
            raise SystemExit(
                f"kernel NSP rx readiness regression: rc={result.returncode}, "
                f"stdout={result.stdout!r}, stderr={result.stderr!r}"
            )
    print("NSP RX ready normal/OOB independence regression passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
