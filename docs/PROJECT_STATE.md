# Project State

This is the continuity record for DECnet-IV-Linux. A fresh session should read this file first, then execute `Next action` without reconstructing the project from chat history.

## Goal

Build a minimal maintained Linux distribution with a fresh native DECnet Phase IV implementation delivered primarily as an out-of-tree kernel module, familiar DECnet user-mode tools, and reproducible x86_64/aarch64 VM images.

## Non-negotiable architecture

- Reference distribution: Alpine Linux 3.24 initially using `linux-virt`.
- Kernel delivery: out-of-tree module; avoid a permanent kernel fork.
- Implementation base: fresh code informed by DECnet specifications and independent interoperability behavior, not the removed/legacy Linux DECnet kernel stack.
- Kernel scope as the project matures: Ethernet, Phase IV routing, NSP, DDCMP, socket/UAPI plumbing, timers, forwarding and management hooks.
- Userspace target: familiar DECnet/Linux command experience for `ncp`, `sethost`, `dncopy`, `phone` and related tools.
- Required CPU targets: x86_64 and aarch64.
- Primary VM artifact: QCOW2, with RAW and conversion formats at release time.

## External conformance

The implementation must be exercised independently against:

1. Route20 for build and live routing/interoperability behavior.
2. PyDECnet for its protocol behavior, packet vectors, test suite, Ethernet interoperability and DDCMP interoperability.
3. DECnet protocol documentation plus useful supplementary protocol notes carried with PyDECnet.
4. Later, SIMH-hosted DEC operating systems for application-level validation.

Route20 is a behavioral/reference peer. Its source license is not assumed suitable for direct incorporation into the kernel module.

## Execution order

`docs/ROADMAP.md` is the canonical ordered task list. The phase order is:

0. continuity, repository policy and reference discipline;
1. buildable UAPI/module/control utility on x86_64 and aarch64;
2. reproducible Alpine image and two-VM Ethernet lab;
3. Ethernet initialization and adjacency;
4. endnode, Level 1 and Level 2 routing;
5. NSP and DECnet sockets;
6. Session Control and NICE/NML;
7. familiar user-mode tools as their protocols become ready;
8. DDCMP;
9. mixed Ethernet/DDCMP routing and applications;
10. scale to 16 nodes, physical mixed-CPU testing and release images.

A later phase never removes an earlier acceptance gate.

## Test addressing

- Single source: `tests/lab/test-addresses.env`.
- Default area: 31.
- Default nodes: 70 through 79.
- Default names: DN70 through DN79.
- Larger tests may extend the node range; inter-area tests introduce another configurable area deliberately.

## Test lab rules

- Primary acceptance nodes are separate tiny VMs, not containers sharing one kernel.
- Linux bridges provide raw Ethernet LANs.
- Failure artifacts include topology, addressing, packet capture, kernel logs, DECnet counters and fault-injection seed where applicable.
- Required CPU matrix: x86_64/x86_64, aarch64/aarch64 and mixed x86_64/aarch64.
- Physical lab target: at least two x86_64 and two aarch64 nodes, managed switch, independent management path and mirror capture.
- Required mixed-media path eventually includes Ethernet -> router -> DDCMP -> router -> Ethernet.

## Continuity and promotion gates

- Every substantive commit must update this file in the same commit.
- `tools/project_state_gate.py` enforces that requirement per commit in CI and the local pre-commit hook.
- This file must keep non-empty `Resume point` and `Next action` sections.
- Workflows carry short comments describing what each gate proves.
- Substantive automated work is prepared on a working branch, gates run there, and `main` is advanced only after the branch is green. This gives our project workflow a pre-promotion hard gate even while repository administration is not available through the current connector.

## Phase 1 implementation state

A Phase 1 change is prepared containing:

- `include/uapi/linux/decnet_iv.h`: UAPI version 1, DECnet address encoding and bootstrap ioctls;
- `kernel/decnet/decnet_iv_main.c`: loadable module, default 31.70/DN70 identity, `/dev/decnet_iv`, Routing Layer EtherType receive registration and counters;
- `userspace/dnctl`: diagnostic identity/statistics control utility;
- `tests/unit/test_uapi.c`: address encoding checks including 31.70 = 0x7c46 and 31.79 = 0x7c4f;
- native x86_64/ARM64 build workflow;
- the centralized lab address configuration and ordered roadmap.

Local verification before promotion: userspace builds with warnings as errors, UAPI tests pass, and `decnet_iv.ko` builds against Linux 6.12 headers.

## Resume point

Phase 0 is complete enough to proceed. The first real kernel/userspace bootstrap has been written and verified locally, but must be promoted through the working-branch CI gates before `main` is advanced. The module is intentionally only a receive/control bootstrap; it does not yet claim adjacency, routing, NSP, Session Control or DDCMP functionality.

## Next action

Promote the Phase 1 bootstrap through a working branch, inspect both x86_64 and aarch64 build results, fix any CI-only failures, then advance `main`. Immediately after that, add pinned external-reference baseline gates: Route20 must build, PyDECnet's upstream unit suite must run, and protocol-layer interoperability gates are added as each corresponding layer becomes functional. Then begin Phase 2: reproducible Alpine image plus the DN70/DN71 two-VM raw-Ethernet lab.
