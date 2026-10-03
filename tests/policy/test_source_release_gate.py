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

ROOT = Path(__file__).resolve().parents[2]

def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")

def main() -> int:
    required = (
        "build.sh", "install.sh", "uninstall.sh", "INSTALL.md",
        "docs/DELIVERY.md", "docs/FEATURES.md", "docs/COMPONENTS.md",
        "tools/build-source-release.sh", ".github/workflows/source-release.yml",
    )
    for path in required:
        if not (ROOT / path).is_file():
            raise SystemExit(f"source-release gate: missing {path}")
    if (ROOT / ".github/workflows/release-image.yml").exists():
        raise SystemExit("source-release gate: obsolete release-image workflow remains")
    if (ROOT / ".github/workflows/portability.yml").exists():
        raise SystemExit("source-release gate: obsolete checkout-built portability workflow remains")
    workflow = read_text(".github/workflows/source-release.yml")
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

    area31_smoke = read_text("tests/lab/dniv-area31-smoke.sh")
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
        'http_out="$scratch/qcocal-http.out"',
        'http_err="$scratch/qcocal-http.err"',
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
    for forbidden in ("qemu-system", "dniv.raw", "Release Image"):
        if forbidden in workflow:
            raise SystemExit(f"source-release gate: disk-image release behavior remains: {forbidden}")
    qcow2_lines = [line for line in workflow.splitlines() if ".qcow2" in line]
    for line in qcow2_lines:
        if "-name '*.qcow2'" not in line and "audit.qcow2" not in line:
            raise SystemExit(f"source-release gate: unexpected qcow2 release behavior remains: {line.strip()}")
    if not any("-name '*.qcow2'" in line for line in qcow2_lines) or not any("audit.qcow2" in line for line in qcow2_lines):
        raise SystemExit("source-release gate: generated-payload qcow2 negative is incomplete")
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
    for marker in ("safe install manifest not found", "normalized absolute non-root path", "\"$path\" != *$'\\n'*", "\"$path\" != *$'\\r'*", '"$path" != *"//"*', "staged path crosses symlink parent", "mapfile -t paths", "safe_default_module_path", "module_root_is_default", "module_releases", "required command not found: depmod", 'if [[ -z "$destdir" && -n ${MODULE_ROOT:-} ]]; then', "custom MODULE_ROOT is supported only with non-empty DESTDIR"):
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

    dispatcher = read_text(".github/workflows/repository-policy.yml")
    if "SOURCE_RELEASE source-release.yml" not in dispatcher or "RELEASE_IMAGE release-image.yml" in dispatcher:
        raise SystemExit("source-release gate: acceptance dispatcher not synchronized")
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

    dnfald = read_text("userspace/dnfald/dnfald.c")
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
    ):
        if marker not in dnfald:
            raise SystemExit(f"source-release gate: dnfald root-safety regression: {marker}")

    dnmaild = read_text("userspace/dnmail/dnmaild.c")
    for marker in (
        'openat(rootfd, "mailbox.log",',
        "O_APPEND | O_NOFOLLOW | O_CLOEXEC",
        "st.st_nlink != 1",
        'char directory[] = "/tmp/dnmaild-selftest.XXXXXX"',
        "symlink(victim, mailbox)",
        "link(victim, mailbox)",
        "open_mailbox(directory)",
    ):
        if marker not in dnmaild:
            raise SystemExit(f"source-release gate: dnmaild spool-safety regression: {marker}")

    dnhttpd = read_text("userspace/dnhttpd/dnhttpd.c")
    for marker in (
        "O_RDONLY | O_NOFOLLOW | O_CLOEXEC | O_NONBLOCK",
        "fstat(fd, &st)",
        "S_ISREG(st.st_mode)",
        "st.st_nlink != 1",
        'open_root_file(directory, "escape.html")',
        'open_root_file(directory, "hard.html")',
        'open_root_file(directory, "pipe.html")',
    ):
        if marker not in dnhttpd:
            raise SystemExit(f"source-release gate: dnhttpd root-safety regression: {marker}")

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
    for path in ("README.md", "docs/ROADMAP.md", "docs/ARCHITECTURE.md", "docs/PRE_PRODUCTION_TEST.md"):
        value = read_text(path)
        for stale in ("self-booting QCOW2/RAW images", "Release images remain QCOW2-first", "exact release image"):
            if stale in value:
                raise SystemExit(f"source-release gate: stale release-image contract in {path}: {stale}")
    print("source-release gate passed")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
