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

Reference discipline is now explicit at repository root in `references/`: Digital DNA Phase IV functional specifications are normative, pinned PyDECnet/Route20 are implementation cross-checks, pinned LinuxDECnet defines Linux-facing compatibility expectations, and pinned SIMH plus genuine DEC operating systems provide interoperability evidence. The reference directory contains project-authored distilled notes and pointers rather than unverified wholesale copies of third-party manuals.

The two-node lab uses `tests/lab/dniv_lab.py`, a Python direct-QEMU controller with QMP shutdown, Linux bridge/TAP networking, packet capture, serial marker assertions and disposable qcow2 node overlays. Writable inner-VM checkpoints remain retired. Runtime/evidence lives below short `/tmp/dniv-*` paths and compact evidence is copied back to `scratch/runtime/`.

The two architecture slots retain immutable source-independent foundations. Their session identifier is `outer-v2-<arch>-<foundation-fingerprint>`, derived from `image/ubuntu-base/images.env` and `build-foundation.sh`, never from the candidate SHA. A foundation contains Ubuntu userspace, the pinned kernel/initrd, build headers/toolchain, Python, libpcap and independent-reference runtime dependencies. `git` is included because pinned PyDECnet queries its Git revision at startup. No project source, module/tools, smoke service or candidate SHA is persistent.

Each exact candidate is injected only into a disposable derived image by `tests/lab/prepare-candidate-image.sh`; the reference image is likewise disposable and Route20/PyDECnet remain independently pinned. The persistence architecture is closed and is not to be reopened without concrete evidence that the foundation mechanism itself is defective.

Exact-head candidate `5f4fdc5b3d1bcef87e56ac64b8c3b287f504eddb` established that the persistence mechanism works: repository policy, project state and both native builds passed; amd64 Python E1 passed from a restored foundation; ARM64 reached QEMU but produced no serial output. The same lineage exposed the Route20 `/run` execute restriction and PyDECnet's missing `git` runtime prerequisite. Both were corrected without modifying either reference implementation.

Exact-head candidate `317deebe5a916ca28e576074fab7e310b15b5d37` passed repository policy, project state, native builds and reference baselines. Its ARM64 VM foundation rebuild failed on `/boot/vmlinuz-7.0.0-31-generic` with `unsupported arm64 kernel format; refusing non-Image fallback`, proving the remaining ARM fault was wrapper normalization rather than DECnet. On amd64, the Route20 L1 interop job proved the candidate received and parsed a valid INIT from Route20 node 31.71, but the Route20 daemon exited about 3.5 seconds after its READY marker and before a stable adjacency formed.

ARM64 direct boot normalization now accepts only a bounded chain of recognized formats: raw Linux Image, whole-file gzip/Zstd, EFI-zboot gzip/Zstd, or a structurally valid PE/COFF wrapper containing exactly one bounded `.linux` section. Every path ends by requiring the raw `ARM\x64` Linux Image magic at offset 56. Unknown/malformed formats fail closed. Both image builders are bound to the helper's exact SHA-256, so this change intentionally generates a new foundation fingerprint and one new foundation build per architecture.

The Route20 launcher still runs the exact pinned binary from `/usr/local/libexec`, but now emits the Route20 syslog tail and matching kernel crash lines if the daemon dies. The retained amd64 L1 evidence from run `35262772964`, job `105342341317`, identifies the failure as a Route20 userspace crash after circuit startup: `segfault at 0 ip 0000000000000000 ... error 14`. This is reference-runtime evidence; candidate DECnet behavior must not be changed to mask it.

Exact-head candidate `a04d2a4ec8687f21fafce1950d339b983f15c973` proved ARM64 direct boot is now functional. VM run `35262769735` normalized the real Ubuntu kernel through `pe-linux+efi-zboot:zstd+raw`, built and cached the foundation, injected the exact candidate, formed router adjacency and survived the primary-MAC change. The amd64 E1 job passed. ARM64 stopped only because the harness sampled total routing and hello counters in separate commands, allowing a concurrent hello to create a false `bad-stats`; DN70 therefore exited before transmitting the 40 unicast probes and DN71 subsequently reported zero receive delta.

Exact-head candidate `38c5b49e53c648f6514f52ebff84a93331a4732a` closed that sampling defect. Repository-policy/dispatcher run `35265712742`, the new host regression and ARM64 native build were green. VM run `35265759834` reached `DNIV-E1-UCAST ... delta=40` on both nodes, then DN71 entered the prescribed silent interval and DN70 emitted `DNIV-E1-EXPIRED`. The controller's 300-second deadline fired before recovery only because DN71's intended restart began at guest uptime about 302 seconds. No protocol failure marker occurred before host termination.

The VM controller budget is therefore architecture-specific: amd64 stays at 300 seconds and ARM64 receives 360 seconds. The latter covers the observed ~302-second restart point plus the already-bounded 30-second adjacency recovery wait, five-second post-recovery observation and shutdown margin. The surrounding job remains limited to 40 minutes; kernel and protocol timing are unchanged.

Acceptance run `35266940092` on `31fc8e00d1c46ffd5cc74c6663c287753a0b7e5d` proved the ARM64 guests themselves are green: both delivered unicast `delta=40`, DN70 expired DN71, restart INIT and recovery occurred, and both emitted `DNIV-E1-PASS`; amd64 E1 passed. ARM64 failed only because host PCAP saw one DN70 All-End-Nodes hello. The test intended DN71 silence to exceed listener expiry but remain below DR eligibility; with hello interval 2s, 3.1x listen expiry is 6.2s and the 5s DR delay makes eligibility 11.2s, so the old 12s silence violated the test's own negative assertion.

The silence window is corrected to 7s and a workflow-guard regression reads the actual hello interval, 3.1x multiplier and DR-delay constant and enforces `expiry < silence < DR eligibility`. The old 12s value fails this regression. Acceptance parent `35285482332` ran the updated license scanner successfully and reached this regression; it failed only because the first regression version required one router interval occurrence even though the smoke script has two valid, equal `hello_interval=2` load sites. The regression now accepts repeated equal values and rejects disagreement.

Exact-head `e7ee147f40bcea7525f9a25499fa9f59974cb9b6` proved the E1 correction: parent/dispatcher, both native builds, project state, pinned PyDECnet/Route20 baselines and both VM E1 architectures were green; ARM64 captured 442 DECnet frames. In interop run `35285622023`, ARM64 Route20 routing failed before Route20 execution because the reference VM hit the hardcoded 90-second READY deadline while still completing normal boot, with rootfs handoff around guest uptime 80 seconds. This is an ARM interop harness readiness defect, not candidate DECnet evidence.

Exact-head run `35286846863` exposed that readiness was still coupled to guest boot: the reference service could start while systemd was converging on `multi-user.target`. The reference image now orders the peer after `multi-user.target` and inserts an explicit 60-second idle settle interval before peer startup. `DNIV-REF-READY` is consequently post-boot and post-settle. Host bounds are 180s amd64 and 360s ARM64 for both initial and restart boots, and the workflow guard checks the bounds, both READY waits, the settle-service wiring, and that the reference-image builder remains executable. Exact-head interop run `35288608187` proved this extra guard was needed: both architectures stopped at `prepare-reference-image.sh: Permission denied` because the settle commit had accidentally changed its mode to non-executable.

Repository license validation now excludes `__pycache__` and `.git` directories in the Git enumeration command itself for both exact-tree and staged scans, at any depth, so generated caches and repository metadata never reach the validator.

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
| VM controller budget | amd64 300s; ARM64 360s |
| Infrastructure status | architecture/direct boot/stats sampling/controller budget/E1 closed; ARM64 interop reference-ready bound awaiting exact acceptance |

## Persistent run index

Run IDs are lineage, not execution state. Persistent execution input is limited to the verified source-independent architecture foundation cache. Mutable workflow state remains below ignored `scratch/runtime/`; compact evidence never substitutes for exact source/tree verification.

Acceptance lineage for `5f4fdc5b3d1bcef87e56ac64b8c3b287f504eddb`: repository-policy/dispatcher `35256346698`; native build `35256391400` green on amd64 and arm64; project-state `35256393889` green; Python VM `35256398678` with amd64 green and ARM64 zero-serial direct-boot failure; interoperability `35256400954` exposed the Route20 `/run` and PyDECnet `git` runtime blockers.

Acceptance lineage for `317deebe5a916ca28e576074fab7e310b15b5d37`: repository policy, project state, native build and reference baselines were green; VM lab run `35259650843` failed while normalizing the ARM64 foundation kernel; interop run `35259653065` produced the amd64 Route20 L1 `reference-exited` evidence while ARM64 modes remained blocked at foundation construction.

Acceptance lineage for `a04d2a4ec8687f21fafce1950d339b983f15c973`: repository-policy/dispatcher `35262720736`, native build `35262761176` and project-state `35262763814` were green. VM lab `35262769735` passed amd64 E1 and proved ARM64 foundation/direct boot, adjacency and MAC-change operation before the counter-sampling race produced `bad-stats` on DN70 and the consequent zero unicast delta on DN71. Interop run `35262772964`, amd64 Route20 L1 job `105342341317`, later captured a null-IP Route20 userspace segfault after circuit startup.

Acceptance lineage for `38c5b49e53c648f6514f52ebff84a93331a4732a`: repository-policy/dispatcher `35265712742` was green and ARM64 native build in `35265752902` passed. VM lab `35265759834` proved the sampling fix with bidirectional unicast `delta=40`, DN71 silence and DN70 expiry; its ARM64 job failed only because the 300-second host controller deadline preceded the planned DN71 restart/recovery completion.

## Next action

Run exact-head acceptance for current `main`. Require the new interop-readiness regression and the already-proven two-architecture E1 gates. Reference startup is post-boot/post-settle: 180 seconds on amd64 and 360 seconds on ARM64, including the required 60-second idle interval after `multi-user.target`. If Route20 then exits after READY, diagnose the pinned reference runtime independently and alter candidate protocol code only for separately demonstrated defects.
