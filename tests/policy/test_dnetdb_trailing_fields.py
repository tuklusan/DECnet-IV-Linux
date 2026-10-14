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

"""Reject trailing non-whitespace after an otherwise valid DECnet node entry."""

import os
import shlex
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

HARNESS = r"""
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "dnetdb.c"

/* The parser is under test, not numeric addressing. */
int dnet_pton(int family, const char *src, void *addr)
{
    (void)family;
    memset(addr, 0, sizeof(struct dn_naddr));
    return strcmp(src, "31.70") == 0 ? 1 : 0;
}

static int check(const char *label, const char *input, int expected_fields)
{
    FILE *file = tmpfile();
    struct node_record record;
    int rc, saved;
    size_t size = strlen(input);

    if (!file)
        return 1;
    if (fwrite(input, 1U, size, file) != size) {
        fclose(file);
        return 1;
    }
    rewind(file);
    errno = 0;
    rc = read_node_record(file, &record);
    saved = errno;
    fclose(file);
    if (expected_fields >= 0 && rc == 1 &&
        record.fields == expected_fields && !strcmp(record.name, "DN70"))
        return 0;
    if (expected_fields < 0 && rc == -1 && saved == EINVAL)
        return 0;
    fprintf(stderr, "%s: rc=%d, fields=%d, errno=%d, want fields=%d\n",
            label, rc, record.fields, saved, expected_fields);
    return 1;
}


static int check_name_length(size_t length, int expected_errno)
{
    char name[300], line[400];
    FILE *file;
    struct node_record record;
    int rc, saved;
    size_t size;

    if (length >= sizeof(name))
        return 1;
    memset(name, 'A', length);
    name[length] = '\0';
    if (snprintf(line, sizeof(line), "node 31.70 name %s\\n", name) >=
        (int)sizeof(line))
        return 1;
    file = tmpfile();
    if (!file)
        return 1;
    size = strlen(line);
    if (fwrite(line, 1U, size, file) != size) {
        fclose(file);
        return 1;
    }
    rewind(file);
    errno = 0;
    rc = read_node_record(file, &record);
    saved = errno;
    fclose(file);
    if (!expected_errno && rc == 1 && record.fields == 4 &&
        !strcmp(record.name, name))
        return 0;
    if (expected_errno && rc == -1 && saved == expected_errno)
        return 0;
    fprintf(stderr, "node-name length %zu: rc=%d errno=%d, expected=%d\\n",
            length, rc, saved, expected_errno);
    return 1;
}

int main(void)
{
    int failed = 0;

    failed |= check("valid executor+device",
                    "executor 31.70 name DN70 line eth0\n", 6);
    failed |= check("valid executor", "executor 31.70 name DN70\n", 4);
    failed |= check("valid node", "node 31.70 name DN70\n", 4);
    failed |= check("hidden seventh token",
                    "executor 31.70 name DN70 line eth0 HIDDEN\n", -1);
    failed |= check("hidden comment suffix",
                    "executor 31.70 name DN70 line eth0 #hidden\n", -1);
    failed |= check("hidden control suffix",
                    "executor 31.70 name DN70 line eth0 !\n", -1);
    failed |= check("too many executor tokens",
                    "executor 31.70 name DN70 line eth0 EXTRA MORE\n", -1);
    failed |= check("stray node field", "node 31.70 name DN70 extra\n", -1);
    failed |= check_name_length(6U, 0);
    failed |= check_name_length(7U, ENAMETOOLONG);
    failed |= check_name_length(16U, ENAMETOOLONG);
    failed |= check_name_length(256U, ENAMETOOLONG);
    failed |= check_name_length(257U, EINVAL);
    if (!failed)
        puts("libdnet node database rejects hidden trailing fields and overlong names");
    return failed ? 1 : 0;
}
"""


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="dniv-dnetdb-fields-") as directory:
        source = Path(directory) / "check.c"
        binary = Path(directory) / "check"
        source.write_text(HARNESS, encoding="utf-8")
        subprocess.run(shlex.split(os.environ.get("CC", "cc")) + [
            "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
            "-I" + str(ROOT / "userspace/libdnet"),
            "-I" + str(ROOT / "userspace/libdnet/include"),
            "-I" + str(ROOT / "include/uapi"),
            str(source), "-o", str(binary)
        ], check=True, timeout=60)
        subprocess.run([str(binary)], check=True, timeout=10)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
