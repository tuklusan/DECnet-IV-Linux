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

"""Reject missing VDE frame token before any endpoint is opened."""

from pathlib import Path
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
HEADER = """#ifndef FAKE_VDEPLUG_H
#define FAKE_VDEPLUG_H
#include <sys/types.h>
typedef struct VDECONN VDECONN;
VDECONN *vde_open(char *, char *, void *);
int vde_close(VDECONN *);
int vde_datafd(VDECONN *);
ssize_t vde_recv(VDECONN *, void *, size_t, int);
ssize_t vde_send(VDECONN *, const void *, size_t, int);
#endif
"""
HARNESS = r'''
#define main real_vde_frame_main
#include "tests/lab/vde-frame-echo.c"
#undef main
struct VDECONN { int unused; };
static int opens;
VDECONN *vde_open(char *url, char *description, void *unused) {
    (void)url; (void)description; (void)unused;
    ++opens;
    errno = ENOENT;
    return NULL;
}
int vde_close(VDECONN *c) { (void)c; return 0; }
int vde_datafd(VDECONN *c) { (void)c; return -1; }
ssize_t vde_recv(VDECONN *c, void *buf, size_t len, int flags) {
    (void)c; (void)buf; (void)len; (void)flags;
    return -1;
}
ssize_t vde_send(VDECONN *c, const void *buf, size_t len, int flags) {
    (void)c; (void)buf; (void)len; (void)flags;
    return -1;
}
static int check(const char *token, int valid) {
    int before = opens;
    char *args[] = {"vde-frame-echo", "client", "mock", (char *)token, NULL};
    int rc = real_vde_frame_main(4, args);
    return valid ? (rc == 1 && opens == before + 1) :
                   (rc == 2 && opens == before);
}
int main(void) {
    return (check("0", 1) && check("255", 1) && check("", 0) &&
            check("256", 0) && check("abc", 0)) ? 0 : 1;
}
'''

with tempfile.TemporaryDirectory(prefix="dniv-vde-token-") as tmp:
    d = Path(tmp)
    (d / "libvdeplug.h").write_text(HEADER)
    (d / "token.c").write_text(HARNESS)
    exe = d / "token"
    subprocess.run([os.environ.get("CC", "cc"), "-std=c11", "-Wall", "-Wextra", "-Werror", "-I", str(d), "-I", str(ROOT), str(d / "token.c"), "-o", str(exe)], capture_output=True, text=True, check=True)
    r = subprocess.run([str(exe)], capture_output=True, text=True, timeout=2)
    assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
print("VDE frame token input guard regression passed")
