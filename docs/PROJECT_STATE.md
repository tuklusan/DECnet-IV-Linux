# Project State

This is the continuity record for DECnet-IV-Linux. Repository state is authoritative. Start at `docs/HANDOVER.md`, then read this file and `docs/ROADMAP.md` completely before changing code.

## Goal

Build a complete native DECnet Phase IV stack for maintained Linux, delivered primarily as an out-of-tree kernel module plus the useful DECnet/Linux userspace environment, with reproducible x86_64/aarch64 VM images and independent interoperability.

## Non-negotiable architecture

- Distribution base: Ubuntu Base 26.04.1 LTS, pinned official amd64 and arm64 rootfs tarballs.
- Kernel delivery: fresh out-of-tree module; avoid a permanent kernel fork and do not revive the removed legacy Linux DECnet kernel stack.
- Kernel scope: native Ethernet, endnode/Level 1/Level 2 routing, NSP, sockets/UAPI, Session Control support, NICE/NML hooks/state and DDCMP.
- Core routing, NSP and DDCMP state machines remain in kernel space.
- Userspace target: `ncp`, `sethost`/`dnlogin`, DAP/FAL/RMS tools, PHONE, mail, task/object access, daemons, libraries, diagnostics and administration tools.
- Required CPU targets: x86_64 and aarch64.
- Primary VM artifact: QCOW2, with RAW and conversion formats at release time.

## Reference and licensing policy

Preferred project references are `tuklusan/Route20`, `tuklusan/pydecnet`, `tuklusan/LinuxDECnet` and `tuklusan/simh`. Pin exact SHAs when a reference becomes a gate. Upstreams are comparison sources only.

Every reference is independently licensed. Verify compatibility before copying or adapting source and preserve required notices. If reuse is unclear or incompatible, use observable protocol behavior and implement independently.

Pinned automated references live in `tests/reference/refs.env`. Self-to-self success is never sufficient for final interoperability claims. Exercise the stack against the pinned Route20 and PyDECnet forks, and later against SIMH-hosted real DEC operating systems.

## Execution order

`docs/ROADMAP.md` is canonical:

0. continuity, repository/reference/licensing/SoP discipline;
1. buildable UAPI/module/control utility on x86_64 and aarch64;
2. reproducible Ubuntu Base image and two-VM native Ethernet lab;
3. Ethernet initialization and adjacency;
4. endnode, Level 1 and Level 2 routing;
5. NSP and DECnet sockets;
6. Session Control and NICE/NML;
7. complete useful DECnet/Linux userspace as dependencies become ready;
8. DDCMP;
9. mixed Ethernet/DDCMP routing and applications;
10. scale, portability, real DEC peers, physical mixed-CPU testing and release images.

A later phase never removes an earlier acceptance gate.

## Test addressing

- Single source: `tests/lab/test-addresses.env`.
- Default area: 31.
- Default nodes: 70 through 79.
- Default names: DN70 through DN79.
- Larger tests may extend the node range; inter-area tests introduce another configurable area deliberately.

## Test lab rules

- Primary acceptance nodes are separate VMs, not containers or namespaces sharing one kernel.
- Linux bridges provide raw native Ethernet LANs; DECnet acceptance traffic stays on isolated native DECnet media.
- Scale deliberately from 2 to 4, 8 and 16 independent VMs with routed topologies.
- Required CPU cases include x86_64/x86_64, aarch64/aarch64 and both mixed directions.
- Fault and stress work includes deterministic loss, duplication, delay/reordering where meaningful, link/circuit failure, restart, convergence, connection churn, long-duration traffic and resource/lifetime failures.
- Required mixed-media path eventually includes `Ethernet -> router -> DDCMP -> router -> Ethernet`.

## Repository discipline

- Work on feature branches based on the exact maintained `main` commit. Promote only an exact green reviewed commit to `main`; do not develop directly on the integration line.
- Historical working refs were reconciled into `main` at commit `b51618cbf49ae43b223d3dcd15f156086fea41dc`; they are aliases only and must not carry divergent work.
- Every substantive commit updates this file in the same commit.
- `tools/project_state_gate.py` enforces continuity requirements.
- Keep commits atomic and run applicable static/unit/reference gates before advancing work.
- Generated VM evidence stays under ignored `tests/lab/artifacts/`; do not commit generated images, captures or logs.
- Runner use is demand-driven. All repository workflows are manual-dispatch only and share one x64 plus one arm64 repository-wide concurrency slot. Do not redesign this unless a demonstrated blocker requires it.
- GitHub-hosted runner disks and processes are ephemeral. State required across jobs must be explicit repository data or retained workflow artifacts.

## SoP delivery rule

1. Read the complete latest disk copy byte-for-byte, line-by-line, with no truncation; find and fix defects/gaps.
2. Any fix resets the pass to Step 1 on the new latest disk copy.
3. Delivery requires three consecutive clean complete Step-1 passes.
4. Any later change resets Step 1.

Automated tests, diffs, excerpts or prior reviews do not replace this rule.

## Phase 1 status

Complete foundation retained on `main`: versioned UAPI, `decnet_iv.ko`, configurable 31.70/DN70 identity, `/dev/decnet_iv`, DEC DNA Routing EtherType receive registration/counters, `dnctl`, centralized test addressing, unit address tests and native x86_64/aarch64 build gates.

## Phase 2 status

Complete foundation retained on `main`: pinned Ubuntu Base 26.04.1 amd64/arm64 rootfs tarballs, apt snapshot `20260915T000000Z`, deterministic image assembly, exact guest kernel/module build, direct QEMU kernel/initrd boot, two independent one-NIC VMs, raw EtherType `0x6003` exchange, packet capture and serial evidence.

All workflows are manual-dispatch. Jobs share the repository-wide x64/arm64 concurrency slots. The VM lab checkpoints the base QCOW2, portable node overlays, exact kernel/initrd, checksums, session metadata, logs and capture as resumable artifacts; a resume is accepted only for the same source commit and architecture.

The Phase 2 smoke test deliberately remains a low-level EtherType receive gate. It sends arbitrary unicast payloads and is not a Phase 3 adjacency acceptance test. Since Phase 3 router mode now emits hellos automatically, the smoke service explicitly loads both test nodes as endnodes; endnodes do not subscribe to the all-routers multicast group, so automatic Phase 3 hello traffic cannot satisfy the retained receive-counter gate.

The active E1 feature branch preserves that gate as `phase2` mode. New checkpoints record the selected lab mode; old checkpoints without a mode remain valid for `phase2` only.

## Phase 3 status

Phase 3 implementation is in progress. The current slice adds independent DECnet Ethernet wire helpers and UAPI version 2, including standard Phase IV node MAC derivation, router and endnode hello parsing/generation, periodic hello emission, per-interface adjacency state, 3.1x LAN listen-time expiry, and `dnctl adjacencies`/extended counters.

Router-router adjacencies begin in INIT and become UP when the peer router hello lists the local router with the expected priority. A newly created adjacency may therefore pass through INIT and reach UP within the same hello-processing cycle if that first hello already contains the local router, matching the pinned Route20 behavior. Loss of the listing returns an UP adjacency to INIT; listener expiry removes it. Router nodes accept valid endnode hellos as UP. Endnodes accept router hellos as their router adjacency. Same-area rules apply except for Level 2 router peers, which may be out of area. Router priority and node address drive designated-router choice after the five-second holdoff; the designated router also sends its router hello to the all-endnodes multicast address.

The wire implementation is independent and was cross-checked against pinned Route20 `b94115b2615c6463d1f006924ceeadde8e2d4367` and PyDECnet `a7194be8d72dea6f9eb4f77083f056f53e80df58` behavior. Unit vectors cover node MAC encoding, exact router hello bytes, router-list entries, endnode hello layout/test data, padding/malformed input, INIT/UP two-way decisions and listen-time arithmetic.

Local development evidence for this slice: userspace and unit tests build with both GCC and Clang; the Phase 3 vectors pass; the module builds cleanly with `W=1` against Linux 6.12.96 headers. That build also exposed and fixed a pre-existing portability gap by explicitly including the header that defines `MODULE_ALIAS_NETPROTO`.

The first restarted complete SoP review found two additional Phase 3 defects: the router-list maximum was incorrectly 35 instead of the 33-entry architectural/reference limit (`NBRA=33` in the pinned Route20 fork, consistent with the pinned PyDECnet E-list bound), and the shared hello builders did not reject a null output buffer before writing. Both are corrected with unit coverage. The same pass found the kernel-module README still described only the bootstrap milestone; it is synchronized with UAPI version 2 and the active Phase 3 scope.

The following restarted review found a cross-phase regression: the retained Phase 2 VM smoke test could pass from automatically generated Phase 3 router hellos even if its deliberate raw-frame exchange failed. The smoke nodes now load explicitly as endnodes, isolating the old EtherType receive gate from Phase 3 multicast hello traffic.

The next adversarial review found that correcting the serialized router-list bound alone was insufficient: the kernel could still retain more than 33 router adjacencies on one interface and silently omit the excess from its hello, creating asymmetric adjacency state. Router admission is now capped per interface at 33. When the set is full, a new router replaces only the lowest `(priority, node address)` entry, matching the pinned reference selection rule; otherwise it is ignored. That correction is the reviewed `main` baseline at `7070768397230b990bad7703a8c29a9501e5433b`.

The active `phase3-e1-adjacency` feature branch adds the E1 self-to-self acceptance harness without claiming a runtime pass. It makes the two-node workflow select either the retained `phase2` gate or the new `e1` gate. E1 requires both routers to reach UP with nonzero hello TX/RX, observable INIT evidence from at least one side during initial convergence, one router to unload and remain silent beyond the listen timer, the peer adjacency to disappear, observable INIT evidence from at least one side during restart convergence, both routers to recover UP, and packet-capture evidence for all-routers traffic, designated-router all-endnodes traffic and both DECnet source MACs. Checkpoint mode compatibility is explicit and legacy Phase 2 checkpoints remain resumable only in `phase2` mode.

An adversarial E1 harness review found that the observing router's expiry/recovery loop allowed only 40 seconds while the silent router's scripted silence plus maximum recovery wait could approach 39 seconds. The observation window is widened to 60 seconds so scheduler and boot jitter cannot create a false failure at the boundary.

A subsequent wire-evidence review found that merely seeing some all-endnodes traffic would not prove correct designated-router election. With equal priority, DN71 must win over DN70, so E1 now requires all-routers hellos from both DECnet source MACs, at least one all-endnodes hello from DN71, and zero all-endnodes hellos from DN70.

A further source-address review found the original E1 VM NICs were themselves configured with the DECnet node MACs, making the source-MAC assertion circular. E1 now assigns distinct emulated NIC MACs, requires protocol hello multicast frames to use only the AA-00-04 DECnet source addresses, and keeps the device addresses visibly distinct in capture.

The next receive-path review found that multicast hello success still did not prove the per-device DECnet unicast filter installed by `dev_uc_add()`. E1 now sends raw EtherType `0x6003` probes in each direction to the peer's DECnet node MAC while the hardware NIC uses a different address. Each guest compares its non-hello receive counter before and after those probes, and the host capture independently requires hardware-source unicast probes in both directions. This also fixes the earlier source-MAC check so those deliberate raw probes are not mistaken for kernel-generated hello traffic.

The first complete review of that unicast proof found a synchronization race: one guest could finish a three-packet burst before the peer recorded its receive baseline, causing a false failure despite working filters. The probes are now overlapping ten-second streams, while acceptance still requires at least three post-baseline receives. The canonical Phase 3 roadmap is also synchronized to make unicast delivery to a protocol node MAC distinct from the device MAC an explicit E1 requirement.

No native VM or live independent-peer runtime claim is made yet for the E1 branch. The E1 branch must complete the SoP gate before hosted execution, then pass the required cheap build/reference checks and native x86_64/aarch64 E1 runs before promotion.

## Resume point

`main` remains at reviewed Phase 3 baseline `7070768397230b990bad7703a8c29a9501e5433b`. Active work is on feature branch `phase3-e1-adjacency`, which contains the E1 two-router adjacency acceptance harness while preserving the Phase 2 smoke gate and legacy checkpoint behavior. The harness now covers hello traffic, INIT evidence during convergence, both adjacencies reaching UP, listener expiry, module restart/recovery, designated-router multicast behavior, kernel-derived DECnet hello source addressing and DECnet unicast receive-filter delivery; it has not yet been promoted or given a hosted runtime pass.

## Next action

Restart the SoP sequence from the exact latest `phase3-e1-adjacency` repository copy and require three consecutive clean complete passes. Any defect found resets the sequence. After that exact branch commit is SoP-clean, run only the needed build/reference gates and the E1 two-node native VM mode on x86_64 and aarch64. Promote the exact tested commit to `main` only if every required check is green. Then add live interoperability against the pinned Route20 and PyDECnet forks before beginning Phase 4 routing work.
