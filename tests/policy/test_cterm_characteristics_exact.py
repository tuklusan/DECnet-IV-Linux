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

"""CTERM set/read cannot pass using fake characteristic marker substrings."""

import runpy
import sys
import types
from pathlib import Path

fake_package = types.ModuleType('decnet')
fake_package.__path__ = []
fake_module = types.ModuleType('decnet.async_connectors')
fake_module.AsyncApiConnector = object
sys.modules.setdefault('decnet', fake_package)
sys.modules.setdefault('decnet.async_connectors', fake_module)
mod = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'lab/pydecnet-cterm.py'))
verify = mod['valid_characteristics_after_set']
before = bytes((11, 0, 5, 2, 1, 8, 2, 1, 0))
after = bytes((11, 0, 5, 2, 0, 8, 2, 1, 0))
forged = bytes((11, 0)) + b'junk' + after

# Actual Foundation COMMON-DATA envelope is valid, but old substring checks
# accept the forged payload even though its selectors and layout are nonsense.
record = bytes((9, 0)) + len(forged).to_bytes(2, 'little') + forged
assert mod['common_body'](record, 11) == forged
assert bytes((5, 2, 0)) in forged and bytes((8, 2, 1, 0)) in forged
assert verify(before, after)
assert not verify(before, forged)
assert not verify(before, before)
assert not verify(before, after[:-1])
assert not verify(before, after + b'extra')
assert not verify(before + bytes((5, 2, 1)), after)
print('CTERM characteristic state-change exact-oracle regression passed')
