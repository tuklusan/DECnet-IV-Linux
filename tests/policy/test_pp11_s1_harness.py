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

"""Lock PP-11 S1 reboot and reciprocal-actor harness invariants."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAB = (ROOT / "tests/lab/dniv_lab.py").read_text(encoding="utf-8")
SMOKE = (ROOT / "tests/lab/dniv-smoke.sh").read_text(encoding="utf-8")
CONTROL = (ROOT / "tests/lab/dniv_pp11_s1.py").read_text(encoding="utf-8")
VM_WORKFLOW = (ROOT / ".github/workflows/vm-lab.yml").read_text(encoding="utf-8")
INTEROP_WORKFLOW = (ROOT / ".github/workflows/interop.yml").read_text(encoding="utf-8")
INTEROP_RUN = (ROOT / "tests/lab/run-interop.sh").read_text(encoding="utf-8")
INTEROP_SMOKE = (ROOT / "tests/lab/dniv-interop-smoke.sh").read_text(encoding="utf-8")
SEQWRAP = (ROOT / "tests/lab/dnseqwrap.c").read_text(encoding="utf-8")
BACKLOG = (ROOT / "tests/lab/dnbacklog.c").read_text(encoding="utf-8")
PY_BACKLOG = (ROOT / "tests/lab/pydecnet-backlog.py").read_text(encoding="utf-8")
ACKRANGE = (ROOT / "tests/lab/inject-nsp-ackrange.py").read_text(encoding="utf-8")
INTFLOW = (ROOT / "tests/lab/inject-nsp-intflow.py").read_text(encoding="utf-8")
PCAP = (ROOT / "tests/lab/validate-interop-pcap.py").read_text(encoding="utf-8")
SOCKET = (ROOT / "kernel/decnet/decnet_iv_socket.c").read_text(encoding="utf-8")


def main() -> int:
    required_lab = (
        'if self.mode != "pp11s1":',
        'cmd.append("-no-reboot")',
    )
    for marker in required_lab:
        if marker not in LAB:
            raise SystemExit(f"pp11-s1 regression: missing reboot guard: {marker}")
    for marker in (
        'reset_ack = QmpClient(guest.qmp).execute("system_reset")',
        'qmp_ack={int(reset_ack)}',
        'match = pattern.search(line.strip())',
    ):
        if marker not in CONTROL:
            raise SystemExit(f"pp11-s1 regression: missing reboot/evidence guard: {marker}")
    if 'raise RuntimeError(f"pp11-s1: QMP reset failed' in CONTROL:
        raise SystemExit("pp11-s1 regression: reset reply ambiguity must defer to boot-effect proof")
    if CONTROL.count('match = pattern.search(line.strip())') != 3:
        raise SystemExit("pp11-s1 regression: serial evidence parsers must accept syslog prefixes")
    if 'MAX_ANY_LINKS = 32' not in CONTROL or 'peak_links > MAX_ANY_LINKS' not in CONTROL:
        raise SystemExit("pp11-s1 regression: missing transient NSP link bound")
    if "    timeout-minutes: 75" not in VM_WORKFLOW:
        raise SystemExit("pp11-s1 regression: hosted job budget must permit arm64 completion")
    handoff = "pp11_observe 35\n            # The observer records the peer's final UP transition"
    if handoff not in SMOKE or "sleep 25\n            pp11_actor" not in SMOKE:
        raise SystemExit("pp11-s1 regression: missing reciprocal actor handoff gap")

    workflow_markers = (
        "pp11_pressure=1",
        "peer_segsize=128",
        'DNIV_INTEROP_PP11_PRESSURE="$pp11_pressure"',
    )
    for marker in workflow_markers:
        if marker not in INTEROP_WORKFLOW:
            raise SystemExit(f"pp11-s1 regression: missing pressure workflow marker: {marker}")
    if "'${{ matrix.arch }}' == amd64" in INTEROP_WORKFLOW.split("pp11_pressure=1", 1)[0].splitlines()[-4:]:
        raise SystemExit("pp11-s1 regression: pressure gate must run on both architectures")

    pressure_limits = (
        "connection_table_limit=256",
        "retransmit_queue_limit=64",
        "rx_queue_limit=32",
        "data_window_limit=20",
        "listener_backlog_limit=64",
        "malformed_control_per_round=96",
        "slab_envelope_bytes=67108864",
        "result=FAIL",
        "--pp11-pressure",
    )
    for marker in pressure_limits:
        if marker not in INTEROP_RUN:
            raise SystemExit(f"pp11-s1 regression: missing fail-closed pressure marker: {marker}")
    long_route_filters = (
        'match u8 "$control_flag" 0xff at 23 action drop',
        'match u8 "$window_lo" 0xff at 24',
        'match u8 "$window_hi" 0xff at 25 action drop',
        'match u8 "$int_lo" 0xff at 24',
        'match u8 "$int_hi" 0xff at 25 action drop',
    )
    for marker in long_route_filters:
        if marker not in INTEROP_RUN:
            raise SystemExit(
                f"pp11-s1 regression: missing long-routing pressure filter: {marker}"
            )
    pressure_fault_evidence = (
        'fault=pp11-table-%s round=%s\\n',
        '--name "pp11-table-$pressure_round"',
        'fault=pp11-rx-malformed-%s round=%s\\n',
        'pressure "$pressure_round" >>"$rx_log" 2>&1',
        '--name "pp11-rx-malformed-$pressure_round"',
        'fault=pp11-window-%s round=%s link=%s\\n',
        '--name "pp11-window-$pressure_round"',
        'fault=pp11-retransmit-%s round=%s\\n',
        'pressure "$pressure_round" >>"$int_log" 2>&1 &',
        '--name "pp11-retransmit-$pressure_round"',
        "window_link=${window_link%$'\\r'}",
        "int_link=${int_link%$'\\r'}",
    )
    for marker in pressure_fault_evidence:
        if marker not in INTEROP_RUN:
            raise SystemExit(
                f"pp11-s1 regression: missing fail-closed pressure evidence declaration: {marker}"
            )
    smoke_markers = (
        'while [ "$round" -le 3 ]',
        "count=256",
        "count=32",
        "accepted=64 busy=1",
        "count=20",
        "count=64",
        "PP11-MIRROR-LIVE",
        "pp11_wait_round_recovery",
    )
    for marker in smoke_markers:
        if marker not in INTEROP_SMOKE:
            raise SystemExit(f"pp11-s1 regression: missing pressure guest marker: {marker}")
    if "#define PRESSURE_RECORDS 650U" not in SEQWRAP or             "#define PRESSURE_PAUSE_NS 250000000L" not in SEQWRAP:
        raise SystemExit("pp11-s1 regression: pressure sequence-wrap duration/count changed")
    if "#define PRESSURE_BACKLOG 64U" not in BACKLOG or             "PRESSURE_COUNT = 65" not in PY_BACKLOG:
        raise SystemExit("pp11-s1 regression: pressure backlog boundary changed")
    if "malformed_control=96 rx_future=32" not in ACKRANGE:
        raise SystemExit("pp11-s1 regression: malformed/RX pressure count changed")
    if "credit=100 interrupts=64" not in INTFLOW:
        raise SystemExit("pp11-s1 regression: interrupt retransmit pressure count changed")
    if "candidate_sequence_wraps" not in PCAP or "candidate_no_resources_dc" not in PCAP:
        raise SystemExit("pp11-s1 regression: missing independent PCAP pressure evidence")
    unowned_reject_markers = (
        "static void dniv_reject_unowned(__u16 local_link, __u16 reason)",
        "(void)dniv_nsp_reject(local_link, reason, NULL, 0U);",
        "(void)dniv_nsp_conn_detach(local_link);",
        "dniv_reject_unowned(local_link, reject_reason);",
        "dniv_reject_unowned(pending[--count], DNIV_REASON_OBJECT_BUSY);",
        "dniv_reject_unowned(link, DNIV_REASON_INVALID_DESTINATION);",
        "dniv_reject_unowned(link, DNIV_REASON_OBJECT_BUSY);",
    )
    for marker in unowned_reject_markers:
        if marker not in SOCKET:
            raise SystemExit(
                f"pp11-s1 regression: missing unowned-reject recycle guard: {marker}"
            )
    if SOCKET.count("dniv_reject_unowned(") != 5:
        raise SystemExit("pp11-s1 regression: unowned reject paths changed")
    print("pp11-s1 regression passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
