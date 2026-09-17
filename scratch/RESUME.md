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

Phase 3 remains active and all substantive work stays on `main`. Candidate promotion is controlled by exact-SHA mechanical and protocol acceptance gates. There is no manual delivery-pass counter, no multi-pass review prerequisite, and no review state to carry forward.

Workflow jobs bind exact source commit/tree, expected parent candidate SHA where applicable, run lineage, runner identity, architecture/mode and retained evidence. Routine workflow integrity checks use one bounded parent-to-candidate baseline diff manifest and one matching final manifest. A byte-complete tracked-tree machine scan remains explicit through `tools/integrity_scan.py --full-tree`.

Hosted-runner policy is unchanged: at most 75 minutes per job, `queue: max`, `cancel-in-progress: false`, compact evidence at most 30 days, VM checkpoints 3 days with paginated stale-checkpoint pruning, and fresh interoperability VMs.

Previous exact-head acceptance on `b47b11dd513c4bcb4acb66594c1d96aa6c071a4a` produced green native build `35225302832` and project-state `35225305452`. E1 run `35225310434` failed on arm64 before protocol assertions because the image validator rejected a kernel that QEMU's AArch64 loader would accept through its raw fallback. That validator defect is corrected on current `main`.

The current image builder keeps outer-gzip handling, recognizes and structurally validates exact EFI-zboot headers, accepts raw AArch64 Image metadata when present, and preserves other nonempty kernel artifacts for QEMU raw loading. VM boot remains the executable proof. RAW/QCOW2 logical-content integrity uses `qemu-img compare`.

The current Phase 3 protocol candidate includes per-interface designated-router candidacy timing. A fresh DRDELAY begins when the local router first becomes the best candidate, pending promotion is cancelled while a better router is known, and interface-down or identity changes reset the timer. E1 verifies the handoff timing at the wire level.

Repository branch policy is active and the live remote branch invariant is only `refs/heads/main`. GitHub-owned actions remain pinned to immutable full SHAs. The machine helpers are `tools/workflow_guard.sh` and `tools/integrity_scan.py`; workflow evidence is stored below `integrity/`.

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
| Phase 3 acceptance | corrected current candidate requires fresh exact-SHA gates |
| Latest E1 VM run | `35225310434`, arm64 validator failure on prior candidate before protocol assertions |
| Latest native build run | `35225302832`, success on prior candidate |
| Latest project-state run | `35225305452`, success on prior candidate |

## Persistent run index

Mutable workflow state remains below ignored `scratch/runtime/`; restored evidence remains below ignored `scratch/restored/`. A run ID is lineage, not persistent execution. Only explicitly uploaded and subsequently verified files persist across hosted runners. Runtime evidence belongs only to its exact candidate and never transfers acceptance status to a later commit.

## Next action

Dispatch fresh exact-head native x86_64/aarch64 build, project-state/continuity, pinned reference, E1, Route20 and PyDECnet interoperability gates on the exact current `main` candidate. Phase 4 starts only after that unchanged candidate is green.
