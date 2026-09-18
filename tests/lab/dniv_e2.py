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
    return subprocess.run(args, check=check, text=True,
                          stdout=subprocess.PIPE if capture else None,
                          stderr=subprocess.PIPE if capture else None)


def sudo(*args: str, check: bool = True, capture: bool = False):
    return run("sudo", *args, check=check, capture=capture)


def decnet_mac(area: int, node: int) -> str:
    address = (area << 10) | node
    return f"aa:00:04:00:{address & 0xff:02x}:{address >> 8:02x}"


def contains(path: Path, text: str) -> bool:
    return path.exists() and text in path.read_text(errors="replace")


def pcap_forwarded_long_visits(path: Path, marker: str) -> list[int]:
    data = path.read_bytes()
    if len(data) < 24:
        return []
    magic = data[:4]
    if magic == b"\xd4\xc3\xb2\xa1":
        endian = "<"
    elif magic == b"\xa1\xb2\xc3\xd4":
        endian = ">"
    else:
        raise RuntimeError(f"unsupported pcap magic in {path}")
    off = 24
    visits: list[int] = []
    needle = marker.encode()
    while off + 16 <= len(data):
        _, _, incl, _ = struct.unpack_from(endian + "IIII", data, off)
        off += 16
        frame = data[off:off + incl]
        off += incl
        if len(frame) < 22 or frame[12:14] != b"\x60\x03" or needle not in frame:
            continue
        plen = int.from_bytes(frame[14:16], "little")
        if 16 + plen > len(frame):
            continue
        route = frame[16:16 + plen]
        if route and (route[0] & 0xc7) == 0x06 and len(route) >= 21:
            visits.append(route[18])
    return visits


def pcap_text_count(path: Path, marker: str) -> int:
    r = sudo("tcpdump", "-A", "-nn", "-s0", "-r", str(path),
             "ether proto 0x6003", check=False, capture=True)
    if r.returncode not in (0, 1):
        raise RuntimeError(r.stderr)
    return r.stdout.count(marker)


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
    dest_node: str
    process: subprocess.Popen[bytes] | None = None


class Lab:
    def __init__(self, base: Path, kernel: Path, initrd: Path, work: Path, session: str):
        self.base = base.resolve()
        self.kernel = kernel.resolve()
        self.initrd = initrd.resolve()
        self.work = work
        self.session = session
        self.arch = platform.machine()
        suffix = hashlib.sha256(session.encode()).hexdigest()[:6]
        self.bridges = [f"e2a{suffix}", f"e2b{suffix}"]
        self.pcaps = [work / "lan-a.pcap", work / "lan-b.pcap"]
        self.guests: list[Guest] = []
        self.captures: list[subprocess.Popen[bytes]] = []

    @property
    def accel(self) -> str:
        return "kvm" if Path("/dev/kvm").exists() and os.access("/dev/kvm", os.R_OK | os.W_OK) else "tcg"

    def overlay(self, name: str) -> Path:
        p = self.work / f"{name}.qcow2"
        run("qemu-img", "create", "-q", "-f", "qcow2", "-F", "qcow2",
            "-b", str(self.base), str(p))
        return p

    def setup_network(self, taps_by_bridge: list[list[str]]) -> None:
        for bridge, taps, pcap in zip(self.bridges, taps_by_bridge, self.pcaps):
            sudo("ip", "link", "add", bridge, "type", "bridge")
            sudo("ip", "link", "set", bridge, "up")
            for tap in taps:
                sudo("ip", "tuntap", "add", "dev", tap, "mode", "tap",
                     "user", str(os.getuid()))
                sudo("ip", "link", "set", tap, "master", bridge)
                sudo("ip", "link", "set", tap, "up")
            proc = subprocess.Popen(["sudo", "tcpdump", "-U", "-i", bridge,
                                     "-w", str(pcap), "ether proto 0x6003"],
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
            self.captures.append(proc)
        time.sleep(1)
        if any(p.poll() is not None for p in self.captures):
            raise RuntimeError("E2 capture failed to start")

    def command(self, g: Guest, area: int) -> list[str]:
        cmdline = (
            f"root=LABEL=dniv-root rootfstype=ext4 rw dniv.smoke=1 dniv.mode=e2 "
            f"dniv.area={area} dniv.node={g.node} dniv.name={g.name} "
            f"dniv.role={g.role} dniv.session={self.session} "
            f"dniv.peer={g.peer_mac} dniv.peer_node={g.peer_node} "
            f"dniv.dest_node={g.dest_node}"
        )
        if self.arch == "x86_64":
            cmd = ["qemu-system-x86_64", "-name", g.name, "-accel", self.accel,
                   "-m", "512", "-smp", "1"]
            console = "console=ttyS0"
        elif self.arch == "aarch64":
            accel = self.accel
            cmd = ["qemu-system-aarch64", "-name", g.name,
                   "-machine", "virt,gic-version=host" if accel == "kvm" else "virt,gic-version=3",
                   "-accel", accel, "-cpu", "host" if accel == "kvm" else "max",
                   "-m", "1024", "-smp", "1"]
            console = "earlycon=pl011,0x09000000 console=ttyAMA0"
        else:
            raise RuntimeError(f"unsupported host architecture {self.arch}")

        cmd += ["-kernel", str(self.kernel), "-initrd", str(self.initrd),
                "-append", f"{cmdline} {console}",
                "-drive", f"file={g.disk},if=virtio,format=qcow2"]
        for i, (tap, mac) in enumerate(zip(g.taps, g.macs)):
            cmd += ["-netdev", f"tap,id=lan{i},ifname={tap},script=no,downscript=no",
                    "-device", f"virtio-net-pci,netdev=lan{i},mac={mac}"]
        cmd += ["-qmp", f"unix:{g.qmp},server=on,wait=off",
                "-display", "none", "-monitor", "none",
                "-serial", f"file:{g.log}", "-no-reboot"]
        return cmd

    def start(self, g: Guest, area: int) -> None:
        g.process = subprocess.Popen(self.command(g, area))
        self.guests.append(g)

    def stop(self, g: Guest) -> None:
        if not g.process or g.process.poll() is not None:
            return
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.settimeout(.5)
                s.connect(str(g.qmp))
                s.recv(65536)
                s.sendall(b'{"execute":"qmp_capabilities"}\r\n')
                s.recv(65536)
                s.sendall(b'{"execute":"quit"}\r\n')
        except OSError:
            pass
        try:
            g.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            g.process.kill()
            g.process.wait()

    def close(self) -> None:
        for g in self.guests:
            self.stop(g)
        for p in self.captures:
            if p.poll() is None:
                sudo("kill", str(p.pid), check=False)
                try:
                    p.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    p.kill()
                    p.wait()
        for bridge in self.bridges:
            sudo("ip", "link", "del", bridge, check=False)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("base", type=Path)
    ap.add_argument("kernel", type=Path)
    ap.add_argument("initrd", type=Path)
    a = ap.parse_args()
    for p in (a.base, a.kernel, a.initrd):
        if not p.is_file():
            raise SystemExit(f"E2 missing {p}")
    for cmd in ("qemu-img", "tcpdump", "ip"):
        if shutil.which(cmd) is None:
            raise SystemExit(f"E2 missing host command {cmd}")

    area = 31
    session = os.environ.get("DNIV_LAB_SESSION_ID", f"e2-{os.getpid()}")
    timeout = int(os.environ.get("DNIV_LAB_TIMEOUT_SECONDS", "360"))
    artifacts = Path(os.environ.get("DNIV_LAB_ARTIFACTS", "tests/lab/artifacts"))
    work = artifacts / session
    work.mkdir(parents=True, exist_ok=True)
    suffix = hashlib.sha256(session.encode()).hexdigest()[:6]

    lab = Lab(a.base, a.kernel, a.initrd, work, session)
    router_mac = decnet_mac(area, 72)
    ga = Guest("DN70", 70, "A", lab.overlay("node-a"), work/"node-a.serial.log",
               work/"node-a.qmp", [f"e2a{suffix}0"], [decnet_mac(area,70)],
               router_mac, "31.72", "31.71")
    gb = Guest("DN71", 71, "B", lab.overlay("node-b"), work/"node-b.serial.log",
               work/"node-b.qmp", [f"e2b{suffix}0"], [decnet_mac(area,71)],
               router_mac, "31.72", "31.70")
    gr = Guest("DN72", 72, "R", lab.overlay("router"), work/"router.serial.log",
               work/"router.qmp", [f"e2a{suffix}1", f"e2b{suffix}1"],
               ["52:54:02:00:00:72", "52:54:03:00:00:72"],
               router_mac, "31.72", "31.72")

    ok = False
    try:
        lab.setup_network([[ga.taps[0], gr.taps[0]], [gb.taps[0], gr.taps[1]]])
        lab.start(gr, area)
        lab.start(ga, area)
        lab.start(gb, area)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if all(contains(g.log, f"DNIV-E2-PASS session={session} node={g.name}")
                   for g in (ga, gb, gr)):
                ok = True
                time.sleep(2)
                break
            if any(g.process and g.process.poll() is not None and
                   not contains(g.log, "DNIV-E2-PASS") for g in (ga, gb, gr)):
                break
            time.sleep(1)
    finally:
        lab.close()

    if not ok:
        for g in (ga, gb, gr):
            print(f"--- {g.name} ---", file=sys.stderr)
            if g.log.exists():
                print("\n".join(g.log.read_text(errors="replace").splitlines()[-120:]),
                      file=sys.stderr)
        return 1

    ab_marker = f"DNIV-E2-{session}-DN70-"
    ba_marker = f"DNIV-E2-{session}-DN71-"
    ab_visits = pcap_forwarded_long_visits(lab.pcaps[1], ab_marker)
    ba_visits = pcap_forwarded_long_visits(lab.pcaps[0], ba_marker)
    if len(ab_visits) < 5 or any(v != 1 for v in ab_visits):
        raise SystemExit(f"E2 bad A->B forwarding/visit evidence: {ab_visits}")
    if len(ba_visits) < 5 or any(v != 1 for v in ba_visits):
        raise SystemExit(f"E2 bad B->A forwarding/visit evidence: {ba_visits}")
    if pcap_text_count(lab.pcaps[1], f"DNIV-E2-MAXVISIT-{session}-DN70") != 0:
        raise SystemExit("E2 visit-count ceiling failed A->B")
    if pcap_text_count(lab.pcaps[0], f"DNIV-E2-MAXVISIT-{session}-DN71") != 0:
        raise SystemExit("E2 visit-count ceiling failed B->A")
    print(f"python-lab: E2 pass on {lab.arch}, forced router 31.70<->31.72<->31.71")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
