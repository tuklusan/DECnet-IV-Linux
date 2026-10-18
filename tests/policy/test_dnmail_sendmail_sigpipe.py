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

"""Verify early-exiting sendmail cannot terminate daemon with SIGPIPE."""

import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
HARNESS = r'''
#define main source_daemon_main
#include "userspace/dnmail/dnmaild.c"
#undef main
int main(int argc, char **argv)
{
    pid_t worker;
    int status;
    if (argc != 2) return 40;
    worker = fork();
    if (worker < 0) return 41;
    if (!worker) {
        FILE *staged = tmpfile();
        char bytes[4096];
        pid_t child = -1;
        int input_fd = -1;
        int result;
        alarm(12U);
        if (!staged || configure_sigpipe()) _exit(42);
        memset(bytes, 'X', sizeof(bytes));
        for (int i = 0; i < 512; i++)
            if (fwrite(bytes, 1, sizeof(bytes), staged) != sizeof(bytes))
                _exit(43);
        result = start_complete_sendmail(staged, "/bin/false", &input_fd, &child);
        if (input_fd >= 0 || child > 0)
            abort_sendmail(input_fd, child);
        fclose(staged);
        _exit(result == -1 ? 0 : 44);
    }
    if (waitpid(worker, &status, 0) != worker ||
        !WIFEXITED(status) || WEXITSTATUS(status) != 0)
        return 45;
    if (configure_sigpipe() || start_sendmail(argv[1], &argc, &worker))
        return 46;
    if (close(argc)) {
        abort_sendmail(-1, worker);
        return 47;
    }
    if (waitpid(worker, &status, 0) != worker ||
        !WIFEXITED(status) || WEXITSTATUS(status) != 0)
        return 48;
    return 0;
}
'''
CHILD = r'''
#include <signal.h>
int main(void)
{
    struct sigaction disposition;
    if (sigaction(SIGPIPE, 0, &disposition)) return 3;
    return disposition.sa_handler == SIG_DFL ? 0 : 4;
}
'''

def check():
    with tempfile.TemporaryDirectory(prefix="dniv-sendmail-sigpipe-") as temp:
        work = Path(temp)
        parent_source = work / "daemon-case.c"
        child_source = work / "child.c"
        parent_bin = work / "daemon-case"
        child_bin = work / "child"
        parent_source.write_text(HARNESS, encoding="utf-8")
        child_source.write_text(CHILD, encoding="utf-8")
        cc = os.environ.get("CC", "cc")
        for args in (
            [cc, "-std=gnu11", "-Wall", "-Wextra", "-Werror", "-I", str(ROOT),
             "-I", str(ROOT / "include/uapi"), str(parent_source), "-o", str(parent_bin)],
            [cc, "-std=gnu11", "-Wall", "-Wextra", "-Werror", str(child_source),
             "-o", str(child_bin)],
        ):
            subprocess.run(args, check=True, capture_output=True, text=True, timeout=30)
        result = subprocess.run([str(parent_bin), str(child_bin)],
                                capture_output=True, text=True, timeout=20)
        assert result.returncode == 0, (
            result.returncode, result.stdout, result.stderr)
    print("dnmail sendmail SIGPIPE daemon-isolation regression passed")

if __name__ == "__main__":
    check()
