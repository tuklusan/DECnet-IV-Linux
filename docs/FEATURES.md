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

# Delivered Features

This catalogue describes the production source release. Lab-only helpers and independent reference implementations are identified separately.

## Native kernel networking

- DECnet Phase IV Ethernet framing and logical DECnet MAC/address handling.
- Runtime node identity.
- Endnode, Level 1 router and Level 2 router roles.
- Router/endnode hello generation and parsing.
- Adjacency formation, expiry and recovery.
- Designated-router behavior where applicable.
- Level 1/2 routing databases, metrics, next-hop selection, aging and forwarding.
- Multi-LAN and multi-area forwarding with visit/hop protection.
- NSP connection establishment and teardown.
- NSP segmentation/reassembly, sequencing, acknowledgements, retransmission and timers.
- NSP data flow control, interrupt/out-of-band flow and resource limits.
- Session Control connect/accept/reject behavior and object dispatch.
- Native `AF_DECnet` / `SOCK_SEQPACKET` record ABI plus `SOCK_STREAM` compatibility with short-read preservation and `MSG_WAITALL` across NSP record boundaries.
- Classic `DNPROTO_NSP` socket controls for access data, connect/accept data, peer/local disconnect data, link information, immediate/deferred accept, explicit accept and explicit reject (`DSO_CONACCESS`, `DSO_CONDATA`, `DSO_DISDATA`, `DSO_LINKINFO`, `DSO_ACCEPTMODE`, `DSO_CONACCEPT`, `DSO_CONREJECT`).
- Versioned management UAPI for identity, counters, adjacencies, routes and NSP links.

## Management

- `dnctl` local identity/state administration.
- `ncp` NCP-style local and remote front end.
- `dnnice` NICE client.
- `dnnml` NML object 19 server.

## Library and compatibility surface

- `libdnet` static/shared libraries, including native connection/receive/EOF helpers.
- `/etc/decnet.conf` compatible node database lookup, executor/device lookup, node iteration, object name/number lookup and named-node connection support.
- `libdnet_daemon` static/shared helper library with deferred listener, accept/reject, accept-data and daemon-name helpers.
- `netdnet/dn.h` and `netdnet/dnetdb.h`.
- Project `linux/dn.h` and `linux/decnet_iv.h` UAPI headers.

## Applications

- `dnlogin` / `sethost` CTERM/Foundation remote terminal client with Session access-data support and interactive terminal read/write control.
- `dnping` MIRROR-based connectivity probe with bounded count, frame-size, interval and timeout controls plus packet/round-trip statistics.
- `dnmirror` MIRROR utility.
- `dnobject` named/numbered object client.
- `dntask` task/object client.
- `dnlynx` bounded DECnet-native HTTP/1.0 client.
- `dnhttpd` bounded DECnet-native static HTTP/1.0 server with safe root-level GET handling and explicit bad/not-found responses.

## DAP/FAL

- `dncopy`, `dntype`, `dndir`, `dndel`, `dnrename`, `dnsubmit`, `dnprint`.
- `dnfald` FAL object 17 service with DAP configuration plus the implemented file/directory/delete/rename/submit/print operations.
- Optional Session access-data policy for user/password/account before DAP exchange.

## PHONE

- `phone` client with classic CONNECT/DIAL/DATA session flow.
- `dnphoned` object 29 service with local-user validation, data delivery and DIRECTORY response support.

## Mail

- `dnmail` MAIL-11 client including optional v3 Session capability negotiation and multiple-recipient delivery.
- `dnmaild` object 27 service with legacy/v3 negotiation, local spool delivery, sendmail-compatible execution and bounded direct SMTP delivery.

## Generic object dispatch

- `dnetd` configurable DECnet object-to-program dispatcher using the classic five-field `/etc/dnetd.conf` form by default.
- Numbered/named listeners, explicit accept/reject policy, optional local-account drop and direct child execution with the DECnet socket on standard input/output; unsupported wildcard/authentication modes are rejected rather than silently weakened.

## MULTINET/VDE integration

- `dnmultinet` generates and launches a PyDECnet-based VDE Ethernet to MULTINET TCP router.
- Connect/listen mode, routing role, costs, priority, API socket and runtime peer environment are configurable.
- PyDECnet and VDE2 are optional external runtime dependencies for this integration.

## Interoperability coverage

The release is tested against pinned Route20 and PyDECnet, LinuxDECnet compatibility behavior, SIMH-hosted DEC operating systems where applicable, VDE2 distributed Ethernet, MULTINET TCP and controlled HECnet Area-31 peers. Those references are not embedded product components.

## Pending project-goal feature

DDCMP remains part of the standing DECnet-IV-Linux project goal, but no native DDCMP implementation is present in the current tracked tree. It is therefore not claimed as delivered by this pre-production source archive and remains blocking for any final release that claims the complete project goal.

## Scope boundary

A historical DECnet feature is not implicitly claimed merely because the project implements DECnet Phase IV. Features not represented by the native component inventory and canonical acceptance plan are outside the current release claim.
