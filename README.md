# DECnet-IV-Linux

A modern Linux implementation of DECnet Phase IV.

The canonical project contract is `docs/PROJECT_INSTRUCTIONS.md`. Repository state is authoritative: read `docs/PROJECT_STATE.md`, `docs/HANDOVER.md`, and `docs/ROADMAP.md` before substantive work.

## Project goals

- Implement DECnet Phase IV as a fresh out-of-tree Linux kernel module; do not revive the removed legacy Linux DECnet stack.
- Provide native Ethernet, endnode/Level 1/Level 2 routing, NSP, DECnet sockets/UAPI, Session Control, NICE/NML, and DDCMP.
- Restore the useful DECnet/Linux userspace environment: `ncp`, `sethost`/`dnlogin`, DAP/FAL tools, PHONE, mail, task/object access, daemons, libraries, and administration tools.
- Build reproducible VM images and validate x86_64, aarch64, and mixed-architecture networks.
- Scale from 2 to 16 independent VMs through routed and mixed Ethernet/DDCMP topologies, with independent implementations, real DEC peers, deterministic faults, and stress.

## References

Prefer the user's forks and pin exact tested SHAs:

- `tuklusan/Route20`
- `tuklusan/pydecnet`
- `tuklusan/LinuxDECnet`
- `tuklusan/simh`

Upstreams are comparison sources only. Respect each source's license; do not copy incompatible or unclear code into the implementation.

## Current baseline

The reference distribution is Alpine Linux 3.24 with `linux-virt`. `decnet_iv.ko` is built out of tree and managed by AKMS in Alpine; DKMS metadata covers Debian/RHEL-family lifecycle testing.

Phase 1 provides UAPI version 1, configurable identity (default 31.70 / DN70), DEC DNA Routing EtherType receive registration/counters, `/dev/decnet_iv`, and `dnctl`. It does not yet claim adjacency, routing, NSP, Session Control, or DDCMP.

Phase 2 builds the reproducible two-VM native-Ethernet lab. Current implementation status and the exact next action live only in `docs/PROJECT_STATE.md`.

## Workflow

Substantive work uses feature branches. Every substantive commit updates `docs/PROJECT_STATE.md` and the generated `docs/HANDOVER.md` together. Promote only an exact commit whose required gates are green.

Before an updated artifact is delivered or promoted, apply the SoP rule in `docs/PROJECT_INSTRUCTIONS.md`: review the complete latest disk copy untruncated, fix defects/gaps, reset after any fix, require three consecutive clean full passes, and reset after any later change.

## Layout

- `include/uapi/` — versioned kernel/userspace ABI
- `kernel/decnet/` — native DECnet Phase IV kernel module
- `userspace/` — DECnet command-line tools, daemons, and libraries
- `image/alpine/` — reference VM image construction
- `packaging/` — AKMS/DKMS lifecycle metadata
- `tests/` — unit, reference, VM, interoperability, fault, and stress tests
- `docs/` — project contract, architecture, roadmap, test lab, and continuity state
- `.github/workflows/` — repository, build, reference, state, and VM gates
