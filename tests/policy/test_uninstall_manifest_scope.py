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

"""Reject edited installation manifests that target unrelated files."""

import pathlib
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
UNINSTALL = ROOT / "uninstall.sh"
HELPER = ROOT / "tools" / "manifest-member.sh"


def run(*args):
    return subprocess.run(args, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=False)


def main():
    with tempfile.TemporaryDirectory(prefix="dniv-manifest-scope-") as td:
        stage = pathlib.Path(td)
        prefix = "/usr/local"
        base = stage / "usr/local"
        manifest = base / "share/decnet-iv-linux/install-manifest.txt"
        foreign = base / "bin/unrelated-service"
        good = base / "bin/dncopy"
        foreign.parent.mkdir(parents=True)
        manifest.parent.mkdir(parents=True)
        foreign.write_text("not DECnet-owned\n")
        good.write_text("DECnet-managed\n")
        # Unpatched source silently deletes this unrelated application.
        manifest.write_text("/usr/local/bin/unrelated-service\n")
        rejected = run("env", f"DESTDIR={stage}", str(UNINSTALL))
        assert rejected.returncode != 0, rejected.stdout + rejected.stderr
        assert foreign.read_text() == "not DECnet-owned\n"
        assert manifest.is_file(), "rejected manifest was unexpectedly removed"

        # Validation must happen before removing any earlier valid member.
        manifest.write_text("/usr/local/bin/dncopy\n/usr/local/bin/unrelated-service\n")
        rejected = run("env", f"DESTDIR={stage}", str(UNINSTALL))
        assert rejected.returncode != 0, rejected.stdout + rejected.stderr
        assert good.is_file() and foreign.is_file() and manifest.is_file()

        custom = "/opt/dniv"
        other = stage / "opt/dniv/bin/foreign"
        m2 = stage / "opt/dniv/share/decnet-iv-linux/install-manifest.txt"
        other.parent.mkdir(parents=True)
        m2.parent.mkdir(parents=True)
        other.write_text("foreign\n")
        m2.write_text(custom + "/bin/foreign\n")
        rejected = run("env", f"DESTDIR={stage}", f"PREFIX={custom}", str(UNINSTALL))
        assert rejected.returncode != 0, rejected.stdout + rejected.stderr
        assert other.is_file()

        # The installer also must reject an old poisoned manifest before
        # writing its first module or application target.
        package = stage / "fixture-package"
        (package / "kernel/decnet").mkdir(parents=True)
        (package / "tools").mkdir()
        (package / "kernel/decnet/decnet_iv.ko").write_bytes(b"fixture module")
        (package / "install.sh").write_bytes((ROOT / "install.sh").read_bytes())
        (package / "tools/manifest-member.sh").write_bytes(HELPER.read_bytes())
        fakebin = stage / "fakebin"
        fakebin.mkdir()
        modinfo = fakebin / "modinfo"
        modinfo.write_text("#!/bin/sh\nprintf '6.8.0-fixture SMP\\n'\n")
        modinfo.chmod(0o755)
        manifest.write_text("/usr/local/bin/unrelated-service\n")
        rejected = run("env", f"DESTDIR={stage}",
                       f"PATH={fakebin}:/usr/bin:/bin", "bash",
                       str(package / "install.sh"))
        assert rejected.returncode != 0, rejected.stdout + rejected.stderr
        assert "unsafe existing manifest path" in rejected.stderr, rejected.stderr
        assert not (stage / "lib/modules/6.8.0-fixture/extra/decnet_iv.ko").exists()
        assert foreign.is_file()

        # A legitimate installed command, alias or source document is allowed.
        for path in ("/usr/local/bin/dncopy", "/usr/local/bin/sethost",
                     "/usr/local/sbin/dnctl",
                     "/usr/local/share/doc/decnet-iv-linux/SOURCE-METADATA"):
            assert run("bash", "-c",
                       'source "$1"; dniv_manifest_prefix_member "$2" "$3"',
                       "bash", str(HELPER), path, prefix).returncode == 0, path
        manifest.write_text("/usr/local/bin/dncopy\n")
        ok = run("env", f"DESTDIR={stage}", str(UNINSTALL))
        assert ok.returncode == 0, ok.stdout + ok.stderr
        assert not good.exists() and not manifest.exists()
        assert foreign.is_file(), "uninstall deleted unrelated file"
    print("installation manifest membership rejects foreign files before removal")


if __name__ == "__main__":
    main()
