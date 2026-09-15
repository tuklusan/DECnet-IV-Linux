# VM test lab

The acceptance lab uses separate VMs so each node has its own kernel, module state,
timers and interface state. The default address allocation comes from
`test-addresses.env` and starts at area 31, nodes 70 through 79.

## Phase 2 smoke test

The first lab boots DN70 (31.70) and DN71 (31.71) on one isolated Linux bridge.
The official Alpine tiny image is not modified with libguestfs. Instead, each node
receives a NoCloud `CIDATA` seed and provisions itself on first boot.

QEMU sets the SMBIOS type-1 product serial to `ds=nocloud` for every guest so Alpine
Tiny Cloud enables its NoCloud provider without depending on the seed block device
being visible during the earliest label probe. The attached ISO or FAT `cidata`
volume remains the source of `meta-data` and `user-data`.

The launcher sparse-grows each tiny QCOW2 guest disk to 4 GiB by default before
first boot. Tiny Cloud then expands the root filesystem during initial bootstrap.
Set `DNIV_LAB_DISK_BYTES` to an integer number of bytes to use a different size;
values below 1 GiB are rejected. `DNIV_LAB_TIMEOUT_SECONDS` controls the guest
completion window; the x86 launcher defaults to 1200 seconds and the ARM/mixed CI
jobs use 2400 seconds to allow for software emulation. Attempt metadata records the
selected timeout and an explicit failure result/reason, and the launcher fails
promptly if either guest exits without its completion marker.

Each guest:

1. uses a separate disposable management NIC only to reach Alpine package mirrors;
2. installs the module source under `/usr/src` and registers it with AKMS;
3. reboots into the installed `linux-virt` kernel;
4. proves the loaded `decnet_iv.ko` came from the AKMS-managed module path;
5. configures its node identity with `dnctl`;
6. transmits raw DECnet Routing Layer EtherType `0x6003` frames to its peer;
7. waits for non-zero receive counters, prints final counters to the serial console,
   and powers off.

The host captures only the isolated DECnet bridge to `lan.pcap`. The gate succeeds
only when both guests report received routing frames and the capture contains native
DECnet EtherType traffic. The management NIC is never part of the DECnet data path.

This proves VM/image/module-lifecycle/Ethernet plumbing only; it does not yet claim
Phase IV hello, adjacency, routing or NSP behavior.

## Phase 2 architecture matrix

The Phase 2 promotion gate runs the same native-Ethernet acceptance in four CPU
pairings:

- x86_64 DN70 with x86_64 DN71;
- aarch64 DN70 with aarch64 DN71 on an aarch64 runner;
- x86_64 DN70 with aarch64 DN71;
- aarch64 DN70 with x86_64 DN71.

The aarch64 guests boot the pinned Alpine UEFI tiny image through QEMU AArch64 UEFI.
Mixed pairs share one Linux bridge exactly like the x86-only case; one architecture
may use software emulation when the runner cannot accelerate both guest types. Guest
startup therefore keeps sending bounded probes until the slower peer is online rather
than assuming both architectures provision at the same speed.

`run-two-node-arch.sh` records both guest architectures and base-image checksums in
its session evidence. ARM and mixed jobs retain manifests, serial logs and pcaps but
not their disposable multi-gigabyte guest disks.

## Resumable lab sessions

Every x86 recovery run has a stable session ID and a separate attempt ID. Stateful
files live under `tests/lab/artifacts/sessions/<session-id>/`:

- `session.env` records the session ID, provisioned source revision, base-image
  checksum, virtual disk size, MACs and stateful disk/seed names;
- `dn70.qcow2` and `dn71.qcow2` are the resumable guest disks;
- the NoCloud seeds carry the same session ID in their instance IDs;
- `attempts/<attempt-id>/` contains that attempt's serial logs, pcap, PID files and
  `attempt.env` result metadata;
- `latest-attempt` identifies the newest attempt.

A fresh run creates the session. To continue preserved disks locally, set the same
`DNIV_LAB_SESSION_ID`, choose a new `DNIV_LAB_ATTEMPT_ID`, set
`DNIV_LAB_RESUME=1`, and run the launcher again. Resume never silently recreates a
missing disk, seed or manifest.

When a preserved disk is smaller than the requested virtual size, the launcher grows
it without replacing it. If our `/var/lib/decnet-lab/provisioned` marker is absent,
the launcher clears Tiny Cloud's completion marker so an interrupted first bootstrap
can retry on the same known disk. A successfully provisioned disk keeps its Tiny
Cloud completion state.

Attempt metadata records both `SESSION_SOURCE_REV` and `RUNNER_SOURCE_REV` (and the
corresponding base-image checksums), so a preserved image cannot be mistaken for an
image freshly provisioned from the launcher revision that happens to resume it.

CI uploads the entire x86 session directory, including the QCOW2 disks, for recovery.
It also uploads a separate compact x86 evidence artifact containing the session and
attempt manifests, serial logs and pcap so a failure can be inspected without the
stateful disks. A manual workflow run can restore a prior session by supplying its
workflow run ID. If no explicit session ID is supplied, the restored session defaults
to `gha-<prior-run-id>`.

For an exact-commit recovery check without manual workflow inputs, a validation branch
named `resume-<prior-run-id>` selects the same restore path and inferred
`gha-<prior-run-id>` session. ARM/mixed jobs are skipped on these recovery-only
branches; the x86 job must restore the retained artifact and pass on the exact commit
being validated.

## Portability lab

`DISTRO_MATRIX.md` defines the later smallest-image Alpine, Debian and RHEL-family
matrix. Alpine uses AKMS; Debian/RHEL-family guests use DKMS. Every lifecycle test
must include a real kernel package update and automatic module rebuild.
