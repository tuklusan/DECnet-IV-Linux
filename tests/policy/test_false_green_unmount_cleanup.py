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

"""Never delete a still-mounted PP-10 exhaustion fixture after failed umount."""

from pathlib import Path
import subprocess
import tempfile

SOURCE = Path(__file__).resolve().parents[2] / ".github/workflows/false-green.yml"


def exercise(failed: str | None, original_exit: int) -> None:
    source = SOURCE.read_text(encoding="utf-8")
    anchor = source.index("name: Prove literal evidence exhaustion fails closed")
    start = source.index("          cleanup() {\n", anchor)
    end = source.index("          trap cleanup EXIT", start)
    # Take the original shell function out of YAML. All mount tools are mocked.
    block = "\n".join(
        line[10:] if line.startswith("          ") else line
        for line in source[start:end].splitlines()
    )
    with tempfile.TemporaryDirectory(prefix="dniv-false-green-unmount-") as work:
        log = Path(work) / "mock-actions"
        script = f'''set -euo pipefail
bytes_root=/tmp/dniv-mock-bytes
inodes_root=/tmp/dniv-mock-inodes
tmp=/tmp/dniv-mock-owned-work
MOCK_LOG="{log}"
mountpoint() {{
  [[ "$2" == "$bytes_root" || "$2" == "$inodes_root" ]]
}}
sudo() {{
  printf 'umount:%s\\n' "$*" >> "$MOCK_LOG"
  if [[ "$*" == "umount {failed}" ]]; then return 19; fi
}}
rm() {{
  printf 'rm:%s\\n' "$*" >> "$MOCK_LOG"
}}
{block}
trap cleanup EXIT
exit {original_exit}
'''
        result = subprocess.run(
            ["bash", "-c", script], capture_output=True, text=True, timeout=5
        )
        events = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
        deletions = [event for event in events if event.startswith("rm:")]
        if failed is not None:
            if not result.returncode or deletions:
                raise AssertionError(
                    f"unmount failure did not fail closed: {failed} "
                    f"status={result.returncode} events={events}"
                )
        elif result.returncode != original_exit or deletions != [
            "rm:-rf -- /tmp/dniv-mock-owned-work"
        ]:
            raise AssertionError(
                f"successful cleanup changed original status or skipped deletion: "
                f"status={result.returncode} events={events}"
            )


def main() -> None:
    for failed in ("/tmp/dniv-mock-bytes", "/tmp/dniv-mock-inodes", None):
        for status in (0, 7):
            exercise(failed, status)
    print("False-green PP-10 failed-unmount preservation regression passed")


if __name__ == "__main__":
    main()
