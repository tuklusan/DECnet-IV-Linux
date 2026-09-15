# Handover

This file is the stable handover entry point for DECnet-IV-Linux.

The authoritative live continuity record is `docs/PROJECT_STATE.md`. The authoritative ordered execution plan is `docs/ROADMAP.md`. Read both completely from the current repository copy before changing code; do not reconstruct project state from chat history.

## Resume procedure

1. Read `docs/PROJECT_STATE.md` completely, including `Resume point` and `Next action`.
2. Read `docs/ROADMAP.md` and confirm the next action still follows the ordered plan.
3. Read `docs/REVIEWER.md` before preparing any substantive check-in.
4. Work on a feature branch, run every applicable gate, and promote only the exact green commit.
5. Any change after review resets the project SoP review sequence to Step 1.

If this file and `docs/PROJECT_STATE.md` ever disagree about live project state, fix the disagreement before continuing; `docs/PROJECT_STATE.md` carries the detailed current state.
