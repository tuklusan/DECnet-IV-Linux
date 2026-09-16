# Consolidated Pre-Production Test Procedure

## Purpose

This is the single pre-production acceptance procedure for DECnet-IV-Linux. It combines:

1. tests derived from the Linux implementation and its failure modes;
2. relevant tests and behaviors from the pinned Route20, PyDECnet, LinuxDECnet and SIMH references;
3. the existing project E0-E4 and D0-D5 lab plan; and
4. Linux-kernel-specific negative, lifecycle, fault and stress tests.

Duplicate tests are executed once as a canonical acceptance case with all contributing sources recorded. Upstream native test suites still run once at their exact pinned revisions as reference-source health checks. Passing a self-to-self test never substitutes for independent interoperability.

Tests run from the simplest deterministic checks to the hardest multi-node fault and soak tests. Negative tests are mandatory, not optional cleanup.

## Authority and exact revisions

Repository state, `docs/HANDOVER.md`, `docs/ROADMAP.md`, `docs/ARCHITECTURE.md` and `docs/TEST_LAB.md` remain authoritative.

Reference revisions are those pinned by `tests/reference/refs.env`:

| Reference | Revision | Use |
| --- | --- | --- |
| Route20 | `b94115b2615c6463d1f006924ceeadde8e2d4367` | independent Ethernet/routing behavior and live peer |
| PyDECnet behavior/live | `a7194be8d72dea6f9eb4f77083f056f53e80df58` | independent live peer |
| PyDECnet tests | `9a844987bf3a1450632dee8d37e60a23a453bad3` | protocol vectors, state-machine behavior and reference-source test baseline |
| LinuxDECnet | `ff39eef045d1e4b7b72a3d40111e89c07a473398` | userspace/API behavior and interoperability comparison |
| SIMH | `5b73b1032b52d19bf80752ea4d9cbbdc92e7b5e0` | real DEC operating-system peer host and simulator reference health |

A reference result is evidence about that reference only. It does not prove the Linux implementation.

## Test identity and de-duplication

Each acceptance test has one canonical `PP-xx` home.

A case is a duplicate only when it proves the same protocol invariant with the same failure meaning. The stronger canonical case wins: exact vector plus boundary checks plus malformed input plus recovery is preferred over a simple happy-path duplicate. All original sources remain listed against that case.

The following are dimensions, not duplicates and must not be collapsed:

- x86_64 versus aarch64;
- endnode, Level 1 router and Level 2 router;
- Phase III versus Phase IV where supported;
- Ethernet versus DDCMP;
- Linux-to-Linux versus independent peer;
- one LAN versus routed/multi-area topology;
- clean traffic versus injected loss, duplication, reordering, delay or corruption;
- first start versus restart/reload/recovery;
- minimum, boundary and maximum sizes.

Upstream tests outside the DECnet-IV-Linux release scope are not silently deleted. They are classified as one of:

- **mapped**: covered by a canonical `PP-xx` acceptance case;
- **reference-health**: run in the exact upstream suite but not used as a Linux semantic acceptance claim;
- **feature-gated**: becomes mandatory, positive and negative, when that feature is claimed;
- **harness**: support code, not counted as an independent test.

## Feature gating

A test may be feature-gated only while the feature is outside the release claim. The moment a release claims the feature, every applicable positive test and every applicable negative family in this document becomes a blocking test.

"Not implemented" is not a pass result.

## Mandatory negative-test contract

Every applicable protocol layer or user-visible feature must exercise every relevant family below. A stage with an applicable but missing negative case fails pre-production.

1. **Encoding and bounds:** truncated, oversized, zero/empty where illegal, invalid count/range, bad length, bad checksum/CRC, unknown type and reserved values.
2. **Identity and destination:** wrong node, area, MAC, multicast class, station, object, circuit, interface or address.
3. **Sequence and state:** stale, duplicate, out-of-order, wraparound, half-space ambiguity where defined, invalid transition and unsolicited control input.
4. **Timing and liveness:** expiry, timeout, delayed input, silence, restart and reconnect.
5. **Faulted transport:** deterministic loss, duplication, reordering, corruption and disconnect/reconnect.
6. **Resources and backpressure:** queue pressure, connection/object exhaustion, full windows, allocation failure where injectable and recovery after pressure is removed.
7. **Lifecycle and concurrency:** module load/unload, interface down/up, unregister, identity change, peer restart and close/connect/accept/timer races.
8. **UAPI and permissions:** wrong version/size, invalid arguments, short buffers/copies, invalid pointers where safely injectable, wrong state and insufficient privilege.
9. **Topology churn:** link/router loss, alternate path, stale route expiry, reconvergence and repeated changes under traffic.
10. **Application failure:** wrong credentials, denied access, unknown object/entity, interrupted transfer, cancellation and peer/application restart.

For every negative case, a pass requires all of the following:

- malformed or forbidden input is rejected, dropped or bounded as specified;
- no kernel panic, oops, warning caused by the test, lockup, use-after-free or memory corruption;
- no stale protocol state survives beyond its defined lifetime;
- counters and externally visible error state are consistent;
- subsequent valid traffic succeeds or the protocol reconverges within its defined timers;
- no unbounded memory, object, queue or timer growth remains after recovery.

## Execution matrix

Run the applicable canonical stages over this matrix:

| Axis | Required values |
| --- | --- |
| Architecture | x86_64/x86_64, aarch64/aarch64, x86_64→aarch64, aarch64→x86_64 |
| VM count | 2 first, then 4, 8 and 16 independent VMs as stress rises |
| Node role | endnode, Level 1 router, Level 2 router as implemented |
| Media | Ethernet, DDCMP, then mixed Ethernet/DDCMP |
| Peer | Linux peer, pinned Route20, pinned PyDECnet, LinuxDECnet userspace where applicable, real DEC OS/peer when available |
| Topology | single LAN, two-LAN router, alternate routers, multi-area, mixed media |
| Traffic | idle control traffic, unidirectional, bidirectional, concurrent sessions and bulk data |
| Faults | none first; then each mandatory negative family; then combined faults under load |

Lab node defaults remain area 31, nodes 70-79. Larger and multi-area topologies must use explicit configuration rather than accidental address reuse.

## Ordered pre-production stages

### PP-00 — provenance, source health and reproducibility

**Goal:** prove that the exact sources and artifacts under test are known before testing protocol behavior.

Positive tests:

- record the exact DECnet-IV-Linux commit;
- verify reference SHAs against `tests/reference/refs.env`;
- build the Linux module/tools natively for x86_64 and aarch64;
- build pinned Route20;
- run the complete pinned PyDECnet native test discovery once;
- build/check the pinned LinuxDECnet reference needed by the release;
- build the pinned SIMH target needed for the real DEC peer and run the applicable native SIMH health checks used for that target;
- verify kernel, initrd, base image and overlay hashes before VM resume;
- prove a resumed checkpoint matches architecture, source revision and mode.

Mandatory negatives:

- wrong or missing reference SHA;
- dirty/mismatched artifact;
- corrupted checkpoint hash;
- architecture or mode mismatch on resume;
- invalid configuration or missing required dependency.

**Pass:** every mismatch fails closed. No acceptance evidence from another commit or artifact is reused.

### PP-01 — pure vectors, UAPI layout and protocol codecs

**Goal:** catch deterministic byte-level errors before a VM is involved.

Canonical coverage:

- UAPI version, structure size and address extraction/composition;
- Phase IV node-id and standard Ethernet MAC mapping;
- little-endian Routing Layer payload length;
- Ethernet frame encode/decode and padding handling;
- router/endnode hello encode/decode;
- Phase III/IV init, hello, data and routing-update formats as implemented;
- routing/update checksums;
- DDCMP header/data CRC;
- modulo sequence arithmetic and wrap behavior;
- NSP packet encode/decode;
- Session Control packet encode/decode;
- NICE/NML packet encode/decode;
- minimum, boundary and maximum legal lengths.

Sources consolidated here include local `test_uapi.c`, local `test_phase3.c`, E0/D0 vector requirements, and relevant PyDECnet `test_common`, `test_crc`, `test_modulo`, `test_packet`, `test_routingpacket`, `test_nsppacket`, `test_sessionpacket`, `test_nicepacket`, `test_framer` and `test_ddcmp`.

Mandatory negatives include null/short inputs, invalid node/area, wrong MAC prefix, invalid destination class, truncated and oversized declared lengths, bad list counts/ranges, bad checksum/CRC, unknown message type, invalid sequence number and exact half-modulo ambiguity where the protocol arithmetic makes ordering undefined.

**Pass:** exact expected bytes and errors match the canonical vectors; malformed input never escapes bounds or mutates protocol state.

### PP-02 — single-node kernel/module/UAPI lifecycle

**Goal:** test Linux-specific behavior that upstream user-space stacks cannot cover.

Positive tests:

- repeated module load/unload;
- identity configure/readback and counter readback;
- interface bind/unbind and valid state transitions;
- timer start/cancel/rearm;
- multicast and DECnet unicast filter ownership by node role;
- runtime identity change;
- clean teardown with no surviving adjacency, socket, timer or filter state.

Generated Linux-specific negatives:

- wrong UAPI version/structure size;
- bad node/role/interface values;
- invalid or removed ifindex;
- short user buffer/copy and invalid pointer paths where safely testable;
- unprivileged operation where privilege is required;
- interface rename/down/up/unregister during activity;
- identity change racing receive/timer work;
- repeated load/unload while traffic is arriving;
- injected allocation pressure where practical.

Run with kernel diagnostics appropriate to the test build, including KASAN, KCSAN, UBSAN, lockdep and kmemleak coverage where feasible.

**Pass:** deterministic errno/drop behavior, no stale filters/state, no diagnostic finding, and successful reuse after the fault.

### PP-03 — two-node Ethernet adjacency (existing E1)

**Goal:** prove the smallest real network using two independent VMs.

Positive tests:

- standard EtherType plus two-byte little-endian payload length;
- correct DECnet protocol source MAC, deliberately different from NIC MAC;
- router hello discovery;
- router adjacency INIT then UP only when the peer lists the local router with expected priority;
- endnode/router behavior as applicable;
- designated-router election;
- All-Routers, All-Level-2-Routers and All-Endnodes destination behavior by role;
- 3.1x listener expiry behavior;
- bidirectional DECnet unicast delivery;
- capture evidence before and after restart;
- recovery after module restart;
- primary NIC MAC change while the module is loaded, with DECnet unicast reception preserved.

Mandatory negatives:

- wrong source/destination MAC;
- hello to a multicast group invalid for the local role;
- peer omits local router from its list;
- wrong priority/type/area where invalid;
- peer silence until expiry;
- link down/up;
- malformed/truncated/oversized hello;
- randomized invalid Ethernet/Routing frames;
- restart during control traffic.

**Pass:** both nodes agree on expected adjacency state, expiry and recovery; capture proves correct wire framing and addressing.

### PP-04 — independent Ethernet peer interoperability

**Goal:** remove shared-implementation blind spots.

Run Linux in both directions against the pinned Route20 and pinned live PyDECnet revisions for every currently claimed Ethernet role/phase. Use LinuxDECnet where its userspace/API behavior is relevant.

Positive tests:

- adjacency establishment;
- standard Ethernet length framing;
- role-correct multicast behavior;
- protocol unicast delivery;
- data forwarding appropriate to role;
- peer restart and clean recovery.

Mandatory negatives:

- wrong area/type/priority/listing;
- malformed and bad-length frames;
- MTU/boundary payloads;
- peer silence/restart;
- changed peer MAC/address;
- unsupported message type.

**Pass:** independent implementations reach compatible state and exchange valid traffic in both directions. Self-to-self results are supporting evidence only.

### PP-05 — routed Ethernet, E2 through E4

**Goal:** progress from one router to full Phase IV routed Ethernet.

**E2:** router with two LANs. Verify adjacency on each circuit, route installation, forwarding, hop/visit handling, route loss and reconvergence.

**E3:** multiple routers and alternate paths. Verify route selection, designated-router behavior, forwarding during link/router removal, stale-route expiry, alternate-path convergence and absence of loops.

**E4:** multiple areas with Level 2 routing. Verify Level 1/Level 2 adjacency rules, inter-area forwarding, Level 2 multicast, area-route updates and return traffic.

Consolidates relevant PyDECnet `test_routing`, `test_route_eth`, `test_route_ptp` and `test_routingpacket` behaviors.

Mandatory negatives:

- bad routing-update checksum;
- invalid count/start/range;
- update from wrong adjacency/role;
- stale and withdrawn route;
- visit/hop boundary;
- link/router failure during traffic;
- repeated topology churn;
- malformed/random routing input.

**Pass:** no forwarding loop, no stale route beyond timers, deterministic reconvergence and correct counters.

### PP-06 — NSP and Linux socket behavior

**Goal:** prove transport semantics and the Linux-facing socket lifecycle.

Positive tests:

- listen/connect/accept;
- connection initialization and confirmation;
- segmented and boundary-size data;
- interrupt/out-of-band path where exposed;
- ACK, delayed ACK, NAK and retransmission;
- data and interrupt flow control;
- backpressure;
- keepalive/inactivity behavior;
- orderly disconnect, abort and reject;
- concurrent connections and bidirectional traffic;
- poll/epoll and close behavior where exposed.

Consolidates PyDECnet `test_nsp`, `test_nsppacket`, `test_modulo` and relevant `test_timers`.

Mandatory negatives:

- invalid/stale/future sequence or ACK;
- duplicate and reordered segment;
- sequence wrap and ambiguous half-space comparison;
- deterministic packet loss/corruption/delay;
- malformed control/data packet;
- connection/object/resource exhaustion;
- zero/full window and sustained backpressure;
- timeout/retransmit races;
- simultaneous close/abort/restart;
- connect/accept/close/poll races;
- peer disappearance then recovery.

**Pass:** delivery/ordering semantics hold, failures terminate or retry as specified, resources return to baseline and sockets remain safe under races.

### PP-07 — Session Control, NICE/NML and userspace

**Goal:** prove object access and the standard DECnet/Linux tools claimed by the release.

Positive tests as implemented:

- Session Control object selection and connect data;
- authentication and access control;
- NICE/NML read/show/set operations permitted by the release;
- host/node-name mapping;
- `ncp`;
- `sethost`/`dnlogin`;
- DAP/FAL file operations;
- PHONE;
- mail;
- task/object access;
- daemons, libraries and diagnostics.

Consolidates relevant PyDECnet `test_session`, `test_sessionpacket`, `test_nicepacket`, `test_host`, `test_event`, `test_mirror`, `file_app_exerciser.py` and `module_app_exerciser.py`, plus applicable LinuxDECnet user-level behavior.

Mandatory negatives:

- authentication failure and explicit denial;
- unknown/disabled object;
- malformed connect data/format;
- invalid NICE entity/operation/parameter;
- insufficient privilege;
- bad host/node lookup;
- application exit during connection;
- interrupted/cancelled file transfer;
- peer or daemon restart;
- full/empty/boundary application payloads.

**Pass:** user-visible exit status and protocol response are deterministic, permissions are enforced, and a failed request cannot poison the next valid request.

### PP-08 — DDCMP, D0 through D5

**Goal:** prove the point-to-point data-link implementation from vectors through physical media.

**D0:** vectors for CRC, sequence, ACK/NAK/REP, maintenance/control frames, framing and malformed input.

**D1:** two independent VMs over emulated serial.

**D2:** independent reference peer.

**D3:** deterministic fault injection: loss, duplication, reordering, delay, corruption, disconnect and reconnect.

**D4:** physical asynchronous circuit when part of the release claim.

**D5:** physical synchronous circuit when part of the release claim.

Consolidates PyDECnet `test_ddcmp`, `test_framer`, `test_modulo` and point-to-point routing cases.

Mandatory negatives:

- bad header/data CRC;
- short/oversized frame;
- wrong station/address/type/control field;
- duplicate/out-of-order/wrapped sequence;
- lost ACK/NAK/REP;
- delayed/repeated control;
- random stream chunk boundaries and noise;
- link disconnect/reconnect during data;
- maintenance/data mode misuse.

**Pass:** retransmit/recovery is bounded, sequence state remains correct and valid traffic resumes without stale data delivery.

### PP-09 — mixed-media routed network

**Goal:** prove that Ethernet and DDCMP do not work only in isolation.

Minimum topology: Ethernet endnode → router → DDCMP → router → Ethernet endnode. Add alternate paths and Level 2 routing as the implementation reaches them.

Positive tests:

- routing updates cross the intended circuits;
- NSP session and application traffic cross the full path;
- boundary-size payloads survive differing media/framing;
- route changes converge.

Mandatory negatives:

- DDCMP loss/corruption during Ethernet-originated traffic;
- Ethernet circuit loss during DDCMP-originated traffic;
- one router restart;
- asymmetric fault;
- repeated route churn;
- path/MTU boundary conditions.

**Pass:** no loop, duplicate application delivery or stale path remains after convergence.

### PP-10 — scale, architecture and stress ladder

**Goal:** turn correct behavior into durable behavior.

Default minimum ladder:

| Stress level | Minimum work |
| --- | --- |
| S0 deterministic smoke | 2 VMs; one clean cycle of all applicable lower-stage happy paths and mandatory negatives |
| S1 churn | 2-4 VMs; at least 10 restart/link/identity/topology cycles while traffic runs |
| S2 sustained faults | 4-8 VMs; at least 1 hour; deterministic loss/duplication/reordering/delay/corruption plus concurrent sessions |
| S3 heavy | 8-16 VMs; at least 1,000 injected fault events while forwarding/session traffic runs; at least 8 hours |
| S4 release soak | 16 independent VMs; at least 24 hours; mixed architecture and mixed media where available; repeated peer/router/application restarts and all applicable fault classes |

The minimums above are project release policy. Lowering one requires a recorded reason in the release evidence; silently shortening a soak is a failure.

Across S0-S4:

- exercise x86_64 and aarch64, including mixed directions;
- approach documented adjacency, route, socket and queue limits;
- use minimum/boundary/maximum packet sizes;
- keep traffic bidirectional and concurrent;
- record memory/object/timer growth;
- repeat module/interface lifecycle operations;
- run diagnostics-enabled kernels in stress subsets where practical.

**Pass:** no crash, lockup, leak, unbounded growth, permanent adjacency/route/session loss or unexplained packet-state divergence.

### PP-11 — real-peer and release-image acceptance

**Goal:** prove the exact release artifact against software that does not share the Linux implementation.

Use the pinned SIMH revision to host an available real DEC operating system, and use physical DEC equipment when available and lawful to operate. Test the final release image, not a development filesystem.

Positive tests:

- cold boot and configured startup;
- adjacency/routing appropriate to the DEC peer;
- NSP/Session Control;
- NICE/NML;
- each claimed user tool/application;
- reboot, module reload and service restart;
- file/image reproducibility and artifact hashes.

Mandatory negatives:

- peer reboot during session;
- network outage and restoration;
- wrong credentials/object/node;
- interrupted transfer;
- router/circuit outage where topology permits.

**Pass:** the exact candidate image interoperates and recovers without special one-off changes.

## Upstream traceability and disposition

The native upstream suite remains a source-health gate even where individual semantics are mapped below. This prevents de-duplication from hiding a regression in the reference itself.

### Route20

At pinned revision `b94115b2615c6463d1f006924ceeadde8e2d4367`, no standalone repository test suite is used as a canonical test source. Its build is `PP-00`; live Ethernet/routing behavior is `PP-04`/`PP-05`. Any newly discovered native test at the pinned revision must be added to this table before release rather than silently ignored.

### PyDECnet test tree

| Upstream file | Disposition |
| --- | --- |
| `dntest.py` | harness |
| `file_app_exerciser.py` | mapped to PP-07 |
| `module_app_exerciser.py` | mapped to PP-07 |
| `systemtest.py` | harness |
| `test_bridge.py` | reference-health; feature-gated if DECnet bridge behavior is claimed |
| `test_common.py` | mapped to PP-01 |
| `test_config.py` | mapped to PP-00/PP-02/PP-07 where configuration semantics apply; other circuit-specific options reference-health/feature-gated |
| `test_crc.py` | mapped to PP-01/PP-08 for protocol CRC; generic CRC machinery reference-health |
| `test_ddcmp.py` | mapped to PP-08 |
| `test_ethernet.py` | mapped to PP-01/PP-03/PP-05 |
| `test_event.py` | mapped to PP-07 when NICE/NML events are claimed; otherwise feature-gated/reference-health |
| `test_framer.py` | mapped to PP-08 |
| `test_gre.py` | reference-health; feature-gated if GRE is claimed |
| `test_host.py` | mapped to PP-07 |
| `test_mirror.py` | mapped to PP-07 |
| `test_modulo.py` | mapped to PP-01/PP-06/PP-08 |
| `test_mop.py` | reference-health; feature-gated if MOP is claimed |
| `test_multinet.py` | reference-health; feature-gated if MultiNet-specific behavior is claimed |
| `test_nicepacket.py` | mapped to PP-07 |
| `test_nsp.py` | mapped to PP-06 |
| `test_nsppacket.py` | mapped to PP-01/PP-06 |
| `test_packet.py` | mapped to PP-01 for packet/codec invariants; generic framework internals reference-health |
| `test_route_eth.py` | mapped to PP-03/PP-05 |
| `test_route_ptp.py` | mapped to PP-05/PP-08/PP-09 |
| `test_routing.py` | mapped to PP-03/PP-05/PP-09 |
| `test_routingpacket.py` | mapped to PP-01/PP-05 |
| `test_session.py` | mapped to PP-07 |
| `test_sessionpacket.py` | mapped to PP-01/PP-07 |
| `test_timers.py` | mapped to PP-02/PP-06/PP-08 where protocol-visible; generic timer implementation reference-health |

The complete native PyDECnet test discovery at the pinned test revision runs once in `PP-00`, so a mapped case is not an excuse to skip its upstream test.

### LinuxDECnet

At pinned revision `ff39eef045d1e4b7b72a3d40111e89c07a473398`, no standalone test suite is used as a canonical release suite. Buildable/reference user tools and API behavior are comparison evidence in `PP-00`/`PP-07`; live interoperability is used where compatible. LinuxDECnet defects are not copied into the Linux kernel implementation merely to make the comparison agree.

### SIMH

SIMH is a simulator dependency, not a DECnet protocol oracle. Its pinned build and the native health checks needed for the selected simulated machine belong to `PP-00`. Generic simulator CPU/device regressions remain reference-health only. DECnet/Linux release evidence comes from the DEC operating system running on the simulator and is canonical in `PP-11`.

## Existing project test mapping

| Existing project gate | Canonical home |
| --- | --- |
| E0 vectors | PP-01 |
| E1 two-node LAN | PP-03 |
| E2 two-LAN router | PP-05 |
| E3 alternate routers | PP-05 |
| E4 multi-area/Level 2 | PP-05 |
| D0 vectors | PP-01 and PP-08 |
| D1 emulated serial | PP-08 |
| D2 independent DDCMP peer | PP-08 |
| D3 injected DDCMP faults | PP-08 |
| D4 physical async | PP-08 |
| D5 physical sync | PP-08 |
| mixed Ethernet/DDCMP | PP-09 |
| x86_64/aarch64 VM matrix | PP-03 through PP-11 as applicable |

`tests/lab/dniv-smoke.sh` and `run-two-node.sh` remain the implementation of applicable PP-03 cases until superseded. Their checkpoint/hash, capture, MAC-change, expiry, restart and bidirectional-unicast assertions are separate invariants even when they execute in one script.

## Evidence required for every run

Store enough evidence to reproduce and diagnose the result:

- exact DECnet-IV-Linux commit and reference SHAs;
- architecture, kernel, compiler and relevant configuration;
- image/kernel/initrd/overlay hashes;
- topology and node/area/circuit identities;
- exact test/stress level and random seed, if any;
- packet captures for wire-level stages;
- serial/service/kernel logs;
- counter snapshots before/after negatives;
- fault injection schedule;
- elapsed duration and restart/churn counts;
- kernel diagnostic output;
- pass/fail result for each canonical ID and negative family.

A failure report must preserve the first bad evidence before retries.

## Failure and retry rule

A failed test is a failure of the exact candidate until explained and fixed. Re-running until it passes does not erase the first failure.

After a code, test, image, workflow or acceptance-document change:

1. invalidate acceptance evidence for the previous candidate;
2. restart the repository SoP sequence from the new exact tree;
3. after three consecutive clean complete SoP passes, rerun the affected acceptance stages plus every downstream stage whose evidence depends on them;
4. promote only the exact commit whose required matrix is green.

## Final release gate

A pre-production candidate is releasable only when all of these are true:

- every claimed feature has its positive canonical cases;
- every applicable mandatory negative family has a real test and passes;
- every upstream test/module has a recorded disposition;
- exact pinned reference-source health gates are green;
- x86_64 and aarch64 required matrix entries are green;
- independent-peer interoperability is green;
- routed and mixed-media gates required by the release are green;
- the required stress/soak level is green;
- kernel diagnostics show no blocking defect;
- evidence belongs to the exact candidate commit;
- three consecutive complete clean SoP passes were performed on that exact final repository tree;
- no later change occurred after those passes.

Anything less is development evidence, not pre-production acceptance.
