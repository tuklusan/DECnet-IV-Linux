# VM test lab

The acceptance lab uses separate VMs so each node has its own kernel, module state,
timers and interface state. The default address allocation comes from
`test-addresses.env` and starts at area 31, nodes 70 through 79.

## Phase 2 smoke test

The first lab boots DN70 (31.70) and DN71 (31.71) on one isolated Linux bridge.
The official Alpine tiny image is not modified with libguestfs. Instead, each node
receives a NoCloud `CIDATA` seed and provisions itself on first boot.

Each guest:

1. uses a separate disposable management NIC only to reach Alpine package mirrors;
2. installs the module source under `/usr/src` and registers it with AKMS;
3. reboots into the installed `linux-virt` kernel;
4. proves the loaded `decnet_iv.ko` came from the AKMS-managed module path;
5. configures its node identity with `dnctl`;
6. transmits raw DECnet Routing Layer EtherType `0x6003` frames to its peer;
7. prints receive counters to the serial console and powers off.

The host captures only the isolated DECnet bridge to `lan.pcap`. The gate succeeds
only when both guests report received routing frames and the capture contains native
DECnet EtherType traffic. The management NIC is never part of the DECnet data path.

This proves VM/image/module-lifecycle/Ethernet plumbing only; it does not yet claim
Phase IV hello, adjacency, routing or NSP behavior.

## Resumable lab sessions

Every run has a stable session ID and a separate attempt ID. Stateful files live under
`tests/lab/artifacts/sessions/<session-id>/`:

- `session.env` records the session ID, source revision, base-image checksum, MACs and
  stateful disk/seed names;
- `dn70.qcow2` and `dn71.qcow2` are the resumable guest disks;
- the NoCloud seeds carry the same session ID in their instance IDs;
- `attempts/<attempt-id>/` contains that attempt's serial logs, pcap, PID files and
  `attempt.env` result metadata;
- `latest-attempt` identifies the newest attempt.

A fresh run creates the session. To continue preserved disks locally, set the same
`DNIV_LAB_SESSION_ID`, choose a new `DNIV_LAB_ATTEMPT_ID`, set
`DNIV_LAB_RESUME=1`, and run the launcher again.

CI uploads the entire session directory, including the qcow2 disks. A manual workflow
run can restore a prior session by supplying its workflow run ID. If no explicit
session ID is supplied, the restored session defaults to `gha-<prior-run-id>`.

## Portability lab

`DISTRO_MATRIX.md` defines the later smallest-image Alpine, Debian and RHEL-family
matrix. Alpine uses AKMS; Debian/RHEL-family guests use DKMS. Every lifecycle test
must include a real kernel package update and automatic module rebuild.
