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

# Distilled Digital DNA Phase IV Specification Set

This is the minimum protocol-document set for the current project goal. The repository stores the index and project notes rather than bulk copies of scanned manuals. Where a stable text transcription is available, the direct transcription URL is preferred for searchability; original scans remain useful for checking diagrams, typography and transcription errors.

## Core Phase IV documents

| Layer | Digital specification | Project use | Searchable source |
| --- | --- | --- | --- |
| Architecture | DECnet Digital Network Architecture (Phase IV) General Description, AA-N149A-TK | Layering, terminology and relationships between components | https://linux-decnet.sourceforge.net/docs/doc_index.html |
| Ethernet data link | DNA Phase IV Ethernet Data Link Functional Specification, AA-Y298A-TK | DECnet-over-Ethernet conventions and link behavior | https://linux-decnet.sourceforge.net/docs/edatlin10.txt |
| Routing | DNA Phase IV Routing Layer Functional Specification V2.0, AA-X435A-TK | Endnode, L1/L2 router behavior, initialization, routing updates, forwarding, visit count, adjacency | https://linux-decnet.sourceforge.net/docs/route20.txt |
| NSP | DNA Phase IV Network Services Protocol Functional Specification V4.0, AA-X439A-TK | Logical links, sequencing, ACKs, retransmission, flow control and disconnect behavior | https://linux-decnet.sourceforge.net/docs/nsp401.txt |
| Session Control | DNA Session Control Functional Specification V1.0, AA-K182A-TK | Object addressing, connect data and user/session semantics above NSP | https://linux-decnet.sourceforge.net/docs/session10.txt |
| Network management / NICE | DNA Phase IV Network Management Functional Specification V4.0, AA-X437A-TK | NICE entities, parameters, counters, read/control operations and event model | https://linux-decnet.sourceforge.net/docs/netman40.txt |
| MOP | DNA Phase IV Maintenance Operations Functional Specification V3.0, AA-X436A-TK | Maintenance functions, console carrier, counters and later load/dump work | https://linux-decnet.sourceforge.net/docs/maintop30.txt |
| DAP | DNA Data Access Protocol Functional Specification V5.6, AA-K177A-TK | Remote file access message formats and procedures for DAP/FAL/RMS tools | https://linux-decnet.sourceforge.net/docs/dap_v5_6_0.txt |

The Phase IV specification family and order numbers are independently corroborated by Digital's later Phase IV Token Ring functional specification and by the preserved DECnet Phase IV specification index.

## Development rule

Read the applicable functional specification before copying behavior from any implementation. Tests derived from a specification should cite the document/version and, where practical, the section or state-table entry that motivates the test.

Specifications are authoritative for protocol meaning. Implementations are evidence about interoperability and about mistakes that real systems may make.

## Practical layer mapping for this repository

- Phase 3 Ethernet initialization/adjacency: Ethernet Data Link + Routing V2.0.
- Phase 4 routing: Routing V2.0, then Route20/PyDECnet cross-checks.
- Phase 5 NSP/socket ABI: NSP V4.0 plus Session Control V1.0; LinuxDECnet is the Linux API compatibility reference.
- Phase 6 management: Network Management V4.0/NICE plus PyDECnet NML and LinuxDECnet NML behavior.
- Phase 7 file utilities: DAP V5.6 plus LinuxDECnet libdap/librms/FAL and PyDECnet FAL.
- Phase 8 distributed lab transport: VDE2/libvdeplug behavior plus PyDECnet MULTINET TCP and controlled HECnet Area-31 peers.
