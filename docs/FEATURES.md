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
- Session Control v1 Connect Initiate input validates reserved menu/version bits and consumes the entire declared access/user-data field payload; malformed prefixes with trailing bytes are rejected rather than dispatched to an application listener.
- Named Session Control end-user descriptors also require the specified zero object-type octet; conflicting numeric type bytes in named source/destination selectors are rejected.
- Session Control v1 source end-user descriptors accept only defined formats 0, 1 and 2; reserved format codes, including format 4, are rejected before application dispatch.
- `dnping` rejects a MIRROR reply longer than the exact transmitted request, even when the truncated reply prefix matches; local sequenced-socket positive/negative regression enforces this.
- Native `AF_DECnet` / `SOCK_SEQPACKET` record ABI preserves classic `MSG_EOR` message framing across multiple writes, enforces the `DNBUFSIZE` aggregate record bound, and provides `SOCK_STREAM` compatibility with short-read preservation and `MSG_WAITALL` across NSP record boundaries.
- Native sequenced sockets report an already-observed ordinary peer disconnect as EOF even with `MSG_DONTWAIT`; nonblocking mode suppresses waiting but does not replace terminal EOF with `EAGAIN`. Retransmit-exhaustion reason 39 remains the distinct `EHOSTUNREACH` error path.
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
- `dnhttpd` bounded DECnet-native static HTTP/1.0 server serving regular root-level files through the full 8192-byte body limit, with safe root-level GET handling that rejects symbolic-link, hard-link and non-regular leaf escapes without blocking on special files, plus explicit bad/not-found responses. HTTP request records containing embedded NUL bytes are rejected as bad requests instead of being silently accepted by a prefix-only parser.

## DAP/FAL

- `dncopy`, `dntype`, `dndir`, `dndel`, `dnrename`, `dnsubmit`, `dnprint`.
- All `dncopy` DAP clients configure 30-second per-send and per-receive socket idle timeouts so a silent connected peer does not cause an unbounded wait.
- `dncopy` retrieval stages named local output only after remote DAP OPEN/CONNECT inside a private mode-0700 temporary directory, then atomically publishes it after the complete DAP transfer and local flush/sync/close. Failed transfers preserve existing files; concurrent creation of a previously absent destination fails safely instead of clobbering a different writer's new file; symlink/special-file destinations are rejected.
- `dncopy` record-mode uploads reject embedded NUL and overlong physical text records rather than silently discarding bytes; `-m block` preserves binary payloads. CRLF/empty records and a full-length final line without a newline are handled explicitly.
- `dncopy` CR-delimited DAP stream downloads preserve CRLF normalization across DATA-message boundaries, including intervening empty records, instead of inserting a duplicate newline at a split CR/LF boundary.
- `dnfald` FAL object 17 service with DAP configuration plus the implemented file/directory/delete/rename/submit/print operations; `--root` pins the served directory and file data operations reject symbolic-link, hard-link and non-regular leaf escapes without blocking on special files. CREATE is exclusive: an existing target is never truncated or overwritten. Uploads stage in an unnamed `O_TMPFILE` inode and use `linkat(AT_EMPTY_PATH)` to publish a complete stream only after successful flush, sync and close. A failed or aborted pre-publication CREATE leaves no partial name; a concurrent replacement file is never unlinked. A served filesystem must support these Linux operations plus `user.*` extended attributes; unsupported filesystems fail closed rather than falling back to race-prone named partial files. Directory enumeration reports `readdir()`/stream-close failures instead of falsely completing a partial listing.
- DAP record-mode FAL CREATE/GET preserves VAR and VFC DATA-message boundaries, including empty records, using versioned little-endian length-framed regular-file storage identified by `user.decnet.record-framing=1`. Incoming corrupt/truncated framed data and oversized records fail closed; absent-marker plain Linux files retain byte-stream behavior except when they claim VAR/VFC via an RFM xattr, where GET fails closed rather than inventing logical record boundaries. Invalid local RFM/RAT xattrs are rejected before advertising attributes. The DAP ATTRIBUTES parser decodes EX-6 attribute menus through BKS (the first eight available fields) and rejects unsupported higher-numbered menu fields rather than silently misaligning RFM.
- Optional Session access-data policy for user/password/account before DAP exchange.

## PHONE

- `phone` client with classic CONNECT/DIAL/DATA session flow.
- `dnphoned` object 29 service with local-user validation, data delivery and DIRECTORY response support. Full 1800-byte `phone` client text messages fit the server's 2048-byte NSP sequenced-record receive bound; an isolated socketpair selftest verifies the maximum-length PHONE DATA handshake and delivery.

## Mail

- An empty `dnmail` message body is serialized as the MAIL-11 end-of-message marker immediately after the subject (without an invalid zero-length native NSP record); `dnmaild` selftests cover empty-body completion and unchanged mailbox framing.
- `dnmail` MAIL-11 client including optional v3 Session capability negotiation and multiple-recipient delivery. The client rejects an explicitly empty `-s` subject before opening a network connection; zero-byte native NSP records are not emitted, so empty subjects cannot be sent safely.
- `dnmaild` object 27 service with legacy/v3 negotiation, local spool delivery, sendmail-compatible execution and bounded direct SMTP delivery; the local `mailbox.log` spool is created owner-only (0600), opened inside `--root` without following symbolic links and rejects multiply linked/non-regular targets. Final spool flush/close failure invalidates the stream before common cleanup, so an already-closed `FILE` is never closed a second time. A sendmail pipe-close error is retained as delivery failure only after the spawned sendmail child has still been waited/reaped, preventing orphan/zombie leakage on that error path.
- Persistent `dnetd`, `dnfald`, `dnhttpd`, `dnmaild`, `dnphoned`, `dnmirror` and `dnobject` loops isolate malformed or aborted client sessions; explicit bounded/once modes still report session failures, and persistent `dnetd` reaps exited dispatch children asynchronously.
- Fixed-buffer DECnet sequenced-packet consumers reject overlong records instead of silently accepting truncated data; the shared receive helper uses `MSG_TRUNC` to recover the original record length and reports `EMSGSIZE` when it exceeds the caller buffer.

## Generic object dispatch

- `dnetd` configurable DECnet object-to-program dispatcher using the classic five-field `/etc/dnetd.conf` form by default.
- `dnetd` rejects overlong physical configuration lines instead of interpreting one physical line as multiple buffered fragments. It also rejects embedded NUL bytes, requires complete valid option fields (`N`, `N,N`, `N,A`, `N,Y` or `N,R`, case-insensitive), and accepts a valid final physical line without a trailing newline.
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

- DAP `dncopy` attribute decoder checks all first-eight negotiated ATTR fields and their declared lengths; malformed optional fields and unexpected trailing data fail closed.

- `dnphoned` rejects unexpected transport EOF even after PHONE DATA; a properly framed PHONE GOODBYE completes the call, including valid calls with no DATA records. Socketpair regressions cover explicit GOODBYE and both premature EOF cases.

- DAP/FAL GET of ordinary fixed or stream data also works on filesystems without user extended-attribute support; a missing or unsupported private record-framing marker still rejects ambiguous VAR/VFC record downloads rather than fabricating record boundaries.

- Native `SOCK_STREAM` receives consume valid zero-length NSP DATA records without reporting false end-of-stream. Ordinary peer disconnection remains the only normal EOF condition; a nonblocking stream read after a zero-length record reports EAGAIN while the connection remains open.
