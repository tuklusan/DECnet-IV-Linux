# Project State

This is the continuity record for DECnet-IV-Linux. Repository state is authoritative. Read this file and `docs/ROADMAP.md` completely before changing code.

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

Pinned automated references live in `tests/reference/refs.env`. Existing reference gates remain part of every later phase.

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
- Historical working refs were reconciled into `main` at commit `b51618cbf49ae43b223d3dcd15f156086fea41dc`; do not revive divergent work from them.
- Every substantive commit updates this file in the same commit.
- `tools/project_state_gate.py` enforces continuity requirements.
- Keep commits atomic and run applicable static/unit/reference gates before advancing work.

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

Ubuntu Base 26.04.1 was selected because it is the smallest official non-cloud Ubuntu rootfs intended for custom images and is published for both required CPU architectures. The pinned release provides 33 MiB amd64 and arm64 tarballs. Exact filenames and SHA-256 values are in `image/ubuntu-base/images.env`.

The apt dependency set is also frozen with Ubuntu Snapshot Service timestamp `20260915T000000Z`; apt in Ubuntu 24.04 and later accepts snapshot IDs directly, so later rebuilds do not silently pick newer kernel or userspace packages.

The new lab deliberately removes the old boot/provisioning complexity. CI expands the rootfs, installs Ubuntu's virtual kernel plus the module/tools, copies out the exact kernel and initrd, then direct-boots two QCOW2 overlays with QEMU `-kernel`/`-initrd`. Each guest has one raw Ethernet NIC. A small boot-conditioned smoke service sets node identity, sends EtherType `0x6003` frames to its peer, verifies kernel receive counters and powers off. No installer, cloud metadata, firmware image or management NIC is involved.

A pre-gate static pass caught two issues before relying on CI: the strict-C11 raw-frame helper now enables the libc interfaces needed for `struct ifreq`, and MAC parsing rejects trailing garbage. This change resets the SoP sequence.

## Resume point

The repository is cleanly based on Ubuntu Base 26.04.1 and the Phase 2 lab has been replaced with the direct-kernel-boot design. The exact new VM gate must now prove both native CPU cases before protocol work proceeds.

## Next action

Run the exact new VM gate on amd64 and arm64. Fix only defects demonstrated by retained serial/pcap evidence. Once both native two-node cases are green and the SoP gate is clean, move immediately into Phase 3: implement DECnet Ethernet address handling, hello parsing/generation and adjacency state/expiry with independent Route20/PyDECnet vectors. Add mixed-CPU VM execution after the native lab is stable; do not let VM plumbing block protocol implementation again.
