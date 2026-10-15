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

"""No durable PP-11 PASS marker before *every* final interop assertion."""

from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tests/lab/run-interop.sh"


def check():
    source = SOURCE.read_text()
    anchor = 'if [[ "$pp11_pressure" == 1 ]]; then\n    grep -Fq "DNIV-INTEROP-PP11-PRESSURE-PASS'
    tail = source[source.rfind(anchor):]
    assert tail.startswith(anchor) and tail.endswith('arch=$host_arch"\n')
    with tempfile.TemporaryDirectory(prefix="dniv-pp11-evidence-") as tmp:
        directory = Path(tmp)
        for case in ("good", "missing-recovery", "candidate-fail", "ref1-fail", "ref2-fail"):
            candidate = directory / "candidate.log"
            ref1 = directory / "ref1.log"
            ref2 = directory / "ref2.log"
            evidence = directory / "pressure.env"
            candidate.write_text("DNIV-INTEROP-PP11-PRESSURE-PASS session=1 scenario=2 rounds=3\n"
                                 + ("" if case == "missing-recovery" else
                                    "DNIV-INTEROP-RECOVERED session=1 scenario=2\n")
                                 + ("DNIV-INTEROP-FAIL\n" if case == "candidate-fail" else ""))
            ref1.write_text("DNIV-REF-FAIL\n" if case == "ref1-fail" else "")
            ref2.write_text("DNIV-REF-FAIL\n" if case == "ref2-fail" else "")
            evidence.write_text("events=10000\nvalidator=PENDING\nresult=PENDING\n")
            script = (
                "set -euo pipefail\n"
                f'candidate_log="{candidate}"\nref1_log="{ref1}"\nref2_log="{ref2}"\n'
                f'pressure_env="{evidence}"\n'
                'pp11_pressure=1\nsession=1\nscenario=2\nhost_arch=amd64\nreference=route20\n'
                + tail
            )
            result = subprocess.run(["bash", "-c", script], capture_output=True,
                                    text=True, timeout=5)
            transcript = evidence.read_text()
            if case == "good":
                assert result.returncode == 0, (result.returncode, result.stderr)
                assert transcript.count("validator=PASS\n") == 1
                assert transcript.count("result=PASS\n") == 1
                assert "PENDING" not in transcript
            else:
                assert result.returncode != 0, case
                assert "result=PASS" not in transcript, (case, transcript)
                assert "validator=PASS" not in transcript, (case, transcript)
    print("interop final PP-11 evidence assertions source regression passed")


if __name__ == "__main__":
    check()
