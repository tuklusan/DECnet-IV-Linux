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

"""Do not let symlink resolution disguise evidence members as regular files."""

from pathlib import Path
import importlib.util
import tempfile


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "tools/evidence_guard.py"


def reject(fn):
    try:
        fn()
    except SystemExit:
        return
    raise AssertionError("evidence guard accepted a symbolic-link member")


def check():
    spec = importlib.util.spec_from_file_location("dniv_evidence_guard_under_test", MODULE)
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    with tempfile.TemporaryDirectory(prefix="dniv-evidence-links-") as tmp:
        base = Path(tmp)
        root = base / "proof"
        root.mkdir()
        (root / "actual.txt").write_text("genuine evidence\n")
        (root / "alias.txt").symlink_to("actual.txt")
        (root / "aliasdir").symlink_to(".", target_is_directory=True)
        manifest = root / "evidence.json"
        guard.manifest(root, manifest, ["actual.txt"])
        guard.verify(root, manifest)
        reject(lambda: guard.manifest(root, manifest, ["alias.txt"]))
        reject(lambda: guard.manifest(root, manifest, ["aliasdir/actual.txt"]))
        reject(lambda: guard.rooted(root, "alias.txt"))
        reject(lambda: guard.rooted(root, "aliasdir/actual.txt"))
        reject(lambda: guard.rooted(root, "../outside"))
        reject(lambda: guard.rooted(root, "/etc/passwd"))
        linked_root = base / "proof-link"
        linked_root.symlink_to(root, target_is_directory=True)
        reject(lambda: guard.manifest(linked_root, manifest, ["actual.txt"]))
        guard.manifest(root, manifest, ["actual.txt"])
        # Mutated manifest cannot launder the symlink into a valid file.
        payload = manifest.read_text().replace("actual.txt", "alias.txt")
        manifest.write_text(payload)
        reject(lambda: guard.verify(root, manifest))
        guard.manifest(root, manifest, ["actual.txt"])
        (root / "actual.txt").write_text("tampered evidence\n")
        reject(lambda: guard.verify(root, manifest))
    print("evidence symlink and containment regression passed")


if __name__ == "__main__":
    check()
