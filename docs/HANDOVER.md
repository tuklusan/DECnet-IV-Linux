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
Phase 1 and all external/build/repository/continuity gates are green. Phase 2 remains unpromoted on `work/phase2-vm-lab`. Persistent session identity is implemented and the 4 GiB disk-growth path is proven by fresh session `gha-34950592707`; its package installation completed and exposed only AKMS selecting the stale running kernel instead of the newly installed kernel. The seed now targets the installed `linux-virt` kernel explicitly. Incomplete resumed guests also refresh their NoCloud provisioning payload without replacing their known QCOW2 disks or changing the stable session ID. Known session `gha-34948868114` remains retained from workflow run `34948868114` for the required recovery proof.

Next action:
Run the workflows on the explicit-target-kernel and incomplete-seed-refresh fix. First prove a fresh x86 session provisions DN70 and DN71, reboots into the installed kernel, loads the AKMS-managed module, exchanges native EtherType `0x6003` frames and reports non-zero receive counters with retained serial logs and pcap. Then explicitly resume known session `gha-34948868114` from prior workflow run `34948868114` and prove the interrupted-bootstrap repair reuses those exact disks, refreshes only the incomplete provisioning seed, completes AKMS for the installed kernel and reaches the same Ethernet acceptance result. Keep Route20, the full usable PyDECnet suite, both native build targets and both pinned Alpine image checks green. Only after fresh and resumed x86 paths are proven add native aarch64 UEFI and mixed-architecture runs, then promote the exact green commit and begin Phase 3 hello/adjacency work. DECnet-over-IP work remains deferred.

Continuity rules:
- Every substantive commit must update `docs/PROJECT_STATE.md` in that same commit.
- Regenerate `docs/HANDOVER.md` with `python3 tools/render_handover.py`; CI must reject drift.
- Work on a working branch and promote only an exact commit whose required gates are green.
- Keep the fresh out-of-tree DECnet Phase IV kernel implementation; do not fall back to the removed legacy Linux DECnet stack.
- Keep Route20 and PyDECnet as independent conformance/interoperability references.
- Keep x86_64 and aarch64 as required targets and the configurable default lab range at 31.70-31.79.

Proceed directly from the Next action. Do not ask me to reconstruct prior chat history.
```
