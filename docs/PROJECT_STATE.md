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

The current PyDECnet reference is pinned for documentation, vectors and live interoperability. Its present tree has a pre-existing self-test contradiction in `Macaddr("1.24")`: the code takes the hexadecimal path before the DECnet `area.node` path while the upstream test still requires `area.node`. The hard full-suite pin is therefore the immediately preceding revision. The suite is run unmodified; no tests are skipped or rewritten. Move the test pin forward when upstream fixes the contradiction.

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

- Every substantive commit must update this file and `docs/HANDOVER.md` in the same commit.
- `docs/HANDOVER.md` is generated deterministically from this file by `tools/render_handover.py`; it contains a copy/paste-ready next-session prompt.
- The local pre-commit hook regenerates and stages the handover before running the continuity gate.
- `tools/project_state_gate.py` checks every substantive commit in the pushed range, validates non-empty Resume point/Next action sections, and verifies that each commit's handover exactly matches that commit's project state.
- Force-pushes are handled by falling back to the merge-base with `origin/main` when the event's previous SHA is missing or no longer an ancestor.
- Workflows carry short comments describing what each gate proves.
- Substantive automated work is prepared on a working branch, gates run there, and `main` is advanced only after the branch is green.
- During long interactive work, surface the current handover text before the conversation becomes difficult to continue; the repository copy remains authoritative if no such message is available.

## Phase 1 status

Phase 1 is on `main` and green on both required CPU architectures. It contains UAPI version 1, `decnet_iv.ko`, default 31.70/DN70 identity, `/dev/decnet_iv`, DEC DNA Routing EtherType receive registration/counters, `dnctl`, centralized test addressing, unit address tests and native x86_64/ARM64 build gates.

The bootstrap does not yet claim adjacency, routing, NSP, Session Control or DDCMP functionality.

## External baseline status

The corrected external-reference baseline is promoted to `main` and green. Route20 builds at its pinned revision. The full unmodified PyDECnet suite runs at the last passing revision immediately before its current `Macaddr("1.24")` self-test contradiction; the current PyDECnet revision remains pinned separately for documentation, vectors and live interoperability.

## Phase 2 status

Work is on `work/phase2-vm-lab`. Alpine 3.24.1 official tiny QCOW2 bases are pinned for x86_64 BIOS and aarch64 UEFI. The first VM gate builds `decnet_iv.ko` against the guest's installed `linux-virt` headers, installs `dnctl` and a tiny raw-frame probe, boots DN70 and DN71 on one Linux bridge, retains serial logs and a pcap, and requires bidirectional EtherType `0x6003` receive counters. The first CI attempt established that Alpine's 129-byte `.sha512` sidecars contain a bare SHA-512 digest rather than a GNU checksum manifest; verification now accepts bare, GNU and BSD/OpenSSL SHA-512 formats. Native AArch64 VM execution follows after the x86 lab is green.

## Resume point

Phase 1 and the external reference baselines are promoted and green on `main`. Phase 2 remains unpromoted on `work/phase2-vm-lab` and is being kept as one clean substantive commit directly on top of `main`. The current rewrite includes the two-node VM lab, generated handover enforcement, force-push-safe continuity range selection, and corrected Alpine SHA-512 verification. The previous VM run did not reach guest boot because both architecture jobs stopped at the checksum-format mismatch.

## Next action

Run every workflow on the rewritten Phase 2 commit. Confirm the Project State Gate now validates from the main merge-base after a branch rewrite and that both pinned Alpine images verify. Then repair any next x86 VM-lab failure until DN70 and DN71 boot customized Alpine, load the module, exchange EtherType `0x6003` frames and report non-zero receive counters with a retained pcap. Add native aarch64 UEFI and mixed-architecture runs only after x86 is green; promote only after all gates pass, then begin Phase 3 hello and adjacency logic.
