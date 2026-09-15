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
Phase 1 and all external/build/repository/continuity gates are green. Phase 2 remains unpromoted on `work/phase2-vm-lab`. Persistent session identity is implemented and now includes safe sparse disk growth, interrupted-bootstrap recovery and honest session-versus-runner provenance. Known session `gha-34948868114` is retained from workflow run `34948868114`; it booted both guests and failed only because the original 128 MiB roots ran out of space during package installation. The current launcher grows such disks to 4 GiB and can retry that same session without recreating DN70 or DN71.

Next action:
Run the workflows on the disk-growth/recovery commit. First prove a fresh x86 session can provision DN70 and DN71 on the 4 GiB sparse disks, reboot, load the AKMS-managed module, exchange native EtherType `0x6003` frames and report non-zero receive counters with retained serial logs and pcap. Then explicitly resume known session `gha-34948868114` from prior workflow run `34948868114` and prove the interrupted-bootstrap repair recovers those exact disks rather than replacing them. Keep Route20, the full usable PyDECnet suite, both native build targets and both pinned Alpine image checks green. Only after fresh and resumed x86 paths are proven add native aarch64 UEFI and mixed-architecture runs, then promote the exact green commit and begin Phase 3 hello/adjacency work. DECnet-over-IP work remains deferred.

Continuity rules:
- Every substantive commit must update `docs/PROJECT_STATE.md` in that same commit.
- Regenerate `docs/HANDOVER.md` with `python3 tools/render_handover.py`; CI must reject drift.
- Work on a working branch and promote only an exact commit whose required gates are green.
- Keep the fresh out-of-tree DECnet Phase IV kernel implementation; do not fall back to the removed legacy Linux DECnet stack.
- Keep Route20 and PyDECnet as independent conformance/interoperability references.
- Keep x86_64 and aarch64 as required targets and the configurable default lab range at 31.70-31.79.

Proceed directly from the Next action. Do not ask me to reconstruct prior chat history.
```
