# DECnet-IV-Linux

A minimal modern Linux distribution with native DECnet Phase IV networking.

## Project goals

- Use a small, actively maintained Linux base.
- Implement DECnet Phase IV as a fresh out-of-tree Linux kernel module.
- Do not depend on the old Linux DECnet implementation.
- Provide a small versioned userspace ABI while the stack is brought up.
- Implement familiar tools such as `sethost`, `ncp`, `phone`, `dncopy`, and related utilities as their protocol layers become ready.
- Build bootable VM disk images.
- Test first with two isolated VMs and scale to sixteen nodes.
- Require x86_64 and aarch64 builds and mixed-architecture testing.

## Current baseline

The reference distribution target is Alpine Linux 3.24 with `linux-virt`, a minimal X.Org + Fluxbox GUI, and `decnet_iv.ko` built against the exact image kernel.

Phase 1 is the buildable bootstrap: UAPI version 1, configurable node identity (default 31.70 / DN70), DECnet Routing Layer EtherType receive registration, receive counters, and the `dnctl` diagnostic controller.

## Layout

- `include/uapi/` — versioned kernel/userspace ABI
- `kernel/decnet/` — native DECnet Phase IV kernel module
- `userspace/` — DECnet command-line tools and libraries
- `image/alpine/` — reference VM image construction
- `tests/` — unit and multi-node interoperability tests
- `docs/` — architecture, ordered roadmap, test lab and continuity state
- `.github/workflows/` — policy, build, test and image gates

Read `docs/PROJECT_STATE.md` first when resuming work. `docs/ROADMAP.md` is the canonical task order.
