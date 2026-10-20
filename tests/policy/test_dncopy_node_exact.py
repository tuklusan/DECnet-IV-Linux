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

"""Compile and test the actual dncopy parse_node with no network operations."""

from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
source = (ROOT / "userspace/dncopy/dncopy.c").read_text(encoding="utf-8")
start = source.index("static int parse_node(")
end = source.index("static int copy_span(", start)
parser = source[start:end]

harness = r'''#include <errno.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
''' + parser + r'''
int main(int argc, char **argv)
{
    uint16_t got = 0;
    int ok;
    if (argc != 3) return 3;
    ok = parse_node(argv[1], &got);
    if (argv[2][0] == 'Y')
        return (ok == 0 && got == (uint16_t)((31U << 10) | 70U)) ? 0 : 1;
    return ok != 0 ? 0 : 1;
}
'''
with tempfile.TemporaryDirectory(prefix="dniv-dncopy-parse-") as temp:
    source_path = Path(temp) / "parser.c"
    binary = Path(temp) / "parser"
    source_path.write_text(harness, encoding="utf-8")
    subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                    str(source_path), "-o", str(binary)], check=True)
    cases = [("31.70", "Y"), ("031.00070", "Y")]
    cases += [(bad, "N") for bad in (
        "-18446744073709551615.1", "1.-18446744073709551615",
        "+31.70", "31.+70", " 31.70", "31. 70",
        "31.70junk", "0.70", "64.70", "31.0", "31.1024",
        "18446744073709551617.1", "31.18446744073709551617")]
    for value, expect in cases:
        result = subprocess.run([str(binary), value, expect],
                                capture_output=True, text=True, timeout=3)
        assert result.returncode == 0, (value, expect, result.returncode,
                                        result.stderr)
print("dncopy original parse_node strict decimal regression passed")
