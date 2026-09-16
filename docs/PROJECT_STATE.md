# Project State

This is the authoritative continuity record for DECnet-IV-Linux. Read `docs/HANDOVER.md`, this file, `docs/ROADMAP.md`, `docs/ARCHITECTURE.md`, `docs/TEST_LAB.md` and `docs/PRE_PRODUCTION_TEST.md` before changing protocol, image or acceptance behavior.

## Goal

Build a complete native DECnet Phase IV stack for maintained Linux as a fresh out-of-tree kernel module plus useful DECnet/Linux userspace. Deliver reproducible x86_64/aarch64 VM images and prove behavior against independent implementations and real DEC systems.

## Architecture

- Base image: pinned Ubuntu Base 26.04.1 LTS for amd64 and arm64.
- Kernel target: native Ethernet, endnode/L1/L2 routing, NSP, sockets/UAPI, Session Control support, NICE/NML hooks/state and DDCMP.
- Routing, NSP and DDCMP state machines remain in kernel space.
- Userspace target: `ncp`, `sethost`/`dnlogin`, DAP/FAL/RMS tools, PHONE, mail, task/object access, daemons, libraries, diagnostics and administration tools.
- Primary VM artifact: QCOW2; RAW/conversion formats follow for release.
- Acceptance nodes are independent VMs with independent kernels. Namespaces/containers do not satisfy VM gates.

## References and licensing

Preferred references are the project forks `tuklusan/Route20`, `tuklusan/pydecnet`, `tuklusan/LinuxDECnet` and `tuklusan/simh`. Upstreams are comparison/provenance sources only. Direct reuse requires compatible licensing and retained notices; otherwise use documented protocol behavior and independent implementation.

Pinned revisions in `tests/reference/refs.env`:

- Route20: `b94115b2615c6463d1f006924ceeadde8e2d4367`
- PyDECnet behavior/live: `a7194be8d72dea6f9eb4f77083f056f53e80df58`
- PyDECnet tests: `9a844987bf3a1450632dee8d37e60a23a453bad3`
- LinuxDECnet comparison: `ff39eef045d1e4b7b72a3d40111e89c07a473398`
- SIMH: `5b73b1032b52d19bf80752ea4d9cbbdc92e7b5e0`

Self-to-self success is never sufficient for final interoperability claims.

## Repository discipline

- Perform substantive work on a feature branch from the exact current `main` commit. Do not promote a branch tip merely because it is newer.
- Every substantive commit updates this file in the same commit.
- Promotion is only the exact commit that has satisfied the required SoP and acceptance gates; never rebuild or amend between green evidence and promotion.
- Pull requests are not required for this single-developer repository unless deliberately used for review; the branch/commit identity remains the release unit.
- `tools/project_state_gate.py` enforces the continuity-file rule.
- `tools/repo_policy.py` enforces the configured whole-token repository policy. Local hooks live in `.githooks`.
- The repository-policy workflow is the sole automatic workflow exception. Build, continuity, reference and VM workflows are demand-driven.
- Workflow/job concurrency groups queue with cancellation disabled; repository-wide x64 and arm64 runner slots bound concurrency.
- An owner-opened issue titled exactly `DNIV acceptance gates` dispatches current `main` acceptance workflows after policy succeeds and the event revision still matches `main`.
- Generated VM evidence remains under ignored `tests/lab/artifacts/` and workflow artifacts.

## SoP delivery rule

1. Read the complete latest repository copy byte-for-byte and line-by-line without truncation; find and fix defects/gaps.
2. Any fix resets the sequence to Step 1 on the new latest copy.
3. Delivery requires three consecutive clean complete Step-1 passes.
4. Any later change resets the sequence.

Automated tests, diffs, excerpts and previous reviews do not replace this rule.

## Phase status

### Phase 1

Foundation complete: versioned UAPI, `decnet_iv.ko`, configurable identity, `/dev/decnet_iv`, Routing Layer EtherType registration/counters, `dnctl`, centralized test addressing, unit tests and native x86_64/aarch64 build gates.

### Phase 2

Foundation complete: pinned Ubuntu Base 26.04.1 amd64/arm64 root files, pinned package snapshot `20260915T000000Z`, deterministic ext4/QCOW2 assembly, exact guest kernel/module build, direct kernel/initrd boot, two independent one-NIC VMs, packet capture and serial evidence.

Ubuntu Base initially lacks usable certificate trust for the snapshot service. The image builder bootstraps only signed `ca-certificates` with TLS peer verification temporarily disabled, refreshes package-owned trust, then requires ordinary verified snapshot access before the remaining packages. Snapshot metadata/package signatures remain required.

The image build uses a 4 GiB sparse root filesystem. The former 2 GiB workspace filled while installing the arm64 virtual-kernel modules. The larger sparse backing preserves compact QCOW2 output while providing installation workspace.

The retained Phase 2 smoke gate generates DECnet Routing Layer Ethernet frames between two endnodes. VM checkpoints contain base image, portable overlays, exact kernel/initrd, checksums, session metadata, logs and capture; resume requires matching architecture/source revision/mode.

### Phase 3

Implementation is in progress. UAPI v2 provides standard Phase IV node MAC derivation, router/endnode hello generation/parsing, periodic hello transmission, per-interface adjacency state, 3.1x listen expiry, designated-router election, extended counters and `dnctl adjacencies`.

Router-router adjacencies begin INIT and become UP when the peer lists the local router with expected priority. Loss of that listing returns an UP adjacency to INIT; listener expiry removes it. Routers accept valid endnode hellos as UP. Endnodes select one router adjacency. Same-area rules apply except L2 routers may form L2 adjacency across areas. Router admission is capped at 33 per interface and keeps the highest `(priority, node address)` set. Total adjacency storage is 64.

The E1 self-to-self harness proves L1 hello exchange, INIT/UP behavior, expiry, module restart/recovery, designated-router behavior, protocol source MACs, DECnet unicast receive-filter ownership and survival of a primary NIC MAC change while loaded. DN71 wins the equal-priority designated-router election over DN70. NIC hardware MACs deliberately differ from DECnet node MACs.

Full-tree reviews found and corrected several shared-implementation blind spots:

- standard DECnet Ethernet includes a two-byte little-endian Routing Layer payload length after EtherType `0x6003`; the implementation now emits/validates/strips it and ignores legal trailing padding;
- L2 routers own and transmit on the All-Level-2-Routers multicast group `09-00-2B-02-00-00`;
- runtime identity change and hello validation/adjacency mutation share the adjacency lock so an in-flight old-identity hello cannot repopulate stale state;
- software receive validation checks local unicast and role-correct multicast destinations instead of relying only on hardware filtering;
- whole-token repository matching treats underscore as a separator; workflow/job queues do not replace older pending runs.

Three consecutive clean complete SoP passes were previously reached on `e59afc1cdee594417137f21a5ea3f0ebb72807eb`. Acceptance exposed the old 2 GiB arm64 image-space failure, so all evidence from that earlier revision is historical only. Every later image/protocol/policy/workflow/acceptance correction resets SoP.

The protocol implementation baseline on `main` before the pre-production-procedure feature branch is `c29693951aabd6b632079676866edcd1ba30cbf8` (`Validate received DECnet destinations`). No Phase 3 completion claim is valid until the exact promoted commit completes required review and acceptance/interoperability evidence.

## Test addressing

Ordinary lab addressing is centralized in `tests/lab/test-addresses.env`: area 31, nodes 70 through 79, names DN70 through DN79. Larger/inter-area tests extend this explicitly.

## Pre-production acceptance procedure

`docs/PRE_PRODUCTION_TEST.md` is the single consolidated production acceptance procedure. It de-duplicates E0-E4/D0-D5 with applicable pinned-reference coverage and adds Linux-kernel lifecycle/concurrency, malformed-input, resource, evidence, security, performance, stress, soak, endurance, real-peer and upgrade/rollback coverage.

The forensic review of the initial consolidation found gaps that are now explicit blockers: SMP/multi-vCPU races; 32-bit compatibility UAPI; namespace isolation/device movement; nonlinear/cloned/fragmented skb paths; exact adjacency/router saturation/replacement boundaries; filter transaction rollback and filter-reference coexistence; exact timer/DR/version/padding/endnode-test-data boundaries; boot/late-NIC ordering; false-green harness tests; image-build/storage/download/snapshot/conversion failures; second Ethernet driver/offload/MTU coverage; adversarial fairness; property/model/differential and mutation-generated tests; hard-power release-image recovery; 72-hour and 7-day endurance; long quiet periods; and N-1 upgrade/downgrade/rollback/mixed-version testing once an N-1 release exists.

The same inventory found LinuxDECnet `dnprogs/libvaxdata/src/test.c`; it is PP-00 reference health and becomes PP-07 blocking evidence when VAX/RMS conversion is claimed. The pinned SIMH makefile normally runs available per-simulator tests; the exact DEC-host target is therefore built with tests enabled and its relevant target transcript retained.

Documentation does not make a requirement green. Required tests must be executed with complete evidence. Missing evidence invalidates production acceptance.

This correction resets the SoP sequence. No review or acceptance result from an earlier procedure revision carries forward.

## Resume point

The protocol baseline remains Phase 3 on current `main`; the consolidated pre-production procedure is being completed on a feature branch. The candidate procedure now includes implementation-derived, reference-derived, negative, stress, soak, endurance, false-green, real-peer and future upgrade/rollback gates. No documentation-only change advances the protocol phase.

## Next action

On the exact latest pre-production-procedure candidate, complete three consecutive clean full-repository SoP passes. Any defect or edit restarts the sequence. Promote only that exact green commit; do not amend or rebuild it after the evidence is tied to it. After promotion, continue Phase 3 exact-head acceptance and live interoperability against the pinned Route20 and PyDECnet forks, including two-byte Ethernet length framing and L2 multicast behavior. Phase 4 routing begins only after the Phase 3 gates are green.
