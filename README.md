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

## Planned architecture

- `kernel/decnet/` — native DECnet Phase IV kernel module
- `userspace/` — DECnet command-line tools and libraries
- `image/alpine/` — minimal Linux image construction
- `tests/` — multi-node DECnet interoperability tests
- `docs/` — protocol and architecture notes
- `.github/workflows/` — build, test, and image CI

## Status

Bootstrap repository. No DECnet implementation has been imported.

The kernel networking stack will be a fresh implementation guided by DECnet Phase IV specifications and interoperability testing. Existing implementations may be studied for externally observable behavior, but code will not be copied into the kernel module unless licensing is explicitly compatible.
