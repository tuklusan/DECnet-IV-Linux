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

Workflow jobs bind exact source commit/tree, expected parent candidate SHA where applicable, run lineage, runner identity, architecture/mode and retained evidence. Routine workflow integrity checks use one bounded parent-to-candidate baseline diff manifest and one matching final manifest. A byte-complete tracked-tree machine scan remains explicit through `tools/integrity_scan.py --full-tree`.

Hosted-runner policy is unchanged: at most 75 minutes per job, `queue: max`, `cancel-in-progress: false`, compact evidence at most 30 days, VM checkpoints 3 days with paginated stale-checkpoint pruning, and fresh interoperability VMs.

Acceptance parent `35232209976` targeted exact candidate `3f41bec910b5b07520c23b05dcbb1996d091ef62`. Native build child `35232466634` completed green on x86_64 and aarch64. Project-state child `35232469698` completed green. The parent repository-policy and dispatcher jobs were green and the branch-cleanup job correctly skipped.

E1 child `35232475152` failed before Phase 3 protocol acceptance. On arm64 the image path reached final RAW/QCOW2 validation and detected a logical-content mismatch. On amd64 both guests booted to `multi-user.target`, but the just-created smoke-service dependency was absent from the boot transaction and no acceptance markers appeared. The evidence is consistent with late ext4 backing-file metadata writes racing image conversion rather than a DECnet protocol result.

Interop child `35232477599` also failed before independent-peer protocol assertions on both architectures while preparing the mutated reference image after its package installation. Base/candidate preparation could complete first; the reference mutation then failed in its final image-integrity sequence. The correction therefore applies to every RAW filesystem mutation path instead of weakening the logical image comparison.

The current correction makes base ext4 creation eager with `lazy_itable_init=0,lazy_journal_init=0`. After the final unmount, the base builder, interoperability-candidate builder and reference-image builder all synchronize the backing file and run `e2fsck -fy`. Exit statuses 0 and 1 are accepted; higher statuses fail the build. Only then may RAW-to-QCOW2 conversion, `qemu-img check`, and logical `qemu-img compare` proceed. The image-builder policy regression requires these safeguards.

All results belonging to `3f41bec910b5b07520c23b05dcbb1996d091ef62` become historical when this correction lands. A fresh exact-head acceptance lineage is mandatory.

Repository branch policy remains exactly one remote branch, `refs/heads/main`. GitHub-owned actions remain pinned to immutable full SHAs. The machine helpers are `tools/workflow_guard.sh` and `tools/integrity_scan.py`; workflow evidence is stored below `integrity/`.

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
| Previous acceptance parent | `35232209976` on `3f41bec910b5b07520c23b05dcbb1996d091ef62` |
| Previous native build run | `35232466634`, success |
| Previous project-state run | `35232469698`, success |
| Previous E1 VM run | `35232475152`, image-path failure before protocol acceptance |
| Previous interoperability run | `35232477599`, image-preparation failure before protocol assertions |
| Phase 3 acceptance | fresh exact-head lineage required after current correction |

## Persistent run index

Mutable workflow state remains below ignored `scratch/runtime/`; restored evidence remains below ignored `scratch/restored/`. A run ID is lineage, not persistent execution. Only explicitly uploaded and subsequently verified files persist across hosted runners. Runtime evidence belongs only to its exact candidate and never transfers acceptance status to a later commit.

## Next action

Commit the ext4 image-stability correction directly to `main`, then dispatch fresh exact-head native x86_64/aarch64 build, project-state/continuity, pinned reference, E1 and bounded Route20/PyDECnet interoperability gates. Phase 4 starts only after that unchanged candidate is green.
