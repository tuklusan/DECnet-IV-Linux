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

The implementation must be exercised independently against Route20 and PyDECnet, using DECnet protocol documentation and useful supplementary protocol notes carried with PyDECnet. Later add SIMH-hosted DEC operating systems for application-level validation.

Pinned revisions are stored in `tests/reference/refs.env`. Route20 is a behavioral/reference peer; its source license is not assumed suitable for direct incorporation into the kernel module.

The current PyDECnet reference is pinned for documentation, vectors and live interoperability. Its present tree has a pre-existing self-test contradiction in `Macaddr("1.24")` introduced by a July 2024 change: the code takes the hexadecimal path before the DECnet `area.node` path while the upstream test still requires `area.node`. The hard full-suite pin is therefore the immediately preceding revision. The suite is run unmodified; no tests are skipped or rewritten. Move the test pin forward when upstream fixes the contradiction.

## Execution order

`docs/ROADMAP.md` is the canonical ordered task list:

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
- Substantive automated work is prepared on a working branch, gates run there, and `main` is advanced only after the branch is green.

## Phase 1 status

Phase 1 is on `main` and green on both required CPU architectures. It contains UAPI version 1, `decnet_iv.ko`, default 31.70/DN70 identity, `/dev/decnet_iv`, DEC DNA Routing EtherType receive registration/counters, `dnctl`, centralized test addressing, unit address tests and native x86_64/ARM64 build gates.

The bootstrap does not yet claim adjacency, routing, NSP, Session Control or DDCMP functionality.

## External baseline status

Route20's pinned build passed. The first current-PyDECnet run executed 988 tests: 983 passed, 4 skipped and one upstream `Macaddr("1.24")` test errored because current code contradicts that same test. The baseline has been corrected to keep the current PyDECnet revision for live/docs reference and run the entire unmodified suite at the immediately preceding revision before that upstream regression.

## Resume point

Phase 1 is promoted and green. External baselines are on `work/reference-baselines`; Route20 passed, and the PyDECnet suite pin has just been corrected after diagnosing an upstream self-test regression. This corrected branch must pass all gates before promotion.

## Next action

Run the corrected external-reference gates. If green, fast-forward `main` to the tested commit. Then start Phase 2 on a fresh working branch: pin the official Alpine 3.24.1 tiny QCOW2 bases for x86_64 BIOS and aarch64 UEFI, build/install the exact `linux-virt` module plus `dnctl`, boot DN70 and DN71 as separate VMs on a raw Ethernet bridge, collect pcaps/logs, and prove bidirectional EtherType `0x6003` reception before implementing hello/adjacency logic.
