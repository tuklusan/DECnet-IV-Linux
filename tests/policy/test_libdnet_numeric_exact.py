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

"""Native libdnet exact decimal parsing (actual packaged C, no sockets)."""

from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
body = r'''
#include "__SOURCE__"
int main(void) {
    struct dn_naddr addr;
    if (dnet_pton(AF_DECnet, "31.70", &addr) != 1 ||
        addr.a_addr[0] != 70 || addr.a_addr[1] != 124) return 10;
    if (dnet_pton(AF_DECnet, "031.00070", &addr) != 1) return 11;
    if (dnet_pton(AF_DECnet, "+31.70", &addr) != 0) return 12;
    if (dnet_pton(AF_DECnet, "31.+70", &addr) != 0) return 13;
    if (dnet_pton(AF_DECnet, " 31.70", &addr) != 0) return 14;
    if (dnet_pton(AF_DECnet, "31. 70", &addr) != 0) return 15;
    if (dnet_pton(AF_DECnet, "-18446744073709551615.70", &addr) != 0)
        return 16;
    if (dnet_pton(AF_DECnet, "31.-18446744073709551615", &addr) != 0)
        return 17;
    if (dnet_pton(AF_DECnet, "0.70", &addr) != 0) return 18;
    if (dnet_pton(AF_DECnet, "31.1024", &addr) != 0) return 19;
    return 0;
}
'''
with tempfile.TemporaryDirectory() as tmp:
    source = Path(tmp) / 'probe.c'
    output = Path(tmp) / 'probe'
    source.write_text(body.replace('__SOURCE__', str(root / 'userspace/libdnet/libdnet.c')))
    subprocess.run(['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                    '-ffunction-sections', '-fdata-sections',
                    f'-I{root / "include/uapi"}',
                    f'-I{root / "userspace/libdnet/include"}',
                    str(source), '-Wl,--gc-sections', '-o', str(output)],
                   check=True, capture_output=True, text=True)
    test = subprocess.run([str(output)], capture_output=True, text=True)
    assert test.returncode == 0, (test.returncode, test.stderr)
print('libdnet strict decimal parser regression passed')
