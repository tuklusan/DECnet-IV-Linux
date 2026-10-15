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

"""Only a Route20 daemon owned by this VDE2 invocation may be stopped."""

from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ("prove-vde2-cross-runner.sh", "prove-vde2.sh")


def check_script(script_path):
    original = script_path.read_text()
    begin = original.index("cleanup() {\n")
    end = original.index("\n}\ntrap cleanup EXIT INT TERM", begin) + 3
    cleanup = original[begin:end]
    assert "route20_pid" in cleanup, "cleanup must scope Route20 ownership"
    assert 'if [[ -e /var/run/route20.pid ]]; then' in original, (
        "preexisting Route20 service must prevent server launch"
    )
    assert original.index('if [[ -e /var/run/route20.pid ]]; then') < original.index(
        'sudo "$work/route20/Route20/route20" "$work/route20.ini"'
    )
    for owned, expected in (("", False), ("32145", True), ("11111", False)):
        with tempfile.TemporaryDirectory(prefix="dniv-route20-ownership-") as tmp:
            pidfile = Path(tmp) / "route20.pid"
            log = Path(tmp) / "sudo.log"
            pidfile.write_text("32145\n")
            test_cleanup = cleanup.replace("/var/run/route20.pid", str(pidfile))
            script = f'''set -euo pipefail
work="{tmp}/scratch"
server_sock="{tmp}/switch"
mkdir -p "$work"
route20_pid="{owned}"
stop_pid() {{ :; }}
stop_process_tree() {{ :; }}
stop_switch() {{ :; }}
sudo() {{ printf '%s\\n' "$*" >> "{log}"; }}
{test_cleanup}
cleanup
'''
            result = subprocess.run(["bash", "-c", script], capture_output=True,
                                    text=True, timeout=5)
            assert result.returncode == 0, (result.stdout, result.stderr)
            actions = log.read_text().splitlines() if log.exists() else []
            killed = "kill 32145" in actions
            assert killed is expected, (owned, actions)
            assert ("rm -f " + str(pidfile) in actions) is expected, actions
            if not expected:
                assert pidfile.exists(), "unowned pidfile was deleted"

def check():
    for script in SCRIPTS:
        check_script(ROOT / "tests/lab" / script)
    print("VDE2 Route20 PID ownership and no-disruption source regression passed")


if __name__ == "__main__":
    check()
