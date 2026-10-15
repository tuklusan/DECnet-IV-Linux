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

"""Clock failures must not be treated as monotonic zero milliseconds."""

from pathlib import Path
import os
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]
HARNESS = r'''
#define _POSIX_C_SOURCE 200809L
#define main dniv_real_main
#include "tests/lab/dnadjwait.c"
#undef main
int __wrap_clock_gettime(clockid_t clock, struct timespec *ts) {
    (void)clock; (void)ts;
    errno = EIO;
    return -1;
}
int main(void) {
    uint64_t value = 1234;
    if (monotonic_ms(&value) != -1 || value != 1234)
        return 1;
    return 0;
}
'''


def check():
    with tempfile.TemporaryDirectory(prefix="dniv-clock-test-") as d:
        source = Path(d) / "clock.c"
        exe = Path(d) / "clock"
        source.write_text(HARNESS)
        subprocess.run(
            [os.environ.get("CC", "cc"), "-std=gnu11", "-Wall", "-Wextra",
             "-Werror", "-I", str(ROOT), "-I", str(ROOT / "include/uapi"),
             str(source), "-Wl,--wrap=clock_gettime", "-o", str(exe)],
            check=True, capture_output=True, text=True,
        )
        result = subprocess.run([str(exe)], capture_output=True, text=True,
                                timeout=5)
        assert result.returncode == 0, result.stderr
    print("dnadjwait clock-error source regression passed")


if __name__ == "__main__":
    check()

