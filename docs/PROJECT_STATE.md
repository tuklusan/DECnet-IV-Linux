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

## External conformance

Self-to-self success is never sufficient for final interoperability claims. Exercise the stack against the pinned Route20 and PyDECnet forks, and later against SIMH-hosted real DEC operating systems.

Pinned automated references live in `tests/reference/refs.env`. CI fetches the preferred forks, not upstream repositories. Existing reference gates remain part of every later phase.

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
- Linux bridges provide raw native Ethernet LANs.
- DECnet acceptance traffic stays on isolated native DECnet media.
- The Phase 2 lab has one NIC per VM and no runtime provisioning network.
- Scale deliberately from 2 to 4, 8 and 16 independent VMs with routed topologies.
- Required CPU cases include x86_64/x86_64, aarch64/aarch64 and both mixed directions.
- Fault and stress work includes deterministic loss, duplication, delay/reordering where meaningful, link/circuit failure, restart, convergence, connection churn, long-duration traffic and resource/lifetime failures.
- Required mixed-media path eventually includes `Ethernet -> router -> DDCMP -> router -> Ethernet`.

## Repository discipline

- Do not create development branches. Keep one maintained `main` line.
- Historical working refs were reconciled into `main` at commit `b51618cbf49ae43b223d3dcd15f156086fea41dc`; they are aliases only and must not carry divergent work.
- Every substantive commit updates this file in the same commit.
- `tools/project_state_gate.py` enforces continuity requirements.
- Local policy hooks are installed with `tools/install-hooks.sh`; both hook entry points are executable in the repository.
- Keep commits atomic and run applicable static/unit/reference gates before advancing work.
- Generated VM evidence stays under ignored `tests/lab/artifacts/`; do not commit generated images, captures or logs.
- Keep only project-relevant source, tests, build/image machinery and continuity documentation.
- Runner use is demand-driven. All repository workflows are manual-dispatch only and use per-workflow/ref concurrency with cancellation of duplicate in-progress runs. Launch only the exact gate needed for the exact commit being evaluated; do not fan out routine pushes into runner work.

## SoP delivery rule

1. Read the complete latest disk copy byte-for-byte, line-by-line, with no truncation; find and fix defects/gaps.
2. Any fix resets the pass to Step 1 on the new latest disk copy.
3. Delivery requires three consecutive clean complete Step-1 passes.
4. Any later change resets Step 1.

Automated tests, diffs, excerpts or prior reviews do not replace this rule.

## Phase 1 status

Phase 1 is on `main` and contains UAPI version 1, `decnet_iv.ko`, default 31.70/DN70 identity, `/dev/decnet_iv`, DEC DNA Routing EtherType receive registration/counters, `dnctl`, centralized test addressing, unit address tests and native x86_64/aarch64 build gates.

The bootstrap does not claim adjacency, routing, NSP, Session Control, NICE/NML application behavior or DDCMP functionality.

## Phase 2 status

Ubuntu Base 26.04.1 was selected because it is the smallest official non-cloud Ubuntu rootfs intended for custom images and is published for both required CPU architectures. The pinned release provides 33 MiB amd64 and arm64 tarballs. Exact filenames and SHA-256 values are in `image/ubuntu-base/images.env`; those pins have also been cross-checked against the current official Ubuntu Base SHA256SUMS.

The apt dependency set is frozen with Ubuntu Snapshot Service timestamp `20260915T000000Z`; apt in Ubuntu 24.04 and later accepts snapshot IDs directly, so later rebuilds do not silently pick newer kernel or userspace packages.

The lab deliberately removes the old boot/provisioning complexity. CI expands the rootfs, installs Ubuntu's virtual kernel plus the module/tools, copies out the exact kernel and initrd, then direct-boots two QCOW2 overlays with QEMU `-kernel`/`-initrd`. Each guest has one raw Ethernet NIC. A boot-conditioned smoke service sets node identity, sends EtherType `0x6003` frames to its peer, verifies kernel receive counters and powers off. No installer, cloud metadata, firmware image or management NIC is involved.

The latest complete review caught two final lifetime mistakes in the VM harness. First, the base machine identity was being cleared before package installation, allowing package scripts to recreate it before the image was cloned. It is now cleared after all package work. Second, background shell functions rather than QEMU itself were the recorded guest PIDs, so teardown could kill a wrapper and leave its emulator behind; the launch path now `exec`s QEMU and guest termination uses a TERM grace period followed by KILL.

The following adversarial pass found one UAPI consistency gap: `dnctl stats` consumed the kernel statistics structure without checking its returned UAPI version, unlike the identity path. Statistics output now rejects an unsupported kernel UAPI version before interpreting counters.

Runner pressure then exposed an operational flaw in the gate layout: every main-line promotion launched all gates, including expensive reference and two-VM jobs, producing a large queued backlog. Workflows are now demand-driven `workflow_dispatch` jobs with duplicate-run concurrency cancellation. This operational change resets the SoP sequence.

## Resume point

The repository is based on Ubuntu Base 26.04.1, historical branch refs are reconciled aliases of the maintained line, generated VM artifacts are ignored, and Phase 2 uses a direct-kernel-boot two-VM design driven by the centralized test address pool. Reference CI consumes the preferred fork URLs. Repository runners are no longer launched by routine pushes; gates are started only when the exact commit and exact evidence need them.

## Next action

Restart SoP pass 1 from the complete latest repository copy. Do not launch another runner until a specific gate is required. When Phase 2 is ready for runtime proof, run only the exact native two-node VM gate for the exact candidate commit; fix only defects demonstrated by retained serial/pcap evidence. Once both native CPU cases are green and three consecutive full SoP passes are clean, move immediately into Phase 3: implement DECnet Ethernet address handling, hello parsing/generation and adjacency state/expiry with independent Route20/PyDECnet vectors. Add mixed-CPU VM execution after the native lab is stable; do not let VM plumbing block protocol implementation again.
