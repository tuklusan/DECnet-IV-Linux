# DECnet-IV-Linux

A minimal modern Linux distribution with native DECnet Phase IV networking.

## Project goals

- Use a small, actively maintained Linux base.
- Implement DECnet Phase IV as a new out-of-tree Linux kernel module.
- Do **not** depend on the old Linux DECnet implementation.
- Provide a stable userspace ABI for DECnet applications.
- Implement essential tools such as `sethost`, `ncp`, `phone`, `dncopy`, and related utilities.
- Build bootable VM disk images.
- Test first with two isolated VMs and scale to sixteen nodes in CI.
- Target x86_64 first, then aarch64.

## Current baseline

The reference distribution target is Alpine Linux 3.24 with `linux-virt`, a minimal X.Org + Fluxbox GUI, and the new `decnet_iv.ko` module built against the exact image kernel.

Milestone 0 introduces the fresh kernel plumbing: a versioned `/dev/decnet_iv` control ABI, node identity configuration, DECnet Routing Layer EtherType (`0x6003`) receive registration, receive statistics, and the `dnctl` userspace controller. No old Linux DECnet implementation has been imported.

## Layout

- `include/uapi/` — versioned kernel/userspace ABI
- `kernel/decnet/` — native DECnet Phase IV kernel module
- `userspace/` — DECnet command-line tools and libraries
- `image/alpine/` — reference VM image construction
- `tests/` — multi-node DECnet interoperability tests
- `docs/` — protocol, architecture, and milestone notes
- `.github/workflows/` — build, test, and image CI

See `docs/MILESTONES.md` for the implementation path.
