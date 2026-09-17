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

# Scratch Resume Index

## Current checkpoint

Phase 3 remains active and all substantive work stays on `main`. Candidate promotion is controlled only by exact-SHA mechanical, build, VM, reference, protocol and interoperability gates.

The two-node lab uses `tests/lab/dniv_lab.py`, a Python direct-QEMU controller with QMP shutdown, Linux bridge/TAP networking, packet capture, serial marker assertions and disposable qcow2 node overlays. Writable inner-VM checkpoints remain retired.

The two architecture slots now retain immutable outer base sessions across acceptance jobs. The session identifier is `outer-v1-<arch>-<source-sha>` and the persisted payload is `base.qcow2`, `boot/vmlinuz`, `boot/initrd.img`, `session.env` and `SHA256SUMS`. Because GitHub-hosted runner root filesystems are ephemeral, the payload is stored in the Actions cache and restored onto the matching amd64 or arm64 runner. Restores are accepted only when the manifest matches the exact architecture and source SHA, all checksums verify, and `qemu-img check` passes.

The same outer session is consumed by `vm-lab.yml` and `interop.yml`. Architecture-specific `dniv-runner-*` serialization means the first job can create a missing session without a same-architecture race; later jobs for that exact candidate restore it. New source SHAs receive new session IDs and cannot reuse a prior candidate image.

Interoperability no longer accepts or downloads prior-run scratch evidence. Those restored artifacts were lineage-only and did not participate in VM execution. Candidate/reference working images remain disposable and are rebuilt from the verified immutable outer base; they are not persisted as acceptance state.

Repository branch policy remains exactly one remote branch, `refs/heads/main`. Repository-policy/control jobs do not consume protocol-lab concurrency slots. GitHub-owned actions, including cache restore/save, are pinned to immutable full SHAs.

The first persistence candidate `22fa6771250b5f46b68ac822fd9af38d82baba23` is historical: GitHub rejected `vm-lab.yml` before job creation because `runner.temp` is not available in job-level `env`. The corrected definition stores the restored cache under `${{ github.workspace }}/scratch/outer/<arch>`, which is ignored by Git and valid at job scope.

| Field | Current value |
| --- | --- |
| Protocol phase | Phase 3 |
| Working ref | `main` only |
| Remote branch invariant | only `refs/heads/main` |
| Hosted job ceiling | 75 minutes |
| Protocol runner queue policy | architecture-specific `dniv-runner-*`, `queue: max` |
| Repository-control queue policy | exact-SHA workflow concurrency; no protocol runner slot |
| VM lifecycle | Python direct QEMU/QMP for two-node gate |
| Outer architecture state | immutable exact-SHA base session cached per architecture |
| Outer session ID | `outer-v1-<arch>-<source-sha>` |
| Inner VM disk state | disposable qcow2 overlays/derived images |
| Writable inner VM checkpoint artifacts | retired |
| Interop prior-run evidence restore | retired |
| Compact evidence retention | 30 days maximum |
| Acceptance child binding | parent run ID + exact expected SHA |
| Current feasibility target | E1 and interoperability using restored architecture sessions |

## Persistent run index

Run IDs remain lineage, not execution state. Persistent execution input is limited to the verified immutable architecture session cache. Mutable workflow state remains below ignored `scratch/runtime/`; compact evidence may be uploaded, but it never substitutes for exact source/tree verification or becomes writable guest state for a later run.

## Next action

Dispatch fresh exact-head acceptance. Confirm each architecture creates at most one cache session for the exact candidate, later same-SHA jobs restore it, and no protocol job repeats full base-image construction after that session exists. Then continue Phase 3 protocol/interoperability debugging from the resulting evidence.
