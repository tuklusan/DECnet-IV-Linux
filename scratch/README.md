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

Every workflow creates a unique directory under `scratch/runtime/<run-id>/<run-attempt>/<job>/`. It records `state.json`, exact source commit/tree identity, workflow/run/job/runner identifiers, parent or resumed run identifiers, status milestones, and the three byte-complete SoP scan manifests. VM and interoperability workflows place resumable disks, packet captures, serial logs, hashes, and other evidence below the same run directory.

At job completion the complete run directory is uploaded as a workflow artifact retained for 90 days. Workflows with a `resume_run_id` input restore prior artifacts under `scratch/restored/<run-id>/` before resuming. Artifacts never make runner-local RAM or processes persistent; only explicitly saved files are resumable.

`tools/sop_scan.py` reads every tracked blob completely from both the commit object and the checked-out file, compares bytes and executable/symlink mode, records size/line/hash data, and computes a deterministic whole-tree scan digest. `tools/workflow_sop.sh` requires three consecutive matching scans of the exact source revision before an acceptance job proceeds, then workflows perform a final exact-tree scan before preserving state. These scans verify completeness and immutability of the reviewed bytes; they supplement, rather than replace, the required semantic/manual SoP review.

`scratch/RESUME.md` is the durable human resume index. `docs/PROJECT_STATE.md` remains the authoritative protocol/project state. Every substantive commit must refresh both files in the same commit.
