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

"""Executable false-green regressions for exact-source acceptance controls."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INTEGRITY = ROOT / "tools" / "integrity_scan.py"
SCRATCH = ROOT / "tools" / "scratch_state.py"
WORKFLOW_GUARD = ROOT / "tools" / "workflow_guard.sh"
EVIDENCE_GUARD = ROOT / "tools" / "evidence_guard.py"

SPEC = importlib.util.spec_from_file_location("dniv_lab_false_green", ROOT / "tests/lab/dniv_lab.py")
assert SPEC and SPEC.loader
LAB = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = LAB
SPEC.loader.exec_module(LAB)


def run(root: Path, *args: str, check: bool = True, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=root,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )


def expect_failure(result: subprocess.CompletedProcess[str], marker: str, label: str) -> None:
    output = result.stdout + result.stderr
    if result.returncode == 0 or marker not in output:
        raise SystemExit(f"false-green regression did not reject {label}: {output}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="dniv-false-green-") as temporary:
        root = Path(temporary)
        run(root, "git", "init", "-q", "-b", "main")
        run(root, "git", "config", "user.name", "False Green Test")
        run(root, "git", "config", "user.email", "false-green@example.invalid")

        payload = root / "payload.txt"
        payload.write_text("base\n", encoding="utf-8")
        run(root, "git", "add", "payload.txt")
        run(root, "git", "commit", "-q", "-m", "base")
        parent = run(root, "git", "rev-parse", "HEAD").stdout.strip()

        payload.write_text("candidate\n", encoding="utf-8")
        run(root, "git", "add", "payload.txt")
        run(root, "git", "commit", "-q", "-m", "candidate")
        head = run(root, "git", "rev-parse", "HEAD").stdout.strip()

        baseline = root / "baseline.json"
        final = root / "final.json"
        run(
            root, sys.executable, str(INTEGRITY), "--rev", head,
            "--pass-id", "baseline", "--output", str(baseline),
        )

        payload.write_text("tampered checkout\n", encoding="utf-8")
        result = run(
            root, sys.executable, str(INTEGRITY), "--rev", head,
            "--pass-id", "tampered", "--baseline", str(baseline),
            "--output", str(final), check=False,
        )
        expect_failure(result, "tracked checkout differs", "tracked checkout mutation")
        run(root, "git", "restore", "payload.txt")

        corrupt = root / "corrupt-baseline.json"
        baseline_data = json.loads(baseline.read_text(encoding="utf-8"))
        baseline_data["scan_sha256"] = "0" * 64
        corrupt.write_text(json.dumps(baseline_data) + "\n", encoding="utf-8")
        result = run(
            root, sys.executable, str(INTEGRITY), "--rev", head,
            "--pass-id", "corrupt", "--baseline", str(corrupt),
            "--output", str(final), check=False,
        )
        expect_failure(result, "scan differs from baseline", "corrupt integrity manifest")

        state = root / "state"
        result = run(
            root, sys.executable, str(SCRATCH), "init", "--dir", str(state),
            "--workflow", "false-green", "--job", "lineage",
            "--source-sha", head, "--parent-run-id", "1", "--expected-sha", parent,
            check=False,
        )
        expect_failure(result, "does not match parent expected SHA", "wrong parent candidate")

        run(
            root, sys.executable, str(SCRATCH), "init", "--dir", str(state),
            "--workflow", "false-green", "--job", "lineage",
            "--source-sha", head, "--parent-run-id", "1", "--expected-sha", head,
        )
        state_path = state / "state.json"
        state_data = json.loads(state_path.read_text(encoding="utf-8"))
        state_data["source_tree"] = "0" * 40
        state_path.write_text(json.dumps(state_data) + "\n", encoding="utf-8")
        result = run(root, sys.executable, str(SCRATCH), "verify", "--dir", str(state), check=False)
        expect_failure(result, "checkout no longer matches recorded source commit/tree", "stale scratch lineage")

        run(
            root, sys.executable, str(SCRATCH), "init", "--dir", str(state),
            "--workflow", "false-green", "--job", "guard",
            "--source-sha", head, "--parent-run-id", "1", "--expected-sha", head,
        )
        env = os.environ.copy()
        env["GITHUB_REF"] = "refs/heads/not-main"
        result = run(root, "bash", str(WORKFLOW_GUARD), str(state), head, "main", check=False, env=env)
        expect_failure(result, "acceptance workflows must run from main", "non-main acceptance")

        env["GITHUB_REF"] = "refs/heads/main"
        result = run(root, "bash", str(WORKFLOW_GUARD), str(state), parent, "main", check=False, env=env)
        expect_failure(result, "does not match requested", "wrong requested revision")

        # Guest pass-like text must never substitute for independent wire proof.
        valid_wire = {
            "routersA": 2, "routersB": 2, "endnodesA": 0, "endnodesB": 1,
            "nicHelloA": 0, "nicHelloB": 0,
            "changedNicHelloA": 0, "changedNicHelloB": 0,
            "ucastAB": 3, "ucastBA": 3,
        }
        LAB.validate_e1_wire_values(valid_wire)
        suppressed = dict(valid_wire)
        suppressed["ucastBA"] = 0
        try:
            LAB.validate_e1_wire_values(suppressed)
        except SystemExit as exc:
            if "wire evidence incomplete" not in str(exc):
                raise
        else:
            raise SystemExit("false-green regression accepted pass markers with suppressed wire traffic")

        pass_marker = "DNIV-E1-PASS session=forged node=DN70"
        forged_log = root / "forged.serial.log"
        forged_log.write_text(pass_marker + "\n", encoding="utf-8")
        try:
            LAB.require_guest_log_evidence(
                forged_log,
                [pass_marker, "DNIV-E1-RECOVERED session=forged node=DN70"],
            )
        except SystemExit as exc:
            if "guest serial evidence incomplete" not in str(exc):
                raise
        else:
            raise SystemExit("false-green regression accepted a forged guest pass marker")

        dead_log = root / "dead.serial.log"
        dead_log.touch()
        try:
            LAB.require_guest_log_evidence(dead_log, [pass_marker])
        except SystemExit as exc:
            if "guest serial evidence missing or empty" not in str(exc):
                raise
        else:
            raise SystemExit("false-green regression accepted dead guest logging")

        class DeadCapture:
            @staticmethod
            def poll() -> int:
                return 1

        fake = object.__new__(LAB.Lab)
        fake.tcpdump = DeadCapture()
        try:
            fake.require_capture_running()
        except RuntimeError as exc:
            if "packet capture exited" not in str(exc):
                raise
        else:
            raise SystemExit("false-green regression accepted a dead packet capture")

        faults = root / "fault-events.log"
        try:
            LAB.require_fault_event(faults, "requested-injector")
        except SystemExit as exc:
            if "requested fault event" not in str(exc):
                raise
        else:
            raise SystemExit("false-green regression accepted an inactive requested injector")
        LAB.record_fault_event(faults, "requested-injector")
        LAB.require_fault_event(faults, "requested-injector")
        LAB.record_fault_event(faults, "requested-injector")
        try:
            LAB.require_fault_event(faults, "requested-injector")
        except SystemExit as exc:
            if "count=2 expected=1" not in str(exc):
                raise
        else:
            raise SystemExit("false-green regression accepted a corrupt fault-event manifest")

        evidence = root / "evidence"
        run(root, sys.executable, str(EVIDENCE_GUARD), "preflight",
            "--root", str(evidence), "--min-free-bytes", "1", "--min-free-inodes", "1")
        evlog = evidence / "run.log"
        evstate = evidence / "state.json"
        evlog.write_text("wire proof\n", encoding="utf-8")
        evstate.write_text('{"status":"success"}\n', encoding="utf-8")
        manifest = evidence / "manifest.json"
        run(root, sys.executable, str(EVIDENCE_GUARD), "manifest",
            "--root", str(evidence), "--output", str(manifest),
            "--require", "run.log", "--require", "state.json")
        run(root, sys.executable, str(EVIDENCE_GUARD), "verify",
            "--root", str(evidence), "--manifest", str(manifest))

        original_log = evlog.read_bytes()
        corrupt_log = bytearray(original_log)
        corrupt_log[0] ^= 1
        evlog.write_bytes(corrupt_log)
        result = run(root, sys.executable, str(EVIDENCE_GUARD), "verify",
            "--root", str(evidence), "--manifest", str(manifest), check=False)
        expect_failure(result, "evidence hash mismatch", "same-size corrupt evidence")
        evlog.write_bytes(original_log)

        evlog.write_text("truncated\n", encoding="utf-8")
        result = run(root, sys.executable, str(EVIDENCE_GUARD), "verify",
            "--root", str(evidence), "--manifest", str(manifest), check=False)
        expect_failure(result, "evidence size mismatch", "truncated evidence")
        evlog.write_bytes(original_log)

        evstate.unlink()
        result = run(root, sys.executable, str(EVIDENCE_GUARD), "verify",
            "--root", str(evidence), "--manifest", str(manifest), check=False)
        expect_failure(result, "required evidence is missing or non-regular", "omitted required evidence")
        evstate.write_text('{"status":"success"}\n', encoding="utf-8")

        result = run(root, sys.executable, str(EVIDENCE_GUARD), "preflight",
            "--root", str(evidence), "--min-free-bytes", str(1 << 62), "--min-free-inodes", "1",
            check=False)
        expect_failure(result, "insufficient free evidence bytes", "exhausted evidence bytes")
        result = run(root, sys.executable, str(EVIDENCE_GUARD), "preflight",
            "--root", str(evidence), "--min-free-bytes", "1", "--min-free-inodes", str(1 << 62),
            check=False)
        expect_failure(result, "insufficient free evidence inodes", "exhausted evidence inodes")

        blocked = root / "blocked-evidence"
        blocked.write_text("not a directory\n", encoding="utf-8")
        result = run(root, sys.executable, str(EVIDENCE_GUARD), "preflight",
            "--root", str(blocked), "--min-free-bytes", "1", "--min-free-inodes", "1",
            check=False)
        expect_failure(result, "cannot create evidence directory", "unavailable evidence directory")



        non_e1_fault = root / "non-e1-fault.log"
        valid_fault = (
            "fault=reference-unicast-drop-flow-xoff source=aa destination=bb\n"
            "Sent 128 bytes 2 pkt (dropped 2, overlimits 0 requeues 0)\n"
            "flow-inject: pass xoff=1 resumed=1\n"
        )
        non_e1_fault.write_text(valid_fault, encoding="utf-8")
        fault_args = (
            sys.executable, str(EVIDENCE_GUARD), "fault",
            "--path", str(non_e1_fault),
            "--name", "reference-unicast-drop-flow-xoff",
            "--require-tc-active",
            "--require-marker", "flow-inject: pass",
        )
        run(root, *fault_args)

        non_e1_fault.write_text(valid_fault.replace("2 pkt", "0 pkt"), encoding="utf-8")
        result = run(root, *fault_args, check=False)
        expect_failure(result, "fault evidence injector inactive", "inactive non-E1 injector")

        non_e1_fault.write_text(
            valid_fault.replace(
                "fault=reference-unicast-drop-flow-xoff",
                "fault=wrong-fault",
            ),
            encoding="utf-8",
        )
        result = run(root, *fault_args, check=False)
        expect_failure(result, "fault evidence name mismatch", "corrupt non-E1 fault manifest")

        non_e1_fault.write_text(
            valid_fault + "fault=reference-unicast-drop-flow-xoff duplicate=1\n",
            encoding="utf-8",
        )
        result = run(root, *fault_args, check=False)
        expect_failure(result, "fault evidence declaration count=2", "duplicate non-E1 fault manifest")

        non_e1_fault.write_text(
            valid_fault.replace("flow-inject: pass xoff=1 resumed=1\n", ""),
            encoding="utf-8",
        )
        result = run(root, *fault_args, check=False)
        expect_failure(result, "fault evidence missing proof marker", "missing non-E1 injector proof")

        non_e1_fault.unlink()
        result = run(root, *fault_args, check=False)
        expect_failure(result, "fault evidence missing or non-regular", "missing non-E1 fault evidence")

        interop = (ROOT / "tests/lab/run-interop.sh").read_text(encoding="utf-8")
        for safeguard in (
            "evidence_guard.py\" fault",
            "raw-interrupt-credit-flow",
            "pydecnet-connect-timeout",
            "reference-egress-drop-reserved",
            "reference-unicast-drop-until-di-retry-exhaustion",
            "reference-unicast-drop-until-ci-retry-exhaustion",
        ):
            if safeguard not in interop:
                raise SystemExit(f"interop fault evidence safeguard missing: {safeguard}")

        # Persistent architecture foundations are the repository's only
        # checkpoint-like resume input. Reject corruption, missing members,
        # stale identity metadata and accidental candidate-source coupling.
        foundation = root / "foundation"
        (foundation / "boot").mkdir(parents=True)
        member_bytes = {
            "base.qcow2": b"qcow2-foundation\n",
            "boot/vmlinuz": b"kernel-foundation\n",
            "boot/initrd.img": b"initrd-foundation\n",
        }
        for rel, data in member_bytes.items():
            (foundation / rel).write_bytes(data)
        session_text = (
            "FORMAT=2\n"
            "SESSION_ID=outer-v2-amd64-deadbeef\n"
            "ARCH=amd64\n"
            "FOUNDATION_FINGERPRINT=deadbeef\n"
            "UBUNTU_BASE_RELEASE=26.04.1\n"
            "UBUNTU_APT_SNAPSHOT=20260901T000000Z\n"
        )
        session_path = foundation / "session.env"
        session_path.write_text(session_text, encoding="utf-8")

        def write_foundation_sums() -> None:
            entries = []
            for rel in ("base.qcow2", "boot/vmlinuz", "boot/initrd.img", "session.env"):
                value = hashlib.sha256((foundation / rel).read_bytes()).hexdigest()
                entries.append(f"{value}  {rel}\n")
            (foundation / "SHA256SUMS").write_text("".join(entries), encoding="utf-8")

        foundation_args = (
            sys.executable, str(EVIDENCE_GUARD), "foundation",
            "--root", str(foundation),
            "--session-id", "outer-v2-amd64-deadbeef",
            "--arch", "amd64",
            "--fingerprint", "deadbeef",
            "--release", "26.04.1",
            "--snapshot", "20260901T000000Z",
        )
        write_foundation_sums()
        run(root, *foundation_args)

        kernel_path = foundation / "boot/vmlinuz"
        original_kernel = kernel_path.read_bytes()
        kernel_path.write_bytes(b"X" + original_kernel[1:])
        result = run(root, *foundation_args, check=False)
        expect_failure(result, "foundation hash mismatch", "corrupt persistent foundation member")
        kernel_path.write_bytes(original_kernel)

        initrd_path = foundation / "boot/initrd.img"
        original_initrd = initrd_path.read_bytes()
        initrd_path.unlink()
        result = run(root, *foundation_args, check=False)
        expect_failure(result, "foundation member missing or non-regular", "missing persistent foundation member")
        initrd_path.write_bytes(original_initrd)

        session_path.write_text(
            session_text.replace("ARCH=amd64", "ARCH=arm64"),
            encoding="utf-8",
        )
        result = run(root, *foundation_args, check=False)
        expect_failure(result, "foundation metadata mismatch ARCH", "wrong persistent foundation architecture")

        session_path.write_text(session_text + "SOURCE_SHA=" + head + "\n", encoding="utf-8")
        result = run(root, *foundation_args, check=False)
        expect_failure(result, "forbidden foundation metadata key: SOURCE_SHA", "candidate-coupled persistent foundation")

        session_path.write_text(session_text, encoding="utf-8")
        write_foundation_sums()
        sums_path = foundation / "SHA256SUMS"
        sums = sums_path.read_text(encoding="utf-8").splitlines()
        sums_path.write_text("\n".join(sums[:-1]) + "\n", encoding="utf-8")
        result = run(root, *foundation_args, check=False)
        expect_failure(result, "foundation checksum members mismatch", "missing foundation checkpoint checksum")

        workflow = (ROOT / ".github/workflows/false-green.yml").read_text(encoding="utf-8")
        for safeguard in (
            "retry_probe:",
            "mount -t tmpfs",
            "gh run download",
            "inputs.retry_probe && github.run_attempt > 1",
            "inputs.retry_probe && github.run_attempt == 1",
            "Seal final false-green evidence",
        ):
            if safeguard not in workflow:
                raise SystemExit(f"false-green workflow missing safeguard: {safeguard}")

    print("false-green acceptance-control regression passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
