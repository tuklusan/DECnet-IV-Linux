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
Candidate `1f38fa5b636fe2bdfb6d65117322d62c38306361` is rejected by VM workflow run `34988919295`: x86_64/x86_64 exposed a host-side completion race after DN71 had already emitted its valid completion marker, while aarch64/aarch64 and both mixed directions timed out because the ARM Tiny Cloud payload did not run; mixed x86 also produced empty serial logs with the FAT seed presented as a generic virtio block disk. The current repair makes completion tracking per-node and fixed-string, returns ARM/mixed NoCloud delivery to ISO media, uses the known-working x86 CD-ROM attachment, and uses a virtio-scsi SCSI CD-ROM on AArch64. The implementation still stops at Routing Layer EtherType plumbing: no adjacency, routing, NSP, Session Control, NICE/NML application behavior, or DDCMP is claimed yet. The retained recovery source remains workflow run `34948868114`, session `gha-34948868114`.

When read on a feature branch, freeze and review this completion/ISO-media repair under SoP, then finish the exact-commit gates described above. When read from `main`, Phase 2 and the documentation reconciliation have been promoted together and the next development work is Phase 3 Ethernet hello/adjacency on a new feature branch.

Next action:
Freeze the completion/ISO-media repair, run three consecutive clean full SoP passes over every updated deliverable, and publish those exact bytes in one substantive commit with this state and generated handover. Require every normal-branch gate on that exact commit to pass, including fresh x86_64/x86_64, aarch64/aarch64, and both mixed CPU VM cases. Then validate the same commit on recovery branch `resume-34948868114` and require its restored x86 session to pass without replacing the retained QCOW2 disks. After that evidence is green, reconcile current `main` without force into a new descendant candidate, restart SoP, and repeat the exact-commit promotion gates because the reconciled bytes are a new deliverable. Only the final reconciled green commit may fast-forward `main`. After promotion, begin Phase 3 on a new feature branch: implement DECnet Ethernet address handling, endnode/router hello parsing and generation, adjacency state/expiry, and independent Route20/PyDECnet interoperability vectors while retaining all Phase 0-2 gates. DECnet-over-IP remains deferred.

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
