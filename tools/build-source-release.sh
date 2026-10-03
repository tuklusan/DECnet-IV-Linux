#!/usr/bin/env bash
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
set -euo pipefail
if [[ $# -ne 3 ]]; then echo "usage: $0 OUTPUT_DIR VERSION SOURCE_SHA" >&2; exit 2; fi
output_dir=$1
version=$2
source_sha=$3
case "$version" in
  ""|*[!A-Za-z0-9._+-]*|[.-]*)
    echo "build-source-release: invalid version: $version" >&2
    exit 2
    ;;
esac
root=$(git rev-parse --show-toplevel)
commit=$(git -C "$root" rev-parse --verify "$source_sha^{commit}")
epoch=$(git -C "$root" show -s --format=%ct "$commit")
name="DECnet-IV-Linux-$version"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/$name" "$output_dir"
git -C "$root" archive --format=tar "$commit" | tar -xf - -C "$work/$name"
cat >"$work/$name/SOURCE-METADATA" <<EOF_METADATA
version=$version
source_sha=$commit
source_date_epoch=$epoch
EOF_METADATA
for forbidden in .git '*.qcow2' '*.raw' '*.img' '*.iso' '*.ko' '*.o'; do
  if find "$work/$name" -name "$forbidden" -print -quit | grep -q .; then echo "build-source-release: forbidden generated payload matched $forbidden" >&2; exit 2; fi
done
for required in build.sh install.sh uninstall.sh INSTALL.md docs/DELIVERY.md docs/FEATURES.md docs/COMPONENTS.md LICENSE; do
  test -r "$work/$name/$required" || { echo "build-source-release: required release member missing: $required" >&2; exit 2; }
done
archive="$output_dir/$name.tar.xz"
(
  cd "$work"
  find "$name" -print0 | LC_ALL=C sort -z |
    tar --null --files-from=- --no-recursion --format=posix --owner=0 --group=0 --numeric-owner --mtime="@$epoch" --pax-option=delete=atime,delete=ctime -cJf "$archive"
)
(cd "$output_dir" && sha256sum "$(basename "$archive")" >"$(basename "$archive").sha256")
printf '%s\n' "$archive"
