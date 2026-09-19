<!-- ============================================================================ -->
<!-- Copyright (c) 2026 Supratim Sanyal of SANYALnet Labs. -->
<!-- Proprietary rights reserved except as expressly licensed herein. -->
<!-- -->
<!-- DECnet-IV-Linux -->
<!-- This file is governed by the SANYALnet Labs Non-Commercial License in the -->
<!-- root LICENSE file. Non-Commercial use is permitted; Commercial Use and use -->
<!-- for AI/ML model training are prohibited unless separately authorized. -->
<!-- -->
<!-- Attribution is required: "Based on original work by Supratim Sanyal of -->
<!-- SANYALnet Labs." See LICENSE for full terms, warranty disclaimer, termination, -->
<!-- patent, trademark, and governing-law provisions. -->
<!-- ============================================================================ -->

# DECnet-IV-Linux Test Lab

## Purpose

The lab proves DECnet protocol behavior independently of release-image production. Protocol tests spend their time booting and exercising nodes, not reinstalling Ubuntu packages or serializing mutable VM state.

## Persistent architecture foundations

There are two logical outer foundations: amd64 and arm64. GitHub-hosted runner root filesystems are ephemeral, so the foundations are retained in the Actions cache and restored onto the matching architecture runner. The stable ID is `outer-v2-<arch>-<foundation-fingerprint>`. The fingerprint is derived from the pinned Ubuntu image metadata and `build-foundation.sh`; it deliberately excludes the candidate source SHA.

A foundation contains only `base.qcow2`, `boot/vmlinuz`, `boot/initrd.img`, `session.env` and `SHA256SUMS`. It contains Ubuntu userspace, the pinned guest kernel/initrd, headers/compiler and independent-peer runtime dependencies. It must not contain project source, `decnet_iv.ko`, project tools, smoke services or any candidate SHA.

A restore is usable only if architecture, foundation fingerprint, Ubuntu release/snapshot and stable session ID match, every checksum verifies, `qemu-img check` passes, and the manifest contains no `SOURCE_SHA`. A source-only project commit therefore reuses the same foundation. A foundation recipe, Ubuntu pin or architecture change produces a different cache key.

The architecture-specific `dniv-runner-x64` and `dniv-runner-arm64` concurrency groups serialize creation and consumption. Cache eviction can require rebuilding a foundation, but ordinary candidate changes do not.

## Disposable exact-candidate images

`tests/lab/prepare-candidate-image.sh` clones the verified foundation into a disposable image, archives the exact checked-out `HEAD`, builds `decnet_iv.ko`, `dnctl` and `dnraw` against the foundation's pinned guest headers, records the exact source SHA, and installs the two-node and interoperability smoke entry points. It performs no package installation.

The Python two-node controller receives that disposable candidate image as its immutable per-run base and creates fresh qcow2 node overlays. Interoperability creates a disposable exact-candidate image plus a disposable reference image from the same foundation. The reference image receives only the current harness plus runtime helpers; Route20/PyDECnet payloads remain independently pinned and attached separately.

## Two-node execution

`tests/lab/dniv_lab.py` owns VM lifecycle for the Phase 2/E1 gate. It creates fresh qcow2 node overlays, a Linux bridge, two TAP devices, DECnet packet capture and one QMP socket per guest, launches QEMU directly, waits for guest acceptance markers, validates captured wire behavior and removes host networking on exit.

VM runtime files live under a deliberately short `/tmp/dniv-*` path so QMP UNIX sockets remain below the Linux pathname limit. Compact serial/pcap evidence is copied into `scratch/runtime/`; qcow2 overlays and QMP sockets are discarded and never uploaded.

## Architectures

The hosted matrix remains amd64 on `ubuntu-24.04` with `qemu-system-x86_64`, and arm64 on `ubuntu-24.04-arm` with `qemu-system-aarch64`. KVM is used when `/dev/kvm` is usable; otherwise the controller falls back to TCG. Native self-hosted KVM machines remain an optimization, not an acceptance dependency.

## Addressing

Ordinary test nodes use area 31, nodes 70 through 79, with names DN70 through DN79 as defined in `tests/lab/test-addresses.env`. DECnet Phase IV protocol MACs are derived from area/node. E1 deliberately gives the emulated NIC a different primary MAC so the test proves protocol-originated frames use the DECnet-derived source MAC and unicast filtering survives later primary-MAC changes.

## Interoperability

Route20 and PyDECnet remain pinned independent peers. Their VDE-enabled live pins support both modern and legacy libvdeplug open ABIs. Interoperability consumes the same source-independent architecture foundation, derives the disposable exact-candidate image, builds the exact pinned peer, and executes bounded L1/L2/endnode scenarios. Prior-run evidence restore is not part of execution. Route20 continues to run in an independent reference VM. PyDECnet runs its pinned source directly on the architecture-matched hosted runner through its native Linux TAP backend attached to the same host bridge as the candidate VM. This removes QEMU virtio/libpcap receive-filter timing from PyDECnet interoperability without changing candidate protocol behavior. The host TAP's Linux device MAC deliberately remains distinct from PyDECnet's DECnet logical MAC; assigning the logical MAC to the TAP creates a bridge-local FDB entry and prevents candidate unicast from reaching the TAP queue. PyDECnet readiness is application-backed and requires its own `DECnet/Python is running` marker. Route20 reference READY remains bounded at 180 seconds on amd64 and 600 seconds on ARM64; host PyDECnet readiness is bounded at 60 seconds.

## Scale and faults

The Python controller is intentionally small enough to extend from two to 16 independent VMs. The target topology API should support multiple local bridges/TAPs plus rootless VDE2 segments, deterministic link down/up, delay/loss/corruption, guest kill/restart, packet capture per segment and independent reference peers. Distributed runners may join user-owned VDE switches over SSH. Internet point-to-point attachment is provided separately through a MULTINET TCP gateway and must not be conflated with VDE2 proof. Those extensions must preserve exact-SHA evidence and bounded hosted-job execution.

E4 router readiness is adjacency-backed rather than a boot marker: L1 routers must see their local L2 peer UP, and L2 routers must see both the local L1 and cross-area L2 peer UP before endpoints start. Endpoint probes remain active for a bounded 90-second convergence window so independent ARM64 TCG boot skew cannot turn a valid routed path into a one-direction sampling false failure. Host PCAP checks still require the correct router source MAC and visit count at transit and destination segments in both directions.

## Distributed VDE2, MULTINET and Area-31

VDE2 and MULTINET are independent transport test tracks. `tests/lab/prove-vde2.sh` has a green local/rootless proof for real libvdeplug frame delivery plus Route20/PyDECnet adjacency. `tests/lab/prove-multinet.sh` has a separate green proof for the pinned PyDECnet MULTINET module and a live TCP point-to-point adjacency/reconnect cycle. These tracks are never combined to manufacture a pass.

The current VDE2 proof is single-host. Cross-runner VDE2 remains unproven until two hosted machines each run their own `vde_switch` and the switches are actually joined, with frame delivery, adjacency, disconnect/reconnect and fault evidence retained across the host boundary.

The Area-31 stage uses `userspace/dnmultinet/dnmultinet.py` as a VDE-to-MULTINET gateway in TCP client mode. Its repository-tracked workflow must obtain `MULTINET_REMOTE_HOST`, `MULTINET_REMOTE_PORT`, `VAX_ADDR`, `VAX_USERNAME` and `VAX_PASSWORD` from Actions secrets only. The first executable step must detect missing prerequisites and identify the missing secret names without printing values. The MULTINET endpoint is one Area-31 area router; the VAX at `VAX_ADDR` is another area router reachable through that path.

As userspace matures, keep reusable Linux/VAX test pairs under `tests/lab` (with VAX-side helpers in a dedicated subdirectory). Start with remote node/route/NICE information and counters, then NSP/Session/object access, login, DAP/FAL, PHONE, mail, task access and application experiments. Evidence must redact credentials and must distinguish local transport proof, remote routing proof and application proof. See `docs/HECNET_LAB.md`.

## Release-image separation

`image/ubuntu-base/build-image.sh` remains the canonical full exact-source release/test image path. `image/ubuntu-base/build-foundation.sh` exists only to amortize expensive package/kernel preparation for protocol acceptance. Release-image correctness remains an independent gate and is not inferred from a cached foundation.

For direct host-TAP PyDECnet runs, a separate host `dnraw` loop injects marked DECnet-Ethernet unicast frames through the Linux bridge toward the candidate logical MAC. This preserves the same post-NIC-MAC-change lower-layer receive proof used by guest-backed references without coupling that check to PyDECnet routing/NSP convergence.

Direct PyDECnet interoperability also exercises inbound native sockets. The pinned host-TAP peer exposes its Unix Session API; `pydecnet-inbound.py` connects to candidate object 240 and named object `DNIVTEST`. The guest `dnaccept` server must accept both, report the PyDECnet node/source object through `getpeername()`, echo records, and observe disconnect before the existing MAC-change/expiry/recovery sequence continues.
