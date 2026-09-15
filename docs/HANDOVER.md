# Next Chat Handover

This file is generated from `docs/PROJECT_STATE.md` by `tools/render_handover.py`.
Do not edit it by hand.

## Copy/paste into the next chat

```text
Continue the DECnet-IV-Linux project: https://github.com/tuklusan/DECnet-IV-Linux

Use the repository as canonical project memory. First read `docs/PROJECT_STATE.md`,
`docs/ROADMAP.md`, and `docs/HANDOVER.md`, then inspect the active working branch
and its CI status before changing code.

Goal:
Build a minimal maintained Linux distribution with a fresh native DECnet Phase IV implementation delivered primarily as an out-of-tree kernel module, familiar DECnet user-mode tools, and reproducible x86_64/aarch64 VM images.

Resume point:
Phase 1 and the external reference baselines are promoted and green on `main`. Phase 2 remains unpromoted on `work/phase2-vm-lab` and is being kept as one clean substantive commit directly on top of `main`. The current rewrite includes the two-node VM lab, generated handover enforcement, force-push-safe continuity range selection, and corrected Alpine SHA-512 verification. The previous VM run did not reach guest boot because both architecture jobs stopped at the checksum-format mismatch.

Next action:
Run every workflow on the rewritten Phase 2 commit. Confirm the Project State Gate now validates from the main merge-base after a branch rewrite and that both pinned Alpine images verify. Then repair any next x86 VM-lab failure until DN70 and DN71 boot customized Alpine, load the module, exchange EtherType `0x6003` frames and report non-zero receive counters with a retained pcap. Add native aarch64 UEFI and mixed-architecture runs only after x86 is green; promote only after all gates pass, then begin Phase 3 hello and adjacency logic.

Continuity rules:
- Every substantive commit must update `docs/PROJECT_STATE.md` in that same commit.
- Regenerate `docs/HANDOVER.md` with `python3 tools/render_handover.py`; CI must reject drift.
- Work on a working branch and promote only an exact commit whose required gates are green.
- Keep the fresh out-of-tree DECnet Phase IV kernel implementation; do not fall back to the removed legacy Linux DECnet stack.
- Keep Route20 and PyDECnet as independent conformance/interoperability references.
- Keep x86_64 and aarch64 as required targets and the configurable default lab range at 31.70-31.79.

Proceed directly from the Next action. Do not ask me to reconstruct prior chat history.
```
