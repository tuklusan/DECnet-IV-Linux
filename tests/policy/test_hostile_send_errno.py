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

"""Compile real negative-check helper and detect disconnected false positives."""

from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
source = (ROOT / "tests/lab/dnhostile.c").read_text()
helper = re.search(r"static int must_fail_errno\([^)]*\)\n\{.*?\n\}", source, re.S)
assert helper, "missing errno-specific send guard"
assert re.search(r'must_fail_errno\(send\(fd, "x", 1, MSG_DONTROUTE\),\s*EOPNOTSUPP,', source)
assert re.search(r'must_fail_errno\(send\(fd, oversize, \(size_t\)DNBUFSIZE \+ 1U, MSG_EOR\),\s*EMSGSIZE,', source)

fixture = "#include <errno.h>\n#include <stdio.h>\n" + helper.group() + r"""
int main(void) {
    errno = EOPNOTSUPP;
    if (must_fail_errno(-1, EOPNOTSUPP, "supported reject")) return 1;
    errno = ENOTCONN;
    if (!must_fail_errno(-1, EOPNOTSUPP, "unconnected false green")) return 2;
    errno = EMSGSIZE;
    if (must_fail_errno(-1, EMSGSIZE, "oversize reject")) return 3;
    errno = EINVAL;
    if (!must_fail_errno(-1, EMSGSIZE, "unrelated error")) return 4;
    errno = EOPNOTSUPP;
    if (!must_fail_errno(0, EOPNOTSUPP, "unexpected success")) return 5;
    return 0;
}
"""
with tempfile.TemporaryDirectory() as tmp:
    cfile = Path(tmp) / "negative.c"
    binary = Path(tmp) / "negative"
    cfile.write_text(fixture)
    subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                    str(cfile), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True, capture_output=True)
print("Hostile send error classification regression passed")
