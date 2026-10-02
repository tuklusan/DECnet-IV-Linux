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

1. Read `docs/PROJECT_STATE.md` completely. Its `Resume point` and `Next action` section describe the live protocol/repository state.
2. Read `scratch/RESUME.md` completely. It records exact acceptance lineage and the persistent architecture-foundation model.
3. Read `docs/ROADMAP.md` completely and confirm the next action follows the ordered dependency plan.
4. Read `docs/ARCHITECTURE.md`, `docs/TEST_LAB.md`, `docs/HECNET_LAB.md` and `docs/PRE_PRODUCTION_TEST.md` before changing architecture, image construction, distributed transport or acceptance tests.
5. Perform substantive work directly on `main`. Every substantive commit must refresh both `docs/PROJECT_STATE.md` and `scratch/RESUME.md` in the same commit. Acceptance applies only to the exact unchanged `main` commit that passes the documented exact-SHA gates.
6. Mutable workflow state belongs below ignored `scratch/runtime/`. Persistent VM input is limited to verified source-independent architecture foundations keyed by architecture plus foundation fingerprint; exact candidate images and writable node overlays remain disposable.
7. Development uses three exact-SHA acceptance depths: fast for each substantive increment, consolidated at related-work checkpoints, and full for phase/release promotion. Fast/consolidated evidence never substitutes for the complete full gate; scheduled nightly full acceptance re-proves the current main candidate. Full interoperability uses one scenario per job (14 jobs at present) so independent cases run in parallel.
8. Area-31/VAX integration is optional external interoperability. When its repository-tracked workflow is added, it must consume only runtime secrets, verify the required secret names are present before network activity, explain missing prerequisites without exposing values, and never substitute remote success for local exact-SHA acceptance.
9. Read `docs/PP_EVIDENCE.md` before advancing pre-production work. It is the canonical proof index; raw proof remains in run-attempt-qualified retained artifacts and logs.
10. Owner constraints are release policy: PP-11 S3-S6 are skipped for this release; from `## Timing/scheduler tests` onward execute only practically possible tests, remote-host test programs are user-mode C/C++ only, and impossible requirements are recorded exactly as `Not tested in lab environment`; PP-13 is skipped for the first release.
11. PYRTR `31.3` is the disruptive-test boundary. Remote HECnet systems beyond it must not be rebooted, stopped, reconfigured or otherwise state-changed. MIM `1.13` is stricter: access it only read-only with valid DECnet methods, never for load/stress/fault testing, and only copy required resources away from it.
12. Local test infrastructure may install pinned `tuklusan/simh` and, when useful, build one or more local RSX-11M-PLUS V4.6 SIMH instances from resources copied read-only from MIM; every acquisition, checksum, build, configuration and DECnet setup step must be documented.

Repository files are authoritative. Do not reconstruct current state from chat history or stale workflow runs.

Phase 8 is complete on exact fully green candidate `9b73e61bbd0f95b82410276f7b5dc3db94e219ba`. Resume Phase 9 from the final `Next action` entries in `docs/PROJECT_STATE.md` and `scratch/RESUME.md`; repository state remains authoritative.
