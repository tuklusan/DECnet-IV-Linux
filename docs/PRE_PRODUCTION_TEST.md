<!-- ============================================================================ -->
<!-- Copyright (c) 2026 Supratim Sanyal of SANYALnet Labs. -->
<!-- Proprietary rights reserved except as expressly licensed herein. -->
<!-- -->
<!-- DECnet-IV-Linux -->
<!-- This file is governed by the SANYALnet Labs Non-Commercial License in the -->
<!-- root LICENSE file. Non-Commercial use is permitted; Commercial Use and use -->
<!-- for AI/ML model training are prohibited unless separately authorized. -->
<!-- -->
<!-- Attribution is required: "Based on original work by Supratim Sanyal of -->
<!-- SANYALnet Labs." See LICENSE for full terms, warranty disclaimer, termination, -->
<!-- patent, trademark, and governing-law provisions. -->
<!-- ============================================================================ -->

# Consolidated Pre-Production Test Procedure

## Purpose

This is the single pre-production acceptance procedure for DECnet-IV-Linux. It consolidates project tests, the existing E0-E4 ladder, relevant behavior and native tests from the exact pinned Route20, PyDECnet, LinuxDECnet and SIMH references, plus Linux-kernel-specific lifecycle, concurrency, negative, stress, endurance, security and recovery testing.

Tests progress from deterministic byte/vector checks to destructive routed and distributed-transport endurance. Positive, negative, stress and recovery coverage are all mandatory when applicable. Self-to-self success is development evidence only; final interoperability requires independent implementations or real DEC peers.

A documented test that was not actually executed is not green. Manual and physical tests count only when their exact procedure, candidate identity and evidence are retained.

## Authority and pinned references

Repository state, `docs/HANDOVER.md`, `docs/PROJECT_STATE.md`, `docs/ROADMAP.md`, `docs/ARCHITECTURE.md`, `docs/TEST_LAB.md`, `docs/HECNET_LAB.md` and `tests/reference/refs.env` are authoritative.

| Reference | Revision | Acceptance use |
| --- | --- | --- |
| Route20 | `a9ef7c0b7f875f0dd2e8abaf11213798a8e4474c` | independent Ethernet/routing behavior, live peer and native VDE reference |
| PyDECnet behavior/live | `8d93c2a546317c67aba0adf9433f5f3efdf1f85c` | independent live peer, native VDE and MULTINET authority |
| PyDECnet tests | `9a844987bf3a1450632dee8d37e60a23a453bad3` | protocol vectors/state machines and native reference baseline |
| LinuxDECnet | `ff39eef045d1e4b7b72a3d40111e89c07a473398` | userspace/API and VAX-data conversion comparison |
| SIMH | `5b73b1032b52d19bf80752ea4d9cbbdc92e7b5e0` | real DEC operating-system host and simulator reference health |

A reference result proves that reference only. It does not prove this implementation.

## De-duplication and traceability

Each semantic invariant has one canonical `PP-xx` home. Two cases are duplicates only when they prove the same invariant with the same failure meaning. The stronger canonical case wins: exact legal vectors plus boundaries plus malformed input plus recovery is preferred over a simple happy path.

These are dimensions, not duplicates: x86_64/aarch64; 1/2/4/8 vCPU; endnode/L1/L2; Phase III/IV where supported; Ethernet/VDE2/MULTINET transport; Linux/self versus independent peer; single LAN/routed/multi-area; first-start/restart/upgrade; clean/faulted transport; size/timer/table boundaries; kernel/toolchain/driver variants; and extracted-source-release versus repository-checkout execution.

Every upstream test is classified as one of:

- **mapped** — the same invariant is exercised by a canonical PP case;
- **reference-health** — run unchanged at its exact pin but not treated as Linux semantic proof;
- **feature-gated** — blocking positive, negative, stress and recovery coverage when the feature is claimed;
- **harness** — support code rather than an independent semantic test.

No in-scope upstream test disappears because it is inconvenient. The repository-maintained in-scope discovery set runs at the pinned revision; explicitly out-of-scope modules remain classified in this document rather than silently re-entering acceptance.

## Feature gating

A case may be feature-gated only while the feature is outside the release claim. Once claimed, all applicable positive cases, negative families, stress cases, recovery assertions and evidence requirements in this document are blocking.

`Not implemented`, `not automated`, `flaky`, `manual later`, `could not reproduce`, `fault injector inactive` and `evidence missing` are not pass results.

## Mandatory negative-test contract

Every applicable layer and user-visible feature exercises every relevant family below:

1. **Encoding/bounds** — short, truncated, overlong, zero/empty where illegal, invalid count/range/length/checksum/CRC, unknown type, reserved fields, padding, alignment and nested length errors.
2. **Identity/destination** — wrong node, area, source, destination, MAC, multicast group, station, object, circuit, interface and duplicate identity.
3. **Sequence/state** — stale, duplicate, future, reordered, wraparound, exact half-space ambiguity, unsolicited control, illegal transition and rollback.
4. **Timing/liveness** — just-before/exact/just-after boundaries, expiry, timeout, silence, scheduler delay, VM pause/resume, restart and reconnect.
5. **Transport faults** — deterministic loss, duplication, reordering, delay, corruption, truncation, disconnect/reconnect and asymmetric failure.
6. **Resources/backpressure** — adjacency, route, socket, connection, object, table and queue saturation; allocation failure; full windows; buffer pressure; disk/inode exhaustion; recovery after pressure clears.
7. **Lifecycle/concurrency** — load/unload, open/close, device register/unregister, identity change, peer restart, timer/workqueue races, simultaneous operations and cross-CPU execution.
8. **UAPI/permissions** — wrong version/size/command/index/argument, short copy, invalid pointer where safely injectable, compatibility ABI, wrong state and insufficient privilege.
9. **Topology churn** — link/router/circuit loss, alternate path, withdrawal, stale route expiry, repeated reconvergence and overlapping changes under traffic.
10. **Application/storage** — authentication/authorization failure, unknown object, daemon death, cancellation, interrupted transfer, read-only/full storage, bad metadata and process restart.
11. **Harness/evidence** — dead capture/logger, missing/truncated evidence, bad pass marker, wrong hash/revision/mode, inactive injector, exhausted evidence storage and corrupt checkpoint.
12. **Adversarial load** — malformed/control floods, spoofing, churn floods and resource pressure while valid traffic remains live within declared service limits.
13. **Upgrade/rollback** — incompatible old/new ABI, stale config/checkpoint, partial upgrade, failed rollback and mixed-version network behavior once an N-1 release exists.

For each negative test, pass requires all applicable outcomes: bounded/rejected behavior as specified; no panic, oops, test-caused warning, lockup, memory corruption or use-after-free; no stale state beyond defined lifetime; correct counters/errors; requested faults proven to have occurred; valid work succeeds afterward or reconverges; resources return to baseline or a predeclared bounded envelope; and mandatory evidence is complete.

## Production matrix

| Axis | Required production values |
| --- | --- |
| CPU architecture | x86_64/x86_64, aarch64/aarch64, x86_64→aarch64, aarch64→x86_64 |
| vCPU | 1 plus representative 2, 4 and 8 vCPU SMP; concurrency stress uses more than one vCPU |
| VM count | 2, then 4, 8 and 16 independent VMs |
| Kernel/toolchain | oldest/newest supported maintained kernel lines; GCC and Clang where supported; clean rebuilds |
| Kernel diagnostics | KASAN, KCSAN, UBSAN, license-compatible lock debugging, kmemleak and KFENCE subsets as applicable |
| Node role | endnode, Level 1 router, Level 2 router |
| Transport | native Ethernet; rootless/distributed VDE2 Ethernet; MULTINET TCP gateway |
| Peer | Linux, pinned Route20, pinned PyDECnet, applicable LinuxDECnet userspace, SIMH-hosted DEC OS, physical DEC peer where available |
| Ethernet path | virtio plus at least one second emulated or physical driver; offloads on/off; multi-NIC |
| Topology | one LAN, two-LAN router, alternate routers, multi-area, cross-runner VDE2, controlled HECnet Area-31 |
| Traffic | idle, quiet-after-burst, unidirectional, bidirectional, microburst, sustained bulk, many concurrent sessions |
| Faults | each mandatory family alone, then selected overlapping faults under load |
| Boot/lifecycle | cold boot, warm reboot, reload, late NIC, initially-down link, repeated restart, hard power loss |

Area 31 nodes 70-79 remain the ordinary lab pool. Larger/multi-area topologies use deliberate explicit configuration.

## Exact boundary catalogue

Boundary coverage is not satisfied by the words `minimum` and `maximum`. Test the exact implementation/protocol boundary and adjacent values where meaningful:

- DECnet area: 0 invalid, 1, 63, 64 invalid;
- DECnet node: 0 invalid, 1, 1023, 1024/out-of-field invalid at parsing/configuration boundaries;
- node name: length 0, 1, 6, 7; legal alphanumeric; punctuation rejection; lowercase normalization; missing/forced terminator cases;
- node type: invalid/reserved values around all supported endnode/L1/L2 values and reserved flag bits;
- router priority: 0, 127, 128 invalid;
- hello timer: zero/fallback semantics, 1, 65535 and overflow-safe listen-lifetime calculation;
- protocol version fields: current major/minor/ECO, lower major, higher major and minor/ECO variations with expected behavior established from specification/reference interoperability;
- Ethernet Routing Layer declared length: 0, shortest legal, exact payload, largest legal block, one above, truncated payload and legal trailing Ethernet padding;
- DECnet pad byte/path: no pad, 1, largest representable useful pad, pad >= packet length, zero-length encoded pad and nested pad marker;
- router list: 0, 1, 32, 33 and 34 entries; malformed entry size; duplicate entry; invalid address/priority; self/local entry behavior;
- endnode test-data length/content: 0, 1, 49, 50, 51, largest fitting value and one-byte overrun; expected legal range established from protocol/reference; one-bit mutation of the required test pattern;
- adjacency storage: 63, 64 and attempted 65th total entry plus reclamation after expiry;
- router admission: 32, 33 and attempted 34th router on one interface, including equal-priority node-address tie replacement in both directions;
- every sequence space: zero, last, wrap, duplicate, previous/future and exact half-space ambiguity where ordering is undefined;
- every later buffer/window/segment/object/file-size limit: zero, one, one below, exact limit and one above.

## Development versus promotion execution

The complete procedure below defines production acceptance coverage; it does not require every production case to run after every development increment. Exact-SHA development uses bounded targeted/fast/consolidated execution plus full promotion coverage as documented in `docs/TEST_LAB.md`. Reduced profiles eliminate unrelated repetition while preserving the full catalogue for scheduled weekly revalidation and mandatory phase/release promotion. Only a full run can satisfy a phase-closure or release acceptance claim.

Scenario parallelism is an execution optimization only. Splitting independent interoperability scenarios into separate jobs does not change their assertions, peer pins, evidence rules or pass criteria.

## Ordered acceptance stages

### PP-00 — provenance, source health, build and reproducibility

Record the exact DECnet-IV-Linux commit/tree, source-tarball SHA-256, all reference SHAs, kernel/compiler/configuration and installed-artifact hashes. Build module/userspace/unit tests natively on x86_64 and aarch64, the supported kernel floor plus maintained/current validated kernel lines, and both supported compiler families where the kernel build permits them. Run appropriate kernel warning/static-analysis modes.

Build the exact Route20 pin. Run the repository-maintained in-scope PyDECnet native module set unmodified. Build applicable LinuxDECnet tools/libraries and run `dnprogs/libvaxdata/src/test.c` as reference health; it also becomes mapped PP-07 evidence when VAX/RMS conversion is claimed. Build the exact selected SIMH DEC-host target with tests enabled and retain target-specific per-simulator test output for the VAX/PDP-11/DEC CPU, storage, Ethernet and timer path used by PP-12. Serial/synchronous DECnet media are outside this project's transport claim. Unrelated simulator families remain reference-health only.

Build the source release tarball twice from identical inputs and require byte-for-byte equality. The archive must contain no `.git` directory, generated object/module files or QCOW2/RAW/IMG/ISO payloads. Extract it into a clean directory and execute the documented `build.sh`, staged `install.sh` and `uninstall.sh` on both native architectures. The installed component manifest must cover the complete delivered kernel/userspace/header/library/documentation set.

Mandatory negatives: wrong/missing pin; partial/bad source download; source checksum mismatch; truncated/corrupt archive; missing `SOURCE-METADATA`; generated binary/disk payload accidentally entering the source archive; missing/wrong kernel headers; unsupported kernel build tree; compiler/Python below the declared floor; interrupted extraction/build/install; non-root live install; unsafe uninstall manifest; wrong architecture/revision/mode; output/evidence directory unavailable/full/read-only.

### PP-01 — vectors, codecs, properties, models and differential checks

Exercise UAPI layout/address composition, node MAC mapping, Ethernet length framing/padding, Phase III/IV packet forms as supported, router/endnode hellos, checksums, sequence arithmetic, NSP, Session Control, NICE/NML and DAP/RMS conversions when implemented. Run every exact boundary catalogue case.

Sources include local unit tests and the relevant PyDECnet `test_common`, `test_crc`, `test_modulo`, `test_packet`, `test_routingpacket`, `test_nsppacket`, `test_sessionpacket`, `test_nicepacket` and applicable transport/routing suites.

Mandatory generated coverage:

- retained deterministic fuzz corpus for every decoder/encoder and later UAPI/socket entry point;
- one-bit and structured mutations around every known-good vector;
- property checks such as legal encode→decode round trip and decoder non-mutation on rejected input;
- model-based generation of adjacency, routing and NSP state transitions once those state machines exist;
- differential generation against pinned independent references where both sides expose comparable encoding/parsing/state behavior;
- mutation testing of the test suite: deliberately invert/remove representative parser/state-machine decisions and prove the relevant canonical test fails. The mutations are test artifacts, never production commits.

Every discovered crash, hang, out-of-bounds access, unexpected state mutation or differential mismatch gets a minimized permanent regression vector/seed.

### PP-02 — kernel/module/UAPI lifecycle and concurrency

Exercise load/unload and failed-init unwind; identity/stats/adjacency UAPI; native 64-bit plus 32-bit compatibility userspace on 64-bit kernels where supported; privilege/device permissions; timer/workqueue start-cancel-rearm; role-correct filters; runtime identity change across one/multiple NICs; devices existing before load and appearing later; down/up/rename/unregister/re-register; non-Ethernet and loopback exclusion; `init_net` isolation; device movement between namespaces; nonlinear/fragmented/cloned skb input; multiple active interfaces; adjacency/router saturation; duplicate identity; concurrent stats reset/read and adjacency enumeration; and clean teardown.

Filter ownership tests must cover coexistence/refcounts: pre-install the same unicast/multicast address through another legitimate consumer, load/change/unload DECnet, and prove DECnet removes only its own reference without breaking the other consumer. Inject filter-add failure at each unicast/multicast stage and on first/middle/last device; require exact rollback and continued old-identity operation.

Race/failpoint cases include identity change versus RX/timer/stats/device events; unload with open control fd; ioctl/close/unload; receive during unload; unregister during RX/timer work; allocation failure; counter near-wrap and jiffies/timer wrap via test hooks where practical. Exercise `cancel_delayed_work_sync` paths under concurrent scheduling and identity changes.

SMP is mandatory on 2/4/8-vCPU guests with CPU affinity/migration, multiple receive queues/interfaces and CPU hotplug where supported. Diagnostic subsets include KASAN, KCSAN, UBSAN, license-compatible lock debugging, kmemleak and KFENCE.

Full `CONFIG_PROVE_LOCKING` lockdep is not directly applicable to this non-GPL out-of-tree module on the pinned Linux kernel: `CONFIG_DEBUG_LOCK_ALLOC` maps `mutex_lock()` to the GPL-only `mutex_lock_nested()` interface and brings in other GPL-only lockdep helpers. Acceptance must not relabel the module or weaken kernel export licensing. The applicable locking subset therefore enables `CONFIG_DEBUG_SPINLOCK`, `CONFIG_DEBUG_MUTEXES`, `CONFIG_DEBUG_RWSEMS` and `CONFIG_DEBUG_ATOMIC_SLEEP` with `panic_on_warn=1`; full lockdep remains not applicable unless the licensing boundary changes legitimately.

### PP-03 — two-node Ethernet adjacency (E1)

Using two independent VMs, prove standard EtherType/length framing, protocol source MAC distinct from NIC MAC, endnode/router discovery, router INIT→UP rules, designated-router election, role-correct multicast, listener expiry, bidirectional protocol unicast, module/peer restart recovery and primary NIC MAC change while loaded.

Mandatory negatives/boundaries include wrong source/destination/multicast class; duplicate address/MAC; omitted local router; changed priority/type/address; cross-area L1 rejection/permitted L2 case; listener expiry just-before/at/after 3.1x; DR startup delay just-before/at/after; equal-priority tie/handover; link down/up; silence; reboot/hard kill; malformed/random frames while valid hellos continue; promisc/allmulti exposure; offloads on/off and supported MTU changes.

Repeat single/multi-vCPU and at least two Ethernet driver paths before production release.

### PP-04 — independent Ethernet peer interoperability

Run Linux both directions against exact pinned Route20 and live PyDECnet for each claimed Ethernet role/phase; include applicable LinuxDECnet behavior and later real DEC peers. Prove adjacency, framing, multicast, unicast, role/area rules, boundary frames, forwarding and restart without one-off patches/configuration. Repeat controllable malformed length/list/type/destination, changed identity, silence, hard restart, unsupported-message and MTU cases through the independent path.

### PP-05 — routed Ethernet E2-E4

E2: two LANs through one router. E3: alternate routers/paths. E4: multiple areas with L1/L2 rules. Prove route installation, metrics/ties, forwarding/return path, visit/hop limits, withdrawal/aging, DR/preferred-router behavior as applicable, failover and convergence without loops.

Consolidates relevant PyDECnet `test_routing`, `test_route_eth`, `test_route_ptp` and `test_routingpacket` behavior.

Negatives/stress include bad update checksum/count/start/range; wrong adjacency/role; stale/duplicate/conflicting routes; metric/tie boundaries; route-table saturation; one/multiple failures during bidirectional traffic; asymmetric faults; route flaps; thundering-herd restart; malformed update flood while valid routing/traffic remains live. Retain convergence-time and packet-loss distributions. Thresholds are declared before the candidate run.

### PP-06 — NSP and Linux sockets

Prove listen/connect/accept including nonblocking paths; initialization/confirmation; segmentation/buffer boundaries; ACK/delayed ACK/NAK/retransmit; data/interrupt flow control; backpressure; keepalive/inactivity; orderly disconnect/reject/abort; shutdown/half-close where supported; poll/epoll; socket options; fork/dup/process-exit; concurrent sessions and bidirectional bulk.

Consolidates PyDECnet `test_nsp`, `test_nsppacket`, `test_modulo` and relevant `test_timers`.

Negatives/stress: stale/future/duplicate/reordered sequence/ACK; many sequence wraps and half-space cases; lost control/ACK; malformed/spoofed connection IDs; full/zero windows; sender/receiver stall; socket/object exhaustion; simultaneous connect/close/abort/restart; EINTR/signals; accept/close/poll races; hard peer death; syscall fuzzing; many-client fairness so one abusive/blocked connection cannot starve independent valid sessions beyond declared limits.

### PP-07 — Session Control, NICE/NML and userspace

As implemented, test object selection/connect data, authentication/access, management operations, node-name mapping, `ncp`, `sethost`/`dnlogin`, DAP/FAL/RMS operations, PHONE, mail, task/object access, daemons/libraries/diagnostics.

Consolidates relevant PyDECnet `test_session`, `test_sessionpacket`, `test_nicepacket`, `test_host`, `test_event`, `test_mirror`, `file_app_exerciser.py`, `module_app_exerciser.py`, LinuxDECnet behavior and `dnprogs/libvaxdata/src/test.c` once VAX/RMS conversion is claimed.

Negatives include bad credentials/denial/unknown object; malformed Session/NICE input; daemon crash/restart; signals/cancellation; interrupted transfer; zero/one-byte/boundary/large/binary files with hashes; DEC record/attribute/conversion round trips; disk/inode/quota/read-only/permission changes; partial-output cleanup; peer restart; many clients; terminal interruption; locale/character handling where exposed; and no credential/secret leakage into ordinary evidence.

### PP-08 — VDE2 and MULTINET transport proofs

VDE2 and MULTINET are proven independently before they are combined.

VDE2 proof requires real libvdeplug frame delivery, multiple independent VDE endpoints, Route20/PyDECnet adjacency on the VDE fabric, switch/client restart, disconnect/reconnect, malformed/oversized frame rejection where applicable, and an actual cross-host VDE join before any multi-runner topology depends on it. The already-green single-host proof does not satisfy the cross-runner requirement.

MULTINET proof uses the pinned PyDECnet implementation as the behavioral authority. Run its complete MULTINET test module, including TCP connect/listen, fragmented/coalesced framing, IPv4/IPv6 cases where supported, late listener, restart and reconnect. The live gate uses one L2 listener with two simultaneous L1 connectors, requires an unopened-port negative, repeated connector churn while the unaffected peer stays alive, and listener restart followed by recovery of both connectors. UDP is not part of the supported project transport claim.

Transport proofs are separate jobs and separate evidence sets. Neither may mask a failure in the other.

### PP-09 — distributed and HECnet routing

After PP-08 is independently green, connect local DECnet-IV-Linux VMs through VDE2 to a PyDECnet-derived MULTINET gateway. The repository-tracked remote workflow must consume `MULTINET_REMOTE_HOST`, `MULTINET_REMOTE_PORT`, `VAX_ADDR`, `VAX_USERNAME` and `VAX_PASSWORD` only as runtime secrets; before network activity it must detect missing prerequisites by name without exposing values. Prove one controlled adjacency to the MULTINET-facing Area-31 area router first, then bidirectional routing to the second Area-31 router at `VAX_ADDR`. Query routing/NICE state and counters where implemented, exercise NSP/MIRROR and Session/object traffic, and add paired Linux/VAX user-level tests as Phase 7 tools become available. Exercise route establishment/withdrawal, peer and gateway restart, link interruption, reconnect, asymmetric failure, boundary NSP traffic and repeated churn. No loop, duplicate application delivery, credential leakage, leaked disposable node identity or stale path after convergence is allowed.

### PP-10 — harness/evidence false-green tests

Prove the test system catches a bad system before trusting it. Deliberately corrupt known vectors, expected hashes, pass markers, checkpoints and fault manifests; use wrong revision/architecture/mode; suppress required traffic; kill capture/logging; exhaust evidence disk/inodes; truncate/corrupt evidence; disable a requested injector; omit a required file; print a guest pass-like marker without host wire/state proof; retry a failed test and preserve first-failure evidence.

Every requested fault records an injection count/event log and the test asserts that the fault actually happened. Production evidence completeness is blocking; warning-only artifact behavior is insufficient for release acceptance.

The repository-tracked PP-10 workflow begins with executable fail-closed acceptance-control regressions: tracked checkout mutation, corrupt integrity manifest, parent-candidate mismatch, stale scratch lineage, non-main execution and wrong requested revision must all be rejected. Guest pass-like text remains insufficient without independent E1 wire counters; final E1 validation requires complete non-empty guest serial lifecycle evidence; packet-capture death remains fatal through the final pass window; requested diagnostic host-silence faults are counted exactly. Evidence preflight checks bytes, inodes and writeability, and the workflow additionally mounts bounded tmpfs filesystems and literally exhausts bytes and inodes to prove those failures are blocking. Required-file SHA-256 manifests must reject same-size corruption, truncation and omitted members. Duplicate or inactive requested fault events are rejected. All GitHub evidence uploads must fail when files are absent and use run-attempt-qualified non-overwriting artifact names.

A full-profile acceptance issue may set `PP10_RETRY_PROBE=true`. That makes the false-green child deliberately fail attempt 1 after writing a unique failure marker. On a failed-job rerun, attempt 2 must find and download the run-attempt-1 artifact, validate the retained failure marker and only then continue to success; attempt 2 is uploaded under its own run-attempt-qualified name.

The failed-job retry proof is executed green on exact candidate `2bd27dbd0fbfa01a2804961d99b02ffb00f89874`: both run-attempt artifacts are retained and full acceptance issue #860 is closed. The repository's actual persistent resume input is the source-independent architecture-foundation cache, not a candidate VM checkpoint. `tools/evidence_guard.py foundation` verifies its exact member set, SHA-256 hashes, architecture, session/fingerprint, Ubuntu release/snapshot and source independence before a cached foundation may be reused; exact-SHA fast acceptance of that guard is green on `a6356880e19647617bf1200dafdb8d6f7db690c5`. Candidate images and overlays remain disposable.

The non-E1 interoperability fault path now records and validates the real fault evidence it uses. `evidence_guard.py fault` requires exactly one expected `fault=` declaration, rejects missing/empty/duplicate/mismatched evidence, requires nonzero tc packet counts for tc-backed injectors, and requires the injector/observer proof marker for raw-packet or peer-driven faults. `tests/lab/run-interop.sh` applies that check to loss, clean-drain, XOFF/XON, ACK-range, interrupt loss/credit flow, CC retry, DI loss/exhaustion, full-window, response retry exhaustion, CI exhaustion, CR timeout and reserved-port peer isolation. The PP-10 regression deliberately proves inactive, corrupt, duplicate, missing and proof-marker-free non-E1 evidence is rejected. PP-10 remains open only until this final fault-evidence increment executes green on an exact full acceptance candidate.

### PP-11 — stress, performance, soak and endurance

| Level | Minimum production work |
| --- | --- |
| S0 deterministic | 2 VMs; all applicable lower-stage happy paths and mandatory negatives once |
| S1 churn | 2-4 VMs; at least 100 combined module/interface/identity/peer/reboot/topology cycles under traffic |
| S2 sustained faults | 4-8 VMs; at least 1 hour and at least 10,000 deterministic injected fault events |
| S3 heavy | **Owner-authorized lab skip.** Current lab cannot execute this level; not blocking for this project release under the explicit 2026-10-01 authorization. |
| S4 release soak | **Owner-authorized lab skip.** Current lab cannot execute this level; not blocking for this project release under the explicit 2026-10-01 authorization. |
| S5 endurance | **Owner-authorized lab skip.** Current lab cannot execute this level; not blocking for this project release under the explicit 2026-10-01 authorization. |
| S6 first-production/core-change endurance | **Owner-authorized lab skip.** Current lab cannot execute this level; not blocking for this project release under the explicit 2026-10-01 authorization. |

S0-S2 remain blocking and executable in the current lab. S3-S6 are explicitly waived for this lab/release by project-owner authorization dated 2026-10-01; do not fabricate substitute evidence or treat shorter runs as equivalent. Revisit the waiver only if lab capability changes or the owner revokes it.

For executable endurance/stress work, duration never substitutes for event/count coverage. Repeat sequence wraps many times; drive tables/queues to limits and back; combine malformed/control floods with valid traffic; use microbursts, sustained load and long idle where the active level requires them; cold boot/reboot/reload/hard-kill guests; pause/resume guests; move work across CPUs; repeatedly exercise SMP RX/timer/ioctl/device races; sample memory/slab/object/timer/work/adjacency/route/socket counts; quiesce after pressure and require return to baseline or predeclared bounded envelope with no monotonic growth.

Retain p50/p95/p99 latency, throughput, CPU/memory use, setup and convergence distributions for claimed services. Performance/fairness limits are declared before the run; unexplained regressions block release until explained or explicitly accepted by release policy.

The first executable PP-11 increment makes native socket churn count explicit and fail-closed. `dnsocklife` accepts a bounded requested cycle count, the guest records the exact completed count, and the host requires that marker. Full-profile amd64 PyDECnet L1 interoperability requests 100 connect/exchange/disconnect lifecycle cycles against the independent peer; ordinary fast/consolidated coverage remains at 16 cycles. This establishes the S1 socket-lifecycle floor but does not by itself satisfy S1: module/interface/identity/peer restart, reboot/topology churn and traffic-overlap coverage remain required.

The second executable PP-11 increment adds a dedicated two-VM `pp11s1` full-profile gate on both amd64 and arm64 with two vCPUs per guest. Each architecture executes exactly 100 counted disruptive cycles under continuously offered DECnet raw and MIRROR application traffic: 10 module reloads, 20 interface down/up cycles, 20 runtime identity changes/restores, 20 explicit peer-restart cycles observed as adjacency loss/recovery from the opposite VM, 20 host TAP detach/reattach topology cycles and 10 QMP reset/reboot cycles. Every cycle requires post-fault MIRROR recovery; the peer observer must account for all 35 guest-local disruptions per side. The gate retains cycle/fault timelines, PCAP, serial logs, host RSS/thread/CPU samples and guest link/adjacency/route/memory/slab snapshots before and after churn. Predeclared service limits require at least 40 successful MIRROR batches and 100 raw traffic markers per guest, p99 successful MIRROR latency no greater than 20 seconds, aggregate application payload throughput at least 25 B/s, both vCPUs exercised by application calls, final adjacency restored, at most eight live NSP links and slab growth within a 64 MiB envelope. This closes the explicit 100-cycle disruptive-churn floor only after exact-SHA execution is retained; repeated sequence-wrap/table/queue and malformed/control-flood pressure still remain before S1 can be declared complete.

### PP-12 — real peers and exact source release

Use exact pinned SIMH to host available real DEC operating systems and physical DEC systems where available. QCOCAL and IMPVAX are available SIMH-emulated VAX machines running OpenVMS and are the project's named SIMH/OpenVMS peers for PP-12 and any earlier/later PP case that explicitly requires SIMH machines. Prefer more than one DEC OS/version/role when practical. Local lab hosts may install pinned `tuklusan/simh` and create one or more RSX-11M-PLUS V4.6 instances when that adds useful independent DEC coverage. Required RSX/SIMH resources may be copied from MIM `1.13`, reachable through PYRTR `31.3`, but MIM itself is read-only: use only valid DECnet access methods, make no remote changes, run no load/stress/fault tests against it, and document the complete local acquisition/checksum/install/configuration/DECnet setup procedure. Build and install only from the exact hashed source tarball being accepted; repository-checkout or repaired-image substitutions do not satisfy PP-12 source provenance.

Test cold/warm boot, NIC early/late/initially down, configured startup, adjacency/routing, NSP/Session/NICE, every claimed user tool, service/module restart and repeated reboot only on project-controlled local/SIMH systems. **Never power-cycle, shut down, reboot, pause, resume, hard-stop, or otherwise change the running state of any machine reached beyond PYRTR (31.3) over the MULTINET/HECnet uplink.** Remote HECnet peers beyond PYRTR are observation/traffic peers only. Include disruptive peer restart/hard-stop tests only on locally controlled peers such as QCOCAL/IMPVAX or disposable lab VMs; retain non-disruptive wrong-credentials/object/node and interrupted-transfer checks against remote peers where safe.

Release-install recovery is mandatory for the source distribution: exercise clean install, reinstall over the same version, interrupted/staged-install failure, module unload/reload, kernel reboot on project-controlled systems, and manifest-driven uninstall. A failed install must not leave an untracked partial module/library/tool set. After reinstall or recovery, required network/application behavior must remain valid. No one-off source patch or manual repair is allowed after the source-tarball hash is fixed.

### PP-13 — upgrade, downgrade, rollback and mixed-version compatibility

**Owner-authorized skip for the first production release.** There is no N-1 production release and therefore no real mixed-version population to test. PP-13 is explicitly not applicable and non-blocking under project-owner authorization dated 2026-10-01.

Do not fabricate an N-1 release, synthetic downgrade path, or pretend mixed-version evidence merely to satisfy this stage. Re-enable PP-13 as a blocking stage once a real production release exists and an N-1/N compatibility surface is meaningful.

## Timing/scheduler tests

**Owner lab-execution rule from this heading onward:** execute only tests that are practically possible in the available lab. On remote hosts, the maximum permitted active test action is writing and executing user-mode C/C++ programs; do not perform kernel modifications, privileged disruptive experiments, host configuration changes, reboot/power operations or other unavailable/inappropriate tests. MIM `1.13` is a stricter exception: it is read-only via valid DECnet methods only, with no program installation/execution, load, stress or fault testing. Any requirement that cannot practically be exercised under these constraints must be recorded exactly as `Not tested in lab environment`; do not fabricate equivalent coverage or silently omit it.

Timers require explicit treatment: listener expiry and DR delay just-before/at/after boundaries; zero/fallback and maximum timers without arithmetic overflow; CPU saturation/workqueue delay during expiry; VM pause/resume; large scheduling stalls; timer cancel/rearm concurrent with unload/identity change/device removal; and jiffies wrap via test hooks where practical. The previously specified S5/S6 long-idle requirement is covered by the owner-authorized S3-S6 lab waiver for this release.

## Ethernet/device-path tests

Production release covers virtio plus at least one independent Ethernet driver/path, offloads on/off where skb shape can change, MTU change, multi-NIC, promisc/allmulti, device MAC change, staggered link availability, register/unregister/re-register, nonlinear/cloned/fragmented receive buffers and filter-reference coexistence. Bridge/bond/VLAN/macvlan are required when claimed. A second driver, SMP, multi-NIC, non-init namespace isolation and nonlinear skb input may not be excluded merely because the first harness does not create them.

## Security/hostile-input resilience

This is not a cryptographic-security claim. It requires bounded parsing and correct local privilege/authorization behavior under hostile input. Flood malformed/spoofed Layer-2/control traffic while valid peers remain active; attempt resource/churn exhaustion within lab limits; fuzz protocol/UAPI/socket inputs; require bounded CPU/memory/table growth and recovery; and ensure evidence does not unnecessarily expose credentials/secrets.

## Upstream traceability

### Route20

At `a9ef7c0b7f875f0dd2e8abaf11213798a8e4474c`, no standalone path named as a test suite was found in the pinned tree. Build is PP-00; live Ethernet/routing behavior maps to PP-04/PP-05 and native VDE Ethernet behavior maps to PP-08. Any subsequently discovered native test at this pin is classified before release.

### PyDECnet

The repository-maintained in-scope native module set at `9a844987bf3a1450632dee8d37e60a23a453bad3` runs in PP-00. Pinned test modules are disposed as follows:

| Upstream file | Disposition |
| --- | --- |
| `dntest.py` | harness |
| `systemtest.py` | harness |
| `file_app_exerciser.py` | mapped PP-07 |
| `module_app_exerciser.py` | mapped PP-07 |
| `test_bridge.py` | reference-health; feature-gated if bridge behavior is claimed |
| `test_common.py` | mapped PP-01 |
| `test_config.py` | mapped PP-00/PP-02/PP-07 where applicable; remaining options reference-health/feature-gated |
| `test_crc.py` | mapped PP-01 for applicable protocol checksums/CRC machinery; generic machinery reference-health |
| `test_ethernet.py` | mapped PP-01/PP-03/PP-05 |
| `test_event.py` | mapped PP-07 when management events are claimed; otherwise feature-gated/reference-health |
| `test_gre.py` | reference-health; feature-gated if GRE is claimed |
| `test_host.py` | mapped PP-07 |
| `test_mirror.py` | mapped PP-07 |
| `test_modulo.py` | mapped PP-01/PP-06/PP-08 where applicable |
| `test_mop.py` | reference-health; feature-gated if MOP is claimed |
| `test_multinet.py` | mapped/blocking PP-08 for MULTINET TCP transport |
| `test_nicepacket.py` | mapped PP-01/PP-07 |
| `test_nsp.py` | mapped PP-06 |
| `test_nsppacket.py` | mapped PP-01/PP-06 |
| `test_packet.py` | mapped PP-01 for codec invariants; generic framework internals reference-health |
| `test_route_eth.py` | mapped PP-03/PP-05 |
| `test_route_ptp.py` | mapped PP-05/PP-08/PP-09 for MULTINET point-to-point routing |
| `test_routing.py` | mapped PP-03/PP-05/PP-09 |
| `test_routingpacket.py` | mapped PP-01/PP-05 |
| `test_session.py` | mapped PP-07 |
| `test_sessionpacket.py` | mapped PP-01/PP-07 |
| `test_timers.py` | mapped PP-02/PP-06/PP-08 where protocol-visible; generic timer machinery reference-health |

### LinuxDECnet

At `ff39eef045d1e4b7b72a3d40111e89c07a473398`, LinuxDECnet is compatibility/reference material, not the kernel implementation base. `dnprogs/libvaxdata/src/test.c` is an explicit PP-00 reference-health conversion test and becomes mapped/blocking PP-07 evidence when VAX/RMS conversion is claimed. Other applicable userspace/API behavior is comparison/live-interoperability evidence. Historical defects are not copied for compatibility.

### SIMH

SIMH is a simulator dependency, not a DECnet protocol oracle. At `5b73b1032b52d19bf80752ea4d9cbbdc92e7b5e0`, normal builds run available per-simulator tests unless disabled. PP-00 therefore builds the exact selected DEC-host target with tests enabled and retains its transcript. CPU/device/network/timer tests used by the selected DEC host are blocking reference health for PP-12; serial/synchronous DECnet media are not part of this project's transport claim, and unrelated machine families remain reference-health only. DECnet/Linux semantic acceptance comes from the DEC operating system running on SIMH in PP-12.

## Gate and planned-case mapping

| Existing gate | Canonical home |
| --- | --- |
| E0 vectors | PP-01 |
| E1 two-node LAN | PP-03 |
| E2 two-LAN router | PP-05 |
| E3 alternate routers | PP-05 |
| E4 multi-area/L2 | PP-05 |
| VDE2 local/independent proof | PP-08 |
| MULTINET TCP framing/reconnect proof | PP-08 |
| VDE2 cross-runner/SSH proof | PP-08 |
| HECnet Area-31 controlled routing | PP-09 |
| harness false-green | PP-10 |
| 2→4→8→16 stress/endurance | PP-11 |
| real DEC/exact source release | PP-12 |
| upgrade/rollback/mixed version | PP-13 once N-1 exists |

Current `tests/lab/dniv-smoke.sh` and `run-two-node.sh` implement only the currently automated subset. A future PP case is not green merely because the present harness has no mode for it.

## Evidence required for every run

`docs/PP_EVIDENCE.md` is the canonical repository-tracked proof index. Every executed canonical PP case must get an entry tying its result to the exact candidate, workflow/run/job and retained artifact/log evidence. Owner-authorized skips and every impossible post-Timing requirement must also appear there explicitly; the ledger never substitutes for the raw artifacts.

Retain exact source commit/tree and source-tarball SHA-256; reference SHAs; kernel/compiler/configuration/harness version; built module/userspace/library/header/install-manifest hashes; architecture/vCPU/driver/offload/MTU/topology/identity/media; canonical case and stress level; random/fuzz/fault seed; requested and actual injection counts; packet/VDE2/MULTINET traces where transport behavior matters; complete serial/kernel/service/application logs; state/counter/resource snapshots before/during/after fault and after quiescence; fault/topology timeline; duration/packet/session/byte/restart/churn counts; measured distributions; diagnostic output; and explicit pass/fail for every canonical case/applicable negative family.

Missing mandatory evidence invalidates the run.

## Failure, retry and regression rule

A failed test remains a failure of that exact candidate until explained/fixed or the test itself is proven invalid. Retrying until green does not erase the first failure. Every discovered protocol, kernel or harness defect gains the smallest practical permanent regression test; minimized fuzz vectors and exact fault seeds join the corpus.

After any code, test-lab infrastructure, source-release workflow or acceptance-document change:

1. invalidate prior-candidate promotion status;
2. run exact-SHA mechanical/build/state plus the smallest fail-closed VM/protocol/interoperability gate that directly exercises the changed behavior and its required architecture coverage;
3. rerun every affected canonical acceptance stage and downstream dependent stage before claiming that stage complete;
4. do not launch the full repository-wide matrix after every intermediate fix. Full acceptance is reserved for closing a canonical PP increment, deliberate release/pre-production checkpoints, the weekly scheduled regression, or an explicit owner request;
5. promote only the exact unchanged commit whose required canonical evidence and final full matrix are green.

`PROFILE=targeted` is the bounded development profile for a named expensive gate. Its scope must identify the exact target and must not silently stand in for final full acceptance. `SCOPE=pp11-pressure` runs Build Bootstrap, Project State, dual-architecture E1 and only the amd64/arm64 PyDECnet L1 pressure jobs. `SCOPE=source-release` runs Build Bootstrap, Project State, dual-architecture source-tarball reproducibility/build/install/uninstall, and the exact packaged tarball through Debian 13/Fedora 42 on amd64/arm64 with GCC/Clang.

## Final pre-production gate

A candidate is releasable only when every claimed feature has executed positive canonical tests; every applicable negative family has a real executed case; every upstream test has a disposition; required x86_64/aarch64, SMP, kernel/toolchain and driver entries are green; independent-peer, routed and distributed VDE2/MULTINET requirements are green; false-green harness tests are green; the required stress/endurance tier is green; PP-13 is green when an N-1 release exists; diagnostics have no blocking finding; all evidence belongs to the exact unchanged candidate; and every required exact-SHA acceptance gate is green.

Anything less is development evidence, not pre-production acceptance.
