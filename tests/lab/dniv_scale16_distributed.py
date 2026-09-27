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

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

from dniv_scale import Lab, decnet_mac, guest, marker_sources, wait_for_markers


def ssh_sync(config: Path, token: str, side: str) -> None:
    mine = f"/tmp/dniv-scale16-{token}-{side}.ready"
    peer_side = "b" if side == "a" else "a"
    peer = f"/tmp/dniv-scale16-{token}-{peer_side}.ready"
    cleanup = (
        f"rm -f {mine} {peer}; " if side == "a" else ""
    )
    remote = (
        cleanup
        + f": > {mine}; "
        + f"for i in $(seq 1 600); do [ -f {peer} ] && exit 0; sleep 1; done; "
        + "exit 111"
    )
    last = None
    for _ in range(3):
        last = subprocess.run(
            ["ssh", "-F", str(config), "dniv-bastion", remote],
            text=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        if last.returncode == 0:
            return
        time.sleep(2)
    raise RuntimeError(
        f"scale-16 distributed synchronization failed side={side}: "
        f"{(last.stderr if last else '').strip()}")


def run_partition(args: argparse.Namespace, work: Path, session: str) -> None:
    side = args.side
    suffix = hashlib.sha256(session.encode()).hexdigest()[:4]
    lab = Lab(args.base, args.kernel, args.initrd, work, session, 2)
    endpoint_nodes = [70, 71, 74, 75, 76, 77]
    hold = True
    probes = 120
    if platform.machine() == "aarch64":
        os.environ.setdefault("DNIV_SCALE_CMA_ZERO", "1")

    if side == "a":
        local_area, remote_area = 31, 32
        l1_mac = decnet_mac(31, 72)
        l2_mac = decnet_mac(31, 73)
        remote_l2 = decnet_mac(32, 73)
        l1 = guest(lab, suffix, "L1A", 31, 72, "L1", "e4", [(0, 20)],
                   ["52:54:21:31:00:72"], l2_mac, "31.73", "31.72")
        l2 = guest(lab, suffix, "L2A", 31, 73, "L2", "e4",
                   [(0, 21), (1, 20)],
                   ["52:54:22:31:00:73", "52:54:23:31:00:73"],
                   l1_mac, "31.72", "32.73")
        role = "A"
    else:
        local_area, remote_area = 32, 31
        l1_mac = decnet_mac(32, 72)
        l2_mac = decnet_mac(32, 73)
        remote_l2 = decnet_mac(31, 73)
        l2 = guest(lab, suffix, "L2B", 32, 73, "L2", "e4",
                   [(1, 20), (0, 21)],
                   ["52:54:23:32:00:73", "52:54:22:32:00:73"],
                   l1_mac, "32.72", "31.73")
        l1 = guest(lab, suffix, "L1B", 32, 72, "L1", "e4", [(0, 20)],
                   ["52:54:21:32:00:72"], l2_mac, "32.73", "32.72")
        role = "B"

    endpoints = []
    for index, node in enumerate(endpoint_nodes):
        endpoints.append(guest(
            lab, suffix, f"{role}{local_area}{node}", local_area, node, role, "e4",
            [(0, index)], [decnet_mac(local_area, node)], l1_mac,
            f"{local_area}.72", f"{remote_area}.{node}",
            hold_after_pass=hold, probe_count=probes))

    try:
        lab.setup_network([
            [g.taps[0] for g in endpoints] + [l1.taps[0], l2.taps[0]],
            [l2.taps[1], args.cross_tap],
        ])
        lab.start(l1)
        time.sleep(2)
        lab.start(l2)

        ready_deadline = time.monotonic() + 900
        while time.monotonic() < ready_deadline:
            if all(
                (g.log.exists() and
                 f"DNIV-E4-ROUTER-READY session={session} node={g.name}"
                 in g.log.read_text(errors="replace"))
                for g in (l1, l2)
            ):
                break
            for g in (l1, l2):
                if g.process and g.process.poll() is not None:
                    raise RuntimeError(
                        f"scale-16 distributed router exited before readiness: {g.name}")
            time.sleep(1)
        else:
            raise RuntimeError("scale-16 distributed routers did not become ready")

        started = []
        for endpoint in endpoints:
            lab.start(endpoint)
            wait_for_markers(
                [endpoint], "DNIV-E4-PASS", session, 600, [l1, l2] + started)
            started.append(endpoint)

        live = [l1, l2] + started
        if len(live) != 8 or any(
                g.process is None or g.process.poll() is not None for g in live):
            raise RuntimeError(
                f"scale-16 distributed side {side} did not retain 8 guests")
        print(f"scale-16-distributed: side={side} 8 independent guests live")
        ssh_sync(args.ssh_config, args.sync_token, side)
        time.sleep(3)
    finally:
        lab.close()

    if side == "a":
        checks = []
        for node in endpoint_nodes:
            checks += [
                (lab.pcaps[1], f"DNIV-E4-{session}-A31{node}-",
                 l2_mac, 2, f"A31{node} transit"),
                (lab.pcaps[0], f"DNIV-E4-{session}-B32{node}-",
                 l2_mac, 3, f"B32{node} destination"),
            ]
    else:
        checks = []
        for node in endpoint_nodes:
            checks += [
                (lab.pcaps[1], f"DNIV-E4-{session}-B32{node}-",
                 l2_mac, 2, f"B32{node} transit"),
                (lab.pcaps[0], f"DNIV-E4-{session}-A31{node}-",
                 l2_mac, 3, f"A31{node} destination"),
            ]

    for pcap, marker, source, visit, label in checks:
        seen = marker_sources(pcap, marker)
        matching = [
            1 for actual_source, actual_visit in seen
            if actual_source == source and actual_visit == visit
        ]
        if len(matching) < 5:
            raise RuntimeError(
                f"scale-16 distributed missing {label} via {source} "
                f"visit={visit}: {seen}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("base", type=Path)
    parser.add_argument("kernel", type=Path)
    parser.add_argument("initrd", type=Path)
    parser.add_argument("--side", choices=("a", "b"), required=True)
    parser.add_argument("--cross-tap", required=True)
    parser.add_argument("--ssh-config", type=Path, required=True)
    parser.add_argument("--sync-token", required=True)
    args = parser.parse_args()
    for path in (args.base, args.kernel, args.initrd, args.ssh_config):
        if not path.is_file():
            raise SystemExit(f"scale-16 distributed missing {path}")
    session = os.environ.get(
        "DNIV_LAB_SESSION_ID", f"scale16-dist-{args.sync_token}")
    artifacts = Path(
        os.environ.get("DNIV_LAB_ARTIFACTS", "tests/lab/artifacts"))
    work = artifacts / session
    work.mkdir(parents=True, exist_ok=True)
    try:
        run_partition(args, work, session)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        for log in sorted(work.glob("*.serial.log")):
            print(f"--- {log.stem} ---", file=sys.stderr)
            print("\n".join(log.read_text(errors="replace").splitlines()[-120:]),
                  file=sys.stderr)
        return 1
    print(
        f"python-scale16-distributed: pass arch={platform.machine()} "
        f"side={args.side}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
