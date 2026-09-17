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

`scratch/` is the repository-root persistence workspace for workflow and review state. The directory itself, this contract, and `RESUME.md` are tracked. Mutable runner state is deliberately not committed because changing the candidate while acceptance is running would invalidate the exact-head gate and reset SoP.

Every workflow creates a unique directory under `scratch/runtime/<run-id>/<run-attempt>/<job>/`. It records `state.json`, exact source commit/tree identity, workflow/run/job/runner identifiers, parent or resumed run identifiers, status milestones, and workflow scan manifests. VM and interoperability workflows place packet captures, serial logs, hashes, and other evidence below the same run directory.

A hosted run/session ID records lineage only. Hosted RAM, processes and live VM state do not survive job termination. Resume exists only for files that were explicitly uploaded as artifacts and subsequently restored and verified.

Compact workflow evidence is retained for at most 30 days. The two-node VM workflow uploads its sealed format-2 QCOW2 checkpoint separately from compact evidence, retains that heavy checkpoint for 3 days, and after a successful replacement upload deletes older successful checkpoint artifacts for the same architecture. Failed-run checkpoint artifacts age out under the same short retention window. Interoperability runs always start fresh VMs, so transient interoperability QCOW2 overlays are excluded from uploaded evidence.

Every hosted job declares an explicit timeout no greater than 75 minutes. `tools/workflow_budget_gate.py` enforces job timeouts, evidence retention, rolling VM checkpoint safeguards and interoperability disk exclusion before workflow scan evidence is recorded.

`tools/sop_scan.py` can verify every tracked blob completely with explicit `--full-tree`, and its default bounded mode records the exact parent-to-candidate diff plus changed-file blob hashes while checking checkout bytes and modes. `tools/workflow_sop.sh` runs the ordinary policy/regression gates and records one bounded baseline diff manifest; workflows perform a matching final scan before preserving state. These machine checks prove candidate identity and checkout immutability for their recorded scope. They do not replace the delivery SoP, which requires three consecutive complete semantic/manual reads of the exact latest tracked tree.

`scratch/RESUME.md` is the durable human resume index. `docs/PROJECT_STATE.md` remains the authoritative protocol/project state. Every substantive commit must refresh both files in the same commit.
