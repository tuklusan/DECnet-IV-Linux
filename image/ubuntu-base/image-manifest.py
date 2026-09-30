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

import hashlib
import os
import stat
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: image-manifest.py ROOT OUTPUT")

root = os.path.abspath(sys.argv[1])
output = sys.argv[2]
skip_roots = {"proc", "sys", "dev", "run", "tmp", "var/tmp"}

def skipped(rel):
    return any(rel == p or rel.startswith(p + "/") for p in skip_roots)

rows = []
for base, dirs, files in os.walk(root, topdown=True, followlinks=False):
    relbase = os.path.relpath(base, root)
    if relbase == ".":
        relbase = ""
    dirs[:] = sorted(d for d in dirs if not skipped(f"{relbase}/{d}".strip("/")))
    names = sorted(dirs + files)
    for name in names:
        path = os.path.join(base, name)
        rel = f"{relbase}/{name}".strip("/")
        if skipped(rel):
            continue
        st = os.lstat(path)
        mode = stat.S_IMODE(st.st_mode)
        common = f"{rel}\t{st.st_uid}:{st.st_gid}\t{mode:04o}"
        if stat.S_ISREG(st.st_mode):
            h = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(chunk)
            rows.append(f"f\t{common}\t{st.st_size}\t{h.hexdigest()}")
        elif stat.S_ISLNK(st.st_mode):
            rows.append(f"l\t{common}\t{os.readlink(path)}")
        elif stat.S_ISDIR(st.st_mode):
            rows.append(f"d\t{common}")
        elif stat.S_ISCHR(st.st_mode) or stat.S_ISBLK(st.st_mode):
            kind = "c" if stat.S_ISCHR(st.st_mode) else "b"
            rows.append(f"{kind}\t{common}\t{os.major(st.st_rdev)}:{os.minor(st.st_rdev)}")
        elif stat.S_ISFIFO(st.st_mode):
            rows.append(f"p\t{common}")
        elif stat.S_ISSOCK(st.st_mode):
            rows.append(f"s\t{common}")
        else:
            raise SystemExit(f"unsupported file type in image: {rel}")

with open(output, "w", encoding="utf-8", newline="\n") as f:
    for row in sorted(rows):
        f.write(row + "\n")
