# Consolidated Pre-Production Test Procedure

## Purpose

This is the single pre-production acceptance procedure for DECnet-IV-Linux. It combines tests derived from the Linux implementation, the existing E0-E4 and D0-D5 lab plan, relevant tests and behavior from the exact pinned Route20, PyDECnet, LinuxDECnet and SIMH references, and Linux-specific lifecycle, concurrency, fault, security, endurance and recovery testing.

Tests run from cheap deterministic checks to destructive, long-running routed and mixed-media soak tests. Positive, negative, stress and recovery cases are equally mandatory when they apply. A self-to-self pass is useful development evidence but never substitutes for an independent peer.

A documented test that is not actually executed does not count as green. A manual or physical test may satisfy a gate only when its exact procedure and evidence are retained.

## Authority and exact revisions

Repository state, `docs/HANDOVER.md`, `docs/ROADMAP.md`, `docs/ARCHITECTURE.md`, `docs/TEST_LAB.md` and `tests/reference/refs.env` remain authoritative.

| Reference | Revision | Use |
| --- | --- | --- |
| Route20 | `b94115b2615c6463d1f006924ceeadde8e2d4367` | independent Ethernet/routing behavior and live peer |
| PyDECnet behavior/live | `a7194be8d72dea6f9eb4f77083f056f53e80df58` | independent live peer |
| PyDECnet tests | `9a844987bf3a1450632dee8d37e60a23a453bad3` | protocol vectors/state machines and native test baseline |
| LinuxDECnet | `ff39eef045d1e4b7b72a3d40111e89c07a473398` | userspace/API and VAX-data conversion comparison |
| SIMH | `5b73b1032b52d19bf80752ea4d9cbbdc92e7b5e0` | real DEC operating-system peer host and simulator health |

A reference result proves only that reference. It does not prove this implementation.

## De-duplication and traceability

Each acceptance invariant has one canonical `PP-xx` home. Two cases are duplicates only when they prove the same invariant with the same failure meaning. Architecture, role, media, peer implementation, topology, first-start/restart behavior, clean/faulted transport, size boundary, vCPU count, kernel configuration and driver are dimensions, not duplicates.

The stronger case wins when consolidating duplicates: exact vector plus legal boundaries plus malformed boundaries plus state/recovery assertions is preferred over a simple happy path. Every original source remains recorded against the canonical case.

Every upstream test is classified as one of:

- **mapped** — a canonical `PP-xx` case proves the same invariant;
- **reference-health** — run at the exact pin but not used as a Linux semantic claim;
- **feature-gated** — becomes a blocking positive and negative test when the feature is claimed;
- **harness** — support code, not an independent semantic test.

No upstream test may disappear because it looks inconvenient.

## Feature gating

A test may be feature-gated only while its feature is outside the release claim. Once a release claims that feature, all applicable positive cases, negative families, stress cases and recovery assertions in this document become blocking.

`Not implemented`, `not automated`, `flaky`, `manual later` and `could not reproduce` are not pass results.

## Mandatory negative-test contract

Every applicable layer and user-visible feature must exercise every relevant family below:

1. **Encoding and bounds** — short, truncated, overlong, zero/empty where illegal, count/range overflow, invalid length, checksum/CRC, unknown type, reserved bits/values, padding and alignment.
2. **Identity and destination** — wrong node, area, MAC, multicast group, station, object, circuit, interface, source, destination and duplicate identity.
3. **Sequence and state** — stale, duplicate, future, out-of-order, wraparound, exact half-space ambiguity where defined, unsolicited control, illegal transition and state rollback.
4. **Timing and liveness** — just-before/exact/just-after boundaries, expiry, timeout, silence, delayed input, scheduler delay, pause/resume, restart and reconnect.
5. **Faulted transport** — deterministic loss, duplication, reordering, delay, corruption, truncation, disconnect/reconnect and asymmetric failure.
6. **Resources and backpressure** — adjacency/route/session/socket/object/table/queue saturation, allocation failure, disk/inode exhaustion, full windows, buffer pressure and recovery after pressure clears.
7. **Lifecycle and concurrency** — load/unload, open/close, interface/register/unregister, identity change, peer restart, timer/workqueue races, simultaneous operations and cross-CPU execution.
8. **UAPI and permissions** — wrong ABI version/size, invalid command/index/argument, short copy, invalid pointer where safely injectable, compatibility ABI, wrong state and insufficient privilege.
9. **Topology churn** — link/router/circuit loss, alternate path, stale route expiry, route withdrawal, repeated reconvergence and overlapping changes under traffic.
10. **Application/storage failure** — wrong credentials, denied/unknown object, daemon death, cancellation, interrupted transfer, read-only/full storage, bad file metadata and process restart.
11. **Harness/evidence failure** — dead capture/logger, missing/truncated evidence, bad pass marker, wrong hash, inactive fault injector, wrong source revision, exhausted evidence storage and corrupted checkpoint.
12. **Adversarial load** — malformed/control floods, spoofing, churn floods and resource pressure while valid traffic must continue within documented service limits.

For every negative case, pass requires all applicable outcomes: bounded/rejected behavior as specified; no panic/oops/test-caused warning/lockup/use-after-free/corruption; no stale state beyond defined lifetime; externally visible counters/errors consistent with observed traffic; subsequent valid traffic succeeds or reconverges; resources return to their baseline or a documented bounded envelope; and the injected failure is proven to have happened.

## Production matrix

Run the applicable canonical stages across these dimensions. Pairwise coverage is acceptable only for non-critical combinations; protocol-state, lifetime, concurrency and release-image dimensions require the explicit combinations below.

| Axis | Required production values |
| --- | --- |
| CPU architecture | x86_64/x86_64, aarch64/aarch64, x86_64→aarch64, aarch64→x86_64 |
| vCPU | 1 plus representative 2, 4 and 8 vCPU SMP cases; concurrency stress must use more than one vCPU |
| VM count | 2, then 4, 8 and 16 independent VMs |
| Kernel/toolchain | oldest and newest supported maintained kernel lines; GCC and Clang where supported; clean rebuilds |
| Kernel diagnostics | KASAN, KCSAN, UBSAN, lockdep, kmemleak and KFENCE subsets as applicable |
| Node role | endnode, Level 1 router, Level 2 router |
| Media | Ethernet, DDCMP, then mixed Ethernet/DDCMP |
| Peer | Linux peer, pinned Route20, pinned PyDECnet, applicable LinuxDECnet userspace, SIMH-hosted DEC OS, physical DEC peer where available |
| Ethernet driver/path | virtio plus at least one second emulated or physical driver; offloads on/off where relevant; multi-NIC |
| Topology | single LAN, two-LAN router, alternate routers, multi-area, mixed media |
| Traffic | idle, quiet-after-burst, unidirectional, bidirectional, microburst, sustained bulk and concurrent sessions |
| Faults | each negative family alone, then selected overlapping faults under load |
| Boot/lifecycle | cold boot, warm reboot, reload, late NIC, initially-down link, repeated reboot/restart |

Ordinary lab addressing remains area 31, nodes 70-79. Larger and multi-area tests use explicit configuration rather than accidental address reuse.

## Exact boundary catalogue

Boundary testing is not satisfied by `minimum/maximum` prose. Applicable tests must include the exact implementation/protocol boundaries and one value on either side:

- DECnet area: 0 invalid, 1, 63, 64 invalid;
- DECnet node: 0 invalid, 1, 1023, values outside the address field invalid;
- node name: 0 invalid, 1 and 6 legal characters, 7 invalid, invalid punctuation, lowercase normalization and termination;
- router priority: 0, 127, 128 invalid;
- hello timer: zero/fallback semantics where defined, 1 and 65535, plus overflow-safe lifetime behavior;
- Ethernet Routing Layer declared length: 0 invalid, shortest legal, exact payload, largest legal block, one too large, truncated payload and legal trailing Ethernet padding;
- router list: 0, 1, 32, 33 and 34 entries, malformed entry size, duplicate entry and invalid entry address/priority;
- adjacency storage: 63, 64 and attempted 65th total entries, with reclamation after expiry;
- router admission: 32, 33 and 34 peers on one interface, including equal-priority node-address tie replacement;
- every sequence space: zero, last value, wrap, duplicate, previous/future and exact half-space ambiguity when ordering is undefined;
- every buffer/window/segment/file-size limit introduced later: zero, one, one-below, exact limit and one-above.

## Ordered pre-production stages

### PP-00 — provenance, source health, builds and reproducibility

**Goal:** prove the exact sources and artifacts before protocol behavior is trusted.

Required positive cases:

- record the exact DECnet-IV-Linux commit and complete source-tree identity;
- verify every reference SHA against `tests/reference/refs.env`;
- native module/userspace/unit build on x86_64 and aarch64;
- build with the oldest and newest supported maintained kernel/header baseline;
- build with GCC and Clang where supported; run kernel `W=1`/`C=1` or equivalent static-analysis checks appropriate to the tree;
- build pinned Route20;
- run the complete unmodified pinned PyDECnet native test discovery;
- build the applicable pinned LinuxDECnet tools/libraries and run `dnprogs/libvaxdata/src/test.c` as reference-health; when VAX/RMS conversion is claimed this test also maps to PP-07 and becomes blocking semantic evidence;
- build the exact pinned SIMH DEC-host target with tests enabled. The pinned makefile normally runs per-simulator tests when available; retain the exact target/test transcript. Tests for the selected VAX/PDP-11/DEC CPU, storage, Ethernet, serial/timer path used by PP-11 are blocking reference health; unrelated simulator machines remain reference-health only;
- build the image twice from identical inputs and compare the documented reproducibility outputs;
- verify base image, kernel, initrd, module, userspace, overlay and checkpoint hashes;
- resume only a checkpoint matching architecture, exact source revision and acceptance mode.

Mandatory negatives:

- missing/wrong pin, source revision or dependency;
- bad/partial download and checksum mismatch;
- unavailable/bad package snapshot or failed certificate bootstrap;
- full filesystem, full inode table and insufficient output space during image construction;
- interrupted extraction/build/qemu-img conversion and rejection of partial artifacts;
- corrupt/missing checkpoint member or hash;
- resume architecture/revision/mode mismatch;
- evidence directory unavailable/full/read-only.

**Pass:** every mismatch and incomplete artifact fails closed; no prior-candidate evidence is reused.

### PP-01 — pure vectors, UAPI layout and codecs

**Goal:** catch byte-level defects before a VM is involved.

Canonical coverage includes UAPI layout/version and address composition; standard node MAC mapping; Ethernet length framing and padding; Phase III/IV init/hello/data/routing-update forms as implemented; router/endnode hellos; routing checksums; DDCMP CRC/framing; sequence arithmetic; NSP packets; Session Control; NICE/NML; DAP/RMS data conversions when implemented; and all exact boundary catalogue cases.

Sources include local `test_uapi.c`, local `test_phase3.c`, E0/D0, and relevant PyDECnet `test_common`, `test_crc`, `test_modulo`, `test_packet`, `test_routingpacket`, `test_nsppacket`, `test_sessionpacket`, `test_nicepacket`, `test_framer` and `test_ddcmp`.

Mandatory malformed vectors include null/short input, nested/invalid padding, bad count/length/checksum/CRC, unknown type, reserved values, duplicate list entries, self hello, source MAC/address mismatch, illegal destination class and one-bit mutations around known-good vectors.

Fuzz protocol decoders/encoders with a retained deterministic corpus and minimized regressions. Every discovered crash/hang/OOB/state mutation becomes a permanent regression vector.

**Pass:** exact legal bytes and exact errors match; malformed input never escapes bounds or mutates state unexpectedly.

### PP-02 — Linux kernel/module/UAPI lifecycle

**Goal:** test Linux behavior independent implementations cannot cover.

Required positives and boundaries:

- load/unload and failed-init unwind; thousands of load/unload cycles in stress subsets;
- configure/read identity, stats and adjacency enumeration;
- native 64-bit UAPI plus 32-bit compatibility userspace on 64-bit kernels where the architecture supports it, with layout and errno parity;
- privilege enforcement and device permissions;
- timer/workqueue start/cancel/rearm;
- role-correct unicast/multicast filter ownership;
- runtime identity change across one and multiple Ethernet devices;
- device existing before module load and registered after module load;
- interface down/up, rename, unregister/re-register and late appearance;
- non-Ethernet and loopback devices ignored as intended;
- `init_net` isolation: traffic/devices in another network namespace must not populate or mutate global DECnet state; moving a device between namespaces must not leak filters or adjacency state;
- nonlinear/fragmented/cloned receive buffers: split length field/payload across fragments, non-zero headroom/alignment and legal trailing padding;
- adjacency/router saturation and exact replacement rules from the boundary catalogue;
- duplicate DECnet node/MAC identity collision behavior;
- concurrent stats read/reset and adjacency enumeration during churn;
- clean teardown leaves no filter, timer, work, adjacency or device state behind.

Mandatory failpoint/race cases:

- invalid ioctl, version, index, pointer/copy and privilege;
- identity change racing RX, timer aging, stats and device events;
- filter-add failure at each unicast/multicast stage and on first/middle/last device during identity change; assert exact rollback and continued old identity operation;
- unload with open control fd, ioctl/close/unload races, receive during unload;
- interface unregister while receive/timer work is active;
- memory-allocation failure where injectable;
- counter near-wrap through test hooks where practical;
- jiffies/timer wrap through test hooks where practical.

SMP is mandatory: run concurrent RX/timer/ioctl/netdevice churn on 2/4/8 vCPU guests, with CPU affinity and migration. Exercise multiple active interfaces/queues. CPU hotplug is included where the supported kernel/VM permits it.

Diagnostic subsets must include KASAN, KCSAN, UBSAN, lockdep, kmemleak and KFENCE as appropriate. Static checks include compiler warnings and sparse/smatch or maintained equivalents when available.

**Pass:** deterministic errno/drop behavior, exact rollback, no stale state, no diagnostic finding and successful valid reuse after faults.

### PP-03 — two-node Ethernet adjacency (E1)

**Goal:** prove the smallest real DECnet LAN using two independent VMs.

Required positives:

- standard EtherType and two-byte little-endian length;
- protocol-derived source MAC deliberately different from NIC MAC;
- router/endnode discovery as applicable;
- router INIT then UP only under the expected listing/priority rule;
- designated-router election after the specified startup delay;
- role-correct All-Routers, All-Level-2-Routers and All-Endnodes behavior;
- listener expiry and recovery;
- bidirectional protocol unicast delivery;
- module and peer restart recovery;
- primary NIC MAC change while loaded, preserving DECnet unicast reception;
- single- and multi-vCPU variants; virtio and at least one second driver/path before release.

Mandatory negatives/boundaries:

- wrong source MAC, wrong destination and wrong multicast class;
- same-address/MAC duplicate peer;
- peer omits local router, changes priority/type/address or violates area rules;
- cross-area Level 1 rejection and permitted Level 2 behavior;
- 3.1x listener timer just before, at and after expiry;
- designated-router decision just before, at and after the startup-delay boundary; equal-priority node-address tie and live handover;
- link down/up, peer silence, reboot and hard VM kill;
- malformed/truncated/oversized/random frames while valid hellos continue;
- promisc/allmulti exposure must not cause acceptance of role-invalid destinations;
- offloads on/off and MTU change around supported limits.

**Pass:** peer/state/capture/counters agree, invalid traffic cannot create stale state, and valid traffic survives or reconverges.

### PP-04 — independent Ethernet peer interoperability

**Goal:** remove shared-implementation blind spots.

Run Linux both directions against exact pinned Route20 and pinned live PyDECnet for every claimed Ethernet role/phase; use applicable LinuxDECnet user behavior and later real DEC peers.

Prove adjacency, framing, multicast, protocol unicast, forwarding, role/area rules, boundary frames and restart. Repeat mandatory malformed length/list/type/destination, changed peer identity, silence, hard restart, unsupported message and MTU cases against the independent path where the peer permits controlled injection.

**Pass:** independent implementations reach compatible state and exchange valid traffic in both directions without one-off code/configuration changes.

### PP-05 — routed Ethernet, E2 through E4

**Goal:** prove full Phase IV routed Ethernet.

**E2:** two LANs through one router: adjacency each circuit, route installation, forwarding, visit/hop limits, circuit loss and reconvergence.

**E3:** alternate routers: route selection, designated-router/preferred-router behavior as applicable, live failover, stale-route expiry, no loops and return-path correctness.

**E4:** multiple areas: Level 1/Level 2 adjacency restrictions, area routing, Level 2 multicast, update propagation, inter-area forwarding and return traffic.

Consolidates relevant PyDECnet `test_routing`, `test_route_eth`, `test_route_ptp` and `test_routingpacket` behavior.

Mandatory negatives/stress:

- bad update checksum/count/start/range and update from wrong role/adjacency;
- duplicate/stale/withdrawn/conflicting routes;
- equal-cost/tie and metric boundary behavior;
- visit/hop boundary and loop attempts;
- adjacency/router table saturation and route-table saturation;
- one and multiple link/router failures during bidirectional traffic;
- rapid repeated topology churn and thundering-herd router restarts;
- malformed routing-update flood while valid routes/traffic must continue;
- asymmetric faults and route flaps.

Measure and retain convergence time distribution and packet loss during each fault. Thresholds are declared before release testing, not invented after seeing results.

**Pass:** no loop or stale route beyond defined timers, bounded reconvergence and consistent forwarding/counters.

### PP-06 — NSP and Linux socket behavior

**Goal:** prove transport semantics and Linux socket lifetime.

Positive cases include listen/connect/accept; nonblocking connect/accept; initialization/confirmation; segmentation and all buffer boundaries; ACK/delayed ACK/NAK/retransmit; flow control; backpressure; keepalive/inactivity; interrupt/out-of-band path where exposed; orderly disconnect/reject/abort; half-close/shutdown where supported; poll/epoll; socket options; fork/dup/process-exit semantics; concurrent sessions and bidirectional bulk data.

Consolidates PyDECnet `test_nsp`, `test_nsppacket`, `test_modulo` and relevant `test_timers`.

Mandatory negatives/stress:

- stale/future/duplicate/reordered sequence/ACK, repeated sequence wrap and half-space ambiguity;
- deterministic loss/duplication/reorder/corruption/delay, including lost control/ACKs;
- malformed controls/data and spoofed connection identifiers;
- full/zero windows, sender/receiver stall, sustained backpressure and queue exhaustion;
- connection/socket/object exhaustion and recovery;
- simultaneous connect/close/abort/restart; EINTR/signals; accept/close/poll races; peer hard death;
- syscall fuzzing once the socket ABI exists, with minimized regression cases;
- many-client fairness: one abusive or blocked connection must not starve independent valid sessions beyond declared limits.

**Pass:** reliable ordering/delivery holds, failure semantics are correct, resources return to baseline and no race corrupts socket/NSP state.

### PP-07 — Session Control, NICE/NML and userspace

**Goal:** prove the user-facing DECnet/Linux environment claimed by the release.

Positive cases as implemented include Session Control object selection/connect data; authentication/access; NICE/NML permitted operations; node-name/host mapping; `ncp`; `sethost`/`dnlogin`; DAP/FAL/RMS copy/type/directory behavior; PHONE; mail; task/object access; daemons/libraries/diagnostics.

Consolidates relevant PyDECnet `test_session`, `test_sessionpacket`, `test_nicepacket`, `test_host`, `test_event`, `test_mirror`, `file_app_exerciser.py`, `module_app_exerciser.py`, applicable LinuxDECnet behavior and, once VAX/RMS conversion is claimed, LinuxDECnet `dnprogs/libvaxdata/src/test.c` vectors.

Mandatory application/storage cases:

- wrong credentials, explicit denial, unknown/disabled object and insufficient privilege;
- malformed connect/NICE entity/operation/parameter;
- daemon/application crash, restart, signal and cancellation during requests;
- interrupted file transfer and resume/retry semantics if provided;
- zero, one-byte, boundary, large and binary files with end-to-end hashes;
- DEC record/attribute/text/binary conversion vectors and round trips where claimed;
- disk full, inode full, quota, read-only destination, permission changes and partial-output cleanup;
- peer restart during interactive and bulk operations;
- many concurrent clients, terminal interruption and locale/character handling where exposed;
- no credentials/secrets written to ordinary acceptance evidence.

**Pass:** exit status/protocol reply is deterministic, access control holds, files/data are correct, failed work does not poison the next request and partial artifacts follow documented semantics.

### PP-08 — DDCMP, D0 through D5

**Goal:** prove the point-to-point layer from pure vectors to physical media.

**D0:** CRCs, sequence wrap, ACK/NAK/REP, maintenance/control frames, framing and malformed vectors.

**D1:** two fresh-kernel independent VMs over emulated serial/byte stream.

**D2:** independent DDCMP peer.

**D3:** deterministic loss, duplication, reorder, delay, corruption, noise, disconnect/reconnect and asymmetric fault injection.

**D4:** physical asynchronous serial when claimed.

**D5:** physical synchronous DDCMP or compatible peer when claimed.

Consolidates PyDECnet `test_ddcmp`, `test_framer`, `test_modulo` and point-to-point routing cases.

Mandatory cases include bad header/data CRC; short/oversized/noisy frame; one-byte and randomized stream chunking; wrong station/address/type/control; duplicate/out-of-order/wrapped sequence; lost/repeated/delayed ACK/NAK/REP; station/address collision; long idle then traffic; disconnect/reconnect under data; maintenance/data misuse; and, on supported physical links, rate/baud, parity/break/carrier/flow-control and unplug/replug behavior.

**Pass:** retransmit/recovery is bounded, sequence state remains correct and no stale/duplicate application data is delivered.

### PP-09 — mixed-media routed network

**Goal:** prove Ethernet and DDCMP together.

Minimum path: Ethernet endnode → router → DDCMP → router → Ethernet endnode. Add alternate paths, multiple areas and independent peer components as implementation permits.

Run NSP and application traffic end-to-end, boundary payloads, route change and recovery. Inject DDCMP loss/corruption while Ethernet-originated traffic runs; Ethernet failure while DDCMP-originated traffic runs; router restart; asymmetric faults; MTU/path boundaries; and repeated route churn.

**Pass:** no loop, duplicate application delivery or stale path after convergence.

### PP-10 — harness, evidence and false-green tests

**Goal:** prove the test system can detect a bad system. This stage is mandatory before relying on a new or materially changed harness.

Deliberately break one expected invariant at a time and require the gate to fail:

- corrupt a known vector, expected hash, pass marker or checkpoint member;
- use wrong source revision/architecture/mode;
- inject wrong source/destination MAC or suppress required packets;
- kill packet capture or logging before/during the test;
- fill evidence filesystem/inodes and truncate/corrupt logs/captures;
- disable a requested fault injector and prove the run fails because the expected injected-event count is missing;
- corrupt the fault schedule/seed manifest;
- omit one required evidence file;
- force a guest to print a pass-like marker without satisfying host-side wire/state evidence;
- retry a failed test and verify the first failure evidence remains preserved.

Every test that requests a fault must record an injection counter/event log and assert the requested fault actually occurred. Evidence completeness is a blocking assertion; `warn` for missing production evidence is not a release pass.

**Pass:** each deliberately sabotaged run fails for the expected reason, and a subsequent clean run passes.

### PP-11 — stress, performance and endurance ladder

**Goal:** prove durable behavior, not only correctness in short runs.

| Level | Minimum production work |
| --- | --- |
| S0 deterministic | 2 VMs; all applicable lower-stage happy paths and mandatory negatives once |
| S1 churn | 2-4 VMs; at least 100 combined module/interface/identity/peer/reboot/topology cycles while traffic runs |
| S2 sustained faults | 4-8 VMs; at least 1 hour and at least 10,000 deterministic injected fault events across applicable classes |
| S3 heavy | 8-16 VMs; at least 8 hours, at least 100,000 injected events, concurrent sessions/bulk traffic, table/queue pressure and multi-vCPU subsets |
| S4 release soak | 16 independent VMs; at least 24 hours; mixed architecture/media where available; repeated peer/router/application restarts; busy and quiet windows |
| S5 endurance | 16 independent VMs on a persistent lab controller; at least 72 hours; mixed architectures, multi-vCPU subset, independent peers, alternating high-load/fault and long quiet periods |
| S6 first-production/core-change endurance | at least 168 hours/7 days for the first production release and after material core state-machine, lifetime/concurrency, routing, NSP, DDCMP, major-kernel or NIC-driver-baseline changes |

Duration alone is insufficient: each level must also meet its event/count requirements. Lowering a duration or count requires a recorded release-policy change before the candidate run; silently stopping early is failure.

Across stress/endurance:

- repeat sequence-number wraps many times, not once;
- drive adjacency, route, socket/session and queues to documented limits and back;
- combine malformed/control floods with valid control/data traffic and measure fairness/liveness;
- use microbursts, sustained traffic and long idle/quiet periods;
- repeatedly cold boot, reboot, reload and hard-kill selected guests;
- pause/resume selected VMs and test timer/recovery behavior;
- move work across CPUs and exercise SMP receive/timer/ioctl/netdevice concurrency;
- sample memory/slab/object/timer/work/adjacency/route/socket counts throughout;
- after each pressure period quiesce the system and require resources to return to baseline or a predeclared bounded envelope with no monotonic growth;
- retain p50/p95/p99 latency, throughput, CPU/memory use, connection setup and reconvergence distributions for claimed services.

Performance acceptance thresholds are declared per release/profile before testing. There is no universal magic throughput number. Any unexplained regression versus the approved baseline blocks release until explained or explicitly accepted.

**Pass:** no crash/lockup/leak/unbounded growth/permanent state loss, service remains within declared fairness/performance limits, and recovery continues after long quiet as well as busy periods.

### PP-12 — real peers and exact release image

**Goal:** prove the actual candidate image against systems that do not share this implementation.

Use exact pinned SIMH to host available real DEC operating systems and physical DEC systems where available. Prefer more than one DEC OS/version/role when practical. Use the exact release QCOW2/RAW artifact, not a repaired development filesystem.

Positive cases include cold/warm boot; NIC early/late/initially down; configured startup; adjacency/routing; NSP/Session/NICE; each claimed application/tool; service/module restart; repeated reboot; release-image hash/reproducibility and, where relevant, physical mixed-CPU/media operation.

Mandatory negatives include peer reboot/hard stop during session/transfer, outage/restoration, wrong credentials/object/node, interrupted transfer, circuit/router loss and recovery. No one-off patch or manual state repair may be introduced after the release image hash is fixed.

**Pass:** the exact candidate image interoperates and recovers with retained evidence.

## Timing, scheduler and clock-specific tests

Timers deserve their own mandatory treatment because short happy-path tests miss them:

- hello/listen expiry just before, at and after the 3.1x boundary;
- designated-router startup delay just before, at and after its boundary;
- zero/fallback and maximum legal hello timer values without arithmetic overflow;
- CPU saturation/workqueue delay while timers expire;
- VM pause/resume and large scheduling stalls;
- timer cancel/rearm concurrent with unload, identity change and device removal;
- clock/jiffies wrap through test hooks where practical;
- long-idle behavior during S5/S6 followed by immediate valid traffic.

Pass requires protocol time, not wall-clock wishful thinking, to match the specified tolerance and no stale timer/work item after teardown.

## Ethernet/device-path tests

Before production release, cover virtio plus at least one independent Ethernet driver/path. Test offloads on/off where they can alter skb shape; MTU changes; multiple NICs; bridge/bond/VLAN/macvlan only when such deployment is supported or claimed; promisc/allmulti; device MAC changes; staggered link availability; device unregister/re-register; and nonlinear/cloned/fragmented receive buffers.

Unsupported stacking configurations may be explicitly excluded from the product claim, but broad Linux features such as a second driver, multiple NICs, SMP, non-init namespace isolation and nonlinear skb input cannot be excluded merely because the initial harness does not create them.

## Security and hostile-input resilience

This is not a claim of cryptographic security. It is a requirement that local privileges and protocol parsing remain bounded under hostile input.

- enforce control-device permissions and management/session authorization;
- flood malformed/spoofed Layer-2/control traffic while valid peers remain active;
- attempt resource-exhaustion and churn attacks within lab limits;
- fuzz decoders and later socket/UAPI entry points using retained seeds/corpus;
- require bounded CPU/memory/table growth and recovery after attack traffic stops;
- prove evidence does not expose credentials/secrets unnecessarily.

## Upstream traceability

### Route20

At `b94115b2615c6463d1f006924ceeadde8e2d4367`, the pinned tree contains no standalone path named as a test suite. Build is PP-00; live Ethernet/routing behavior maps to PP-04/PP-05 and later DDCMP behavior is mapped when used. If a test is added or discovered at the pin, it must be classified before release rather than silently ignored.

### PyDECnet

The complete unmodified native discovery at `9a844987bf3a1450632dee8d37e60a23a453bad3` runs once in PP-00. The exact pinned test tree is classified as follows:

| Upstream file | Disposition |
| --- | --- |
| `dntest.py` | harness |
| `systemtest.py` | harness |
| `file_app_exerciser.py` | mapped PP-07 |
| `module_app_exerciser.py` | mapped PP-07 |
| `test_bridge.py` | reference-health; feature-gated if bridge behavior is claimed |
| `test_common.py` | mapped PP-01 |
| `test_config.py` | mapped PP-00/PP-02/PP-07 where applicable; remaining options reference-health/feature-gated |
| `test_crc.py` | mapped PP-01/PP-08 for protocol CRC; generic machinery reference-health |
| `test_ddcmp.py` | mapped PP-08 |
| `test_ethernet.py` | mapped PP-01/PP-03/PP-05 |
| `test_event.py` | mapped PP-07 when management events are claimed; otherwise feature-gated/reference-health |
| `test_framer.py` | mapped PP-08 |
| `test_gre.py` | reference-health; feature-gated if GRE is claimed |
| `test_host.py` | mapped PP-07 |
| `test_mirror.py` | mapped PP-07 |
| `test_modulo.py` | mapped PP-01/PP-06/PP-08 |
| `test_mop.py` | reference-health; feature-gated if MOP is claimed |
| `test_multinet.py` | reference-health; feature-gated if MultiNet behavior is claimed |
| `test_nicepacket.py` | mapped PP-01/PP-07 |
| `test_nsp.py` | mapped PP-06 |
| `test_nsppacket.py` | mapped PP-01/PP-06 |
| `test_packet.py` | mapped PP-01 for packet/codec invariants; generic framework internals reference-health |
| `test_route_eth.py` | mapped PP-03/PP-05 |
| `test_route_ptp.py` | mapped PP-05/PP-08/PP-09 |
| `test_routing.py` | mapped PP-03/PP-05/PP-09 |
| `test_routingpacket.py` | mapped PP-01/PP-05 |
| `test_session.py` | mapped PP-07 |
| `test_sessionpacket.py` | mapped PP-01/PP-07 |
| `test_timers.py` | mapped PP-02/PP-06/PP-08 where protocol-visible; generic timer implementation reference-health |

### LinuxDECnet

At `ff39eef045d1e4b7b72a3d40111e89c07a473398`, LinuxDECnet is a compatibility/reference source, not a kernel implementation base. Its `dnprogs/libvaxdata/src/test.c` native conversion program is an explicit PP-00 reference-health test for VAX I2/I4/F4/D8/G8 and conditional H16 conversion behavior. It becomes mapped/blocking PP-07 evidence when the release claims VAX/RMS data conversion. Other buildable user tools/API behavior are comparison evidence and live interoperability is used where compatible. Known historical defects are not copied merely to make comparison agree.

### SIMH

SIMH is a simulator dependency, not a DECnet protocol oracle. At `5b73b1032b52d19bf80752ea4d9cbbdc92e7b5e0`, the makefile states that normal builds run per-simulator tests when available unless tests are disabled. PP-00 therefore builds the exact selected DEC-host target with tests enabled and retains that transcript. The CPU/device/network/serial/timer tests needed by the selected DEC host path are blocking reference health for PP-12; unrelated machine families remain reference-health only. DECnet/Linux semantic acceptance comes from the DEC operating system running on SIMH in PP-12.

## Existing project gate mapping

| Existing gate | Canonical home |
| --- | --- |
| E0 vectors | PP-01 |
| E1 two-node LAN | PP-03 |
| E2 two-LAN router | PP-05 |
| E3 alternate routers | PP-05 |
| E4 multi-area/Level 2 | PP-05 |
| D0 vectors | PP-01/PP-08 |
| D1 emulated serial | PP-08 |
| D2 independent DDCMP peer | PP-08 |
| D3 injected DDCMP faults | PP-08 |
| D4 physical async | PP-08 |
| D5 physical sync | PP-08 |
| mixed Ethernet/DDCMP | PP-09 |
| harness false-green checks | PP-10 |
| 2→4→8→16 VM stress | PP-11 |
| real DEC/release image | PP-12 |

`tests/lab/dniv-smoke.sh` and `run-two-node.sh` implement only the currently automated subset. A future PP case is not green merely because the current harness has no mode for it.

## Evidence required for every run

Retain enough to reproduce and diagnose the first failure:

- exact source commit, reference SHAs, tool/kernel/compiler/configuration and test-harness revision;
- image/kernel/initrd/module/userspace/overlay hashes;
- architecture, vCPU count, driver/offload/MTU, topology, identities and media;
- exact canonical case, stress level, random/fuzz/fault seed and requested injection counts;
- proof that each requested fault was actually injected;
- packet captures or DDCMP traces where wire behavior matters;
- complete serial, kernel, service and application logs;
- state/counter/resource snapshots before, during, after failure and after quiescence;
- fault schedule and topology-change timeline;
- duration, packet/session/byte/fault/restart/churn counts;
- performance/convergence distributions when measured;
- kernel diagnostic output;
- explicit pass/fail for each canonical case and each applicable negative family.

Missing mandatory evidence makes the run invalid, not `probably fine`.

## Failure, retry and regression rule

A failed test remains a failure of that exact candidate until explained and fixed or the test is proven invalid. Retrying until a green attempt appears does not erase the first failure.

Every discovered protocol/kernel/harness defect must gain the smallest practical permanent regression test before closure. Minimized fuzz inputs and exact fault seeds join the retained regression corpus.

After any code, test, image, workflow or acceptance-document change:

1. invalidate prior-candidate acceptance evidence;
2. restart the repository SoP sequence from the exact new tree;
3. after three consecutive clean complete SoP passes, rerun affected acceptance stages and every downstream stage depending on them;
4. promote only the exact commit whose required matrix and evidence are green.

## Final pre-production gate

A candidate is releasable only when every claimed feature has positive canonical tests; every applicable negative family has a real executed test; every upstream test/source-health item has a disposition; required x86_64/aarch64, SMP, kernel/toolchain and driver entries are green; independent-peer and routed/mixed-media requirements are green; harness false-green tests are green; required stress/endurance tier is green; kernel diagnostics have no blocking finding; all evidence belongs to the exact candidate; and three consecutive complete clean SoP passes were performed on that exact final tree with no later change.

Anything less is development evidence, not pre-production acceptance.
