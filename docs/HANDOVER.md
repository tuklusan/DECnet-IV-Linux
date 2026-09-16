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

1. Read `docs/PROJECT_STATE.md` completely. Its `Resume point` and `Next action` describe the live repository state.
2. Read `docs/ROADMAP.md` completely and confirm the next action follows the ordered dependency plan.
3. Read `docs/ARCHITECTURE.md`, `docs/TEST_LAB.md` and `docs/PRE_PRODUCTION_TEST.md` before changing architecture, image construction or acceptance tests.
4. Perform substantive work directly on `main`. Every substantive commit must refresh `docs/PROJECT_STATE.md` in the same commit. Acceptance applies only to the exact unchanged `main` commit that passed the required SoP and gates.
5. After any change, restart the SoP sequence from the complete latest repository copy. Delivery requires three consecutive clean full passes.

Repository files are authoritative. Do not reconstruct current state from chat history or stale workflow runs.
