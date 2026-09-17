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

Phase 3 remains active and all substantive work stays on `main`. Candidate promotion is controlled only by the documented exact-SHA mechanical, build, VM, reference, protocol and interoperability gates.

Workflow jobs bind exact source commit/tree, expected parent candidate SHA where applicable, run lineage, runner identity, architecture/mode and retained evidence. Routine workflow integrity checks use one bounded parent-to-candidate baseline diff manifest and one matching final manifest. A byte-complete tracked-tree machine scan remains explicit through `tools/integrity_scan.py --full-tree`.

Hosted-runner policy is unchanged: at most 75 minutes per job, `queue: max`, `cancel-in-progress: false`, compact evidence at most 30 days, VM checkpoints 3 days with paginated stale-checkpoint pruning, and fresh interoperability VMs.

Exact-SHA acceptance parent `35228747062` ran on `3582b7ab3b0336f8b28cec6e8c1a68d02514d440`. Native build `35228787667`, project-state `35228789830`, and reference-baseline `35228792392` completed green. E1 `35228794763` failed before protocol acceptance: arm64 emitted no serial output from the direct-boot artifact, while amd64 booted normally but never ran the smoke entry point. Interop `35228796950` also exposed an independent harness defect: Route20 reference startup failed because a read-only vvfat bundle backend was connected to a writable virtio frontend and QEMU rejected it with `Block node is read-only`.

The current correction normalizes an exact validated arm64 EFI-zboot wrapper by expanding its bounded gzip payload to a raw AArch64 Image. Unknown nonempty kernel artifacts still retain QEMU raw fallback semantics, and VM boot remains the executable proof. The image builder now enables `dniv-smoke.service` through systemd's offline enable operation and verifies both enabled state and the `multi-user.target` dependency before image conversion. The interop harness marks the vvfat reference bundle block frontend read-only.

Repository branch policy remains only `refs/heads/main`. GitHub-owned actions remain pinned to immutable full SHAs. The machine helpers are `tools/workflow_guard.sh` and `tools/integrity_scan.py`; workflow evidence is stored below `integrity/`.

| Field | Current value |
| --- | --- |
| Protocol phase | Phase 3 |
| Working ref | `main` only |
| Remote branch invariant | only `refs/heads/main` |
| Hosted job ceiling | 75 minutes |
| Runner queue policy | `queue: max`; no cancellation of pending acceptance work |
| Interoperability scenarios per hosted job | maximum 2 |
| Compact evidence retention | 30 days |
| VM checkpoint retention | 3 days; rolling newest successful per architecture; paginated pruning |
| Acceptance child binding | parent run ID + exact expected SHA |
| Routine workflow integrity requirement | one bounded baseline diff manifest plus matching final diff manifest |
| Explicit machine full-tree scan | `tools/integrity_scan.py --full-tree` |
| Phase 3 acceptance | fresh exact-SHA gates required after current corrections |
| Latest E1 VM run | `35228794763`, failed on prior candidate before protocol acceptance |
| Latest native build run | `35228787667`, success on prior candidate |
| Latest project-state run | `35228789830`, success on prior candidate |
| Latest reference-baseline run | `35228792392`, success on prior candidate |
| Latest interoperability run | `35228796950`, harness/reference-start failures on prior candidate; not promotable |

## Persistent run index

Mutable workflow state remains below ignored `scratch/runtime/`; restored evidence remains below ignored `scratch/restored/`. A run ID is lineage, not persistent execution. Only explicitly uploaded and subsequently verified files persist across hosted runners. Runtime evidence belongs only to its exact candidate and never transfers acceptance status to a later commit.

## Next action

Dispatch fresh exact-head native x86_64/aarch64 build, project-state/continuity, pinned reference, E1, Route20 and PyDECnet interoperability gates on the corrected current `main` candidate. Phase 4 starts only after that unchanged candidate is green.
