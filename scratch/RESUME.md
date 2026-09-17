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

A foundation contains Ubuntu userspace, the pinned kernel/initrd, build headers/toolchain, Python and libpcap runtime. It explicitly contains no project source, module/tools, smoke services or candidate SHA. Restores verify architecture, fingerprint, Ubuntu release/snapshot, all SHA-256 sums and `qemu-img check`, and reject a manifest containing `SOURCE_SHA`.

Each exact candidate is injected only into a disposable derived image by `tests/lab/prepare-candidate-image.sh`. That script archives exact `HEAD`, builds the module and userspace against the foundation's pinned guest headers, records the candidate SHA, and installs the test entry points without running `apt`. The reference image is also disposable and receives only the current harness/runtime helper; Route20/PyDECnet payloads remain independently pinned.

The VM workflow places Python-lab runtime below a short `/tmp/dniv-*` path. This removes the Linux UNIX-domain socket pathname failure seen when QMP sockets were under the long Actions scratch path. Serial/pcap evidence is copied back to `scratch/runtime/`; qcow2 and QMP files are deleted and excluded from uploaded evidence.

Exact-head candidate `0ea6d28f4f77ca156a2dbc04bffec83034fd2723` proved the final persistence boundary. Repository policy and native amd64/arm64 builds passed. Both `outer-v2` foundations were built/saved once and later restored by interoperability jobs, and exact-candidate/reference image preparation completed without guest package installation. amd64 guests booted to systemd and reached live DECnet adjacency, so normal work is no longer blocked on image provisioning.

Three bounded execution defects were identified from that evidence and are being corrected together: `dniv-smoke.sh` must accept the deliberately aligned whitespace in `dnctl stats`; the QEMU vvfat reference bundle appears as `/dev/vdb1` and the reference guest must mount that partition when present; and ARM64 QEMU `virt` direct boot is raised to 1 GiB with explicit GIC selection and PL011 early console. None of these changes modifies `build-foundation.sh`, so the existing amd64/arm64 `outer-v2` cache keys remain valid and should be reused on the next acceptance run.

Repository branch policy remains exactly one remote branch, `refs/heads/main`. Repository-policy/control jobs do not consume protocol-lab concurrency slots. GitHub-owned actions, including cache restore/save, remain pinned to immutable full SHAs.

The older `outer-v1-<arch>-<source-sha>` cache layout is obsolete because it rebuilt the expensive foundation for every source commit. `outer-v2` is the final persistence boundary; do not reopen that design without concrete evidence that the foundation cache itself is invalid.

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
| Infrastructure status | closed; only bounded acceptance corrections remain |

## Persistent run index

Run IDs remain lineage, not execution state. Persistent execution input is limited to the verified source-independent architecture foundation cache. Mutable workflow state remains below ignored `scratch/runtime/`; compact evidence may be uploaded, but it never substitutes for exact source/tree verification or becomes writable guest state for a later run.

Acceptance lineage that established the current checkpoint: repository-policy/dispatcher `35246804540`; native build `35246841277` green on amd64 and arm64; Python VM lab `35246849288` reached live amd64 DECnet adjacency and exposed the aligned-stats parser issue while ARM64 produced no serial output under the 512 MiB implicit-GIC configuration; interoperability `35246852105` restored the same foundations and exposed the vvfat `/dev/vdb1` partition behavior on amd64.

## Next action

Commit the three bounded corrections as one exact state and run one acceptance lineage using the existing `outer-v2` caches. Once execution reaches the next substantive DECnet failure, resume Phase 3 protocol/interoperability work from that failure and stop spending project time on infrastructure unless evidence directly implicates the persistent foundation mechanism.
