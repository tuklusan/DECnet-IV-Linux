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

"""PP-11 S2 evidence must fail closed, and all raw sockets must close."""

import argparse
import importlib.util
from pathlib import Path
import tempfile
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tests/lab/inject-pp11-s2.py"
EVENTS = 10000
DURATION = 3600.0


class FakeSocket:
    def __init__(self, *, bind_fails=False, send_fails=False):
        self.closed = False
        self.bind_fails = bind_fails
        self.send_fails = send_fails
        self.calls = 0

    def bind(self, _address):
        if self.bind_fails:
            raise OSError("simulated AF_PACKET bind failure")

    def send(self, frame):
        self.calls += 1
        if self.send_fails:
            raise OSError("simulated AF_PACKET send failure")
        return len(frame)

    def close(self):
        self.closed = True


def exercise(*, actual_duration, fail_bind=False, fail_send=False):
    spec = importlib.util.spec_from_file_location("pp11_s2_under_test", SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sockets = []

    def socket_factory(*_args):
        sock = FakeSocket(bind_fails=fail_bind and len(sockets) == 1,
                          send_fails=fail_send and not sockets)
        sockets.append(sock)
        return sock

    calls = 0

    def monotonic():
        nonlocal calls
        calls += 1
        if calls == 1:
            return 0.0
        if calls <= EVENTS + 1:
            return ((calls - 1) * DURATION / EVENTS) + 0.001
        return actual_duration

    with tempfile.TemporaryDirectory(prefix="dniv-pp11-s2-") as tmp:
        evidence = Path(tmp) / "result.log"
        args = argparse.Namespace(interface=["test0", "test1"],
                                  destination="02:00:00:00:00:01",
                                  events=EVENTS, duration=DURATION,
                                  evidence=evidence)
        with mock.patch.object(module.argparse.ArgumentParser, "parse_args", return_value=args), \
             mock.patch.object(module.socket, "socket", side_effect=socket_factory), \
             mock.patch.object(module.time, "monotonic", side_effect=monotonic), \
             mock.patch.object(module.time, "sleep", side_effect=AssertionError("unexpected sleep")):
            try:
                code = module.main()
            except (OSError, RuntimeError) as exc:
                outcome = exc
            else:
                outcome = code
        transcript = evidence.read_text() if evidence.exists() else ""
    assert sockets and all(sock.closed for sock in sockets), "raw socket leak"
    return outcome, transcript, sockets


def check():
    result, log, sockets = exercise(actual_duration=3600.001)
    assert result == 0 and "RESULT=PASS\n" in log
    assert sum(sock.calls for sock in sockets) == EVENTS

    result, log, _ = exercise(actual_duration=3599.999)
    assert isinstance(result, RuntimeError), result
    assert "RESULT=FAIL\n" in log, log[-200:]
    assert "RESULT=PASS" not in log

    result, log, _ = exercise(actual_duration=3600.001, fail_send=True)
    assert isinstance(result, OSError), result
    assert "RESULT=PASS" not in log

    result, log, _ = exercise(actual_duration=3600.001, fail_bind=True)
    assert isinstance(result, OSError), result
    assert not log
    print("PP-11 S2 envelope/evidence and socket cleanup regression passed")


if __name__ == "__main__":
    check()
