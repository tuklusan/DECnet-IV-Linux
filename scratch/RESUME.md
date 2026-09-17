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

Phase 3 remains the active protocol phase. Work is performed only on `main`. The repository-root `scratch/` persistence contract, exact-tree SoP scan tooling, workflow state/evidence persistence, runner budgets and main-only repository policy are active. Mutable workflow state is written below ignored `scratch/runtime/` during a run and restored below ignored `scratch/restored/` on later runner sessions.

Hosted-runner lifetime and storage policy is machine-enforced. Every workflow job declares a timeout no greater than 75 minutes. Every workflow/job concurrency block uses `queue: max`, so the shared x64/arm64 runner slots retain up to GitHub's queue limit instead of replacing an older pending gate. Compact logs, scan manifests and packet evidence are retained for at most 30 days. Two-node resumable QCOW2 checkpoints are kept separately for 3 days and older successful checkpoints for the same architecture are pruned after a replacement uploads successfully. The pruning step paginates the full artifact listing before selecting stale same-architecture checkpoints. Interoperability evidence excludes transient QCOW2 overlays because those peers always start fresh.

Acceptance fan-out is bound to one immutable candidate. The owner acceptance dispatcher passes both its run ID and exact `GITHUB_SHA` to every child. `tools/scratch_state.py` rejects a child with a parent run ID unless an expected SHA is also supplied, resolves that SHA to a commit, and refuses initialization unless it equals the child's actual source commit. `state.json` retains both the source and expected SHA for later audit. If `main` moves during dispatch or before a queued child starts, the child fails instead of silently testing a different candidate.

Candidate `a122e8e82541a9499b9b514568b70e77de97ca4b` completed three consecutive clean semantic/manual SoP passes and exact-head acceptance parent `35184898090` dispatched children bound to that SHA. Repository/continuity, x86_64 and arm64 native builds, and pinned reference baselines were green. E1 child run `35184925391` then failed on both architectures before any DECnet protocol assertion. The amd64 guests reached userspace, but systemd parsed `/etc/systemd/system/dniv-smoke.service` as repeated assignments outside a section and refused it because no `ExecStart` was visible; rerunning the job reproduced the same failure. The tracked source remained the expected 1023-byte unit, so this exposed an image-integrity acceptance gap. The arm64 guests produced zero serial bytes for the full 300-second gate. Ubuntu arm64 packages provide gzip-compressed `vmlinuz` images while AArch64 direct boot requires a decompressed Image, explaining the direct-boot failure mode. No result from that acceptance attempt is promotable.

The image builder correction verifies archived smoke script/unit bytes against their installed guest copies, validates the installed unit with `systemd-analyze`, builds acceptance QCOW2 without compression, checks QCOW2 structure, round-trips the finished image back to raw and rechecks the critical guest hashes. On arm64 it decompresses a gzip-packaged `vmlinuz` before direct boot and requires the mandatory AArch64 Image magic; amd64 keeps its packaged direct-boot image. `tests/policy/test_image_builder_gate.py` requires all of those safeguards from staged and committed sources. This change invalidates the preceding three SoP passes and all acceptance evidence, so the new candidate starts at zero semantic/manual passes.

Repository branch policy is active and the remote invariant is satisfied. Project work must be on local `main`; pre-push rejects creation/update of any non-main branch and rejects deletion of `main`, while permitting cleanup deletion of obsolete non-main refs. Acceptance policy inspects remote heads and requires `refs/heads/main` to be the only branch. Cleanup run `35179252422` removed the legacy refs, verified only `main` remained, ran the exact-main workflow SoP machinery, and completed successfully. A future non-main branch creation event enters the same cleanup path automatically.

The first cleanup canary, run `35179022863`, failed before deleting any ref because the workflow attempted to write `maintenance.env` before creating its scratch directory. The corrected run `35179252422` passed after that initialization-order fix. Both runs are diagnostic history; later corrections reset semantic SoP.

GitHub-owned workflow actions are pinned to immutable full commit SHAs: checkout v4.4.0 `11d5960a326750d5838078e36cf38b85af677262`, upload-artifact v4.6.2 `ea165f8d65b6e75b540449e92b4886f43607fa02`, and download-artifact v4.3.0 `d3f86a106a0bac45b974a628896c90dbdf5c8093`. `tools/workflow_budget_gate.py` enforces these pins together with `queue: max`, the 75-minute ceiling, retention limits, expected-SHA inputs, complete paginated VM-checkpoint pruning and the maximum-two-scenario interoperability rows. Regression gates cover exact staged/committed workflow sources, queueing, action pins, storage safeguards, scenario bounds and branch-update policy. `tests/policy/test_image_builder_gate.py` additionally enforces explicit initramfs generation, installed guest-byte validation, arm64 direct-boot decompression/header validation and post-QCOW2 critical-file integrity using exact staged/committed source selection.

A run/session ID records lineage only. Hosted runner RAM, processes and live QEMU state do not survive job termination. Persistence exists only for explicitly uploaded and subsequently verified files. Two-node resume additionally requires the sealed format-2 checkpoint hashes, matching architecture, exact source revision and mode.

| Field | Current value |
| --- | --- |
| Protocol phase | Phase 3 |
| Working ref | `main` only |
| Remote branch invariant | satisfied: only `refs/heads/main` |
| Hosted job voluntary ceiling | 75 minutes |
| Runner queue policy | `queue: max` on every concurrency block |
| Interoperability scenarios per hosted job | maximum 2 |
| Compact workflow evidence retention | 30 days |
| Resumable VM checkpoint retention | 3 days, rolling newest successful per architecture, paginated pruning |
| Acceptance child binding | parent run ID + exact expected SHA |
| SoP clean semantic/manual passes on this candidate | 0 |
| Byte-complete workflow scan requirement | 3 matching scans plus final post-gate scan |
| Phase 3 acceptance | prior exact candidate failed E1 image/direct-boot gates; fresh acceptance required after correction |
| Latest acceptance parent run | `35184898090`, failed by E1 child |
| Latest branch-cleanup run | `35179252422`, success |
| Latest resumable VM run | `35184925391`, amd64 and arm64 E1 failed before protocol assertions |
| Latest interoperability run | prior-candidate evidence; ineligible after image correction |

## Persistent run index

Every workflow records a `state.json` containing source commit/tree, expected candidate SHA where applicable, workflow/job, run ID, run attempt, runner identity, architecture/mode, parent/resume run IDs, milestones and status. Compact scratch artifacts retain scan manifests, logs, packet evidence and small checkpoint metadata. The two-node VM workflow separately retains a short-lived sealed format-2 checkpoint containing the base disk, both node deltas, kernel, initrd, `session.env` and hashes.

The tracked table above is the durable human index. It is updated with `docs/PROJECT_STATE.md` in every substantive commit. Runtime artifacts are evidence attached to an exact commit; they never make a changed commit inherit prior SoP or acceptance status.

## Next action

Restart the complete semantic/manual SoP review on this exact new `main` candidate and require three consecutive clean full-repository passes. The workflow byte-scan manifests, image-builder regression, branch-policy regression, continuity regression and workflow-budget/action-pin/storage gate must agree on that same commit/tree. Then execute a fresh exact-head repository policy/continuity, native x86_64/aarch64 build, pinned reference baselines, E1 self-to-self, and bounded live Route20/PyDECnet interoperability suites. Only after that unchanged Phase 3 candidate is green may Phase 4 kernel routing work begin.
