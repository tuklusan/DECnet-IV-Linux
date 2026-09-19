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

1. Read `docs/PROJECT_STATE.md` completely. Its `Resume point` and `Next action` describe the live protocol/repository state.
2. Read `scratch/RESUME.md` completely. It records exact acceptance lineage and the persistent architecture-foundation model.
3. Read `docs/ROADMAP.md` completely and confirm the next action follows the ordered dependency plan.
4. Read `docs/ARCHITECTURE.md`, `docs/TEST_LAB.md`, `docs/HECNET_LAB.md` and `docs/PRE_PRODUCTION_TEST.md` before changing architecture, image construction, distributed transport or acceptance tests.
5. Perform substantive work directly on `main`. Every substantive commit must refresh both `docs/PROJECT_STATE.md` and `scratch/RESUME.md` in the same commit. Acceptance applies only to the exact unchanged `main` commit that passes the documented exact-SHA gates.
6. Mutable workflow state belongs below ignored `scratch/runtime/`. Persistent VM input is limited to verified source-independent architecture foundations keyed by architecture plus foundation fingerprint; exact candidate images and writable node overlays remain disposable.
7. Candidate promotion is determined only by the documented exact-SHA mechanical, build, VM, reference, protocol and interoperability gates.

Repository files are authoritative. Do not reconstruct current state from chat history or stale workflow runs.
