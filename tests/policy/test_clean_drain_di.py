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
"""Exercise the actual PCAP validator's clean-disconnect proof without VM traffic."""

import importlib.util
from pathlib import Path
import unittest


class CleanDrainEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path(__file__).resolve().parents[1] / "lab" / "validate-interop-pcap.py"
        spec = importlib.util.spec_from_file_location("dniv_pcap_validator_drain", source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cls.validate = staticmethod(module.validate_clean_drain_counts)

    def test_valid_retransmission_then_disconnect(self):
        for probes, di_after in [(2, 1), (3, 2)]:
            with self.subTest(probes=probes, di_after=di_after):
                self.validate({
                    "candidate_drain_probe": probes,
                    "candidate_drain_retransmit_before_di": di_after,
                    "candidate_drain_di_before_retransmit": 0,
                })

    def test_reject_missing_di_even_with_retransmits(self):
        with self.assertRaisesRegex(ValueError, "missing.*DI"):
            self.validate({
                "candidate_drain_probe": 3,
                "candidate_drain_retransmit_before_di": 0,
                "candidate_drain_di_before_retransmit": 0,
            })

    def test_reject_di_before_retransmit(self):
        with self.assertRaisesRegex(ValueError, "preceded"):
            self.validate({
                "candidate_drain_probe": 3,
                "candidate_drain_retransmit_before_di": 1,
                "candidate_drain_di_before_retransmit": 1,
            })

    def test_reject_insufficient_retransmission(self):
        with self.assertRaisesRegex(ValueError, "retransmit"):
            self.validate({
                "candidate_drain_probe": 1,
                "candidate_drain_retransmit_before_di": 1,
                "candidate_drain_di_before_retransmit": 0,
            })


if __name__ == "__main__":
    unittest.main()
