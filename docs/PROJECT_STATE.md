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

# Project State

This is the authoritative continuity record for DECnet-IV-Linux. Read `docs/HANDOVER.md`, this file, `scratch/RESUME.md`, `docs/ROADMAP.md`, `docs/ARCHITECTURE.md`, `docs/TEST_LAB.md` and `docs/PRE_PRODUCTION_TEST.md` before changing protocol, image or acceptance behavior. Commit history retains prior state records; this file describes the current tree.

## Goal

Build a complete native DECnet Phase IV stack for maintained Linux as a fresh out-of-tree kernel module plus useful DECnet/Linux userspace. Deliver reproducible x86_64/aarch64 VM images and prove behavior against independent implementations and later real DEC systems.

## Architecture

- Base image: pinned Ubuntu Base 26.04.1 LTS for amd64 and arm64.
- Kernel target: native Ethernet; endnode/Level 1/Level 2 routing; NSP; sockets/UAPI; Session Control; NICE/NML state/hooks; DDCMP.
- Routing, NSP and DDCMP state machines remain in kernel space.
- Userspace target: `ncp`, `sethost`/`dnlogin`, DAP/FAL/RMS tools, PHONE, mail, task/object access, daemons, libraries, diagnostics and administration tools.
- Primary VM artifact: QCOW2; RAW and conversion formats follow for release.
- Acceptance nodes are independent VMs, not containers or namespaces sharing one kernel.

## References and licensing

Preferred references are the project forks `tuklusan/Route20`, `tuklusan/pydecnet`, `tuklusan/LinuxDECnet` and `tuklusan/simh`. Upstreams are comparison/provenance sources only. Direct reuse requires compatible licensing and retained notices; otherwise use documented protocol behavior and independent implementation.

Pinned revisions in `tests/reference/refs.env`:

- Route20: `b94115b2615c6463d1f006924ceeadde8e2d4367`
- PyDECnet behavior/live: `a7194be8d72dea6f9eb4f77083f056f53e80df58`
- PyDECnet tests: `9a844987bf3a1450632dee8d37e60a23a453bad3`
- LinuxDECnet comparison: `ff39eef045d1e4b7b72a3d40111e89c07a473398`
- SIMH: `5b73b1032b52d19bf80752ea4d9cbbdc92e7b5e0`

The live PyDECnet pin has a pre-existing `Macaddr("1.24")` self-test contradiction, so its immediately preceding internally consistent revision remains the unmodified unit-test baseline. Route20 is the independent oracle for dedicated All-Level-2-Routers multicast behavior; the live PyDECnet pin interoperates as an L2 router through All-Routers and is not required to emit that dedicated multicast.

The product license is the canonical root `LICENSE`, blob `c6dabab19a2d36bffddabe7584a932c72fa272c3`. It applies to project-owned material only; third-party material remains under its original license. `tools/license_monkey.py` pins that exact license and canonical project header. The kernel module reports `MODULE_LICENSE("Proprietary")`, matching the product license.

Self-to-self success is never sufficient for final interoperability claims.

## Repository discipline

- Perform substantive work directly on `main`; do not create or use feature branches for project work.
- The remote branch invariant is exactly one head: `refs/heads/main`. `tools/repo_policy.py` rejects local project work outside `main`, rejects pushes that create/update non-main branches, rejects deletion of `main`, permits deletion of obsolete non-main refs, and makes acceptance fail while any non-main remote branch exists.
- An owner-opened issue titled exactly `DNIV branch cleanup` is the maintenance path for removing legacy remote branch refs. A non-main branch creation event enters the same cleanup job automatically. Cleanup checks out current `main`, deletes every non-main head, verifies that only `main` remains, then runs the exact-main workflow SoP machinery.
- Every substantive commit updates both this file and `scratch/RESUME.md` in the same commit.
- Acceptance applies only to the exact unchanged `main` commit that satisfies the required SoP and gates.
- `tools/project_state_gate.py`, `tools/license_monkey.py`, `tools/repo_policy.py` and `tools/workflow_budget_gate.py` enforce continuity, licensing/header, repository/branch policy, and hosted-runner/workflow-storage policy.
- Ordinary source/document pushes do not automatically consume hosted runners. Acceptance workflows are demand-driven; an owner-opened issue titled exactly `DNIV acceptance gates` is the controlled dispatcher after repository policy succeeds and the event revision still equals `main`.
- Acceptance children are bound to the dispatcher's exact candidate SHA. The dispatcher supplies both its run ID and `GITHUB_SHA`; `tools/scratch_state.py` refuses a parent-linked child without an expected SHA and refuses any source/expected mismatch. The expected SHA is retained in `state.json`. A `main` change during dispatch therefore produces a clean child failure instead of mixed-commit evidence.
- Runner jobs share repository-wide x64 and arm64 concurrency slots. Every workflow/job concurrency block uses `queue: max`; pending jobs queue up to GitHub's documented queue limit instead of replacing the previously pending gate. `cancel-in-progress: true` is forbidden by the workflow policy gate.
- Every hosted job declares an explicit timeout no greater than 75 minutes. Short build/policy jobs use smaller caps. Long-duration campaigns must checkpoint and continue in later jobs; a hosted runner is never treated as persistent compute.
- Live interoperability matrix rows contain at most two scenarios per hosted job. Route20 and PyDECnet coverage is split into bounded suites with unique scratch/evidence names so worst-case protocol waits cannot silently turn the 75-minute cap into a false-red acceptance run.
- GitHub-owned actions used by the workflows are full-SHA pinned: checkout v4.4.0 `11d5960a326750d5838078e36cf38b85af677262`, upload-artifact v4.6.2 `ea165f8d65b6e75b540449e92b4886f43607fa02`, and download-artifact v4.3.0 `d3f86a106a0bac45b974a628896c90dbdf5c8093`. The workflow policy gate rejects movable tags for these actions.
- `scratch/` is the persistent workflow/review namespace. Tracked `scratch/RESUME.md` records the durable human checkpoint; mutable run state is written below ignored `scratch/runtime/`, uploaded as workflow artifacts, and restored below ignored `scratch/restored/` on later runner sessions.
- A run/session ID is lineage, not persistence by itself. Hosted RAM, processes and live QEMU state disappear when the job ends. Persistence exists only for explicitly uploaded and subsequently verified files.
- Compact logs, scan manifests and packet evidence use at most 30-day retention. Two-node resumable QCOW2 checkpoints are separated from compact evidence, retained for 3 days, and older successful checkpoints for the same architecture are automatically deleted after a replacement has uploaded successfully. Compact VM evidence excludes the checkpoint kernel and initrd so heavy checkpoint payloads are not duplicated under the longer retention period. Failed-run checkpoints age out by retention policy.
- Interoperability runs always start fresh VMs; their uploaded evidence excludes transient QCOW2 overlays. An interoperability `resume_run_id` restores prior evidence/lineage only.
- Each workflow state records the exact source commit/tree, expected parent candidate SHA where applicable, workflow/job/run/attempt, runner identity, parent/resume run identifiers, milestones, scan manifests, logs and applicable resumable evidence.

## SoP delivery rule

1. Read the complete latest repository copy byte-for-byte and line-by-line without truncation; find and fix defects/gaps.
2. Any fix resets the sequence to Step 1 on the new latest copy.
3. Delivery requires three consecutive clean complete Step-1 passes.
4. Any later change resets the sequence.

`tools/sop_scan.py` and `tools/workflow_sop.sh` verify that workflow jobs repeatedly read the complete tracked byte image of one exact commit/tree and that no tracked byte changes during a gate. `tools/workflow_sop.sh` also runs regression tests for continuity, workflow-budget/queue/action-pin rules, direct-boot image construction safeguards and branch policy before running those gates. Those machine checks are evidence of byte completeness, immutability and policy-gate behavior; they do not replace the required semantic/manual SoP review. Automated tests, diffs, excerpts and previous reviews likewise do not replace the rule.

`tools/project_state_gate.py` validates staged continuity records from the staged index and committed continuity records from the requested commit object. Working-tree contents cannot substitute for either source. `tools/workflow_budget_gate.py` applies the same source discipline: pre-commit checks read the staged index and acceptance checks read the requested commit object. It enforces the 75-minute ceiling, bounded retention, `queue: max`, immutable GitHub action pins, parent expected-SHA plumbing, compact VM exclusions and maximum-two-scenario interoperability rows. `tests/policy/test_image_builder_gate.py` follows the same discipline: the pre-commit hook reads the staged image builder and workflow SoP reads the requested commit object, preventing a good mutable working copy from masking a bad staged/committed direct-boot builder.

## Phase status

### Phase 1

Foundation complete: versioned UAPI, `decnet_iv.ko`, configurable identity, `/dev/decnet_iv`, Routing Layer EtherType registration/counters, `dnctl`, centralized test addressing, unit tests and native x86_64/aarch64 build gates.

### Phase 2

Foundation complete: pinned Ubuntu Base 26.04.1 amd64/arm64 rootfs files, pinned package snapshot `20260915T000000Z`, deterministic ext4/QCOW2 assembly, exact guest kernel/module build, direct kernel/initrd boot, two independent one-NIC VMs, packet capture and serial evidence.

Ubuntu Base initially lacks usable certificate trust for the snapshot service. Image construction bootstraps only signed `ca-certificates` with TLS peer verification temporarily disabled, refreshes package-owned trust, then requires ordinary verified snapshot access for all remaining packages. Because package installation uses `--no-install-recommends`, image construction explicitly installs `initramfs-tools` and requires the generated `/boot/initrd.img-$krel` before build cleanup. The sparse root filesystem floor is 4 GiB.

Image source staging archives the exact tracked `HEAD` commit with `git archive` and records that commit inside the guest source tree. Mutable `scratch/runtime`, restored workflow artifacts, generated lab evidence and other untracked checkout state cannot leak into the base candidate image. Derived candidate/reference images likewise install their guest scripts and package-snapshot metadata from that archived in-image source tree rather than the mutable host checkout.

The retained `phase2` smoke gate exchanges deliberately generated standard DECnet Routing Layer Ethernet frames. Successful resumable checkpoints are sealed as format 2 and include `session.env` in `SHA256SUMS`; resume requires matching architecture, exact source revision and mode. Older unsealed format-1 checkpoints are rejected.

### Phase 3

Implementation is in progress. UAPI v2 provides standard Phase IV node MAC derivation, router/endnode hello generation and parsing, periodic hello transmission, per-interface adjacency state, 3.1x listen-time expiry, designated-router election, extended counters and `dnctl adjacencies`.

Implemented corrections include the two-byte little-endian Ethernet Routing Layer payload length, legal trailing Ethernet padding, dedicated All-Level-2-Routers membership/transmission for Linux L2 routers, transactional filter installation, runtime identity-change serialization with adjacency processing, software destination-class validation, and the 128-byte maximum accepted Phase IV endnode hello test-data image.

Router-router adjacencies begin INIT and become UP when the peer router hello lists the local router with expected priority. Loss of that listing returns an UP adjacency to INIT; listen expiry removes it. Routers accept valid endnode hellos as UP. Endnodes select one router adjacency. Same-area rules apply except that L2 routers may form L2 adjacencies across areas. Router admission is capped at 33 per interface and retains the highest `(priority, node address)` set.

The E1 self-to-self harness covers L1 hello exchange, observable INIT/UP behavior, listener expiry, module restart/recovery, designated-router behavior, protocol source MACs, DECnet unicast-filter ownership and survival of a post-install primary device-MAC change.

The independent-peer harness boots candidate and reference in separate VMs on both native architectures. Route20 and PyDECnet cover Linux L1 router, L2 router and endnode roles against independent routers. PyDECnet additionally runs as an independent endnode against a Linux L1 router, closing the previously missing independent proof that Linux router-side endnode-hello parsing/admission works. The gate requires standard framing, protocol-derived source MACs, two-way router-list evidence where applicable, endnode hello test data, hardware-MAC change survival, protocol-unicast reception, hard peer loss/listen expiry, fresh-peer recovery and retained packet/serial evidence. The reference image never loads `decnet_iv`.

Previous full-tree reviews fixed QEMU process-lifetime handling in the interop harness, sealed checkpoint metadata integrity, stale format-1 lab documentation, the missing independent endnode-to-Linux-router direction, hosted HEAD-metadata policy enforcement, durable `scratch/` workflow state/evidence handling, exact-commit base-image source staging, derived-image provenance, exact-source continuity/workflow-budget validation, hosted duration/storage budgets and bounded interoperability suites. The workflow sanity review then found acceptance-integrity gaps in pending-job replacement, dispatcher/main races, historical branch refs and movable action tags. The infrastructure correction added `queue: max`, exact parent-candidate SHA binding, main-only branch enforcement plus cleanup, immutable action pins and regression coverage. Cleanup canary run `35179022863` proved the new workflow loaded and executed but failed safely before ref deletion because its scratch directory had not yet been created when `maintenance.env` was written. The corrected cleanup run `35179252422` then removed all legacy refs, verified that only `main` remained, completed the exact-main machine SoP checks, and finished green.

Three consecutive complete semantic/manual SoP passes then completed cleanly on candidate `a57f44a2400bbf1fce7cc411489d51182c9ccd95`, and acceptance parent run `35181684059` dispatched exact-SHA-bound child gates. Native x86_64/aarch64 builds and project-state validation were green, and the Route20 reference baseline was green. VM child run `35181712924` exposed an image-construction defect before protocol boot on arm64: the kernel package installed, but `--no-install-recommends` left no initramfs generator, so no `/boot/initrd.img-*` existed. The correction explicitly installs `initramfs-tools`, asserts the exact generated initrd before package cleanup, and adds `tests/policy/test_image_builder_gate.py` to local/workflow gates. The first review of that correction then found the local hook called the new gate without staged-source selection; the gate now has explicit `--staged` and `--tree` modes, and both call sites use them. These changes invalidate all acceptance evidence and all semantic/manual SoP passes from earlier candidates; the latest candidate starts again at zero clean passes.

## Test addressing

Ordinary lab addressing is centralized in `tests/lab/test-addresses.env`: area 31, nodes 70 through 79, names DN70 through DN79. Larger and inter-area tests extend this deliberately. The live L2 interoperability scenario deliberately places the independent peer in area 32.

## Pre-production acceptance

`docs/PRE_PRODUCTION_TEST.md` is the single consolidated production acceptance procedure. It de-duplicates E0-E4/D0-D5 with applicable pinned-reference coverage and adds Linux-kernel lifecycle/concurrency, malformed-input, resource, evidence, security, performance, stress, soak, endurance, real-peer and upgrade/rollback coverage. Documentation alone is never green; required tests must execute with complete evidence.

Hosted-runner campaigns longer than one job are segmented at verified disk/evidence checkpoints. Segmented execution is not described as uninterrupted soak. Any release requirement that explicitly needs uninterrupted execution beyond the hosted-job ceiling must run on a persistent controller outside the ephemeral hosted-runner model.

## Resume point

Phase 3 remains active. Acceptance child VM run `35181712924` on prior candidate `a57f44a2400bbf1fce7cc411489d51182c9ccd95` failed before boot on arm64 because direct-boot image construction had no explicit initramfs generator under `--no-install-recommends`. The image builder now explicitly installs `initramfs-tools` and asserts the generated initrd before cleanup. The first review of the new regression also caught a staged-source bypass in its pre-commit invocation; `tests/policy/test_image_builder_gate.py` now reads either the staged index or the requested commit object, and the hook/workflow pass the corresponding mode. No SoP pass or acceptance result from either earlier candidate carries forward.

## Next action

Restart the semantic/manual SoP sequence from Step 1 on this exact new `main` commit and require three consecutive clean complete full-repository passes. The workflow scan manifests, image-builder regression, branch-policy regression, continuity regression and workflow-budget/action-pin gate must independently agree on that same commit/tree. Then dispatch a fresh exact-head acceptance parent and rerun repository policy/continuity, native x86_64/aarch64 build, pinned reference baselines, E1 self-to-self and bounded live Route20/PyDECnet interoperability suites on both architectures. Accept only that unchanged Phase 3 commit after every gate is green. Phase 4 kernel routing begins only after Phase 3 acceptance.
