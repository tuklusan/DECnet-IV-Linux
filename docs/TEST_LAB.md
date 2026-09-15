# Test Lab

## Purpose

The lab must prove protocol interoperability, not merely that two copies of the same implementation can talk to each other.

Every protocol milestone is tested against independent peers and on both x86_64 and aarch64.

The default isolated DECnet test pool is area 31, nodes 70 through 79. Tests may override the pool when more nodes or multiple areas are required.

## Two complementary labs

### Disposable virtual lab

This is the normal per-change test environment.

- Build x86_64 and aarch64 images natively where possible.
- Boot each node as a small VM with its own kernel.
- Connect VM NICs to Linux bridges made by the test controller.
- Carry DECnet directly as Ethernet frames. IP is not required on the DECnet test LAN.
- Give router VMs two or more virtual NICs and attach them to separate bridges.
- Capture traffic on every bridge for failure diagnosis and protocol checks.
- Use hardware virtualization when available and QEMU software emulation as the portable fallback.

A separate kernel per node is important. Network namespaces alone are not sufficient for the main tests because they share one kernel and one copy of the DECnet module state.

### Physical architecture lab

A small permanent lab validates real drivers, timing, DMA, alignment, endian assumptions, multicast filtering and actual Ethernet hardware.

Recommended shape:

- two x86_64 Linux nodes;
- two aarch64 Linux nodes;
- one test controller;
- a managed Ethernet switch with VLAN and port-mirroring support;
- separate management connectivity where practical so test-LAN failures do not remove control of a node.

The controller installs the same disk image artifacts produced by the normal build, starts tests, collects serial/console output, captures traffic from the mirror port and restores nodes after failures.

## Architecture matrix

The minimum native matrix is:

| Node A | Node B | Required |
| --- | --- | --- |
| x86_64 | x86_64 | yes |
| aarch64 | aarch64 | yes |
| x86_64 | aarch64 | yes |

Independent peer implementations are then substituted for either side. This catches assumptions that self-to-self tests miss.

## Ethernet test ladder

### E0 - Wire vectors

Check address encoding, DECnet MAC derivation, routing header forms, checksums and all packet decoders against independent vectors.

### E1 - Two nodes on one LAN

Start with two nodes on one Ethernet segment using addresses 31.70 and 31.71.

Prove:

- hello transmission and reception;
- adjacency creation and expiry;
- correct multicast and unicast destination addresses;
- short and long data reception;
- bidirectional routing-layer data delivery;
- clean recovery after one node disappears and returns.

Run the topology as implementation-to-implementation, implementation-to-DECnet/Python and implementation-to-Route20 where the peer role is supported.

### E2 - Router on two LANs

A router node has one interface on LAN A and one on LAN B. Endnodes on opposite LANs must communicate only through the router.

Prove route installation, forwarding, visit-count handling, adjacency loss, reconvergence and correct packet captures on both LANs.

### E3 - Multiple routers

Use at least two alternate paths. Remove links and routers while traffic is active and verify convergence without loops.

### E4 - Multiple areas

The default area-31 pool remains the normal test range. Dedicated Level 2 tests allocate a second configurable area so area routing can be tested without changing normal defaults.

## DDCMP architecture

DDCMP protocol processing belongs in the kernel implementation.

For automated testing the DDCMP engine should have pluggable byte-stream transports. A test transport can connect the kernel DDCMP endpoint to a small userspace relay while keeping framing, CRC, sequence, acknowledgement, retransmission and link state in the kernel.

This gives three useful backends:

1. test relay over TCP or UDP for interoperability with existing implementations and simulators;
2. asynchronous TTY/serial for physical serial testing;
3. synchronous hardware/framer support for real DDCMP links.

The relay is transport plumbing only. It must not implement DDCMP protocol state.

## DDCMP test ladder

### D0 - Frame vectors

Test start/control/data frames, header and data CRCs, sequence-number wrap, ACK, NAK, REP and malformed input.

### D1 - Two local endpoints

Connect two fresh-kernel VMs by an emulated serial link and run sustained bidirectional traffic.

### D2 - Independent peer

Connect one node to DECnet/Python using its DDCMP TCP/UDP support and exercise startup, data, errors and reconnects.

Connect separately to Route20 using its supported point-to-point transport.

### D3 - Error injection

Inject deterministic loss, delay, duplication, corruption, disconnects and reconnects. Verify counters and retransmission behavior, not just final delivery.

### D4 - Physical asynchronous serial

Connect x86_64 and aarch64 nodes through real UART/serial hardware. Repeat startup, sustained traffic and fault/reconnect tests at several line speeds.

### D5 - Physical synchronous DDCMP

Use synchronous DDCMP framing hardware or a compatible simulator/physical peer. This is the final check that the byte-stream test transport has not hidden timing or framing assumptions.

## Mixed-circuit tests

Mixed tests are essential because routing across unlike circuits is where layer boundaries are most likely to leak.

### M1 - Ethernet to DDCMP

- 31.70: x86_64 endnode on Ethernet LAN A
- 31.71: router with Ethernet LAN A plus one DDCMP circuit
- 31.72: aarch64 endnode on the DDCMP side

Send traffic in both directions and verify headers, counters and route state on all three nodes.

### M2 - DDCMP between two Ethernet LANs

- LAN A contains an implementation node plus an independent Ethernet peer.
- Router A connects LAN A to a DDCMP link.
- Router B connects the DDCMP link to LAN B.
- LAN B contains an implementation node plus a second independent peer.

Exercise endnode-to-endnode, router-to-router, NSP and application traffic across the complete path.

### M3 - Mixed implementations

Replace individual nodes with DECnet/Python, Route20 and later SIMH guests running DEC operating systems. No topology is accepted solely on implementation-to-implementation success.

## Fault matrix

Ethernet tests should include link down/up, multicast loss, packet loss, duplication, delay, reordering where meaningful, router restart and interface restart.

DDCMP tests should include corrupted header CRC, corrupted data CRC, missing ACK, duplicate data, delayed ACK, sequence wrap, carrier loss, process/peer restart and reconnect.

Mixed tests should fail one circuit while traffic is active and verify route withdrawal and recovery.

## Evidence retained for every failed test

The controller keeps:

- per-node console log;
- kernel log;
- DECnet counters and route/adjacency state;
- packet capture for every Ethernet segment;
- DDCMP byte/frame trace when enabled;
- topology and address allocation used by the run;
- random seed for any fault injection.

A failure should be reproducible from the saved topology and seed.

## Scale plan

Normal pull-request tests stop at small topologies.

Nightly or manual tests grow through 4, 8 and 16 nodes. The default 31.70-31.79 pool is extended by configuration for the 16-node case; the default itself does not change.

The 16-node topology should mix x86_64, aarch64, Ethernet, DDCMP, routers, endnodes and at least one independent implementation whenever runner capacity allows.
