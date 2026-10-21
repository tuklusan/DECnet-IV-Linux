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

"""Compile actual Area-31 and inbound lab address/timeout parsers without DECnet I/O."""

from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
for source_path, function, end_marker in (
    ("tests/lab/area31-native.c", "parse_node", "\nstatic void nice_dump_frame("),
    ("tests/lab/dnaccept.c", "parse_node", "\nstatic int make_listener("),
    ("tests/lab/dnackrange.c", "parse_node", "\nint main("),
    ("tests/lab/dnadjwait.c", "parse_address", "\nstatic int monotonic_ms("),
    ("tests/lab/dnbacklog.c", "parse_node", "\nstatic int make_listener("),
    ("tests/lab/dnccretry.c", "parse_node", "\nstatic int peer_is("),
    ("tests/lab/dnconnectloss.c", "parse_node", "\nstatic void fill_peer("),
    ("tests/lab/dndiexhaust.c", "parse_node", "\nstatic void fill_peer("),
    ("tests/lab/dndiloss.c", "parse_node", "\nstatic void fill_peer("),
    ("tests/lab/dndrain.c", "parse_node", "\nint main("),
    ("tests/lab/dnexhaust.c", "parse_node", "\nint main("),
    ("tests/lab/dnfair.c", "parse_node", "\nstatic void fill_peer("),
    ("tests/lab/dnflow.c", "parse_node", "\nstatic int send_record("),
    ("tests/lab/dnintflow.c", "parse_node", "\nstatic int send_oob("),
    ("tests/lab/dnintloss.c", "parse_node", "\nint main("),
    ("tests/lab/dnkeepalive.c", "parse_node", "\nint main("),
    ("tests/lab/dnloss.c", "parse_node", "\nint main("),
):
    source = (root / source_path).read_text()
    start = source.index("static int " + function + "(")
    end = source.index(end_marker, start)
    parser = source[start:end]
    driver = """
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <errno.h>
#include <string.h>
typedef uint16_t __u16;
#define DNIV_ADDR(area, node) (((area) << 10U) | (node))
""" + parser + """
int main(int argc, char **argv) {
    uint16_t address = 0;
    int rc;
    if (argc != 3)
        return 3;
    rc = """ + function + """(argv[1], &address);
    if (argv[2][0] == 'V')
        return rc == 0 && address == ((31U << 10) | 70U) ? 0 : 1;
    return rc != 0 ? 0 : 1;
}
"""
    with tempfile.TemporaryDirectory() as tmp:
        cfile = Path(tmp) / "probe.c"
        binary = Path(tmp) / "probe"
        cfile.write_text(driver)
        subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                        str(cfile), "-o", str(binary)], check=True)
        for valid in ("31.70", "031.00070"):
            subprocess.run([str(binary), valid, "V"], check=True)
        for invalid in (
            "-18446744073709551615.1", "1.-18446744073709551615",
            "+31.70", "31.+70", " 31.70", "31. 70",
            "0.70", "64.70", "31.0", "31.1024",
            "18446744073709551617.70", "31.18446744073709551617",
            "31.70junk",
        ):
            subprocess.run([str(binary), invalid, "X"], check=True)
    print("Area31 and lab strict decimal identity passed")

# Compile the actual timeout-validation branch from dnadjwait, not a replica.
source = (root / "tests/lab/dnadjwait.c").read_text()
start = source.index("    errno = 0;\n    timeout_ms = strtoul(argv[3], &end, 10);")
end = source.index("\n    fd = open(", start)
timeout_block = source[start:end]
probe = """
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
int main(int argc, char **argv) {
    unsigned long timeout_ms;
    char *end;
    if (argc != 4)
        return 3;
""" + timeout_block + """
    return 0;
}
"""
with tempfile.TemporaryDirectory() as tmp:
    cfile = Path(tmp) / "timeout.c"
    binary = Path(tmp) / "timeout"
    cfile.write_text(probe)
    subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                    str(cfile), "-o", str(binary)], check=True)
    for valid_timeout in ("1", "600000", "00010"):
        subprocess.run([str(binary), "up", "31.70", valid_timeout], check=True)
    for invalid_timeout in ("-18446744073709551615", "+1", " 1",
                            "0", "600001", "999999999999999999999999999",
                            "1xyz", ""):
        outcome = subprocess.run([str(binary), "up", "31.70", invalid_timeout],
                                 capture_output=True, check=False)
        if outcome.returncode != 2:
            raise AssertionError(f"invalid timeout {invalid_timeout!r} accepted")
print("dnadjwait source timeout validation passed")

# Extract the actual negative-test ITERATIONS parser from dnhostile.
source = (root / "tests/lab/dnhostile.c").read_text()
start = source.index("        errno = 0;\n        iterations = strtoul(argv[1], &end, 10);")
end = source.index("\n    } else if (argc != 1)", start)
iteration_block = source[start:end]
probe = """
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
int main(int argc, char **argv) {
    unsigned long iterations = 4096U;
    char *end = NULL;
    if (argc != 2)
        return 3;
""" + iteration_block + """
    return 0;
}
"""
with tempfile.TemporaryDirectory() as tmp:
    cfile = Path(tmp) / "iterations.c"
    binary = Path(tmp) / "iterations"
    cfile.write_text(probe)
    subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                    str(cfile), "-o", str(binary)], check=True)
    for count in ("256", "100000", "0004096"):
        subprocess.run([str(binary), count], check=True)
    for count in ("-18446744073709551360", "+256", " 256", "255",
                  "100001", "999999999999999999999", "256bad", ""):
        result = subprocess.run([str(binary), count], capture_output=True,
                                check=False)
        if result.returncode != 2:
            raise AssertionError(f"invalid hostile iterations {count!r} accepted")
print("hostile iterations strict decimal source validation passed")
