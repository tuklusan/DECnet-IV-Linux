<!-- ============================================================================ -->
<!-- Copyright (c) 2026 Supratim Sanyal of SANYALnet Labs. -->
<!-- Proprietary rights reserved except as expressly licensed herein. -->
<!-- -->
<!-- DECnet-IV-Linux -->
<!-- This file is governed by the SANYALnet Labs Non-Commercial License in the -->
<!-- root LICENSE file. Non-Commercial use is permitted; Commercial Use and use -->
<!-- for AI/ML model training are prohibited unless separately authorized. -->
<!-- -->
<!-- Attribution is required: "Based on original work by Supratim Sanyal of -->
<!-- SANYALnet Labs." See LICENSE for full terms, warranty disclaimer, termination, -->
<!-- patent, trademark, and governing-law provisions. -->
<!-- ============================================================================ -->

# Area-31 Distributed Lab

Area 31 is the project's Internet-connected HECnet lab area. External connectivity is optional test infrastructure, never a substitute for exact-SHA local acceptance.

## VDE2

VDE2 is the preferred Ethernet fabric for rootless local and distributed lab segments.

- Every runner/container owns its own user-mode `vde_switch`.
- QEMU, PyDECnet and the Route20 fork attach directly through libvdeplug.
- Separate hosts may join their VDE switches with `vde_plug` over SSH.
- The VDE2 proof is independent of MULTINET proof. A failure in either transport cannot be hidden by the other.
- VDE2 proof must cover real frame delivery, independent Route20/PyDECnet adjacency, restart, disconnect and malformed/oversized frame behavior before distributed scale tests depend on it.

The project forks carrying native VDE support are pinned in `tests/reference/refs.env`. SIMH already provides a VDE backend and remains a separate interoperability participant.

## MULTINET

MULTINET is the supported point-to-point Internet transport for the lab. The initial implementation boundary deliberately uses the proven PyDECnet MULTINET engine rather than inventing a second protocol interpretation.

Only TCP connect/listen modes are accepted for normal project use. MULTINET/UDP is excluded from the project transport claim because it lacks the reliability and restart properties required for dependable routing tests.

`userspace/dnmultinet/dnmultinet.py` launches a PyDECnet router with:

- one VDE Ethernet circuit facing local DECnet-IV-Linux VMs; and
- one MULTINET TCP circuit facing a local or remote peer.

This gives the native Linux stack an Internet path without adding a non-Ethernet media implementation to the kernel.

Example configuration preview:

```sh
python3 userspace/dnmultinet/dnmultinet.py \
  --node 31.80 --name MNET80 --type l2router \
  --vde vde:///tmp/dn31.ctl \
  --mode connect --peer-host peer.example.net --peer-port 700 \
  --dry-run
```

The actual Area-31 peer address, port and any access restrictions belong in runtime configuration or repository secrets, not source control.

## HECnet proof sequence

Use the following order:

1. prove VDE2 locally with `tests/lab/prove-vde2.sh`;
2. prove MULTINET independently with `tests/lab/prove-multinet.sh`;
3. run a local VDE DECnet-IV-Linux topology behind the MULTINET gateway;
4. establish one controlled Area-31 HECnet adjacency;
5. prove routing to/from explicitly selected remote nodes;
6. exercise NSP/MIRROR and later Session/NICE/application traffic;
7. add failure/reconnect, route withdrawal, peer restart and sustained-load cases;
8. only then use the remote area as part of 4/8/16-node scale and endurance testing.

No public HECnet route is advertised from a disposable CI job until its node identity and peer endpoint have been explicitly assigned for that run.
