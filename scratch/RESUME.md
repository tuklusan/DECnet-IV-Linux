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

The prior acceptance lineage on `3f41bec910b5b07520c23b05dcbb1996d091ef62` proved native x86_64/aarch64 build and continuity but failed before protocol acceptance in guest-image preparation. Commit `102972a5e8a35e517ac65bd100a8d3f271f37720` corrected late ext4 metadata/conversion instability. The current work changes the acceptance architecture rather than continuing to add checkpoint/image plumbing.

The two-node lab now uses `tests/lab/dniv_lab.py`: a Python direct-QEMU controller with QMP shutdown, Linux bridge/TAP networking, packet capture, serial marker assertions, and disposable qcow2 overlays over one immutable candidate base. `tests/lab/run-two-node.sh` is retired. VM resume inputs, archived writable checkpoints, rebasing, checksum sealing and stale-checkpoint pruning are removed from `vm-lab.yml`; transient `.qcow2` and `.qmp` files are excluded from evidence uploads.

The hosted workflow still builds one immutable candidate base per architecture. This is deliberate for the first feasibility run. If E1 is green, the next reduction is to prepare/persist the base outside ordinary protocol runs, preferably on native self-hosted KVM-capable x86_64 and aarch64 runners. Interoperability has not yet been migrated and remains the next target after the Python two-node path proves itself.

Repository branch policy remains exactly one remote branch, `refs/heads/main`. GitHub-owned actions remain pinned to immutable full SHAs. The machine helpers remain `tools/workflow_guard.sh`, `tools/integrity_scan.py`, `tools/project_state_gate.py` and `tools/workflow_budget_gate.py`.

| Field | Current value |
| --- | --- |
| Protocol phase | Phase 3 |
| Working ref | `main` only |
| Remote branch invariant | only `refs/heads/main` |
| Hosted job ceiling | 75 minutes |
| Runner queue policy | `queue: max`; no cancellation of pending acceptance work |
| VM lifecycle | Python direct QEMU/QMP |
| VM disk state | disposable qcow2 overlays over immutable base |
| Writable VM checkpoint artifacts | retired |
| Compact evidence retention | 30 days maximum |
| Acceptance child binding | parent run ID + exact expected SHA |
| Previous acceptance parent | `35232209976` on `3f41bec910b5b07520c23b05dcbb1996d091ef62` |
| Previous native build run | `35232466634`, success |
| Previous project-state run | `35232469698`, success |
| Previous E1 VM run | `35232475152`, image-path failure before protocol acceptance |
| Previous interoperability run | `35232477599`, image-preparation failure before protocol assertions |
| Current feasibility target | E1 on Python overlay controller |

## Persistent run index

Mutable workflow state remains below ignored `scratch/runtime/`; restored evidence may exist below ignored `scratch/restored/` only for workflows that explicitly consume prior evidence. A run ID is lineage, not persistent execution. VM writable disks are ephemeral and do not transfer acceptance state between runs.

## Next action

Commit the Python/QEMU migration and checkpoint cleanup directly to `main`, then dispatch fresh exact-head acceptance. Treat E1 as the proof point for the new controller. If it passes on both architectures, migrate interoperability orchestration and then remove the remaining protocol-test image mutation machinery where it is no longer needed.
