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

"""Broken VDE data descriptors must never spin forever in server mode."""

from pathlib import Path
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
HEADER = '''
#ifndef FAKE_VDEPLUG_H
#define FAKE_VDEPLUG_H
#include <sys/types.h>
typedef struct VDECONN VDECONN;
VDECONN *vde_open(char *, char *, void *);
int vde_close(VDECONN *);
int vde_datafd(VDECONN *);
ssize_t vde_recv(VDECONN *, void *, size_t, int);
ssize_t vde_send(VDECONN *, const void *, size_t, int);
#endif
'''
HARNESS = r'''
#define main real_vde_frame_main
#include "tests/lab/vde-frame-echo.c"
#undef main
struct VDECONN { int unused; };
static struct VDECONN fake_conn;
static int closed;
VDECONN *vde_open(char *url, char *description, void *unused) {
    (void)url; (void)description; (void)unused;
    return &fake_conn;
}
int vde_close(VDECONN *c) { (void)c; ++closed; return 0; }
int vde_datafd(VDECONN *c) { (void)c; errno = EBADF; return -1; }
ssize_t vde_recv(VDECONN *c, void *buffer, size_t len, int flags) {
    (void)c; (void)buffer; (void)len; (void)flags;
    return -1;
}
ssize_t vde_send(VDECONN *c, const void *buffer, size_t len, int flags) {
    (void)c; (void)buffer; (void)len; (void)flags;
    return -1;
}
int main(void) {
    int result = run_server("mock");
    return result == 1 && closed == 1 ? 0 : 1;
}
'''


def check():
    with tempfile.TemporaryDirectory(prefix="dniv-vde-badfd-") as tmp:
        base = Path(tmp)
        (base / "libvdeplug.h").write_text(HEADER)
        (base / "vde_badfd.c").write_text(HARNESS)
        exe = base / "vde_badfd"
        subprocess.run([os.environ.get("CC", "cc"), "-std=c11", "-Wall", "-Wextra", "-Werror", "-I", str(base), "-I", str(ROOT), str(base / "vde_badfd.c"), "-o", str(exe)], capture_output=True, text=True, check=True)
        result = subprocess.run([str(exe)], capture_output=True, text=True, timeout=2)
        assert result.returncode == 0, (result.returncode, result.stderr)
    print("VDE echo invalid-descriptor fail-closed regression passed")


if __name__ == "__main__":
    check()
