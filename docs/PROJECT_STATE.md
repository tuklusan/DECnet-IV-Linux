# Project State

This is the continuity record for DECnet-IV-Linux. A fresh session should read `docs/PROJECT_INSTRUCTIONS.md` and this file first, then `docs/HANDOVER.md` and `docs/ROADMAP.md`, and execute `Next action` without reconstructing project state from chat history.

## Goal

Build a complete native DECnet Phase IV stack for maintained Linux, delivered primarily as an out-of-tree kernel module plus the useful DECnet/Linux userspace environment, with reproducible x86_64/aarch64 VM images and independent interoperability.

Kernel scope grows through native Ethernet, endnode/Level 1/Level 2 routing, NSP, sockets/UAPI, Session Control support, NICE/NML hooks/state, and DDCMP. Userspace scope includes `ncp`, `sethost`/`dnlogin`, DAP/FAL/RMS tools, PHONE, mail, task/object access, daemons, libraries, administration tools, and deliberately classified historical DECnet/Linux capabilities.

## Project contract

`docs/PROJECT_INSTRUCTIONS.md` is the compact normative project contract. Repository files are authoritative over chat history.

The mandatory SoP delivery rule is:

1. read the complete latest disk copy byte-for-byte, line-by-line, with no truncation; find and fix defects/gaps;
2. any fix resets the pass to Step 1 on the new latest disk copy;
3. delivery requires three consecutive clean complete Step-1 passes;
4. any later change resets Step 1.

Automated tests, diffs, excerpts, or prior reviews do not replace this rule.

## Non-negotiable architecture

- Reference distribution: Alpine Linux 3.24 initially using `linux-virt`.
- Kernel delivery: fresh out-of-tree module; avoid a permanent kernel fork and do not revive the removed legacy Linux DECnet kernel stack.
- Module lifecycle: automatic rebuild after supported kernel package changes is mandatory. Alpine uses AKMS; DKMS metadata is maintained for Debian and RHEL-family systems.
- Kernel scope as the project matures: native Ethernet, Phase IV endnode/L1/L2 routing, NSP, DDCMP, sockets/UAPI, timers, forwarding, concurrency/lifetime handling, and management hooks.
- Core routing, NSP, and DDCMP state machines remain in kernel space.
- Userspace target: the useful DECnet/Linux experience, including network management, terminal access, DAP/FAL/RMS, PHONE, mail, task/object services, daemons, libraries, diagnostics, and administration tools.
- Historical DECnet/Linux capabilities must be implemented, replaced by a documented modern equivalent, explicitly obsolete with justification, or deferred with a tracked dependency.
- Required CPU targets: x86_64 and aarch64.
- Primary VM artifact: QCOW2, with RAW and conversion formats at release time.

## Reference and licensing policy

Preferred project references are:

- `tuklusan/Route20`;
- `tuklusan/pydecnet`;
- `tuklusan/LinuxDECnet`;
- `tuklusan/simh`.

Upstream repositories are comparison sources only. Exact reference repositories and revisions consumed by CI are stored in `tests/reference/refs.env`.

Current automated baselines use the preferred Route20 and PyDECnet forks at pinned SHAs. The pinned Route20 SHA and both PyDECnet SHAs have been verified to exist in the preferred forks.

Every reference is independently licensed. Before copying or adapting source, verify the source license and compatibility with the destination and preserve required notices/provenance. If licensing is unclear or incompatible, use the reference only for externally specified/observable protocol behavior and implement independently.

`tuklusan/LinuxDECnet` is the primary compatibility inventory for historical userspace behavior and `dnprogs`. `tuklusan/simh` is the preferred simulator fork for later real DEC operating-system peers. Pin exact SHAs before either becomes an automated gate.

## External conformance

The implementation is exercised independently against the pinned Route20 and PyDECnet forks. Later application-level validation adds SIMH-hosted real DEC operating systems; self-to-self success alone is never sufficient for final interoperability claims.

Every useful and internally consistent reference test at the pinned revisions must pass unmodified. The current PyDECnet reference is pinned for documentation, vectors, and live interoperability. Its current tree has a pre-existing self-test contradiction in `Macaddr("1.24")`: the code takes the hexadecimal path before the DECnet `area.node` path while the test still requires `area.node`. The hard full-suite pin is therefore the immediately preceding internally consistent revision. No test is skipped or rewritten; move the hard pin forward when the contradiction is fixed.

## Execution order

`docs/ROADMAP.md` is the canonical ordered task list:

0. continuity, repository/reference/licensing/SoP discipline;
1. buildable UAPI/module/control utility on x86_64 and aarch64;
2. reproducible Alpine image and two-VM native Ethernet lab;
3. Ethernet initialization and adjacency;
4. endnode, Level 1 and Level 2 routing;
5. NSP and DECnet sockets;
6. Session Control and NICE/NML;
7. complete useful DECnet/Linux userspace as dependencies become ready;
8. DDCMP;
9. mixed Ethernet/DDCMP routing and applications;
10. scale, portability, real DEC peers, physical mixed-CPU testing, and release images.

A later phase never removes an earlier acceptance gate.

## Test addressing

- Single source: `tests/lab/test-addresses.env`.
- Default area: 31.
- Default nodes: 70 through 79.
- Default names: DN70 through DN79.
- Larger tests may extend the node range; inter-area tests introduce another configurable area deliberately.

## Test lab rules

- Primary acceptance nodes are separate VMs, not containers or namespaces sharing one kernel.
- Linux bridges provide raw native Ethernet LANs.
- Disposable management NICs may be used only for provisioning/package access; DECnet acceptance traffic stays on isolated native DECnet media.
- Native DECnet is stressed first. DECnet-over-IP tunneling is deferred until native Ethernet, routing, transport, session, and application layers are mature.
- Scale deliberately from 2 to 4, 8, and 16 independent VMs with real routed topologies, not only single-LAN node counts.
- Required CPU cases include x86_64/x86_64, aarch64/aarch64, and both mixed directions.
- Fault and stress work includes deterministic loss, duplication, delay/reordering where meaningful, link/circuit failure, restart, convergence, connection churn, long-duration traffic, application concurrency, and kernel lifetime/resource failures.
- Failure artifacts include topology/addressing, source/kernel/module/reference revisions, serial/kernel/application logs, packet captures, protocol counters/state, session/attempt identity, and fault seed where applicable.
- Later portability uses the smallest official maintained images from Alpine, Debian, and RHEL-family distributions and proves real kernel upgrades rebuild the module automatically.
- Physical lab target: at least two x86_64 and two aarch64 nodes, managed switch, independent management path, and mirrored capture.
- Required mixed-media path eventually includes `Ethernet -> router -> DDCMP -> router -> Ethernet`.
- Independent peers include pinned Route20/PyDECnet forks and later SIMH-hosted real DEC systems.

## Continuity and promotion gates

- Every substantive commit updates this file and `docs/HANDOVER.md` in the same commit.
- `docs/HANDOVER.md` is generated deterministically from this file by `tools/render_handover.py`.
- The local pre-commit hook regenerates/stages the handover before running the continuity gate.
- `tools/project_state_gate.py` checks every substantive commit in the pushed range, validates non-empty Resume point/Next action sections, and verifies handover/state agreement.
- Work is prepared on a feature/working branch; only the exact commit whose required gates are green is promoted.
- The SoP rule applies to each updated deliverable before it is published/promoted. Any fix or later change resets its clean-pass count.
- During long interactive work, surface current handover text before the conversation becomes difficult to continue; the repository copy remains authoritative.

## Phase 1 status

Phase 1 is included in `main` and is green on both required CPU architectures. It contains UAPI version 1, `decnet_iv.ko`, default 31.70/DN70 identity, `/dev/decnet_iv`, DEC DNA Routing EtherType receive registration/counters, `dnctl`, centralized test addressing, unit address tests, and native x86_64/aarch64 build gates.

The bootstrap does not yet claim adjacency, routing, NSP, Session Control, NICE/NML application behavior, or DDCMP functionality.

## External baseline status

The external-reference baseline is green at its pinned revisions. Route20 builds at `ROUTE20_REF`. The full usable unmodified PyDECnet suite runs at `PYDECNET_TEST_REF`, the last internally consistent revision immediately before the current `Macaddr("1.24")` contradiction; `PYDECNET_REF` remains the current documentation/vector/live-interoperability pin.

Reference CI consumes the preferred `tuklusan/Route20` and `tuklusan/pydecnet` forks through repository URLs in `tests/reference/refs.env`; the upstream URLs are retained there only for explicit comparison provenance.

## Phase 2 status

The Phase 2 implementation base before promotion is `work/phase2-vm-lab` at `58f4353c88834f7c71d4508fa0b55b8ad62f2e82`. Alpine 3.24.1 official tiny QCOW2 bases are pinned for x86_64 BIOS and aarch64 UEFI. The x86 lab uses NoCloud `CIDATA` first-boot provisioning instead of offline image mutation. DN70 and DN71 each have an isolated DECnet NIC plus a disposable QEMU user-network management NIC used only to install packages. The seed carries the source tree, installs the module under `/usr/src`, registers/builds it with AKMS, installs the small user tools, reboots into the installed kernel, and requires the test to load the AKMS-managed module before exchanging EtherType `0x6003` frames. DKMS metadata and a native-build smoke test cover the parallel lifecycle path for Debian/RHEL-family systems.

A resumable x86 lab session has stable `DNIV_LAB_SESSION_ID` separate from each `DNIV_LAB_ATTEMPT_ID`. Session disks, matching NoCloud seeds, and `session.env` live under `tests/lab/artifacts/sessions/<session-id>/`; attempts keep their own serial logs, pcap, and result manifest. Resume requires the known manifest/disks/seeds and does not silently replace disk identity.

Known retained session `gha-34948868114` comes from workflow run `34948868114`. Its original 128 MiB root filled while installing `linux-virt-dev` and build dependencies. The launcher sparse-grows new and resumed QCOW2 disks to 4 GiB and retries interrupted Tiny Cloud bootstrap only when the project's provisioned marker is absent.

Fresh session `gha-34950592707` from workflow run `34950592707` proved the 4 GiB path: Tiny Cloud discovered the ISO seed, package installation completed at 472.8 MiB, and the run then exposed AKMS selecting the stale running kernel while newer headers were available. Commit `c103b708c082b136aaaf200162fbf54c5bb8969d`, tested by workflow run `34956282545`, then proved the remaining package-lifecycle defect: plain `apk add linux-virt linux-virt-dev` left the already-installed `linux-virt` at `6.18.35-0-virt` while installing `linux-virt-dev` `6.18.52-r0`, so `/usr/share/kernel/virt/kernel.release` correctly remained `6.18.35-0-virt` and AKMS could not obtain matching old headers.

Candidate `eb518891197be467a1c8ca7a4c05d20e4e1b8570` fixed that kernel/header split and was tested by workflow run `34958450892`. All non-VM gates were green, including x86_64/aarch64 native builds, repository policy, continuity, Route20, and the full usable pinned PyDECnet suite. The candidate was rejected because all four VM jobs failed, and that failure reset SoP.

The `eb518891197be467a1c8ca7a4c05d20e4e1b8570` failure evidence exposed two provisioning defects rather than protocol failures. Its x86 guest in the mixed x86-to-aarch64 evidence reached userspace tool compilation after upgrading the kernel/header pair and building the AKMS module, but `dnctl` required Alpine's userspace `linux-headers`. Its aarch64 guests booted normally but did not execute the provisioning payload when an ISO seed was presented as a generic virtio block device. Candidate `8b08c2873e0b0914e5a1e33005d5ab229125e133` therefore added transient `linux-headers` and FAT `cidata` block seeds for ARM/mixed guests while retaining ISO/CD-ROM seeds for the resumable x86 path.

Workflow run `34963593635` rejected `8b08c2873e0b0914e5a1e33005d5ab229125e133` as well: repository policy, continuity, both native build/DKMS jobs, Route20, and the full pinned PyDECnet suite were green, but fresh x86_64/x86_64, aarch64/aarch64, and both mixed CPU VM jobs all failed. This failure resets SoP again; neither rejected candidate may be promoted.

The aarch64 evidence from run `34963593635` is specific: UEFI and the pinned Alpine root disk booted normally, the 4 MiB FAT `cidata` seed appeared as a virtio block device, and the guest reached the Alpine login prompt without any `DNIV-PROVISION` output or native DECnet traffic. Alpine Tiny Cloud enables itself during early boot when its datasource is requested through DMI or a discoverable seed label; relying only on the late-appearing virtio label is therefore insufficient for this boot path. The repaired launcher sets QEMU SMBIOS type-1 product serial to `ds=nocloud` on every x86_64 and aarch64 guest, while the attached `cidata` volume remains the actual NoCloud metadata payload.

The x86 job in run `34963593635` used QEMU TCG and exceeded its former 600-second guest-completion window. The earlier `34950592707` evidence proves the same pinned x86 image can boot, discover the ISO seed, and execute provisioning through package installation, so the repaired x86 launcher uses a bounded configurable timeout with a 1200-second default rather than classifying a slow TCG run as a protocol failure. Both VM launchers record the selected completion timeout and an explicit failure result/reason in attempt evidence, and fail promptly if a guest exits before reporting completion. CI also retains a compact x86 evidence artifact containing manifests, serial logs, and pcap in addition to the stateful resumable session artifact, so future failures remain directly diagnosable without the multi-hundred-megabyte QCOW2 payload.

Candidate `e4b2f23c43d48fe6b4d35ddf6dfcc2ed07a5ff0a` was tested by workflow run `34984520980`. Repository policy, continuity, x86_64/aarch64 native build/DKMS gates, and the pinned Route20/PyDECnet baselines were green, but the fresh x86_64/x86_64 VM gate failed. Compact evidence shows both x86 guests discovered the seed, upgraded to `linux-virt`/`linux-virt-dev` 6.18.52, built and installed `decnet_iv.ko` successfully with AKMS, then provisioning aborted while linking `dnctl` because the tiny Alpine image did not contain `/usr/local/sbin`. No native DECnet acceptance traffic was emitted. This rejects the candidate and resets SoP. The repair explicitly creates `/usr/local/sbin` and `/etc/local.d` before installing userspace tools and the local startup service.

Candidate `1f38fa5b636fe2bdfb6d65117322d62c38306361` was tested by VM workflow run `34988919295`. All four VM jobs failed, rejecting the candidate and resetting SoP. Compact x86 evidence proves the x86_64/x86_64 failure is a host-side completion race: DN71 emitted its valid `DNIV-LAB-DONE` marker and shut down normally while DN70 was still finishing, and the launcher treated that already-complete DN71 exit as an early guest failure. The repaired launchers use fixed-string completion markers and require a QEMU process to remain live only while that specific node has not yet reported completion.

The ARM and mixed evidence from run `34988919295` exposes a distinct seed-device defect. Both AArch64 guests booted the pinned UEFI root to `localhost login:` with the 4 MiB seed visible as `vda` and the 4 GiB root as `vdb`, but Tiny Cloud never ran and no native DECnet traffic was captured. In both mixed directions the x86 guest serial log was empty while the FAT configuration disk was presented as a generic virtio block device. The repair drops that ARM/mixed FAT-block path: mixed x86 uses the same ISO/CD-ROM attachment already proven by the x86-only lab, and AArch64 presents the ISO `CIDATA` seed as a SCSI CD-ROM behind a virtio-scsi controller. SMBIOS `ds=nocloud` remains as the early activation hint.

For an incomplete resumed guest, the launcher refreshes only that guest's NoCloud provisioning payload while preserving stable session ID, instance ID, and QCOW2 disk; successfully provisioned guests retain their seed. Manifests/attempt metadata track each seed's source revision. Earlier session `gha-34948701365` remains intentionally non-resumable because its failure preceded seed/manifest retention.

The Phase 2 promotion candidate extends the VM gate from x86_64/x86_64 to aarch64/aarch64 plus both mixed x86_64/aarch64 directions. AArch64 guests use the pinned UEFI tiny image and AArch64 UEFI firmware. Mixed guests share one native Ethernet bridge; one guest may use QEMU software emulation where the runner cannot accelerate both architectures. Guest completion no longer assumes equal provisioning speed: each node sends bounded native probes until it receives peer traffic, then returns confirmation probes before shutdown.

The x86 workflow retains manual `workflow_dispatch` recovery and also recognizes a validation branch named `resume-<prior-run-id>`. On that branch it infers the retained `gha-<prior-run-id>` session, restores the prior workflow artifact, and exercises the same recovery path on the exact commit under test. ARM/mixed jobs are deliberately skipped on recovery-only branches because their normal-branch results already belong to the same commit.

## Documentation reconciliation status

The reconciliation adds `docs/PROJECT_INSTRUCTIONS.md` as the exact compact project contract; aligns README, architecture, roadmap, test-lab, reference-baseline, state, and generated handover documentation; expands Phase 7 to the complete useful DECnet/Linux userspace scope; records preferred forks, upstream-comparison-only policy, SHA pinning, and license boundaries; makes reference CI consume preferred repository URLs from `tests/reference/refs.env`; and carries the SoP rule into project state and generated handover.

Component-specific Alpine, kernel-bootstrap, packaging, and distro-matrix documentation was reviewed and remains accurate, so it is not changed merely for churn. The VM-lab README is updated only where Phase 2 architecture/recovery behavior now changes.

## Promotion state

This repository state is designed to become the Phase 2/documentation promotion state. On a feature branch it is only a candidate and must not be promoted until the exact same commit has all required normal-branch gates green and also passes retained-session recovery on `resume-34948868114`. Required normal-branch VM evidence is fresh x86_64/x86_64, aarch64/aarch64, x86_64/aarch64, and aarch64/x86_64 native-Ethernet acceptance, in addition to repository policy, continuity, native build, reference-baseline, and pinned-image verification embedded in those jobs.

`main` independently advanced to `c869da23effea3014daf9a3c5de8ca1db2ccd9bd` while the Phase 2 working history remained based on its earlier merge base. Do not force-update either history. After the Phase 2 repair is green, reconcile the current `main` history into a new descendant candidate; that later change resets SoP and requires the exact reconciled commit to repeat all promotion gates before `main` may move.

If this exact state is read from `main`, its presence there records that those promotion conditions and history reconciliation were satisfied before the fast-forward. No untested merge or follow-up edit may substitute a different commit.

## Resume point

Candidate `1f38fa5b636fe2bdfb6d65117322d62c38306361` is rejected by VM workflow run `34988919295`: x86_64/x86_64 exposed a host-side completion race after DN71 had already emitted its valid completion marker, while aarch64/aarch64 and both mixed directions timed out because the ARM Tiny Cloud payload did not run; mixed x86 also produced empty serial logs with the FAT seed presented as a generic virtio block disk. The current repair makes completion tracking per-node and fixed-string, returns ARM/mixed NoCloud delivery to ISO media, uses the known-working x86 CD-ROM attachment, and uses a virtio-scsi SCSI CD-ROM on AArch64. The implementation still stops at Routing Layer EtherType plumbing: no adjacency, routing, NSP, Session Control, NICE/NML application behavior, or DDCMP is claimed yet. The retained recovery source remains workflow run `34948868114`, session `gha-34948868114`.

When read on a feature branch, freeze and review this completion/ISO-media repair under SoP, then finish the exact-commit gates described above. When read from `main`, Phase 2 and the documentation reconciliation have been promoted together and the next development work is Phase 3 Ethernet hello/adjacency on a new feature branch.

## Next action

Freeze the completion/ISO-media repair, run three consecutive clean full SoP passes over every updated deliverable, and publish those exact bytes in one substantive commit with this state and generated handover. Require every normal-branch gate on that exact commit to pass, including fresh x86_64/x86_64, aarch64/aarch64, and both mixed CPU VM cases. Then validate the same commit on recovery branch `resume-34948868114` and require its restored x86 session to pass without replacing the retained QCOW2 disks. After that evidence is green, reconcile current `main` without force into a new descendant candidate, restart SoP, and repeat the exact-commit promotion gates because the reconciled bytes are a new deliverable. Only the final reconciled green commit may fast-forward `main`. After promotion, begin Phase 3 on a new feature branch: implement DECnet Ethernet address handling, endnode/router hello parsing and generation, adjacency state/expiry, and independent Route20/PyDECnet interoperability vectors while retaining all Phase 0-2 gates. DECnet-over-IP remains deferred.
