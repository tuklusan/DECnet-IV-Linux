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

"""Compile and execute the actual dnraw visit parser, rejecting suffixes."""

from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
raw = ROOT / "tests/lab/dnraw.c"
source = raw.read_text()
helper = re.search(r"static int parse_visit\([^)]*\)\n\{.*?\n\}", source, re.S)
assert helper, "missing strict visit parser"
assert "parse_visit(argv[6], &visit)" in source
assert 'sscanf(argv[6], "%u", &visit)' not in source

fixture = """#include <errno.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
""" + helper.group() + """
int main(void) {
    unsigned int value = 100;
    const char *good[] = {"0", "1", "63", "00042"};
    const char *bad[] = {"", "64", "1garbage", "1 ", "-0", "+1", " 1",
                         "999999999999999999999"};
    size_t i;
    for (i = 0; i < sizeof(good)/sizeof(good[0]); i++) {
        if (parse_visit(good[i], &value)) return 1;
    }
    for (i = 0; i < sizeof(bad)/sizeof(bad[0]); i++) {
        if (!parse_visit(bad[i], &value)) return 2;
    }
    return 0;
}
"""
with tempfile.TemporaryDirectory() as tmp:
    dir = Path(tmp)
    cfile = dir / "visit.c"
    binary = dir / "visit"
    whole = dir / "dnraw"
    cfile.write_text(fixture)
    subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                    str(cfile), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
    subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                    str(raw), "-o", str(whole)], check=True)
    invalid = subprocess.run([str(whole), "--short", "lo",
                              "52:54:00:00:00:01", "31.70", "31.71",
                              "1garbage", "x"],
                             capture_output=True, text=True)
    assert invalid.returncode == 2, invalid
    assert "invalid short-data argument" in invalid.stderr
print("dnraw exact visit token regression passed")
