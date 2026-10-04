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

"""PP-11 S2 four-VM one-hour sustained deterministic fault controller."""

from __future__ import annotations
import hashlib
import os
from pathlib import Path
import re
import subprocess
import struct
import sys
import time

from dniv_scale import Lab, decnet_mac, guest, wait_for_markers

FAULT_EVENTS = 10000
FAULT_DURATION = 3600.0
VALID_PROBES = 1200
MAX_SLAB_GROWTH_KB = 65536
MAX_LINKS = 32
MIN_RESOURCE_SAMPLES = 50
MIN_FORWARDED = 1000
MIN_TRAFFIC_SPAN_SECONDS = FAULT_DURATION - 10.0
MAX_VALID_GAP_SECONDS = 30.0
FATAL = (
    "BUG: KASAN:", "BUG: KCSAN:", "kernel BUG at", "Kernel panic", "Oops:",
    "general protection fault", "use-after-free", "double free", "WARNING: CPU:",
)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def host_sample(path: Path, guests) -> None:
    stamp = time.time_ns()
    with path.open("a", encoding="utf-8") as out:
        for item in guests:
            if item.process is None or item.process.poll() is not None:
                raise RuntimeError(f"pp11-s2: guest exited during sustained fault run: {item.name}")
            status = Path(f"/proc/{item.process.pid}/status").read_text(encoding="utf-8")
            rss = re.search(r"^VmRSS:\s+(\d+)\s+kB$", status, re.MULTILINE)
            threads = re.search(r"^Threads:\s+(\d+)$", status, re.MULTILINE)
            out.write(
                f"{stamp}\t{item.name}\trss_kb={rss.group(1) if rss else '0'}"
                f"\tthreads={threads.group(1) if threads else '0'}\n"
            )


def parse_resources(path: Path, session: str, node: str) -> list[tuple[int, int, int, int, int]]:
    pattern = re.compile(
        rf"DNIV-PP11-S2-RESOURCE session={re.escape(session)} node={re.escape(node)} "
        r"stage=\S+ links=(\d+) adj=(\d+) routes=(\d+) mem_kb=(\d+) slab_kb=(\d+)"
    )
    return [tuple(int(value) for value in match.groups())
            for match in pattern.finditer(read_text(path))]


def pcap_faults(paths: list[Path]) -> int:
    marker = b"DNIV-S2-FAULT-"
    return sum(path.read_bytes().count(marker) for path in paths if path.exists())


def forwarded_timestamps(path: Path, marker: str, router_mac: str) -> list[float]:
    data = path.read_bytes()
    if len(data) < 24:
        return []
    magic = data[:4].hex()
    if magic == "d4c3b2a1":
        endian, divisor = "<", 1_000_000.0
    elif magic == "a1b2c3d4":
        endian, divisor = ">", 1_000_000.0
    elif magic == "4d3cb2a1":
        endian, divisor = "<", 1_000_000_000.0
    elif magic == "a1b23c4d":
        endian, divisor = ">", 1_000_000_000.0
    else:
        raise RuntimeError(f"unsupported pcap magic in {path}")
    needle = marker.encode()
    out: list[float] = []
    off = 24
    while off + 16 <= len(data):
        sec, frac, incl, _ = struct.unpack_from(endian + "IIII", data, off)
        off += 16
        frame = data[off:off + incl]
        off += incl
        if len(frame) < 37 or frame[12:14].hex() != "6003" or needle not in frame:
            continue
        plen = int.from_bytes(frame[14:16], "little")
        if 16 + plen > len(frame):
            continue
        route = frame[16:16 + plen]
        if len(route) < 21 or (route[0] & 0xc7) != 0x06:
            continue
        source = ":".join(f"{value:02x}" for value in frame[6:12])
        if source == router_mac and route[18] == 1:
            out.append(sec + frac / divisor)
    return out


def require_forwarded(path: Path, session: str, node: str,
                      router_mac: str) -> tuple[int, float, float]:
    marker = f"DNIV-PP11-S2-VALID-{session}-{node}-"
    times = forwarded_timestamps(path, marker, router_mac)
    count = len(times)
    if count < MIN_FORWARDED:
        raise RuntimeError(f"pp11-s2: forwarded valid traffic {node}={count} < {MIN_FORWARDED}")
    span = times[-1] - times[0]
    if span < MIN_TRAFFIC_SPAN_SECONDS:
        raise RuntimeError(
            f"pp11-s2: valid traffic span {node}={span:.3f}s < {MIN_TRAFFIC_SPAN_SECONDS:.3f}s"
        )
    max_gap = max((right - left for left, right in zip(times, times[1:])), default=0.0)
    if max_gap > MAX_VALID_GAP_SECONDS:
        raise RuntimeError(
            f"pp11-s2: valid traffic gap {node}={max_gap:.3f}s > {MAX_VALID_GAP_SECONDS:.3f}s"
        )
    return count, span, max_gap


def main() -> int:
    if len(sys.argv) != 4:
        raise SystemExit(f"usage: {sys.argv[0]} BASE-QCOW2 KERNEL INITRD")
    base, kernel, initrd = (Path(arg) for arg in sys.argv[1:4])
    for path in (base, kernel, initrd):
        if not path.is_file():
            raise SystemExit(f"pp11-s2: missing {path}")
    session = os.environ.get("DNIV_LAB_SESSION_ID", f"pp11-s2-{os.getpid()}")
    artifacts = Path(os.environ.get("DNIV_LAB_ARTIFACTS", "tests/lab/artifacts"))
    work = artifacts / session
    work.mkdir(parents=True, exist_ok=True)
    suffix = hashlib.sha256(session.encode()).hexdigest()[:4]
    lab = Lab(base, kernel, initrd, work, session, 2)
    area = 31
    router_mac = decnet_mac(area, 72)
    a0 = guest(lab, suffix, "DN70", area, 70, "A", "pp11s2", [(0, 0)],
               [decnet_mac(area, 70)], router_mac, "31.72", "31.71",
               hold_after_pass=True, probe_count=VALID_PROBES)
    a1 = guest(lab, suffix, "DN73", area, 73, "A", "pp11s2", [(0, 1)],
               [decnet_mac(area, 73)], router_mac, "31.72", "31.71",
               hold_after_pass=True, probe_count=VALID_PROBES)
    b0 = guest(lab, suffix, "DN71", area, 71, "B", "pp11s2", [(1, 0)],
               [decnet_mac(area, 71)], router_mac, "31.72", "31.70",
               hold_after_pass=True, probe_count=VALID_PROBES)
    r0 = guest(lab, suffix, "DN72", area, 72, "R", "pp11s2",
               [(0, 2), (1, 1)],
               ["52:54:12:00:00:72", "52:54:13:00:00:72"],
               router_mac, "31.72", "31.72")
    endpoints = [a0, a1, b0]
    guests = [r0, *endpoints]
    injector_log = work / "fault-events.tsv"
    injector_out = work / "injector.log"
    host_resources = work / "host-resources.tsv"
    started = time.monotonic()
    success = False
    try:
        lab.setup_network([[a0.taps[0], a1.taps[0], r0.taps[0]],
                           [b0.taps[0], r0.taps[1]]])
        lab.start(r0)
        wait_for_markers([r0], "DNIV-PP11-S2-ROUTER-READY", session, 300, [])
        for endpoint in endpoints:
            lab.start(endpoint)
        wait_for_markers(endpoints, "DNIV-PP11-S2-TRAFFIC-READY", session, 420, [r0])
        time.sleep(5)
        if any(proc.poll() is not None for proc in lab.captures):
            raise RuntimeError("pp11-s2: capture died before fault injection")
        command = [
            "sudo", "python3", str(Path(__file__).with_name("inject-pp11-s2.py")),
            "--interface", lab.bridges[0], "--interface", lab.bridges[1],
            "--destination", router_mac, "--events", str(FAULT_EVENTS),
            "--duration", str(int(FAULT_DURATION)), "--evidence", str(injector_log),
        ]
        with injector_out.open("wb") as output:
            proc = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT)
            sample_at = time.monotonic()
            while proc.poll() is None:
                now = time.monotonic()
                if now >= sample_at:
                    host_sample(host_resources, guests)
                    sample_at = now + 60.0
                if any(item.process is None or item.process.poll() is not None for item in guests):
                    proc.terminate()
                    raise RuntimeError("pp11-s2: guest exited while injector was active")
                if any(capture.poll() is not None for capture in lab.captures):
                    proc.terminate()
                    raise RuntimeError("pp11-s2: capture died while injector was active")
                time.sleep(1)
            if proc.returncode:
                raise RuntimeError(f"pp11-s2: injector failed rc={proc.returncode}")
        wait_for_markers(endpoints, "DNIV-PP11-S2-PASS", session, 900, [r0])
        host_sample(host_resources, guests)
        success = True
    finally:
        lab.close()
    if not success:
        return 1
    elapsed = time.monotonic() - started
    evidence = read_text(injector_log)
    if f"EVENTS_SENT={FAULT_EVENTS}" not in evidence or "RESULT=PASS" not in evidence:
        raise RuntimeError("pp11-s2: exact fault-count evidence missing")
    duration_match = re.search(r"^DURATION_ACTUAL=([0-9.]+)$", evidence, re.MULTILINE)
    if not duration_match or float(duration_match.group(1)) < FAULT_DURATION:
        raise RuntimeError("pp11-s2: one-hour fault duration not proven")
    captured_faults = pcap_faults(lab.pcaps)
    if captured_faults < FAULT_EVENTS:
        raise RuntimeError(f"pp11-s2: captured faults={captured_faults} < {FAULT_EVENTS}")
    forwarded = {
        "DN70": require_forwarded(lab.pcaps[1], session, "DN70", router_mac),
        "DN73": require_forwarded(lab.pcaps[1], session, "DN73", router_mac),
        "DN71": require_forwarded(lab.pcaps[0], session, "DN71", router_mac),
    }
    summary = [
        f"SESSION={session}", f"ARCH={lab.arch}", "VM_COUNT=4",
        f"FAULT_EVENTS={FAULT_EVENTS}", f"FAULTS_CAPTURED={captured_faults}",
        f"FAULT_DURATION_SECONDS={float(duration_match.group(1)):.3f}",
        f"TOTAL_RUNTIME_SECONDS={elapsed:.3f}",
    ]
    for item in guests:
        log = read_text(item.log)
        for marker in FATAL:
            if marker in log:
                raise RuntimeError(f"pp11-s2: fatal marker {marker} in {item.name}")
        rows = parse_resources(item.log, session, item.name)
        if len(rows) < MIN_RESOURCE_SAMPLES:
            raise RuntimeError(f"pp11-s2: {item.name} resource samples={len(rows)}")
        base_row, final_row = rows[0], rows[-1]
        peak_links = max(row[0] for row in rows)
        if peak_links > MAX_LINKS:
            raise RuntimeError(f"pp11-s2: {item.name} peak links={peak_links}")
        if final_row[4] > base_row[4] + MAX_SLAB_GROWTH_KB:
            raise RuntimeError(f"pp11-s2: {item.name} slab growth exceeded envelope")
        if final_row[1] < 1:
            raise RuntimeError(f"pp11-s2: {item.name} lost final adjacency")
        summary.extend([
            f"{item.name}_RESOURCE_SAMPLES={len(rows)}",
            f"{item.name}_PEAK_LINKS={peak_links}",
            f"{item.name}_SLAB_BASE_KB={base_row[4]}",
            f"{item.name}_SLAB_FINAL_KB={final_row[4]}",
            f"{item.name}_FINAL_ADJ={final_row[1]}",
        ])
    for node, (count, span, max_gap) in forwarded.items():
        summary.extend([
            f"{node}_FORWARDED_VALID={count}",
            f"{node}_VALID_SPAN_SECONDS={span:.3f}",
            f"{node}_MAX_VALID_GAP_SECONDS={max_gap:.3f}",
        ])
    host_lines = [line for line in read_text(host_resources).splitlines() if line.strip()]
    if len(host_lines) < 4 * MIN_RESOURCE_SAMPLES:
        raise RuntimeError(f"pp11-s2: host resource samples={len(host_lines)}")
    summary.extend([
        f"HOST_RESOURCE_ROWS={len(host_lines)}",
        f"LIMIT_MAX_SLAB_GROWTH_KB={MAX_SLAB_GROWTH_KB}",
        f"LIMIT_MAX_LINKS={MAX_LINKS}",
        f"LIMIT_MIN_FORWARDED={MIN_FORWARDED}",
        f"LIMIT_MIN_TRAFFIC_SPAN_SECONDS={MIN_TRAFFIC_SPAN_SECONDS:.3f}",
        f"LIMIT_MAX_VALID_GAP_SECONDS={MAX_VALID_GAP_SECONDS:.3f}",
        "RESULT=PASS",
    ])
    (work / "summary.env").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print(
        f"pp11-s2: pass arch={lab.arch} vms=4 faults={FAULT_EVENTS} "
        f"duration={float(duration_match.group(1)):.1f}s captured={captured_faults}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
