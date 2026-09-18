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

"""Small, deterministic QEMU/QMP controller for DECnet protocol labs.

The controller deliberately treats the supplied base image as immutable. Every
node receives a throw-away qcow2 overlay; no checkpoint is uploaded or restored.
The release image builder remains a separate concern.
"""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import platform
import re
import shutil
import socket
import struct
import subprocess
import sys
import time
from dataclasses import dataclass

ROUTERS = "ab:00:00:03:00:00"
ENDNODES = "ab:00:00:04:00:00"


def run(*args: str, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=check,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def sudo(*args: str, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return run("sudo", *args, check=check, capture=capture)


def read_env(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if not sep:
            raise ValueError(f"invalid env line in {path}: {raw}")
        result[key] = value.strip().strip('"').strip("'")
    return result


def decnet_mac(area: int, node: int) -> str:
    address = (area << 10) | node
    return f"aa:00:04:00:{address & 0xff:02x}:{(address >> 8) & 0xff:02x}"


def lab_mac(area: int, node: int, changed: bool = False) -> str:
    address = (area << 10) | node
    prefix = "52:54:01" if changed else "52:54:00"
    return f"{prefix}:00:{address & 0xff:02x}:{(address >> 8) & 0xff:02x}"


def pcap_count(path: Path, expression: str) -> int:
    result = sudo(
        "tcpdump", "-nn", "-e", "-r", str(path), expression,
        check=False, capture=True,
    )
    if result.returncode not in (0, 1):
        raise RuntimeError(result.stderr.strip() or f"tcpdump failed for {expression}")
    return sum(1 for line in result.stdout.splitlines() if line.strip())



def pcap_router_init_seen(path: Path, mac_a: str, mac_b: str) -> bool:
    data = path.read_bytes()
    if len(data) < 24:
        return False
    magic = data[:4]
    if magic == b"\xd4\xc3\xb2\xa1":
        endian = "<"
    elif magic == b"\xa1\xb2\xc3\xd4":
        endian = ">"
    else:
        raise RuntimeError(f"unsupported pcap magic in {path}")

    def mac_bytes(text: str) -> bytes:
        return bytes(int(part, 16) for part in text.split(":"))

    endpoints = {mac_bytes(mac_a): mac_bytes(mac_b),
                 mac_bytes(mac_b): mac_bytes(mac_a)}
    off = 24
    while off + 16 <= len(data):
        _, _, incl, _ = struct.unpack_from(endian + "IIII", data, off)
        off += 16
        frame = data[off:off + incl]
        off += incl
        if len(frame) < 43 or frame[12:14] != b"\x60\x03":
            continue
        plen = int.from_bytes(frame[14:16], "little")
        if 16 + plen > len(frame):
            continue
        route = frame[16:16 + plen]
        if route and route[0] & 0x80:
            pad = route[0] & 0x7f
            if pad == 0 or pad >= len(route):
                continue
            route = route[pad:]
        if len(route) < 27 or route[0] != 0x0b:
            continue
        peer = endpoints.get(frame[6:12])
        if peer is None:
            continue
        rslen = route[26]
        if rslen % 7 or 27 + rslen > len(route):
            continue
        if all(route[pos:pos + 6] != peer
               for pos in range(27, 27 + rslen, 7)):
            return True
    return False


def contains(path: Path, needle: str) -> bool:
    try:
        return needle in path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return False


@dataclass
class Guest:
    name: str
    node: int
    peer_node: int
    peer_mac: str
    role: str
    nic_mac: str
    tap: str
    disk: Path
    log: Path
    qmp: Path
    process: subprocess.Popen[bytes] | None = None


class QmpClient:
    def __init__(self, path: Path):
        self.path = path

    def execute(self, command: str) -> None:
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and not self.path.exists():
            time.sleep(0.05)
        if not self.path.exists():
            return
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.settimeout(1.0)
                sock.connect(str(self.path))
                sock.recv(65536)
                sock.sendall(b'{"execute":"qmp_capabilities"}\r\n')
                sock.recv(65536)
                payload = ('{"execute":"' + command + '"}\r\n').encode("ascii")
                sock.sendall(payload)
        except (OSError, TimeoutError):
            return


class Lab:
    def __init__(self, base: Path, kernel: Path, initrd: Path, work: Path, mode: str, session: str):
        self.base = base.resolve()
        self.kernel = kernel.resolve()
        self.initrd = initrd.resolve()
        self.work = work
        self.mode = mode
        self.session = session
        self.host_arch = platform.machine()
        self.guests: list[Guest] = []
        self.tcpdump: subprocess.Popen[bytes] | None = None
        suffix = hashlib.sha256(session.encode("utf-8")).hexdigest()[:6]
        self.bridge = f"br{suffix}"
        self.pcap = work / "lan.pcap"

    @property
    def accel(self) -> str:
        kvm = Path("/dev/kvm")
        return "kvm" if kvm.exists() and os.access(kvm, os.R_OK | os.W_OK) else "tcg"

    def create_overlay(self, name: str) -> Path:
        target = self.work / f"{name}.qcow2"
        run("qemu-img", "create", "-q", "-f", "qcow2", "-F", "qcow2", "-b", str(self.base), str(target))
        return target

    def create_network(self, taps: list[str]) -> None:
        sudo("ip", "link", "add", self.bridge, "type", "bridge")
        sudo("ip", "link", "set", self.bridge, "up")
        for tap in taps:
            sudo("ip", "tuntap", "add", "dev", tap, "mode", "tap", "user", str(os.getuid()))
            sudo("ip", "link", "set", tap, "master", self.bridge)
            sudo("ip", "link", "set", tap, "up")
        self.tcpdump = subprocess.Popen(
            ["sudo", "tcpdump", "-U", "-i", self.bridge, "-w", str(self.pcap), "ether proto 0x6003"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if self.tcpdump.poll() is not None:
                raise RuntimeError("tcpdump exited before capture became ready")
            if self.pcap.exists() and self.pcap.stat().st_size > 0:
                return
            time.sleep(0.1)
        raise RuntimeError("packet capture did not become ready")

    def qemu_command(self, guest: Guest, area: int) -> list[str]:
        common = (
            f"root=LABEL=dniv-root rootfstype=ext4 rw dniv.smoke=1 dniv.mode={self.mode} "
            f"dniv.area={area} dniv.node={guest.node} dniv.name={guest.name} "
            f"dniv.peer={guest.peer_mac} dniv.peer_node={area}.{guest.peer_node} "
            f"dniv.role={guest.role} dniv.session={self.session}"
        )
        if self.host_arch == "x86_64":
            cmd = ["qemu-system-x86_64", "-name", guest.name, "-accel", self.accel, "-m", "512", "-smp", "1"]
            console = "console=ttyS0"
        elif self.host_arch == "aarch64":
            accel = self.accel
            cpu = "host" if accel == "kvm" else "max"
            machine = "virt,gic-version=host" if accel == "kvm" else "virt,gic-version=3"
            cmd = ["qemu-system-aarch64", "-name", guest.name, "-machine", machine, "-accel", accel,
                   "-cpu", cpu, "-m", "1024", "-smp", "1"]
            console = "earlycon=pl011,0x09000000 console=ttyAMA0"
        else:
            raise RuntimeError(f"unsupported host architecture: {self.host_arch}")
        cmd += [
            "-kernel", str(self.kernel), "-initrd", str(self.initrd), "-append", f"{common} {console}",
            "-drive", f"file={guest.disk},if=virtio,format=qcow2",
            "-netdev", f"tap,id=lan,ifname={guest.tap},script=no,downscript=no",
            "-device", f"virtio-net-pci,netdev=lan,mac={guest.nic_mac}",
            "-qmp", f"unix:{guest.qmp},server=on,wait=off",
            "-display", "none", "-monitor", "none", "-serial", f"file:{guest.log}", "-no-reboot",
        ]
        return cmd

    def start(self, guest: Guest, area: int) -> None:
        guest.process = subprocess.Popen(self.qemu_command(guest, area))
        self.guests.append(guest)

    def stop_guest(self, guest: Guest) -> None:
        proc = guest.process
        if proc is None or proc.poll() is not None:
            return
        QmpClient(guest.qmp).execute("quit")
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()

    def close(self) -> None:
        for guest in self.guests:
            self.stop_guest(guest)
        if self.tcpdump is not None and self.tcpdump.poll() is None:
            sudo("kill", str(self.tcpdump.pid), check=False)
            try:
                self.tcpdump.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.tcpdump.kill()
                self.tcpdump.wait()
        for guest in self.guests:
            sudo("ip", "link", "del", guest.tap, check=False)
        sudo("ip", "link", "del", self.bridge, check=False)


def validate_args(base: Path, kernel: Path, initrd: Path, mode: str, session: str) -> None:
    for path in (base, kernel, initrd):
        if not path.is_file():
            raise SystemExit(f"python-lab: missing {path}")
    if mode not in {"phase2", "e1"}:
        raise SystemExit(f"python-lab: invalid mode: {mode}")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", session):
        raise SystemExit("python-lab: invalid session id")
    for command in ("qemu-img", "tcpdump", "ip"):
        if shutil.which(command) is None:
            raise SystemExit(f"python-lab: missing host command: {command}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("base", type=Path)
    parser.add_argument("kernel", type=Path)
    parser.add_argument("initrd", type=Path)
    args = parser.parse_args()

    mode = os.environ.get("DNIV_LAB_MODE", "phase2")
    session = os.environ.get("DNIV_LAB_SESSION_ID", f"local-{int(time.time())}-{os.getpid()}")
    timeout = int(os.environ.get("DNIV_LAB_TIMEOUT_SECONDS", "240"))
    if timeout < 1:
        raise SystemExit("python-lab: timeout must be positive")
    validate_args(args.base, args.kernel, args.initrd, mode, session)

    env = read_env(Path(__file__).with_name("test-addresses.env"))
    area = int(env["DECNET_TEST_AREA"])
    node_a = int(env["DECNET_TEST_FIRST_NODE"])
    last_node = int(env["DECNET_TEST_LAST_NODE"])
    node_b = node_a + 1
    prefix = env["DECNET_TEST_NAME_PREFIX"]
    if not (1 <= area <= 63 and 1 <= node_a < node_b <= min(last_node, 1023)):
        raise SystemExit("python-lab: invalid DECnet test address pool")
    name_a, name_b = f"{prefix}{node_a}", f"{prefix}{node_b}"
    if not all(re.fullmatch(r"[A-Za-z0-9]{1,6}", name) for name in (name_a, name_b)):
        raise SystemExit("python-lab: generated DECnet node name is invalid")

    artifacts = Path(os.environ.get("DNIV_LAB_ARTIFACTS", "tests/lab/artifacts"))
    work = artifacts / session
    work.mkdir(parents=True, exist_ok=True)
    suffix = hashlib.sha256(session.encode("utf-8")).hexdigest()[:6]
    mac_a, mac_b = decnet_mac(area, node_a), decnet_mac(area, node_b)
    nic_a, nic_b = mac_a, mac_b
    changed_a, changed_b = nic_a, nic_b
    if mode == "e1":
        nic_a, nic_b = lab_mac(area, node_a), lab_mac(area, node_b)
        changed_a, changed_b = lab_mac(area, node_a, True), lab_mac(area, node_b, True)

    lab = Lab(args.base, args.kernel, args.initrd, work, mode, session)
    guest_a = Guest(name_a, node_a, node_b, mac_b, "A", nic_a, f"da{suffix}", lab.create_overlay("node-a"),
                    work / "node-a.serial.log", work / "node-a.qmp")
    guest_b = Guest(name_b, node_b, node_a, mac_a, "B", nic_b, f"db{suffix}", lab.create_overlay("node-b"),
                    work / "node-b.serial.log", work / "node-b.qmp")

    marker = "DNIV-E1-PASS" if mode == "e1" else "DNIV-LAB-PASS"
    pass_a = pass_b = False
    try:
        lab.create_network([guest_a.tap, guest_b.tap])
        lab.start(guest_a, area)
        lab.start(guest_b, area)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            pass_a = contains(guest_a.log, f"{marker} session={session} node={name_a}")
            pass_b = contains(guest_b.log, f"{marker} session={session} node={name_b}")
            if pass_a and pass_b:
                time.sleep(3)
                break
            if guest_a.process is not None and guest_a.process.poll() is not None and not pass_a:
                break
            if guest_b.process is not None and guest_b.process.poll() is not None and not pass_b:
                break
            time.sleep(1)
    finally:
        lab.close()

    if not (pass_a and pass_b):
        for guest in (guest_a, guest_b):
            print(f"--- {guest.name} ---", file=sys.stderr)
            if guest.log.exists():
                print("\n".join(guest.log.read_text(errors="replace").splitlines()[-160:]), file=sys.stderr)
        return 1

    frames = pcap_count(lab.pcap, "ether proto 0x6003")
    if frames < 2:
        raise SystemExit(f"python-lab: expected captured DECnet frames, saw {frames}")

    if mode == "e1":
        values = {
            "routersA": pcap_count(lab.pcap, f"ether proto 0x6003 and ether dst {ROUTERS} and ether src {mac_a}"),
            "routersB": pcap_count(lab.pcap, f"ether proto 0x6003 and ether dst {ROUTERS} and ether src {mac_b}"),
            "endnodesA": pcap_count(lab.pcap, f"ether proto 0x6003 and ether dst {ENDNODES} and ether src {mac_a}"),
            "endnodesB": pcap_count(lab.pcap, f"ether proto 0x6003 and ether dst {ENDNODES} and ether src {mac_b}"),
            "nicHelloA": pcap_count(lab.pcap, f"ether proto 0x6003 and ether src {nic_a} and (ether dst {ROUTERS} or ether dst {ENDNODES})"),
            "nicHelloB": pcap_count(lab.pcap, f"ether proto 0x6003 and ether src {nic_b} and (ether dst {ROUTERS} or ether dst {ENDNODES})"),
            "changedNicHelloA": pcap_count(lab.pcap, f"ether proto 0x6003 and ether src {changed_a} and (ether dst {ROUTERS} or ether dst {ENDNODES})"),
            "changedNicHelloB": pcap_count(lab.pcap, f"ether proto 0x6003 and ether src {changed_b} and (ether dst {ROUTERS} or ether dst {ENDNODES})"),
            "ucastAB": pcap_count(lab.pcap, f"ether proto 0x6003 and ether src {changed_a} and ether dst {mac_b}"),
            "ucastBA": pcap_count(lab.pcap, f"ether proto 0x6003 and ether src {changed_b} and ether dst {mac_a}"),
        }
        if not (values["routersA"] >= 2 and values["routersB"] >= 2 and values["endnodesA"] == 0 and
                values["endnodesB"] >= 1 and values["nicHelloA"] == 0 and values["nicHelloB"] == 0 and
                values["changedNicHelloA"] == 0 and values["changedNicHelloB"] == 0 and
                values["ucastAB"] >= 3 and values["ucastBA"] >= 3):
            raise SystemExit("python-lab: E1 wire evidence incomplete " + " ".join(f"{k}={v}" for k, v in values.items()))
        required_a = [
            f"DNIV-E1-CHANGEADDR session={session} node={name_a} mac={changed_a}",
            f"DNIV-E1-UCAST session={session} node={name_a}",
            f"DNIV-E1-EXPIRED session={session} node={name_a}",
            f"DNIV-E1-RECOVERED session={session} node={name_a}",
        ]
        required_b = [
            f"DNIV-E1-CHANGEADDR session={session} node={name_b} mac={changed_b}",
            f"DNIV-E1-UCAST session={session} node={name_b}",
            f"DNIV-E1-RECOVERED session={session} node={name_b}",
        ]
        for needle in required_a:
            if not contains(guest_a.log, needle):
                raise SystemExit(f"python-lab: missing node A evidence: {needle}")
        for needle in required_b:
            if not contains(guest_b.log, needle):
                raise SystemExit(f"python-lab: missing node B evidence: {needle}")
        init_logged = (contains(guest_a.log, f"DNIV-E1-INIT session={session}") or
                       contains(guest_b.log, f"DNIV-E1-INIT session={session}"))
        if not init_logged and not pcap_router_init_seen(lab.pcap, mac_a, mac_b):
            raise SystemExit("python-lab: E1 initial INIT state was not observed")
        if not (contains(guest_a.log, f"DNIV-E1-RESTART-INIT session={session}") or contains(guest_b.log, f"DNIV-E1-RESTART-INIT session={session}")):
            raise SystemExit("python-lab: E1 restart INIT state was not observed")
        print(f"python-lab: E1 pass on {lab.host_arch} for {area}.{node_a}/{area}.{node_b}, captured {frames} DECnet frames")
    else:
        print(f"python-lab: Phase 2 pass on {lab.host_arch} for {area}.{node_a}/{area}.{node_b}, captured {frames} DECnet routing frames")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
