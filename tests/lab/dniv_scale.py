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
import shutil
import socket
import struct
import subprocess
import sys
import time
from dataclasses import dataclass


def run(*args: str, check: bool = True, capture: bool = False):
    return subprocess.run(
        args, check=check, text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def sudo(*args: str, check: bool = True, capture: bool = False):
    return run("sudo", *args, check=check, capture=capture)


def decnet_mac(area: int, node: int) -> str:
    address = (area << 10) | node
    return f"aa:00:04:00:{address & 0xff:02x}:{(address >> 8) & 0xff:02x}"


def contains(path: Path, text: str) -> bool:
    return path.exists() and text in path.read_text(errors="replace")


def marker_sources(path: Path, marker: str) -> list[tuple[str, int]]:
    data = path.read_bytes()
    if len(data) < 24:
        return []
    if data[:4] == b"\xd4\xc3\xb2\xa1":
        endian = "<"
    elif data[:4] == b"\xa1\xb2\xc3\xd4":
        endian = ">"
    else:
        raise RuntimeError(f"unsupported pcap magic in {path}")
    needle = marker.encode()
    out: list[tuple[str, int]] = []
    off = 24
    while off + 16 <= len(data):
        _, _, incl, _ = struct.unpack_from(endian + "IIII", data, off)
        off += 16
        frame = data[off:off + incl]
        off += incl
        if len(frame) < 37 or frame[12:14] != b"\x60\x03" or needle not in frame:
            continue
        plen = int.from_bytes(frame[14:16], "little")
        if 16 + plen > len(frame):
            continue
        route = frame[16:16 + plen]
        if len(route) >= 21 and (route[0] & 0xc7) == 0x06:
            source = ":".join(f"{b:02x}" for b in frame[6:12])
            out.append((source, route[18]))
    return out


@dataclass
class Guest:
    name: str
    area: int
    node: int
    role: str
    mode: str
    disk: Path
    log: Path
    qmp: Path
    taps: list[str]
    macs: list[str]
    peer_mac: str
    peer_node: str
    dest_node: str
    process: subprocess.Popen[bytes] | None = None


class Lab:
    def __init__(self, base: Path, kernel: Path, initrd: Path,
                 work: Path, session: str, segment_count: int):
        self.base = base.resolve()
        self.kernel = kernel.resolve()
        self.initrd = initrd.resolve()
        self.work = work
        self.session = session
        self.arch = platform.machine()
        suffix = hashlib.sha256(session.encode()).hexdigest()[:6]
        self.bridges = [f"sc{i}{suffix}" for i in range(segment_count)]
        self.pcaps = [work / f"segment-{i}.pcap" for i in range(segment_count)]
        self.guests: list[Guest] = []
        self.captures: list[subprocess.Popen[bytes]] = []

    @property
    def accel(self) -> str:
        if Path("/dev/kvm").exists() and os.access("/dev/kvm", os.R_OK | os.W_OK):
            return "kvm"
        return "tcg"

    @property
    def guest_memory(self) -> int:
        override = os.environ.get("DNIV_SCALE_GUEST_MB")
        if override:
            value = int(override)
            if value < 384:
                raise RuntimeError("DNIV_SCALE_GUEST_MB must be >= 384")
            return value
        return 512 if self.arch == "x86_64" else 640

    def overlay(self, name: str) -> Path:
        path = self.work / f"{name}.qcow2"
        run("qemu-img", "create", "-q", "-f", "qcow2", "-F", "qcow2",
            "-b", str(self.base), str(path))
        return path

    def setup_network(self, groups: list[list[str]]) -> None:
        if len(groups) != len(self.bridges):
            raise RuntimeError("scale segment definition mismatch")
        for bridge, taps, pcap in zip(self.bridges, groups, self.pcaps):
            sudo("ip", "link", "add", bridge, "type", "bridge")
            sudo("ip", "link", "set", bridge, "up")
            for tap in taps:
                sudo("ip", "tuntap", "add", "dev", tap, "mode", "tap",
                     "user", str(os.getuid()))
                sudo("ip", "link", "set", tap, "master", bridge)
                sudo("ip", "link", "set", tap, "up")
            proc = subprocess.Popen(
                ["sudo", "tcpdump", "-U", "-i", bridge, "-w", str(pcap),
                 "ether proto 0x6003"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.captures.append(proc)
        time.sleep(1)
        if any(proc.poll() is not None for proc in self.captures):
            raise RuntimeError("scale capture failed to start")

    def command(self, guest: Guest) -> list[str]:
        cmdline = (
            f"root=LABEL=dniv-root rootfstype=ext4 rw dniv.smoke=1 "
            f"dniv.mode={guest.mode} dniv.area={guest.area} dniv.node={guest.node} "
            f"dniv.name={guest.name} dniv.role={guest.role} "
            f"dniv.session={self.session} dniv.peer={guest.peer_mac} "
            f"dniv.peer_node={guest.peer_node} dniv.dest_node={guest.dest_node}"
        )
        memory = str(self.guest_memory)
        if self.arch == "x86_64":
            cmd = ["qemu-system-x86_64", "-name", guest.name,
                   "-accel", self.accel, "-m", memory, "-smp", "1"]
            console = "console=ttyS0"
        elif self.arch == "aarch64":
            accel = self.accel
            cmd = ["qemu-system-aarch64", "-name", guest.name,
                   "-machine", "virt,gic-version=host" if accel == "kvm"
                   else "virt,gic-version=3",
                   "-accel", accel,
                   "-cpu", "host" if accel == "kvm" else "max",
                   "-m", memory, "-smp", "1"]
            console = "earlycon=pl011,0x09000000 console=ttyAMA0"
        else:
            raise RuntimeError(f"unsupported host architecture {self.arch}")
        cmd += ["-kernel", str(self.kernel), "-initrd", str(self.initrd),
                "-append", f"{cmdline} {console}",
                "-drive", f"file={guest.disk},if=virtio,format=qcow2"]
        for index, (tap, mac) in enumerate(zip(guest.taps, guest.macs)):
            cmd += ["-netdev",
                    f"tap,id=lan{index},ifname={tap},script=no,downscript=no",
                    "-device", f"virtio-net-pci,netdev=lan{index},mac={mac}"]
        cmd += ["-qmp", f"unix:{guest.qmp},server=on,wait=off",
                "-display", "none", "-monitor", "none",
                "-serial", f"file:{guest.log}", "-no-reboot"]
        return cmd

    def start(self, guest: Guest) -> None:
        guest.process = subprocess.Popen(self.command(guest))
        self.guests.append(guest)

    def stop(self, guest: Guest) -> None:
        if not guest.process or guest.process.poll() is not None:
            return
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.settimeout(.5)
                sock.connect(str(guest.qmp))
                sock.recv(65536)
                sock.sendall(b'{"execute":"qmp_capabilities"}\r\n')
                sock.recv(65536)
                sock.sendall(b'{"execute":"quit"}\r\n')
        except OSError:
            pass
        try:
            guest.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            guest.process.kill()
            guest.process.wait()

    def close(self) -> None:
        for guest in self.guests:
            self.stop(guest)
        for proc in self.captures:
            if proc.poll() is None:
                sudo("kill", str(proc.pid), check=False)
                try:
                  proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
        for bridge in self.bridges:
            sudo("ip", "link", "del", bridge, check=False)


def guest(lab: Lab, suffix: str, name: str, area: int, node: int,
          role: str, mode: str, tap_indexes: list[tuple[int, int]],
          macs: list[str], peer_mac: str, peer_node: str,
          dest_node: str) -> Guest:
    taps = [f"s{segment}{suffix}{slot}" for segment, slot in tap_indexes]
    stem = name.lower()
    return Guest(name, area, node, role, mode, lab.overlay(stem),
                 lab.work / f"{stem}.serial.log", lab.work / f"{stem}.qmp",
                 taps, macs, peer_mac, peer_node, dest_node)


def validate_inputs(args: argparse.Namespace) -> None:
    for path in (args.base, args.kernel, args.initrd):
        if not path.is_file():
            raise SystemExit(f"scale missing {path}")
    if args.nodes not in (4, 8, 16):
        raise SystemExit("scale node count must be 4, 8, or 16")
    for command in ("qemu-img", "tcpdump", "ip"):
        if shutil.which(command) is None:
            raise SystemExit(f"scale missing host command {command}")


def wait_for_markers(guests: list[Guest], marker: str, session: str,
                     timeout: int, keepalive: list[Guest]) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if all(contains(g.log, f"{marker} session={session} node={g.name}")
                for g in guests):
            return
        for g in keepalive:
            if g.process and g.process.poll() is not None:
                raise RuntimeError(&"scale transit guest exited: {g.name}")
        for g in guests:
            if g.process and g.process.poll() is not None and not contains(
                    g.log, f"{marker} session={session} node={g.name}"):
                raise RuntimeError(f"scale endpoint exited early: {g.name}")
        time.sleep(1)
    raise RuntimeError(f"scale timed out waiting for {marker}")


def run_four(args: argparse.Namespace, work: Path, session: str,
             timeout: int) -> None:
    area = 31
    suffix = hashlib.sha256(session.encode()).hexdigest()[:4]
    lab = Lab(args.base, args.kernel, args.initrd, work, session, 2)
    router_mac = decnet_mac(area, 72)
    a0 = guest(lab, suffix, "DN70", area, 70, "A", "e2", [(0, 0)],
               [decnet_mac(area, 70)], router_mac, "31.72", "31.71")
    a1 = guest(lab, suffix, "DN73", area, 73, "A", "e2", [(0, 1)],
               [decnet_mac(area, 73)], router_mac, "31.72", "31.71")
    b0 = guest(lab, suffix, "DN71", area, 71, "B", "e2", [(1, 0)],
               [decnet_mac(area, 71)], router_mac, "31.72", "31.70")
    r0 = guest(lab, suffix, "DN72", area, 72, "R", "e2",
               [(0, 2), (1, 1)],
               ["52:54:12:00:00:72", "52:54:13:00:00:72"],
               router_mac, "31.72", "31.72")
    endpoints = [a0, a1, b0]
    try:
        lab.setup_network([[a0.taps[0], a1.taps[0], r0.taps[0]],
                            [b0.taps[0], r0.taps[1]]])
        lab.start(r0)
        for g in endpoints:
            lab.start(g)
        wait_for_markers(endpoints, "DNIV-E2-PASS", session, timeout, [r0])
        time.sleep(2)
    finally:
        lab.close()

    checks = [
        (lab.pcaps[1], f"DNIV-E2-{session}-DN70-", "DN70->DN71"),
        (lab.pcaps[1], f"DNIV-E2-{session}-DN73-", "DN73->DN71"),
        (lab.pcaps[0], f"DNIV-E2-{session}-DN71-", "DN71->DN70"),
    ]
    for pcap, marker, label in checks:
        seen = marker_sources(pcap, marker)
        forwarded = [1 for source, visit in seen
                     if source == router_mac and visit == 1]
        if len(forwarded) < 5:
            raise RuntimeError(f"scale-4 missing {label} evidence: {seen}")


def run_multi_area(args: argparse.Namespace, work: Path, session: str,
                   timeout: int) -> None:
    endpoint_nodes = [70, 71] if args.nodes == 8 else [70, 71, 74, 75, 76, 77]
    suffix = hashlib.sha256(session.encode()).hexdigest()[:4]
    lab = Lab(args.base, args.kernel, args.initrd, work, session, 3)
    l1a_mac = decnet_mac(31, 72)
    l2a_mac = decnet_mac(31, 73)
    l1b_mac = decnet_mac(32, 72)
    l2b_mac = decnet_mac(32, 73)

    l1a = guest(lab, suffix, "L1A", 31, 72, "L1", "e4", [(0, 20)],
                ["52:54:21:31:00:72"], l2a_mac, "31.73", "31.72")
    l2a = guest(lab, suffix, "L2A", 31, 73, "L2", "e4",
                [(0, 21), (1, 20)],
                ["52:54:22:31:00:73", "52:54:23:31:00:73"],
                l1a_mac, "31.72", "32.73")
    l2b = guest(lab, suffix, "L2B", 32, 73, "L2", "e4",
                [(1, 21), (2, 21)],
                ["52:54:23:32:00:73", "52:54:22:32:00:73"],
                l1b_mac, "32.72", "31.73")
    l1b = guest(lab, suffix, "L1B", 32, 72, "L1", "e4", [(2, 20)],
                ["52:54:21:32:00:72"], l2b_mac, "32.73", "32.72")
    routers = [l1a, l2a, l2b, l1b]

    side_a: list[Guest] = []
    side_b: list[Guest] = []
    for index, node in enumerate(endpoint_nodes):
        side_a.append(guest(
            lab, suffix, f"A31{node}", 31, node, "A", "e4", [(0, index)],
            [decnet_mac(31, node)], l1a_mac, "31.72", f"32.{node}"))
        side_b.append(guest(
            lab, suffix, f"B32{node}", 32, node, "B", "e4", [(2, index)],
            [decnet_mac(32, node)], l1b_mac, "32.72", f"31.{node}"))
    endpoints = side_a + side_b

    try:
        lab.setup_network([
            [g.taps[0] for g in side_a] + [l1a.taps[0], l2a.taps[0]],
            [l2a.taps[1], l2b.taps[0]],
            [g.taps[0] for g in side_b] + [l1b.taps[0], l2b.taps[1]],
        ])
        for r in routers:
            lab.start(r)
        ready_deadline = time.monotonic() + min(timeout, 900)
        while time.monotonic() < ready_deadline:
            if all(contains(r.log,
                            f"DNIV-E4-ROUTER-READY session={session} node={r.name}")
                   for r in routers):
                break
            for r in routers:
                if r.process and r.process.poll() is not None:
                    raise RuntimeError(f"scale router exited before readiness: {r.name}")
            time.sleep(1)
        else:
            raise RuntimeError("scale routers did not all become ready")
        time.sleep(10)
        for g in endpoints:
            lab.start(g)
        wait_for_markers(endpoints, "DNIV-E4-PASS", session, timeout, routers)
        time.sleep(2)
    finally:
        lab.close()

    for a, b in zip(side_a, side_b):
        for pcap, marker, source, visit, label in [
            (lab.pcaps[1], f"DNIV-E4-{session}-{a.name}-", l2a_mac, 2,
             f"{a.name} transit"),
            (lab.pcaps[2], f"DNIV-E4-{session}-{a.name}-", l2b_mac, 3,
             f"{a.name} destination"),
            (lab.pcaps[1], f"DNIV-E4-{session}-{b.name}-", l2b_mac, 2,
             f"{b.name} transit"),
            (lab.pcaps[0], f"DNIV-E4-{session}-{b.name}-", l2a_mac, 3,
             f"{b.name} destination"),
        ]:
            seen = marker_sources(pcap, marker)
            matching = [1 for actual_source, actual_visit in seen
                        if actual_source == source and actual_visit == visit]
            if len(matching) < 5:
                raise RuntimeError(
                    f"scale-{args.nodes} missing {label} via {source} "
                    f"visit={visit}: {seen}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("base", type=Path)
    parser.add_argument("kernel", type=Path)
    parser.add_argument("initrd", type=Path)
    parser.add_argument("--nodes", type=int, required=True)
    args = parser.parse_args()
    validate_inputs(args)

    session = os.environ.get("DNIV_LAB_SESSION_ID",
                             f"scale-{args.nodes}-{os.getpid()}")
    base_timeout = int(os.environ.get("DNIV_LAB_TIMEOUT_SECONDS", "900"))
    timeout = max(base_timeout, 600 if args.nodes == 4 else
                  900 if args.nodes == 8 else 1500)
    artifacts = Path(os.environ.get("DNIV_LAB_ARTIFACTS", "tests/lab/artifacts"))
    work = artifacts / session
    work.mkdir(parents=True, exist_ok=True)

    try:
        if args.nodes == 4:
            run_four(args, work, session, timeout)
        else:
            run_multi_area(args, work, session, timeout)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        for log in sorted(work.glob("*.serial.log")):
            print(f"--- {log.stem} ---", file=sys.stderr)
            print("\n".join(log.read_text(errors="replace").splitlines()[-120:]),
                  file=sys.stderr)
        return 1

    print(f"python-scale: pass arch={platform.machine()} nodes={args.nodes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
