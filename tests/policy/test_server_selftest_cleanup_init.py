#!/usr/bin/env python3
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

"""Early selftest errors must not pass uninitialized paths to unlink()."""

from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def run(app: str, cc: str, temp: Path) -> None:
    source = ROOT / "userspace" / app / f"{app}.c"
    expected_prefix = f"/tmp/{app}-"
    probe = temp / f"{app}-{cc}.c"
    exe = temp / f"{app}-{cc}"
    probe.write_text(
        '#define _GNU_SOURCE\n'
        '#include <errno.h>\n#include <stdio.h>\n#include <string.h>\n'
        'static int unowned = 0;\n'
        'static int fail_mkstemp(char *name) { (void)name; errno = EACCES; return -1; }\n'
        'static int audit_unlink(const char *path) {\n'
        f'  if (path[0] && strncmp(path, "{expected_prefix}", {len(expected_prefix)})) unowned++;\n'
        '  return 0;\n}\n'
        '#define mkstemp fail_mkstemp\n'
        '#define unlink audit_unlink\n'
        '#define main excluded_original_main\n'
        f'#include "{source.as_posix()}"\n'
        '#undef main\n#undef unlink\n#undef mkstemp\n'
        'int main(void) { (void)selftest(); return unowned ? 1 : 0; }\n',
        encoding='utf-8',
    )
    subprocess.run(
        [cc, '-O0', '-ftrivial-auto-var-init=pattern', '-Wall', '-Wextra',
         '-Werror', '-I', str(ROOT / 'include/uapi'), '-o', str(exe), str(probe)],
        check=True, capture_output=True, text=True,
    )
    result = subprocess.run([str(exe)], capture_output=True, timeout=10)
    if result.returncode:
        raise AssertionError(
            f'{app} {cc} passed an uninitialized or foreign path to unlink on '
            f'preparation failure (rc={result.returncode})'
        )


def main() -> None:
    compilers = [cc for cc in ('gcc', 'clang') if shutil.which(cc)]
    if not compilers:
        raise AssertionError('no C compiler for actual server cleanup regression')
    with tempfile.TemporaryDirectory(prefix='dniv-selftest-cleanup-') as directory:
        for app in ('dnfald', 'dnhttpd'):
            for cc in compilers:
                run(app, cc, Path(directory))
    print('FAL/HTTP selftest early-failure cleanup ownership passed')


if __name__ == '__main__':
    main()
