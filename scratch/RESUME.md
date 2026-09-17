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

The two-node lab uses `tests/lab/dniv_lab.py`, a Python direct-QEMU controller with QMP shutdown, Linux bridge/TAP networking, packet capture, serial marker assertions and disposable qcow2 node overlays. Writable inner-VM checkpoints remain retired. Runtime/evidence lives below short `/tmp/dniv-*` paths and compact evidence is copied back to `scratch/runtime/`.

The two architecture slots retain immutable source-independent foundations. Their session identifier is `outer-v2-<arch>-<foundation-fingerprint>`, derived from `image/ubuntu-base/images.env` and `build-foundation.sh`, never from the candidate SHA. A foundation contains Ubuntu userspace, the pinned kernel/initrd, build headers/toolchain, Python, libpcap and independent-reference runtime dependencies. `git` is included because pinned PyDECnet queries its Git revision at startup. No project source, module/tools, smoke service or candidate SHA is persistent.

Each exact candidate is injected only into a disposable derived image by `tests/lab/prepare-candidate-image.sh`; the reference image is likewise disposable and Route20/PyDECnet remain independently pinned. The persistence architecture is closed and is not to be reopened without concrete evidence that the foundation mechanism itself is defective.

Exact-head candidate `5f4fdc5b3d1bcef87e56ac64b8c3b287f504eddb` established that the persistence mechanism works: repository policy, project state and both native builds passed; amd64 Python E1 passed from a restored foundation; ARM64 reached QEMU but produced no serial output. The same lineage exposed the Route20 `/run` execute restriction and PyDECnet's missing `git` runtime prerequisite. Both were corrected without modifying either reference implementation.

Exact-head candidate `317deebe5a916ca28e576074fab7e310b15b5d37` passed repository policy, project state, native builds and reference baselines. Its ARM64 VM foundation rebuild failed on `/boot/vmlinuz-7.0.0-31-generic` with `unsupported arm64 kernel format; refusing non-Image fallback`, proving the remaining ARM fault was wrapper normalization rather than DECnet. On amd64, the Route20 L1 interop job proved the candidate received and parsed a valid INIT from Route20 node 31.71, but the Route20 daemon exited about 3.5 seconds after its READY marker and before a stable adjacency formed.

ARM64 direct boot normalization now accepts only a bounded chain of recognized formats: raw Linux Image, whole-file gzip/Zstd, EFI-zboot gzip/Zstd, or a structurally valid PE/COFF wrapper containing exactly one bounded `.linux` section. Every path ends by requiring the raw `ARM\x64` Linux Image magic at offset 56. Unknown/malformed formats fail closed. Both image builders are bound to the helper's exact SHA-256, so this change intentionally generates a new foundation fingerprint and one new foundation build per architecture.

The Route20 launcher still runs the exact pinned binary from `/usr/local/libexec`, but now emits the Route20 syslog tail and matching kernel crash lines if the daemon dies. This is diagnostic only: no Route20 source, configuration semantics or protocol behavior is changed. The next interop evidence must identify the real runtime cause before candidate DECnet code is altered.

Exact-head candidate `a04d2a4ec8687f21fafce1950d339b983f15c973` proved ARM64 direct boot is now functional. VM run `35262769735` normalized the real Ubuntu kernel through `pe-linux+efi-zboot:zstd+raw`, built and cached the foundation, injected the exact candidate, formed router adjacency and survived the primary-MAC change. The amd64 E1 job passed. ARM64 stopped only because the harness sampled total routing and hello counters in separate commands, allowing a concurrent hello to create a false `bad-stats`; DN70 therefore exited before transmitting the 40 unicast probes and DN71 subsequently reported zero receive delta.

The current candidate replaces those independent reads with one logical counter snapshot plus a bounded retry when the kernel's independently read atomics momentarily report `rx_frames < hello_rx`. A host-side regression deliberately injects one inconsistent sample and requires the next coherent sample to succeed, while permanently inconsistent samples must exhaust the retry bound and fail. Kernel and protocol behavior are untouched.

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
| Infrastructure status | architecture and ARM64 direct boot closed; E1 harness sampling fix awaiting exact acceptance |

## Persistent run index

Run IDs are lineage, not execution state. Persistent execution input is limited to the verified source-independent architecture foundation cache. Mutable workflow state remains below ignored `scratch/runtime/`; compact evidence never substitutes for exact source/tree verification.

Acceptance lineage for `5f4fdc5b3d1bcef87e56ac64b8c3b287f504eddb`: repository-policy/dispatcher `35256346698`; native build `35256391400` green on amd64 and arm64; project-state `35256393889` green; Python VM `35256398678` with amd64 green and ARM64 zero-serial direct-boot failure; interoperability `35256400954` exposed the Route20 `/run` and PyDECnet `git` runtime blockers.

Acceptance lineage for `317deebe5a916ca28e576074fab7e310b15b5d37`: repository policy, project state, native build and reference baselines were green; VM lab run `35259650843` failed while normalizing the ARM64 foundation kernel; interop run `35259653065` produced the amd64 Route20 L1 `reference-exited` evidence while ARM64 modes remained blocked at foundation construction.

Acceptance lineage for `a04d2a4ec8687f21fafce1950d339b983f15c973`: repository-policy/dispatcher `35262720736`, native build `35262761176` and project-state `35262763814` were green. VM lab `35262769735` passed amd64 E1 and proved ARM64 foundation/direct boot, adjacency and MAC-change operation before the counter-sampling race produced `bad-stats` on DN70 and the consequent zero unicast delta on DN71.

## Next action

Run exact-head acceptance for the current `main`, taking ARM64 E1 first. Require the counter-snapshot regression and mechanical/build/state gates to pass. If ARM64 E1 is green, confirm amd64 remains green and continue the full exact-SHA reference/interoperability set. Treat Route20 runtime diagnostics as authoritative for any renewed `reference-exited` result and change DECnet protocol code only for a demonstrated protocol defect.
