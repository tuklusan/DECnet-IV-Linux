# DECnet-IV-Linux

A minimal modern Linux distribution with native DECnet Phase IV networking.

## Project goals

- Use a small, actively maintained Linux base.
- Implement DECnet Phase IV as a fresh out-of-tree Linux kernel module.
- Do not depend on the removed legacy Linux DECnet implementation.
- Provide a versioned kernel/userspace ABI.
- Provide familiar tools such as `sethost`, `ncp`, `phone`, `dncopy`, DAP/FAL utilities, mail, task/object access and administration tools as their protocol layers become ready.
- Build reproducible bootable VM disk images for x86_64 and aarch64.
- Test first with two independent VMs and scale through 4, 8 and 16 nodes.
- Require independent-peer, mixed-architecture, routed, fault and stress testing.

## Current baseline

Phase 1 is the buildable bootstrap: UAPI version 1, configurable node identity (default 31.70 / DN70), DECnet Routing Layer EtherType receive registration, receive counters, and the `dnctl` diagnostic controller.

The distribution/image base is intentionally unset while Phase 2 is rebuilt cleanly.

## Layout

- `include/uapi/` — versioned kernel/userspace ABI
- `kernel/decnet/` — native DECnet Phase IV kernel module
- `userspace/` — DECnet command-line tools and libraries
- `tests/` — unit and interoperability tests
- `docs/` — architecture, roadmap, test lab and continuity state
- `.github/workflows/` — repository, build, reference and continuity gates

Read `docs/PROJECT_STATE.md` first when resuming work. `docs/ROADMAP.md` is the canonical task order.
