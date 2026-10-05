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

# DECnet-IV-Linux Test Lab

## Purpose

The lab proves DECnet protocol behavior independently of source-release production. Its VM disks are disposable test fixtures, never product artifacts. Protocol tests spend their time booting and exercising nodes, not reinstalling Linux packages or serializing mutable VM state.

## Persistent architecture foundations

There are two logical outer foundations: amd64 and arm64. GitHub-hosted runner root filesystems are ephemeral, so the foundations are retained in the Actions cache and restored onto the matching architecture runner. The stable ID is `outer-v2-<arch>-<foundation-fingerprint>`. The fingerprint is derived from the pinned Ubuntu image metadata and `build-foundation.sh`; it deliberately excludes the candidate source SHA.

A foundation contains only `base.qcow2`, `boot/vmlinuz`, `boot/initrd.img`, `session.env` and `SHA256SUMS`. It contains Ubuntu userspace, the pinned guest kernel/initrd, headers/compiler and independent-peer runtime dependencies. It must not contain project source, `decnet_iv.ko`, project tools, smoke services or any candidate SHA.

A restore is usable only if architecture, foundation fingerprint, Ubuntu release/snapshot and stable session ID match, every checksum verifies, `qemu-img check` passes, and the manifest contains no `SOURCE_SHA`. A source-only project commit therefore reuses the same foundation. A foundation recipe, Ubuntu pin or architecture change produces a different cache key.

The architecture-specific `dniv-runner-x64` and `dniv-runner-arm64` concurrency groups serialize creation and consumption. Cache eviction can require rebuilding a foundation, but ordinary candidate changes do not.

## Disposable exact-candidate images

`tests/lab/prepare-candidate-image.sh` clones the verified foundation into a disposable image, archives the exact checked-out `HEAD`, builds `decnet_iv.ko`, `dnctl` and `dnraw` against the foundation's pinned guest headers, records the exact source SHA, and installs the two-node and interoperability smoke entry points. It performs no package installation.

The Python two-node controller receives that disposable candidate image as its immutable per-run base and creates fresh qcow2 node overlays. Interoperability creates a disposable exact-candidate image plus a disposable reference image from the same foundation. The reference image receives only the current harness plus runtime helpers; Route20/PyDECnet payloads remain independently pinned and attached separately.

## Two-node execution

`tests/lab/dniv_lab.py` owns VM lifecycle for the Phase 2/E1 gate. It creates fresh qcow2 node overlays, a Linux bridge, two TAP devices, DECnet packet capture and one QMP socket per guest, launches QEMU directly, waits for guest acceptance markers, validates captured wire behavior and removes host networking on exit.

VM runtime files live under a deliberately short `/tmp/dniv-*` path so QMP UNIX sockets remain below the Linux pathname limit. Compact serial/pcap evidence is copied into `scratch/runtime/`; qcow2 overlays and QMP sockets are discarded and never uploaded. The E1 controller accepts `DNIV_LAB_NIC_MODEL` (`virtio-net-pci` or `e1000`) and `DNIV_LAB_VCPUS` (1, 2, 4 or 8). Full acceptance runs virtio/1-vCPU, virtio/2-vCPU, e1000/4-vCPU and virtio/8-vCPU E1 cases on both hosted architectures; all retain identical wire/state assertions.

## Architectures

The hosted matrix remains amd64 on `ubuntu-24.04` with `qemu-system-x86_64`, and arm64 on `ubuntu-24.04-arm` with `qemu-system-aarch64`. KVM is used when `/dev/kvm` is usable; otherwise the controller falls back to TCG. Native self-hosted KVM machines remain an optimization, not an acceptance dependency.

Phase 9 custom-kernel diagnostics use pinned upstream Linux v7.3-rc5 commit `72d3fcf802c45d00b300f25b848a93c3a2bd7c7e` on both architectures. Full acceptance runs KASAN, KCSAN, the license-compatible lockdebug subset and kmemleak. Kmemleak disables automatic scanning, ages/scans/clears a pre-DECnet baseline, exercises the normal E1 lifecycle, unloads `decnet_iv`, waits past the detector's five-second minimum report age, triggers a final manual scan and rejects any remaining leak report.

The PP-10 harness false-green track has its own exact-SHA workflow. Its first blocking control-plane increment deliberately presents a mutated tracked checkout, a corrupt integrity baseline, a mismatched parent candidate, stale scratch lineage, a non-main acceptance ref and a wrong requested revision, and requires every case to fail closed. Evidence is retained independently from protocol-lab artifacts so a broken acceptance control cannot be hidden by a guest pass marker.

The PP-10 evidence increment adds `tools/evidence_guard.py` for evidence-directory preflight plus required-file SHA-256 manifests, validates E1 wire counters independently from guest pass-like text, treats capture death as fatal while the lab is active, and records/validates requested diagnostic host-silence fault events. Final E1 acceptance also requires non-empty guest serial evidence containing the pass marker and the required lifecycle markers, so a forged pass-like line or dead logging cannot substitute for complete host-visible state. The false-green workflow mounts bounded tmpfs filesystems and literally exhausts byte and inode capacity, while its regressions reject same-size evidence corruption, truncation, omitted required members and duplicate/inactive requested fault events. Workflow evidence uploads are attempt-qualified, non-overwriting and error on missing files. A `retry_probe` mode deliberately fails attempt 1; on a failed-job rerun, attempt 2 must download and validate the attempt-1 artifact before it can pass. Full acceptance can request that executable proof with `PP10_RETRY_PROBE=true`. The persistent-resume negative now uses the real source-independent architecture foundation cache: `evidence_guard.py foundation` rejects missing/corrupt members, wrong architecture/session/fingerprint/release/snapshot metadata, source-candidate contamination and incomplete checksum manifests before reuse; disposable candidate overlays are still never resumed. Non-E1 interoperability faults are also fail-closed: every deliberate tc/raw/peer fault in `run-interop.sh` records a named fault log and is checked with `evidence_guard.py fault`; tc-backed cases require nonzero matched packets and raw/observer cases require their explicit proof marker. The false-green regression rejects inactive, wrong-name, duplicate, missing and marker-free non-E1 fault evidence.

## Addressing

Ordinary test nodes use area 31, nodes 70 through 79, with names DN70 through DN79 as defined in `tests/lab/test-addresses.env`. DECnet Phase IV protocol MACs are derived from area/node. E1 deliberately gives the emulated NIC a different primary MAC so the test proves protocol-originated frames use the DECnet-derived source MAC and unicast filtering survives later primary-MAC changes.

## Acceptance depth and runtime policy

Development acceptance is tiered so reliability coverage is preserved without re-running the entire production matrix after every small increment.

- **Targeted** runs one named expensive development gate without unrelated fan-out. `SCOPE=pp11-pressure` runs Build, Project State, dual-architecture E1 and only the amd64/arm64 PyDECnet L1 pressure jobs. `SCOPE=pp11-s2` runs the dual-architecture one-hour four-VM sustained-fault gate. `SCOPE=pp12` runs exact packaged-source lifecycle plus the strictly read-only real-DEC path. `SCOPE=post-timing` runs dual-architecture 4-vCPU E1 with the local post-Timing scheduler/device/UAPI-hostile extension, including a reply-acknowledged QMP pause/resume cycle. `SCOPE=source-release` runs Build, Project State, source-tarball reproducibility/build/install/uninstall on Ubuntu amd64/arm64, and the exact same tarball through Debian 13/Fedora 44 on amd64/arm64 with GCC/Clang.
- **Fast** is the default exact-SHA development gate. It runs repository policy, native amd64/arm64 build and unit coverage, project-state continuity, E1 on both architectures, and a small independent interop slice selected by change scope. `SCOPE=socket` runs the x64 PyDECnet L1 socket path; `SCOPE=routing` runs x64 Route20 L1 plus x64 PyDECnet L1; `SCOPE=all` runs the same two independent x64 paths. Fast evidence proves the increment is suitable for continued development; it is not phase/release promotion evidence.
- **Consolidated** is used after several related increments or at a subsystem checkpoint. It adds pinned reference baselines, E4 on both architectures, and a broader six-job interop slice spanning Route20/PyDECnet, amd64/arm64 and router/endnode roles.
- **Full** is mandatory for phase closure, release candidates, and any promotion claim. It runs pinned reference baselines, E1-E4 on both architectures, the dual-architecture post-Timing extension, every independent interoperability scenario, PP-11 S1 and S2, and the source-release/PP-12 gate. Portability is part of that gate and consumes the exact packaged archive; full acceptance no longer launches a duplicate standalone portability workflow.
- A scheduled weekly run uses the full profile against the exact current `main` SHA.
- The acceptance issue body may contain exact lines `PROFILE=targeted|fast|consolidated|full` and `SCOPE=all|socket|routing|pp11-pressure|pp11-s2|pp12|post-timing|source-release`. Targeted requires a targeted-only scope. Omitted profile defaults to `fast`; scheduled runs force `full`.

Long stress, soak and release-endurance work remains at the documented checkpoint/release stages. Runtime reduction comes from eliminating redundant repetition and serial scenario packing, not from deleting required production coverage.

## Interoperability

Route20 and PyDECnet remain pinned independent peers. Their VDE-enabled live pins support both modern and legacy libvdeplug open ABIs. Interoperability consumes the same source-independent architecture foundation, derives the disposable exact-candidate image, builds the exact pinned peer, and executes bounded L1/L2/endnode scenarios. Prior-run evidence restore is not part of execution. Route20 continues to run in an independent reference VM. PyDECnet runs its pinned source directly on the architecture-matched hosted runner through its native Linux TAP backend attached to the same host bridge as the candidate VM. This removes QEMU virtio/libpcap receive-filter timing from PyDECnet interoperability without changing candidate protocol behavior. The host TAP's Linux device MAC deliberately remains distinct from PyDECnet's DECnet logical MAC; assigning the logical MAC to the TAP creates a bridge-local FDB entry and prevents candidate unicast from reaching the TAP queue. PyDECnet readiness is application-backed and requires its own `DECnet/Python is running` marker. Route20 reference READY remains bounded at 180 seconds on amd64 and 600 seconds on ARM64; host PyDECnet readiness is bounded at 60 seconds.

## Scale and faults

Phase 9 scale execution is implemented by `tests/lab/dniv_scale.py` through the existing exact-candidate VM workflow. It supports 4, 8 and 16 independent VM modes without mutating the cached architecture foundation. The 4-node mode uses two LANs with one forced router and three endpoints; the 8/16-node modes use paired areas with L1/L2 routers, a transit LAN and multiple independent endnodes in each area. Host PCAP validation requires the expected forwarding source MAC and visit count for every endpoint direction. Full acceptance dispatches `scale4` and `scale8` on both x86_64 and aarch64 plus the distributed 16-node scale workflow; all three scale levels are promotion gates with retained exact-candidate evidence. Later Phase 9 changes must preserve the same 4/8/16-node coverage, deterministic fault evidence, SMP breadth, mixed-architecture distributed segments and independent peers while keeping exact-SHA evidence and bounded hosted-job execution.

E4 router readiness is adjacency-backed rather than a boot marker: L1 routers must see their local L2 peer UP, and L2 routers must see both the local L1 and cross-area L2 peer UP before endpoints start. Endpoint probes remain active for a bounded 90-second convergence window so independent ARM64 TCG boot skew cannot turn a valid routed path into a one-direction sampling false failure. Host PCAP checks still require the correct router source MAC and visit count at transit and destination segments in both directions.

## Distributed VDE2, MULTINET and Area-31

VDE2 and MULTINET are independent transport test tracks. `tests/lab/prove-vde2.sh` is green in enhanced run `35959075714` with three-endpoint frame stress, endpoint/switch restart, a missing-endpoint negative and Route20/PyDECnet adjacency recovery. `tests/lab/prove-multinet.sh` is green in enhanced run `35960257018` with the pinned PyDECnet MULTINET module suite, an unopened-port negative, two simultaneous live connector circuits, repeated connector churn and central-listener restart/recovery. These tracks are never combined to manufacture a pass.

Cross-runner VDE2 is proven on Phase 8 exact candidate `9b73e61bbd0f95b82410276f7b5dc3db94e219ba` by run `36258564105`. Each hosted machine owns its own pinned `tuklusan/vde-2` switch and the authoritative cable carries the framed VDE stream through one bastion SSH/socat rendezvous per side. The proof requires three marked frames, Route20/PyDECnet adjacency, a hard transport cut with frame loss and adjacency expiry, bridge recovery, a client-switch restart and the second adjacency recovery. Both server and arm64 client jobs passed on the unchanged candidate; the automatic x86_64 client fallback remained available only for narrowly classified outer SSH-connect failures.

The Area-31 stage uses `userspace/dnmultinet/dnmultinet.py` as a VDE-to-MULTINET gateway in TCP client mode. Its repository-tracked workflow obtains `MULTINET_REMOTE_HOST`, `MULTINET_REMOTE_PORT`, `VAX_ADDR`, `VAX_USERNAME` and `VAX_PASSWORD` from Actions secrets only. The first executable step detects missing prerequisites by name without printing values. The workflow now builds an exact native DECnet-IV-Linux amd64 candidate, attaches it to the gateway VDE segment, passes assigned DECnet identities through a private read-only control disk, and requires gateway adjacency plus native NML and MIRROR traffic to the VAX router. The MULTINET endpoint is one Area-31 area router; the VAX at `VAX_ADDR` is another area router reachable through that path. Phase 8 remote evidence is green on exact candidate `9b73e61bbd0f95b82410276f7b5dc3db94e219ba` in Area-31 run `36258654316`; future Phase 9/production runs must continue to re-prove the same secret-safe external path rather than inheriting that result.

Pre-production keeps reusable Linux/VAX test pairs under `tests/lab` (with VAX-side helpers in a dedicated subdirectory) for the delivered claimed node/route/NICE information and counters, NSP/Session/object access, login, DAP/FAL, PHONE, mail and task-access paths wherever the remote-peer safety policy permits; application experiments remain supplemental. Evidence must redact credentials and must distinguish local transport proof, remote routing proof and application proof. See `docs/HECNET_LAB.md`.

## Source-release separation

The production object is the reproducible source tarball defined by `docs/DELIVERY.md` and `.github/workflows/source-release.yml`. `image/ubuntu-base/build-foundation.sh` and all derived QCOW2 files are lab-only infrastructure used to obtain independent disposable kernels for protocol, fault and stress testing. No VM disk file is a release artifact or installation requirement.

The exact-artifact portability gate also prepares Torvalds Linux v6.8 commit `e8f897f4afef0031fe618a8e94127a0934896aba` on both supported architectures and requires the packaged source to complete `build.sh` plus staged install/uninstall against kernel release `6.8.0`. This makes the documented Linux 6.8 compatibility floor an executed release gate rather than only a version check. The amd64 packaging job also executes the PP-00 source-input negatives for checksum mismatch, truncated archives, missing/wrong `SOURCE-METADATA`, generated payload injection, wrong pin, read-only output, missing/wrong/too-old kernel trees, below-floor Python/GCC/Clang and non-root live installation before the artifact is accepted.

### PP-12 exact-source real-peer mode

`PROFILE=targeted`, `SCOPE=pp12` dispatches the ordinary exact source-release gate with `pp12_real_peers=true`. PP-12 starts only after the amd64 package job, arm64 extracted-source validation and both-architecture Debian/Fedora GCC/Clang portability jobs are green. Each PP-12 architecture job downloads that same run's source artifact, verifies its checksum and `SOURCE-METADATA`, and builds a disposable guest from the extracted tarball rather than from a repository checkout.

The guest uses the production `build.sh`, `install.sh` and `uninstall.sh`. It proves same-version reinstall, live module load/unload/reload, an actual warm reboot, manifest-driven live uninstall and reinstall, installed-client selftests, and then reuses the recovered image for the secret-safe Area-31 proof. The remote phase adds `sethost`, `ncp`, `dnnice`, `dnping` and safe temporary QCOCAL DAP alias checks to the existing login/FAL/NICE/MIRROR/HTTP/task coverage. PHONE/mail and any operation that would leave inappropriate remote state remain subject to the HECnet safety boundary; their functional coverage remains local/controlled. Full acceptance requests the same PP-12 mode so final release evidence is tied to the exact packaged source artifact.

For direct host-TAP PyDECnet runs, a separate host `dnraw` loop injects marked DECnet-Ethernet unicast frames through the Linux bridge toward the candidate logical MAC. This preserves the same post-NIC-MAC-change lower-layer receive proof used by guest-backed references without coupling that check to PyDECnet routing/NSP convergence.

Connect-control retransmission is proven separately from established-link data retransmission. Before a new MIRROR `connect()`, the host blackholes reference-to-candidate unicast so Connect Confirm replies are lost while candidate CI/RCI traffic still reaches PyDECnet. Blocking connect must terminate with `EHOSTUNREACH`; packet capture must show the initial CI plus every configured RCI carrying a unique connect-data marker. After fault removal, a fresh marked CI and marked MIRROR record must succeed without restarting either endpoint.

Direct PyDECnet interoperability includes deterministic NSP loss/retransmission and retry-exhaustion proofs before inbound listener testing. The retry-exhaustion case holds the same reference-to-candidate unicast fault until the candidate has consumed its five-attempt NSP response budget. Native userspace must wake with `EHOSTUNREACH`, `DSO_DISDATA` reason 39 and `POLLERR|POLLHUP`; packet capture must contain all five marked candidate attempts. After the injector is removed, a fresh MIRROR connection must succeed before later tests proceed.

Direct PyDECnet interoperability includes a deterministic NSP loss/retransmission proof before inbound listener testing. After a native MIRROR link reaches RUN, the candidate emits a unique loss-probe record while the host installs a bounded eight-second ingress filter on the PyDECnet TAP that drops only reference-logical-MAC unicast to the candidate. The filter's packet counter must prove that loss actually occurred; multicast routing/hello traffic is not dropped. Packet capture must then show the single application send appearing at least twice from the candidate, proving timeout retransmission, followed by a reference response after the filter is removed.

Fast/consolidated/full x64 PyDECnet L1 interoperability also includes a bounded reserved-port wire discriminator. After all ordinary socket tests complete, the host injects one valid Connect Confirm to an unmapped local link and a burst of valid Connect Initiates with unique remote link IDs sufficient to exhaust the 256-entry NSP connection table. The candidate must emit at least one Disconnect Confirm reason 41 (No Link) and at least one reason 1 (No Resources); packet capture validates both wire responses. The guest requires a large non-hello receive-counter delta before advancing, preventing a missing injector from false-passing. This destructive saturation runs only after socket functionality has been proven and before the reference is stopped.

Consolidated/full PyDECnet x64 L1 interoperability adds one bounded Session-Control response-timer discriminator without lengthening every fast run. Object 247 deliberately leaves an inbound CI unaccepted past the 30-second connection-response bound. The independent peer must receive reject reason 38, packet capture must contain the candidate's reason-38 Disconnect Initiate, and a second request to the backlog-one listener must then be accepted and echo a uniquely marked record. The second request proves the timed-out first link was removed from the pending listener ring rather than leaking backlog capacity. This timer proof runs only in the x64 PyDECnet L1 job at consolidated/full depth.

Full-profile amd64 PyDECnet L1 also carries the first PP-11 churn floor: the native socket-lifecycle probe must complete exactly 100 connect/exchange/disconnect cycles, with the requested/completed count preserved in guest and host-visible evidence. Fast/consolidated runs keep the existing 16-cycle bound. This is only the socket-lifecycle part of PP-11 S1; disruptive module/interface/identity/peer/reboot/topology churn remains separate.

Direct PyDECnet interoperability also exercises inbound native sockets. The pinned host-TAP peer exposes its Unix Session API; `pydecnet-inbound.py` connects to candidate object 240 and named object `DNIVTEST`. The guest `dnaccept` server must accept both, report the PyDECnet node/source object through `getpeername()`, and echo normal records. The accepted interrupt/OOB proof sends two PyDECnet interrupts per connection, requires Linux `POLLPRI` and `SIOCATMARK` visibility, receives them with `MSG_OOB`, sends an interrupt back to PyDECnet, proves the second peer interrupt only after Linux replenishes interrupt credit, then proves normal record traffic still works before orderly disconnect.

The classic socket-option follow-up adds option evidence in both directions. `dnmrr` sets `DSO_CONACCESS` and `DSO_CONDATA` before its native MIRROR connection, verifies those values through the socket API, and checks `DSO_LINKINFO` in RUN state; packet capture requires the resulting candidate CI access/connect-data image. For inbound connections, PyDECnet supplies username/password/account and connect data, `dnaccept` retrieves them through `getsockopt()`, the listener returns `linux-accept` as CC connect data, and the PyDECnet connector verifies that accept payload. Packet capture requires both reference CI option images and candidate CC data. The existing pinned-PyDECnet `router-endnode` outbound-NSP reference defect remains excluded only from the inbound socket subtest; its candidate-outbound MIRROR/options plus routing/NSP/fault checks remain mandatory.


## PP-11 lab scope authorization

Project-owner authorization dated 2026-10-01 marks PP-11 S3, S4, S5 and S6 as not executable in the current lab and therefore skipped/non-blocking for this release. S0, S1 and S2 remain executable and blocking. Do not synthesize or relabel shorter runs as S3-S6 evidence.


## PP-13 first-release authorization

Project-owner authorization dated 2026-10-01 marks PP-13 completely skipped/non-blocking for the first production release because no N-1 production version exists yet. Do not create synthetic mixed-version, downgrade, rollback, or upgrade evidence. PP-13 becomes relevant only after a real prior production release exists.

## Remaining pre-production owner constraints

The canonical proof index is `docs/PP_EVIDENCE.md`; raw serial/pcap/log/state proof remains in run-attempt-qualified Actions artifacts. Every canonical case must have an explicit result and evidence pointer before it can contribute to release acceptance.

PP-11 S3-S6 remain owner-authorized skips for this release. From and including `## Timing/scheduler tests` in `docs/PRE_PRODUCTION_TEST.md`, execute only practically possible tests. Remote hosts may be used only for user-mode C/C++ test programs, with unavailable requirements recorded exactly as `Not tested in lab environment`. MIM `1.13` is stricter: read-only valid DECnet methods only; no remote writes, program execution, load/stress/endurance/fault testing or state change.

For additional local DEC peers, the lab may install pinned `tuklusan/simh` and create multiple local RSX-11M-PLUS V4.6 instances. Resources may be copied read-only from MIM, but installation and DECnet configuration happen only on project-controlled local systems and the complete acquisition/hash/build/configuration procedure is retained as evidence.

## PP-11 S1 disruptive churn gate

`DNIV_LAB_MODE=pp11s1` runs `tests/lab/dniv_pp11_s1.py` with two exact-candidate L1-router VMs and two vCPUs per guest. The guest smoke state machine serializes the first 70 counted cycles so one peer remains stable while the other performs module, interface, identity and explicit peer-restart churn; the stable peer must observe every adjacency loss/recovery. The host then performs 20 TAP detach/reattach topology cycles and 10 QMP reset/reboot cycles. Each architecture therefore executes exactly 100 cycles.

Raw DECnet Ethernet traffic remains offered throughout, MIRROR application traffic is continuously retried, and every cycle must return to a working MIRROR path. The retained evidence set contains `cycles.tsv`, `host-resources.tsv`, `summary.env`, both serial logs and the DECnet PCAP. `summary.env` records the exact cycle totals plus p50/p95/p99 application latency, payload throughput, CPU-affinity coverage, traffic-marker counts and the declared resource envelopes. Full acceptance dispatches this gate on amd64 and arm64 with two vCPUs; fast/consolidated acceptance does not pretend to satisfy the S1 churn requirement.
