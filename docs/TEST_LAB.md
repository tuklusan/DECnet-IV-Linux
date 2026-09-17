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

The lab proves DECnet protocol behavior independently of release-image production. Protocol tests should spend their time booting and exercising nodes, not repeatedly rebuilding or serializing mutable VM state.

## Architecture sessions

There are two logical outer architecture sessions for each exact candidate: amd64 and arm64. Their stable session IDs are `outer-v1-<arch>-<source-sha>`. GitHub-hosted runners themselves are ephemeral, so their root disks are not relied upon; instead the immutable architecture disk payload is persisted in the Actions cache and restored onto the matching architecture runner.

An outer session contains only:

- `base.qcow2`;
- `boot/vmlinuz`;
- `boot/initrd.img`;
- `session.env`;
- `SHA256SUMS`.

A restore is usable only if `ARCH` and `SOURCE_SHA` match the running job, the stable session ID matches exactly, every checksum verifies, and `qemu-img check` succeeds. Cache keys contain both architecture and exact source SHA, so no cross-architecture or cross-candidate reuse is possible.

The architecture-specific `dniv-runner-x64` and `dniv-runner-arm64` concurrency groups serialize creation/consumption. The first job for an architecture/SHA can populate a missing session; subsequent E1 or interoperability jobs restore it instead of rebuilding the Ubuntu Base image.

## Two-node execution

`tests/lab/dniv_lab.py` owns VM lifecycle for the Phase 2/E1 gate. It receives the verified immutable outer base plus kernel/initrd and creates fresh qcow2 node overlays, a Linux bridge, two TAP devices, DECnet packet capture and one QMP socket per guest. It launches QEMU directly, waits for guest acceptance markers, validates captured wire behavior, shuts guests down through QMP where possible, and removes host networking on every exit path.

Node overlays and QMP sockets are transient and excluded from uploaded evidence. Serial logs, packet captures, outer-session metadata and integrity manifests are durable acceptance evidence.

## Architectures

The hosted matrix remains:

- amd64 on `ubuntu-24.04`, using `qemu-system-x86_64` and KVM when `/dev/kvm` is usable;
- arm64 on `ubuntu-24.04-arm`, using `qemu-system-aarch64` and KVM when `/dev/kvm` is usable.

If KVM is unavailable the controller falls back to TCG. Native self-hosted KVM-capable x86_64 and arm64 machines remain the path to literal persistent runner root disks, but protocol acceptance no longer depends on runner-local disk survival.

## Addressing

Ordinary test nodes use area 31, nodes 70 through 79, with names DN70 through DN79 as defined in `tests/lab/test-addresses.env`. DECnet Phase IV protocol MACs are derived from area/node. E1 deliberately gives the emulated NIC a different primary MAC so the test proves that protocol-originated frames use the DECnet-derived source MAC and that unicast filtering survives later primary-MAC changes.

## Interoperability

Route20 and PyDECnet remain pinned independent peers. Interoperability consumes the same verified architecture session and derives disposable candidate/reference images from it. Prior-run evidence restore is not part of execution. Route20/PyDECnet payloads remain exact-SHA pinned and are injected only into disposable working images.

## Scale and faults

The Python controller is intentionally small enough to extend from two to 16 independent VMs. The target topology API should support multiple bridges/TAPs, mixed-media attachment, deterministic link down/up, delay/loss/corruption via `tc netem`, guest kill/restart, packet capture per segment and independent reference peers. Those extensions must preserve exact-SHA evidence and bounded hosted-job execution.

## Release-image separation

`image/ubuntu-base/build-image.sh` remains the canonical full image-construction path and is used to populate a missing architecture session. Its filesystem and RAW/QCOW2 checks remain valid release/image gates. Once a verified outer session exists for the exact candidate, ordinary protocol jobs restore it rather than repeating full construction.
