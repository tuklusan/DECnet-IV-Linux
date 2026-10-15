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

"""Area-31 occupancy must compare numeric node identities, not printed forms."""

import importlib.util
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "lab" / "area31-parse-known.py"


def test_canonical_area31_occupancy():
    spec = importlib.util.spec_from_file_location("dniv_area31_parse_known", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    sample = (
        "Executor node = 31.0003 (PYRTR), State = On,\n"
        "31.0002 (STATIC) Reachable\n"
        "31.2 (STATIC) Reachable\n"
        "31.0031 (VAX) Reachable\n"
        "31.0004 Unreachable\n"
    )
    count, entries = module.occupied_rows(sample)
    assert count == 4, count
    assert entries == [
        ("31.2", "STATIC", "Reachable"),
        ("31.3", "PYRTR", "On"),
        ("31.31", "VAX", "Reachable"),
    ], entries
    _, occupied = module.occupied_nodes(sample)
    assert occupied == ["31.2", "31.3", "31.31"], occupied
    assert "31.2" in occupied  # Exact-string allocator comparison in prove-area31.sh.
    assert "31.31" in occupied


if __name__ == "__main__":
    test_canonical_area31_occupancy()
    print("Area-31 numeric known-node occupancy regression passed")

