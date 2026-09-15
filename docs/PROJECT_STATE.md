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

Pinned reference revisions live in `tests/reference/refs.env`. Current pins are Route20 `b94115b2615c6463d1f006924ceeadde8e2d4367`, PyDECnet behavior/live reference `a7194be8d72dea6f9eb4f77083f056f53e80df58`, PyDECnet test reference `9a844987bf3a1450632dee8d37e60a23a453bad3`, LinuxDECnet comparison reference `ff39eef045d1e4b7b72a3d40111e89c07a473398`, and SIMH reference `5b73b1032b52d19bf80752ea4d9cbbdc92e7b5e0`. Self-to-self success is never sufficient for final interoperability claims.

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

- This is a single-developer repository. Work directly on the current `main` HEAD.
- Do not create pull requests or development branches for ordinary project work. Historical refs may remain only as inert aliases and must not carry divergent work.
- Preserve useful code by fast-forwarding or committing it directly to `main`; do not require merge ceremonies.
- Every substantive commit updates this file in the same commit.
- `tools/project_state_gate.py` enforces continuity requirements.
- `tools/repo_policy.py` uses Unicode-normalized, case-insensitive whole-token matching for the configured forbidden-word set. It checks tracked and staged paths/content, commit metadata/history, refs, local Git configuration, selected GitHub event metadata and collaborator logins.
- Local repository hooks include pre-commit, commit-message and pre-push policy checks when `tools/install-hooks.sh` has enabled `.githooks`.
- The repository-policy workflow is the sole automatic workflow exception: it runs on pushes and relevant GitHub metadata events as well as manual dispatch. Other build, reference, continuity and VM workflows remain manual-dispatch only.
- Keep commits atomic and run applicable static/unit/reference gates before advancing work.
- Generated VM evidence stays under ignored `tests/lab/artifacts/`; do not commit generated images, captures or logs.
- Runner use is demand-driven except for the automatic repository-policy gate. Runner jobs share one x64 plus one arm64 repository-wide concurrency slot.
- Hosted runner disks and processes are ephemeral. State required across jobs must be explicit repository data or retained workflow artifacts.

## SoP delivery rule

1. Read the complete latest disk copy byte-for-byte, line-by-line, with no truncation; find and fix defects/gaps.
2. Any fix resets the pass to Step 1 on the new latest disk copy.
3. Delivery requires three consecutive clean complete Step-1 passes.
4. Any later change resets Step 1.

Automated tests, diffs, excerpts or prior reviews do not replace this rule.

## Phase 1 status

Complete foundation retained on `main`: versioned UAPI, `decnet_iv.ko`, configurable 31.70/DN70 identity, `/dev/decnet_iv`, DEC DNA Routing Layer EtherType receive registration/counters, `dnctl`, centralized test addressing, unit address tests and native x86_64/aarch64 build gates.

## Phase 2 status

Complete foundation retained on `main`: pinned Ubuntu Base 26.04.1 amd64/arm64 rootfs tarballs, apt snapshot `20260915T000000Z`, deterministic image assembly, exact guest kernel/module build, direct QEMU kernel/initrd boot, two independent one-NIC VMs, raw EtherType `0x6003` exchange, packet capture and serial evidence.

All non-policy workflows are manual-dispatch. Jobs share the repository-wide x64/arm64 concurrency slots. The VM lab checkpoints the base QCOW2, portable node overlays, exact kernel/initrd, checksums, session metadata, logs and capture as resumable artifacts; a resume is accepted only for the same source commit and architecture.

The Phase 2 smoke test remains a low-level EtherType receive gate. It sends deliberate raw unicast payloads and is not a Phase 3 adjacency acceptance test. Smoke nodes load explicitly as endnodes so automatic router hello traffic cannot satisfy the retained counter gate. The two-node workflow preserves this as `phase2` mode; new checkpoints record the selected mode and old checkpoints without a mode remain valid for `phase2` only.

## Phase 3 status

Phase 3 implementation is in progress on `main`. UAPI version 2 adds standard Phase IV node MAC derivation, router/endnode hello parsing and generation, periodic hello emission, per-interface adjacency state and 3.1x LAN listen-time expiry, designated-router selection, extended counters and `dnctl adjacencies`.

Router-router adjacencies begin in INIT and become UP when the peer router hello lists the local router with the expected priority. A first hello may therefore create and promote an adjacency within one receive cycle. Loss of the listing returns an UP adjacency to INIT; listener expiry removes it. Router nodes accept valid endnode hellos as UP. Endnodes accept router hellos as their router adjacency. Same-area rules apply except for Level 2 router peers, which may be out of area. Router priority and node address drive designated-router choice after the five-second holdoff; the designated router also sends its router hello to the all-endnodes multicast address.

The wire implementation was independently cross-checked against the pinned Route20 and PyDECnet behavior. Unit vectors cover node MAC encoding, exact router hello bytes, router-list entries, the 33-router architectural limit, endnode hello layout/test data, padding/malformed input, INIT/UP decisions and listen-time arithmetic. Router admission is capped per interface at 33; when full, a new router replaces only the lowest `(priority, node address)` entry.

The E1 self-to-self acceptance harness is now on `main`. It selects either the retained `phase2` gate or the `e1` gate. E1 requires both routers to reach UP with nonzero hello TX/RX, observable INIT evidence from at least one side during initial convergence, one router to unload and remain silent beyond the listen timer, the peer adjacency to disappear, restart convergence, both routers to recover UP, and packet-capture evidence for all-routers traffic, designated-router all-endnodes traffic and both DECnet source MACs.

E1 deliberately gives each emulated NIC a hardware MAC different from its DECnet node MAC. Kernel-generated hello frames must use the protocol-derived AA-00-04 source addresses. Raw unicast probes are sent in both directions to the DECnet node MAC while the NIC hardware address differs; each guest checks a non-hello receive-counter increase and host capture verifies the probes existed in both directions. Probe streams overlap long enough to remove the earlier baseline race.

With equal priority, DN71 must win designated-router election over DN70. To make the whole-capture assertion independent of arbitrary VM boot skew, DN70 temporarily boots as an endnode until it has received DN71's designated-router hello, unloads the module, then starts as an L1 router. Its router holdoff therefore begins only after DN71 presence is established. E1 then requires all-routers hello evidence from both protocol MACs, all-endnodes hello evidence from DN71 and none from DN70.

The E1 code history through commit `ea5f8727518926bc113d1d462843b5be9730ebf1` was fast-forwarded intact onto `main` when the project switched to direct-current-HEAD development. No runtime claim is implied by that fast-forward. Hosted build/reference/native E1 evidence is still required.

A restarted SoP review after the direct-main policy change found that `tests/reference/refs.env` had lost the preferred LinuxDECnet and SIMH fork pins. The exact current fork revisions are restored and their roles documented.

The next restarted review found that adjacency state was keyed by network-interface index but the netdevice notifier handled registration only. A removed interface could therefore leave an adjacency alive until its listen timer expired, and a quickly reused interface index could inherit stale adjacency/DR state. `NETDEV_UNREGISTER` now drops every adjacency belonging to that interface immediately under the adjacency lock.

The following complete review found that Ethernet receive-filter installation failures during `NETDEV_REGISTER` were logged but reported as notifier success. That allowed module initialization or later interface registration to continue with a DECnet circuit that could not reliably receive its protocol unicast/multicast addresses. The notifier now converts filter errors to notifier errors, allowing the kernel's notifier registration/rollback path to reject the partial setup.

The next review found a namespace and rollback mismatch: a global netdevice notifier programmed DECnet receive filters on interfaces in every network namespace while hello transmission and address updates were intentionally limited to `init_net`. Successful replayed interfaces also depended on synthesized unregister events for rollback, but those events did not remove the installed filters. Registration is now scoped to `init_net` with the per-netns notifier API, and `NETDEV_UNREGISTER` removes receive filters before dropping per-interface adjacencies. The kernel's synthesized unregister events therefore unwind successful replay entries on registration failure and module unload without touching unrelated namespaces.

The restarted review then found that the EtherType packet handler remained global even after notifier/filter lifetime was restricted to `init_net`. A DECnet frame accepted by an interface in another namespace could still update global counters or adjacency state, with interface-index collisions contaminating the `init_net` circuit state. The receive path now rejects non-`init_net` devices before accounting or parsing.

The next full pass found that receive-filter ownership depended on whether the DECnet node MAC happened to equal the device primary MAC at the instant filters were installed. A later primary-MAC change could therefore either remove DECnet receive coverage or make teardown unable to know whether a secondary filter reference existed. Each attached Ethernet device now owns one explicit `dev_uc` reference for the DECnet node MAC regardless of the current primary MAC, and address changes transfer that owned reference transactionally. This makes DECnet receive coverage and teardown independent of `NETDEV_CHANGEADDR`.

The following complete review found that E1 proved delivery when the device MAC merely started different from the DECnet MAC, but did not exercise the specific lifetime case corrected above: a primary device-MAC change after DECnet had installed its owned receive filter. E1 now changes each guest NIC to a second deterministic hardware MAC while the module remains loaded, requires a fresh peer hello and an UP adjacency after that change, sends the raw-unicast probe stream from that changed hardware MAC to the peer DECnet MAC, and verifies in host capture that protocol hellos still use only the DECnet source MAC. `docs/TEST_LAB.md` records the same acceptance behavior. This correction resets the SoP sequence.

An infrastructure hold then strengthened the repository word-policy gate. The matcher now uses case-insensitive whole-token semantics, includes the newly requested configured entries while retaining the prior extra blocked entry, self-checks both text and byte matching, scans local refs/configuration as well as repository/history/event data, adds a pre-push hook, and makes the repository-policy workflow automatic for pushes and relevant GitHub metadata events. GitHub currently reports no repository ruleset, and the available repository connection does not expose ruleset administration, so a server-side pre-receive rule cannot be installed from this session. The local hooks plus automatic policy workflow are the enforceable repository mechanisms available here. This infrastructure change resets the SoP sequence.

## Resume point

`main` is the only active development line and contains the E1 two-router adjacency acceptance harness, including expiry/restart, designated-router, protocol-source-MAC, DECnet-unicast-filter and post-install primary-MAC-change evidence. Protocol work is intentionally held after the repository-policy infrastructure update. Netdevice filters, hello transmission, address updates and EtherType receive processing are restricted to `init_net`, and every attached Ethernet device owns an explicit DECnet unicast-filter reference independent of its primary MAC. The SoP sequence is reset.

## Next action

When protocol work resumes, start the SoP sequence from the exact current `main` HEAD and require three consecutive clean complete passes. Any defect or later edit resets the sequence. Then run the required cheap build/reference gates and native E1 two-node VM mode on x86_64 and aarch64 against that exact HEAD. If all required evidence is green, add live interoperability against the pinned Route20 and PyDECnet forks before beginning Phase 4 routing work. Continue all work directly on current `main` HEAD.