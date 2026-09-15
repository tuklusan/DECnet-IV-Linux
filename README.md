# DECnet-IV-Linux

A minimal modern Linux distribution with native DECnet Phase IV networking.

## Project goals

- Build DECnet Phase IV as a fresh out-of-tree Linux kernel module, not the removed legacy stack.
- Provide a versioned kernel/userspace ABI and the useful DECnet/Linux tool environment.
- Build reproducible x86_64 and aarch64 images.
- Test on independent VMs, independent peers, routed/mixed-media topologies, faults and stress.

## Current baseline

Phase 1 provides the retained bootstrap: configurable node identity (default 31.70 / DN70), DECnet Routing Layer EtherType registration/counters, `dnctl`, and native x86_64/aarch64 build gates.

Phase 2 uses Ubuntu Base 26.04.1 LTS. The official amd64 and arm64 rootfs tarballs are 33 MiB and are pinned by SHA-256. The VM lab builds the root disk before boot and direct-boots its exact kernel/initrd, so there is no installer, cloud provisioning layer, firmware dependency or management NIC in the acceptance path.

Phase 3 is in progress. UAPI version 2 adds DECnet Ethernet address handling, router/endnode hello parsing and generation, adjacency state/expiry, extended counters, and `dnctl adjacencies`. Independent wire vectors are checked against the pinned Route20 and PyDECnet forks before live interoperability gates.

## Layout

- `include/uapi/` — versioned kernel/userspace ABI
- `kernel/decnet/` — native DECnet Phase IV kernel module
- `userspace/` — DECnet command-line tools and libraries
- `image/ubuntu-base/` — pinned rootfs metadata and deterministic image builder
- `tests/` — unit and interoperability tests
- `docs/` — architecture, roadmap, test lab, handover and continuity state
- `.github/workflows/` — repository, build, reference, continuity and VM gates

Start with `docs/HANDOVER.md` when resuming work. It points to the authoritative project state and ordered roadmap.
