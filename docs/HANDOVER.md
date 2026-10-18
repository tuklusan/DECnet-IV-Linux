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

# Handover

This is the stable resume entry point for DECnet-IV-Linux.

## Current completion priority

Previously closed PP-11 S1/S2 and PP-12, the post-Timing practical-lab ledger, and an earlier
source-delivery 3/3 audit are historical evidence, not promotion evidence for changed packaged
bytes. PP-11 S3-S6 and first-release PP-13 remain owner-authorized skips. An altered source
release does not inherit an earlier 3/3 audit or exact-SHA acceptance.

The current release blocker is three independent comprehensive zero-defect semantic reviews
of fresh copies of one fully green exact-SHA packaged source artifact. During a defect-bearing
discovery pass, prove and repair each defect minimally on main with source-derived regression;
recheck affected files/dependencies and CONTINUE the SAME discovery pass at the next unreviewed file.
Preserve exact file/source SHA provenance; after-repair review is provisional until final-package
reconciliation. Local/targeted regressions run per repair, but there is NO per-repair hosted
qualification or fresh artifact download. All four green same-SHA source gates and an independently
fresh, safely verified archive form the qualification CHECKPOINT ONLY at the END of each COMPLETE
discovery pass, not after individual repairs. ONLY at the END of the ENTIRE discovery pass, if
any defect occurred, close it with NO clean credit (0/3), qualify the final repaired main SHA,
reconcile the full final packaged roster/interactions, and start a new clean attempt at file #1.
All 3/3 independent COMPLETE zero-defect clean passes must reread unchanged accepted package bytes,
freshly downloading the same accepted archive before each pass. No redundant gate rerun is needed
if the previously qualified SHA is unchanged. Partial, provisional and mixed-SHA passes never count.
After 3/3, reconcile and re-prove applicable canonical PP evidence in dependency order (S1 before S2),
then require green full-profile exact-SHA acceptance. Production publication uses only the
accepted versioned source tarball bytes without repacking, with checksum and release notes.

The **final production deliverable is source**, not a disk image: one reproducible versioned
source tarball plus checksum and release notes, containing the complete kernel/userspace source,
`build.sh`, `install.sh`, `uninstall.sh`, and the detailed step-by-step `INSTALL.md`
dependency/build/install/configuration/uninstall manual. QCOW2/RAW/IMG/ISO files, prebuilt
kernels/initrds and prebuilt `decnet_iv.ko` files are lab-only or intermediate artifacts and
are never the product.

1. Read `docs/PROJECT_STATE.md` completely. Its `Resume point` and `Next action` section describe the live protocol/repository state.
2. Read `scratch/RESUME.md` completely. It records exact acceptance lineage and the persistent architecture-foundation model.
3. Read `docs/ROADMAP.md` completely and confirm the next action follows the ordered dependency plan.
4. Read `docs/ARCHITECTURE.md`, `docs/DELIVERY.md`, `INSTALL.md`, `docs/FEATURES.md`, `docs/COMPONENTS.md`, `docs/TEST_LAB.md`, `docs/HECNET_LAB.md` and `docs/PRE_PRODUCTION_TEST.md` before changing architecture, delivery/install behavior, lab construction, distributed transport or acceptance tests.
5. Perform substantive work directly on `main`. Every substantive commit must refresh both `docs/PROJECT_STATE.md` and `scratch/RESUME.md` in the same commit. Acceptance applies only to the exact unchanged `main` commit that passes the documented exact-SHA gates.
6. The production deliverable is the exact reproducible source tarball defined by `docs/DELIVERY.md`, with checksum, release notes and the detailed `INSTALL.md` build/install manual; disk images and prebuilt kernel/module payloads are never release artifacts. Mutable workflow state belongs below ignored `scratch/runtime/`. Persistent VM input is limited to verified source-independent architecture foundations keyed by architecture plus foundation fingerprint; exact candidate images and writable node overlays remain disposable lab state.
7. Development uses four exact-SHA acceptance depths: targeted for one named expensive development gate, fast for ordinary increments, consolidated at related-work checkpoints, and full for phase/release promotion. Targeted/fast/consolidated evidence never substitutes for the complete full gate; scheduled weekly full acceptance re-proves the current main candidate. Full interoperability uses one scenario per job (14 jobs at present) so independent cases run in parallel.
8. Area-31/VAX interoperability is implemented in the repository-tracked `.github/workflows/area31-interop.yml` gate and is part of full acceptance. It consumes only runtime secrets, verifies the required secret names before Area-31 transport access, explains missing prerequisites without exposing values, and never substitutes remote success for local exact-SHA acceptance.
9. Read `docs/PP_EVIDENCE.md` before advancing pre-production work. It is the canonical proof index; required run-attempt-qualified artifacts/logs must have been checked at original closure with durable exact-SHA IDs/hashes and results. Once recorded, historical closure remains valid if owner Actions housekeeping deletes the raw runs/artifacts/caches; never substitute unverified, stale, failed, skipped or missing original evidence.
10. Owner constraints are release policy: PP-11 S3-S6 are skipped for this release; from `## Timing/scheduler tests` onward execute only practically possible tests, remote-host test programs are user-mode C/C++ only, and impossible requirements are recorded exactly as `Not tested in lab environment`; PP-13 is skipped for the first release.
11. PYRTR `31.3` is the disruptive-test boundary. Remote HECnet systems beyond it must not be rebooted, stopped, reconfigured or otherwise state-changed. MIM `1.13` is stricter: access it only read-only with valid DECnet methods, never for load/stress/fault testing, and only copy required resources away from it.
12. Local test infrastructure may install pinned `tuklusan/simh` and, when useful, build one or more local RSX-11M-PLUS V4.6 SIMH instances from resources copied read-only from MIM; every acquisition, checksum, build, configuration and DECnet setup step must be documented.
13. Owner scope boundary: DDCMP and IPv6 are explicitly out of scope. They are not claimed product features, are not release blockers, and do not generate PP/reference/device acceptance requirements. MULTINET acceptance is IPv4-only. Historical chronology may retain superseded DDCMP wording, but current contracts must not.

Repository files are authoritative. Do not reconstruct current state from chat history or stale workflow runs.

Phase 8 is complete on exact fully green candidate `9b73e61bbd0f95b82410276f7b5dc3db94e219ba`. Resume Phase 9 from the final `Next action` entries in `docs/PROJECT_STATE.md` and `scratch/RESUME.md`; repository state remains authoritative.
