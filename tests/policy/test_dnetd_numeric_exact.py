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

"""Reject sign and overflow aliases in actual dnetd numeric object parser."""

from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
source = (root / 'userspace/dnetd/dnetd.c').read_text(encoding='utf-8')
begin = source.index('static int parse_unsigned(')
end = source.index('static int parse_options(', begin)
parser = source[begin:end]
program = '#include <errno.h>\n#include <stdlib.h>\n' + parser + r'''
int main(int argc, char **argv)
{
    unsigned long value = 0;
    int rc;
    if (argc != 3) return 3;
    rc = parse_unsigned(argv[1], 255UL, &value);
    if (argv[2][0] == 'Y')
        return rc == 0 && value == 241UL ? 0 : 1;
    return rc != 0 ? 0 : 1;
}
'''
with tempfile.TemporaryDirectory() as temp:
    file = Path(temp) / 'numeric.c'
    exe = Path(temp) / 'numeric'
    file.write_text(program, encoding='utf-8')
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', str(file),
                    '-o', str(exe)], check=True)
    for value in ('241', '0241'):
        assert subprocess.run([str(exe), value, 'Y'], timeout=3).returncode == 0, value
    bad = ('-18446744073709551615', '+241', ' 241', '241 ', '256',
           '18446744073709551617', '-1', '1x', '')
    for value in bad:
        assert subprocess.run([str(exe), value, 'N'], timeout=3).returncode == 0, value
print('dnetd numeric service identity regression passed')
