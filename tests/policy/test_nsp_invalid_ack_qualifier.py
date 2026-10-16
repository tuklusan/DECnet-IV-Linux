#!/usr/bin/env python3
"""Reject illegal NSP ACK qualifiers in real shared wire header."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE = r"""
#include <stdio.h>
#include "include/decnet_iv_nsp_wire.h"
int main(void) {
    struct dniv_nsp_packet packet;
    unsigned int qual;
    for (qual = 0; qual < 8; qual++) {
        unsigned char data[] = {0x60, 1, 0, 2, 0, 0, 0, 1, 0};
        int rc;
        data[6] = (unsigned char)(0x80 | (qual << 4));
        rc = dniv_nsp_parse(data, sizeof(data), &packet);
        if (qual < 4) {
            if (rc != DNIV_NSP_OK || !packet.ack1.present ||
                packet.ack1.qual != qual || packet.segnum != 1)
                return 1;
        } else if (rc != DNIV_NSP_MALFORMED) {
            return 2;
        }
    }
    return 0;
}
"""

def check():
    with tempfile.TemporaryDirectory(prefix="dniv-nsp-ack-") as td:
        source = Path(td) / "test.c"
        binary = Path(td) / "test"
        source.write_text(SOURCE)
        subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                        "-I", str(ROOT), str(source), "-o", str(binary)],
                       check=True, timeout=30)
        subprocess.run([str(binary)], check=True, timeout=30)
    print("NSP malformed ACK qualifier regression passed")

if __name__ == "__main__":
    check()
