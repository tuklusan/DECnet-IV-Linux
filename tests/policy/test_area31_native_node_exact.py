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

"""Exercise the actual Area-31 native decimal-node parser without DECnet I/O."""

from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
for source_path, end_marker in (
    ("tests/lab/area31-native.c", "\nstatic void nice_dump_frame("),
    ("tests/lab/dnaccept.c", "\nstatic int make_listener("),
    ("tests/lab/dnackrange.c", "\nint main("),
):
    source = (root / source_path).read_text()
    start = source.index("static int parse_node(")
    end = source.index(end_marker, start)
    parser = source[start:end]
    driver = """
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <errno.h>
""" + parser + """
int main(int argc, char **argv) {
    uint16_t address = 0;
    int rc;
    if (argc != 3)
        return 3;
    rc = parse_node(argv[1], &address);
    if (argv[2][0] == 'V')
        return rc == 0 && address == ((31U << 10) | 70U) ? 0 : 1;
    return rc != 0 ? 0 : 1;
}
"""
    with tempfile.TemporaryDirectory() as tmp:
        cfile = Path(tmp) / "probe.c"
        binary = Path(tmp) / "probe"
        cfile.write_text(driver)
        subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                        str(cfile), "-o", str(binary)], check=True)
        for valid in ("31.70", "031.00070"):
            subprocess.run([str(binary), valid, "V"], check=True)
        for invalid in (
            "-18446744073709551615.1", "1.-18446744073709551615",
            "+31.70", "31.+70", " 31.70", "31. 70",
            "0.70", "64.70", "31.0", "31.1024",
            "18446744073709551617.70", "31.18446744073709551617",
            "31.70junk",
        ):
            subprocess.run([str(binary), invalid, "X"], check=True)
    print("Area31/inbound/ACK-range strict decimal identity passed")
