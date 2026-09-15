# Project State

This is the continuity record for DECnet-IV-Linux. A fresh session should read this file first, then execute `Next action` without reconstructing the project from chat history.

## Goal

Build a minimal maintained Linux distribution with a fresh native DECnet Phase IV implementation delivered primarily as an out-of-tree kernel module, familiar DECnet user-mode tools, and reproducible x86_64/aarch64 VM images.

## Non-negotiable architecture

- Reference distribution: Alpine Linux 3.24 initially using `linux-virt`.
- Kernel delivery: out-of-tree module; avoid a permanent kernel fork.
- Module lifecycle: automatic rebuild after supported kernel package changes is mandatory. Alpine uses AKMS; DKMS metadata is maintained for Debian and RHEL-family systems.
- Implementation base: fresh code informed by DECnet specifications and independent interoperability behavior, not the removed/legacy Linux DECnet kernel stack.
- Kernel scope as the project matures: Ethernet, Phase IV routing, NSP, DDCMP, socket/UAPI plumbing, timers, forwarding and management hooks.
- Userspace target: familiar DECnet/Linux command experience for `ncp`, `sethost`, `dncopy`, `phone` and related tools.
- Required CPU targets: x86_64 and aarch64.
- Primary VM artifact: QCOW2, with RAW and conversion formats at release time.

## External conformance

The implementation must be exercised independently against Route20 and PyDECnet, using DECnet protocol documentation and useful supplementary protocol notes carried with PyDECnet. Later add SIMH-hosted DEC operating systems for application-level validation.

Pinned revisions are stored in `tests/reference/refs.env`. Route20 is a behavioral/reference peer; its source license is not assumed suitable for direct incorporation into the kernel module.

Every useful and internally consistent upstream/reference test at the pinned revisions must pass unmodified. The current PyDECnet reference is pinned for documentation, vectors and live interoperability. Its present tree has a pre-existing self-test contradiction in `Macaddr("1.24")`: the code takes the hexadecimal path before the DECnet `area.node` path while the upstream test still requires `area.node`. The hard full-suite pin is therefore the immediately preceding revision. The suite is run unmodified; no tests are skipped or rewritten. Move the test pin forward when upstream fixes the contradiction.

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
10. scale, portability, physical mixed-CPU testing and release images.

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
- Disposable management NICs may be used only for provisioning/package access; DECnet acceptance traffic must stay on isolated native DECnet media.
- Native DECnet is stressed first and aggressively. DECnet-over-IP tunneling is deferred until the native Ethernet, routing, transport, session and application layers are mature.
- Failure artifacts include topology, addressing, packet capture, kernel logs, DECnet counters and fault-injection seed where applicable.
- Required CPU matrix: x86_64/x86_64, aarch64/aarch64 and mixed x86_64/aarch64.
- Later portability matrix uses the smallest official maintained images from Alpine, Debian and RHEL-family distributions and proves real kernel package upgrades rebuild the module automatically.
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

Work is on `work/phase2-vm-lab`. Alpine 3.24.1 official tiny QCOW2 bases are pinned for x86_64 BIOS and aarch64 UEFI. The x86 lab uses NoCloud `CIDATA` first-boot provisioning instead of offline image mutation. DN70 and DN71 each have an isolated DECnet NIC plus a disposable QEMU user-network management NIC used only to install packages. The seed carries the source tree, installs the module under `/usr/src`, registers/builds it with AKMS, installs the small user tools, reboots into the installed kernel, and requires the test to load the AKMS-managed module before exchanging EtherType `0x6003` frames. DKMS metadata and a native-build smoke test cover the parallel lifecycle path for Debian/RHEL-family systems. The later portability lab is documented in `tests/lab/DISTRO_MATRIX.md`.

A resumable lab session has a stable `DNIV_LAB_SESSION_ID` separate from each `DNIV_LAB_ATTEMPT_ID`. The known DN70/DN71 QCOW2 disks, matching NoCloud seed ISOs and `session.env` live under `tests/lab/artifacts/sessions/<session-id>/`, while each attempt gets its own serial logs, pcap and result manifest under `attempts/<attempt-id>/`. `DNIV_LAB_RESUME=1` requires the known manifest, disks and seeds to exist and match the requested session instead of silently recreating them. In Actions, a manual run can restore the named `two-node-x86-session-<session-id>` artifact from a prior workflow run and upload the updated session again.

The first session after executable seed generation was fixed is `gha-34948868114`. It is a valid known session with both QCOW2 disks, both seeds and `session.env`, retained by workflow run `34948868114`. Both guests booted and executed NoCloud, but the original 128 MiB tiny root filesystem filled while installing `linux-virt-dev` and build dependencies. The retained serial logs show `No space left on device`; the earlier live timeout tails appeared empty only because QEMU had not flushed file-backed serial output before the script printed them.

The launcher now sparse-grows new and resumed QCOW2 disks to 4 GiB by default before boot. On resume it mounts each known disk through NBD and clears `/var/lib/cloud/.bootstrap-complete` only when `/var/lib/decnet-lab/provisioned` is absent, allowing an interrupted Tiny Cloud bootstrap to retry without replacing the disk identity. Successfully provisioned disks keep their completed bootstrap state. Attempt manifests now distinguish the source/base image recorded for the persistent session from the current runner revision/checksum. Timeout handling terminates QEMU before serial tails are printed so failure evidence is flushed first.

The earlier session `gha-34948701365` remains intentionally non-resumable because its failure happened before seeds and a session manifest existed.

## Resume point

Phase 1 and all external/build/repository/continuity gates are green. Phase 2 remains unpromoted on `work/phase2-vm-lab`. Persistent session identity is implemented and now includes safe sparse disk growth, interrupted-bootstrap recovery and honest session-versus-runner provenance. Known session `gha-34948868114` is retained from workflow run `34948868114`; it booted both guests and failed only because the original 128 MiB roots ran out of space during package installation. The current launcher grows such disks to 4 GiB and can retry that same session without recreating DN70 or DN71.

## Next action

Run the workflows on the disk-growth/recovery commit. First prove a fresh x86 session can provision DN70 and DN71 on the 4 GiB sparse disks, reboot, load the AKMS-managed module, exchange native EtherType `0x6003` frames and report non-zero receive counters with retained serial logs and pcap. Then explicitly resume known session `gha-34948868114` from prior workflow run `34948868114` and prove the interrupted-bootstrap repair recovers those exact disks rather than replacing them. Keep Route20, the full usable PyDECnet suite, both native build targets and both pinned Alpine image checks green. Only after fresh and resumed x86 paths are proven add native aarch64 UEFI and mixed-architecture runs, then promote the exact green commit and begin Phase 3 hello/adjacency work. DECnet-over-IP work remains deferred.
