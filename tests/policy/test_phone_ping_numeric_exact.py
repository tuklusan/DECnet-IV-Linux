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

"""Check numeric CLI parsers using actual shipped C source, without a network."""

from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]

CASES = {
    "phone": (
        "userspace/dnphone/phone.c",
        r'''
    uint16_t addr = 0;
    const char *user = NULL;
    if (parse_target("31.70::TEST", &addr, &user) ||
        addr != ((31 << 10) | 70) || strcmp(user, "TEST")) return 10;
    if (parse_target("031.00070::TEST", &addr, &user)) return 11;
    if (!parse_target("+31.70::TEST", &addr, &user)) return 12;
    if (!parse_target("31.+70::TEST", &addr, &user)) return 13;
    if (!parse_target(" 31.70::TEST", &addr, &user)) return 14;
    if (!parse_target("31. 70::TEST", &addr, &user)) return 15;
    if (!parse_target("31.1024::TEST", &addr, &user)) return 16;
    if (!parse_target("0.70::TEST", &addr, &user)) return 17;
    if (!parse_target("-1.70::TEST", &addr, &user)) return 18;
    return 0;
''',
    ),
    "dnping": (
        "userspace/dnping/dnping.c",
        r'''
    long value = 0;
    if (parse_positive("3", 10, &value) || value != 3) return 10;
    if (parse_positive("0003", 10, &value)) return 11;
    if (!parse_positive("+3", 10, &value)) return 12;
    if (!parse_positive(" 3", 10, &value)) return 13;
    if (!parse_positive("-3", 10, &value)) return 14;
    if (!parse_positive("11", 10, &value)) return 15;
    return 0;
''',
    ),
}

with tempfile.TemporaryDirectory() as tmp:
    for name, (source, checks) in CASES.items():
        probe = Path(tmp) / f"{name}_probe.c"
        binary = Path(tmp) / name
        probe.write_text(
            '#define main shipping_main\n'
            f'#include "{root / source}"\n'
            '#undef main\n'
            f'int main(void) {{{checks}}}\n',
            encoding='utf-8',
        )
        subprocess.run(
            ["cc", "-O2", "-std=c11", "-Wall", "-Wextra", "-Werror",
             "-ffunction-sections", "-fdata-sections",
             f"-I{root / 'include/uapi'}",
             f"-I{root / 'userspace/libdnet/include'}",
             str(probe), "-Wl,--gc-sections", "-o", str(binary)],
            check=True, capture_output=True, text=True,
        )
        check = subprocess.run([str(binary)], capture_output=True, text=True)
        assert check.returncode == 0, (name, check.returncode, check.stderr)

print('phone and dnping strict decimal argument regression passed')
