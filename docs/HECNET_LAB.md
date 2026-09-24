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

## Current proof status

- Local/rootless VDE2 is independently green at enhanced workflow run `35959075714`: three libvdeplug endpoints completed 512 content-checked stress frames across a full switch restart, an endpoint restart, a nonexistent-endpoint negative, and Route20/PyDECnet adjacency recovery.
- MULTINET TCP is independently green at enhanced workflow run `35960257018`: the pinned PyDECnet MULTINET module suite passed, an unopened-port negative stayed down, two simultaneous connector circuits came up, one connector survived five kill/restart cycles while the other stayed alive, and both recovered after listener restart.
- Cross-runner VDE2 has not yet been proven. The documented SSH switch-join design is a plan until two separate hosted machines exchange real frames and DECnet traffic through it.
- Area-31 and VAX integration have not yet been executed.

## VDE2

VDE2 is the preferred Ethernet fabric for rootless local and distributed lab segments.

- Every runner/container owns its own user-mode `vde_switch`.
- QEMU, PyDECnet and the Route20 fork attach directly through libvdeplug.
- Separate hosts may join their VDE switches with `vde_plug` over SSH.
- The cross-runner proof must demonstrate real frame delivery in both directions, DECnet adjacency, switch/client restart and disconnect/reconnect across the host boundary before distributed scale depends on it.
- VDE2 evidence remains independent of MULTINET evidence. A failure in either transport cannot be hidden by the other.

The project forks carrying native VDE support are pinned in `tests/reference/refs.env`. SIMH already provides a VDE backend and remains a separate interoperability participant.

## MULTINET

MULTINET is the supported point-to-point Internet transport for the lab. The implementation boundary deliberately uses the proven PyDECnet MULTINET engine rather than inventing a second protocol interpretation.

Only TCP connect/listen modes are accepted for normal project use. MULTINET/UDP is excluded from the project transport claim because it lacks the reliability and restart properties required for dependable routing tests.

`userspace/dnmultinet/dnmultinet.py` launches a PyDECnet router with one VDE Ethernet circuit facing local DECnet-IV-Linux VMs and one MULTINET TCP circuit facing a local or remote peer. This gives the native Linux stack an Internet path without adding a non-Ethernet media implementation to the kernel.

## Runtime secret contract

The Area-31 workflow will use these GitHub Actions secrets:

- `MULTINET_REMOTE_HOST`
- `MULTINET_REMOTE_PORT`
- `VAX_ADDR`
- `VAX_USERNAME`
- `VAX_PASSWORD`

The workflow and its scripts must check for all required secret names before opening the remote MULTINET connection or attempting VAX access. If one or more are absent, they must stop cleanly and state which secret names are required. They must never print, persist in artifacts, place on process command lines where avoidable, or commit the secret values.

The MULTINET remote endpoint is one Area-31 area router. The node identified by `VAX_ADDR` is another Area-31 area router reachable after the MULTINET adjacency and routing path are established. VAX credentials are for controlled test deployment/login only.

## Repository-tracked Area-31 tests

Remote tests belong in the repository rather than in ad-hoc runner commands. The intended progression is:

1. start a local VDE DECnet-IV-Linux topology and the MULTINET gateway in TCP client mode;
2. establish the controlled adjacency to the remote Area-31 router and record routing state/counters;
3. prove reachability to the VAX router at `VAX_ADDR`;
4. query useful node, circuit, route, adjacency, executor and counter information through NICE/NML as those facilities become available;
5. exercise NSP/MIRROR and Session/object access in both directions;
6. use `VAX_USERNAME`/`VAX_PASSWORD` only when a VAX-side helper actually must be installed or invoked;
7. accumulate reusable Linux/VAX pairs under `tests/lab`, including login, DAP/FAL file operations, PHONE, mail, task/object access and management/counter checks as each userspace feature lands;
8. add failure/reconnect, route withdrawal, gateway/VAX/router restart and sustained-load cases;
9. only then incorporate Area-31 into 4/8/16-node scale and endurance work.

VAX-side scripts/programs should live in a dedicated `tests/lab` subdirectory and be paired with the Linux driver that invokes and validates them. Application experiments such as a small VAX DECnet service plus a `dnlynx` client are welcome after the underlying Session/object and standard DECnet/Linux userspace features are stable; they are supplemental tests, not a shortcut around those layers.

No public HECnet route is advertised from a disposable CI job until its node identity and peer endpoint have been explicitly assigned for that run. External connectivity remains optional interoperability evidence and never substitutes for local exact-SHA acceptance.
