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
| PP-11 S3 | OWNER-AUTHORIZED SKIP | Commit `39ca86f0f11d525abf062684de8779baa9eaef72`; no substitute evidence permitted. |
| PP-11 S4 | OWNER-AUTHORIZED SKIP | Commit `39ca86f0f11d525abf062684de8779baa9eaef72`; no substitute evidence permitted. |
| PP-11 S5 | OWNER-AUTHORIZED SKIP | Commit `39ca86f0f11d525abf062684de8779baa9eaef72`; no substitute evidence permitted. |
| PP-11 S6 | OWNER-AUTHORIZED SKIP | Commit `39ca86f0f11d525abf062684de8779baa9eaef72`; no substitute evidence permitted. |
| Full acceptance of `081f2ef9cb219a143ad15e18a34ad1a4ea376951` | FAIL | Issue #875. KCSAN run `36954406524`, amd64 job `110674076971`, artifact `11206077517`: upstream Linux timer-migration race summary `tmigr_cpu_deactivate / tmigr_next_groupevt`. Portability run `36954591057`, Debian 13 amd64 GCC job `110674646311`, artifact `11205828708`: Debian mirror mid-sync size/hash mismatch before candidate compilation. This candidate is not promotable. |
| PP-12 exact release image / real DEC peers | PARTIAL | QCOCAL and IMPVAX are available SIMH/OpenVMS peers. Exact PP-12 release-image execution is not yet closed. Any additional RSX-11M-PLUS V4.6 instances must be local/project-controlled and built from documented, hashed inputs. MIM may supply read-only copied resources only. |
| PP-13 first release | OWNER-AUTHORIZED SKIP | Commit `081f2ef9cb219a143ad15e18a34ad1a4ea376951`; no real N-1 release exists, so synthetic downgrade/rollback/mixed-version evidence is prohibited. |

## Post-Timing ledger rule

Beginning with `## Timing/scheduler tests` and continuing through every later section of `docs/PRE_PRODUCTION_TEST.md`, each canonical requirement is appended here when reached. Executed requirements get their exact proof pointer. Requirements that cannot practically be exercised under the owner constraints get the literal result `Not tested in lab environment`. No requirement may be silently omitted.
