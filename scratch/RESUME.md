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

Hosted-runner lifetime and storage policy is machine-enforced. Every workflow job declares a timeout no greater than 75 minutes. Every workflow/job concurrency block uses `queue: max`, so the shared x64/arm64 runner slots retain up to GitHub's queue limit instead of replacing an older pending gate. Compact logs, scan manifests and packet evidence are retained for at most 30 days. Two-node resumable QCOW2 checkpoints are kept separately for 3 days and older successful checkpoints for the same architecture are pruned after a replacement uploads successfully. Interoperability evidence excludes transient QCOW2 overlays because those peers always start fresh.

Acceptance fan-out is bound to one immutable candidate. The owner acceptance dispatcher passes both its run ID and exact `GITHUB_SHA` to every child. `tools/scratch_state.py` rejects a child with a parent run ID unless an expected SHA is also supplied, resolves that SHA to a commit, and refuses initialization unless it equals the child's actual source commit. `state.json` retains both the source and expected SHA for later audit. If `main` moves during dispatch or before a queued child starts, the child fails instead of silently testing a different candidate.

Repository branch policy is now explicit. Project work must be on local `main`; pre-push rejects creation/update of any non-main branch and rejects deletion of `main`, while permitting deletion of obsolete non-main refs. Acceptance policy also inspects the remote heads and requires `refs/heads/main` to be the only branch. An owner-only `DNIV branch cleanup` maintenance issue removes legacy remote heads and then runs the exact-main SoP machinery. Existing legacy refs must be cleaned by that maintenance gate before acceptance can pass.

GitHub-owned workflow actions used by this repository are pinned to immutable full commit SHAs: checkout v4.4.0 `11d5960a326750d5838078e36cf38b85af677262`, upload-artifact v4.6.2 `ea165f8d65b6e75b540449e92b4886f43607fa02`, and download-artifact v4.3.0 `d3f86a106a0bac45b974a628896c90dbdf5c8093`. `tools/workflow_budget_gate.py` enforces these pins together with `queue: max`, the 75-minute ceiling, retention limits, expected-SHA inputs and the maximum-two-scenario interoperability rows. Regression tests cover exact staged/committed workflow sources, queueing, action pins, scenario bounds and branch-update policy.

A run/session ID records lineage only. Hosted runner RAM, processes and live QEMU state do not survive job termination. Persistence exists only for explicitly uploaded and subsequently verified files. Two-node resume additionally requires the sealed format-2 checkpoint hashes, matching architecture, exact source revision and mode.

| Field | Current value |
| --- | --- |
| Protocol phase | Phase 3 |
| Working ref | `main` only |
| Remote branch invariant | only `refs/heads/main`; legacy refs pending cleanup gate |
| Hosted job voluntary ceiling | 75 minutes |
| Runner queue policy | `queue: max` on every concurrency block |
| Interoperability scenarios per hosted job | maximum 2 |
| Compact workflow evidence retention | 30 days |
| Resumable VM checkpoint retention | 3 days, rolling newest successful per architecture |
| Acceptance child binding | parent run ID + exact expected SHA |
| SoP clean semantic/manual passes on this candidate | 0 |
| Byte-complete workflow scan requirement | 3 matching scans plus final post-gate scan |
| Phase 3 acceptance | not yet dispatched for this candidate |
| Latest acceptance parent run | none yet |
| Latest resumable VM run | none yet |
| Latest interoperability run | none yet |

## Persistent run index

Every workflow records a `state.json` containing source commit/tree, expected candidate SHA where applicable, workflow/job, run ID, run attempt, runner identity, architecture/mode, parent/resume run IDs, milestones and status. Compact scratch artifacts retain scan manifests, logs, packet evidence and small checkpoint metadata. The two-node VM workflow separately retains a short-lived sealed format-2 checkpoint containing the base disk, both node deltas, kernel, initrd, `session.env` and hashes.

The tracked table above is the durable human index. It is updated with `docs/PROJECT_STATE.md` in every substantive commit. Runtime artifacts are evidence attached to an exact commit; they never make a changed commit inherit prior SoP or acceptance status.

## Next action

Commit this infrastructure correction atomically on `main`, trigger the owner-only branch cleanup gate, and verify the remote contains only `main`. That change resets SoP. Restart the complete semantic/manual SoP review on the exact cleaned `main` candidate and require three consecutive clean full-repository passes. Then execute exact-head repository policy/continuity, native x86_64/aarch64 build, pinned reference baselines, E1 self-to-self, and the bounded live Route20/PyDECnet interoperability suites. Only after that unchanged Phase 3 candidate is green may Phase 4 kernel routing work begin.
