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

# Scratch workspace

`scratch/` is the repository-root persistence workspace for workflow state. The directory itself, this contract, and `RESUME.md` are tracked. Mutable runner state is deliberately not committed because acceptance is tied to one exact source commit.

Every workflow creates a unique directory under `scratch/runtime/<run-id>/<run-attempt>/<job>/`. It records `state.json`, exact source commit/tree identity, workflow/run/job/runner identifiers, parent or resumed run identifiers, status milestones, and workflow integrity manifests. VM and interoperability workflows place packet captures, serial logs, hashes, and other evidence below the same run directory.

A hosted run/session ID records lineage only. Hosted RAM, processes and live VM state do not survive job termination. Persistent workflow inputs exist only when explicitly stored through an approved artifact/cache mechanism and subsequently restored and verified; the only reusable VM input is the source-independent architecture foundation cache.

Compact workflow evidence is retained for at most 30 days. VM workflows may reuse only the verified source-independent architecture foundation stored through the repository's architecture/fingerprint-keyed Actions cache. Exact-candidate images and writable QCOW2 overlays are disposable, are never accepted as resume input, and are excluded from uploaded compact evidence. Interoperability runs always start fresh candidate/reference VMs from verified foundations.

Every hosted job declares an explicit timeout no greater than 75 minutes. `tools/workflow_budget_gate.py` enforces job timeouts, evidence retention, verified-foundation/disposable-candidate safeguards and interoperability disk exclusion before workflow integrity evidence is recorded.

`tools/integrity_scan.py` can verify every tracked blob completely with explicit `--full-tree`, and its default bounded mode records the exact parent-to-candidate diff plus changed-file blob hashes while checking checkout bytes and modes. `tools/workflow_guard.sh` runs ordinary policy/regression gates and records one bounded baseline diff manifest; workflows perform a matching final scan before preserving state. These machine checks prove candidate identity and checkout immutability for their recorded scope.

`scratch/RESUME.md` is the durable human resume index. `docs/PROJECT_STATE.md` remains the authoritative protocol/project state. Every substantive commit must refresh both files in the same commit. Candidate promotion is determined by the documented exact-SHA gates.
