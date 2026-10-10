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

"""Lock the portable source-release contract."""

from pathlib import Path
import os
import re

ROOT = Path(__file__).resolve().parents[2]

def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")

def main() -> int:
    required = (
        "VERSION", "build.sh", "install.sh", "uninstall.sh", "INSTALL.md",
        "docs/DELIVERY.md", "docs/FEATURES.md", "docs/COMPONENTS.md",
        "tools/build-source-release.sh", ".github/workflows/source-release.yml",
        ".github/workflows/production-release.yml",
    )
    for path in required:
        if not (ROOT / path).is_file():
            raise SystemExit(f"source-release gate: missing {path}")
    for path in ("build.sh", "install.sh", "uninstall.sh", "tools/build-source-release.sh"):
        if not os.access(ROOT / path, os.X_OK):
            raise SystemExit(f"source-release gate: required script is not executable: {path}")
    if (ROOT / ".github/workflows/release-image.yml").exists():
        raise SystemExit("source-release gate: obsolete release-image workflow remains")
    if (ROOT / ".github/workflows/portability.yml").exists():
        raise SystemExit("source-release gate: obsolete checkout-built portability workflow remains")
    top_makefile = read_text("Makefile")
    if 'for test in tests/policy/test_*.py; do python3 "$$test"; done' not in top_makefile:
        raise SystemExit("source-release gate: top-level unit target does not execute every policy regression")
    version_text = read_text("VERSION")
    version_lines = [line for line in version_text.splitlines() if line.startswith("version=")]
    if len(version_lines) != 1 or not re.fullmatch(r"version=[0-9]+\.[0-9]+\.[0-9]+", version_lines[0]):
        raise SystemExit("source-release gate: VERSION must contain exactly one production semantic version")
    workflow = read_text(".github/workflows/source-release.yml")
    if '0.0.0-ci-${GITHUB_SHA:0:12}' in workflow:
        raise SystemExit("source-release gate: CI pseudo-version remains in production source packaging")
    for marker in (
        "mapfile -t release_versions < <(sed -n 's/^version=//p' VERSION)",
        'version=${release_versions[0]}',
    ):
        if marker not in workflow:
            raise SystemExit(f"source-release gate: production VERSION binding missing: {marker}")
    builder = read_text("tools/build-source-release.sh")
    if "for required in VERSION build.sh install.sh uninstall.sh" not in builder:
        raise SystemExit("source-release gate: VERSION is not required in the packaged source")
    publication = read_text(".github/workflows/production-release.yml")
    for marker in (
        "github.event.issue.title == 'DNIV production release'",
        "SOURCE_SHA=",
        "ACCEPTANCE_ISSUE=",
        "Acceptance child runs for",
        "(full/all):",
        "SOURCE_RELEASE_RUN_ID",
        "gh run download",
        "decnet-iv-linux-source-$SOURCE_RELEASE_RUN_ID-$SOURCE_RELEASE_ATTEMPT",
        "sha256sum -c",
        "source_sha=$SOURCE_SHA",
        'gh release create "$tag" "$archive" "$checksum"',
        '--target "$SOURCE_SHA"',
        "PP-11 S3-S6",
        "PP-13",
        "tools/workflow_guard.sh",
        "--pass-id pass-1",
        "archive-list.txt",
    ):
        if marker not in publication:
            raise SystemExit(f"source-release gate: production publication safeguard missing: {marker}")
    for marker in (
        "Build source archive twice",
        "cmp \"$a\" \"$b\"",
        'build-source-release.sh" relative',
        "Reject invalid source release inputs",
        "checksum-mismatch negative unexpectedly succeeded",
        "truncated-archive negative unexpectedly succeeded",
        "missing-SOURCE-METADATA negative unexpectedly succeeded",
        "wrong-source-metadata negative unexpectedly succeeded",
        "generated-payload negative unexpectedly succeeded",
        "wrong-pin negative unexpectedly succeeded",
        "read-only-output negative unexpectedly succeeded",
        "missing-kernel-tree negative unexpectedly succeeded",
        "wrong-kernel-release negative unexpectedly succeeded",
        "below-kernel-floor negative unexpectedly succeeded",
        "below-python-floor negative unexpectedly succeeded",
        "below-gcc-floor negative unexpectedly succeeded",
        "below-clang-floor negative unexpectedly succeeded",
        "non-root-live-install negative unexpectedly succeeded",
        "custom-live-module-root negative unexpectedly succeeded",
        "custom-live-module-root uninstall negative unexpectedly succeeded",
        "installed-manifest completeness mismatch",
        "manifest target missing after install",
        "manifest target remains after uninstall",
        "custom-prefix manifest leaked default-prefix paths",
        "relative-PREFIX negative unexpectedly succeeded",
        "env -u KERNEL_RELEASE DESTDIR=\"$custom_prefix_stage\" PREFIX=\"$custom_prefix\" ./install.sh",
        "env -u KERNEL_RELEASE DESTDIR=\"$custom_prefix_stage\" PREFIX=\"$custom_prefix\" ./uninstall.sh",
        "Build install and uninstall extracted source",
        "missing-artifact negative unexpectedly succeeded",
        "unmanaged-target negative unexpectedly succeeded",
        "relative-DESTDIR negative unexpectedly succeeded",
        "non-normalized-DESTDIR negative unexpectedly succeeded",
        "newline-DESTDIR negative unexpectedly succeeded",
        "carriage-return-DESTDIR uninstall negative unexpectedly succeeded",
        "newline-PREFIX negative unexpectedly succeeded",
        "newline-MODULE_ROOT negative unexpectedly succeeded",
        "module-vermagic negative unexpectedly succeeded",
        "managed-target-type negative unexpectedly succeeded",
        "staged-parent-symlink negative unexpectedly succeeded",
        "uninstall-parent-symlink negative unexpectedly succeeded",
        "old_release=0.0.0-audit-old",
        "custom-module-root foreign-manifest negative unexpectedly succeeded",
        "validate-arm64:",
        "  portability:",
        "debian13",
        "fedora44",
        "actions/download-artifact@",
        "pp12_real_peers:",
        "pp12-real-peers:",
        "prepare-pp12-source-image.sh",
        "DNIV-PP12-LIFECYCLE-PASS",
        "source-release-pp12-${{ matrix.arch }}",
    ):
        if marker not in workflow:
            raise SystemExit(f"source-release gate: workflow safeguard missing: {marker}")
    if "fedora:42" in workflow:
        raise SystemExit("source-release gate: EOL Fedora 42 portability image remains")
    for doc in ("docs/TEST_LAB.md", "docs/PRE_PRODUCTION_TEST.md"):
        value = read_text(doc)
        if "Fedora 42" in value or "Fedora 44" not in value:
            raise SystemExit(f"source-release gate: stale Fedora portability documentation remains in {doc}")
    reference_tests = read_text("tests/reference/pydecnet-in-scope-tests.txt")
    broad_reference_modules = {
        "tests.test_gre": "GRE IPv6",
        "tests.test_host": "host dual-stack/IPv6",
        "tests.test_multinet": "MULTINET UDP/IPv6",
    }
    for line in reference_tests.splitlines():
        selected = line.strip()
        if selected in broad_reference_modules:
            raise SystemExit(
                f"source-release gate: broad PyDECnet {selected} module still makes "
                f"{broad_reference_modules[selected]} cases blocking"
            )
    for marker in (
        "tests.test_gre.TestGre4",
        "tests.test_host.TestHost.test_goodhost4",
        "tests.test_host.TestHost.test_badhost2",
        "tests.test_multinet.TestMultinetTCPconnect",
        "tests.test_multinet.TestMultinetTCPconnectLate",
        "tests.test_multinet.TestMultinetTCPlisten",
    ):
        if marker not in reference_tests:
            raise SystemExit(f"source-release gate: IPv4-only reference selector missing: {marker}")
    for excluded in (
        "TestGre6",
        "test_goodhost46",
        "test_goodhost446",
        "test_goodhost466",
        "test_goodhost6",
        "TestMultinetTCPconnect2",
        "TestMultinetTCP6listen",
        "TestMultinetTCP46listen",
        "TestMultinetUDP",
        "TestMultinetUDPnodest",
    ):
        if excluded in reference_tests:
            raise SystemExit(f"source-release gate: out-of-scope IPv6/UDP reference selector selected: {excluded}")

    multinet_proof = read_text("tests/lab/prove-multinet.sh")
    if "-m unittest -v tests.test_multinet\n" in multinet_proof:
        raise SystemExit("source-release gate: MULTINET proof still runs the broad PyDECnet module")
    for marker in (
        "tests.test_multinet.TestMultinetTCPconnect",
        "tests.test_multinet.TestMultinetTCPconnectLate",
        "tests.test_multinet.TestMultinetTCPlisten",
    ):
        if marker not in multinet_proof:
            raise SystemExit(f"source-release gate: IPv4-only MULTINET proof selector missing: {marker}")
    for excluded in (
        "TestMultinetTCPconnect2",
        "TestMultinetTCP6listen",
        "TestMultinetTCP46listen",
        "TestMultinetUDP",
        "TestMultinetUDPnodest",
    ):
        if excluded in multinet_proof:
            raise SystemExit(f"source-release gate: out-of-scope MULTINET proof selector present: {excluded}")

    preproduction = read_text("docs/PRE_PRODUCTION_TEST.md")
    if "`run-two-node.sh`" in preproduction:
        raise SystemExit("source-release gate: stale removed two-node harness remains in pre-production documentation")
    for stale in (
        "Native DDCMP serial/synchronous media remain part of the standing project goal",
        "DDCMP remains part of the standing DECnet-IV-Linux project goal",
        "Native DDCMP is part of the standing project goal",
        "native DDCMP project-goal surface",
        "IPv4/IPv6 cases where supported",
    ):
        if stale in preproduction:
            raise SystemExit(f"source-release gate: stale DDCMP/IPv6 in-scope wording remains: {stale}")
    for required in (
        "DDCMP is explicitly outside project scope",
        "IPv6 is explicitly outside project scope",
        "IPv4 cases",
    ):
        if required not in preproduction:
            raise SystemExit(f"source-release gate: pre-production owner scope boundary missing: {required}")
    if "peer and gateway restart, link interruption" in preproduction:
        raise SystemExit("source-release gate: PP-09 still permits ambiguous disruptive remote-peer testing")
    for required in (
        "project-controlled local gateway restart",
        "Remote HECnet peers beyond PYRTR `31.3` are observation/traffic peers only",
        "do not restart, stop, reconfigure, disconnect or otherwise disrupt them",
    ):
        if required not in preproduction:
            raise SystemExit(f"source-release gate: PP-09 remote-peer safety boundary missing: {required}")
    if "locally controlled peers such as QCOCAL/IMPVAX" in preproduction:
        raise SystemExit("source-release gate: PP-12 still ambiguously treats named remote VAX peers as locally controlled")
    for required in (
        "QCOCAL/IMPVAX instances that are themselves running locally under project control",
        "A QCOCAL/IMPVAX system reached beyond PYRTR `31.3` is a protected remote HECnet peer",
        "must not be restarted, hard-stopped, reconfigured or otherwise disrupted",
    ):
        if required not in preproduction:
            raise SystemExit(f"source-release gate: PP-12 named-peer safety boundary missing: {required}")
    for required in ("`tests/lab/dniv_lab.py`", "`tests/lab/dniv-smoke.sh`"):
        if required not in preproduction:
            raise SystemExit(f"source-release gate: active two-node harness documentation missing: {required}")
    test_lab_scale = read_text("docs/TEST_LAB.md")
    for stale in ("Full acceptance initially dispatches `scale4`", "`scale8` and `scale16` exist but are not promotion-green"):
        if stale in test_lab_scale:
            raise SystemExit(f"source-release gate: stale Phase 9 scale promotion text remains: {stale}")
    for required in ("`scale4` and `scale8` on both x86_64 and aarch64", "distributed 16-node scale workflow"):
        if required not in test_lab_scale:
            raise SystemExit(f"source-release gate: current Phase 9 scale promotion text missing: {required}")
    for stale in ("PP-10 remains open only until", "as Phase 7 tools become available"):
        if stale in preproduction:
            raise SystemExit(f"source-release gate: stale completed acceptance text remains in pre-production documentation: {stale}")
    if "PP-10 is closed" not in preproduction or "e60660c3b7d311451fc854464fa1d7438222f7e2" not in preproduction:
        raise SystemExit("source-release gate: PP-10 closure is not synchronized in pre-production documentation")
    handover_status = read_text("docs/HANDOVER.md")
    if "When its repository-tracked workflow is added" in handover_status:
        raise SystemExit("source-release gate: stale pre-implementation Area-31 wording remains in handover")
    if ".github/workflows/area31-interop.yml" not in handover_status:
        raise SystemExit("source-release gate: handover does not identify the implemented Area-31 workflow")

    run_interop = read_text("tests/lab/run-interop.sh")
    if '-$-$reference-$scenario' in run_interop:
        raise SystemExit("source-release gate: generator-damaged default interop session identifier remains")
    if 'local-$(date -u +%Y%m%dT%H%M%SZ)-${BASHPID}-${reference}-${scenario}' not in run_interop:
        raise SystemExit("source-release gate: unique default interop session identifier missing")

    socat_probe = read_text("tests/lab/probe-socat-rendezvous.sh")
    for stale in (
        'required=(VDE_SSH_HOST VDE_SSH_PORT VDE_SSH_USER VDE_SSH_KEY VDE_SSH_KNOWN_HOSTS GITHUB_RUN_ID)',
        'remote_sock="/tmp/dniv-socat-${run_id}.sock"',
    ):
        if stale in socat_probe:
            raise SystemExit(f"source-release gate: socat rendezvous is not run-attempt isolated: {stale}")
    for required in (
        "GITHUB_RUN_ATTEMPT",
        'rendezvous="${run_id}-${run_attempt}"',
        'remote_sock="/tmp/dniv-socat-${rendezvous}.sock"',
        'python3 - "$ssh_config" "$remote_sock" "$rendezvous"',
    ):
        if required not in socat_probe:
            raise SystemExit(f"source-release gate: socat run-attempt rendezvous safeguard missing: {required}")

    scale16_workflow = read_text(".github/workflows/scale16-distributed.yml")
    for stale in (
        'relay="/tmp/dniv-scale16-${GITHUB_RUN_ID}-${arch}.sock"',
        'cable_ready="/tmp/dniv-scale16-${GITHUB_RUN_ID}-${arch}-cable-${side}.ready"',
        '--sync-token "${GITHUB_RUN_ID}-${arch}"',
    ):
        if stale in scale16_workflow:
            raise SystemExit(f"source-release gate: scale16 shared rendezvous omits run attempt: {stale}")
    for required in (
        'relay="/tmp/dniv-scale16-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}-${arch}.sock"',
        'cable_ready="/tmp/dniv-scale16-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}-${arch}-cable-${side}.ready"',
        'cable_peer="/tmp/dniv-scale16-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}-${arch}-cable-${peer_side}.ready"',
        '--sync-token "${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}-${arch}"',
    ):
        if required not in scale16_workflow:
            raise SystemExit(f"source-release gate: scale16 run-attempt isolation missing: {required}")

    ncp_source = read_text("userspace/ncp/ncp.c")
    if 'run_tool("DNIV_DNNICE", "/usr/local/bin/dnnice",' not in ncp_source or \
       '"/usr/local/sbin/dnnice"' in ncp_source:
        raise SystemExit("source-release gate: ncp dnnice install path drift")
    nice_header = read_text("include/decnet_iv_nice.h")
    for marker in (
        "dniv_nice_reply_entity_offset",
        "Phase IV NICE success replies place the entity immediately after the",
    ):
        if marker not in nice_header:
            raise SystemExit(f"source-release gate: NICE success reply framing regression: {marker}")
    dnping_source = read_text("userspace/dnping/dnping.c")
    for marker in (
        '#define DNPING_MIRROR_OBJECT "#25"',
        "dnet_conn((char *)node, DNPING_MIRROR_OBJECT, SOCK_SEQPACKET,",
        'strcmp(DNPING_MIRROR_OBJECT, "#25")',
    ):
        if marker not in dnping_source:
            raise SystemExit(f"source-release gate: dnping standard MIRROR object regression: {marker}")
    if 'dnet_conn((char *)node, "MIRROR", SOCK_SEQPACKET,' in dnping_source:
        raise SystemExit("source-release gate: dnping reverted to named MIRROR object")

    dnnice_source = read_text("userspace/dnnice/dnnice.c")
    if "return dniv_nice_reply_entity_offset(buf, length, offset);" not in dnnice_source:
        raise SystemExit("source-release gate: dnnice bypasses shared NICE success framing parser")
    for marker in (
        "receive_single_reply",
        "DNIV_NICE_RET_ACCEPTED",
        "dniv_nice_control_reply(response, (size_t)got",
    ):
        if marker not in dnnice_source:
            raise SystemExit(f"source-release gate: dnnice accepted-response prelude regression: {marker}")
    nice_unit = read_text("tests/unit/test_phase6_nice.c")
    for marker in (
        "canonical_len = reply_len - 3U",
        "memcpy(canonical + 1U, reply + 4U, reply_len - 4U)",
        "accepted_compact",
        "accepted_extended",
        "DNIV_NICE_RET_DONE",
    ):
        if marker not in nice_unit:
            raise SystemExit(f"source-release gate: canonical NICE success regression missing: {marker}")
    pp11_s1 = read_text("tests/lab/dniv_pp11_s1.py")
    if 'Lab(base, kernel, initrd, work, "pp11s1", session, nic_model, vcpus, "none", memory_mb, False)' not in pp11_s1:
        raise SystemExit("source-release gate: PP-11 S1 Lab constructor post-timing argument drift")

    candidate_image = read_text("tests/lab/prepare-candidate-image.sh")
    for required in (
        "install -m 0755 /usr/src/decnet-iv-linux/userspace/dnlogin/dnlogin /usr/local/bin/dnlogin",
        "ln -sf dnlogin /usr/local/bin/sethost",
        'sudo test -s "$mnt/usr/local/bin/dnlogin"',
    ):
        if required not in candidate_image:
            raise SystemExit(f"source-release gate: candidate-image dnlogin install contract missing: {required}")
    for stale in (
        "/usr/local/sbin/dnlogin",
        "ln -sf ../sbin/dnlogin /usr/local/bin/sethost",
    ):
        if stale in candidate_image:
            raise SystemExit(f"source-release gate: candidate-image stale dnlogin install path remains: {stale}")

    interop_smoke = read_text("tests/lab/dniv-interop-smoke.sh")
    if "/usr/local/sbin/dnlogin" in interop_smoke:
        raise SystemExit("source-release gate: interoperability CTERM path uses stale sbin dnlogin")
    for required in (
        "/usr/local/bin/dnlogin --probe",
        "/usr/local/bin/dnlogin -u CTERMUSER -p CTERMPASS -a CTERMACCT",
    ):
        if required not in interop_smoke:
            raise SystemExit(f"source-release gate: interoperability production dnlogin path missing: {required}")

    area31_smoke = read_text("tests/lab/dniv-area31-smoke.sh")
    for forbidden in (
        "/usr/local/bin/dncopy --put-text",
        "/usr/local/bin/dndel",
        "/usr/local/bin/dnrename",
        "/usr/local/bin/dntask",
        "DNIVHT.COM",
        "DNIVTK.COM",
    ):
        if forbidden in area31_smoke:
            raise SystemExit(f"source-release gate: remote Area-31 state-change path remains: {forbidden}")
    if "/usr/local/sbin/dnlogin --probe" in area31_smoke:
        raise SystemExit("source-release gate: PP-12 CTERM probe uses stale sbin dnlogin path")
    for required in (
        "DNIV-AREA31-QCOCAL-READONLY-PASS",
        "DNIV-AREA31-PP12-QCOCAL-READONLY-PASS",
        "DNIV-AREA31-PP12-CLIENTS-PASS",
        'cterm_log="$scratch/cterm.err"',
        'for _ in $(seq 1 10)',
        "/usr/local/bin/dnlogin --probe",
        'ncp_log="$scratch/ncp.err"',
        'sed -n \'1,6p\' "$ncp_log" >&2',
        "sed -n '1,4p' \"$cterm_log\" >&2",
    ):
        if required not in area31_smoke:
            raise SystemExit(f"source-release gate: remote Area-31 read-only safeguard missing: {required}")
    area31_driver = read_text("tests/lab/prove-area31.sh")
    if "for _ in $(seq 1 360); do" not in area31_driver:
        raise SystemExit("source-release gate: bounded PYRTR convergence window missing")
    for forbidden in ("make-http-com.py", "make-task-com.py"):
        if forbidden in area31_driver:
            raise SystemExit(f"source-release gate: remote Area-31 program-generation path remains: {forbidden}")
    for stale in (
        "/tmp/dniv-area31-native.err",
        "/tmp/dniv-qcocal-http.out",
        "/tmp/dniv-qcocal-http.err",
    ):
        if stale in area31_smoke:
            raise SystemExit(f"source-release gate: predictable Area-31 guest scratch path remains: {stale}")
    for required in (
        "mktemp -d /tmp/dniv-area31.XXXXXX",
        'remote_log="$scratch/native.err"',
        "trap cleanup_scratch EXIT HUP INT TERM",
    ):
        if required not in area31_smoke:
            raise SystemExit(f"source-release gate: Area-31 guest scratch safeguard missing: {required}")

    state_status = read_text("docs/PROJECT_STATE.md").split("## Resume point", 1)[0]
    if "server timed out/client hung in join step" in state_status:
        raise SystemExit("source-release gate: stale pre-closure cross-runner status remains in project state")
    for required in ("36258564105", "36258635481", "36258643588", "36258654316"):
        if required not in state_status:
            raise SystemExit(f"source-release gate: final Phase 8 infrastructure evidence missing from project state: {required}")

    resume_status = read_text("scratch/RESUME.md").split("## Next action", 1)[0]
    for stale in ("Phase 7 is active on `main`", "cross-runner VDE2 is still unproven", "Area-31 remote integration is still planned"):
        if stale in resume_status:
            raise SystemExit(f"source-release gate: stale current checkpoint remains in scratch resume: {stale}")
    for required in ("Phase 9 is active on `main`", "36258564105", "36258635481", "36258643588", "36258654316"):
        if required not in resume_status:
            raise SystemExit(f"source-release gate: current Phase 8/9 checkpoint missing from scratch resume: {required}")

    hecnet_lab = read_text("docs/HECNET_LAB.md")
    for stale in ("sole remaining Phase 8 exit dependency", "The Area-31 workflow will use these GitHub Actions secrets", "as those facilities become available", "as each userspace feature lands"):
        if stale in hecnet_lab:
            raise SystemExit(f"source-release gate: stale Phase 8/Phase 7 text remains in HECnet documentation: {stale}")
    for required in ("9b73e61bbd0f95b82410276f7b5dc3db94e219ba", "36258564105", "36258635481", "36258643588", "36258654316"):
        if required not in hecnet_lab:
            raise SystemExit(f"source-release gate: Phase 8 final evidence missing from HECnet documentation: {required}")
    test_lab_status = read_text("docs/TEST_LAB.md")
    if "As userspace matures" in test_lab_status:
        raise SystemExit("source-release gate: stale Phase 7 maturity wording remains in lab documentation")
    roadmap = read_text("docs/ROADMAP.md")
    if "as Phase 7 tools mature" in roadmap:
        raise SystemExit("source-release gate: stale Phase 7 maturity wording remains in roadmap")
    pp12_marker = "\n  pp12-real-peers:\n"
    if pp12_marker not in workflow:
        raise SystemExit("source-release gate: PP-12 lab-only job boundary missing")
    release_workflow, pp12_workflow = workflow.split(pp12_marker, 1)
    for forbidden in ("qemu-system", "dniv.raw", "Release Image"):
        if forbidden in release_workflow:
            raise SystemExit(f"source-release gate: disk-image release behavior remains: {forbidden}")
    qcow2_lines = [line for line in release_workflow.splitlines() if ".qcow2" in line]
    for line in qcow2_lines:
        if "-name '*.qcow2'" not in line and "audit.qcow2" not in line:
            raise SystemExit(f"source-release gate: unexpected qcow2 release behavior remains: {line.strip()}")
    if not any("-name '*.qcow2'" in line for line in qcow2_lines) or not any("audit.qcow2" in line for line in qcow2_lines):
        raise SystemExit("source-release gate: generated-payload qcow2 negative is incomplete")
    for marker in (
        "qemu-system-",
        "DNIV_PP12_CANDIDATE_IMAGE",
        'candidate="$RUNNER_TEMP/pp12-candidate-',
        'path: ${{ env.DNIV_SCRATCH_DIR }}/',
    ):
        if marker not in pp12_workflow:
            raise SystemExit(f"source-release gate: PP-12 lab-only image safeguard missing: {marker}")
    if "path: ${{ env.DNIV_PP12_CANDIDATE_IMAGE }}" in pp12_workflow:
        raise SystemExit("source-release gate: PP-12 disposable candidate image is uploaded as evidence")
    readme = read_text("README.md")
    for marker in ("SOCK_SEQPACKET", "SOCK_STREAM", "deferred accept/reject"):
        if marker not in readme:
            raise SystemExit(f"source-release gate: README feature inventory missing: {marker}")

    delivery = read_text("docs/DELIVERY.md")
    for marker in ("source tarball", "Disk images are not release artifacts", "x86_64", "aarch64", "Linux 6.8", "Forward compatibility", "DDCMP and IPv6 are explicitly outside", "not release blockers", "IPv4-only"):
        if marker not in delivery:
            raise SystemExit(f"source-release gate: delivery contract missing: {marker}")
    if "refreshes the dynamic-library cache with `ldconfig` when the host provides that cache mechanism" not in delivery:
        raise SystemExit("source-release gate: delivery dynamic-loader cache contract is stale")
    for stale in ("explicitly **pending**", "blocked until DDCMP", "DDCMP remains part of the standing", "Native DDCMP is part of the standing"):
        if stale in delivery:
            raise SystemExit(f"source-release gate: stale DDCMP release blocker remains: {stale}")
    for doc, marker in (
        ("docs/HANDOVER.md", "DDCMP and IPv6 are explicitly out of scope"),
        ("docs/ROADMAP.md", "DDCMP and IPv6 are explicitly outside project/release scope"),
        ("docs/PROJECT_STATE.md", "Owner scope boundary: DDCMP and IPv6 are explicitly out of scope"),
        ("scratch/RESUME.md", "Owner scope boundary: DDCMP and IPv6 are explicitly out of scope"),
    ):
        if marker not in read_text(doc):
            raise SystemExit(f"source-release gate: owner scope boundary missing from {doc}: {marker}")
    features = read_text("docs/FEATURES.md")
    for marker in ("SOCK_SEQPACKET", "SOCK_STREAM", "DSO_CONACCESS", "DSO_CONDATA", "DSO_DISDATA", "DSO_LINKINFO", "DSO_ACCEPTMODE", "DSO_CONACCEPT", "DSO_CONREJECT"):
        if marker not in features:
            raise SystemExit(f"source-release gate: delivered socket feature missing from catalogue: {marker}")
    for marker in ("## Explicit scope exclusions", "DDCMP and IPv6 transport support are outside", "IPv4-only"):
        if marker not in features:
            raise SystemExit(f"source-release gate: feature scope boundary missing: {marker}")

    kernel_readme = read_text("kernel/decnet/README.md")
    for marker in ("SOCK_SEQPACKET", "SOCK_STREAM", "DSO_DISDATA", "DSO_ACCEPTMODE", "DSO_CONACCEPT", "DSO_CONREJECT"):
        if marker not in kernel_readme:
            raise SystemExit(f"source-release gate: kernel component README missing accepted socket surface: {marker}")
    for stale in ("current follow-up candidate", "remain ordered Phase 5 follow-up work"):
        if stale in kernel_readme:
            raise SystemExit(f"source-release gate: kernel component README contains stale phase text: {stale}")

    components = read_text("docs/COMPONENTS.md")
    for marker in ("## Explicit scope exclusions", "No DDCMP implementation component and no IPv6 transport component are required or claimed", "not a release blocker", "libdnet_daemon.so.1", "install-manifest.txt", "exact default manifest is acceptance-checked on both amd64 and arm64"):
        if marker not in components:
            raise SystemExit(f"source-release gate: component scope boundary missing: {marker}")
    for marker in ("SOCK_SEQPACKET", "SOCK_STREAM", "DNPROTO_NSP", "DSO_DISDATA", "DSO_ACCEPTMODE"):
        if marker not in components:
            raise SystemExit(f"source-release gate: component inventory missing accepted socket surface: {marker}")
    for directory in sorted(path.name for path in (ROOT / "userspace").iterdir() if path.is_dir()):
        if f"userspace/{directory}" not in components:
            raise SystemExit(f"source-release gate: undocumented userspace component: {directory}")
    source_components = list((ROOT / "kernel/decnet").glob("decnet_iv_*.[ch]"))
    source_components += list((ROOT / "include").glob("decnet_iv_*.h"))
    for path in sorted(source_components):
        if path.name not in components:
            raise SystemExit(f"source-release gate: undocumented kernel/protocol source component: {path.name}")
    for path in sorted((ROOT / "tools").iterdir()):
        if path.is_file() and f"tools/{path.name}" not in components:
            raise SystemExit(f"source-release gate: undocumented release/support tool: {path.name}")
    for directory in ("tests/unit/", "tests/policy/", "tests/reference/", "tests/lab/", "tests/lab/vax/"):
        if directory not in components:
            raise SystemExit(f"source-release gate: undocumented test/lab source component: {directory}")
    for directory in (ROOT / ".github/workflows", ROOT / "image/ubuntu-base", ROOT / "references", ROOT / ".githooks"):
        for path in sorted(directory.iterdir()):
            if path.is_file():
                relative = path.relative_to(ROOT).as_posix()
                if relative not in components:
                    raise SystemExit(f"source-release gate: undocumented source-support component: {relative}")
    for relative in ("README.md", "LICENSE", "docs/ARCHITECTURE.md", "docs/ROADMAP.md", "docs/HANDOVER.md", "docs/PROJECT_STATE.md", "scratch/RESUME.md", "docs/HECNET_LAB.md", "docs/TEST_LAB.md", "docs/PRE_PRODUCTION_TEST.md", "docs/PP_EVIDENCE.md", ".gitattributes", ".gitignore", "scratch/.gitignore", "scratch/README.md"):
        if relative not in components:
            raise SystemExit(f"source-release gate: undocumented governance/source-tree component: {relative}")
    builder = read_text("tools/build-source-release.sh")
    for marker in (
        'find "$work/$name" -type l -print -quit',
        'symbolic link in source archive',
        'source already contains generated SOURCE-METADATA',
    ):
        if marker not in builder:
            raise SystemExit(f"source-release gate: builder must reject tracked source links: {marker}")
    for marker in (
        "SOURCE-METADATA",
        "'*.qcow2'", "'*.raw'", "'*.img'", "'*.iso'", "'*.ko'",
        "'*.a'", "'*.so'", "'*.so.*'", "'*.pyc'", "__pycache__",
        "ELF binary payload present",
        "generated_paths=(",
        "output_dir=$(cd \"$output_dir\" && pwd -P)",
        "git -C \"$root\" archive",
    ):
        if marker not in builder:
            raise SystemExit(f"source-release gate: archive safeguard missing: {marker}")

    install = read_text("install.sh")
    for marker in (
        "refusing unmanaged existing target",
        'record "$target"',
        'sort -u "$manifest"',
        "unsafe existing manifest",
        "refusing non-symlink at link target",
        "module vermagic release",
        "required command not found: modinfo",
        "required command not found: mktemp",
        "required command not found: stat",
        'mktemp "$manifest.tmp.XXXXXX"',
        'stat -c %h -- "$manifest"',
        'stat -c %h -- "$destdir$target"',
        "refusing unsafe regular-file target",
        "required command not found: depmod",
        'if [[ -z "$destdir" && -n ${MODULE_ROOT:-} ]]; then',
        "custom MODULE_ROOT is supported only with non-empty DESTDIR",
        "DESTDIR must be empty or a normalized absolute non-root path",
        "\"$path\" != *$'\\n'*",
        "\"$path\" != *$'\\r'*",
        '"$path" != *"//"*',
        "staged path crosses symlink parent",
        "safe_default_module_path",
        "module_root_is_default",
    ):
        if marker not in install:
            raise SystemExit(f"source-release gate: installer safety safeguard missing: {marker}")

    uninstall = read_text("uninstall.sh")
    for marker in (
        "safe install manifest not found",
        "normalized absolute non-root path",
        "\"$path\" != *$'\\n'*",
        "\"$path\" != *$'\\r'*",
        '"$path" != *"//"*',
        "staged path crosses symlink parent",
        "mapfile -t paths",
        "safe_default_module_path",
        "module_root_is_default",
        "module_releases",
        "required command not found: stat",
        '$(stat -c %h -- "$manifest") == 1',
        "required command not found: depmod",
        'if [[ -z "$destdir" && -n ${MODULE_ROOT:-} ]]; then',
        "custom MODULE_ROOT is supported only with non-empty DESTDIR",
    ):
        if marker not in uninstall:
            raise SystemExit(f"source-release gate: uninstaller safety safeguard missing: {marker}")

    build_path = ROOT / "build.sh"
    if not os.access(build_path, os.X_OK):
        raise SystemExit("source-release gate: build.sh is not executable")
    build = read_text("build.sh")
    for marker in (
        "include/config/kernel.release",
        "kernelrelease",
        "does not match KDIR release",
        "Clang 16 or later required",
        "GCC-compatible compiler 12 or later required",
        "target kernel build tree was configured with GCC",
        "target kernel build tree was configured with Clang",
        'for command in bash make ar',
        'grep sed uname; do need',
        'make clean KDIR="$kdir"',
        "need dirname",
    ):
        if marker not in build:
            raise SystemExit(f"source-release gate: end-user build safeguard missing: {marker}")

    for marker in (
        "needs: package-amd64",
        "source-release-portability-${{ matrix.arch }}",
        'source_dir="$RUNNER_TEMP/release"',
        'sha256sum -c "$(basename "$archive").sha256"',
        'grep -Fqx "source_sha=$DNIV_EXPECTED_SHA" SOURCE-METADATA',
        "run_case debian13 debian:13 gcc",
        "git bc bison flex libelf-dev libssl-dev",
        'if [[ "$DNIV_COMPILER" == clang ]]',
        "tests/lab/build-diagnostic-kernel.sh",
        "git -C /tmp/linux-clang fetch --depth=1 origin",
        'test "$(git -C /tmp/linux-clang rev-parse HEAD)" = "$linux_commit"',
        'KBUILD_MODPOST_WARN=1 CC="$cc" KDIR=/tmp/linux-clang KERNEL_RELEASE="$clang_release" ./build.sh',
        'DESTDIR="$stage" KERNEL_RELEASE="$clang_release" ./install.sh',
        "manifest-temp-symlink-stage",
        "install-manifest.txt.tmp.$BASHPID",
        "foreign-victim",
        "manifest-hardlink-stage",
        "hard-linked-manifest negative unexpectedly succeeded",
        "uninstall-manifest-hardlink-stage",
        "hard-linked-uninstall-manifest negative unexpectedly succeeded",
        "target-hardlink-stage",
        "hard-linked-managed-target negative unexpectedly succeeded",
        "KBUILD_MODPOST_WARN=1",
        "linux_floor_commit=e8f897f4afef0031fe618a8e94127a0934896aba",
        'test "$floor_release" = 6.8.0',
        'KDIR=/tmp/linux-floor KERNEL_RELEASE="$floor_release" ./build.sh',
        'DESTDIR="$floor_stage" KERNEL_RELEASE="$floor_release" ./install.sh',
        "run_case fedora44 fedora:44 clang",
    ):
        if marker not in workflow:
            raise SystemExit(f"source-release gate: exact-artifact portability safeguard missing: {marker}")
    diagnostic_kernel = read_text("tests/lab/build-diagnostic-kernel.sh")
    for marker in ("Linux v7.3-rc5", "linux_commit=72d3fcf802c45d00b300f25b848a93c3a2bd7c7e"):
        if marker not in diagnostic_kernel:
            raise SystemExit(f"source-release gate: current upstream kernel pin missing: {marker}")

    diagnostic_installer = read_text("tests/lab/install-diagnostic-module.sh")
    diagnostic_workflow = read_text(".github/workflows/kernel-diagnostics.yml")
    test_lab = read_text("docs/TEST_LAB.md")
    for label, value in (
        ("diagnostic builder", diagnostic_kernel),
        ("diagnostic installer", diagnostic_installer),
        ("diagnostic workflow", diagnostic_workflow),
        ("lab documentation", test_lab),
    ):
        if "7.0.0-dniv-" in value or "pinned upstream Linux v7.0 commit" in value:
            raise SystemExit(f"source-release gate: stale Linux 7.0 diagnostic contract remains in {label}")
    for marker in ("7.3.0-rc5-dniv-",):
        for label, value in (
            ("diagnostic builder", diagnostic_kernel),
            ("diagnostic installer", diagnostic_installer),
            ("diagnostic workflow", diagnostic_workflow),
        ):
            if marker not in value:
                raise SystemExit(f"source-release gate: current diagnostic release contract missing in {label}: {marker}")
    if "Linux v7.3-rc5 commit `72d3fcf802c45d00b300f25b848a93c3a2bd7c7e`" not in test_lab:
        raise SystemExit("source-release gate: lab documentation current-kernel pin is stale")
    if "Linux v6.8 commit `e8f897f4afef0031fe618a8e94127a0934896aba`" not in test_lab:
        raise SystemExit("source-release gate: lab documentation kernel-floor pin is missing")

    reference_workflow = read_text(".github/workflows/reference-baselines.yml")
    for marker in (
        "linuxdecnet-libvaxdata:",
        "https://github.com/tuklusan/LinuxDECnet.git",
        'git -C "$work" fetch --depth=1 origin "$LINUXDECNET_REF"',
        'make -C "$work/dnprogs/libvaxdata/linux" -f makefile.gcc test',
        "simh-vax-reference:",
        "https://github.com/tuklusan/simh.git",
        'git -C "$work" fetch --depth=1 origin "$SIMH_REF"',
        'make -C "$work" vax NOVIDEO=1 TEST_ARG=-v',
        "vax_stddev.c",
        "pdp11_rq.c",
        "pdp11_xq.c",
    ):
        if marker not in reference_workflow:
            raise SystemExit(f"source-release gate: upstream reference-health safeguard missing: {marker}")

    dispatcher = read_text(".github/workflows/repository-policy.yml")
    if "SOURCE_RELEASE source-release.yml" not in dispatcher or "RELEASE_IMAGE release-image.yml" in dispatcher:
        raise SystemExit("source-release gate: acceptance dispatcher not synchronized")
    for marker in (
        "all|socket|routing|pp11-pressure|pp11-s2|pp12|post-timing|source-release",
        'scope" == pp12',
        'scope" == post-timing',
        "-f post_timing=true",
        "VM_LAB_POST_TIMING=vm-lab.yml:e1:virtio-net-pci:4vcpu:post-timing",
        "VM_LAB_PP11_S2=vm-lab.yml:pp11s2:virtio-net-pci:1vcpu",
        '-f pp12_real_peers="$pp12_real_peers"',
        "-f pp12_real_peers=true",
    ):
        if marker not in dispatcher:
            raise SystemExit(f"source-release gate: PP-12 dispatcher safeguard missing: {marker}")
    if "dispatch_and_record PORTABILITY portability.yml" in dispatcher:
        raise SystemExit("source-release gate: full acceptance duplicates portability outside exact release artifact")
    attributes = read_text(".gitattributes")
    if "filter=lfs" in attributes or "qcow2" in attributes.lower():
        raise SystemExit("source-release gate: repository still advertises disk-image delivery")

    install_doc = read_text("INSTALL.md")
    for marker in ("Secure Boot", "MODULE_ROOT", "modprobe -r decnet_iv", "python3 -c 'import decnet'", "module vermagic", "binutils (including `ar`)", "reject existing symlinked parent components", "dnf install gcc make binutils", "dirname", "basename", "mktemp", "stat", "sha256sum", "earlier kernel builds remain valid managed entries", "repeated `//` separators", "CR/LF line breaks", "line-oriented", "pass the same value to `uninstall.sh`", "live install always uses `/lib/modules/<kernel-release>`", "custom `MODULE_ROOT` is rejected for live uninstall"):
        if marker not in install_doc:
            raise SystemExit(f"source-release gate: installation manual missing: {marker}")

    for marker in ("host dynamic-loader mechanism", "installer does not modify `/etc/ld.so.conf`", "When `ldconfig` exists", "removed from the environment passed to PyDECnet"):
        if marker not in install_doc:
            raise SystemExit(f"source-release gate: installation loader contract missing: {marker}")

    dnmultinet = read_text("userspace/dnmultinet/dnmultinet.py")
    for marker in (
        "def safe_config_token",
        "shlex.split(value, comments=False, posix=True)",
        "ipaddress.IPv4Address",
        'env.pop("MULTINET_REMOTE_HOST", None)',
        'env.pop("MULTINET_REMOTE_PORT", None)',
        "--runtime-peer-env refuses --config-out to avoid persisting runtime peer values",
    ):
        if marker not in dnmultinet:
            raise SystemExit(f"source-release gate: dnmultinet config-safety regression: {marker}")
    dnmultinet_selftest = read_text("userspace/dnmultinet/selftest.py")
    for marker in (
        "VDE URL has invalid syntax",
        "local address has invalid syntax",
        "peer host must be an IPv4 address or hostname",
        "refuses --config-out",
        "MULTINET_REMOTE_HOST has invalid syntax",
        "runtime MULTINET peer variables leaked to child environment",
    ):
        if marker not in dnmultinet_selftest:
            raise SystemExit(f"source-release gate: dnmultinet config-safety negative missing: {marker}")
    dnmultinet_make = read_text("userspace/dnmultinet/Makefile")
    if "$(PYTHON) selftest.py" not in dnmultinet_make:
        raise SystemExit("source-release gate: dnmultinet config selftest is not in the normal build")
    if "all: check" not in dnmultinet_make or "test: check" not in dnmultinet_make:
        raise SystemExit("source-release gate: end-user dnmultinet build still coupled to lab-only tests")
    root_make = read_text("Makefile")
    if "$(MAKE) -C userspace/dnmultinet test" not in root_make:
        raise SystemExit("source-release gate: lab dnmultinet tests disappeared from repository unit coverage")

    dncopy = read_text("userspace/dncopy/dncopy.c")
    store_start = dncopy.find("static int store_file")
    store_end = dncopy.find("static int rename_file", store_start)
    store_body = dncopy[store_start:store_end]
    if (
        store_start < 0
        or store_end < 0
        or "if (fd < 0) {\n        int saved_errno = errno;" not in store_body
        or "if (in != stdin)\n            (void)fclose(in);" not in store_body
        or "errno = saved_errno;\n        return -1;" not in store_body
    ):
        raise SystemExit("source-release gate: dncopy store does not close local input when FAL open fails")
    if "if (fd < 0)\n        return -1;" in store_body:
        raise SystemExit("source-release gate: dncopy store leaks local input when FAL open fails")
    text_reader_start = dncopy.find("static int read_text_record")
    text_reader_end = dncopy.find("static int retrieve_file", text_reader_start)
    text_reader = dncopy[text_reader_start:text_reader_end]
    if (
        text_reader_start < 0 or text_reader_end < 0
        or "ch = fgetc(in);" not in text_reader
        or "if (ch == 0) {" not in text_reader
        or "errno = EILSEQ;" not in text_reader
        or "if (len == cap) {" not in text_reader
        or "int read_rc = read_text_record(in, data," not in store_body
        or "payload_cap < sizeof(data) ? payload_cap : sizeof(data)" not in store_body
        or "selftest_text_records()" not in dncopy
        or "fgets((char *)data, sizeof(data), in)" in store_body
    ):
        raise SystemExit("source-release gate: dncopy record-mode input must reject NUL and overlong lines")
    retrieve_start = dncopy.find("static int retrieve_file")
    retrieve_end = dncopy.find("static int store_file", retrieve_start)
    retrieve = dncopy[retrieve_start:retrieve_end]
    for marker in (
        '#define DAP_IO_TIMEOUT_SECONDS 30L',
        'static int set_dap_timeouts(int fd)',
        'if (set_dap_timeouts(fd))',
        'static int selftest_socket_timeouts(void)',
        'selftest_socket_timeouts() ||',
    ):
        if marker not in dncopy:
            raise SystemExit(f"source-release gate: dncopy DAP I/O must have bounded peer-idle timeouts: {marker}")

    connect_marker = 'msg[2] = 2U; /* CONNECT data stream */'
    staging_marker = 'begin_staged_output(local_path, &out, &staged_output,'
    completion_marker = 'recv_message(fd, reply, sizeof(reply), DAP_ACCESS_COMPLETE)'
    publish_marker = 'publish_staged_output(&out, &staged_output, local_path,'
    if (
        retrieve_start < 0 or retrieve_end < 0
        or connect_marker not in retrieve
        or staging_marker not in retrieve
        or completion_marker not in retrieve
        or publish_marker not in retrieve
        or not (retrieve.find(connect_marker) < retrieve.find(staging_marker)
                < retrieve.find(completion_marker) < retrieve.find(publish_marker))
        or 'abort_staged_output(&out, &staged_output)' not in retrieve
        or 'out = fopen(local_path, "wb");' in retrieve
        or 'static int selftest_staged_output(void)' not in dncopy
        or 'selftest_staged_output()' not in dncopy
    ):
        raise SystemExit("source-release gate: dncopy retrieval must stage and atomically publish complete output")

    # Local named downloads must stage unseen, preserve an external new
    # writer, and remove private temporary directories on abort/commit.
    for marker in (
        'static void remove_staged_path(char *path)',
        'if (!mkdtemp(tmp))',
        'static const char leaf[] = "/transfer";',
        'O_CREAT | O_EXCL | O_WRONLY | O_NOFOLLOW, 0600',
        '*existed = 0;',
        '*existed = 1;',
        'link(*staged_path, destination)',
        'remove_staged_path(*staged_path);',
        'static int selftest_staged_private_collision(void)',
        'selftest_staged_private_collision()',
        '(info.st_mode & 0777) != 0700',
        'errno != EEXIST',
        'memcmp(data, "OTHER_WRITER", 12U)',
    ):
        if marker not in dncopy:
            raise SystemExit(f"source-release gate: dncopy private/new-output safety guard missing: {marker}")
    if 'fd = mkstemp(tmp)' in dncopy:
        raise SystemExit("source-release gate: public named temp file reintroduced for dncopy")

    # Reject unknown remote DAP record formats rather than silently copying
    # malformed record-mode payloads without required text conversion.
    for marker in (
        'buf[pos] < DAP_RFM_FIX ||',
        'buf[pos] > DAP_RFM_SCR',
        'attr_rfm_zero',
        'attr_rfm_unsupported',
        '!parse_rfm(attr_rfm_zero, sizeof(attr_rfm_zero), &rfm)',
        '!parse_rfm(attr_rfm_unsupported, sizeof(attr_rfm_unsupported), &rfm)',
    ):
        if marker not in dncopy:
            raise SystemExit(f"source-release gate: malformed DAP RFM accepted: {marker}")

    # Malformed remote ATTR menus must not be silently accepted as valid.
    for marker in (
        'decode_ex(buf, len, &pos, 3U, &ignored) || ignored > 7U',
        'return pos == len ? 0 : -1;',
        'attr_missing_rat',
        '!parse_rfm(attr_missing_rat, sizeof(attr_missing_rat), &rfm)',
        'attr_rat_valid',
        'attr_missing_bks',
    ):
        if marker not in dncopy:
            raise SystemExit(f"source-release gate: dncopy incomplete ATTR acceptance: {marker}")

    # Text decoding of CR-delimited DAP streams must retain CRLF state
    # between DATA messages. An independent exact-source repro showed A\r
    # followed by \nB emitted A\n\nB prior to this safeguard.
    for marker in (
        'static int write_text_payload(FILE *out, const unsigned char *data, size_t len,',
        'unsigned char rfm, int *pending_cr)',
        "if (*pending_cr && data[i] == '\\n') {",
        "*pending_cr = data[i] == '\\r';",
        'int pending_cr = 0;',
        '&pending_cr))',
        'static int selftest_stream_crlf_chunks(void)',
        'write_text_payload(out, NULL, 0U, rfm, &pending_cr)',
        'selftest_stream_crlf_chunks() ||',
    ):
        if marker not in dncopy:
            raise SystemExit(f"source-release gate: dncopy DAP stream CRLF split-record regression: {marker}")

    # DAP CONFIG BUFSIZ is a *complete message* limit, not just the data
    # payload. Each peer must honor the lesser advertised size, including
    # three DATA header bytes and potentially smaller independent DEC peers.
    for marker in (
        '#define DAP_BUFFER_LIMIT 2048U',
        'static int negotiate_buffer_limit(',
        'peer = (size_t)config[2] | ((size_t)config[3] << 8U);',
        'if (peer && peer < 12U)',
        '*limit = !peer || peer > DAP_BUFFER_LIMIT ? DAP_BUFFER_LIMIT : peer;',
        'if (len > dap_send_limit) {',
        'errno = EMSGSIZE;',
        'return dniv_recv_record(fd, buf,',
        'cap < dap_send_limit ? cap : dap_send_limit, flags);',
        'config[3] != 8',
        'selftest_buffer_limit()',
        'payload_cap = dap_send_limit - 3U;',
        'data_len = fread(data, 1, payload_cap, in);',
        'data_len < payload_cap',
    ):
        if marker not in dncopy:
            raise SystemExit(f"source-release gate: dncopy DAP negotiated-buffer regression: {marker}")

    dnfald = read_text("userspace/dnfald/dnfald.c")
    for marker in (
        '#define DAP_BUFFER_LIMIT 2048U',
        'static int negotiate_buffer_limit(',
        'peer = (size_t)config[2] | ((size_t)config[3] << 8U);',
        'if (peer && peer < 12U)',
        '*limit = !peer || peer > DAP_BUFFER_LIMIT ? DAP_BUFFER_LIMIT : peer;',
        'if (len > dap_send_limit) {',
        'errno = EMSGSIZE;',
        'return dniv_recv_record(fd, buf,',
        'cap < dap_send_limit ? cap : dap_send_limit, flags);',
        'config[3] != 8U',
        'negotiate_buffer_limit(request, (size_t)got, &dap_send_limit)',
        'sizeof(reply) : dap_send_limit) - 3U;',
        'count = fread(reply + 3U, 1, payload_cap, in);',
        'if (!count && ferror(in))',
        'static int selftest_get_buffer_limit(int rootfd)',
        'selftest_get_buffer_limit(rootfd)',
        'dap_send_limit = 128U;',
        'got > 128',
        'total != sizeof(fill) || frames < 30U',
    ):
        if marker not in dnfald:
            raise SystemExit(f"source-release gate: dnfald DAP negotiated-buffer regression: {marker}")
    for marker in (
        "DNFAL_XATTR_RECORD_FRAMING",
        "save_record_framing(fileno(out), requested_rfm)",
        "write_framed_payload(out, request + off,",
        "load_record_framing(fileno(in), rfm, &framed)",
        "read_framed_payload(in, reply + 3U,",
        "selftest_framed_records(rootfd, DAP_RFM_VAR)",
        "selftest_framed_records(rootfd, DAP_RFM_VFC)",
        "static int selftest_unframed_metadata(int rootfd)",
        "selftest_unframed_metadata(rootfd)",
        "if (record_oriented_rfm(rfm)) {",
        "if (*rfm < DAP_RFM_FIX || *rfm > DAP_RFM_STMCR || *rat > DAP_RAT_MAX) {",
        "parse_attr_ex(buf, len, &pos, 6U, &menu)",
        "parse_attr_ex(buf, len, &pos, 3U, &value)",
        "0x87U, 0x01U, 1U, 0U,",
    ):
        if marker not in dnfald:
            raise SystemExit(f"source-release gate: FAL record framing / extended ATTR regression: {marker}")
    create_start = dnfald.find("static int serve_create")
    create_end = dnfald.find("static int serve_rename", create_start)
    create_body = dnfald[create_start:create_end]
    if (
        create_start < 0
        or create_end < 0
        or "if (fclose(out)) {" not in create_body
        or 'openat(rootfd, ".", O_TMPFILE | O_RDWR | O_CLOEXEC, 0666)' not in create_body
        or "if (fflush(out) || fsync(fileno(out)))" not in create_body
        or "fcntl(fileno(out), F_DUPFD_CLOEXEC, 0)" not in create_body
        or 'linkat(file_fd, "", rootfd, name, AT_EMPTY_PATH)' not in create_body
        or "unlinkat(rootfd, name, 0)" in create_body
        or 'selftest_abort_create(rootfd, "GOOD.TXT")' not in dnfald
        or 'selftest_abort_create(rootfd, "PARTIAL.TXT")' not in dnfald
        or 'selftest_create_swap(rootfd)' not in dnfald
        or 'selftest_create_success(rootfd)' not in dnfald
    ):
        raise SystemExit("source-release gate: dnfald CREATE lacks atomic staging/publish or race regression")
    directory_start = dnfald.find("static int serve_directory")
    directory_end = dnfald.find("static int serve_erase", directory_start)
    directory_body = dnfald[directory_start:directory_end]
    for marker in (
        "errno = 0;\n        ent = readdir(dir);",
        "int read_errno = errno;",
        "int close_rc = closedir(dir);",
        "if (read_errno) {\n                errno = read_errno;\n                return -1;\n            }",
        "if (close_rc)\n                return -1;",
    ):
        if directory_start < 0 or directory_end < 0 or marker not in directory_body:
            raise SystemExit(f"source-release gate: dnfald directory error handling regression: {marker}")

    for marker in (
        "open(root, O_RDONLY | O_DIRECTORY | O_CLOEXEC)",
        "openat(rootfd, name, flags, 0666)",
        "O_NOFOLLOW | O_CLOEXEC | O_NONBLOCK",
        "st.st_nlink != 1",
        "fgetxattr(fd, DNFAL_XATTR_RFM",
        "fsetxattr(fd, DNFAL_XATTR_RFM",
        "renameat(rootfd, oldname, rootfd, newname)",
        "fdopendir(dirfd)",
        "unlinkat(rootfd, name, 0)",
        'open_regular_at(rootfd, "ESCAPE.TXT", 0)',
        'open_regular_at(rootfd, "HARD.TXT", 1)',
        "mkfifo(fifo_path, 0600)",
        'open_regular_at(rootfd, "FIFO.TXT", 1)',
        "errno = EPROTO;",
    ):
        if marker not in dnfald:
            raise SystemExit(f"source-release gate: dnfald root-safety regression: {marker}")

    smtp_fake = read_text("tests/lab/dnsmtpfake.c")
    if "if (fclose(out))\n        goto out;\n    out = NULL;" in smtp_fake:
        raise SystemExit("source-release gate: SMTP lab helper can re-close an invalid stream after final output close failure")
    if "if (fclose(out)) {\n        out = NULL;\n        goto out;\n    }" not in smtp_fake:
        raise SystemExit("source-release gate: SMTP lab helper final output close failure is not invalidated before cleanup")

    dnmail = read_text("userspace/dnmail/dnmail.c")
    dnmail_make = read_text("userspace/dnmail/Makefile")
    if (
        "if (!*from || !*subject ||" not in dnmail
        or "./dnmail -s '' 31.70::TEST body" not in dnmail_make
        or 'rc=$$?; test "$$rc" -eq 2' not in dnmail_make
    ):
        raise SystemExit("source-release gate: empty MAIL-11 subject may lose NSP record boundary")
    for marker in (
        "static int send_body_record(int fd, const char *body)",
        "return len ? send_record(fd, body, len) : 0;",
        "static int selftest_empty_body(void)",
        "selftest_empty_body()",
        "send_body_record(fd, message)",
    ):
        if marker not in dnmail:
            raise SystemExit(f"source-release gate: empty MAIL-11 body handling: {marker}")
    dnmaild = read_text("userspace/dnmail/dnmaild.c")
    for marker in (
        "const char *sendmail_path, int empty_body)",
        "(!empty_body && dniv_send_record(pair[0], \"body\", 4U, 0))",
        "selftest_spool_session(directory, 1, NULL, 1)",
        "after.st_size - before.st_size !=",
    ):
        if marker not in dnmaild:
            raise SystemExit(f"source-release gate: empty MAIL-11 body server regression: {marker}")
    for marker in (
        "int close_errno = 0;",
        "if (close(input_fd))\n        close_errno = errno;",
        "if (close_errno) {\n                errno = close_errno;\n                return -1;\n            }",
        "if (finish_sendmail(-1, child) >= 0 || errno != EBADF)",
        "if (waitpid(child, NULL, WNOHANG) != -1 || errno != ECHILD)",
    ):
        if marker not in dnmaild:
            raise SystemExit(f"source-release gate: dnmaild sendmail-close cleanup regression: {marker}")
    if 'if (!out || fputs("ok\\n", out) == EOF || fclose(out))' in dnmaild:
        raise SystemExit("source-release gate: dnmaild selftest collapses write/close state and can leak or re-close a stream")
    for marker in (
        'if (fputs("ok\\n", out) == EOF)\n        goto out;',
        'if (fclose(out)) {\n        out = NULL;\n        goto out;\n    }',
    ):
        if marker not in dnmaild:
            raise SystemExit(f"source-release gate: dnmaild selftest stream cleanup regression: {marker}")
    for marker in (
        "char line[512];",
        "for (lines = 0U; lines < 32U; lines++)",
        "line[used - 2U] != '\\r'",
        "(line[3] != ' ' && line[3] != '-')",
        "if (code >= 0 && current != code)",
        "selftest_smtp_reply(\"250-First\\r\\n250 Final\\r\\n\"",
        "selftest_smtp_reply(\"250Xgarbage\\n\"",
        "selftest_smtp_reply(hidden_nul, sizeof(hidden_nul), -1)",
        "selftest_smtp_reply(\"550-First\\r\\n250 Final\\r\\n\"",
    ):
        if marker not in dnmaild:
            raise SystemExit(f"source-release gate: dnmaild SMTP response validation regression: {marker}")
    if 'if (fputs("--\\n", out) == EOF || fclose(out))' in dnmaild:
        raise SystemExit("source-release gate: dnmaild can re-close an invalid stream after final spool close failure")
    for marker in (
        'if (fputs("--\\n", out) == EOF || append_complete_spool(root, out))\n        goto fail;',
        'if (fclose(out)) {\n        out = NULL;\n        goto fail;\n    }',
    ):
        if marker not in dnmaild:
            raise SystemExit("source-release gate: dnmaild final spool close failure is not invalidated before cleanup")
    for marker in (
        'static int append_complete_spool(const char *root, FILE *staged)',
        '#include <sys/file.h>',
        '#include <sys/resource.h>',
        'if (flock(fileno(spool), LOCK_EX) ||',
        '(guarded_fd = dup(fileno(spool))) < 0',
        'setvbuf(spool, NULL, _IONBF, 0)',
        'if (fflush(spool) || fsync(guarded_fd))',
        'if (ftruncate(guarded_fd, original.st_size) || fsync(guarded_fd))',
        'if (ftruncate(guarded_fd, original.st_size))',
        'if (fsync(guarded_fd))',
        'selftest_spool_io_rollback(directory, mailbox)',
        'setrlimit(RLIMIT_FSIZE, &limit)',
        'if (fflush(staged) || fseek(staged, 0L, SEEK_SET))',
        'spool = open_mailbox(root);',
        'out = tmpfile();',
        'if (fputs("--\\n", out) == EOF || append_complete_spool(root, out))',
        'selftest_spool_session(directory, 0, NULL, 0)',
        'selftest_spool_session(directory, 1, NULL, 0)',
        'memcmp(victim_buf, "ok\\n", 3U)',
        'memcmp(victim_buf, "ok\\nFrom: sender", 15U)',
        'openat(rootfd, "mailbox.log",',
        "O_APPEND | O_NOFOLLOW | O_CLOEXEC",
        "st.st_nlink != 1",
        'char directory[] = "/tmp/dnmaild-selftest.XXXXXX"',
        "symlink(victim, mailbox)",
        "link(victim, mailbox)",
        "open_mailbox(directory)",
        "O_NONBLOCK, 0600)",
    ):
        if marker not in dnmaild:
            raise SystemExit(f"source-release gate: dnmaild spool-safety regression: {marker}")

    for marker in (
        'static int start_complete_sendmail(FILE *staged, const char *path,',
        'if (sendmail_path && start_complete_sendmail(out, sendmail_path,',
        'if (child > 0)\n        (void)kill(child, SIGKILL);',
        'selftest_sendmail_replay(directory)',
        'selftest_spool_session(root, 0, script, 0)',
        'selftest_spool_session(root, 1, script, 0)',
    ):
        if marker not in dnmaild:
            raise SystemExit(f"source-release gate: dnmaild precompletion external delivery regression: {marker}")
    for marker in (
        'long body_start = -1L;',
        'if (smtp_host && (body_start = ftell(out)) < 0)',
        'if (smtp_host && (memchr(body,',
        'smtp_fd = smtp_open(smtp_host, smtp_port, smtp_from, recipients,',
        'if (fflush(out) || fseek(out, body_start, SEEK_SET))',
        'smtp_write_record(smtp_fd, (const unsigned char *)line,',
        'selftest_smtp_not_before_eom(directory)',
        'if (poll(&watched, 1, 300) != 0)',
    ):
        if marker not in dnmaild:
            raise SystemExit(f"source-release gate: premature SMTP relay regression: {marker}")
    done_smtp = dnmaild.find('if (got == 1 && body[0] == 0U)\n            break;')
    session = dnmaild.split('static int serve(', 1)[1].split('static int selftest_smtp_reply(', 1)[0]
    smtp_launch = session.find('smtp_fd = smtp_open(')
    if done_smtp < 0 or smtp_launch < 0 or \
            smtp_launch < session.find('if (got == 1 && body[0] == 0U)') or \
            session.count('smtp_fd = smtp_open(') != 1:
        raise SystemExit("source-release gate: SMTP must open only after remote MAIL-11 completion")

    done_record = dnmaild.find('if (got == 1 && body[0] == 0U)\n            break;')
    delivery = dnmaild.find('if (sendmail_path && start_complete_sendmail(out, sendmail_path,')
    if done_record < 0 or delivery < done_record or \
            'start_sendmail(sendmail_path' in dnmaild.split('static int serve(', 1)[1]:
        raise SystemExit("source-release gate: external sendmail must not start before complete MAIL-11 input")

    address_range_markers = {
        "userspace/dnmail/dnmail.c": (
            "area < 1U || area > 63U",
            '!parse_target("0.23::ALICE", &addr, &user)',
        ),
        "userspace/dntask/dntask.c": (
            "area < 1U || area > 63U",
            '!parse_spec("0.71::TASK", &spec)',
            "static int run_output(int fd, int binary, int timeout_seconds)",
            "int rc = poll(&ready, 1, timeout_ms);",
            "errno = ETIMEDOUT;",
            "selftest_output_timeout()",
            "selftest_drain_hangup(0) || selftest_drain_hangup(1)",
            "selftest_interactive_stdin_eof()",
            "int rc = poll(fds, stdin_open ? 2 : 1, timeout_ms);",
            "if (received_record)\n            continue;",
            "if (ready.revents & POLLHUP)\n            return 0;",
            "run_output(fd, binary, timeout_seconds)",
        ),
        "userspace/dnlogin/dnlogin.c": (
            "area < 1U || area > 63U",
            '!parse_node("0.1", &addr)',
        ),
        "userspace/dncopy/dncopy.c": (
            "area < 1 || area > 63",
            '!parse_node("0.1", &addr)',
        ),
        "userspace/dnphone/phone.c": (
            "area < 1U || area > 63U",
            '!parse_target("0.23::ALICE", &addr, &user)',
        ),
        "userspace/dnlynx/dnlynx.c": (
            "area < 1U || area > 63U",
            '!parse_node("0.1",&address)',
        ),
    }
    for path, markers in address_range_markers.items():
        source = read_text(path)
        for marker in markers:
            if marker not in source:
                raise SystemExit(f"source-release gate: DECnet area-zero parser regression: {path}: {marker}")

    libdnet_compat = read_text("userspace/libdnet/compat.c")
    libdnet_peek_test = read_text("userspace/libdnet/selftest.c")
    for marker in (
        'if (!(flags & MSG_EOR) || (flags & MSG_PEEK))',
        'return (int)recv(fd, buf, (size_t)len, recv_flags);',
    ):
        if marker not in libdnet_compat:
            raise SystemExit(f"source-release gate: libdnet MSG_EOR PEEK replay regression: {marker}")
    for marker in (
        'static int selftest_eor_peek(void)',
        'MSG_EOR | MSG_PEEK',
        'got != 3 || memcmp(buffer, "abc", 3U)',
        'if (selftest_eor_peek())',
    ):
        if marker not in libdnet_peek_test:
            raise SystemExit(f"source-release gate: libdnet PEEK regression test missing: {marker}")

    libdnet_numeric = read_text("userspace/libdnet/libdnet.c")
    libdnet_selftest = read_text("userspace/libdnet/selftest.c")
    for marker in (
        "area < 1U || area > 63U",
        "node < 1U || node > 1023U",
    ):
        if marker not in libdnet_numeric:
            raise SystemExit(f"source-release gate: libdnet numeric address range regression: {marker}")
    for marker in (
        'dnet_pton(AF_DECnet, "0.1", &addr)',
        'dnet_pton(AF_DECnet, "31.0", &addr)',
    ):
        if marker not in libdnet_selftest:
            raise SystemExit(f"source-release gate: libdnet zero address regression coverage missing: {marker}")

    dnwindow = read_text("tests/lab/dnwindow.c")
    for marker in (
        "ssize_t sent = send(fd, buf, total, flags | MSG_EOR | MSG_NOSIGNAL);",
        "if (sent < 0)",
        "if ((size_t)sent != total) {",
        "errno = EIO;",
    ):
        if marker not in dnwindow:
            raise SystemExit(f"source-release gate: window probe send/errno regression: {marker}")
    if "if (send(fd, buf, total, flags | MSG_EOR | MSG_NOSIGNAL) != (ssize_t)total)" in dnwindow:
        raise SystemExit("source-release gate: window probe again leaves errno undefined on short success")

    dnflow = read_text("tests/lab/dnflow.c")
    for marker in (
        "ssize_t sent;",
        "errno = EMSGSIZE;",
        "sent = send(fd, buf, n + 1U, MSG_EOR | MSG_NOSIGNAL | flags);",
        "if (sent < 0)",
        "if ((size_t)sent != n + 1U) {",
        "errno = EIO;",
    ):
        if marker not in dnflow:
            raise SystemExit(f"source-release gate: flow probe send/errno regression: {marker}")
    if "return send(fd, buf, n + 1U, MSG_EOR | MSG_NOSIGNAL | flags) ==" in dnflow:
        raise SystemExit("source-release gate: flow probe again collapses send result and leaves errno undefined on short success")

    dnlynx = read_text("userspace/dnlynx/dnlynx.c")
    for marker in (
        "static int append_header_record",
        "write_http_body(record + copied, (size_t)got - copied,",
        "large, sizeof(large), &end, &copied",
        "copied != sizeof(header)",
        "buf[12] != ' '",
        "for (i = 13U; i + 1U < len; i++)",
        "buf[i] == '\\r' && buf[i + 1U] == '\\n'",
        "status_code((const unsigned char *)\"HTTP/1.0 200Bad",
        "static int parse_response_headers(",
        "if (has_length && body_written != content_length)",
        "dnlynx: HTTP stage=truncated-body",
        "Content-Length",
        "Transfer-Encoding",
        "selftest_response(\"HTTP/1.0 200 OK\\r\\nContent-Length: 10",
        "selftest_response(\"HTTP/1.0 200 OK\\r\\nContent-Length: 3",
    ):
        if marker not in dnlynx:
            raise SystemExit(f"source-release gate: dnlynx header/body record-boundary regression: {marker}")

    dnhttpd = read_text("userspace/dnhttpd/dnhttpd.c")
    if 'if (!file || fputs("ok\\n", file) == EOF || fclose(file))' in dnhttpd:
        raise SystemExit("source-release gate: dnhttpd selftest collapses write/close state and can leak or re-close a stream")
    for marker in (
        'if (fputs("ok\\n", file) == EOF)\n        goto out;',
        'if (fclose(file)) {\n        file = NULL;\n        goto out;\n    }',
    ):
        if marker not in dnhttpd:
            raise SystemExit(f"source-release gate: dnhttpd selftest stream cleanup regression: {marker}")
    for marker in (
        "O_RDONLY | O_NOFOLLOW | O_CLOEXEC | O_NONBLOCK",
        "fstat(fd, &st)",
        "S_ISREG(st.st_mode)",
        "st.st_nlink != 1",
        'open_root_file(directory, "escape.html")',
        'open_root_file(directory, "hard.html")',
        'open_root_file(directory, "pipe.html")',
        "static int read_bounded_file",
        "ftruncate(good_fd, (off_t)sizeof(boundary))",
        "ftruncate(good_fd, (off_t)sizeof(boundary) + 1)",
    ):
        if marker not in dnhttpd:
            raise SystemExit(f"source-release gate: dnhttpd root-safety regression: {marker}")

    for marker in (
        "if (!newline || newline == request || newline[-1] != '\\r' ||",
        'memcmp(request + length - 4U, "\\r\\n\\r\\n", 4U)',
        "if (!request[i] ||",
        "static int parse_request_line(",
        'sscanf(line, "%15s %511s %31s %c"',
        'strcmp(version, "HTTP/1.0")',
        'strcmp(version, "HTTP/1.1")',
        "static int selftest_bad_request(",
        "selftest_bad_request(directory, hidden_nul,",
        "selftest_bad_request(directory, invalid_version,",
        "selftest_bad_request(directory, extra_token,",
        "selftest_bad_request(directory, incomplete,",
        "selftest_bad_request(directory, bare_lf,",
        "selftest_bad_request(directory, missing_blank,",
        "selftest_bad_request(directory, trailing_bytes,",
        "parse_request_line(valid, sizeof(valid) - 1U,",
        '"HTTP/1.0 400 Bad Request',
        '"Bad Request\\n", 12U',
    ):
        if marker not in dnhttpd:
            raise SystemExit(f"source-release gate: dnhttpd rejects malformed request lines: {marker}")

    dnetdb_source = read_text("userspace/libdnet/dnetdb.c")
    for marker in (
        "static int read_node_line(FILE *file, char *line, size_t cap)",
        "int line_error = 0;",
        "while ((ch = fgetc(file)) != EOF)",
        "if (ch == '\\0' && !line_error)",
        "line_error = EINVAL;",
        "if (used + 1U >= cap && !line_error)",
        "line_error = E2BIG;",
        "if (!line_error)",
        "if (line_error) {",
        "errno = line_error;",
        "int line_rc = read_node_line(file, line, sizeof(line));",
    ):
        if marker not in dnetdb_source:
            raise SystemExit(f"source-release gate: libdnet node-database line-bound safeguard missing: {marker}")
    if "while (fgets(line, sizeof(line), file))" in dnetdb_source:
        raise SystemExit("source-release gate: libdnet node database still fragments overlong physical lines through fgets")
    for stale in (
        "if (ch == '\\0') {\\n            errno = EINVAL;\\n            return -1;",
        "if (used + 1U >= cap) {\\n            errno = E2BIG;\\n            return -1;",
    ):
        if stale in dnetdb_source:
            raise SystemExit("source-release gate: libdnet node database returns before draining a rejected physical line")

    nsp_wire = read_text("include/decnet_iv_nsp_wire.h")
    nsp_unit = read_text("tests/unit/test_phase5_nsp.c")
    if "if (pkt->type == DNIV_NSP_ACK_CONN) {\n        if (len != 3U)" not in nsp_wire:
        raise SystemExit("source-release gate: NSP Connect Acknowledgment must reject trailing bytes")
    for marker in (
        "const unsigned char bad_ca_trailing[] = {0x24,0x03,0x00,0xaa};",
        "dniv_nsp_parse(bad_ca_trailing, sizeof(bad_ca_trailing), &p)",
    ):
        if marker not in nsp_unit:
            raise SystemExit(f"source-release gate: NSP Connect Acknowledgment trailing-byte regression coverage missing: {marker}")

    main_source = read_text("kernel/decnet/decnet_iv_main.c")
    init_start = main_source.index("static int __init dniv_init(void)")
    exit_start = main_source.index("static void __exit dniv_exit(void)")
    init_body = main_source[init_start:exit_start]
    exit_body = main_source[exit_start:main_source.index("module_init(dniv_init);")]
    init_misc = init_body.find("misc_register(&dniv_miscdev)")
    init_sock = init_body.find("dniv_sock_init()")
    if init_sock < 0 or init_misc < 0 or init_misc < init_sock:
        raise SystemExit("source-release gate: management device is exposed before socket/data-plane initialization")
    if "dniv_sock_exit();\n        dniv_eth_exit();" not in init_body:
        raise SystemExit("source-release gate: late misc-register failure does not unwind initialized socket/data-plane state")
    exit_misc = exit_body.find("misc_deregister(&dniv_miscdev)")
    exit_sock = exit_body.find("dniv_sock_exit()")
    if exit_misc < 0 or exit_sock < 0 or exit_misc > exit_sock:
        raise SystemExit("source-release gate: management device is withdrawn after subsystem teardown starts")

    socket_source = read_text("kernel/decnet/decnet_iv_socket.c")
    for marker in (
        "__u32 tx_record_len;",
        "bool tx_record_open;",
        "__u8 bom = (!dsk->tx_record_open && off == 0U) ? 1U : 0U;",
        "dsk->tx_record_len > DNBUFSIZE - size",
        "(sock->type == SOCK_STREAM ||",
        "(msg->msg_flags & MSG_EOR));",
        "dsk->tx_record_len += chunk;",
        "dsk->tx_record_len = 0U;",
        "dsk->tx_record_open = false;",
        "dsk->tx_record_open = true;",
    ):
        if marker not in socket_source:
            raise SystemExit(f"source-release gate: socket partial-record continuation safeguard missing: {marker}")
    nsp_source = read_text("kernel/decnet/decnet_iv_nsp.c")
    if nsp_source.count("(void)dniv_nsp_transmit(remote_node, wire, (__u16)len);") < 3:
        raise SystemExit("source-release gate: queued NSP data/interrupt/control transmit ownership safeguard missing")
    if "reporting its\n     * transient error to the socket caller would invite the same user bytes" not in nsp_source:
        raise SystemExit("source-release gate: queued NSP transmit duplicate-send rationale missing")
    if "the NSP timer still owns." not in nsp_source:
        raise SystemExit("source-release gate: retained NSP control transmit ownership rationale missing")

    record_io = read_text("userspace/common/record_io.h")
    for marker in (
        "while (off < len)",
        "errno == EINTR",
        "errno = EIO;",
        "flags | MSG_EOR | MSG_NOSIGNAL",
        "flags | MSG_TRUNC",
        "(size_t)got > cap",
        "errno = EMSGSIZE;",
    ):
        if marker not in record_io:
            raise SystemExit(f"source-release gate: sequenced-record I/O safeguard missing: {marker}")
    record_consumers = (
        "userspace/dncopy/dncopy.c",
        "userspace/dnfald/dnfald.c",
        "userspace/dnhttpd/dnhttpd.c",
        "userspace/dnlogin/dnlogin.c",
        "userspace/dnlynx/dnlynx.c",
        "userspace/dnmail/dnmail.c",
        "userspace/dnmail/dnmaild.c",
        "userspace/dnmirror/dnmirror.c",
        "userspace/dnnice/dnnice.c",
        "userspace/dnnml/dnnml.c",
        "userspace/dnobject/dnobject.c",
        "userspace/dnphone/dnphoned.c",
        "userspace/dnphone/phone.c",
        "userspace/dntask/dntask.c",
    )
    for path in record_consumers:
        source = read_text(path)
        if '#include "../common/record_io.h"' not in source or "dniv_recv_record(" not in source:
            raise SystemExit(f"source-release gate: {path} is not using bounded sequenced-record receive")
        if "recv(" in source:
            raise SystemExit(f"source-release gate: raw fixed-buffer recv remains in {path}")
    record_senders = record_consumers + ("userspace/dnping/dnping.c",)
    for path in record_senders:
        source = read_text(path)
        if '#include "../common/record_io.h"' not in source or "dniv_send_record(" not in source:
            raise SystemExit(f"source-release gate: {path} is not retrying short sequenced-record sends")
        raw_source = source
        if path == "userspace/dnmail/dnmaild.c":
            raw_source = raw_source.replace('send(pair[0], "12345", 5U, MSG_EOR)', "")
        if "send(" in raw_source:
            raise SystemExit(f"source-release gate: raw sequenced-record send remains in {path}")
    smtp_fake = read_text("tests/lab/dnsmtpfake.c")
    for source, name in ((dnmaild, "dnmaild"), (smtp_fake, "dnsmtpfake")):
        if "if (!done) {\n            errno = EIO;\n            return -1;\n        }" not in source:
            raise SystemExit(f"source-release gate: {name} zero-write failure leaves errno undefined")
    for marker in (
        "socketpair(AF_UNIX, SOCK_SEQPACKET, 0, pair)",
        'send(pair[0], "12345", 5U, MSG_EOR)',
        "errno != EMSGSIZE",
    ):
        if marker not in dnmaild:
            raise SystemExit(f"source-release gate: overlong-record selftest missing: {marker}")

    phone_server = read_text("userspace/dnphone/dnphoned.c")
    for marker in (
        "unsigned char buf[2048];",
        "static int selftest_large_data(void)",
        "unsigned char data[1803];",
        "selftest_large_data()",
    ):
        if marker not in phone_server:
            raise SystemExit(f"source-release gate: PHONE long DATA record compatibility: {marker}")

    ping_client = read_text("userspace/dnping/dnping.c")
    for marker in (
        "got = (int)dniv_recv_record(fd, rx, (size_t)size, 0);",
        "static int selftest_oversize_reply(void)",
        "errno != EMSGSIZE",
        "selftest_oversize_reply()",
    ):
        if marker not in ping_client:
            raise SystemExit(f"source-release gate: dnping oversized MIRROR reply: {marker}")

    persistent_daemons = {
        "dnfald": dnfald,
        "dnhttpd": dnhttpd,
        "dnmaild": dnmaild,
        "dnphoned": read_text("userspace/dnphone/dnphoned.c"),
        "dnmirror": read_text("userspace/dnmirror/dnmirror.c"),
        "dnobject": read_text("userspace/dnobject/dnobject.c"),
    }
    for daemon, source in persistent_daemons.items():
        if f'perror("{daemon}: session");' not in source or "continue;" not in source:
            raise SystemExit(f"source-release gate: {daemon} no longer isolates failed client sessions")
    for daemon in ("dnfald", "dnphoned"):
        source = persistent_daemons[daemon]
        if "int failed = 0;" not in source or "failed = 1;" not in source or "return failed ? 1 : 0;" not in source:
            raise SystemExit(f"source-release gate: {daemon} bounded-session failure accounting missing")
    for daemon in ("dnhttpd", "dnmaild", "dnmirror", "dnobject"):
        source = persistent_daemons[daemon]
        for marker in ("if (once) {", "return 1;", "continue;"):
            if marker not in source:
                raise SystemExit(f"source-release gate: {daemon} once/default session isolation contract missing: {marker}")
    dnetd = read_text("userspace/dnetd/dnetd.c")
    if "(ssize_t)(sizeof(overlong) - 1U) || close(fd))" in dnetd:
        raise SystemExit("source-release gate: dnetd config-bound selftest can close one descriptor twice")
    for marker in (
        "if (close(fd)) {\n        unlink(path);\n        return -1;\n    }",
        "int saved_errno = errno;\n\n        unlink(path);",
        "rc < 0 && saved_errno == E2BIG",
    ):
        if marker not in dnetd:
            raise SystemExit(f"source-release gate: dnetd config-bound selftest cleanup regression: {marker}")
    for marker in (
        "static void reap_children(int signo)",
        "while (waitpid(-1, NULL, WNOHANG) > 0)",
        "action.sa_flags = SA_RESTART | SA_NOCLDSTOP;",
        "return sigaction(SIGCHLD, &action, NULL);",
        "if (!once && install_child_reaper())",
        "if (selftest_reaper() || selftest_config_line_bound() ||",
        "selftest_config_nul())",
        "static int read_config_line(FILE *file, char *line, size_t cap)",
        "int line_rc = read_config_line(file, line, sizeof(line));",
        "if (ch == 0) {",
        "errno = EILSEQ;",
        "if (len + 1U >= cap) {",
        "if (len == cap - 1U && line[len - 1U] != '\\n') {",
        "static int selftest_config_line_bound(void)",
        "static int selftest_config_nul(void)",
        "char overlong[2200]",
        "errno == E2BIG",
        "char bad_option[] =",
        "parse_line(bad_option",
        "if (text[1] != '\\0' && text[1] != ',') {",
    ):
        if marker not in dnetd:
            raise SystemExit(f"source-release gate: dnetd child-reaping safeguard missing: {marker}")
    if "while (fgets(line, sizeof(line), file))" in dnetd:
        raise SystemExit("source-release gate: dnetd must reject embedded NUL bytes in physical config lines")
    for marker in (
        "if (token) {",
        "errno = E2BIG;",
        'char too_many[] =',
        "parse_line(too_many",
    ):
        if marker not in dnetd:
            raise SystemExit(f"source-release gate: dnetd argument-limit regression: {marker}")
    dnetd_isolation = '''            if (policy < 0) {
                perror("dnetd: accept policy");
                close(fd);
                if (once) {
                    close_listeners(services, service_count);
                    return 1;
                }
                continue;
            }'''
    if dnetd_isolation not in dnetd:
        raise SystemExit("source-release gate: dnetd accept-policy session isolation contract missing")

    dnmirror = persistent_daemons["dnmirror"]
    if 'perror("dnmirror: access");' not in dnmirror or "if (once) {" not in dnmirror:
        raise SystemExit("source-release gate: dnmirror access-session isolation contract missing")

    state = read_text("docs/PROJECT_STATE.md")
    goal = state.split("## Goal", 1)[1].split("## References and licensing", 1)[0]
    if "portable source release" not in goal or "Deliver reproducible x86_64/aarch64 images" in goal:
        raise SystemExit("source-release gate: current project goal still advertises disk-image delivery")

    scratch_readme = read_text("scratch/README.md")
    for stale in ("sealed format-2 QCOW2 checkpoint", "rolling VM checkpoint safeguards", "Resume exists only for files that were explicitly uploaded as artifacts"):
        if stale in scratch_readme:
            raise SystemExit(f"source-release gate: stale VM persistence contract remains in scratch documentation: {stale}")
    for required in ("source-independent architecture foundation", "Actions cache", "never accepted as resume input"):
        if required not in scratch_readme:
            raise SystemExit(f"source-release gate: current VM persistence contract missing from scratch documentation: {required}")

    handover = read_text("docs/HANDOVER.md")
    if "four exact-SHA acceptance depths" not in handover:
        raise SystemExit("source-release gate: handover acceptance-depth model is stale")
    for required in (
        "three independent comprehensive zero-defect semantic reviews",
        "An altered source",
        "resets the formal scan count to 0/3",
        "re-prove applicable canonical PP evidence",
    ):
        if required not in handover:
            raise SystemExit("source-release gate: handover does not enforce current release audit order")
    for path in ("README.md", "docs/ROADMAP.md", "docs/ARCHITECTURE.md", "docs/PRE_PRODUCTION_TEST.md"):
        value = read_text(path)
        for stale in ("self-booting QCOW2/RAW images", "Release images remain QCOW2-first", "exact release image"):
            if stale in value:
                raise SystemExit(f"source-release gate: stale release-image contract in {path}: {stale}")
    print("source-release gate passed")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
