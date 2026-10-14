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

"""Source-derived Area31 guest proof rejects failed/stalled QEMU after marker."""

from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tests/lab/prove-area31.sh"


def run_case(tail: str, scenario: str) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory(prefix="dniv-area31-exit-") as tmp:
        work = Path(tmp)
        log = work / "guest.log"
        if scenario == "good":
            command = "echo DNIV-AREA31-NATIVE-PASS; exit 0"
        elif scenario == "failed":
            command = "echo DNIV-AREA31-NATIVE-PASS; exit 17"
        elif scenario == "stuck":
            command = "echo DNIV-AREA31-NATIVE-PASS; sleep 5"
        else:
            raise AssertionError(scenario)

        setup = (
            'set -euo pipefail\n'
            'area31_arch=amd64\n'
            'vm_log="$1"\n'
            'show_vm_log() { cat "$vm_log" >&2; }\n'
            'bash -c "$2" >"$vm_log" 2>&1 &\n'
            'vm_pid=$!\n'
        )
        runnable = tail.replace("proof_wait=360", "proof_wait=3").replace(
            '[[ "$area31_arch" == arm64 ]] && proof_wait=540', ':'
        ).replace("seq 1 120", "seq 1 3").replace("sleep 1", "sleep 0.05")
        if runnable == tail:
            raise AssertionError("Area31 source has changed unexpectedly")
        script = work / "source-tail.sh"
        script.write_text(setup + runnable, encoding="utf-8")
        subprocess.run(["bash", "-n", str(script)], check=True)
        return subprocess.run(
            ["bash", str(script), str(log), command], capture_output=True,
            text=True, timeout=3,
        )


def main() -> None:
    text = SOURCE.read_text(encoding="utf-8")
    tail = text[text.index("proof_wait=360\n"):]
    if 'if ! wait "$vm_pid"; then' not in tail or \
            'kill -0 "$vm_pid" 2>/dev/null' not in tail or \
            "area31-proof: candidate marked PASS but did not shut down" not in tail:
        raise AssertionError("post-PASS QEMU exit must be strictly checked and bounded")
    good = run_case(tail, "good")
    if good.returncode != 0 or "path pass" not in good.stdout:
        raise AssertionError(f"valid shutdown was rejected: {good}")
    for scenario in ("failed", "stuck"):
        result = run_case(tail, scenario)
        if result.returncode == 0 or "path pass" in result.stdout:
            raise AssertionError(f"{scenario} child falsely certified: {result}")
    print("Area31 source-derived guest PASS requires bounded successful VM shutdown")


if __name__ == "__main__":
    main()
