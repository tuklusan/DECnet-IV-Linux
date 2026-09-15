# Architecture

The canonical project contract is `PROJECT_INSTRUCTIONS.md`. This document expands the technical split without changing that contract.

## Kernel

The target is a fresh out-of-tree `decnet_iv.ko` using supported Linux networking interfaces. A permanent kernel fork and the removed legacy Linux DECnet implementation are out of scope.

Kernel responsibilities grow to include:

1. DECnet Phase IV addressing and native Ethernet integration;
2. initialization, hello processing, adjacency, and circuit state;
3. endnode, Level 1, Level 2/inter-area routing, forwarding, timers, metrics, aging, visit count, and convergence;
4. NSP transport: connection state, sequencing, acknowledgements, retransmission, flow control, timers, and teardown;
5. DECnet sockets and the versioned kernel/userspace ABI;
6. Session Control and NICE/NML kernel hooks/state exposure where required;
7. DDCMP framing/state, CRC, sequencing, ACK/NAK/REP, retransmission, restart, timers, and counters;
8. correct locking, lifetime management, and concurrency.

Core routing, NSP, and DDCMP state machines remain in the kernel. Application protocols belong in userspace.

## Userspace

Userspace is built against the versioned ABI and restores the useful DECnet/Linux environment rather than only a demonstration client.

Required capability groups include:

- network management: `ncp` and NICE/NML services;
- terminal access: `sethost`, `dnlogin`, CTERM and required DTERM compatibility;
- DAP/FAL/RMS file access: `dncopy`, `dntype`, `dndir`, `dndel`, `dnsubmit`, `dnprint`, `fal`, and later `dnmount`/`dapfs`;
- PHONE: `phone` and `phoned`;
- DECnet mail in both useful directions;
- task/object access: `dntask`, `dnetd`, and object dispatch;
- service daemons and administration/configuration tools;
- maintained equivalents of `libdnet`, daemon support libraries, `libdap`, `librms`, and `libvaxdata`.

Historical functionality is either implemented, replaced by a documented modern equivalent, explicitly obsolete with justification, or deferred with a tracked dependency.

## Reference implementations and licensing

Preferred repositories are:

- `tuklusan/Route20`
- `tuklusan/pydecnet`
- `tuklusan/LinuxDECnet`
- `tuklusan/simh`

Reference revisions used by tests are pinned. Upstreams are used only for comparison and update tracking.

Every reference remains independently licensed. Verify license compatibility before source reuse; preserve required notices/provenance. If reuse is unclear or incompatible, implement the externally specified/observed protocol behavior independently.

## Distribution and module lifecycle

The reference VM uses maintained Alpine Linux 3.24 with `linux-virt`. Alpine uses AKMS. Debian/RHEL-family portability uses DKMS. A supported kernel-package upgrade must rebuild and reload the module without manual source repair.

Required CPU targets are x86_64 and aarch64.

## Testing architecture

Acceptance uses independent VMs so every node has its own kernel/module state. The test ladder grows from 2 to 4, 8, and 16 nodes and includes routed multi-LAN/multi-area networks, x86_64/aarch64/mixed CPU combinations, native Ethernet, DDCMP, mixed media, deterministic faults, and sustained stress.

Independent peers include the pinned Route20 and PyDECnet forks and, as application layers mature, SIMH-hosted real DEC operating systems.

The required mixed-media path is:

`Ethernet -> router -> DDCMP -> router -> Ethernet`

Management/provisioning networks are out of band and never count as DECnet acceptance traffic.

## Governance

`PROJECT_STATE.md` is current state, `HANDOVER.md` is generated continuity, and `ROADMAP.md` is canonical task order. Substantive work occurs on feature branches and only exact green commits are promoted.

Every changed deliverable follows the SoP rule in `PROJECT_INSTRUCTIONS.md`; automated tests do not replace the required three consecutive clean full-file reviews.
