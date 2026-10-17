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

"""Execute actual Area-31 survey under offline mocked NICE/MIRROR calls."""

from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
source = (ROOT / "tests/lab/dniv-area31-smoke.sh").read_text()
assert source.count("survey_live=0\n") == 1
loop = source.split("survey_live=0\n", 1)[1].split("\nunset vax_user", 1)[0]
assert 'done <"$survey_manifest"' in loop

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    manifest = tmp / "manifest.tsv"
    operations = tmp / "operations.txt"
    manifest.write_text(
        "31.1\tIMPVAX\tReachable\n"
        "31.2\tQCOCAL\tReachable\n"
        "31.3\tPYRTR\tOn\n"
        "31.13\tMIM\tReachable\n"
        "31.25\tFOREIGN\tReachable\n"
        "31.26\tSLEEP\tUnreachable\n"
    )
    test_shell = r'''
set -eu
linux_node=31.70
linux_name=LINUX
gateway_node=31.3
target=31.1
qcocal=31.2
survey_manifest=$1
operations=$2
parse_node() { case "$1" in 31.*) return 0;; *) return 1;; esac; }
fail() { echo "unexpected failure: $1" >&2; exit 7; }
timeout() { printf '%s %s\n' "$3" "$4" >>"$operations"; return 0; }
''' + "survey_live=0\n" + loop
    run = subprocess.run(["sh", "-c", test_shell, "fixture", str(manifest),
                          str(operations)], capture_output=True, text=True)
    assert run.returncode == 0, (run.stdout, run.stderr)
    calls = operations.read_text().splitlines()
    assert [c for c in calls if c.startswith("--nice-summary ")] == [
        "--nice-summary 31.1", "--nice-summary 31.2",
        "--nice-summary 31.13", "--nice-summary 31.25"]
    assert [c for c in calls if c.startswith("--mirror-once ")] == [
        "--mirror-once 31.1", "--mirror-once 31.2"]
    assert "node=31.13" in run.stdout and "mirror=skipped" in run.stdout
# PP-12 protects external QCOCAL: the documented remote scope must match the
# actual read-only Area-31 probe, not older temporary-alias or HTTP/task tests.
manual = (ROOT / "docs/TEST_LAB.md").read_text(encoding="utf-8")
pp12 = manual.split("### PP-12 exact-source real-peer mode\n", 1)[1].split(
    "\nFor direct host-TAP", 1)[0]
assert "QCOCAL" in pp12 and "read-only" in pp12
assert "`dncopy --probe`" in pp12 and "`dndir`" in pp12
assert "`dnnice`" in pp12 and "`dnping`" in pp12
assert "local/SIMH" in pp12 and "HTTP/task" in pp12
assert "Not tested in lab environment" in pp12
assert "safe temporary QCOCAL DAP alias checks" not in pp12
assert "existing login/FAL/NICE/MIRROR/HTTP/task coverage" not in pp12
actual = source.split('if [ -n "$qcocal" ]; then\n', 2)[-1].split(
    "\nsurvey_live=0", 1)[0]
for required in ('/usr/local/bin/dncopy --probe "$qcocal"',
                 '/usr/local/bin/dndir "$qcocal"',
                 '/usr/local/bin/dnnice "$qcocal" summary',
                 '/usr/local/bin/dnping -q -c 2'):
    assert required in actual, required
for forbidden in ('--put', '--delete', '--rename', 'dnhttp', 'dntask'):
    assert forbidden not in actual, forbidden
print("Area-31 unknown-node active-probe exclusion passed")
