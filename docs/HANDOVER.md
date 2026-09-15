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
Phase 1 and the external reference baselines are promoted and green on `main`. Phase 2 remains unpromoted on `work/phase2-vm-lab`. Persistent session/attempt identity is implemented and the continuity gate is green. The first fresh x86 run verified the pinned image and exposed only a missing execute bit on the NoCloud seed builder before guest boot; that file mode is now fixed. The incomplete failed session `gha-34948701365` is safely non-resumable because its manifest/seeds were never created. The next run should create a fresh session and proceed into actual guest provisioning.

Next action:
Run the workflows on the executable-bit fix. Start a fresh x86 session rather than resuming `gha-34948701365`. Confirm DN70 and DN71 seeds and `session.env` are created, then repair the next VM-lab failure until both guests provision through NoCloud, reboot, load the AKMS-managed module, exchange native EtherType `0x6003` frames and report non-zero receive counters with retained serial logs and pcap. For later reruns of a valid known pair, reuse the same `DNIV_LAB_SESSION_ID` with `DNIV_LAB_RESUME=1` locally, or dispatch the VM workflow with the prior run ID and the original explicit session ID when one was used; never silently recreate a known session. Only after x86 is green add native aarch64 UEFI and mixed-architecture runs, then promote the exact green commit and begin Phase 3 hello/adjacency work. The documented Debian/RHEL-family portability matrix follows without replacing the Alpine reference gate; DECnet-over-IP work remains deferred.

Continuity rules:
- Every substantive commit must update `docs/PROJECT_STATE.md` in that same commit.
- Regenerate `docs/HANDOVER.md` with `python3 tools/render_handover.py`; CI must reject drift.
- Work on a working branch and promote only an exact commit whose required gates are green.
- Keep the fresh out-of-tree DECnet Phase IV kernel implementation; do not fall back to the removed legacy Linux DECnet stack.
- Keep Route20 and PyDECnet as independent conformance/interoperability references.
- Keep x86_64 and aarch64 as required targets and the configurable default lab range at 31.70-31.79.

Proceed directly from the Next action. Do not ask me to reconstruct prior chat history.
```
