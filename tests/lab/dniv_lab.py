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



def pcap_router_hello_count(path: Path, source_mac: str, destination_mac: str = ROUTERS) -> int:
    """Count complete router-hello frames in a live or completed PCAP."""
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return 0
    if len(data) < 24:
        return 0
    magic = data[:4]
    if magic == b"\xd4\xc3\xb2\xa1":
        endian = "<"
    elif magic == b"\xa1\xb2\xc3\xd4":
        endian = ">"
    else:
        raise RuntimeError(f"unsupported pcap magic in {path}")

    source = bytes(int(part, 16) for part in source_mac.split(":"))
    destination = bytes(int(part, 16) for part in destination_mac.split(":"))
    count = 0
    off = 24
    while off + 16 <= len(data):
        _, _, incl, _ = struct.unpack_from(endian + "IIII", data, off)
        off += 16
        if incl > len(data) - off:
            break
        frame = data[off:off + incl]
        off += incl
        if (len(frame) < 17 or frame[0:6] != destination or
                frame[6:12] != source or frame[12:14] != b"\x60\x03"):
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
        if len(route) >= 27 and route[0] == 0x0b:
            count += 1
    return count


def pcap_router_peer_unlisted_count(path: Path, source_mac: str,
                                    peer_mac: str) -> int:
    """Count All-Routers hellos from source whose router list omits peer."""
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return 0
    if len(data) < 24:
        return 0
    magic = data[:4]
    if magic == b"\xd4\xc3\xb2\xa1":
        endian = "<"
    elif magic == b"\xa1\xb2\xc3\xd4":
        endian = ">"
    else:
        raise RuntimeError(f"unsupported pcap magic in {path}")

    source = bytes(int(part, 16) for part in source_mac.split(":"))
    peer = bytes(int(part, 16) for part in peer_mac.split(":"))
    destination = bytes(int(part, 16) for part in ROUTERS.split(":"))
    count = 0
    off = 24
    while off + 16 <= len(data):
        _, _, incl, _ = struct.unpack_from(endian + "IIII", data, off)
        off += 16
        if incl > len(data) - off:
            break
        frame = data[off:off + incl]
        off += incl
        if (len(frame) < 43 or frame[0:6] != destination or
                frame[6:12] != source or frame[12:14] != b"\x60\x03"):
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
        rslen = route[26]
        if rslen % 7 or 27 + rslen > len(route):
            continue
        listed = any(route[pos:pos + 6] == peer
                     for pos in range(27, 27 + rslen, 7))
        if not listed:
            count += 1
    return count


def pcap_router_init_seen(path: Path, mac_a: str, mac_b: str) -> bool:
    """Require an unlisted router hello followed later by a reciprocal listing."""
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
    saw_unlisted: set[bytes] = set()
    off = 24
    while off + 16 <= len(data):
        _, _, incl, _ = struct.unpack_from(endian + "IIII", data, off)
        off += 16
        if incl > len(data) - off:
            return False
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

        source = frame[6:12]
        peer = endpoints.get(source)
        if peer is None:
            continue
        rslen = route[26]
        if rslen % 7 or 27 + rslen > len(route):
            continue
        listed = any(route[pos:pos + 6] == peer
                     for pos in range(27, 27 + rslen, 7))
        if listed and source in saw_unlisted:
            return True
        if not listed:
            saw_unlisted.add(source)
    return False

def contains(path: Path, needle: str) -> bool:
    try:
        return needle in path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return False


def require_guest_log_evidence(path: Path, required: list[str]) -> None:
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size <= 0:
            raise SystemExit(f"python-lab: guest serial evidence missing or empty: {path}")
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise SystemExit(f"python-lab: guest serial evidence unreadable: {path}: {exc}") from exc
    missing = [marker for marker in required if marker not in text]
    if missing:
        raise SystemExit(
            "python-lab: guest serial evidence incomplete missing=" + ",".join(missing)
        )


def validate_e1_wire_values(values: dict[str, int]) -> None:
    required = {
        "routersA", "routersB", "endnodesA", "endnodesB",
        "nicHelloA", "nicHelloB", "changedNicHelloA", "changedNicHelloB",
        "ucastAB", "ucastBA",
    }
    if set(values) != required:
        raise SystemExit(
            "python-lab: incomplete E1 wire counter set missing="
            + ",".join(sorted(required - set(values)))
            + " extra=" + ",".join(sorted(set(values) - required))
        )
    if not (
        values["routersA"] >= 2 and values["routersB"] >= 2
        and values["endnodesA"] == 0 and values["endnodesB"] >= 1
        and values["nicHelloA"] == 0 and values["nicHelloB"] == 0
        and values["changedNicHelloA"] == 0 and values["changedNicHelloB"] == 0
        and values["ucastAB"] >= 3 and values["ucastBA"] >= 3
    ):
        raise SystemExit(
            "python-lab: E1 wire evidence incomplete "
            + " ".join(f"{key}={value}" for key, value in values.items())
        )


def record_fault_event(path: Path, event: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(event + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def require_fault_event(path: Path, event: str, expected: int = 1) -> None:
    try:
        events = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        events = []
    count = sum(line == event for line in events)
    if count != expected:
        raise SystemExit(
            f"python-lab: requested fault event {event!r} count={count} expected={expected}"
        )


KCSAN_IGNORED_REPORTS = frozenset({
    "BUG: KCSAN: data-race in memchr_inv / mod_node_state",
    "BUG: KCSAN: data-race in mod_node_state / memchr_inv",
    "BUG: KCSAN: data-race in __mem_cgroup_flush_stats / tick_do_update_jiffies64",
    "BUG: KCSAN: data-race in tick_do_update_jiffies64 / __mem_cgroup_flush_stats",
    "BUG: KCSAN: data-race in tick_nohz_handler / tick_nohz_idle_got_tick",
    "BUG: KCSAN: data-race in tick_nohz_idle_got_tick / tick_nohz_handler",
    "BUG: KCSAN: data-race in __tmigr_cpu_activate / tmigr_next_groupevt",
    "BUG: KCSAN: data-race in tmigr_next_groupevt / __tmigr_cpu_activate",
    "BUG: KCSAN: data-race in tmigr_cpu_deactivate / tmigr_next_groupevt",
    "BUG: KCSAN: data-race in tmigr_next_groupevt / tmigr_cpu_deactivate",
    "BUG: KCSAN: data-race in wbt_done / wbt_issue",
    "BUG: KCSAN: data-race in wbt_issue / wbt_done",
    "BUG: KCSAN: data-race in blk_mq_dispatch_rq_list / blk_mq_dispatch_rq_list",
    "BUG: KCSAN: data-race in memchr_inv / refresh_cpu_vm_stats",
    "BUG: KCSAN: data-race in refresh_cpu_vm_stats / memchr_inv",
    "BUG: KCSAN: data-race in mem_cgroup_wb_stats / tick_do_update_jiffies64",
    "BUG: KCSAN: data-race in tick_do_update_jiffies64 / mem_cgroup_wb_stats",
})

LOCKDEBUG_FAILURE_MARKERS = (
    "BUG: spinlock",
    "bad unlock balance detected",
    "BUG: sleeping function called from invalid context",
    "scheduling while atomic",
    "DEBUG_LOCKS_WARN_ON",
    "BUG: rwlock",
    "possible circular locking dependency detected",
    "inconsistent lock state",
    "possible recursive locking detected",
    "possible irq lock inversion dependency detected",
    "BUG: MAX_LOCKDEP",
)


def kcsan_unapproved_findings(path: Path) -> list[str]:
    """Return KCSAN report summaries except exact vetted upstream kernel races."""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except FileNotFoundError:
        return []
    return [
        line.strip()
        for line in lines
        if "BUG: KCSAN:" in line and
        not any(allowed in line for allowed in KCSAN_IGNORED_REPORTS)
    ]


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

    @staticmethod
    def _wait_reply(sock: socket.socket) -> bool:
        deadline = time.monotonic() + 2.0
        data = b""
        while time.monotonic() < deadline:
            try:
                chunk = sock.recv(65536)
            except socket.timeout:
                continue
            if not chunk:
                return False
            data += chunk
            if b'"error"' in data:
                return False
            if b'"return"' in data:
                return True
        return False

    def execute(self, command: str) -> bool:
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and not self.path.exists():
            time.sleep(0.05)
        if not self.path.exists():
            return False
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.25)
                sock.connect(str(self.path))
                if not sock.recv(65536):
                    return False
                sock.sendall(b'{"execute":"qmp_capabilities"}\r\n')
                if not self._wait_reply(sock):
                    return False
                payload = ('{"execute":"' + command + '"}\r\n').encode("ascii")
                sock.sendall(payload)
                return self._wait_reply(sock)
        except (OSError, TimeoutError):
            return False


class Lab:
    def __init__(self, base: Path, kernel: Path, initrd: Path | None, work: Path, mode: str, session: str,
                 nic_model: str, vcpus: int, diagnostics: str, memory_mb: int):
        self.base = base.resolve()
        self.kernel = kernel.resolve()
        self.initrd = initrd.resolve() if initrd is not None else None
        self.work = work
        self.mode = mode
        self.session = session
        self.nic_model = nic_model
        self.vcpus = vcpus
        self.diagnostics = diagnostics
        self.memory_mb = memory_mb
        self.host_arch = platform.machine()
        self.host_cpus = sorted(os.sched_getaffinity(0))
        self.controller_cpu: int | None = None
        if (diagnostics in {"kasan", "kcsan", "lockdebug", "kmemleak"} and
                self.host_arch == "aarch64" and self.accel == "tcg"):
            if not self.host_cpus:
                raise RuntimeError("arm64 diagnostic TCG has no schedulable host CPU")
            # The guest masks below already reserve the first host CPU. Pin the
            # controller there as well so QMP and the packet-capture child
            # inherit a CPU that the instrumented TCG guests cannot consume.
            # Merely excluding this CPU from QEMU does not stop Linux from
            # migrating the controller onto a saturated guest CPU.
            self.controller_cpu = self.host_cpus[0]
            os.sched_setaffinity(0, {self.controller_cpu})
        self.guests: list[Guest] = []
        self.tcpdump: subprocess.Popen[bytes] | None = None
        suffix = hashlib.sha256(session.encode("utf-8")).hexdigest()[:6]
        self.bridge = f"br{suffix}"
        self.pcap = work / "lan.pcap"

    @property
    def accel(self) -> str:
        kvm = Path("/dev/kvm")
        return "kvm" if kvm.exists() and os.access(kvm, os.R_OK | os.W_OK) else "tcg"

    def require_capture_running(self) -> None:
        if self.tcpdump is None or self.tcpdump.poll() is not None:
            raise RuntimeError("python-lab: packet capture exited during active lab")

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
        root_device = "LABEL=dniv-root" if self.initrd is not None else "/dev/vda"
        common = (
            f"root={root_device} rootfstype=ext4 rw dniv.smoke=1 dniv.mode={self.mode} "
            f"dniv.area={area} dniv.node={guest.node} dniv.name={guest.name} "
            f"dniv.peer={guest.peer_mac} dniv.peer_node={area}.{guest.peer_node} "
            f"dniv.role={guest.role} dniv.session={self.session}"
        )
        if self.diagnostics == "kfence":
            common += " dniv.diag=kfence kfence.sample_interval=100 panic_on_warn=1 oops=panic"
        elif self.diagnostics == "ubsan":
            common += " dniv.diag=ubsan panic_on_warn=1 oops=panic"
        elif self.diagnostics == "kcsan":
            # Keep KCSAN running so the host can reject candidate findings while
            # allowing only the exact vetted upstream races.
            common += " dniv.diag=kcsan kcsan.skip_watch=1000 panic_on_warn=0 oops=panic net.ifnames=0"
            if self.host_arch == "aarch64":
                common += " net.ifnames=0 init=/usr/local/sbin/dniv-smoke"
        elif self.diagnostics == "lockdebug":
            common += " dniv.diag=lockdebug panic_on_warn=1 oops=panic"
            if self.host_arch == "aarch64":
                common += " net.ifnames=0 init=/usr/local/sbin/dniv-smoke"
        elif self.diagnostics == "kmemleak":
            common += " dniv.diag=kmemleak kmemleak=on panic_on_warn=1 oops=panic"
            if self.host_arch == "aarch64":
                common += " net.ifnames=0 init=/usr/local/sbin/dniv-smoke"
        elif self.diagnostics == "kasan":
            common += " dniv.diag=kasan panic_on_warn=1 oops=panic net.ifnames=0 systemd.mask=systemd-udev-trigger.service"
            if self.host_arch == "aarch64":
                common += " init=/usr/local/sbin/dniv-smoke"
        if self.host_arch == "x86_64":
            cmd = ["qemu-system-x86_64", "-name", guest.name, "-accel", self.accel,
                   "-m", str(self.memory_mb), "-smp", str(self.vcpus)]
            console = "console=ttyS0"
        elif self.host_arch == "aarch64":
            accel = self.accel
            cpu = "host" if accel == "kvm" else "max"
            machine = "virt,gic-version=host" if accel == "kvm" else "virt,gic-version=3"
            cmd = ["qemu-system-aarch64", "-name", guest.name, "-machine", machine, "-accel", accel,
                   "-cpu", cpu, "-m", str(self.memory_mb), "-smp", str(self.vcpus)]
            console = "earlycon=pl011,0x09000000 console=ttyAMA0"
        else:
            raise RuntimeError(f"unsupported host architecture: {self.host_arch}")

        if self.diagnostics in {"kasan", "kcsan", "lockdebug", "kmemleak"} and self.host_arch == "aarch64" and self.accel == "tcg":
            host_cpus = self.host_cpus
            # Keep one schedulable CPU out of both TCG process masks so the
            # host controller, QMP and capture path cannot be starved behind
            # two heavy diagnostic guests.  On a four-CPU runner the two 2-vCPU guest
            # masks intentionally overlap one CPU; guest SMP coverage remains
            # intact while CPU 0 stays available to host orchestration.
            guest_cpus = host_cpus[1:]
            if len(guest_cpus) >= 2 * self.vcpus:
                affinity = (
                    guest_cpus[:self.vcpus]
                    if guest.role == "A"
                    else guest_cpus[self.vcpus:2 * self.vcpus]
                )
            elif len(guest_cpus) >= self.vcpus + 1:
                affinity = (
                    guest_cpus[:self.vcpus]
                    if guest.role == "A"
                    else guest_cpus[-self.vcpus:]
                )
            else:
                raise RuntimeError(
                    "arm64 diagnostic TCG requires one reserved host CPU plus "
                    f"two {self.vcpus}-vCPU guest affinity sets, available={host_cpus}"
                )
            if shutil.which("taskset") is None:
                raise RuntimeError("arm64 diagnostic TCG requires taskset")
            cpu_list = ",".join(str(cpu) for cpu in affinity)
            cmd = ["taskset", "--cpu-list", cpu_list, *cmd]

        cmd += ["-kernel", str(self.kernel)]
        if self.initrd is not None:
            cmd += ["-initrd", str(self.initrd)]
        cmd += [
            "-append", f"{common} {console}",
            "-drive", f"file={guest.disk},if=virtio,format=qcow2",
            "-netdev", f"tap,id=lan,ifname={guest.tap},script=no,downscript=no",
            "-device", f"{self.nic_model},netdev=lan,mac={guest.nic_mac}",
            "-qmp", f"unix:{guest.qmp},server=on,wait=off",
            "-display", "none", "-monitor", "none", "-serial", f"file:{guest.log}",
        ]
        if self.mode != "pp11s1":
            cmd.append("-no-reboot")
        return cmd

    def start(self, guest: Guest, area: int) -> None:
        guest.process = subprocess.Popen(self.qemu_command(guest, area))
        self.guests.append(guest)

    @staticmethod
    def pause_guest(guest: Guest) -> None:
        if guest.process is not None and guest.process.poll() is None:
            if not QmpClient(guest.qmp).execute("stop"):
                raise RuntimeError(f"QMP stop failed for {guest.name}")

    @staticmethod
    def resume_guest(guest: Guest) -> None:
        if guest.process is not None and guest.process.poll() is None:
            if not QmpClient(guest.qmp).execute("cont"):
                raise RuntimeError(f"QMP cont failed for {guest.name}")

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


def validate_args(base: Path, kernel: Path, initrd: Path | None, mode: str, session: str) -> None:
    for path in (base, kernel):
        if not path.is_file():
            raise SystemExit(f"python-lab: missing {path}")
    if initrd is not None and not initrd.is_file():
        raise SystemExit(f"python-lab: missing {initrd}")
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
    parser.add_argument("initrd")
    args = parser.parse_args()
    initrd = None if args.initrd == "-" else Path(args.initrd)

    mode = os.environ.get("DNIV_LAB_MODE", "phase2")
    session = os.environ.get("DNIV_LAB_SESSION_ID", f"local-{int(time.time())}-{os.getpid()}")
    timeout = int(os.environ.get("DNIV_LAB_TIMEOUT_SECONDS", "240"))
    nic_model = os.environ.get("DNIV_LAB_NIC_MODEL", "virtio-net-pci")
    vcpus = int(os.environ.get("DNIV_LAB_VCPUS", "1"))
    diagnostics = os.environ.get("DNIV_LAB_DIAGNOSTICS", "none")
    default_memory = "1024" if platform.machine() == "aarch64" else "512"
    memory_mb = int(os.environ.get("DNIV_LAB_MEMORY_MB", default_memory))
    if timeout < 1:
        raise SystemExit("python-lab: timeout must be positive")
    if nic_model not in {"virtio-net-pci", "e1000"}:
        raise SystemExit(f"python-lab: unsupported NIC model: {nic_model}")
    if vcpus not in {1, 2, 4, 8}:
        raise SystemExit(f"python-lab: unsupported vCPU count: {vcpus}")
    if diagnostics not in {"none", "kfence", "ubsan", "kasan", "kcsan", "lockdebug", "kmemleak"}:
        raise SystemExit(f"python-lab: unsupported diagnostics mode: {diagnostics}")
    if not 256 <= memory_mb <= 4096:
        raise SystemExit(f"python-lab: unsupported guest memory size: {memory_mb}")
    validate_args(args.base, args.kernel, initrd, mode, session)

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

    lab = Lab(args.base, args.kernel, initrd, work, mode, session, nic_model, vcpus, diagnostics, memory_mb)
    guest_a = Guest(name_a, node_a, node_b, mac_b, "A", nic_a, f"da{suffix}", lab.create_overlay("node-a"),
                    work / "node-a.serial.log", work / "node-a.qmp")
    guest_b = Guest(name_b, node_b, node_a, mac_a, "B", nic_b, f"db{suffix}", lab.create_overlay("node-b"),
                    work / "node-b.serial.log", work / "node-b.qmp")

    marker = "DNIV-E1-PASS" if mode == "e1" else "DNIV-LAB-PASS"
    pass_a = pass_b = False
    diagnostic_fault = (
        mode == "e1" and diagnostics in {"kasan", "kcsan", "lockdebug", "kmemleak"} and
        lab.host_arch == "aarch64" and lab.accel == "tcg"
    )
    startup_a_paused = False
    startup_released = not diagnostic_fault
    fault_started = False
    fault_a_paused = False
    fault_b_paused = False
    fault_b_restored = False
    fault_restored = False
    unlisted_a_before = 0
    routers_b_before = 0
    try:
        lab.create_network([guest_a.tap, guest_b.tap])
        lab.start(guest_a, area)
        lab.start(guest_b, area)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            lab.require_capture_running()
            pass_a = contains(guest_a.log, f"{marker} session={session} node={name_a}")
            pass_b = contains(guest_b.log, f"{marker} session={session} node={name_b}")

            if diagnostic_fault and not startup_released:
                quiesced_a = contains(
                    guest_a.log,
                    f"DNIV-E1-BOOTSTRAP-QUIESCED session={session} node={name_a}",
                )
                if quiesced_a and not startup_a_paused:
                    # Keep DN70 unloaded and its virtual clock stopped while
                    # DN71 completes the deliberately expensive diagnostic
                    # module reload. Cross-guest sleeps cannot order this
                    # lifecycle under two instrumented TCG guests.
                    lab.pause_guest(guest_a)
                    startup_a_paused = True

                reload_done_b = contains(
                    guest_b.log,
                    f"DNIV-E1-DIAG-RELOAD-DONE session={session} node={name_b}",
                )
                if startup_a_paused and reload_done_b:
                    lab.resume_guest(guest_a)
                    startup_a_paused = False
                    startup_released = True

            if diagnostic_fault and not fault_started:
                ready_b = contains(
                    guest_b.log,
                    f"DNIV-E1-HOST-SILENCE-READY session={session} node={name_b}",
                )
                initial_a = contains(
                    guest_a.log,
                    f"DNIV-E1-INITIAL session={session} node={name_a}",
                )
                if ready_b and initial_a:
                    unlisted_a_before = pcap_router_peer_unlisted_count(
                        lab.pcap, mac_a, mac_b
                    )
                    routers_b_before = pcap_count(
                        lab.pcap,
                        f"ether proto 0x6003 and ether dst {ROUTERS} and ether src {mac_b}",
                    )
                    # Run DN70 alone while it ages DN71 out. Under arm64
                    # instrumented TCG, leaving both guests runnable can starve the
                    # host controller past DN70's local DR-delay boundary.
                    lab.pause_guest(guest_b)
                    fault_b_paused = True
                    sudo("ip", "link", "set", guest_b.tap, "down")
                    record_fault_event(work / "fault-events.log", "host-silence-link-down")
                    fault_started = True

            if diagnostic_fault and fault_started and not fault_a_paused:
                unlisted_a_now = pcap_router_peer_unlisted_count(
                    lab.pcap, mac_a, mac_b
                )
                # A fresh All-Routers hello that no longer lists DN71 is direct
                # wire proof that DN70's listener expired. Freeze DN70 on that
                # semantic transition instead of counting elapsed hellos; this
                # leaves the full DR-delay interval before an All-Endnodes hello.
                if unlisted_a_now > unlisted_a_before:
                    lab.pause_guest(guest_a)
                    fault_a_paused = True
                    # Let isolated DN71 run alone so it can independently
                    # prove expiry of DN70 before the higher-address router is
                    # restored to the wire.
                    if fault_b_paused:
                        lab.resume_guest(guest_b)
                        fault_b_paused = False

            if diagnostic_fault and fault_a_paused and not fault_b_restored:
                expired_b = contains(
                    guest_b.log,
                    f"DNIV-E1-HOST-SILENCE-EXPIRED session={session} node={name_b}",
                )
                if expired_b:
                    sudo("ip", "link", "set", guest_b.tap, "up")
                    record_fault_event(work / "fault-events.log", "host-silence-link-up")
                    fault_b_restored = True

            if diagnostic_fault and fault_b_restored and not fault_restored:
                routers_b_now = pcap_count(
                    lab.pcap,
                    f"ether proto 0x6003 and ether dst {ROUTERS} and ether src {mac_b}",
                )
                if routers_b_now > routers_b_before:
                    lab.resume_guest(guest_a)
                    fault_restored = True

            if pass_a and pass_b:
                time.sleep(3)
                lab.require_capture_running()
                break
            if guest_a.process is not None and guest_a.process.poll() is not None and not pass_a:
                break
            if guest_b.process is not None and guest_b.process.poll() is not None and not pass_b:
                break
            time.sleep(0.1 if diagnostic_fault else 1)
    finally:
        if startup_a_paused:
            lab.resume_guest(guest_a)
        if fault_b_paused:
            lab.resume_guest(guest_b)
        if fault_a_paused and not fault_restored:
            lab.resume_guest(guest_a)
        lab.close()

    if not (pass_a and pass_b):
        for guest in (guest_a, guest_b):
            print(f"--- {guest.name} ---", file=sys.stderr)
            if guest.log.exists():
                print("\n".join(guest.log.read_text(errors="replace").splitlines()[-160:]), file=sys.stderr)
        return 1

    if diagnostics == "kfence":
        for guest in (guest_a, guest_b):
            if not contains(guest.log, f"DNIV-DIAG-KFENCE session={session}"):
                raise SystemExit(f"python-lab: missing KFENCE runtime marker from {guest.name}")
    elif diagnostics == "ubsan":
        for guest in (guest_a, guest_b):
            if not contains(guest.log, f"DNIV-DIAG-UBSAN session={session}"):
                raise SystemExit(f"python-lab: missing UBSAN runtime marker from {guest.name}")
            if contains(guest.log, "UBSAN:") or contains(guest.log, "runtime error:"):
                raise SystemExit(f"python-lab: UBSAN finding reported by {guest.name}")
    elif diagnostics == "kasan":
        for guest in (guest_a, guest_b):
            if not contains(guest.log, f"DNIV-DIAG-KASAN session={session}"):
                raise SystemExit(f"python-lab: missing KASAN runtime marker from {guest.name}")
            if contains(guest.log, "BUG: KASAN:"):
                raise SystemExit(f"python-lab: KASAN finding reported by {guest.name}")
    elif diagnostics == "kcsan":
        for guest in (guest_a, guest_b):
            if not contains(guest.log, f"DNIV-DIAG-KCSAN session={session}"):
                raise SystemExit(f"python-lab: missing KCSAN runtime marker from {guest.name}")
            findings = kcsan_unapproved_findings(guest.log)
            if findings:
                raise SystemExit(
                    f"python-lab: KCSAN finding reported by {guest.name}: {findings[0]}"
                )
            if any(contains(guest.log, allowed) for allowed in KCSAN_IGNORED_REPORTS):
                print(
                    f"python-lab: ignored vetted upstream KCSAN race from {guest.name}"
                )
    elif diagnostics == "lockdebug":
        for guest in (guest_a, guest_b):
            if not contains(guest.log, f"DNIV-DIAG-LOCKDEBUG session={session}"):
                raise SystemExit(f"python-lab: missing lockdebug runtime marker from {guest.name}")
            if not contains(guest.log, f"DNIV-DIAG-LOCKDEBUG-FINAL session={session}"):
                raise SystemExit(f"python-lab: lockdebug disabled before completion on {guest.name}")
            for finding in LOCKDEBUG_FAILURE_MARKERS:
                if contains(guest.log, finding):
                    raise SystemExit(
                        f"python-lab: lockdebug finding reported by {guest.name}: {finding}"
                    )
    elif diagnostics == "kmemleak":
        for guest in (guest_a, guest_b):
            if not contains(guest.log, f"DNIV-DIAG-KMEMLEAK session={session}"):
                raise SystemExit(f"python-lab: missing kmemleak runtime marker from {guest.name}")
            if not contains(guest.log, f"DNIV-DIAG-KMEMLEAK-FINAL session={session}"):
                raise SystemExit(f"python-lab: kmemleak final scan missing from {guest.name}")
            if contains(guest.log, "DNIV-DIAG-KMEMLEAK-REPORT-BEGIN"):
                raise SystemExit(f"python-lab: kmemleak finding reported by {guest.name}")

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
        validate_e1_wire_values(values)
        required_a = [
            f"{marker} session={session} node={name_a}",
            f"DNIV-E1-CHANGEADDR session={session} node={name_a} mac={changed_a}",
            f"DNIV-E1-UCAST session={session} node={name_a}",
            f"DNIV-E1-EXPIRED session={session} node={name_a}",
            f"DNIV-E1-RECOVERED session={session} node={name_a}",
        ]
        required_b = [
            f"{marker} session={session} node={name_b}",
            f"DNIV-E1-CHANGEADDR session={session} node={name_b} mac={changed_b}",
            f"DNIV-E1-UCAST session={session} node={name_b}",
            f"DNIV-E1-RECOVERED session={session} node={name_b}",
        ]
        require_guest_log_evidence(guest_a.log, required_a)
        require_guest_log_evidence(guest_b.log, required_b)
        init_logged = (contains(guest_a.log, f"DNIV-E1-INIT session={session}") or
                       contains(guest_b.log, f"DNIV-E1-INIT session={session}"))
        if not init_logged and not pcap_router_init_seen(lab.pcap, mac_a, mac_b):
            raise SystemExit("python-lab: E1 initial INIT state was not observed")
        if diagnostic_fault:
            if not contains(guest_b.log, f"DNIV-E1-DIAG-RELOAD session={session}"):
                raise SystemExit("python-lab: diagnostic direct-init module reload was not observed")
            require_fault_event(work / "fault-events.log", "host-silence-link-down")
            require_fault_event(work / "fault-events.log", "host-silence-link-up")
        elif not (contains(guest_a.log, f"DNIV-E1-RESTART-INIT session={session}") or
                  contains(guest_b.log, f"DNIV-E1-RESTART-INIT session={session}")):
            raise SystemExit("python-lab: E1 restart INIT state was not observed")
        print(f"python-lab: E1 pass on {lab.host_arch} nic={lab.nic_model} vcpus={lab.vcpus} diagnostics={lab.diagnostics} "
              f"for {area}.{node_a}/{area}.{node_b}, captured {frames} DECnet frames")
    else:
        print(f"python-lab: Phase 2 pass on {lab.host_arch} nic={lab.nic_model} vcpus={lab.vcpus} "
              f"for {area}.{node_a}/{area}.{node_b}, captured {frames} DECnet routing frames")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
