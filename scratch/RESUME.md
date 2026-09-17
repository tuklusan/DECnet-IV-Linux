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

Exact-head acceptance parent `35195064164` on candidate `3af6da37274006fbd2b0cbe9682821f30bd5f7ba` completed repository policy, project-state/continuity, native x86_64/aarch64 build and external reference gates green. E1 child `35195101815` and independent-interoperability child `35195103898` both failed before protocol assertions during base-image construction.

The failures moved deeper after the preceding image correction. amd64 produced a structurally valid uncompressed QCOW2, but the host `cmp` of intended RAW versus QCOW2-round-tripped RAW reported inequality even though sparse/allocation representation is not guest-visible content. arm64 progressed past the prior ownership problem but failed the raw Image magic check because Ubuntu 26.04 supplies an EFI-zboot wrapper that QEMU 8.x can unpack for direct boot.

The current correction switches base and derived acceptance images to `qemu-img compare` for RAW/QCOW2 logical-content equality and explicitly rejects host RAW `cmp` or strict allocation-sensitive compare. It also keeps one outer-gzip peel for arm64, then accepts either raw AArch64 Image magic or a validated gzip EFI-zboot header with sane payload bounds. `tests/policy/test_image_builder_gate.py` requires every read, signature check and logical comparison safeguard. This substantive change resets the scoped pass count to zero and invalidates all earlier acceptance results for promotion.

Commit `f18465c08fd5c6fe2fb72a12875781a3c874bff3` accidentally created an empty top-level `NONEXISTENT` path during repository tooling. The current candidate deletes it; it contained no protocol/build content and no acceptance was dispatched from that state.

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
| Phase 3 acceptance | EFI-zboot/logical-image correction plus stray-path removal applied; fresh exact-head acceptance required |
| Latest acceptance parent | `35195064164` |
| Latest E1 VM run | `35195101815`, failure during base-image build |
| Latest interoperability run | `35195103898`, failure during base-image build |
| Latest reference baseline run | `35195100046`, success |
| Latest native build run | `35195096243`, success |
| Latest project-state run | `35195098169`, success |
| Latest branch-cleanup run | `35179252422`, success |

## Persistent run index

Mutable workflow state remains below ignored `scratch/runtime/`; restored evidence remains below ignored `scratch/restored/`. A run ID is lineage, not persistent execution. Only explicitly uploaded and subsequently verified files persist across hosted runners.

The tracked table above is the durable human index. Runtime evidence belongs only to its exact candidate and never transfers acceptance status to a later commit.

## Next action

Perform three consecutive semantic/manual passes over the exact first-parent-to-candidate diff with three context lines, using only directly necessary local/dependency context. Any fix creates a new candidate and resets the pass sequence. After three clean passes on the unchanged candidate, run fresh exact-head Phase 3 repository/continuity, x86_64/aarch64 native build, pinned reference, E1, Route20 and PyDECnet interoperability gates. Phase 4 starts only after that unchanged candidate is green.
