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

# Scratch Resume Index

## Current checkpoint

Phase 3 remains active and all substantive work stays on `main`. Candidate promotion is controlled only by exact-SHA mechanical, build, VM, reference, protocol and interoperability gates.

The two-node lab uses `tests/lab/dniv_lab.py`, a Python direct-QEMU controller with QMP shutdown, Linux bridge/TAP networking, packet capture, serial marker assertions and disposable qcow2 node overlays. Writable inner-VM checkpoints remain retired.

The two architecture slots retain immutable source-independent foundations across acceptance sessions. The session identifier is `outer-v2-<arch>-<foundation-fingerprint>`. The fingerprint is derived from `image/ubuntu-base/images.env` and `build-foundation.sh`, not the project source SHA. The persisted payload is `base.qcow2`, `boot/vmlinuz`, `boot/initrd.img`, `session.env` and `SHA256SUMS`.

A foundation contains Ubuntu userspace, the pinned kernel/initrd, build headers/toolchain, Python, libpcap and independent-reference runtime dependencies. `git` is included because the pinned PyDECnet implementation queries its Git revision at startup. The foundation explicitly contains no project source, module/tools, smoke services or candidate SHA. Restores verify architecture, fingerprint, Ubuntu release/snapshot, all SHA-256 sums and `qemu-img check`, and reject a manifest containing `SOURCE_SHA`.

Each exact candidate is injected only into a disposable derived image by `tests/lab/prepare-candidate-image.sh`. That script archives exact `HEAD`, builds the module and userspace against the foundation's pinned guest headers, records the candidate SHA, and installs the test entry points without running `apt`. The reference image is also disposable and receives only the current harness/runtime helper; Route20/PyDECnet payloads remain independently pinned.

The VM workflow places Python-lab runtime below a short `/tmp/dniv-*` path. Serial/pcap evidence is copied back to `scratch/runtime/`; qcow2 and QMP files are deleted and excluded from uploaded evidence. The persistence architecture is closed; current work corrects executable/runtime prerequisites and direct-boot artifact bytes, not the architecture.

Exact-head candidate `5f4fdc5b3d1bcef87e56ac64b8c3b287f504eddb` established the present boundary. Repository policy, project-state, amd64 build and arm64 build all passed. The amd64 Python E1 VM job passed completely from a restored `outer-v2` foundation and disposable candidate image. The arm64 Python VM job restored the same class of foundation and injected the exact candidate successfully, but two QEMU processes remained alive with completely empty serial logs until the 300-second gate timeout. Raising RAM, selecting GIC explicitly and enabling the PL011 early console did not change this, so the remaining arm64 fault is the kernel artifact/loader boundary rather than DECnet execution.

Independent interoperability on that candidate also moved beyond the prior blockers. QEMU vvfat now mounts through `/dev/vdb1`. Route20 then failed with `Permission denied` when executing a correctly mode-0755 binary copied below `/run`; the reference harness now installs the verified Route20 executable under `/usr/local/libexec` and retains only transient configuration/state under `/run`. PyDECnet reached `DNIV-REF-READY`, then its exact pinned `version.py` failed with `FileNotFoundError: git`; the foundation now carries `git` as a reference-runtime dependency rather than altering PyDECnet.

ARM64 direct boot is corrected at image construction. `image/ubuntu-base/normalize-arm64-kernel.sh` recognizes a raw Linux Image or gzip/Zstd EFI-zboot, extracts a raw Image, requires the `ARM\x64` header, and rejects any opaque fallback. `build-foundation.sh` and `build-image.sh` are bound to the exact normalizer SHA-256, and the image-builder policy gate verifies both the helper behavior and binding. Because the foundation recipe bytes change, acceptance for this state intentionally uses a new foundation fingerprint and performs a one-time rebuild per architecture. Subsequent ordinary candidates reuse that new foundation.

Repository branch policy remains exactly one remote branch, `refs/heads/main`. Repository-policy/control jobs do not consume protocol-lab concurrency slots. GitHub-owned actions, including cache restore/save, remain pinned to immutable full SHAs.

The older `outer-v1-<arch>-<source-sha>` cache layout is obsolete. `outer-v2` remains the final persistence boundary; do not reopen that design without concrete evidence that the foundation mechanism itself is defective.

| Field | Current value |
| --- | --- |
| Protocol phase | Phase 3 |
| Working ref | `main` only |
| Remote branch invariant | only `refs/heads/main` |
| Hosted job ceiling | 75 minutes |
| Protocol runner queue policy | architecture-specific `dniv-runner-*`, `queue: max` |
| VM lifecycle | Python direct QEMU/QMP for two-node gate |
| Persistent outer state | source-independent architecture foundation |
| Outer session ID | `outer-v2-<arch>-<foundation-fingerprint>` |
| Exact candidate state | disposable derived qcow2 |
| Inner VM disk state | disposable qcow2 overlays |
| Writable inner VM checkpoint artifacts | retired |
| Interop prior-run evidence restore | retired |
| Compact evidence retention | 30 days maximum |
| Acceptance child binding | parent run ID + exact expected SHA |
| Infrastructure status | architecture closed; ARM artifact/reference-runtime corrections pending exact acceptance |

## Persistent run index

Run IDs remain lineage, not execution state. Persistent execution input is limited to the verified source-independent architecture foundation cache. Mutable workflow state remains below ignored `scratch/runtime/`; compact evidence may be uploaded, but it never substitutes for exact source/tree verification or becomes writable guest state for a later run.

Acceptance lineage for `5f4fdc5b3d1bcef87e56ac64b8c3b287f504eddb`: repository-policy/dispatcher `35256346698`; native build `35256391400` green on amd64 and arm64; project-state `35256393889` green; Python VM `35256398678` with amd64 green and arm64 zero-serial direct-boot failure; interoperability `35256400954`, where amd64 Route20 exposed the `/run` execute restriction and amd64 PyDECnet exposed the missing `git` runtime dependency while arm64 remained blocked before guest execution.

## Next action

Run exact-head acceptance for this ARM64 raw-Image/reference-runtime correction. Expect one new foundation cache generation because the recipe fingerprint changes. Prove amd64 E1 remains green, arm64 reaches serial/DECnet execution, Route20 executes from the root filesystem, PyDECnet remains alive with `git` available, and then resume Phase 3 protocol/interoperability debugging from the first genuine DECnet failure.
