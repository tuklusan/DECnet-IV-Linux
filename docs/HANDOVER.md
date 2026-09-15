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
Phase 1 and the external reference baselines are promoted and green on `main`. Phase 2 remains unpromoted on `work/phase2-vm-lab`. The current rewrite replaces offline image mutation with NoCloud provisioning, adds AKMS/DKMS automatic module-lifecycle metadata, keeps DECnet traffic on an isolated raw Ethernet NIC, and adds resumable VM lab sessions with persistent DN70/DN71 disk identity plus separate per-attempt evidence. The latest session-documentation change initially failed the continuity gate because this canonical state and its generated handover were not updated in the same commit; that drift is now repaired. The rewritten x86 lab still needs a clean end-to-end rerun.

Next action:
Run every workflow on the current Phase 2 commit and keep the full usable upstream/reference baselines green. For an already-created DN70/DN71 pair, reuse the same `DNIV_LAB_SESSION_ID` with `DNIV_LAB_RESUME=1` locally, or dispatch the VM workflow with the prior run ID and the original explicit session ID when one was used; do not recreate known disks unless the session is intentionally discarded. Repair any x86 VM-lab failure until DN70 and DN71 provision through NoCloud, reboot, load the AKMS-managed module, exchange native EtherType `0x6003` frames and report non-zero receive counters with retained serial logs and pcap. Only after x86 is green add native aarch64 UEFI and mixed-architecture runs, then promote the exact green commit and begin Phase 3 hello/adjacency work with progressively heavier native DECnet stress. The documented Debian/RHEL-family portability matrix follows without replacing the Alpine reference gate; DECnet-over-IP work remains deferred.

Continuity rules:
- Every substantive commit must update `docs/PROJECT_STATE.md` in that same commit.
- Regenerate `docs/HANDOVER.md` with `python3 tools/render_handover.py`; CI must reject drift.
- Work on a working branch and promote only an exact commit whose required gates are green.
- Keep the fresh out-of-tree DECnet Phase IV kernel implementation; do not fall back to the removed legacy Linux DECnet stack.
- Keep Route20 and PyDECnet as independent conformance/interoperability references.
- Keep x86_64 and aarch64 as required targets and the configurable default lab range at 31.70-31.79.

Proceed directly from the Next action. Do not ask me to reconstruct prior chat history.
```
