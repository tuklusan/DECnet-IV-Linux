#!/usr/bin/env python3
# ============================================================================
# Copyright (c) 2026 Supratim Sanyal of SANYALnet Labs.
# Proprietary rights reserved except as expressly licensed herein.
#
# DECnet-IV-Linux
# This file is governed by the SANYALnet Labs Non-Commercial License in the
# root LICENSE file. Non-Commercial use is permitted; Commercial Use and use
# for AI/ML model training are prohibited unless separately authorized.
#
# Attribution is required: "Based on original work by Supratim Sanyal of
# SANYALnet Labs." See LICENSE for full terms, warranty disclaimer, termination,
# patent, trademark, and governing-law provisions.
# ============================================================================

"""Regression for bounded architecture-specific interop reference readiness."""

from __future__ import annotations

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (ROOT / "tests/lab/run-interop.sh").read_text(encoding="utf-8")
REFERENCE_IMAGE = (ROOT / "tests/lab/prepare-reference-image.sh").read_text(encoding="utf-8")
CANDIDATE_SMOKE = (ROOT / "tests/lab/dniv-interop-smoke.sh").read_text(encoding="utf-8")
PCAP_VALIDATOR = (ROOT / "tests/lab/validate-interop-pcap.py").read_text(encoding="utf-8")
REFERENCE_PEER = (ROOT / "tests/lab/dniv-reference-peer.sh").read_text(encoding="utf-8")
DNACCEPT = (ROOT / "tests/lab/dnaccept.c").read_text(encoding="utf-8")
DNMRR = (ROOT / "tests/lab/dnmrr.c").read_text(encoding="utf-8")
PYDECNET_INBOUND = (ROOT / "tests/lab/pydecnet-inbound.py").read_text(encoding="utf-8")


def main() -> int:
    default = re.findall(r"^reference_ready_seconds=(\d+)$", SCRIPT, re.MULTILINE)
    arm = re.findall(
        r'if \[\[ "\$host_arch" == aarch64 \]\]; then\n'
        r"\s*reference_ready_seconds=(\d+)\n"
        r"fi",
        SCRIPT,
        re.MULTILINE,
    )
    if default != ["180"]:
        raise SystemExit(f"interop-ready regression: amd64/default bound changed: {default}")
    if arm != ["600"]:
        raise SystemExit(f"interop-ready regression: ARM64 bound changed: {arm}")
    if int(arm[0]) <= int(default[0]):
        raise SystemExit("interop-ready regression: ARM64 bound must exceed default")
    if int(arm[0]) > 660:
        raise SystemExit("interop-ready regression: ARM64 reference-ready bound is excessive")

    executable_paths = [
        ROOT / "tests/lab/prepare-reference-image.sh",
        ROOT / "tests/lab/run-interop.sh",
    ]
    for executable_path in executable_paths:
        if not os.access(executable_path, os.X_OK):
            raise SystemExit(
                "interop-ready regression: interop harness executable bit missing: "
                f"{executable_path.relative_to(ROOT)}"
            )

    required_service_fragments = [
        "After=multi-user.target systemd-udev-settle.service",
        "ExecStartPre=/bin/sleep 60",
        "WantedBy=graphical.target",
        "graphical.target.wants/dniv-reference-peer.service",
    ]
    for fragment in required_service_fragments:
        if fragment not in REFERENCE_IMAGE:
            raise SystemExit(
                "interop-ready regression: reference guest must idle for 60 seconds "
                f"after multi-user boot before peer startup; missing {fragment!r}"
            )

    readiness_uses = (
        'wait_marker "$ref1_log" "$reference_ready_marker" '
        '"$reference_ready_seconds" "$REFERENCE_PID"',
        'wait_marker "$ref2_log" "$reference_ready_marker" '
        '"$reference_ready_seconds" "$REFERENCE_PID"',
    )
    for use in readiness_uses:
        if SCRIPT.count(use) != 1:
            raise SystemExit(
                "interop-ready regression: initial and restart reference "
                f"processes must use the bounded readiness marker/value: {use!r}"
            )
    if re.search(r'wait_marker "\\$ref[12]_log"[^\\n]*" [0-9]+ "\\$REFERENCE_PID"', SCRIPT):
        raise SystemExit("interop-ready regression: hardcoded readiness wait remains")


    convergence_watches = [
        r'DNIV-INTEROP-READY-STOP[^\n]*"\$CANDIDATE_PID" "\$REFERENCE_PID"',
        r'DNIV-INTEROP-PASS[^\n]*"\$CANDIDATE_PID" "\$REFERENCE_PID"',
    ]
    for pattern in convergence_watches:
        if not re.search(pattern, SCRIPT):
            raise SystemExit(
                "interop-ready regression: candidate convergence must fail fast "
                "when the reference VM exits"
            )



    waiter = re.search(
        r"wait_candidate_marker\(\) \{(?P<body>.*?)\n\}",
        SCRIPT,
        re.DOTALL,
    )
    if waiter is None:
        raise SystemExit("interop-ready regression: wait_candidate_marker function missing")
    body = waiter.group("body")
    fail_check = body.find('grep -Fq "$fail_marker" "$reference_log"')
    success_check = body.find('grep -Fq "$marker" "$log"')
    if fail_check < 0 or success_check < 0 or fail_check > success_check:
        raise SystemExit(
            "interop-ready regression: reference failure marker must be checked "
            "before candidate success during convergence"
        )


    if "timeout_seconds=720" not in SCRIPT or 'if [[ "$(uname -m)" == aarch64 ]]; then' not in SCRIPT:
        raise SystemExit(
            "interop-ready regression: ARM64 candidate-ready bound must be "
            "720 seconds for slow ARM64 candidate convergence"
        )
    if "DNIV_INTEROP_TIMEOUT_SECONDS:-}" not in SCRIPT:
        raise SystemExit(
            "interop-ready regression: explicit candidate timeout override must remain supported"
        )

    logical_nic_guard = (
        'if [[ "$reference" == pydecnet ]]; then\n'
        '    reference_hw=$reference_mac\n'
        'fi'
    )
    if logical_nic_guard not in SCRIPT:
        raise SystemExit(
            "interop-ready regression: PyDECnet reference NIC must use its "
            "DECnet logical MAC so ARM64 TCG does not depend on delayed "
            "promiscuous receive programming"
        )
    direct_tap_fragments = [
        'host_pydecnet="$work/host-pydecnet"',
        'circuit ETH-0 Ethernet $tap_reference --mode tap',
        "reference_ready_marker='DECnet/Python is running'",
        'host_pydecnet_api="/tmp/dniv-api-${suffix}.sock"',
        '"$script_dir/pydecnet-inbound.py" "$host_pydecnet_api"',
    ]
    for fragment in direct_tap_fragments:
        if fragment not in SCRIPT:
            raise SystemExit(
                "interop-ready regression: PyDECnet independent reference must "
                f"use the direct host TAP path; missing {fragment!r}"
            )
    if 'ip link set "$tap" address "$reference_hw"' in SCRIPT:
        raise SystemExit(
            "interop-ready regression: PyDECnet TAP Linux MAC must remain "
            "distinct from the DECnet logical MAC so bridge unicast reaches "
            "the TAP queue"
        )
    host_probe_fragments = [
        'cc -O2 -Wall -Wextra "$script_dir/dnraw.c" -o "$host_dnraw"',
        '"DNIV-INTEROP-PROBE-$session-$scenario-host-$probe_i"',
        'terminate_pid "${HOST_PROBE_PID:-}"',
    ]
    for fragment in host_probe_fragments:
        if fragment not in SCRIPT:
            raise SystemExit(
                "interop-ready regression: direct-TAP PyDECnet must retain "
                f"independent host raw-probe evidence; missing {fragment!r}"
            )
    if 'if counts["probes"] < 3' not in PCAP_VALIDATOR:
        raise SystemExit(
            "interop-ready regression: raw diagnostic probe minimum must apply "
            "to both independent reference paths"
        )
    if 'payload.startswith(b"DNIV-INTEROP-PROBE-")' not in PCAP_VALIDATOR:
        raise SystemExit(
            "interop-ready regression: raw probe evidence must be identified "
            "by its payload marker when reference hardware and DECnet MACs match"
        )
    if "args.reference_hw != args.reference_mac" not in PCAP_VALIDATOR:
        raise SystemExit(
            "interop-ready regression: pcap hello validation must allow a "
            "reference NIC whose hardware and DECnet logical MAC are identical"
        )

    responsive_call = (
        'if ! wait_post_change_hello "$peer_node" "$peer_kind" '
        '"$hello_ready_before" 240; then'
    )
    if responsive_call not in CANDIDATE_SMOKE:
        raise SystemExit(
            "interop-ready regression: PyDECnet NSP proof must require a "
            "fresh peer hello while the adjacency remains UP"
        )
    baseline_pos = CANDIDATE_SMOKE.find("hello_ready_before=$2")
    responsive_pos = CANDIDATE_SMOKE.find(responsive_call)
    mirror_pos = CANDIDATE_SMOKE.find('/usr/local/sbin/dnmrr "$peer_node"')
    if (
        baseline_pos < 0
        or responsive_pos < baseline_pos
        or mirror_pos < responsive_pos
    ):
        raise SystemExit(
            "interop-ready regression: fresh-hello readiness must be sampled "
            "after adjacency UP and before the MIRROR socket connect"
        )
    if "wait_peer_stable" in CANDIDATE_SMOKE:
        raise SystemExit(
            "interop-ready regression: fixed-duration guest stability polling "
            "must not gate PyDECnet NSP under ARM64 TCG"
        )
    if 'reason=no-unicast-probes' not in CANDIDATE_SMOKE:
        raise SystemExit(
            "interop-ready regression: post-MAC-change raw unicast receive "
            "proof must remain required for every independent reference path"
        )

    router_endnode_reference_guard = (
        'if [[ "$reference" == pydecnet && "$scenario" != router-endnode ]]; then'
    )
    if router_endnode_reference_guard not in SCRIPT:
        raise SystemExit(
            "interop-ready regression: PyDECnet inbound socket proof must skip only "
            "the pinned reference endnode outbound-NSP NoLink defect"
        )
    if 'if [ "$scenario" != router-endnode ]; then' not in CANDIDATE_SMOKE:
        raise SystemExit(
            "interop-ready regression: candidate listener must skip only the "
            "pinned PyDECnet endnode outbound-NSP NoLink defect"
        )

    inbound_fragments = [
        '/usr/local/sbin/dnaccept "$peer_node" "$session" "$scenario"',
        "DNIV-INTEROP-LISTEN-PASS",
    ]
    for fragment in inbound_fragments:
        if fragment not in CANDIDATE_SMOKE:
            raise SystemExit(
                "interop-ready regression: PyDECnet must retain direct inbound "
                f"AF_DECnet listen/accept proof; missing {fragment!r}"
            )
    candidate_image = (
        ROOT / "tests/lab/prepare-candidate-image.sh"
    ).read_text(encoding="utf-8")
    if "/usr/local/sbin/dnaccept" not in candidate_image:
        raise SystemExit(
            "interop-ready regression: candidate image must include dnaccept"
        )

    oob_candidate_fragments = [
        "POLLPRI",
        "SIOCATMARK",
        "MSG_OOB",
        'OOB_ONE "py-oob-one"',
        'OOB_TWO "py-oob-two"',
        'OOB_REPLY "linux-oob"',
        'AFTER_OOB "after-oob"',
    ]
    for fragment in oob_candidate_fragments:
        if fragment not in DNACCEPT:
            raise SystemExit(
                "interop-ready regression: candidate inbound proof must retain "
                f"interrupt/OOB coverage; missing {fragment!r}"
            )

    oob_reference_fragments = [
        "connection.interrupt(OOB_ONE)",
        "connection.interrupt(OOB_TWO)",
        'reply.type != "interrupt"',
        "time.sleep(1.0)",
    ]
    for fragment in oob_reference_fragments:
        if fragment not in PYDECNET_INBOUND:
            raise SystemExit(
                "interop-ready regression: PyDECnet inbound driver must retain "
                f"interrupt/OOB credit coverage; missing {fragment!r}"
            )

    option_candidate_fragments = [
        "DSO_CONACCESS",
        "DSO_CONDATA",
        "DSO_LINKINFO",
        'ACCESS_USER "DNIVUSER"',
        'CONNECT_DATA "dniv-connect"',
    ]
    for fragment in option_candidate_fragments:
        if fragment not in DNMRR:
            raise SystemExit(
                "interop-ready regression: MIRROR proof must retain outbound "
                f"classic socket-option coverage; missing {fragment!r}"
            )

    option_listener_fragments = [
        "getsockopt(fd, DNPROTO_NSP, DSO_CONDATA",
        "getsockopt(fd, DNPROTO_NSP, DSO_CONACCESS",
        'ACCEPT_DATA "linux-accept"',
        'CONNECT_DATA "py-connect"',
    ]
    for fragment in option_listener_fragments:
        if fragment not in DNACCEPT:
            raise SystemExit(
                "interop-ready regression: inbound listener proof must retain "
                f"access/connect-data coverage; missing {fragment!r}"
            )

    option_reference_fragments = [
        "conndata=CONNECT_DATA",
        "username=ACCESS_USER",
        "password=ACCESS_PASS",
        "account=ACCESS_ACCOUNT",
        "bytes(response) != ACCEPT_DATA",
    ]
    for fragment in option_reference_fragments:
        if fragment not in PYDECNET_INBOUND:
            raise SystemExit(
                "interop-ready regression: PyDECnet driver must retain "
                f"access/connect-data coverage; missing {fragment!r}"
            )

    option_pcap_fragments = [
        'counts["candidate_option_ci"] < 1',
        'counts["reference_option_ci"] < 2',
        'counts["candidate_accept_data"] < 2',
    ]
    for fragment in option_pcap_fragments:
        if fragment not in PCAP_VALIDATOR:
            raise SystemExit(
                "interop-ready regression: pcap evidence must retain "
                f"classic socket-option proof; missing {fragment!r}"
            )

    oob_pcap_fragments = [
        'counts["candidate_interrupt"] < 2',
        'counts["reference_interrupt"] < 4',
    ]
    for fragment in oob_pcap_fragments:
        if fragment not in PCAP_VALIDATOR:
            raise SystemExit(
                "interop-ready regression: pcap evidence must retain "
                f"bidirectional interrupt proof; missing {fragment!r}"
            )

    print("interop-ready regression passed: route20=180/600s pydecnet-host=60s direct-tap inbound+oob+options")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
