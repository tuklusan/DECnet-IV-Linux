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

# Pre-Production Evidence Ledger

This is the canonical repository-tracked index for `docs/PRE_PRODUCTION_TEST.md`. Raw proof remains in retained run-attempt-qualified workflow artifacts, packet captures, serial logs, state snapshots and application logs. A ledger entry without its required raw evidence is not a pass.

## Result vocabulary

- `PASS` — exact executed requirement passed and the listed raw evidence is retained.
- `FAIL` — executed requirement failed; the candidate is not promotable on that evidence.
- `PARTIAL` — useful executed proof exists but does not satisfy the full canonical requirement.
- `OWNER-AUTHORIZED SKIP` — explicit release-owner waiver; never relabel as test evidence.
- `Not tested in lab environment` — required wording for a post-Timing requirement that cannot practically be executed under the current lab constraints.

Every future entry records the PP case, exact candidate SHA, architecture/topology/peer, workflow/run/job, artifact/log identifiers, requested and actual counts/duration/faults, and the final result.

## Canonical owner constraints

- MAIN only; branches are prohibited.
- PP-11 S0-S2 remain blocking. PP-11 S3-S6 are `OWNER-AUTHORIZED SKIP` for this release under commit `39ca86f0f11d525abf062684de8779baa9eaef72`.
- PP-13 is `OWNER-AUTHORIZED SKIP` for the first production release under commit `081f2ef9cb219a143ad15e18a34ad1a4ea376951`.
- From `## Timing/scheduler tests` onward, execute only tests practically possible in the available lab. Remote-host active test programs are limited to user-mode C/C++; no kernel/privileged disruptive work, host reconfiguration or reboot/power operations. Every impossible requirement is entered as `Not tested in lab environment`.
- PYRTR `31.3` is the disruptive-test boundary. Systems reached beyond it are non-disruptive observation/traffic peers.
- MIM `1.13` is stricter: read-only access by valid DECnet methods only. Never write/change remote state, install/execute test programs, or use MIM for load, stress, endurance, negative/fault-tolerance or disruptive testing. Required resources may only be copied away read-only.
- Local lab systems may install pinned `tuklusan/simh` and create multiple local RSX-11M-PLUS V4.6 instances from resources copied read-only from MIM. Acquisition source, hashes, SIMH pin, install steps, RSX configuration and DECnet configuration must be retained before those instances count as evidence.

## Current proof ledger

| Case | Result | Exact candidate / evidence |
| --- | --- | --- |
| PP-10 complete false-green/evidence closure | PASS | `e60660c3b7d311451fc854464fa1d7438222f7e2`; acceptance issue #867; all 28 full-profile child workflows green. Harness False-Green run `36941947721` passed required failed-job retry; retained attempt-1 artifact `11200198661`, attempt-2 artifact `11200561788`. Distributed Scale16 `36942234978` green on both amd64 and both arm64 partitions. |
| PP-11 S1 socket-lifecycle implementation | PARTIAL | Full amd64 PyDECnet L1 requests exactly 100 connect/exchange/disconnect cycles; fast/consolidated request 16. Fast acceptance of the surrounding implementation is green on `7b5cf5a02acce315964b708ddd0f544047981e48` via issue #870, but that fast profile is not the 100-cycle S1 proof and does not close S1. |
| PP-11 S1 disruptive module/interface/identity/peer/reboot/topology implementation | PARTIAL | The full-only `pp11s1` two-VM gate is implemented for amd64 and arm64 at two vCPUs with exactly 100 counted cycles per architecture: module 10, interface 20, identity 20, peer-restart 20, topology 20, reboot 10. It requires continuous raw/MIRROR traffic, exact peer-loss/recovery accounting, post-cycle MIRROR recovery, retained p50/p95/p99/throughput and resource envelopes. No PASS is recorded until exact-SHA execution completes; repeated sequence-wrap/table/queue/malformed-control pressure remains separate. |
| PP-11 S1 disruptive churn execution on `73e96f38f73cff067769353fa2bb998cb78b563d` | FAIL | Full issue #878; Python QEMU VM Lab run `36959665140`. amd64 job `110690334636`, artifact `11208856214`: adjacency recovered after module reload 1 and background MIRROR traffic continued, but the harness's concurrent one-shot MIRROR probe failed. arm64 job `110690334421`, artifact `11208986490`: module cycles 1-2 passed and cycle 3 hit the same probe race. This is harness evidence, not a protocol PASS; successor waits for a fresh success from the continuous application stream and fails fast on guest error markers. |
| PP-11 S1 churn execution on `a0a20d942a15f7cb51044489d6eedf93f8823602` | FAIL | Full issue #880, run `36997320356`: amd64 job `110806915328` artifact `11223764342` timed out after DN71 reached 205 NSP links; arm64 job `110806915532` artifact `11223059783` failed `pp11-post-cycle-mirror` after DN70 link growth reached 41. Both PCAPs retain live router hellos, peer unicast and PP-11 raw traffic through termination, so wire adjacency remained active. |
| PP-11 S1 scheduled revalidation on `a0a20d942a15f7cb51044489d6eedf93f8823602` | FAIL | Run `36999699012` reproduced the same pattern: arm64 job `110821094506` artifact `11224648060` failed at peer-restart 3 after 43 links; amd64 job `110821094908` artifact `11225242239` timed out with DN71 at 138 links before its first local module cycle. This confirms a protocol-side unreclaimed NSP connection-slot leak, not only the prior probe harness race. |
| PP-11 S1 scheduled diagnostics on `a0a20d942a15f7cb51044489d6eedf93f8823602` | PARTIAL | KCSAN run `36999503334`: amd64 passed; arm64 reported exact pair `memchr_inv / refresh_cpu_vm_stats`, artifact `11225005387`. Both raced-access stacks are upstream `mm/vmstat.c`; pinned `torvalds/linux` `ce1e0223d8ad4211275c82a17ed6d43ab81e13d9` retains the same advisory vmstat scan/flush paths and documents tolerated imprecision. Scheduled Scale16 run `36999675158` is green on all four amd64/arm64 partitions. |
| PP-11 S1 detached-link correction execution on `b01b50fd1f33250fa7c18cae57e24317967d4559` | PARTIAL | Full issue #882, run `37017940457`. The protocol leak is corrected in the executed local-churn evidence: amd64 DN70/DN71 peak NSP link counts were 5/5 and arm64 were 5/6, versus 138-205 and 41-43 before the fix; all four guests completed the 35 guest-local module/interface/identity/peer-restart cycles with final adjacency UP. The run did not close S1 because two independent harness defects stopped the host phase. amd64 job `110873367775`, artifact `11234426233` SHA-256 `e8ec857e3e0cf9ba412fd33ddbcdc4e46987c1a72a1cffdc2e8f3614f6a75dea`: DN70 entered its observer after DN71 had already started the reciprocal actor and saw only 34/35 transitions. arm64 job `110873367262`, artifact `11234516392` SHA-256 `32b5ba6be7fa07d04a28bfabbc70f7aebf4a5341b57a7756b8cc6cf1a93ed95a`: both guests reached HOST-READY and all 20 topology cycles passed, then the first QMP `system_reset` caused DN70 QEMU to exit because the common launch still carried `-no-reboot`. |
| Full acceptance diagnostics on `b01b50fd1f33250fa7c18cae57e24317967d4559` | FAIL | Issue #882 was green outside PP-11 S1, amd64 KCSAN and arm64 KASAN. KCSAN run `37017706629` amd64 job `110872585255`, artifact `11232847830` SHA-256 `3015063da09ba917d845e1e3ca966a65b03d0f478160d70b86ba218f7e36704a`, reported `mem_cgroup_wb_stats / tick_do_update_jiffies64`. Pinned upstream Linux `ce1e0223d8ad4211275c82a17ed6d43ab81e13d9` shows the reader reaches a direct `jiffies_64` read through `mem_cgroup_flush_stats_ratelimited()`; upstream commit `ca1f4a5ecab084af7f405baa902edbed171b57e6` documents the same `tick_do_update_jiffies64` writer racing a direct `jiffies_64` reader and explains that using volatile `jiffies` prevents the KCSAN warning. This is generic Linux timer accounting, so only this exact pair and reverse ordering are vetted. KASAN run `37017683435` arm64 job `110872505018`, artifact `11234056167` SHA-256 `7f0d6e6dd69109bc56045653c1f78f5d0f1f95410e9048e3be0baf022af8e168`, had no KASAN finding and both guests passed E1, but PCAP validation saw one DN70 All-Endnodes hello. The retained PCAP shows DN70's first router hello omitting DN71 at 14:34:39.257 UTC and the lone DR hello only at 14:34:45.704 UTC; the count-based host handoff reacted late. The successor freezes on that semantic peer-unlisted router hello instead. |
| PP-11 S3 | OWNER-AUTHORIZED SKIP | Commit `39ca86f0f11d525abf062684de8779baa9eaef72`; no substitute evidence permitted. |
| PP-11 S4 | OWNER-AUTHORIZED SKIP | Commit `39ca86f0f11d525abf062684de8779baa9eaef72`; no substitute evidence permitted. |
| PP-11 S5 | OWNER-AUTHORIZED SKIP | Commit `39ca86f0f11d525abf062684de8779baa9eaef72`; no substitute evidence permitted. |
| PP-11 S6 | OWNER-AUTHORIZED SKIP | Commit `39ca86f0f11d525abf062684de8779baa9eaef72`; no substitute evidence permitted. |
| Full acceptance of `081f2ef9cb219a143ad15e18a34ad1a4ea376951` | FAIL | Issue #875. KCSAN run `36954406524`, amd64 job `110674076971`, artifact `11206077517`: upstream Linux timer-migration race summary `tmigr_cpu_deactivate / tmigr_next_groupevt`. Portability run `36954591057`, Debian 13 amd64 GCC job `110674646311`, artifact `11205828708`: Debian mirror mid-sync size/hash mismatch before candidate compilation. This candidate is not promotable. |
| PP-12 exact release image / real DEC peers | PARTIAL | QCOCAL and IMPVAX are available SIMH/OpenVMS peers. Exact PP-12 release-image execution is not yet closed. Any additional RSX-11M-PLUS V4.6 instances must be local/project-controlled and built from documented, hashed inputs. MIM may supply read-only copied resources only. |
| PP-13 first release | OWNER-AUTHORIZED SKIP | Commit `081f2ef9cb219a143ad15e18a34ad1a4ea376951`; no real N-1 release exists, so synthetic downgrade/rollback/mixed-version evidence is prohibited. |

## Post-Timing ledger rule

Beginning with `## Timing/scheduler tests` and continuing through every later section of `docs/PRE_PRODUCTION_TEST.md`, each canonical requirement is appended here when reached. Executed requirements get their exact proof pointer. Requirements that cannot practically be exercised under the owner constraints get the literal result `Not tested in lab environment`. No requirement may be silently omitted.
