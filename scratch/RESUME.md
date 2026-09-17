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

Phase 3 remains the active protocol phase. Work is performed only on `main`. The repository-root `scratch/` persistence contract, exact-tree SoP scan tooling, and workflow state/evidence persistence are active. Mutable workflow state is written below ignored `scratch/runtime/` during a run, uploaded as uniquely named workflow artifacts, and restored below ignored `scratch/restored/` on later runner sessions.

The latest review found that image construction copied the mutable workflow checkout after `scratch/runtime/` had been created. The image builder now archives the exact tracked `HEAD` commit with `git archive`, records that source commit inside the guest tree, and installs the guest test harness from the archived copy. Transient runner state therefore cannot contaminate candidate images. This fix is substantive, so all earlier SoP pass counts and acceptance evidence are invalid for the resulting `main` candidate.

| Field | Current value |
| --- | --- |
| Protocol phase | Phase 3 |
| Working ref | `main` only |
| SoP clean semantic/manual passes on this candidate | 0 |
| Byte-complete workflow scan requirement | 3 matching scans plus final post-gate scan |
| Phase 3 acceptance | not yet dispatched for this candidate |
| Latest acceptance parent run | none yet |
| Latest resumable VM run | none yet |
| Latest interoperability run | none yet |

## Persistent run index

Every workflow records a `state.json` containing source commit/tree, workflow/job, run ID, run attempt, runner identity, architecture/mode, parent/resume run IDs, milestones and status. The surrounding scratch artifact retains scan manifests, logs and applicable VM/packet evidence. Artifact names include workflow purpose, architecture where applicable and run ID so a later session can restore the exact prior state into `scratch/restored/`.

The tracked table above is the durable human index. It is updated with `docs/PROJECT_STATE.md` in every substantive commit. Runtime artifacts are evidence attached to an exact commit; they never make a changed commit inherit prior SoP or acceptance status.

## Next action

Restart the complete semantic/manual SoP review on the exact resulting `main` commit. Require three consecutive clean full-repository passes, with workflow byte-scan manifests agreeing on that same commit/tree. Then execute exact-head repository policy/continuity, native x86_64/aarch64 build, pinned reference baselines, E1 self-to-self, and live Route20/PyDECnet interoperability gates. Retain every workflow state directory and evidence bundle through `scratch/` artifacts. Phase 4 starts only after the unchanged Phase 3 candidate is green.
