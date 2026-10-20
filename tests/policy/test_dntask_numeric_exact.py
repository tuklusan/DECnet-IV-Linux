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

"""Reject signed/blank DECnet and timeout arguments without opening sockets."""

from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]

HARNESS = r'''
#define main shipping_main
#define socket stub_socket
#include "__SOURCE__"
#undef main
#undef socket
int stub_socket(int domain, int type, int protocol) {
    (void)domain; (void)type; (void)protocol;
    errno = EAFNOSUPPORT;
    return -1;
}
int main(void) {
    struct task_spec spec;
    if (parse_spec("31.71::", &spec) ||
        spec.addr != ((31 << 10) | 71) || strcmp(spec.object, "TASK"))
        return 10;
    if (parse_spec("031.00071::TASK", &spec)) return 11;
    if (!parse_spec("+31.71::TASK", &spec)) return 12;
    if (!parse_spec("31.+71::TASK", &spec)) return 13;
    if (!parse_spec(" 31.71::TASK", &spec)) return 14;
    if (!parse_spec("31. 71::TASK", &spec)) return 15;
    if (!parse_spec("-1.71::TASK", &spec)) return 16;
    if (!parse_spec("31.1024::TASK", &spec)) return 17;
    char *plus_arg[] = {"dntask", "-t", "+1", "31.71::", NULL};
    if (shipping_main(4, plus_arg) != 2) return 18;
    char *blank_arg[] = {"dntask", "-T", " 1", "31.71::", NULL};
    if (shipping_main(4, blank_arg) != 2) return 19;
    char *minus_zero[] = {"dntask", "-t", "-0", "31.71::", NULL};
    if (shipping_main(4, minus_zero) != 2) return 20;
    return 0;
}
'''
with tempfile.TemporaryDirectory() as tmp:
    source = Path(tmp) / 'probe.c'
    binary = Path(tmp) / 'probe'
    source.write_text(HARNESS.replace('__SOURCE__', str(root / 'userspace/dntask/dntask.c')))
    subprocess.run(['cc', '-std=c11', '-D_POSIX_C_SOURCE=200809L', '-O2', '-Wall', '-Wextra', '-Werror',
                    f'-I{root / "include/uapi"}', str(source), '-o', str(binary)],
                   check=True, capture_output=True, text=True)
    result = subprocess.run([str(binary)], capture_output=True, text=True)
    assert result.returncode == 0, (result.returncode, result.stderr)
print('dntask exact numeric CLI regression passed')
