# Implementation Roadmap

This is the canonical execution order for DECnet-IV-Linux. `PROJECT_INSTRUCTIONS.md` is the project contract. Later phases never remove earlier acceptance gates.

## Test and delivery discipline

- Prefer `tuklusan/Route20`, `tuklusan/pydecnet`, `tuklusan/LinuxDECnet`, and `tuklusan/simh`; pin exact revisions when used by a gate. Upstreams are comparison sources only.
- Run every useful, internally consistent reference test unmodified. If a reference revision contradicts its own suite, document it and hard-pin the last internally consistent revision while retaining the newer revision separately for live reference work.
- Prefer native DECnet on raw Ethernet or native DDCMP media. DECnet-over-IP must not substitute for unfinished native layers.
- Stress each layer for node count, traffic volume, churn, loss, restart, route changes, reconnects, resource lifetime, and long-duration operation.
- Management networks are out of band and never carry DECnet acceptance traffic.
- Before delivery/promotion, apply the SoP rule: complete untruncated latest-disk review, reset after any fix, three consecutive clean passes, and reset after any later change.

## Phase 0 - repository continuity and reference discipline

Exit criteria:

- repository policy and continuity gates are active;
- every substantive commit refreshes `PROJECT_STATE.md` and generated `HANDOVER.md`;
- feature branches are used and only exact green commits are promoted;
- preferred forks and SHA pins are recorded; upstreams are comparison-only;
- licensing boundaries are checked before source reuse;
- Route20 and PyDECnet baselines are green at their pinned revisions;
- the SoP delivery rule is documented and followed.

Status: substantially complete.

## Phase 1 - buildable kernel and userspace bootstrap

Deliver:

- versioned UAPI;
- out-of-tree `decnet_iv.ko`;
- configurable local identity, default 31.70 / DN70;
- DEC DNA Routing EtherType receive registration/counters;
- `dnctl`;
- native x86_64 and aarch64 build gates;
- Alpine AKMS and Debian/RHEL-family DKMS metadata;
- address/UAPI unit tests.

Exit criteria: module, userspace bootstrap, lifecycle metadata, and unit tests build cleanly on both architectures.

## Phase 2 - reproducible VM image and two-node lab

Deliver:

- pinned Alpine base images;
- NoCloud first-boot provisioning;
- AKMS-managed module install/rebuild;
- DN70 and DN71 as separate VMs on isolated native Ethernet;
- out-of-band management NICs only for provisioning;
- retained serial logs, kernel evidence, counters, and pcap;
- resumable known VM sessions.

Exit criteria: both VMs independently boot the installed kernel, load the AKMS-managed module, exchange deliberate EtherType `0x6003` frames on the isolated LAN, and report non-zero receive counters.

## Phase 3 - Ethernet initialization and adjacency

Deliver address/MAC handling, initialization, endnode/router hellos, adjacency state, and expiry timers.

Exit criteria: local peers form/age adjacencies correctly and repeat applicable behavior with the pinned PyDECnet and Route20 forks.

## Phase 4 - Phase IV routing

Deliver endnode, Level 1, Level 2/inter-area routing, routing/forwarding databases, metrics, visit count, aging, convergence, and multi-LAN topologies.

Exit criteria: forced routed paths work; failures converge without loops; independent-peer interoperability passes.

## Phase 5 - NSP transport and DECnet sockets

Deliver NSP connection state, sequencing, ACK/retransmission, flow control, timers, teardown, and native DECnet socket integration.

Exit criteria: reliable sustained bidirectional logical links pass load, reconnect, loss, churn, peer restart, and long-duration tests against independent peers.

## Phase 6 - Session Control and NICE/NML

Deliver Session Control object dispatch and useful NICE/NML executor/node/circuit/line/counter management.

Exit criteria: scripted and interactive local/remote management works under sustained native DECnet load.

## Phase 7 - complete DECnet/Linux userspace

Implement each capability when its lower-layer dependencies are ready. Account explicitly for the useful `tuklusan/LinuxDECnet/dnprogs` inventory.

Deliver at least:

- `ncp`;
- `sethost`, `dnlogin`, `ctermd`, `rmtermd`, CTERM and required DTERM compatibility;
- DAP/FAL/RMS: `dncopy`, `dntype`, `dndir`, `dndel`, `dnsubmit`, `dnprint`, `fal`, then `dnmount`/`dapfs`;
- PHONE client/server: `phone`, `phoned`;
- DECnet mail including the roles of `vmsmaild` and `sendvmsmail`;
- `dntask`, `dnetd`, and general object/task dispatch;
- useful diagnostics such as `dnping` and maintained equivalents of `dts`/`dtr`;
- administration/configuration roles including `startnet`, `decnetconf`, `setether`, `dnroute`, NML services, and deferred legacy tunnel compatibility;
- maintained equivalents of `libdnet`, daemon support libraries, `libdap`, `librms`, and `libvaxdata`.

Every historical capability is implemented, replaced by a documented modern equivalent, explicitly obsolete with justification, or deferred with a tracked dependency.

Exit criteria: useful application interoperability passes repeatedly and concurrently against independent implementations and suitable real DEC peers.

## Phase 8 - DDCMP

Deliver kernel DDCMP framing/state, CRC, ACK/NAK/REP, sequencing, retransmission, timers, restart/recovery, counters, and a CI byte-stream carrier that does not implement protocol state.

Exit criteria: normal and deterministic fault-injected links recover correctly; applicable PyDECnet/Route20 interoperability passes; later physical serial tests follow.

## Phase 9 - mixed-media routing and applications

Required topology:

`Ethernet -> DECnet router -> DDCMP -> DECnet router -> Ethernet`

Exercise routing, NSP, Session Control, NICE/NML, CTERM, DAP/FAL, PHONE, mail, and task/object access as available.

Exit criteria: application traffic traverses mixed media in both directions and survives link/circuit failure and recovery.

## Phase 10 - scale, portability, physical systems, and release

Deliver:

- 4, 8, and 16-node routed/stress topologies;
- x86_64/x86_64, aarch64/aarch64, and mixed-architecture cases;
- Alpine, Debian-family, and RHEL-family lifecycle/portability tests;
- real supported kernel upgrades proving automatic module rebuild;
- SIMH-hosted real DEC peers and, where practical, more than one DEC OS family;
- physical x86_64/aarch64 Ethernet lab and later physical DDCMP;
- reproducible QCOW2/RAW images, packages, checksums, manifest, source/kernel/reference revisions.

Exit criteria: all applicable build, conformance, routed, mixed-media, fault, stress, kernel-lifetime, portability, physical-hardware, release-reproducibility, repository, and SoP gates pass.
