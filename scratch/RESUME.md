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

Phase 3 remains the active protocol phase. Work is performed only on `main`. The repository-root `scratch/` persistence contract, exact-tree SoP scan tooling, and workflow state/evidence persistence are active. Mutable workflow state is written below ignored `scratch/runtime/` during a run and restored below ignored `scratch/restored/` on later runner sessions.

Hosted-runner lifetime and storage policy is now explicit and machine-enforced. Every workflow job declares a timeout no greater than 75 minutes; shorter jobs use smaller caps. `tools/workflow_budget_gate.py`, invoked by every workflow SoP entry, rejects missing/over-limit job timeouts and artifact retention above 30 days. A run or session ID records lineage only: hosted runner RAM, processes and live VM state do not survive job termination.

Two-node VM persistence is explicit disk checkpointing. Compact logs, scan manifests and packet evidence are retained for 30 days. The resumable QCOW2 checkpoint is uploaded separately for 3 days, and after a successful replacement upload the workflow deletes older checkpoint artifacts for that architecture. Failed-run artifacts age out by retention policy. Interoperability evidence excludes transient QCOW2 overlays because that workflow always starts fresh independent peers; its `resume_run_id` restores prior evidence for lineage, not a live or disk-resumed VM.

The latest review also corrected `tools/project_state_gate.py` so staged checks validate the staged index copies of `docs/PROJECT_STATE.md` and this file, while committed checks validate the requested commit objects. Different working-tree contents can no longer mask invalid continuity records. These workflow/policy corrections are substantive, so all earlier SoP pass counts and acceptance evidence are invalid for the resulting `main` candidate.

| Field | Current value |
| --- | --- |
| Protocol phase | Phase 3 |
| Working ref | `main` only |
| Hosted job voluntary ceiling | 75 minutes |
| Compact workflow evidence retention | 30 days |
| Resumable VM checkpoint retention | 3 days, rolling newest successful per architecture |
| SoP clean semantic/manual passes on this candidate | 0 |
| Byte-complete workflow scan requirement | 3 matching scans plus final post-gate scan |
| Phase 3 acceptance | not yet dispatched for this candidate |
| Latest acceptance parent run | none yet |
| Latest resumable VM run | none yet |
| Latest interoperability run | none yet |

## Persistent run index

Every workflow records a `state.json` containing source commit/tree, workflow/job, run ID, run attempt, runner identity, architecture/mode, parent/resume run IDs, milestones and status. The surrounding compact scratch artifact retains scan manifests, logs and applicable packet evidence. The two-node VM workflow additionally retains a short-lived sealed format-2 checkpoint artifact containing the base disk, both node deltas, kernel, initrd, `session.env` and hashes.

The tracked table above is the durable human index. It is updated with `docs/PROJECT_STATE.md` in every substantive commit. Runtime artifacts are evidence attached to an exact commit; they never make a changed commit inherit prior SoP or acceptance status. A session ID alone never proves persistence: resume is valid only after the matching artifact has been restored and verified.

## Next action

Restart the complete semantic/manual SoP review on the exact resulting `main` commit. Require three consecutive clean full-repository passes, with workflow byte-scan manifests agreeing on that same commit/tree and the workflow budget gate green. Then execute exact-head repository policy/continuity, native x86_64/aarch64 build, pinned reference baselines, E1 self-to-self, and live Route20/PyDECnet interoperability gates. Preserve compact evidence automatically and retain only the rolling resumable VM checkpoints defined above. Phase 4 starts only after the unchanged Phase 3 candidate is green.
