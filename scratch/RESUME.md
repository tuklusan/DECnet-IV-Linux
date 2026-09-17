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

Exact-head acceptance parent `35192508159` on candidate `6d4ef7b364392d1a999c1bf433d833aed86c6eef` completed repository/continuity, native x86_64/aarch64 build and external reference gates green; the PyDECnet reference row passed on one isolated rerun after its timing-sensitive DDCMP UDP queue test missed by one packet on the first attempt. E1 child `35192540407` and independent-interoperability child `35192542464` both failed before protocol assertions while building the exact candidate image.

The failures are now localized. arm64 copied/decompressed the direct-boot kernel but attempted a non-root Image-header `dd` while the artifact could still be root-owned, producing `Permission denied`. amd64 passed `qemu-img check` and produced a mountable round-tripped raw image, but the `ro,noload` verification mount did not expose the already-validated smoke entry point. The correction gives the arm64 kernel artifact to the invoking user before the header probe and replaces the fragile mounted critical-file round-trip check with a complete RAW byte-for-byte comparison after QCOW2 conversion. Pre-conversion exact smoke script/unit comparisons and systemd validation remain mandatory. The image-builder policy gate now requires both safeguards.

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
| Phase 3 acceptance | base-image acceptance failure corrected; fresh exact-head acceptance required |
| Latest acceptance parent | `35192508159` |
| Latest E1 VM run | `35192540407`, failure during image build |
| Latest interoperability run | `35192542464`, failure during candidate image build |
| Latest reference baseline run | `35192537809`, success on attempt 2 |
| Latest branch-cleanup run | `35179252422`, success |

## Persistent run index

Mutable workflow state remains below ignored `scratch/runtime/`; restored evidence remains below ignored `scratch/restored/`. A run ID is lineage, not persistent execution. Only explicitly uploaded and subsequently verified files persist across hosted runners.

The tracked table above is the durable human index. Runtime evidence belongs only to its exact candidate and never transfers acceptance status to a later commit.

## Next action

Perform three consecutive semantic/manual passes over the exact first-parent-to-candidate diff with three context lines, using only directly necessary local/dependency context. Any fix creates a new candidate and resets the pass sequence. After three clean passes on the unchanged candidate, run fresh exact-head Phase 3 repository/continuity, x86_64/aarch64 native build, pinned reference, E1, Route20 and PyDECnet interoperability gates. Phase 4 starts only after that unchanged candidate is green.
