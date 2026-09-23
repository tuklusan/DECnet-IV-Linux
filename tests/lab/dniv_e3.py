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


def run(*args: str, check: bool = True):
    return subprocess.run(args, check=check, text=True)


def sudo(*args: str, check: bool = True):
    return run("sudo", *args, check=check)


def decnet_mac(area: int, node: int) -> str:
    address = (area << 10) | node
    return f"aa:00:04:00:{address & 0xff:02x}:{address >> 8:02x}"


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
    pos = 24
    while pos + 16 <= len(data):
        _, _, incl, _ = struct.unpack_from(endian + "IIII", data, pos)
        pos += 16
        frame = data[pos:pos + incl]
        pos += incl
        if len(frame) < 37 or frame[12:14] != b"\x60\x03" or needle not in frame:
            continue
        plen = int.from_bytes(frame[14:16], "little")
        if 16 + plen > len(frame):
            continue
        route = frame[16:16 + plen]
        if len(route) >= 21 and (route[0] & 0xc7) == 0x06:
            src = ":".join(f"{b:02x}" for b in frame[6:12])
            out.append((src, route[18]))
    return out


@dataclass
class Guest:
    name: str
    node: int
    role: str
    disk: Path
    log: Path
    qmp: Path
    taps: list[str]
    macs: list[str]
    peer_mac: str
    peer_node: str
    alt_peer_mac: str
    alt_peer_node: str
    dest_node: str
    process: subprocess.Popen[bytes] | None = None


class Lab:
    def __init__(self, base: Path, kernel: Path, initrd: Path,
                 work: Path, session: str):
        self.base = base.resolve()
        self.kernel = kernel.resolve()
        self.initrd = initrd.resolve()
        self.work = work
        self.session = session
        self.arch = platform.machine()
        suffix = hashlib.sha256(session.encode()).hexdigest()[:6]
        self.bridges = [f"e3a{suffix}", f"e3b{suffix}"]
        self.pcaps = [work / "lan-a.pcap", work / "lan-b.pcap"]
        self.guests: list[Guest] = []
        self.captures: list[subprocess.Popen[bytes]] = []

    @property
    def accel(self) -> str:
        if Path("/dev/kvm").exists() and os.access("/dev/kvm", os.R_OK | os.W_OK):
            return "kvm"
        return "tcg"

    def overlay(self, name: str) -> Path:
        path = self.work / f"{name}.qcow2"
        run("qemu-img", "create", "-q", "-f", "qcow2", "-F", "qcow2",
            "-b", str(self.base), str(path))
        return path

    def setup_network(self, groups: list[list[str]]) -> None:
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
            raise RuntimeError("E3 capture failed to start")

    def command(self, guest: Guest, area: int) -> list[str]:
        cmdline = (
            f"root=LABEL=dniv-root rootfstype=ext4 rw dniv.smoke=1 dniv.mode=e3 "
            f"dniv.area={area} dniv.node={guest.node} dniv.name={guest.name} "
            f"dniv.role={guest.role} dniv.session={self.session} "
            f"dniv.peer={guest.peer_mac} dniv.peer_node={guest.peer_node} "
            f"dniv.alt_peer={guest.alt_peer_mac} "
            f"dniv.alt_peer_node={guest.alt_peer_node} "
            f"dniv.dest_node={guest.dest_node}"
        )
        if self.arch == "x86_64":
            cmd = ["qemu-system-x86_64", "-name", guest.name,
                   "-accel", self.accel, "-m", "512", "-smp", "1"]
            console = "console=ttyS0"
        elif self.arch == "aarch64":
            accel = self.accel
            cmd = ["qemu-system-aarch64", "-name", guest.name,
                   "-machine", "virt,gic-version=host" if accel == "kvm"
                   else "virt,gic-version=3",
                   "-accel", accel, "-cpu", "host" if accel == "kvm" else "max",
                   "-m", "1024", "-smp", "1"]
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

    def start(self, guest: Guest, area: int) -> None:
        guest.process = subprocess.Popen(self.command(guest, area))
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("base", type=Path)
    parser.add_argument("kernel", type=Path)
    parser.add_argument("initrd", type=Path)
    args = parser.parse_args()
    for path in (args.base, args.kernel, args.initrd):
        if not path.is_file():
            raise SystemExit(f"E3 missing {path}")
    for command in ("qemu-img", "tcpdump", "ip"):
        if shutil.which(command) is None:
            raise SystemExit(f"E3 missing host command {command}")

    area = 31
    session = os.environ.get("DNIV_LAB_SESSION_ID", f"e3-{os.getpid()}")
    timeout = max(int(os.environ.get("DNIV_LAB_TIMEOUT_SECONDS", "360")), 600)
    artifacts = Path(os.environ.get("DNIV_LAB_ARTIFACTS",
                                    "tests/lab/artifacts"))
    work = artifacts / session
    work.mkdir(parents=True, exist_ok=True)
    suffix = hashlib.sha256(session.encode()).hexdigest()[:6]

    lab = Lab(args.base, args.kernel, args.initrd, work, session)
    r1_mac = decnet_mac(area, 72)
    r2_mac = decnet_mac(area, 73)
    ga = Guest("DN70", 70, "A", lab.overlay("node-a"),
               work / "node-a.serial.log", work / "node-a.qmp",
               [f"e3a{suffix}0"], [decnet_mac(area, 70)],
               r2_mac, "31.73", r1_mac, "31.72", "31.71")
    gb = Guest("DN71", 71, "B", lab.overlay("node-b"),
               work / "node-b.serial.log", work / "node-b.qmp",
               [f"e3b{suffix}0"], [decnet_mac(area, 71)],
               r2_mac, "31.73", r1_mac, "31.72", "31.70")
    r1 = Guest("DN72", 72, "R1", lab.overlay("router-1"),
               work / "router-1.serial.log", work / "router-1.qmp",
               [f"e3a{suffix}1", f"e3b{suffix}1"],
               ["52:54:02:00:00:72", "52:54:03:00:00:72"],
               r2_mac, "31.73", r2_mac, "31.73", "31.72")
    r2 = Guest("DN73", 73, "R2", lab.overlay("router-2"),
               work / "router-2.serial.log", work / "router-2.qmp",
               [f"e3a{suffix}2", f"e3b{suffix}2"],
               ["52:54:02:00:00:73", "52:54:03:00:00:73"],
               r1_mac, "31.72", r1_mac, "31.72", "31.73")

    guests = (ga, gb, r1, r2)
    ok = False
    try:
        lab.setup_network([
            [ga.taps[0], r1.taps[0], r2.taps[0]],
            [gb.taps[0], r1.taps[1], r2.taps[1]],
        ])
        routers = (r1, r2)
        for guest in routers:
            lab.start(guest, area)

        router_deadline = time.monotonic() + min(timeout, 480)
        while time.monotonic() < router_deadline:
            if all(contains(g.log,
                            f"DNIV-E3-ROUTER-READY session={session} node={g.name}")
                   for g in routers):
                break
            for router in routers:
                if router.process and router.process.poll() is not None:
                    raise RuntimeError(
                        f"E3 router exited before readiness: {router.name}")
            time.sleep(1)
        else:
            raise RuntimeError("E3 routers did not both reach readiness")

        time.sleep(5)
        lab.start(ga, area)
        lab.start(gb, area)

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if all(contains(g.log,
                            f"DNIV-E3-PASS session={session} node={g.name}")
                   for g in guests):
                ok = True
                time.sleep(2)
                break
            for guest in guests:
                if (guest.process and guest.process.poll() is not None and
                        not contains(guest.log, "DNIV-E3-PASS")):
                    raise RuntimeError(f"E3 guest exited early: {guest.name}")
            time.sleep(1)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
    finally:
        lab.close()

    if not ok:
        for guest in guests:
            print(f"--- {guest.name} ---", file=sys.stderr)
            if guest.log.exists():
                print("\n".join(
                    guest.log.read_text(errors="replace").splitlines()[-140:]),
                    file=sys.stderr)
        return 1

    evidence = [
        (lab.pcaps[1], f"DNIV-E3-PRE-{session}-DN70-", r2_mac, "A->B pre"),
        (lab.pcaps[0], f"DNIV-E3-PRE-{session}-DN71-", r2_mac, "B->A pre"),
        (lab.pcaps[1], f"DNIV-E3-POST-{session}-DN70-", r1_mac, "A->B post"),
        (lab.pcaps[0], f"DNIV-E3-POST-{session}-DN71-", r1_mac, "B->A post"),
    ]
    for pcap, marker, expected_source, label in evidence:
        seen = marker_sources(pcap, marker)
        matching = [visit for source, visit in seen
                    if source == expected_source and visit == 1]
        if len(matching) < 5:
            raise SystemExit(
                f"E3 missing {label} forwarding via {expected_source}: {seen}")

    for guest in (ga, gb):
        if not contains(guest.log,
                        f"DNIV-E3-PRIMARY session={session} node={guest.name} router=31.73"):
            raise SystemExit(f"E3 {guest.name} never selected primary router")
        if not contains(guest.log,
                        f"DNIV-E3-ALTERNATE session={session} node={guest.name} router=31.72"):
            raise SystemExit(f"E3 {guest.name} never converged to alternate")
    if not contains(r2.log,
                    f"DNIV-E3-PRIMARY-DOWN session={session} node=DN73"):
        raise SystemExit("E3 primary router shutdown evidence missing")

    print(f"python-lab: E3 pass on {lab.arch}, 31.73 -> 31.72 convergence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
