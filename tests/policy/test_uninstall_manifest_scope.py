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

        # NUL bytes cannot turn an invalid line into an owned pathname.
        # Bash mapfile otherwise truncates at the first NUL.
        ncp = base / "bin/ncp"
        ncp.write_text("foreign-ncp-must-survive\n")
        manifest.write_bytes(b"/usr/local/bin/ncp\x00unowned\n")
        rejected = run("env", f"DESTDIR={stage}", str(UNINSTALL))
        assert rejected.returncode != 0, rejected.stdout + rejected.stderr
        assert ncp.read_text() == "foreign-ncp-must-survive\n"
        assert manifest.is_file()

        # Incomplete final manifest line is malformed, even for an allowed name.
        manifest.write_bytes(b"/usr/local/bin/ncp")
        rejected = run("env", f"DESTDIR={stage}", str(UNINSTALL))
        assert rejected.returncode != 0, rejected.stdout + rejected.stderr
        assert ncp.is_file() and manifest.is_file()

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

        # Installer must reject the raw NUL-bearing manifest before writes.
        manifest.write_bytes(b"/usr/local/bin/ncp\x00unowned\n")
        rejected = run("env", f"DESTDIR={stage}",
                       f"PATH={fakebin}:/usr/bin:/bin", "bash",
                       str(package / "install.sh"))
        assert rejected.returncode != 0, rejected.stdout + rejected.stderr
        assert "unsafe existing manifest bytes" in rejected.stderr, rejected.stderr
        assert not (stage / "lib/modules/6.8.0-fixture/extra/decnet_iv.ko").exists()
        assert ncp.read_text() == "foreign-ncp-must-survive\n"

        # A failed first install must not promise ownership of an artifact
        # that was never installed: it might later belong to another writer.
        # Stub only install(1); the real packaged install/uninstall scripts run.
        failing_install = fakebin / "install"
        failing_install.write_text("#!/bin/sh\nexit 42\n")
        failing_install.chmod(0o755)
        manifest.write_text("")
        module_member = "/lib/modules/6.8.0-fixture/extra/decnet_iv.ko"
        module_file = stage / module_member.lstrip("/")
        module_file.parent.mkdir(parents=True, exist_ok=True)
        assert not module_file.exists()
        failed = run("env", f"DESTDIR={stage}",
                     "MODULE_ROOT=/lib/modules/6.8.0-fixture",
                     f"PATH={fakebin}:/usr/bin:/bin", "bash",
                     str(package / "install.sh"))
        assert failed.returncode == 42, failed.stdout + failed.stderr
        assert not module_file.exists()
        assert module_member not in manifest.read_text(), (
            "incomplete install falsely claimed ownership of module")
        module_file.write_text("FOREIGN-WRITER-KEEPS-THIS\n")
        clean = run("env", f"DESTDIR={stage}",
                    "MODULE_ROOT=/lib/modules/6.8.0-fixture",
                    "KERNEL_RELEASE=6.8.0-fixture", str(UNINSTALL))
        assert clean.returncode == 0, clean.stdout + clean.stderr
        assert module_file.read_text() == "FOREIGN-WRITER-KEEPS-THIS\n", (
            "uninstall removed a foreign file after failed install")

        # A completed file installation must still be recorded, even if a
        # later component fails: the uninstaller owns ONLY the completed one.
        module_file.unlink()  # remove the synthetic foreign test fixture
        manifest.parent.mkdir(parents=True, exist_ok=True)
        failing_install.write_text('#!/bin/sh\nexec /usr/bin/install "$@"\n')
        installed = run("env", f"DESTDIR={stage}",
                        "MODULE_ROOT=/lib/modules/6.8.0-fixture",
                        f"PATH={fakebin}:/usr/bin:/bin", "bash",
                        str(package / "install.sh"))
        assert installed.returncode != 0, installed.stdout + installed.stderr
        assert "missing built artifact" in installed.stderr, installed.stderr
        assert module_file.read_bytes() == b"fixture module"
        assert manifest.read_text() == module_member + "\n"
        cleanup = run("env", f"DESTDIR={stage}",
                      "MODULE_ROOT=/lib/modules/6.8.0-fixture",
                      "KERNEL_RELEASE=6.8.0-fixture", str(UNINSTALL))
        assert cleanup.returncode == 0, cleanup.stdout + cleanup.stderr
        assert not module_file.exists() and not manifest.exists()

        # A legitimate installed command, alias or source document is allowed.
        for path in ("/usr/local/bin/dncopy", "/usr/local/bin/sethost",
                     "/usr/local/sbin/dnctl",
                     "/usr/local/share/doc/decnet-iv-linux/SOURCE-METADATA"):
            assert run("bash", "-c",
                       'source "$1"; dniv_manifest_prefix_member "$2" "$3"',
                       "bash", str(HELPER), path, prefix).returncode == 0, path
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text("/usr/local/bin/dncopy\n")
        ok = run("env", f"DESTDIR={stage}", str(UNINSTALL))
        assert ok.returncode == 0, ok.stdout + ok.stderr
        assert not good.exists() and not manifest.exists()
        assert foreign.is_file(), "uninstall deleted unrelated file"
    print("installation manifest membership rejects foreign files before removal")


if __name__ == "__main__":
    main()
