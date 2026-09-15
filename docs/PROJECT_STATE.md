# Project State

This file is the continuity record for DECnet-IV-Linux. Keep it short, current, and sufficient for work to resume from a fresh conversation or workstation.

## Goal

Build a minimal, actively maintained Linux distribution with a fresh native DECnet Phase IV implementation delivered primarily as an out-of-tree kernel module, plus familiar DECnet user-mode tools and reproducible VM images.

## Core architecture

- Reference distribution: Alpine Linux 3.24, initially using `linux-virt`.
- Kernel delivery: out-of-tree module, avoiding a permanent Linux kernel fork.
- Kernel scope: DECnet Ethernet, Phase IV routing, NSP, DDCMP, socket/UAPI plumbing, timers, forwarding, and network-management hooks as implementation matures.
- Userspace: familiar DECnet/Linux command experience without reusing the old Linux DECnet kernel implementation.
- Initial user commands: `sethost`, `ncp`, `phone`, `dncopy`, plus diagnostic/configuration tools.
- Architectures: x86_64 and aarch64 are required targets.
- VM artifacts: QCOW2 is primary; RAW and common conversion formats may be added for releases.

## Compatibility and conformance

The implementation must be independently exercised against:

1. Route20 for build and live DECnet interoperability, including routing behavior.
2. PyDECnet for protocol behavior, packet vectors, its test suite, Ethernet interoperability, and DDCMP interoperability.
3. DECnet protocol documentation and supplementary protocol notes carried by the PyDECnet project.
4. Later, SIMH-hosted DEC operating systems for application-level validation.

Route20 is a behavioral/interoperability reference. Its source license is not assumed to be suitable for direct incorporation into the Linux kernel module.

## Test addressing

- Default configurable test pool: area 31, nodes 70 through 79.
- Default names: `DN70` through `DN79` unless a test needs another name.
- The pool must be configurable from one place.
- Larger tests may extend the node-number range while keeping area 31 unless the test specifically covers inter-area routing.

## Test lab strategy

- CI uses independent tiny VMs, not containers as the primary acceptance environment, so every node has its own kernel and module state.
- Linux bridges provide raw Ethernet LANs between guests.
- Every failing network test should retain packet captures, kernel logs, DECnet counters, topology, addressing, and fault-injection seed where applicable.
- Run x86_64-to-x86_64, aarch64-to-aarch64, and mixed x86_64-to-aarch64 tests.
- A physical lab should eventually contain at least two x86_64 and two aarch64 nodes, a managed switch, and independent management access.

## Ethernet test progression

1. Two-node same-LAN adjacency and data exchange.
2. Router between two isolated LANs with no alternate path.
3. Multiple routers and alternate paths.
4. Failure, recovery, convergence, visit-count, and loop-prevention tests.
5. Mixed peers using our stack, Route20, and PyDECnet.

## DDCMP test progression

1. Frame, CRC, sequencing, ACK/NAK/REP, timer, and restart vectors.
2. Two of our kernels over a byte-stream test transport.
3. Our kernel against PyDECnet over supported DDCMP transports.
4. Our kernel against Route20 where supported.
5. Fault injection: CRC errors, lost acknowledgements, duplicates, delay, disconnect/reconnect, and sequence wrap.
6. Real asynchronous serial and later synchronous DDCMP hardware.

The test transport may carry bytes over TCP or UDP, but the DDCMP state machine remains part of the DECnet implementation rather than being implemented by the relay.

## Mixed-media acceptance

Required mixed topology includes Ethernet -> DECnet router -> DDCMP -> DECnet router -> Ethernet, with application traffic crossing the entire path. Eventually exercise NSP, Session Control, NICE/NML, CTERM, PHONE, and DAP/FAL-style file operations through mixed paths.

## User experience target

Preserve familiar command behavior where practical:

- `sethost [options] nodename`, with the traditional terminal-oriented interaction.
- `ncp` one-shot commands and interactive `NCP>` mode with DEC-style verbs and objects.
- `phone` command/switch-hook interaction.
- `dncopy` transparent DECnet file specifications and record/block transfer modes.

Compatibility belongs in userspace. The kernel ABI should remain small, versioned, and clean.

## Workflow rules

- Workflows contain short comments explaining what each gate proves and what it does not prove yet.
- Any substantive repository change must update this file in the same change set.
- The project-state gate enforces that rule so a fresh session can reconstruct current intent and next work from the repository itself.

## Current next milestone

Create the first buildable native module/UAPI/userspace control milestone, then establish automated compile checks and two-node Ethernet smoke tests. External conformance gates against Route20 and PyDECnet are required as the relevant protocol layers become functional.
