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
- Every substantive commit updates both this file and `scratch/RESUME.md` in the same commit.
- Acceptance applies only to the exact unchanged `main` commit that satisfies the required SoP and gates.
- `tools/project_state_gate.py`, `tools/license_monkey.py`, `tools/repo_policy.py` and `tools/workflow_budget_gate.py` enforce continuity, licensing/header, repository word policy, and hosted-runner/storage policy.
- Ordinary source/document pushes do not automatically consume hosted runners. Acceptance workflows are demand-driven; an owner-opened issue titled exactly `DNIV acceptance gates` is the controlled dispatcher after repository policy succeeds and the event revision still equals `main`.
- Runner jobs share repository-wide x64 and arm64 concurrency slots and queue rather than replacing pending work.
- Every hosted job declares an explicit timeout no greater than 75 minutes. Short build/policy jobs use smaller caps. Long-duration campaigns must checkpoint and continue in later jobs; a hosted runner is never treated as persistent compute.
- `scratch/` is the persistent workflow/review namespace. Tracked `scratch/RESUME.md` records the durable human checkpoint; mutable run state is written below ignored `scratch/runtime/`, uploaded as workflow artifacts, and restored below ignored `scratch/restored/` on later runner sessions.
- A run/session ID is lineage, not persistence by itself. Hosted RAM, processes and live QEMU state disappear when the job ends. Persistence exists only for explicitly uploaded and subsequently verified files.
- Compact logs, scan manifests and packet evidence use at most 30-day retention. Two-node resumable QCOW2 checkpoints are separated from compact evidence, retained for 3 days, and older successful checkpoints for the same architecture are automatically deleted after a replacement has uploaded successfully. Failed-run checkpoints age out by retention policy.
- Interoperability runs always start fresh VMs; their uploaded evidence excludes transient QCOW2 overlays. An interoperability `resume_run_id` restores prior evidence/lineage only.
- Each workflow state records the exact source commit/tree, workflow/job/run/attempt, runner identity, parent/resume run identifiers, milestones, scan manifests, logs and applicable resumable evidence.

## SoP delivery rule

1. Read the complete latest repository copy byte-for-byte and line-by-line without truncation; find and fix defects/gaps.
2. Any fix resets the sequence to Step 1 on the new latest copy.
3. Delivery requires three consecutive clean complete Step-1 passes.
4. Any later change resets the sequence.

`tools/sop_scan.py` and `tools/workflow_sop.sh` verify that workflow jobs repeatedly read the complete tracked byte image of one exact commit/tree and that no tracked byte changes during a gate. `tools/workflow_sop.sh` also runs the hosted-runner/storage budget gate before the three scans. Those machine checks are evidence of byte completeness, immutability and workflow-budget compliance; they do not replace the required semantic/manual SoP review. Automated tests, diffs, excerpts and previous reviews likewise do not replace the rule.

`tools/project_state_gate.py` validates staged continuity records from the staged index and committed continuity records from the requested commit object. Working-tree contents cannot substitute for either source.

## Phase status

### Phase 1

Foundation complete: versioned UAPI, `decnet_iv.ko`, configurable identity, `/dev/decnet_iv`, Routing Layer EtherType registration/counters, `dnctl`, centralized test addressing, unit tests and native x86_64/aarch64 build gates.

### Phase 2

Foundation complete: pinned Ubuntu Base 26.04.1 amd64/arm64 rootfs files, pinned package snapshot `20260915T000000Z`, deterministic ext4/QCOW2 assembly, exact guest kernel/module build, direct kernel/initrd boot, two independent one-NIC VMs, packet capture and serial evidence.

Ubuntu Base initially lacks usable certificate trust for the snapshot service. Image construction bootstraps only signed `ca-certificates` with TLS peer verification temporarily disabled, refreshes package-owned trust, then requires ordinary verified snapshot access for all remaining packages. The sparse root filesystem floor is 4 GiB.

Image source staging archives the exact tracked `HEAD` commit with `git archive` and records that commit inside the guest source tree. Mutable `scratch/runtime`, restored workflow artifacts, generated lab evidence and other untracked checkout state cannot leak into the base candidate image. Derived candidate/reference images likewise install their guest scripts and package-snapshot metadata from that archived in-image source tree rather than the mutable host checkout.

The retained `phase2` smoke gate exchanges deliberately generated standard DECnet Routing Layer Ethernet frames. Successful resumable checkpoints are sealed as format 2 and include `session.env` in `SHA256SUMS`; resume requires matching architecture, exact source revision and mode. Older unsealed format-1 checkpoints are rejected.

### Phase 3

Implementation is in progress. UAPI v2 provides standard Phase IV node MAC derivation, router/endnode hello generation and parsing, periodic hello transmission, per-interface adjacency state, 3.1x listen-time expiry, designated-router election, extended counters and `dnctl adjacencies`.

Implemented corrections include the two-byte little-endian Ethernet Routing Layer payload length, legal trailing Ethernet padding, dedicated All-Level-2-Routers membership/transmission for Linux L2 routers, transactional filter installation, runtime identity-change serialization with adjacency processing, software destination-class validation, and the 128-byte maximum accepted Phase IV endnode hello test-data image.

Router-router adjacencies begin INIT and become UP when the peer router hello lists the local router with expected priority. Loss of that listing returns an UP adjacency to INIT; listen expiry removes it. Routers accept valid endnode hellos as UP. Endnodes select one router adjacency. Same-area rules apply except that L2 routers may form L2 adjacencies across areas. Router admission is capped at 33 per interface and retains the highest `(priority, node address)` set.

The E1 self-to-self harness covers L1 hello exchange, observable INIT/UP behavior, listener expiry, module restart/recovery, designated-router behavior, protocol source MACs, DECnet unicast-filter ownership and survival of a post-install primary device-MAC change.

The independent-peer harness boots candidate and reference in separate VMs on both native architectures. Route20 and PyDECnet cover Linux L1 router, L2 router and endnode roles against independent routers. PyDECnet additionally runs as an independent endnode against a Linux L1 router, closing the previously missing independent proof that Linux router-side endnode-hello parsing/admission works. The gate requires standard framing, protocol-derived source MACs, two-way router-list evidence where applicable, endnode hello test data, hardware-MAC change survival, protocol-unicast reception, hard peer loss/listen expiry, fresh-peer recovery and retained packet/serial evidence. The reference image never loads `decnet_iv`.

Previous full-tree reviews fixed QEMU process-lifetime handling in the interop harness, sealed checkpoint metadata integrity, stale format-1 lab documentation, the missing independent endnode-to-Linux-router direction, hosted HEAD-metadata policy enforcement, durable `scratch/` workflow state/evidence handling, exact-commit base-image source staging, and derived-image provenance. The latest operational review found two acceptance-control gaps: continuity validation could be masked by different working-tree files, and several hosted jobs inherited the provider's much larger default runtime while large VM artifacts were retained indiscriminately. Continuity validation now reads the index/commit object as appropriate. Workflow jobs are capped at 75 minutes or less, compact evidence is bounded to 30 days, transient interop disks are not uploaded, and short-lived rolling VM checkpoints are managed separately. These corrections reset SoP; no earlier clean pass or acceptance evidence carries forward.

## Test addressing

Ordinary lab addressing is centralized in `tests/lab/test-addresses.env`: area 31, nodes 70 through 79, names DN70 through DN79. Larger and inter-area tests extend this deliberately. The live L2 interoperability scenario deliberately places the independent peer in area 32.

## Pre-production acceptance

`docs/PRE_PRODUCTION_TEST.md` is the single consolidated production acceptance procedure. It de-duplicates E0-E4/D0-D5 with applicable pinned-reference coverage and adds Linux-kernel lifecycle/concurrency, malformed-input, resource, evidence, security, performance, stress, soak, endurance, real-peer and upgrade/rollback coverage. Documentation alone is never green; required tests must execute with complete evidence.

Hosted-runner campaigns longer than one job are segmented at verified disk/evidence checkpoints. Segmented execution is not described as uninterrupted soak. Any release requirement that explicitly needs uninterrupted execution beyond the hosted-job ceiling must run on a persistent controller outside the ephemeral hosted-runner model.

## Resume point

The current `main` candidate combines the Phase 1/2 foundation, Phase 3 Ethernet initialization/adjacency implementation, self-to-self E1 harness, live two-VM Route20/PyDECnet interoperability in both router directions that their roles support, signed-snapshot certificate bootstrap, exact-commit image and derived-image guest source staging, framing/filter/multicast/concurrency fixes, endnode test-data bound, repository policy, exact-QEMU-PID hard-stop testing, sealed format-2 VM checkpoints, hosted HEAD-metadata policy enforcement, the repository-root `scratch/` persistence namespace, exact-source continuity validation, and automatic hosted-runner/artifact budgets. Acceptance workflows record exact run/session lineage and evidence below `scratch/runtime/`, restore prior artifacts below `scratch/restored/`, require three matching byte-complete exact-tree scans plus a final post-gate scan, and reject workflow definitions outside the 75-minute/30-day budgets. The protocol phase remains Phase 3.

## Next action

Restart the semantic/manual SoP sequence on the exact resulting `main` commit and require three consecutive clean complete full-repository passes. The workflow scan manifests and workflow-budget gate must independently agree on that same commit/tree. Then run exact-head repository policy/continuity, native x86_64/aarch64 build, pinned reference baselines, E1 self-to-self and live Route20/PyDECnet interoperability on both architectures. Preserve compact evidence under the bounded retention policy and only the rolling resumable VM checkpoints. Accept only that unchanged `main` commit after every required Phase 3 gate is green. Any defect, evidence gap or later edit resets SoP. Phase 4 routing begins only after the Phase 3 gates are green.
