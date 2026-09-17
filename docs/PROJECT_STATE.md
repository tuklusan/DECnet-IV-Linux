<!-- ============================================================================ -->
<!-- Copyright (c) 2026 Supratim Sanyal of SANYALnet Labs. -->
<!-- Proprietary rights reserved except as expressly licensed herein. -->
<!-- -->
<!-- DECnet-IV-Linux -->
<!-- This file is governed by the SANYALnet Labs Non-Commercial License in the -->
<!-- root LICENSE file. Non-Commercial use is permitted; Commercial Use and use -->
<!-- for AI/ML model training are prohibited unless separately authorized. -->
<!-- -->
<!-- Attribution is required: "Based on original work by Supratim Sanyal of -->
<!-- SANYALnet Labs." See LICENSE for full terms, warranty disclaimer, termination, -->
<!-- patent, trademark, and governing-law provisions. -->
<!-- ============================================================================ -->

# Project State

This is the authoritative continuity record for DECnet-IV-Linux. Read `docs/HANDOVER.md`, this file, `scratch/RESUME.md`, `docs/ROADMAP.md`, `docs/ARCHITECTURE.md`, `docs/TEST_LAB.md` and `docs/PRE_PRODUCTION_TEST.md` before changing protocol, image or acceptance behavior.

## Goal

Build a complete native DECnet Phase IV stack for maintained Linux as an out-of-tree kernel module plus DECnet/Linux userspace. Deliver reproducible x86_64/aarch64 images and prove behavior against independent implementations and later real DEC systems.

## References and licensing

Preferred exact reference pins remain Route20 `b94115b2615c6463d1f006924ceeadde8e2d4367`, PyDECnet live `a7194be8d72dea6f9eb4f77083f056f53e80df58`, PyDECnet tests `9a844987bf3a1450632dee8d37e60a23a453bad3`, LinuxDECnet `ff39eef045d1e4b7b72a3d40111e89c07a473398`, and SIMH `5b73b1032b52d19bf80752ea4d9cbbdc92e7b5e0`. The product license is the canonical root `LICENSE`; the kernel reports `MODULE_LICENSE("Proprietary")`.

The root `references/` directory records the development source-of-truth hierarchy and distilled protocol/reference index. Digital DNA Phase IV functional specifications are normative; PyDECnet and Route20 are independent implementation cross-checks; LinuxDECnet is the Linux ABI/userspace compatibility reference; SIMH plus genuine DEC operating systems are interoperability oracles. Third-party documents and code retain their original licenses.

## Repository discipline

- Work directly on `main`; do not create or use feature branches.
- The remote branch invariant is exactly `refs/heads/main`.
- Every substantive commit updates this file and `scratch/RESUME.md` in the same commit.
- Acceptance applies only to one exact unchanged `main` commit and children are bound to parent run ID plus exact expected SHA.
- Hosted jobs have explicit timeouts of at most 75 minutes; protocol concurrency uses architecture-specific `dniv-runner-*` slots with `queue: max` and `cancel-in-progress: false`.
- GitHub-owned actions remain pinned to immutable full SHAs.
- Compact evidence retention is at most 30 days. Transient candidate images, VM overlays and QMP sockets are never acceptance state.
- Candidate promotion is determined only by documented exact-SHA mechanical, build, VM, reference, protocol and interoperability gates.

## Phase status

### Phase 1

Foundation complete: UAPI v2, `decnet_iv.ko`, configurable identity, Routing Layer EtherType registration/counters, `dnctl`, centralized test addressing, unit tests and native x86_64/aarch64 build gates.

### Phase 2

Foundation complete: pinned Ubuntu Base 26.04.1 amd64/arm64 rootfs files and package snapshot `20260915T000000Z`, deterministic ext4/QCOW2 construction, exact guest kernel/module/userspace build, direct kernel/initrd boot, independent VMs, packet capture and serial evidence. Release-image integrity retains `qemu-img check` and logical RAW/QCOW2 equality.

### Phase 3

Implementation remains active. Router/endnode hello generation/parsing, periodic hello, per-interface adjacencies, 3.1x listen expiry, DR election, router-router INIT/UP behavior, endnode admission/router selection, L2 cross-area behavior, 33-router/interface admission, protocol source MACs, DECnet unicast filters and primary-MAC-change survival are implemented and covered by the E1/interop harnesses.

The VM persistence architecture is closed. Source-independent `outer-v2-<arch>-<foundation-fingerprint>` foundations contain Ubuntu userspace, the pinned guest kernel/initrd, headers/compiler and independent-reference runtime dependencies, but no candidate source or SHA. `tests/lab/prepare-candidate-image.sh` and `tests/lab/prepare-reference-image.sh` derive disposable exact-candidate/reference images without package installation. `tests/lab/dniv_lab.py` launches direct QEMU guests, TAP/bridge networking, packet capture and serial evidence, and removes disposable disks and sockets after each run.

Exact-head candidate `5f4fdc5b3d1bcef87e56ac64b8c3b287f504eddb` proved the persistence architecture was no longer the blocker: repository policy, project state and native amd64/arm64 builds were green, and amd64 Python E1 passed from a restored foundation. ARM64 restored and injected the candidate but produced no serial output while QEMU remained alive, isolating the fault to the direct-boot kernel artifact/loader boundary. That run also exposed two reference-runtime defects: Route20 could not execute from `/run`, and pinned PyDECnet required `git` at startup. Route20 is now installed under `/usr/local/libexec`; `git` is a legitimate foundation dependency.

Candidate `317deebe5a916ca28e576074fab7e310b15b5d37` then passed repository policy, project state, native builds and reference baselines. Its ARM64 VM path failed while normalizing Ubuntu 26.04's `7.0.0-31-generic` boot artifact because the helper recognized raw Image and EFI-zboot but not the additional wrapper presented by that package. The amd64 Route20 L1 interoperability job advanced far enough to prove the reference emitted a valid router INIT for node 31.71 and the candidate parsed it, but Route20 exited about 3.5 seconds after its READY marker before a stable adjacency formed. The captured LAN trace shows the Route20 INIT followed by loss of reference traffic; this is reference-runtime evidence, not yet a candidate adjacency defect.

The ARM64 normalizer now treats the kernel artifact as a bounded chain of recognized containers. It accepts a raw ARM64 Linux Image, whole-file gzip or Zstd, EFI-zboot gzip/Zstd, and a structurally valid PE/COFF wrapper with exactly one bounded `.linux` section. Each extracted layer is re-evaluated, nesting is bounded, and success still requires the raw Linux `ARM\x64` magic at offset 56. Unknown or malformed wrappers are rejected. Both image builders remain bound to the exact helper SHA-256, so changing the helper intentionally changes the foundation fingerprint and forces one foundation rebuild per architecture.

The Route20 reference launcher now preserves failure evidence instead of merely reporting `reference-exited`: on an unexpected Route20 death it emits the Route20 syslog tail and relevant kernel crash lines into the serial log. It does not patch, wrap or otherwise alter the pinned Route20 implementation. The captured amd64 L1 evidence from interop run `35262772964`, job `105342341317`, now identifies the reference failure: Route20 completes Ethernet/circuit startup and then the kernel reports `dniv-route20-re[285]: segfault at 0 ip 0000000000000000 ... error 14`. Candidate protocol code must not be changed for that demonstrated reference-runtime crash; the pinned Route20 startup/callback path must be diagnosed separately.

Exact-head candidate `a04d2a4ec8687f21fafce1950d339b983f15c973` cleared the ARM64 boot boundary in VM run `35262769735`: the real Ubuntu 26.04 kernel normalized through `pe-linux+efi-zboot:zstd+raw`, the foundation and candidate injection completed, and both routers reached UP adjacency after the runtime primary-MAC change. The amd64 E1 job passed. ARM64 then failed in the harness because `Routing frames received` and `Hello frames received` were sampled by separate `dnctl stats` calls; a hello arriving between calls manufactured `hello > routing` and DN70 exited before its unicast transmit loop, after which DN71 correctly observed zero unicast receive delta.

Exact-head candidate `38c5b49e53c648f6514f52ebff84a93331a4732a` proved the coherent counter-snapshot repair. Acceptance parent `35265712742`, its dispatcher, the host-side stats regression and the ARM64 native build were green. In VM run `35265759834`, both ARM routers completed the unicast stage with `delta=40`; DN71 entered the intentional silent interval and DN70 expired adjacency 31.71 correctly. The only failure was the host controller's 300-second deadline: DN71 began the prescribed module restart at guest uptime about 302 seconds, immediately after the controller deadline had elapsed, so the VMs were terminated before restart adjacency/recovery markers could occur. This is a bounded test-duration defect, not a DECnet protocol failure.

The VM lab therefore keeps amd64 at a 300-second controller budget and gives ARM64 360 seconds. The observed restart point plus the existing 30-second bounded adjacency wait, five-second recovery observation and shutdown margin fit inside 360 seconds while the enclosing job remains capped at 40 minutes. No guest behavior, kernel code or protocol timing is relaxed.

Exact-head `31fc8e00d1c46ffd5cc74c6663c287753a0b7e5d` then completed the guest-side ARM64 E1 sequence in VM run `35266940092`: both nodes reached bidirectional unicast `delta=40`, DN70 expired DN71, restart INIT was observed, adjacency recovered and both guests emitted `DNIV-E1-PASS`. amd64 E1 was green. The ARM64 job failed only in host PCAP validation because DN70 emitted one All-End-Nodes hello during DN71 silence. The harness comment required DN71 to return after listener expiry but before DR eligibility, yet its 12-second silence exceeded the implemented 2-second hello × 3.1 listener multiplier plus 5-second DR delay = 11.2 seconds. The negative DR assertion was therefore self-contradictory on slower ARM execution.

The E1 silence interval is now 7 seconds. A host regression derives listener expiry and DR delay from the actual wire/kernel constants and requires `expiry < silence < expiry + DR delay`; it rejects the former 12-second interval. Acceptance run `35285482332` proved the updated license scanner and all earlier policy checks green, then exposed a regression-test bug: the smoke script contains two valid L1-router `hello_interval=2` module-load sites. The regression now requires all router interval occurrences to agree instead of requiring exactly one. No kernel or DECnet protocol behavior is changed.

Exact-head acceptance for `e7ee147f40bcea7525f9a25499fa9f59974cb9b6` closed the E1 gate: repository policy/dispatcher, both native builds, project state, both pinned reference baselines, and both amd64/ARM64 E1 VM jobs were green. ARM64 reported `e1-silence regression passed: expiry=6.2s silence=7s dr=11.2s` and `python-lab: E1 pass on aarch64 ... captured 442 DECnet frames`. Interop run `35285622023` then exposed a separate ARM64 harness bound: the Route20 reference VM was terminated by the host's hardcoded 90-second READY deadline while still finishing normal boot, reaching root-filesystem handoff only around guest uptime 80 seconds. Route20 had not started, so this failure is neither the known Route20 null-IP crash nor a candidate protocol defect.

Interop reference readiness is bounded by host architecture: amd64 remains 90 seconds. Exact-head run `35286846863` disproved the first ARM64 increase to 150 seconds: Route20 routing job `105420965692` and Route20 endnode job `105424436668` both hit the readiness deadline before `DNIV-REF-READY`, at roughly 126 and 124 seconds of guest uptime while systemd was still starting. ARM64 therefore receives 240 seconds for both initial and restart reference boots. A workflow-guard regression requires exactly those bounded values and both READY waits to use the architecture-selected value. Candidate, reference, and protocol semantics are unchanged.

Repository policy and acceptance dispatch remain isolated from protocol-lab runner concurrency. Release-image construction remains a separate exact-source gate and is not inferred from the cached protocol foundation.

The license scanner prunes `__pycache__` and `.git` directories at Git enumeration time for both exact-tree and staged scans, at any depth. Their contents never enter header/license validation; ordinary tracked files and symlink blobs remain in scope.

## Test addressing

Ordinary lab addressing remains area 31, nodes 70 through 79, names DN70 through DN79. The live L2 interoperability case deliberately uses an independent peer in area 32.

## Pre-production acceptance

`docs/PRE_PRODUCTION_TEST.md` is the consolidated production procedure. Required tests must execute with complete evidence; documentation alone is never green. Long campaigns reuse immutable source-independent architecture foundations while keeping exact-candidate and writable guest state disposable.

## Resume point

Phase 3 is the active workstream. Repository policy, native builds, project continuity, reference baselines, ARM64 direct boot, coherent counter sampling, controller budget and two-architecture E1 behavior are closed on the current lineage. The current harness change extends the ARM64 interop reference-guest READY bound from the disproven 150 seconds to 240 seconds while preserving amd64 at 90 seconds; it does not change kernel or DECnet behavior.

The next independent blocker is Route20 stability: the retained diagnostics now show a null-instruction-pointer userspace segfault immediately after Route20 circuit startup. That reference-runtime crash must be diagnosed in the exact pinned Route20 fork before any candidate DECnet protocol change is considered for those failed interop cases.

## Next action

Run exact-head acceptance on `main`. Require the interop-readiness regression plus the already-green mechanical/build/state/reference/E1 gates. On ARM64, require the reference guest to reach READY within 240 seconds before classifying any Route20 behavior. If ARM64 then reproduces the null-instruction-pointer Route20 crash already proven on amd64 job `105420965768`, classify it as the same independent reference-runtime blocker. Add diagnostic-only stack/core or sanitizer evidence for Route20 without changing normal reference semantics before considering any candidate DECnet code change.
