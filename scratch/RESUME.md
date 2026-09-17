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

Phase 3 remains active and all substantive work stays on `main`. The active delivery review is the complete exact tracked tree, byte-for-byte and line-by-line. Any defect changes the candidate and resets the clean-pass count; three consecutive clean complete passes are required before fresh acceptance.

Workflow jobs bind exact source commit/tree, expected parent candidate SHA where applicable, run lineage, runner identity, architecture/mode and retained evidence. Routine workflow immutability checks use one bounded parent-to-candidate baseline diff manifest and one matching final manifest. A byte-complete tracked-tree machine scan remains explicit through `tools/sop_scan.py --full-tree`; these machine checks do not replace the semantic/manual delivery passes.

Hosted-runner policy is unchanged: at most 75 minutes per job, `queue: max`, `cancel-in-progress: false`, compact evidence at most 30 days, VM checkpoints 3 days with paginated stale-checkpoint pruning, and fresh interoperability VMs.

Exact-head acceptance parent `35195064164` on candidate `3af6da37274006fbd2b0cbe9682821f30bd5f7ba` completed repository policy, project-state/continuity, native x86_64/aarch64 build and external reference gates green. E1 child `35195101815` and independent-interoperability child `35195103898` both failed before protocol assertions during base-image construction.

The image failures moved deeper after the preceding image correction. amd64 produced a structurally valid uncompressed QCOW2, but the host `cmp` of intended RAW versus QCOW2-round-tripped RAW reported inequality even though sparse/allocation representation is not guest-visible content. arm64 progressed past the prior ownership problem but failed the raw Image magic check because Ubuntu 26.04 supplies an EFI-zboot wrapper that QEMU 8.x can unpack for direct boot.

Candidate `c33241a984b6f1c61c0a7aa83b89945dd60a4fb6` switches base and derived acceptance images to `qemu-img compare` for RAW/QCOW2 logical-content equality and explicitly rejects host RAW `cmp` or strict allocation-sensitive compare. It also keeps one outer-gzip peel for arm64, then accepts either raw AArch64 Image magic or a validated gzip EFI-zboot header with sane payload bounds. `tests/policy/test_image_builder_gate.py` requires every read, signature check and logical comparison safeguard.

Commit `f18465c08fd5c6fe2fb72a12875781a3c874bff3` accidentally created an empty top-level `NONEXISTENT` path during repository tooling; candidate `c33241a984b6f1c61c0a7aa83b89945dd60a4fb6` deleted it. A later unintended non-main ref triggered repository cleanup run `35219630482`. The cleanup step successfully deleted every non-main ref and confirmed only `refs/heads/main` remained, but its verification step failed because `workflow_sop.sh ... main` rejected the create-event `GITHUB_REF` even though the job had checked out exact current `main`. Candidate `57f123d43760554a333772755da9d196c6444614` added a dedicated `maintenance` scope, changed cleanup to use it, and added regression coverage so maintenance still verifies exact remote main while acceptance-only ref checks remain confined to `main` scope.

The first complete-tree review of `57f123d43760554a333772755da9d196c6444614` found stale continuity and SoP text. `docs/TEST_LAB.md` still claimed three automatic pre-work exact-tree scans, while current workflows record one bounded baseline plus a matching final manifest. It also claimed the Repository Policy workflow did not run on `create`, although non-main branch creation intentionally triggers automatic cleanup. `docs/HANDOVER.md` and `docs/PROJECT_STATE.md` still described the semantic/manual SoP as diff-scoped rather than complete-tree. Candidate `c71bc79a176bbac367a910567160e8809283c051` corrected those records.

The first complete-tree pass on `c71bc79a176bbac367a910567160e8809283c051` found the same obsolete machine-scan description in `scratch/README.md`, which still claimed three automatic complete scans and a three-scan `workflow_sop.sh` gate. Candidate `f2bab342389ce8da8c8696c222c37c35326ceefe` corrected the scratch workspace contract to describe the actual bounded baseline/final machine checks while preserving the separate three-pass complete semantic/manual delivery SoP.

The complete-tree pass on `f2bab342389ce8da8c8696c222c37c35326ceefe` then found a real Phase IV DR handoff defect. `dniv_local_is_dr()` delayed only from module load/identity change, so after a higher-priority or equal-priority higher-address router disappeared the local router could start sending All-Endnodes hellos immediately. The pinned live PyDECnet reference starts a new five-second DRDELAY whenever the local router first becomes the best candidate and cancels that pending transition when a better router is known. The correction keeps separate candidate timing per interface, resets it across interface-down and identity changes, and drops interface adjacencies on link-down.

The E1 regression is strengthened at the wire level rather than relying only on a source check. DN71 is the designated router at equal priority because its node address is higher. E1 silences DN71 long enough for DN70 to expire it, but for less than listener expiry plus DRDELAY. DN70 must show expiry/recovery yet must never emit an All-Endnodes hello during that gap. The existing capture rule `endnodesA == 0` therefore detects the old immediate-handoff bug while still requiring DN71 All-Endnodes traffic.

Commit `f2147d83c4063a461bc732f3e017608bd5ba675c` accidentally created tracked `scratch/SHOULD_NOT_CREATE` during repository tooling. It has no acceptance evidence. The current forward correction deletes it together with the DRDELAY change and both durable continuity updates. Consequently the complete clean-pass count is zero again.

Repository branch policy is active and the live remote branch invariant is only `refs/heads/main`. Cleanup run `35219630482` is the latest cleanup attempt: branch deletion succeeded, post-delete SoP verification exposed the maintenance-scope bug that is now corrected. GitHub-owned actions remain pinned to immutable full SHAs.

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
| Delivery semantic/manual SoP scope | complete exact tracked tree, byte-for-byte and line-by-line |
| Clean complete semantic/manual passes on this candidate | 0 |
| Routine workflow scan requirement | one bounded baseline diff manifest plus matching final diff manifest |
| Explicit machine full-tree scan | `tools/sop_scan.py --full-tree` |
| Phase 3 acceptance | image/maintenance corrections plus DR handoff correction applied; pending exact-head gates |
| Latest acceptance parent | `35195064164` |
| Latest E1 VM run | `35195101815`, failure during base-image build |
| Latest interoperability run | `35195103898`, failure during base-image build |
| Latest reference baseline run | `35195100046`, success |
| Latest native build run | `35195096243`, success |
| Latest project-state run | `35195098169`, success |
| Latest branch-cleanup run | `35219630482`, branch deletion success; verification failure exposed now-fixed maintenance-scope bug |

## Persistent run index

Mutable workflow state remains below ignored `scratch/runtime/`; restored evidence remains below ignored `scratch/restored/`. A run ID is lineage, not persistent execution. Only explicitly uploaded and subsequently verified files persist across hosted runners.

The tracked table above is the durable human index. Runtime evidence belongs only to its exact candidate and never transfers acceptance status to a later commit.

## Next action

Verify repository/continuity and branch-cleanup maintenance behavior on exact head, then dispatch fresh exact-head Phase 3 x86_64/aarch64 native build, pinned reference, E1, Route20 and PyDECnet interoperability gates. Phase 4 starts only after that unchanged candidate is green.
