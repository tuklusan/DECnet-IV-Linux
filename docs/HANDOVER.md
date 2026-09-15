# Next Chat Handover

This file is generated from `docs/PROJECT_STATE.md` by `tools/render_handover.py`.
Do not edit it by hand.

## Copy/paste into the next chat

```text
Continue the DECnet-IV-Linux project: https://github.com/tuklusan/DECnet-IV-Linux

Use repository state as canonical project memory. First read `docs/PROJECT_INSTRUCTIONS.md`,
`docs/PROJECT_STATE.md`, `docs/HANDOVER.md`, and `docs/ROADMAP.md`, then inspect the active
working branch and its CI status before changing code.

Goal:
Build a complete native DECnet Phase IV stack for maintained Linux, delivered primarily as an out-of-tree kernel module plus the useful DECnet/Linux userspace environment, with reproducible x86_64/aarch64 VM images and independent interoperability.

Kernel scope grows through native Ethernet, endnode/Level 1/Level 2 routing, NSP, sockets/UAPI, Session Control support, NICE/NML hooks/state, and DDCMP. Userspace scope includes `ncp`, `sethost`/`dnlogin`, DAP/FAL/RMS tools, PHONE, mail, task/object access, daemons, libraries, administration tools, and deliberately classified historical DECnet/Linux capabilities.

Resume point:
Phase 1 remains green on both required architectures. Phase 2 implementation remains unpromoted on `work/phase2-vm-lab` at `58f4353c88834f7c71d4508fa0b55b8ad62f2e82`. The current documentation/reference-policy reconciliation is prepared on `work/project-doc-reconcile` from that exact head. It does not change Phase 2 protocol or VM implementation. Preferred Route20/PyDECnet pins have been verified to exist in the user forks; reference CI is being redirected to those forks through `tests/reference/refs.env`.

The prior Phase 2 technical next step remains: prove the explicit-installed-kernel AKMS fix on a fresh x86 session, then resume known session `gha-34948868114` and prove repair using the exact retained disks.

Next action:
Run all required gates on the exact `work/project-doc-reconcile` commit, including repository policy, continuity/handover, native x86_64/aarch64 build gates, reference baselines from the preferred forks, and applicable pinned-image/VM gates. If and only if that exact commit is green, fast-forward the Phase 2 working branch to that exact commit without additional edits. Then continue the existing Phase 2 acceptance: first prove a fresh x86 DN70/DN71 session provisions, reboots into the installed kernel, loads the AKMS-managed module, exchanges native EtherType `0x6003` frames and reports non-zero receive counters with retained logs/pcap; then resume `gha-34948868114` from run `34948868114` and prove exact-disk recovery. After fresh and resumed x86 paths pass, add native aarch64 UEFI and mixed-architecture runs, promote only the exact green Phase 2 commit, and begin Phase 3 hello/adjacency work. DECnet-over-IP remains deferred.

Continuity rules:
- Every substantive commit must update `docs/PROJECT_STATE.md` and generated `docs/HANDOVER.md` together.
- Work on a feature/working branch and promote only the exact commit whose required gates are green.
- Prefer `tuklusan/Route20`, `tuklusan/pydecnet`, `tuklusan/LinuxDECnet`, and `tuklusan/simh`; pin exact SHAs when used by a gate, and use upstreams only for comparison.
- Respect source licenses and implement independently when reuse is unclear or incompatible.
- Keep the fresh out-of-tree kernel design; do not fall back to the removed legacy Linux DECnet stack.
- Keep x86_64/aarch64, independent VMs, routed/mixed-media networks, independent/real DEC peers, fault injection, and stress as acceptance requirements.
- Apply the SoP rule to every updated deliverable: read the complete latest disk copy untruncated, fix defects/gaps, reset after any fix, require three consecutive clean full passes, and reset after any later change.

Proceed directly from the Next action. Do not reconstruct project state from prior chat history.
```
