#!/usr/bin/env python3
# Copyright (c) 2026 Supratim Sanyal of SANYALnet Labs.
# Governed by the SANYALnet Labs Non-Commercial License; see LICENSE.
# Attribution: Based on original work by Supratim Sanyal of SANYALnet Labs.

"""Check that stream receives account for bytes actually delivered by copy_to_iter."""

import os
import shlex
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOCKET_SOURCE = ROOT / "kernel/decnet/decnet_iv_socket.c"

C_PREFIX = r"""
#include <stddef.h>
#include <string.h>
#include <errno.h>
#include <assert.h>
#include <stdio.h>
struct iter { unsigned char *buf; size_t capacity; size_t used; };
struct msghdr { struct iter msg_iter; };
struct rx { unsigned char stream_rx[8]; size_t stream_rx_off; };
static size_t copy_to_iter(const void *src, size_t requested, struct iter *it) {
    size_t space = it->capacity - it->used;
    size_t length = requested < space ? requested : space;
    memcpy(it->buf + it->used, src, length);
    it->used += length;
    return length;
}
static int transfer(struct rx *dsk, struct msghdr *msg, size_t chunk) {
    size_t copied = 0;
"""
C_SUFFIX = r"""
    return (int)copied;
}
int main(void) {
    struct rx dsk = {{'A','B','C','D'}, 0};
    unsigned char first[2] = {0}, second[4] = {0};
    struct msghdr m1 = {{first, sizeof first, 0}};
    struct msghdr m2 = {{second, sizeof second, 0}};
    assert(transfer(&dsk, &m1, 4) == 2);
    assert(dsk.stream_rx_off == 2);
    assert(memcmp(first, "AB", 2) == 0);
    assert(transfer(&dsk, &m2, 2) == 2);
    assert(dsk.stream_rx_off == 4);
    assert(memcmp(second, "CD", 2) == 0);
    puts("partial stream copy preserves byte accounting");
    return 0;
}
"""

def main() -> int:
    source = SOCKET_SOURCE.read_text(encoding="utf-8")
    start = source.index("static int dniv_stream_recv_locked(")
    end = source.index("\nstatic int dniv_sock_recvmsg(", start)
    routine = source[start:end]
    begin = routine.index("        if (chunk) {")
    stop = routine.index("\n        if (!(flags & MSG_WAITALL))", begin)
    snippet = routine[begin:stop]
    if "copy_to_iter(" not in snippet or "dsk->stream_rx_off += moved;" not in snippet:
        raise SystemExit("stream receive copy accounting no longer matches the regression")
    with tempfile.TemporaryDirectory(prefix="dniv-partial-recv-") as directory:
        root = Path(directory)
        (root / "check.c").write_text(C_PREFIX + snippet + "\n}\n" +
                                      C_SUFFIX.split("    return (int)copied;\n}\n", 1)[1],
                                      encoding="utf-8")
        # The extracted snippet has early return; normal path also returns copied.
        file = root / "check.c"
        generated = file.read_text(encoding="utf-8")
        file.write_text(generated.replace("\n}\nint main(void)", 
                                          "\n    return (int)copied;\n}\nint main(void)", 1),
                        encoding="utf-8")
        exe = root / "check"
        subprocess.run(shlex.split(os.environ.get("CC", "cc")) + [
            "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
            str(file), "-o", str(exe)], check=True, timeout=60)
        subprocess.run([str(exe)], check=True, timeout=20)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
