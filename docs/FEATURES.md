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
- Native `AF_DECnet` / `SOCK_SEQPACKET` record ABI preserves classic `MSG_EOR` message framing across multiple writes, enforces the `DNBUFSIZE` aggregate record bound, and provides `SOCK_STREAM` compatibility with short-read preservation and `MSG_WAITALL` across NSP record boundaries.
- Delivered record-oriented userspace retries short positive `SOCK_SEQPACKET` sends until the complete `MSG_EOR` record is accepted; interrupted sends are retried and impossible zero-progress writes fail with a deterministic `EIO` instead of leaking stale `errno`.
- Multi-segment socket writes preserve an in-progress NSP record across short/partial sends, and once NSP data, interrupt or retained connection-control traffic is committed to retransmission state, an immediate Ethernet transmit result cannot contradict that accepted queue/state ownership.
- Classic `DNPROTO_NSP` socket controls for access data, connect/accept data, peer/local disconnect data, link information, immediate/deferred accept, explicit accept and explicit reject (`DSO_CONACCESS`, `DSO_CONDATA`, `DSO_DISDATA`, `DSO_LINKINFO`, `DSO_ACCEPTMODE`, `DSO_CONACCEPT`, `DSO_CONREJECT`).
- Versioned management UAPI for identity, counters, adjacencies, routes and NSP links.
- The `/dev/decnet_iv` management endpoint is published only after routing, NSP, Ethernet and socket initialization completes, and is withdrawn before subsystem teardown.

## Management

- `dnctl` local identity/state administration.
- `ncp` NCP-style local and remote front end.
- `dnnice` NICE client.
- `dnnml` NML object 19 server.

## Library and compatibility surface

- `libdnet` static/shared libraries, including native connection/receive/EOF helpers.
- `/etc/decnet.conf` compatible node database lookup, executor/device lookup, node iteration, object name/number lookup and named-node connection support, with strict bounded physical-line parsing that rejects embedded NULs and overlong records, drains the rejected physical line through newline/EOF, and cannot resynchronize an iterator inside malformed line data.
- `libdnet_daemon` static/shared helper library with deferred listener, accept/reject, accept-data and daemon-name helpers.
- `netdnet/dn.h` and `netdnet/dnetdb.h`.
- Project `linux/dn.h` and `linux/decnet_iv.h` UAPI headers.

## Applications

- `dnlogin` / `sethost` CTERM/Foundation remote terminal client with Session access-data support and interactive terminal read/write control.
- `dnping` MIRROR-based connectivity probe with bounded count, frame-size, interval and timeout controls plus packet/round-trip statistics.
- `dnmirror` MIRROR utility.
- `dnobject` named/numbered object client.
- `dntask` task/object client.
- `dnlynx` bounded DECnet-native HTTP/1.0 client; the 8192-byte header bound applies to the HTTP header itself, so a valid header remains accepted when the same NSP record also carries a larger response-body prefix.
- `dnhttpd` bounded DECnet-native static HTTP/1.0 server serving regular root-level files through the full 8192-byte body limit, with safe root-level GET handling that rejects symbolic-link, hard-link and non-regular leaf escapes without blocking on special files, plus explicit bad/not-found responses.

## DAP/FAL

- `dncopy`, `dntype`, `dndir`, `dndel`, `dnrename`, `dnsubmit`, `dnprint`.
- `dncopy` retrieval opens a named local destination only after the remote DAP file OPEN and data-stream CONNECT have succeeded, so an unreachable/missing remote source cannot truncate an existing local file.
- `dnfald` FAL object 17 service with DAP configuration plus the implemented file/directory/delete/rename/submit/print operations; `--root` pins the served directory and file data operations reject symbolic-link, hard-link and non-regular leaf escapes without blocking on special files. A failed CREATE, including a final stream flush/close error, removes the incomplete target instead of leaving failed transfer data behind. Directory enumeration reports `readdir()`/stream-close failures instead of falsely completing a partial listing.
- Optional Session access-data policy for user/password/account before DAP exchange.

## PHONE

- `phone` client with classic CONNECT/DIAL/DATA session flow.
- `dnphoned` object 29 service with local-user validation, data delivery and DIRECTORY response support.

## Mail

- `dnmail` MAIL-11 client including optional v3 Session capability negotiation and multiple-recipient delivery.
- `dnmaild` object 27 service with legacy/v3 negotiation, local spool delivery, sendmail-compatible execution and bounded direct SMTP delivery; the local `mailbox.log` spool is created owner-only (0600), opened inside `--root` without following symbolic links and rejects multiply linked/non-regular targets. Final spool flush/close failure invalidates the stream before common cleanup, so an already-closed `FILE` is never closed a second time. A sendmail pipe-close error is retained as delivery failure only after the spawned sendmail child has still been waited/reaped, preventing orphan/zombie leakage on that error path.
- Persistent `dnetd`, `dnfald`, `dnhttpd`, `dnmaild`, `dnphoned`, `dnmirror` and `dnobject` loops isolate malformed or aborted client sessions; explicit bounded/once modes still report session failures, and persistent `dnetd` reaps exited dispatch children asynchronously.
- Fixed-buffer DECnet sequenced-packet consumers reject overlong records instead of silently accepting truncated data; the shared receive helper uses `MSG_TRUNC` to recover the original record length and reports `EMSGSIZE` when it exceeds the caller buffer.

## Generic object dispatch

- `dnetd` configurable DECnet object-to-program dispatcher using the classic five-field `/etc/dnetd.conf` form by default.
- `dnetd` rejects overlong physical configuration lines instead of interpreting one physical line as multiple buffered fragments.
- Numbered/named listeners, explicit accept/reject policy, optional local-account drop and direct child execution with the DECnet socket on standard input/output; unsupported wildcard/authentication modes are rejected rather than silently weakened.

## MULTINET/VDE integration

- `dnmultinet` generates and launches a PyDECnet-based VDE Ethernet to MULTINET TCP router.
- Connect/listen mode, routing role, costs, priority, API socket and runtime peer environment are configurable.
- PyDECnet and VDE2 are optional external runtime dependencies for this integration.

## Interoperability coverage

The release is tested against pinned Route20 and PyDECnet, LinuxDECnet compatibility behavior, SIMH-hosted DEC operating systems where applicable, VDE2 distributed Ethernet, MULTINET TCP and controlled HECnet Area-31 peers. Those references are not embedded product components.

## Explicit scope exclusions

DDCMP and IPv6 transport support are outside the current project and release scope by owner decision. Neither is claimed as a delivered feature, neither blocks release, and neither creates PP/reference/device acceptance requirements. MULTINET project acceptance is IPv4-only.

## Scope boundary

A historical DECnet feature is not implicitly claimed merely because the project implements DECnet Phase IV. Features not represented by the native component inventory and canonical acceptance plan are outside the current release claim.
