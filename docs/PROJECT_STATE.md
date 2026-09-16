# Project State

This is the authoritative continuity record for DECnet-IV-Linux. Read `docs/HANDOVER.md`, this file, `docs/ROADMAP.md`, `docs/ARCHITECTURE.md` and `docs/TEST_LAB.md` before changing protocol, image or acceptance behavior.

## Goal

Build a complete native DECnet Phase IV stack for maintained Linux as a fresh out-of-tree kernel module plus useful DECnet/Linux userspace. Deliver reproducible x86_64/aarch64 VM images and prove behavior against independent implementations and, later, real DEC systems.

## Architecture

- Base image: pinned Ubuntu Base 26.04.1 LTS for amd64 and arm64.
- Kernel: native Ethernet, endnode/Level 1/Level 2 routing, NSP, sockets/UAPI, Session Control support, NICE/NML hooks/state and DDCMP.
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

Self-to-self success is never sufficient for final interoperability claims.

## Repository discipline

- Work directly on current `main`; do not create pull requests or ordinary development branches.
- Every substantive commit updates this file in the same commit.
- `tools/project_state_gate.py` enforces continuity.
- `tools/repo_policy.py` enforces the configured case-insensitive whole-token repository word policy across the current tree, relevant new commit objects, refs/configuration, selected repository event metadata and collaborators. Local pre-commit, commit-message and pre-push hooks are provided by `.githooks`.
- The repository-policy workflow is the sole automatic workflow exception. Build, continuity, reference and VM workflows are demand-driven.
- An owner-opened issue titled exactly `DNIV acceptance gates` is the controlled dispatcher for those manual acceptance workflows after policy succeeds and `main` still matches the event revision.
- Generated VM evidence remains under ignored `tests/lab/artifacts/` and workflow artifacts.
- Runner jobs share repository-wide x64 and arm64 concurrency slots.
- The repository currently has no server-side ruleset available through the connected management surface, so local hooks plus the automatic policy workflow are the enforceable mechanisms available here.

## SoP delivery rule

1. Read the complete latest repository copy byte-for-byte and line-by-line without truncation; find and fix defects/gaps.
2. Any fix resets the sequence to Step 1 on the new latest copy.
3. Delivery requires three consecutive clean complete Step-1 passes.
4. Any later change resets the sequence.

Automated tests, diffs, excerpts and previous reviews do not replace this rule.

## Phase status

### Phase 1

Foundation complete: versioned UAPI, `decnet_iv.ko`, configurable identity, `/dev/decnet_iv`, Routing Layer EtherType registration/counters, `dnctl`, centralized test addressing, unit tests, and native x86_64/aarch64 build gates.

### Phase 2

Foundation complete: pinned Ubuntu Base 26.04.1 amd64/arm64 rootfs files, pinned package snapshot `20260915T000000Z`, deterministic ext4/QCOW2 assembly, exact guest kernel/module build, direct kernel/initrd boot, two independent one-NIC VMs, packet capture and serial evidence. The image builder seeds host trust only long enough to reach the pinned package snapshot, then installs and refreshes package-owned certificate trust in the guest.

The retained `phase2` smoke gate sends deliberately generated DECnet Routing Layer Ethernet frames between two endnodes. VM checkpoints contain the base image, portable overlays, exact kernel/initrd, checksums, session metadata, logs and capture and may resume only against the matching architecture/source revision/mode.

### Phase 3

Implementation is in progress. UAPI v2 provides standard Phase IV node MAC derivation, router/endnode hello generation and parsing, periodic hello transmission, per-interface adjacency state, 3.1x listen-time expiry, designated-router election, extended counters and `dnctl adjacencies`.

Router-router adjacencies begin INIT and become UP when the peer router hello lists the local router with the expected priority. Loss of that listing returns an UP adjacency to INIT; listen expiry removes it. Router nodes accept valid endnode hellos as UP. Endnodes select one router adjacency. Same-area rules apply except that Level 2 routers may form Level 2 adjacencies across areas. Router admission is capped at 33 per interface and retains the highest `(priority, node address)` set.

The E1 self-to-self harness proves L1 router hello exchange, INIT/UP behavior, listener expiry, module restart/recovery, designated-router behavior, protocol source MACs, DECnet unicast receive-filter ownership, and survival of a post-install primary device-MAC change. DN71 wins the equal-priority designated-router election over DN70. The harness deliberately uses hardware MACs different from DECnet node MACs and verifies raw unicast delivery to the DECnet address after the hardware address changes.

The latest SoP review found two independent-peer interoperability gaps that the self-to-self harness had hidden. First, DECnet Ethernet carries a two-byte little-endian Routing Layer payload length immediately after EtherType `0x6003`; both pinned Route20 and PyDECnet use that field, while the Linux implementation and raw lab generator had emitted/consumed the Routing Layer payload directly. The implementation now emits, validates and strips that length field, ignores trailing Ethernet padding through the declared length, and unit coverage includes valid/truncated/oversized length cases. The raw lab frame generator now emits the same standard framing.

Second, a Level 2 router must participate in the All-Level-2-Routers multicast group `09-00-2B-02-00-00`. The pinned Route20 reference both subscribes/sends for Level 2 operation. The Linux implementation now owns that multicast filter transactionally for Level 2 routers, rolls prior filters back if installation fails, removes it symmetrically at teardown, and sends periodic router hellos to both All-Routers and All-Level-2-Routers. These corrections reset the SoP sequence.

The previous exact-head acceptance attempt before these corrections had green native build and continuity gates but exposed a minimal-image certificate bootstrap failure during E1 image construction. That image defect was corrected before this review. Exact-head acceptance for the current framing/Level-2 corrections has not yet been claimed.

## Test addressing

Ordinary lab addressing is centralized in `tests/lab/test-addresses.env`: area 31, nodes 70 through 79, names DN70 through DN79. Larger and inter-area tests must extend this deliberately through configuration.

## Resume point

`main` contains the Phase 1/2 foundation, the Phase 3 E1 harness, minimal-image trust bootstrap, explicit DECnet unicast-filter ownership, `init_net` isolation, standard DECnet Ethernet payload-length framing, and Level 2 multicast participation. The SoP sequence is reset by the latest Ethernet corrections. No Phase 3 completion claim is valid until the new exact tree completes three clean full reviews and the required acceptance/interoperability evidence is green.

## Next action

Run three consecutive clean complete SoP passes on the exact latest `main` tree. Any defect or edit restarts the sequence. Then invoke the owner-only acceptance dispatcher and require green repository policy, continuity, reference, native x86_64/aarch64 build and E1 VM gates at that exact revision. Add and run live Phase 3 interoperability against the pinned Route20 and PyDECnet forks, including standard two-byte Ethernet length framing and Level 2 multicast behavior. Only after those gates are green may Phase 4 routing work begin. Continue directly on current `main`.
