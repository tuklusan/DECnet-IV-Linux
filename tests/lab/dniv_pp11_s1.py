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

"""PP-11 S1 disruptive two-VM churn controller.

This gate deliberately separates guest-local churn from host-controlled
network/reboot churn. Two exact-candidate VMs continuously offer DECnet
traffic while 100 explicitly counted disruption cycles execute. The gate is
bounded and produces host and guest resource/performance evidence; it is not a
substitute for PP-11 S2 or the owner-waived S3-S6 levels.
"""

from __future__ import annotations
import hashlib
import math
import os
from pathlib import Path
import re
import sys
import time
from dniv_lab import Guest, Lab, QmpClient, decnet_mac, read_env, sudo

LOCAL_EXPECTED = {"module": 5, "interface": 10, "identity": 10, "peer-restart": 10}
LOCAL_PER_GUEST = sum(LOCAL_EXPECTED.values())
TOPOLOGY_PER_GUEST = 10
REBOOT_PER_GUEST = 5
TOTAL_CYCLES = 2 * (LOCAL_PER_GUEST + TOPOLOGY_PER_GUEST + REBOOT_PER_GUEST)
MIN_APP_SUCCESSES = 40
MIN_RAW_MARKERS = 100
MAX_P99_MS = 20000
MIN_PAYLOAD_BPS = 25.0
MAX_SLAB_GROWTH_KB = 65536
MAX_FINAL_LINKS = 8
FATAL_MARKERS = (
    "DNIV-LAB-FAIL", "BUG: KASAN:", "BUG: KCSAN:", "kernel BUG at",
    "Kernel panic", "Oops:", "general protection fault", "use-after-free",
    "double free", "WARNING: CPU:",
)

def log_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""

def marker_count(path: Path, marker: str) -> int:
    return sum(1 for line in log_text(path).splitlines() if marker in line)

def wait_marker_count(guest: Guest, marker: str, wanted: int, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if marker_count(guest.log, marker) >= wanted:
            return
        if guest.process is not None and guest.process.poll() is not None:
            raise RuntimeError(f"pp11-s1: {guest.name} exited waiting for {marker}")
        time.sleep(0.5)
    raise RuntimeError(f"pp11-s1: timeout waiting for {guest.name} marker={marker!r} count={wanted}")

def wait_app_progress(guest: Guest, baseline: int, timeout: float) -> None:
    marker = "DNIV-PP11-APP-PASS session="
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if marker_count(guest.log, marker) > baseline:
            return
        if guest.process is not None and guest.process.poll() is not None:
            raise RuntimeError(f"pp11-s1: {guest.name} exited before traffic recovery")
        time.sleep(0.5)
    raise RuntimeError(f"pp11-s1: no application traffic recovery from {guest.name}")

def append_event(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
        handle.flush()
        os.fsync(handle.fileno())

def tap_is_up(tap: str) -> bool:
    flags = int(Path(f"/sys/class/net/{tap}/flags").read_text().strip(), 16)
    return bool(flags & 0x1)

def process_sample(guest: Guest) -> tuple[int, int, int]:
    proc = guest.process
    if proc is None or proc.poll() is not None:
        raise RuntimeError(f"pp11-s1: cannot sample stopped guest {guest.name}")
    pid = proc.pid
    status = Path(f"/proc/{pid}/status").read_text(encoding="utf-8")
    rss_match = re.search(r"^VmRSS:\s+(\d+)\s+kB$", status, re.MULTILINE)
    threads_match = re.search(r"^Threads:\s+(\d+)$", status, re.MULTILINE)
    stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").split()
    cpu_ticks = int(stat[13]) + int(stat[14])
    return int(rss_match.group(1)) if rss_match else 0, int(threads_match.group(1)) if threads_match else 0, cpu_ticks

def record_host_sample(path: Path, stage: str, guest: Guest) -> None:
    rss, threads, ticks = process_sample(guest)
    append_event(path, f"{time.time_ns()}\t{stage}\t{guest.name}\trss_kb={rss}\tthreads={threads}\tcpu_ticks={ticks}")

def percentile(values: list[int], q: float) -> int:
    if not values:
        raise RuntimeError("pp11-s1: percentile requested for empty sample")
    ordered = sorted(values)
    rank = max(1, math.ceil(q * len(ordered)))
    return ordered[rank - 1]

def pcap_marker_count(path: Path, marker: str) -> int:
    try:
        return path.read_bytes().count(marker.encode("ascii"))
    except FileNotFoundError:
        return 0

def parse_local_cycles(guest: Guest, session: str) -> dict[str, int]:
    counts = {key: 0 for key in LOCAL_EXPECTED}
    pattern = re.compile(
        rf"^DNIV-PP11-CYCLE-PASS session={re.escape(session)} node={re.escape(guest.name)} "
        r"kind=(module|interface|identity|peer-restart) index=([0-9]+)$"
    )
    seen: dict[str, set[int]] = {key: set() for key in LOCAL_EXPECTED}
    for line in log_text(guest.log).splitlines():
        match = pattern.match(line.strip())
        if not match:
            continue
        kind = match.group(1)
        index = int(match.group(2))
        if index in seen[kind]:
            raise RuntimeError(f"pp11-s1: duplicate {kind} cycle {index} in {guest.name}")
        seen[kind].add(index)
    for kind, indexes in seen.items():
        expected = LOCAL_EXPECTED[kind]
        if indexes != set(range(1, expected + 1)):
            raise RuntimeError(f"pp11-s1: {guest.name} {kind} cycles={sorted(indexes)} expected=1..{expected}")
        counts[kind] = len(indexes)
    return counts

def parse_latency(guest: Guest, session: str) -> tuple[list[int], set[int]]:
    pattern = re.compile(
        rf"^DNIV-PP11-APP-PASS session={re.escape(session)} node={re.escape(guest.name)} "
        r"seq=([0-9]+) cpu=([0-9]+) ms=([0-9]+) bytes=5240$"
    )
    values: list[int] = []
    cpus: set[int] = set()
    for line in log_text(guest.log).splitlines():
        match = pattern.match(line.strip())
        if match:
            cpus.add(int(match.group(2)))
            values.append(int(match.group(3)))
    return values, cpus

def parse_resources(guest: Guest, session: str) -> list[dict[str, int | str]]:
    pattern = re.compile(
        rf"^DNIV-PP11-RESOURCE session={re.escape(session)} node={re.escape(guest.name)} "
        r"stage=([^ ]+) links=([0-9]+) adj=([0-9]+) routes=([0-9]+) mem_kb=([0-9]+) slab_kb=([0-9]+)$"
    )
    rows: list[dict[str, int | str]] = []
    for line in log_text(guest.log).splitlines():
        match = pattern.match(line.strip())
        if match:
            rows.append({
                "stage": match.group(1), "links": int(match.group(2)),
                "adj": int(match.group(3)), "routes": int(match.group(4)),
                "mem_kb": int(match.group(5)), "slab_kb": int(match.group(6)),
            })
    return rows

def write_summary(path: Path, session: str, host_arch: str, runtime: float,
                  guests: tuple[Guest, Guest], cycle_counts: dict[str, int]) -> None:
    total_successes = 0
    total_bytes = 0
    lines = ["FORMAT=1", f"SESSION={session}", f"ARCH={host_arch}",
             f"TOTAL_CYCLES={sum(cycle_counts.values())}", f"RUNTIME_SECONDS={runtime:.3f}"]
    for kind in ("module", "interface", "identity", "peer-restart", "topology", "reboot"):
        lines.append(f"CYCLES_{kind.upper().replace('-', '_')}={cycle_counts.get(kind, 0)}")
    for guest in guests:
        values, cpus = parse_latency(guest, session)
        if len(values) < MIN_APP_SUCCESSES:
            raise RuntimeError(f"pp11-s1: {guest.name} application successes={len(values)} < {MIN_APP_SUCCESSES}")
        p50, p95, p99 = percentile(values, 0.50), percentile(values, 0.95), percentile(values, 0.99)
        if p99 > MAX_P99_MS:
            raise RuntimeError(f"pp11-s1: {guest.name} p99={p99}ms > {MAX_P99_MS}ms")
        if not {0, 1}.issubset(cpus):
            raise RuntimeError(f"pp11-s1: {guest.name} did not exercise both vCPUs: cpus={sorted(cpus)}")
        total_successes += len(values)
        total_bytes += len(values) * 5240
        raw = pcap_marker_count(path.parent / "lan.pcap", f"DNIV-PP11-RAW-{session}-{guest.name}-")
        if raw < MIN_RAW_MARKERS:
            raise RuntimeError(f"pp11-s1: {guest.name} raw traffic markers={raw} < {MIN_RAW_MARKERS}")
        resources = parse_resources(guest, session)
        if len(resources) < 4:
            raise RuntimeError(f"pp11-s1: insufficient resource snapshots from {guest.name}")
        first = resources[0]
        initial_ready = next((row for row in resources if str(row["stage"]) == "host-ready-1"), None)
        last = resources[-1]
        if initial_ready is None:
            raise RuntimeError(f"pp11-s1: missing pre-host-churn resource snapshot from {guest.name}")
        if int(initial_ready["slab_kb"]) > int(first["slab_kb"]) + MAX_SLAB_GROWTH_KB:
            raise RuntimeError(f"pp11-s1: {guest.name} local-churn slab growth exceeded envelope")
        if int(last["slab_kb"]) > int(first["slab_kb"]) + MAX_SLAB_GROWTH_KB:
            raise RuntimeError(f"pp11-s1: {guest.name} final slab growth exceeded envelope")
        if int(last["links"]) > MAX_FINAL_LINKS or int(last["adj"]) < 1:
            raise RuntimeError(f"pp11-s1: {guest.name} final state links={last['links']} adj={last['adj']} outside envelope")
        lines.extend([
            f"{guest.name}_APP_SUCCESSES={len(values)}", f"{guest.name}_P50_MS={p50}",
            f"{guest.name}_P95_MS={p95}", f"{guest.name}_P99_MS={p99}",
            f"{guest.name}_RAW_MARKERS={raw}", f"{guest.name}_CPUS={','.join(str(cpu) for cpu in sorted(cpus))}",
            f"{guest.name}_SLAB_BASE_KB={first['slab_kb']}",
            f"{guest.name}_SLAB_LOCAL_DONE_KB={initial_ready['slab_kb']}",
            f"{guest.name}_SLAB_FINAL_KB={last['slab_kb']}",
            f"{guest.name}_FINAL_LINKS={last['links']}", f"{guest.name}_FINAL_ADJ={last['adj']}",
        ])
    payload_bps = total_bytes / max(runtime, 0.001)
    if payload_bps < MIN_PAYLOAD_BPS:
        raise RuntimeError(f"pp11-s1: aggregate payload throughput={payload_bps:.2f} B/s < {MIN_PAYLOAD_BPS:.2f} B/s")
    lines.extend([
        f"APP_SUCCESSES={total_successes}", f"PAYLOAD_BYTES={total_bytes}", f"PAYLOAD_BPS={payload_bps:.3f}",
        f"LIMIT_MIN_APP_SUCCESSES_PER_GUEST={MIN_APP_SUCCESSES}",
        f"LIMIT_MIN_RAW_MARKERS_PER_GUEST={MIN_RAW_MARKERS}", f"LIMIT_MAX_P99_MS={MAX_P99_MS}",
        f"LIMIT_MIN_PAYLOAD_BPS={MIN_PAYLOAD_BPS:.3f}", f"LIMIT_MAX_SLAB_GROWTH_KB={MAX_SLAB_GROWTH_KB}",
        f"LIMIT_MAX_FINAL_LINKS={MAX_FINAL_LINKS}", "RESULT=PASS",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

def main() -> int:
    if len(sys.argv) != 4:
        raise SystemExit(f"usage: {sys.argv[0]} BASE-QCOW2 KERNEL INITRD")
    base, kernel, initrd = (Path(arg) for arg in sys.argv[1:4])
    for path in (base, kernel, initrd):
        if not path.is_file():
            raise SystemExit(f"pp11-s1: missing {path}")
    env = read_env(Path(__file__).with_name("test-addresses.env"))
    area = int(env["DECNET_TEST_AREA"])
    node_a = int(env["DECNET_TEST_FIRST_NODE"])
    node_b = node_a + 1
    name_a = f"{env['DECNET_TEST_NAME_PREFIX']}{node_a}"
    name_b = f"{env['DECNET_TEST_NAME_PREFIX']}{node_b}"
    session = os.environ.get("DNIV_LAB_SESSION_ID", f"pp11-s1-{int(time.time())}-{os.getpid()}")
    timeout = int(os.environ.get("DNIV_PP11_S1_TIMEOUT_SECONDS", "2400"))
    nic_model = os.environ.get("DNIV_LAB_NIC_MODEL", "virtio-net-pci")
    vcpus = int(os.environ.get("DNIV_LAB_VCPUS", "2"))
    if vcpus < 2:
        raise SystemExit("pp11-s1: requires at least 2 vCPUs")
    memory_mb = 1024 if os.uname().machine == "aarch64" else 512
    artifacts = Path(os.environ.get("DNIV_LAB_ARTIFACTS", "tests/lab/artifacts"))
    work = artifacts / session
    work.mkdir(parents=True, exist_ok=True)
    lab = Lab(base, kernel, initrd, work, "pp11s1", session, nic_model, vcpus, "none", memory_mb)
    suffix = hashlib.sha256(session.encode("utf-8")).hexdigest()[:6]
    mac_a, mac_b = decnet_mac(area, node_a), decnet_mac(area, node_b)
    guest_a = Guest(name_a, node_a, node_b, mac_b, "A", mac_a, f"pa{suffix}", lab.create_overlay("node-a"),
                    work / "node-a.serial.log", work / "node-a.qmp")
    guest_b = Guest(name_b, node_b, node_a, mac_a, "B", mac_b, f"pb{suffix}", lab.create_overlay("node-b"),
                    work / "node-b.serial.log", work / "node-b.qmp")
    guests = (guest_a, guest_b)
    cycle_file = work / "cycles.tsv"
    host_resources = work / "host-resources.tsv"
    start = time.monotonic()
    success = False
    try:
        lab.create_network([guest_a.tap, guest_b.tap])
        lab.start(guest_a, area)
        lab.start(guest_b, area)
        for guest in guests:
            wait_marker_count(guest, f"DNIV-PP11-HOST-READY session={session} node={guest.name} boot=1", 1, float(timeout))
            record_host_sample(host_resources, "local-done", guest)
        for guest in guests:
            peer = guest_b if guest is guest_a else guest_a
            for index in range(1, TOPOLOGY_PER_GUEST + 1):
                base_guest = marker_count(guest.log, "DNIV-PP11-APP-PASS session=")
                base_peer = marker_count(peer.log, "DNIV-PP11-APP-PASS session=")
                append_event(cycle_file, f"BEGIN\ttopology\t{guest.name}\t{index}")
                record_host_sample(host_resources, f"topology-{guest.name}-{index}-before", guest)
                sudo("ip", "link", "set", guest.tap, "down")
                if tap_is_up(guest.tap):
                    raise RuntimeError(f"pp11-s1: {guest.tap} remained UP after topology fault")
                append_event(cycle_file, f"FAULT\ttopology\t{guest.name}\t{index}\tdown")
                time.sleep(9.0)
                sudo("ip", "link", "set", guest.tap, "up")
                if not tap_is_up(guest.tap):
                    raise RuntimeError(f"pp11-s1: {guest.tap} did not return UP")
                append_event(cycle_file, f"RESTORE\ttopology\t{guest.name}\t{index}\tup")
                recover_timeout = 180.0 if lab.host_arch == "aarch64" else 120.0
                wait_app_progress(guest, base_guest, recover_timeout)
                wait_app_progress(peer, base_peer, recover_timeout)
                record_host_sample(host_resources, f"topology-{guest.name}-{index}-after", guest)
                append_event(cycle_file, f"PASS\ttopology\t{guest.name}\t{index}")
        for guest in guests:
            peer = guest_b if guest is guest_a else guest_a
            for index in range(1, REBOOT_PER_GUEST + 1):
                boot_before = marker_count(guest.log, f"DNIV-PP11-BOOT-READY session={session} node={guest.name}")
                ready_before = marker_count(guest.log, f"DNIV-PP11-HOST-READY session={session} node={guest.name}")
                app_guest = marker_count(guest.log, "DNIV-PP11-APP-PASS session=")
                app_peer = marker_count(peer.log, "DNIV-PP11-APP-PASS session=")
                append_event(cycle_file, f"BEGIN\treboot\t{guest.name}\t{index}")
                record_host_sample(host_resources, f"reboot-{guest.name}-{index}-before", guest)
                if not QmpClient(guest.qmp).execute("system_reset"):
                    raise RuntimeError(f"pp11-s1: QMP reset failed for {guest.name}")
                append_event(cycle_file, f"FAULT\treboot\t{guest.name}\t{index}\tsystem_reset")
                reboot_timeout = 300.0 if lab.host_arch == "aarch64" else 180.0
                wait_marker_count(guest, f"DNIV-PP11-BOOT-READY session={session} node={guest.name}", boot_before + 1, reboot_timeout)
                wait_marker_count(guest, f"DNIV-PP11-HOST-READY session={session} node={guest.name}", ready_before + 1, reboot_timeout)
                wait_app_progress(guest, app_guest, reboot_timeout)
                wait_app_progress(peer, app_peer, reboot_timeout)
                record_host_sample(host_resources, f"reboot-{guest.name}-{index}-after", guest)
                append_event(cycle_file, f"PASS\treboot\t{guest.name}\t{index}")
        time.sleep(5)
        lab.require_capture_running()
        success = True
    finally:
        lab.close()
    if not success:
        return 1
    cycle_counts = {kind: 0 for kind in (*LOCAL_EXPECTED.keys(), "topology", "reboot")}
    for guest in guests:
        for kind, count in parse_local_cycles(guest, session).items():
            cycle_counts[kind] += count
        if f"DNIV-PP11-OBSERVER-DONE session={session} node={guest.name} cycles=35" not in log_text(guest.log):
            raise RuntimeError(f"pp11-s1: {guest.name} did not observe all peer churn")
        text = log_text(guest.log)
        for marker in FATAL_MARKERS:
            if marker in text:
                raise RuntimeError(f"pp11-s1: fatal guest marker from {guest.name}: {marker}")
    for line in cycle_file.read_text(encoding="utf-8").splitlines():
        fields = line.split("\t")
        if len(fields) == 4 and fields[0] == "PASS" and fields[1] in {"topology", "reboot"}:
            cycle_counts[fields[1]] += 1
    if cycle_counts["topology"] != 2 * TOPOLOGY_PER_GUEST:
        raise RuntimeError(f"pp11-s1: topology cycle count={cycle_counts['topology']}")
    if cycle_counts["reboot"] != 2 * REBOOT_PER_GUEST:
        raise RuntimeError(f"pp11-s1: reboot cycle count={cycle_counts['reboot']}")
    if sum(cycle_counts.values()) != TOTAL_CYCLES:
        raise RuntimeError(f"pp11-s1: total cycle count={sum(cycle_counts.values())} expected={TOTAL_CYCLES}")
    runtime = time.monotonic() - start
    write_summary(work / "summary.env", session, lab.host_arch, runtime, guests, cycle_counts)
    print(f"pp11-s1: pass arch={lab.host_arch} vcpus={vcpus} cycles={TOTAL_CYCLES} runtime={runtime:.1f}s evidence={work}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
