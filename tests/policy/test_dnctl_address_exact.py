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

"""Compile and execute the actual dnctl address parser without device access."""

from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
code = (ROOT / 'userspace/dnctl/dnctl.c').read_text(encoding='utf-8')
begin = code.index('static int parse_address(')
end = code.index('static int normalize_name(', begin)
parser = code[begin:end]
harness = '''#include <errno.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
typedef uint16_t __u16;
#define DNIV_ADDR(area,node) (((area) << 10) | (node))
''' + parser + '''
int main(int argc, char **argv)
{
    __u16 address = 0;
    int rc;
    if (argc != 3) return 3;
    rc = parse_address(argv[1], &address);
    if (argv[2][0] == 'Y')
        return rc == 0 && address == (31 * 1024 + 70) ? 0 : 1;
    return rc != 0 ? 0 : 1;
}
'''
with tempfile.TemporaryDirectory() as temp:
    file = Path(temp) / 'parser.c'
    binary = Path(temp) / 'parser'
    file.write_text(harness, encoding='utf-8')
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', str(file),
                    '-o', str(binary)], check=True)
    valid = ('31.70', '031.00070')
    invalid = ('-18446744073709551615.70', '31.-18446744073709551615',
               '+31.70', '31.+70', ' 31.70', '31. 70',
               '18446744073709551617.70', '31.18446744073709551617',
               '0.70', '64.70', '31.0', '31.1024', '31.70x')
    for value, flag in ((x, 'Y') for x in valid):
        assert subprocess.run([str(binary), value, flag], timeout=3).returncode == 0, value
    for value in invalid:
        assert subprocess.run([str(binary), value, 'N'], timeout=3).returncode == 0, value
print('dnctl numeric identity strict parser regression passed')
