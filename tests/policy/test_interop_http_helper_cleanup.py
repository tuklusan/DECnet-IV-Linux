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

"""Source-derived, non-privileged interop HTTP helper child-lifecycle test."""

from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tests/lab/run-interop.sh"


def scenario(functions: str, name: str) -> None:
    with tempfile.TemporaryDirectory(prefix="dniv-http-helper-") as td:
        script = Path(td) / "exercise.sh"
        script.write_text(
            "#!/usr/bin/env bash\nset -euo pipefail\n"
            + functions
            + "\nbridge_owned=0\ntap_candidate_owned=0\n"
            "tap_reference_owned=0\nhost_pydecnet_api_owned=0\n"
            f"sleep 60 & {name}=$!\n"
            "cleanup\n"
            f"if kill -0 \"${name}\" 2>/dev/null; then\n"
            f"    kill \"${name}\" 2>/dev/null || true\n"
            f"    wait \"${name}\" 2>/dev/null || true\n"
            f"    echo \"child not reaped: {name}\" >&2\n"
            "    exit 45\n"
            "fi\n"
        )
        subprocess.run(["bash", "-n", str(script)], check=True)
        check = subprocess.run(
            ["bash", str(script)], text=True, capture_output=True, timeout=10
        )
        if check.returncode:
            raise AssertionError(
                f"{name} survived the parent cleanup: "
                f"exit={check.returncode} stderr={check.stderr!r}"
            )


def main() -> None:
    source = SOURCE.read_text()
    begin = source.index("terminate_pid() {")
    end = source.index("trap cleanup EXIT INT TERM", begin)
    functions = source[begin:end]
    assert "cleanup() {" in functions and "terminate_pid() {" in functions
    for name in ("pyhttp_pid", "pyhttp_object_pid"):
        scenario(functions, name)
        assert f"    unset {name}\n" in source, name
    print("interop HTTP server children terminated and reaped on harness cleanup")


if __name__ == "__main__":
    main()
