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

"""SMTP must not connect when a required socket timeout cannot be set."""

from pathlib import Path
import os
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]
HARNESS = r'''
#define main dnmaild_source_main
#include "userspace/dnmail/dnmaild.c"
#undef main
static int fail_at;
static int calls;
static int connections;
static int closes;
int __real_close(int);
int __wrap_close(int fd) {
    closes++;
    return __real_close(fd);
}
int __wrap_setsockopt(int fd, int level, int option,
                      const void *value, socklen_t len) {
    (void)fd; (void)level; (void)option; (void)value; (void)len;
    calls++;
    if (fail_at == calls) {
        errno = EIO;
        return -1;
    }
    return 0;
}
int __wrap_connect(int fd, const struct sockaddr *address, socklen_t len) {
    (void)fd; (void)address; (void)len;
    connections++;
    errno = ECONNREFUSED;
    return -1;
}
int main(void) {
    for (fail_at = 1; fail_at <= 2; fail_at++) {
        calls = connections = closes = 0;
        if (smtp_open("127.0.0.1", 2525, "sender@localhost",
                      "user@localhost", "sender", "subject", "user") != -1 ||
            calls != fail_at || connections != 0 || closes != 1)
            return 1;
    }
    fail_at = 0;
    calls = connections = closes = 0;
    if (smtp_open("127.0.0.1", 2525, "sender@localhost",
                  "user@localhost", "sender", "subject", "user") != -1 ||
        calls != 2 || connections != 1 || closes != 1)
        return 2;
    return 0;
}
'''


def check():
    with tempfile.TemporaryDirectory(prefix="dniv-smtp-timeout-") as tmp:
        cfile = Path(tmp) / "smtp.c"
        binary = Path(tmp) / "smtp"
        cfile.write_text(HARNESS)
        subprocess.run(
            [os.environ.get("CC", "cc"), "-std=gnu11", "-Wall", "-Wextra",
             "-Werror", "-I", str(ROOT), "-I", str(ROOT / "include/uapi"),
             str(cfile), "-Wl,--wrap=setsockopt", "-Wl,--wrap=connect",
             "-Wl,--wrap=close", "-o", str(binary)],
            check=True, capture_output=True, text=True, timeout=30,
        )
        result = subprocess.run([str(binary)], capture_output=True, text=True,
                                timeout=5)
        assert result.returncode == 0, (
            result.returncode, result.stdout, result.stderr)
    print("dnmail SMTP timeout error regression passed")


if __name__ == "__main__":
    check()
