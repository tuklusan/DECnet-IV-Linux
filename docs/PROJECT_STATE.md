# Project State

This is the detailed continuity record for DECnet-IV-Linux. A fresh session should enter through `docs/HANDOVER.md`, then read this file and `docs/ROADMAP.md` completely before executing `Next action`; do not reconstruct project state from chat history.

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

The project-owned `tuklusan/Route20` and `tuklusan/pydecnet` forks are the primary pinned reference peers. Upstream repositories are comparison points. DECnet protocol documentation and useful supplementary protocol notes carried with PyDECnet remain protocol references. Later add SIMH-hosted DEC operating systems for application-level validation.

Pinned revisions are stored in `tests/reference/refs.env`. Route20 is a behavioral/reference peer; its source license is not assumed suitable for direct incorporation into the kernel module.

The current PyDECnet reference is pinned for documentation, vectors and live interoperability. Its present tree has a pre-existing self-test contradiction in `Macaddr("1.24")` introduced by a July 2024 change: the code takes the hexadecimal path before the DECnet `area.node` path while the test still requires `area.node`. The hard full-suite pin is therefore the immediately preceding revision. The suite is run unmodified; no tests are skipped or rewritten. Move the test pin forward when the reference fixes the contradiction.

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

- `docs/HANDOVER.md` is the stable handover entry point; this file carries detailed live state and `docs/ROADMAP.md` carries ordered execution.
- Every substantive commit must update this file in the same commit.
- `tools/project_state_gate.py` validates the exact staged or committed bytes, not a possibly different working-tree copy.
- Every substantive commit must also carry a fresh `reviews/CHECKIN_REVIEW.json` from the independent Neurotic Paranoid Code Reviewer.
- `tools/paranoid_review_gate.py` binds that receipt to the exact parent and the complete tracked path/mode/blob snapshot, excluding only the self-referential receipt; receipt-only commits are rejected.
- The reviewer directive is in `docs/REVIEWER.md`: two full untruncated reads, deep then adversarial, followed by exactly three consecutive clean SoP passes. Any fix or later change resets the pass count.
- Reviewer output is limited to BLOCKER, CRITICAL and MAJOR findings; programmer disposition is explicit.
- This file must keep non-empty `Resume point` and `Next action` sections.
- Workflows carry short comments describing what each gate proves.
- Substantive work is prepared on a working branch, gates run there, and `main` is advanced only to the exact green commit.

## Phase 1 status

Phase 1 is implemented and builds on both required CPU architectures. It contains UAPI version 1, `decnet_iv.ko`, default 31.70/DN70 identity, `/dev/decnet_iv`, DEC DNA Routing EtherType receive registration/counters, `dnctl`, centralized test addressing, unit address tests and native x86_64/ARM64 build gates.

The bootstrap does not yet claim adjacency, routing, NSP, Session Control or DDCMP functionality.

The paranoid full-tree review found and fixed a Phase-1 parameter-validation defect: invalid module area/node values could previously be masked into apparently valid DECnet addresses and an overlong default name could be truncated. Defaults are now range/name validated before address construction.

## External baseline status

The pinned `tuklusan/Route20` revision builds. The pinned current `tuklusan/pydecnet` revision is retained for live/docs reference; the complete unmodified suite is run at the immediately preceding revision before its known `Macaddr("1.24")` self-test regression. CI now fetches the project forks rather than bypassing them for upstream URLs.

## Reviewer gate status

The check-in gate has a local hook, CI workflow, closed receipt schema and unit coverage. The review receipt binds the complete tracked repository snapshot. During its first repository-wide review it found and fixed pre-existing gate, kernel, reference-discipline and documentation defects, including the previously missing stable `docs/HANDOVER.md` entry point.

## Resume point

This commit contains the completed independent paranoid-review check-in gate plus all BLOCKER, CRITICAL and MAJOR defects found during its repository-wide review. If this exact commit is still on `work/paranoid-review-gate`, promote it only after every required gate is green. Once this exact commit is on `main`, the continuity/review baseline is complete and Phase 2 is the active next phase.

## Next action

If this exact commit is not yet on `main`, promote only this exact green commit. Once it is on `main`, start Phase 2 on a fresh working branch: pin the official Alpine 3.24.1 tiny QCOW2 bases for x86_64 BIOS and aarch64 UEFI, build/install the exact `linux-virt` module plus `dnctl`, boot DN70 and DN71 as separate VMs on a raw Ethernet bridge, collect pcaps/logs, and prove bidirectional EtherType `0x6003` reception before implementing hello/adjacency logic.
