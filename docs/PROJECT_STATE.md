# Project State

This is the authoritative continuity record for DECnet-IV-Linux. Read `docs/HANDOVER.md`, this file, `docs/ROADMAP.md`, `docs/ARCHITECTURE.md`, `docs/TEST_LAB.md` and `docs/PRE_PRODUCTION_TEST.md` before changing protocol, image or acceptance behavior.

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
- Policy token boundaries treat Unicode letters/digits as word characters and punctuation or underscore as separators. This preserves the short-token false-positive protection inside ordinary words while rejecting identifier-style uses separated by underscores.
- The repository-policy workflow is the sole automatic workflow exception. Build, continuity, reference and VM workflows are demand-driven.
- Workflow-level and job-level concurrency groups use `queue: max` with cancellation disabled. This prevents an older pending policy or acceptance run from being silently replaced by a newer run while preserving the one-x64/one-arm64 execution ceiling; the platform queue limit still applies.
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

Foundation complete: pinned Ubuntu Base 26.04.1 amd64/arm64 rootfs files, pinned package snapshot `20260915T000000Z`, deterministic ext4/QCOW2 assembly, exact guest kernel/module build, direct kernel/initrd boot, two independent one-NIC VMs, packet capture and serial evidence. Ubuntu Base does not initially contain usable certificate trust for the snapshot service, so the image builder bootstraps only the signed `ca-certificates` package with TLS peer verification temporarily disabled, refreshes package-owned trust, and then requires an ordinary verified snapshot update before installing the remaining image packages. Repository signatures continue to authenticate snapshot metadata and packages during the bootstrap step.

The image build requires a 4 GiB sparse root filesystem. The 2 GiB predecessor exhausted the ext4 filesystem while unpacking the arm64 virtual-kernel module package after downloading the pinned package set; the larger sparse backing size preserves the small QCOW2-on-disk behavior while providing sufficient installation workspace.

The retained `phase2` smoke gate sends deliberately generated DECnet Routing Layer Ethernet frames between two endnodes. VM checkpoints contain the base image, portable overlays, exact kernel/initrd, checksums, session metadata, logs and capture and may resume only against the matching architecture/source revision/mode.

### Phase 3

Implementation is in progress. UAPI v2 provides standard Phase IV node MAC derivation, router/endnode hello generation and parsing, periodic hello transmission, per-interface adjacency state, 3.1x listen-time expiry, designated-router election, extended counters and `dnctl adjacencies`.

Router-router adjacencies begin INIT and become UP when the peer router hello lists the local router with the expected priority. Loss of that listing returns an UP adjacency to INIT; listen expiry removes it. Router nodes accept valid endnode hellos as UP. Endnodes select one router adjacency. Same-area rules apply except that Level 2 routers may form Level 2 adjacencies across areas. Router admission is capped at 33 per interface and retains the highest `(priority, node address)` set.

The E1 self-to-self harness proves L1 router hello exchange, INIT/UP behavior, listener expiry, module restart/recovery, designated-router behavior, protocol source MACs, DECnet unicast receive-filter ownership, and survival of a post-install primary device-MAC change. DN71 wins the equal-priority designated-router election over DN70. The harness deliberately uses hardware MACs different from DECnet node MACs and verifies raw unicast delivery to the DECnet address after the hardware address changes.

The latest protocol reviews found independent-peer interoperability gaps that self-to-self testing had hidden. DECnet Ethernet carries a two-byte little-endian Routing Layer payload length immediately after EtherType `0x6003`; the Linux implementation now emits, validates and strips that field and ignores Ethernet padding beyond the declared length. A Level 2 router must also participate in the All-Level-2-Routers multicast group `09-00-2B-02-00-00`; the implementation now owns that filter transactionally and sends Level 2 router hellos to it.

A later full-tree review found a runtime identity-change race: hello validation could read the old local address before `DNIV_IOC_SET_IDENTITY`, then update adjacency state after the address transaction had cleared it. Hello validation and adjacency mutation now share the adjacency lock with local-address publication/clear, so every received hello is evaluated wholly against one identity.

Repository review then found two policy/CI scheduling gaps. Whole-token matching originally treated underscore as a word character, permitting identifier-style configured tokens between underscores; the matcher now treats underscore as a separator while preserving Unicode-alphanumeric embedding protection. Workflow-level concurrency also originally used the platform's single-pending default, under which a newer pending run can replace an older one. All workflow-level concurrency groups now use `queue: max`, matching the already-queued job-level groups.

A subsequent full-tree review found that hello processing relied on hardware multicast filtering and did not verify the Ethernet destination in software. The receive path now validates the destination against the local DECnet unicast address and role-appropriate multicast groups under the same adjacency lock as runtime identity changes. Unit vectors cover endnode, Level 1 and Level 2 destination acceptance and rejection.

Three consecutive clean complete SoP passes were reached on `e59afc1cdee594417137f21a5ea3f0ebb72807eb`, after which exact-head acceptance was dispatched. Repository policy, continuity, native x86_64/aarch64 build, Route20 build and the pinned PyDECnet unit baseline were green. The arm64 E1 image build then exposed the old 2 GiB image-workspace limit; the root image floor is now 4 GiB. Every later image, protocol, policy, workflow or acceptance correction resets the SoP sequence; evidence from earlier revisions does not carry forward.

## Test addressing

Ordinary lab addressing is centralized in `tests/lab/test-addresses.env`: area 31, nodes 70 through 79, names DN70 through DN79. Larger and inter-area tests must extend this deliberately through configuration.

## Pre-production acceptance procedure

`docs/PRE_PRODUCTION_TEST.md` is the consolidated release-gate procedure. It de-duplicates project E0-E4/D0-D5 coverage with protocol-relevant tests and behavior from the pinned references and adds Linux-kernel-specific lifecycle, concurrency, malformed-input, resource, evidence, security, stress, endurance and recovery coverage. Upstream-native tests still run at their exact pins as reference-source health where applicable.

A forensic review of the first consolidated procedure found missing production classes that are now explicit blockers: SMP/multi-vCPU races; 32-bit compatibility UAPI; network-namespace isolation and device migration; nonlinear/fragmented skb receive paths; exact router/adjacency saturation and replacement boundaries; filter-transaction failpoint rollback; timer and designated-router boundary tests; boot/late-NIC ordering; evidence/harness false-green tests; image-build storage/download/snapshot/conversion failures; second Ethernet driver/offload/MTU coverage; adversarial fairness; explicit 72-hour and 7-day endurance tiers; and long quiet periods as well as busy faults.

The same forensic inventory found a previously unaccounted native LinuxDECnet test, `dnprogs/libvaxdata/src/test.c`, which exercises VAX integer/floating conversion behavior. It is now required as PP-00 reference health and becomes PP-07 blocking evidence when VAX/RMS data conversion is claimed. The exact pinned SIMH makefile also states that normal builds run available per-simulator tests; the procedure now requires the selected DEC-host target to be built with those tests enabled and the target-specific transcript retained.

Documentation-only requirements do not count as green. A required test must be automated or executed manually/physically with complete evidence. Missing required evidence invalidates a production acceptance run rather than producing a warning-only pass.

This forensic correction resets the SoP sequence. No review or acceptance result from the predecessor procedure carries forward.

## Resume point

`main` contains the Phase 1/2 foundation, the Phase 3 E1 harness, signed-snapshot certificate bootstrap, a 4 GiB sparse image workspace, explicit DECnet unicast-filter ownership, `init_net` isolation, standard DECnet Ethernet payload-length framing, Level 2 multicast participation, serialized runtime identity-change/hello processing, role-aware hello destination validation, corrected whole-token policy boundaries, and non-replacing workflow/job concurrency queues. The consolidated pre-production procedure is being hardened on its test branch; no documentation-only change advances the protocol phase.

## Next action

On the exact latest pre-production-procedure candidate, complete three consecutive clean full-repository SoP passes after the forensic correction. Any defect or edit restarts the sequence. Do not promote the procedure until those passes are clean. Protocol work remains at Phase 3: exact-head acceptance and live interoperability against pinned Route20 and PyDECnet, including standard two-byte Ethernet length framing and Level 2 multicast behavior, remain required before Phase 4 routing work begins.
