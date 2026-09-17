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

The lab proves DECnet protocol behavior independently of release-image production. Protocol tests should spend their time booting and exercising nodes, not serializing mutable VM state between hosted runners.

## Current two-node architecture

`tests/lab/dniv_lab.py` owns VM lifecycle for the Phase 2/E1 two-node gate. The workflow supplies one read-only-by-convention base QCOW2 plus its kernel/initrd. The controller creates fresh qcow2 overlays, a Linux bridge, two TAP devices, a DECnet-only packet capture and one QMP socket per guest. It launches QEMU directly, waits for guest acceptance markers, validates the captured wire behavior, shuts guests down through QMP where possible, and removes host networking on every exit path.

The base image is immutable input. Overlay disks and QMP sockets are transient and are excluded from uploaded evidence. Serial logs, packet captures, scratch metadata and integrity manifests remain the durable acceptance evidence.

## Architectures

The hosted proof matrix remains native runner architecture where available:

- amd64 on `ubuntu-24.04`, using `qemu-system-x86_64` and KVM only when `/dev/kvm` is usable.
- arm64 on `ubuntu-24.04-arm`, using `qemu-system-aarch64` and KVM only when `/dev/kvm` is usable.

If KVM is unavailable the controller falls back to TCG. Long term, native self-hosted KVM-capable x86_64 and aarch64 runners are preferred so protocol tests do not depend on nested/emulated virtualization performance.

## Addressing

Ordinary test nodes use area 31, nodes 70 through 79, with names DN70 through DN79 as defined in `tests/lab/test-addresses.env`. DECnet Phase IV protocol MACs are derived from area/node. E1 deliberately gives the emulated NIC a different primary MAC so the test proves that protocol-originated frames use the DECnet-derived source MAC and that unicast filtering survives later primary-MAC changes.

## Evidence

For each two-node session the controller retains:

- `node-a.serial.log` and `node-b.serial.log`;
- `lan.pcap` containing EtherType `0x6003` traffic;
- workflow scratch/integrity metadata.

It does not retain guest overlays, VM checkpoints or QMP sockets.

## Interoperability

Route20 and PyDECnet remain pinned independent peers. The existing interoperability workflow still uses its shell launcher and derived peer images while the Python two-node controller is proven. After E1 is green on both architectures, interoperability should move to the same Python lifecycle model and image mutation should be reduced to the minimum needed to inject a pinned peer payload.

## Scale and faults

The Python controller is intentionally small enough to extend from two to 16 independent VMs. The target topology API should support multiple bridges/TAPs, mixed-media attachment, deterministic link down/up, delay/loss/corruption via `tc netem`, guest kill/restart, packet capture per segment and independent reference peers. Those extensions must preserve exact-SHA evidence and bounded hosted-job execution.

## Release-image separation

`image/ubuntu-base/build-image.sh` remains the release/base-image construction path. Its filesystem and RAW/QCOW2 integrity checks are valid image-production gates, but image construction is not itself a DECnet protocol assertion. Once persistent immutable bases are available, ordinary protocol jobs should consume them and leave full image construction to dedicated image/release validation.
