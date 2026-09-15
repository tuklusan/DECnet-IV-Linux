# Test Lab

## Purpose

The lab proves protocol interoperability and kernel robustness, not merely that two copies of one implementation communicate.

Every applicable milestone is tested on x86_64 and aarch64, with mixed-architecture cases. Independent peers use pinned project forks; later application tests include SIMH-hosted real DEC operating systems.

The default isolated pool is area 31, nodes 70 through 79. Larger and inter-area tests extend this deliberately from `tests/lab/test-addresses.env`.

## Virtual lab

The normal acceptance environment uses separate VMs so every node has its own kernel, module state, timers, and interfaces.

- Build x86_64 and aarch64 images natively where practical.
- Connect DECnet NICs to isolated Linux bridges.
- Carry DECnet directly as native Ethernet frames; IP is not required on the DECnet LAN.
- Give routers two or more DECnet interfaces on separate bridges.
- Keep provisioning/package NICs out of band.
- Capture traffic and retain node evidence on failure.
- Use hardware virtualization when available and software emulation as fallback.

Containers or namespaces sharing one kernel do not satisfy primary kernel acceptance.

## Physical lab

Before release-quality claims, repeat important tests on at least two x86_64 and two aarch64 Linux systems, a managed switch, independent management connectivity, and mirrored capture capability. Exercise real drivers, timing, DMA/alignment assumptions, multicast filtering, sustained traffic, failures, restart, and convergence.

## Architecture matrix

| Node A | Node B | Required |
| --- | --- | --- |
| x86_64 | x86_64 | yes |
| aarch64 | aarch64 | yes |
| x86_64 | aarch64 | yes |
| aarch64 | x86_64 | yes |

Independent peers substitute for either side as the protocol layer becomes available.

## Ethernet ladder

### E0 - wire vectors

Check addressing/MAC derivation, routing headers, checksums where applicable, encoders, and decoders against independent vectors.

### E1 - two nodes

Use 31.70 and 31.71 on one LAN. As Phase 3 arrives, prove hello exchange, adjacency creation/expiry, correct multicast/unicast addressing, short/long data, bidirectional delivery, and recovery after disappearance/restart.

Repeat with the pinned PyDECnet and Route20 forks where peer roles apply.

### E2 - router on two LANs

Endnodes on opposite LANs communicate only through the router. Prove route installation, forwarding, visit-count handling, adjacency loss, reconvergence, and packet correctness.

### E3 - multiple routers

Use alternate paths. Remove links/routers during traffic and verify convergence without loops.

### E4 - multiple areas

Add a second configurable area for Level 2 tests while retaining area 31 as the normal pool.

## DDCMP

DDCMP protocol state belongs in the kernel. CI may carry DDCMP bytes through a small TCP/UDP relay, but the relay must not implement framing, CRC, sequencing, ACK/NAK/REP, retransmission, timers, or link state.

Test:

- frame/control vectors, CRCs, malformed input, and sequence wrap;
- sustained bidirectional local VM links;
- pinned independent peers where supported;
- deterministic loss, delay, duplication, corruption, ACK loss, carrier loss, restart, and reconnect;
- later physical asynchronous serial and suitable synchronous hardware/peer tests.

## Mixed media

Required final routed path:

`Ethernet -> router -> DDCMP -> router -> Ethernet`

Exercise routing first, then NSP, Session Control, NICE/NML, CTERM, DAP/FAL, PHONE, mail, and task/object traffic as those layers exist. Applications must not depend on which circuit type the route crosses.

## Independent and real peers

No topology is accepted solely on self-to-self success. Use the pinned `tuklusan/Route20` and `tuklusan/pydecnet` references. As application layers mature, use `tuklusan/simh` to run suitable real DEC operating systems for terminal, file, management, PHONE, mail, task/object, and routing tests where supported.

## Fault and stress matrix

Use deterministic seeds for randomized faults and retain each seed.

Ethernet/routing faults include link/interface down/up, multicast loss, packet loss, duplication, controlled delay/reordering, router/node restart, route changes, adjacency churn, and alternate-path convergence.

NSP stress includes concurrent logical links, connection churn, sustained bidirectional traffic, long-lived sessions, flow-control pressure, delayed/missing acknowledgements, loss/duplication, retransmission, abrupt close, peer restart, and reconnect loops.

Application stress includes repeated/concurrent terminal sessions, NICE/NCP queries, PHONE users, file transfers over varied RMS/record types and sizes, interrupted DAP transfers, mail queues, task invocation, authentication failures, daemon restart, and disk-full behavior where practical.

Kernel stress fails on attributable oops/panic/WARN, invalid access, use-after-free, corruption, deadlock/lock-order failure, refcount/queue errors, stuck resources, or persistent leakage. Use Linux debug facilities/sanitizers in dedicated builds where practical.

## Evidence

For every failed applicable test retain:

- topology, node names/addresses, architecture, kernel/module/source revisions;
- pinned reference revisions;
- console and kernel logs;
- DECnet counters and adjacency/routing/NSP/DDCMP state;
- packet captures and DDCMP traces where applicable;
- application logs/result manifest;
- VM session/attempt identity;
- fault seed.

A failure should be reproducible from retained state and seed.

## Scale

Grow deliberately from 2 to 4, 8, and 16 independent VMs. Larger tests must contain real routed topologies, multiple LANs/routers, redundant and forced multi-hop paths, multiple areas when appropriate, mixed architectures, and eventually mixed Ethernet/DDCMP circuits and independent peers.

## Delivery discipline

Changes to this lab documentation and other deliverables follow the SoP rule in `PROJECT_INSTRUCTIONS.md`: full latest-disk review with no truncation, reset after any fix, three consecutive clean passes, and reset after any later change.
