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

QCOCAL and IMPVAX are SIMH-emulated VAX systems running OpenVMS. Treat both as available SIMH-hosted real-DEC operating-system peers for future PP stages that require SIMH/OpenVMS machines, especially PP-12, while preserving the existing exact-SHA, secret-safety and evidence rules.

MIM `1.13` is reachable through PYRTR `31.3`, but it has a stricter canonical boundary than ordinary remote peers: access MIM only read-only with valid DECnet methods. Never install or execute test software there, alter files/configuration, or use it for load, stress, endurance, negative/fault-tolerance or disruptive testing. Required SIMH/RSX-11M-PLUS V4.6 resources may be copied away from MIM read-only and then installed/configured only on project-controlled local systems; retain acquisition hashes and the complete local setup procedure.

## Current proof status

Phase 8 is complete on exact candidate `9b73e61bbd0f95b82410276f7b5dc3db94e219ba`. Its full acceptance parent is Repository Policy run `36258507655`.

- Cross-runner VDE2 is green at run `36258564105`, including three marked frames, hard transport loss, adjacency expiry/recovery, bridge reconnect and client-switch restart on the unchanged candidate.
- Local/rootless VDE2 is green at run `36258635481`; enhanced run `35959075714` remains the detailed restart/stress baseline.
- MULTINET TCP is green at run `36258643588`; enhanced run `35960257018` remains the detailed negative/restart/stress baseline.
- Area-31 interoperability is green on x86_64 and arm64 at run `36258654316`. Phase 9/production acceptance must re-prove the applicable external path rather than inherit Phase 8 evidence.

## VDE2

VDE2 is the preferred Ethernet fabric for rootless local and distributed lab segments.

- Every runner/container owns its own user-mode `vde_switch`.
- QEMU, PyDECnet and the Route20 fork attach directly through libvdeplug.
- Separate hosts may join their VDE switches with `vde_plug` over SSH.
- `.github/workflows/vde2-cross-runner.yml` is the repository-tracked two-host gate. It uses a pre-existing SSH bastion only as rendezvous; hosted runners are never assumed to accept inbound Internet connections directly.
- The cross-runner proof must demonstrate real frame delivery in both directions, DECnet adjacency, switch/client restart and disconnect/reconnect across the host boundary before distributed scale depends on it.
- VDE2 evidence remains independent of MULTINET evidence. A failure in either transport cannot be hidden by the other.

The project forks carrying native VDE support are pinned in `tests/reference/refs.env`. SIMH already provides a VDE backend and remains a separate interoperability participant.

### Cross-runner SSH rendezvous contract

The cross-runner VDE2 workflow consumes `VDE_SSH_HOST`, `VDE_SSH_PORT`, `VDE_SSH_USER`, `VDE_SSH_KEY` and `VDE_SSH_KNOWN_HOSTS` only at runtime. Its unprivileged reverse-forward port is derived automatically from the exact candidate SHA. The bastion must already exist and permit TCP reverse forwarding; the project does not create or assume a public relay. Both runners validate prerequisites before checkout/network activity, write key/configuration material only below runner-temporary storage with restrictive permissions, and never retain it as evidence. The server's ephemeral inner SSH account is restricted to the VDE plug plus readiness/completion marker commands.

## MULTINET

MULTINET is the supported point-to-point Internet transport for the lab. The implementation boundary deliberately uses the proven PyDECnet MULTINET engine rather than inventing a second protocol interpretation.

Only TCP connect/listen modes are accepted for normal project use. MULTINET/UDP is excluded from the project transport claim because it lacks the reliability and restart properties required for dependable routing tests.

`userspace/dnmultinet/dnmultinet.py` launches a PyDECnet router with one VDE Ethernet circuit facing local DECnet-IV-Linux VMs and one MULTINET TCP circuit facing a local or remote peer. Its Area-31 mode reads the remote host/port from runtime environment variables, keeps the generated configuration in a memory-backed file descriptor, refuses secret-backed dry-run output, and can expose a local API socket for bounded remote probes. This gives the native Linux stack an Internet path without adding a non-Ethernet media implementation to the kernel.

## Runtime secret contract

The Area-31 workflow uses these GitHub Actions secrets:

- `MULTINET_REMOTE_HOST`
- `MULTINET_REMOTE_PORT`
- `VAX_ADDR`
- `VAX_USERNAME`
- `VAX_PASSWORD`

The workflow and its scripts must check for all required secret names before opening the remote MULTINET connection or attempting VAX access. If one or more are absent, they must stop cleanly and state which secret names are required. They must never print, persist in artifacts, or commit the secret values. The Area-31 native path stores the VAX user/password only in private files on the disposable read-only control image, then supplies them to `dnlogin`/`dncopy` through `DNACCESS_USER` and `DNACCESS_PASSWORD`; the secret values never appear in QEMU or application command-line arguments.

The MULTINET remote endpoint is one Area-31 area router. The node identified by `VAX_ADDR` is another Area-31 area router reachable after the MULTINET adjacency and routing path are established. VAX credentials are for controlled test deployment/login only.

## Repository-tracked Area-31 tests

Remote tests belong in the repository rather than in ad-hoc runner commands. Full acceptance dispatches `.github/workflows/area31-interop.yml` automatically. The proof now also turns PYRTR's structured known-node view into a per-run capability corpus: every currently reachable Area-31 identity in that corpus is probed from the native Linux candidate with a bounded NICE executor-summary request and, when NICE succeeds, a bounded MIRROR-object probe. Unsupported or absent objects are recorded as capabilities rather than treated as candidate failures. The required VAX proof remains strict and now exercises MIRROR record sizes 1, 127, 128, 255, 256, 511 and 512 bytes before re-reading NICE counters. The workflow keeps remote endpoints and credentials in Actions secrets, establishes the MULTINET adjacency to PYRTR at 31.3, asks PYRTR through NML for known nodes, and selects disposable Area-31 identities not present in that view before the native proof. `tests/lab/prove-area31.sh` rechecks the contract, starts the rootless VDE/MULTINET gateway and uses `tests/lab/area31-nice.py` to require VAX executor summary/status/counter replies without printing secret values. The intended progression is:

1. start a local VDE DECnet-IV-Linux topology and the MULTINET gateway in TCP client mode;
2. establish the controlled adjacency to the remote Area-31 router and record routing state/counters;
3. prove reachability to the VAX router at `VAX_ADDR`;
4. query the delivered node, circuit, route, adjacency, executor and counter information through NICE/NML;
5. exercise NSP/MIRROR and Session/object access in both directions;
6. use `VAX_USERNAME`/`VAX_PASSWORD` only when a VAX-side helper actually must be installed or invoked;
7. retain reusable Linux/VAX pairs under `tests/lab` for the delivered claimed login, DAP/FAL file operations, PHONE, mail, task/object access and management/counter paths wherever the remote-peer safety policy permits;
8. run failure/reconnect, route withdrawal, restart, sustained-load and endurance cases only on project-controlled local/SIMH systems; remote HECnet peers beyond PYRTR remain non-disruptive observation/traffic peers, and MIM remains strictly read-only;
9. incorporate only project-controlled local/SIMH systems into 4/8/16-node scale and endurance work; remote Area-31 systems provide non-disruptive interoperability evidence only.

VAX-side scripts/programs should live in a dedicated `tests/lab` subdirectory and be paired with the Linux driver that invokes and validates them. Application experiments such as a small VAX DECnet service plus a `dnlynx` client are welcome after the underlying Session/object and standard DECnet/Linux userspace features are stable; they are supplemental tests, not a shortcut around those layers.

No public HECnet route is advertised from a disposable CI job outside Area 31. Disposable identities are selected only from Area 31 and checked against PYRTR's NML known-node view before the final proof identity is used. External connectivity remains optional interoperability evidence and never substitutes for local exact-SHA acceptance.


## Remote peer safety boundary

PYRTR (31.3) is the hard operational boundary for disruptive testing. Any machine reached on the far side of PYRTR via the MULTINET/HECnet uplink is read/traffic-only for project testing: do not power-cycle, shut down, reboot, pause/resume, hard-stop, reconfigure its operating state, or otherwise cause a remote state transition. From `## Timing/scheduler tests` onward, remote-host active probes are limited to user-mode C/C++ programs when the remote host permits that activity; impossible requirements are recorded as `Not tested in lab environment`. MIM `1.13` is stricter and permits read-only valid-DECnet access only, never remote program installation/execution or stress/fault activity. PP-12 disruptive restart/power tests must use only project-controlled local systems, disposable lab VMs, or named SIMH/OpenVMS peers such as QCOCAL and IMPVAX only when those instances are actually under project control and are not being reached as protected remote systems beyond PYRTR.
