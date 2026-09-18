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
    area: int
    node: int
    role: str
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
                 work: Path, session: str):
        self.base = base.resolve()
        self.kernel = kernel.resolve()
        self.initrd = initrd.resolve()
        self.work = work
        self.session = session
        self.arch = platform.machine()
        suffix = hashlib.sha256(session.encode()).hexdigest()[:6]
        self.bridges = [f"e4a{suffix}", f"e4t{suffix}", f"e4b{suffix}"]
        self.pcaps = [work / "area31.pcap", work / "transit.pcap",
                      work / "area32.pcap"]
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
            raise RuntimeError("E4 capture failed to start")

    def command(self, guest: Guest) -> list[str]:
        cmdline = (
            f"root=LABEL=dniv-root rootfstype=ext4 rw dniv.smoke=1 dniv.mode=e4 "
            f"dniv.area={guest.area} dniv.node={guest.node} dniv.name={guest.name} "
            f"dniv.role={guest.role} dniv.session={self.session} "
            f"dniv.peer={guest.peer_mac} dniv.peer_node={guest.peer_node} "
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("base", type=Path)
    parser.add_argument("kernel", type=Path)
    parser.add_argument("initrd", type=Path)
    args = parser.parse_args()
    for path in (args.base, args.kernel, args.initrd):
        if not path.is_file():
            raise SystemExit(f"E4 missing {path}")
    for command in ("qemu-img", "tcpdump", "ip"):
        if shutil.which(command) is None:
            raise SystemExit(f"E4 missing host command {command}")

    session = os.environ.get("DNIV_LAB_SESSION_ID", f"e4-{os.getpid()}")
    timeout = int(os.environ.get("DNIV_LAB_TIMEOUT_SECONDS", "360"))
    artifacts = Path(os.environ.get("DNIV_LAB_ARTIFACTS",
                                    "tests/lab/artifacts"))
    work = artifacts / session
    work.mkdir(parents=True, exist_ok=True)
    suffix = hashlib.sha256(session.encode()).hexdigest()[:6]

    l1a_mac = decnet_mac(31, 72)
    l2a_mac = decnet_mac(31, 73)
    l1b_mac = decnet_mac(32, 72)
    l2b_mac = decnet_mac(32, 73)
    lab = Lab(args.base, args.kernel, args.initrd, work, session)

    a = Guest("A3170", 31, 70, "A", lab.overlay("end-a"),
              work/"end-a.serial.log", work/"end-a.qmp",
              [f"e4a{suffix}0"], [decnet_mac(31, 70)],
              l1a_mac, "31.72", "32.70")
    l1a = Guest("L1A", 31, 72, "L1", lab.overlay("l1-a"),
                work/"l1-a.serial.log", work/"l1-a.qmp",
                [f"e4a{suffix}1"], ["52:54:01:31:00:72"],
                l2a_mac, "31.73", "31.72")
    l2a = Guest("L2A", 31, 73, "L2", lab.overlay("l2-a"),
                work/"l2-a.serial.log", work/"l2-a.qmp",
                [f"e4a{suffix}2", f"e4t{suffix}1"],
                ["52:54:02:31:00:73", "52:54:03:31:00:73"],
                l1a_mac, "31.72", "31.73")
    l2b = Guest("L2B", 32, 73, "L2", lab.overlay("l2-b"),
                work/"l2-b.serial.log", work/"l2-b.qmp",
                [f"e4t{suffix}2", f"e4b{suffix}2"],
                ["52:54:03:32:00:73", "52:54:02:32:00:73"],
                l1b_mac, "32.72", "32.73")
    l1b = Guest("L1B", 32, 72, "L1", lab.overlay("l1-b"),
                work/"l1-b.serial.log", work/"l1-b.qmp",
                [f"e4b{suffix}1"], ["52:54:01:32:00:72"],
                l2b_mac, "32.73", "32.72")
    b = Guest("B3270", 32, 70, "B", lab.overlay("end-b"),
              work/"end-b.serial.log", work/"end-b.qmp",
              [f"e4b{suffix}0"], [decnet_mac(32, 70)],
              l1b_mac, "32.72", "31.70")
    guests = (a, l1a, l2a, l2b, l1b, b)

    ok = False
    try:
        lab.setup_network([
            [a.taps[0], l1a.taps[0], l2a.taps[0]],
            [l2a.taps[1], l2b.taps[0]],
            [b.taps[0], l1b.taps[0], l2b.taps[1]],
        ])
        for guest in (l2a, l2b, l1a, l1b, a, b):
            lab.start(guest)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if all(contains(g.log,
                            f"DNIV-E4-PASS session={session} node={g.name}")
                   for g in guests):
                ok = True
                time.sleep(2)
                break
            for guest in guests:
                if (guest.process and guest.process.poll() is not None and
                        not contains(guest.log, "DNIV-E4-PASS")):
                    raise RuntimeError(f"E4 guest exited early: {guest.name}")
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
                    guest.log.read_text(errors="replace").splitlines()[-160:]),
                    file=sys.stderr)
        return 1

    checks = [
        (lab.pcaps[1], f"DNIV-E4-{session}-A3170-", l2a_mac, 2,
         "A transit"),
        (lab.pcaps[2], f"DNIV-E4-{session}-A3170-", l2b_mac, 3,
         "A destination"),
        (lab.pcaps[1], f"DNIV-E4-{session}-B3270-", l2b_mac, 2,
         "B transit"),
        (lab.pcaps[0], f"DNIV-E4-{session}-B3270-", l2a_mac, 3,
         "B destination"),
    ]
    for pcap, marker, expected_source, expected_visit, label in checks:
        records = marker_sources(pcap, marker)
        matching = [1 for source, visit in records
                    if source == expected_source and visit == expected_visit]
        if len(matching) < 5:
            raise SystemExit(
                f"E4 missing {label} evidence via {expected_source} "
                f"visit={expected_visit}: {records}")

    print(f"python-lab: E4 pass on {lab.arch}, area 31 <-> area 32")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
