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

Phase 3 remains active and all substantive work stays on `main`. Routine SoP has been narrowed from complete-repository rereads to the exact first-parent-to-candidate unified diff with three lines of context. Automatic three-pass full-tree scanning is disabled. `tools/sop_scan.py` now defaults to the bounded diff and `--full-tree` is explicit opt-in only.

The semantic/manual delivery rule still requires three consecutive clean passes, but those passes review the same bounded candidate diff plus only directly necessary local/dependency context. A fix creates a new candidate, recomputes the diff and resets the scoped pass count.

Workflow jobs still bind exact source commit/tree, expected parent candidate SHA where applicable, run lineage, runner identity, architecture/mode and retained evidence. `tools/workflow_sop.sh` runs the ordinary policy/regression checks and records one bounded baseline diff manifest. Each workflow's existing final scan compares against that same bounded manifest and therefore detects candidate/checkout drift without repeatedly rereading every tracked repository blob.

Hosted-runner policy is unchanged: at most 75 minutes per job, `queue: max`, `cancel-in-progress: false`, compact evidence at most 30 days, VM checkpoints 3 days with paginated stale-checkpoint pruning, and fresh interoperability VMs.

Exact-head acceptance parent `35184898090` on candidate `a122e8e82541a9499b9b514568b70e77de97ca4b` reached green repository/continuity, native build and pinned reference gates, but E1 child `35184925391` failed before DECnet protocol assertions. amd64 exposed a bad installed smoke-service image and arm64 did not boot to serial output because the packaged kernel image required direct-boot handling. Commit `d3416e1ad9d2a5e057c6c49e9407cec92683dc86` hardened the base-image path with smoke byte/unit checks, uncompressed acceptance QCOW2, post-conversion verification and arm64 kernel decompression/header validation.

A later focused review identified one remaining image-integrity gap: both derived interoperability builders still use compressed RAW-to-QCOW2 conversion and lack post-conversion guest-content proof. That correction remains the next code change.

Repository branch policy remains active with only `refs/heads/main`. Cleanup run `35179252422` is the last successful branch-cleanup run. GitHub-owned actions remain pinned to immutable full SHAs.

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
| Routine semantic/manual SoP scope | exact first-parent-to-candidate diff, three context lines |
| Clean scoped semantic/manual passes on this candidate | 0 |
| Routine workflow scan requirement | one bounded baseline diff manifest plus matching final diff manifest |
| Explicit full-tree scan | opt-in only via `tools/sop_scan.py --full-tree` |
| Phase 3 acceptance | prior candidate failed E1 image/direct-boot gates; fresh acceptance required after corrections |
| Latest acceptance parent | `35184898090` |
| Latest E1 VM run | `35184925391` |
| Latest branch-cleanup run | `35179252422`, success |

## Persistent run index

Mutable workflow state remains below ignored `scratch/runtime/`; restored evidence remains below ignored `scratch/restored/`. A run ID is lineage, not persistent execution. Only explicitly uploaded and subsequently verified files persist across hosted runners.

The tracked table above is the durable human index. Runtime evidence belongs only to its exact candidate and never transfers acceptance status to a later commit.

## Next action

Fix `tests/lab/prepare-interop-candidate.sh` and `tests/lab/prepare-reference-image.sh` so their derived QCOW2 images receive fail-fast structural/content verification equivalent to the base-image path, add the smallest regression needed to prevent recurrence, and update this file plus `docs/PROJECT_STATE.md` in that same commit. Perform the three semantic/manual passes only on that resulting bounded diff. Then run fresh exact-head Phase 3 acceptance gates. Phase 4 starts only after the unchanged Phase 3 candidate is green.
