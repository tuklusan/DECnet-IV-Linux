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

"""Prevent false-positive HTTP acceptance of substring-carrying garbage."""

import ast
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
source = ROOT / "tests/lab/pydecnet-http.py"
raw = source.read_text()
assert "if not valid_http_response(raw):" in raw
assert 'if b"HTTP/1.0 200 OK\\r\\n" not in raw' not in raw
node = next(
    (n for n in ast.parse(raw).body
     if isinstance(n, ast.FunctionDef) and n.name == "valid_http_response"),
    None,
)
assert node is not None
scope = {}
exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"),
     scope)
valid = scope["valid_http_response"]

body = b"DECNET-WEB-PASS\n"
head = (b"HTTP/1.0 200 OK\r\nContent-Length: 16\r\n"
        b"Content-Type: text/html\r\nConnection: close\r\n\r\n")
golden = head + body
valid_cases = (
    golden,
    b"HTTP/1.0 200 OK\r\nConnection: close\r\n"
    b"Content-Type: text/html\r\nContent-Length: 16\r\n\r\n" + body,
)
bad_cases = (
    b"GARBAGE" + golden,
    golden + b"TRAILING-GARBAGE",
    golden.replace(b"Length: 16", b"Length: 2"),
    golden.replace(b"\r\n\r\n", b"\r\n"),
    golden.replace(b"200 OK", b"404 Not Found"),
    golden.replace(b"Content-Length: 16", b"Content-Length: 17"),
    golden.replace(b"Content-Type: text/html", b"X-Fake: text/html"),
    golden.replace(b"\r\nContent-Length: 16",
                   b"\r\nContent-Length: 16\r\nContent-Length: 16"),
    b"HTTP/1.0 200 OK\r\n" + body,
)
assert all(valid(c) for c in valid_cases)
assert all(not valid(c) for c in bad_cases)
subprocess.run(["python3", "-m", "py_compile", str(source)], check=True)
print("PyDECnet HTTP response framing/content regression passed")
