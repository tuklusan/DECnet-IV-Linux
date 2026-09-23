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

# DECnet-IV-Linux Reference Hierarchy

This directory records the source material used to design and test DECnet-IV-Linux. It is deliberately small: keep authoritative specifications and independent implementations easy to find, but do not turn the repository into a museum dump of every DECnet manual ever scanned.

## Source-of-truth order

When references disagree, use this order for development decisions:

1. **Digital Network Architecture Phase IV functional specifications — normative.** Use them for wire formats, state machines, timers, routing rules, NSP, Session Control, NICE/network management, DAP, MOP and Ethernet behavior.
2. **`tuklusan/pydecnet` — strong whole-stack implementation cross-check.** Use it for independent behavior across routing, NSP, Session Control, NICE/NML, DAP/FAL, MOP and MULTINET, including useful edge cases.
3. **`tuklusan/Route20` — strong routing implementation cross-check.** Use it especially for Phase IV Ethernet initialization, Level 1/Level 2 routing, adjacency and forwarding behavior.
4. **`tuklusan/LinuxDECnet` — primary Linux ABI/userspace compatibility reference.** Use it for AF_DECnet/socket expectations, DECnet/Linux userspace, NML, DAP/FAL/RMS, CTERM and utilities. Do not use its unsupported historical routing code as the authority for Phase IV routing.
5. **`tuklusan/simh` plus genuine DEC operating systems — interoperability oracle.** Use simulated or real VMS/RSX/TOPS systems to establish observable peer behavior, particularly where a published specification is ambiguous or products contain compatibility quirks.

The short rule is:

**Digital DNA specifications define the protocol. PyDECnet and Route20 independently cross-check our implementation. LinuxDECnet defines the Linux-facing compatibility target. SIMH and real DEC peers prove interoperability.**

If implementations disagree with a Digital functional specification, the specification wins unless there is documented evidence that shipping DEC systems require a compatibility deviation. Record such deviations explicitly; do not quietly promote an implementation bug into a protocol rule.

If a real DEC peer behaves differently from an unambiguous specification, preserve both facts: implement the specification by default and add only the smallest compatibility behavior needed for proven interoperability.

## Project-specific use

For routing work, normally triangulate **Digital Routing V2.0 -> Route20 -> PyDECnet -> DEC peer**.

For NSP and Session Control, normally triangulate **Digital NSP/Session Control -> PyDECnet -> LinuxDECnet -> DEC peer**.

For Linux sockets and classic utilities, normally triangulate **Digital wire specification -> LinuxDECnet ABI/userspace behavior -> PyDECnet/DEC peer on the wire**.

For distributed transport, prove **VDE2 independently**, prove **PyDECnet MULTINET TCP independently**, then combine them only for controlled Area-31/HECnet routing tests.

See `PROTOCOL_SPECS.md`, `IMPLEMENTATIONS.md` and `LICENSING.md` for the retained subset and exact pins.
