#!/usr/bin/env python3
"""Require a fresh independent review receipt for every substantive commit."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

RECEIPT = "reviews/CHECKIN_REVIEW.json"
REVIEWER = "Neurotic Paranoid Code Reviewer"
SCOPE = "complete latest repository disk copy, byte-for-byte, line-by-line, untruncated"
SEVERITIES = {"BLOCKER", "CRITICAL", "MAJOR"}
DISPOSITIONS = {"fixed", "accepted", "explained", "rejected", "ignored"}
RECEIPT_KEYS = {
    "schema",
    "reviewer",
    "review_scope",
    "reviewed_parent",
    "reviewed_tree",
    "manual_reads",
    "sop_clean_passes",
    "findings",
}
FINDING_KEYS = {"severity", "summary", "programmer_disposition"}


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(args, check=check, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def git_text(*args: str) -> str:
    return run("git", *args).stdout.decode("utf-8", errors="strict").strip()


def ensure_commit(rev: str) -> None:
    probe = run("git", "cat-file", "-e", rev + "^{commit}", check=False)
    if probe.returncode == 0:
        return
    fetched = run("git", "fetch", "--no-tags", "--depth=256", "origin", rev, check=False)
    if fetched.returncode != 0:
        sys.stderr.write(fetched.stderr.decode("utf-8", errors="replace"))
        raise RuntimeError(f"unable to fetch revision {rev}")


def changed_paths(base: str, head: str) -> list[str]:
    raw = run("git", "diff", "--name-only", "--no-renames", "-z", base, head).stdout
    return [p.decode("utf-8", errors="surrogateescape") for p in raw.split(b"\0") if p]


def staged_paths() -> list[str]:
    raw = run("git", "diff", "--cached", "--name-only", "--no-renames", "-z").stdout
    return [p.decode("utf-8", errors="surrogateescape") for p in raw.split(b"\0") if p]


def index_paths() -> list[str]:
    raw = run("git", "ls-files", "-z").stdout
    result = []
    for raw_path in raw.split(b"\0"):
        if not raw_path:
            continue
        path = raw_path.decode("utf-8", errors="surrogateescape")
        if path != RECEIPT:
            result.append(path)
    return result


def commit_paths(commit: str) -> list[str]:
    raw = run("git", "ls-tree", "-r", "--name-only", "-z", commit).stdout
    result = []
    for raw_path in raw.split(b"\0"):
        if not raw_path:
            continue
        path = raw_path.decode("utf-8", errors="surrogateescape")
        if path != RECEIPT:
            result.append(path)
    return result


def staged_entry(path: str) -> dict[str, str]:
    raw = run("git", "ls-files", "--stage", "-z", "--", path).stdout
    records = [record for record in raw.split(b"\0") if record]
    if len(records) != 1:
        raise RuntimeError(f"staged path {path!r}: expected one Git index entry, found {len(records)}")
    try:
        meta, _raw_path = records[0].split(b"\t", 1)
        mode, oid, stage = meta.split()
        if stage != b"0":
            raise RuntimeError(f"staged path {path!r}: unresolved index stage {stage.decode('ascii')}")
        return {"mode": mode.decode("ascii"), "oid": oid.decode("ascii")}
    except (ValueError, UnicodeDecodeError) as exc:
        raise RuntimeError(f"staged path {path!r}: malformed Git index entry") from exc


def commit_entry(commit: str, path: str) -> dict[str, str]:
    raw = run("git", "ls-tree", "-z", commit, "--", path).stdout
    records = [record for record in raw.split(b"\0") if record]
    if len(records) != 1:
        raise RuntimeError(f"commit {commit[:12]} path {path!r}: expected one Git tree entry, found {len(records)}")
    try:
        meta, _raw_path = records[0].split(b"\t", 1)
        mode, kind, oid = meta.split()
        if kind != b"blob":
            raise RuntimeError(f"commit {commit[:12]} path {path!r}: expected blob, found {kind.decode('ascii')}")
        return {"mode": mode.decode("ascii"), "oid": oid.decode("ascii")}
    except (ValueError, UnicodeDecodeError) as exc:
        raise RuntimeError(f"commit {commit[:12]} path {path!r}: malformed Git tree entry") from exc


def staged_tree_snapshot() -> dict[str, dict[str, str]]:
    return {path: staged_entry(path) for path in sorted(index_paths())}


def commit_tree_snapshot(commit: str) -> dict[str, dict[str, str]]:
    return {path: commit_entry(commit, path) for path in sorted(commit_paths(commit))}


def load_json_bytes(data: bytes, label: str) -> tuple[dict | None, list[str]]:
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, [f"{label}: invalid JSON: {exc}"]
    if not isinstance(value, dict):
        return None, [f"{label}: top-level value must be an object"]
    return value, []


def read_staged_receipt() -> tuple[dict | None, list[str]]:
    result = run("git", "show", ":" + RECEIPT, check=False)
    if result.returncode != 0:
        return None, [f"staged commit: missing {RECEIPT}"]
    return load_json_bytes(result.stdout, "staged receipt")


def read_commit_receipt(commit: str) -> tuple[dict | None, list[str]]:
    result = run("git", "show", f"{commit}:{RECEIPT}", check=False)
    if result.returncode != 0:
        return None, [f"commit {commit[:12]}: missing {RECEIPT}"]
    return load_json_bytes(result.stdout, f"commit {commit[:12]} receipt")


def validate_findings(value: object) -> list[str]:
    if not isinstance(value, list):
        return ["findings must be a list"]
    errors: list[str] = []
    for index, finding in enumerate(value, 1):
        label = f"finding {index}"
        if not isinstance(finding, dict):
            errors.append(f"{label} must be an object")
            continue
        unknown = set(finding) - FINDING_KEYS
        missing = FINDING_KEYS - set(finding)
        if unknown:
            errors.append(f"{label} has unknown field(s): {', '.join(sorted(unknown))}")
        if missing:
            errors.append(f"{label} is missing field(s): {', '.join(sorted(missing))}")
        severity = finding.get("severity")
        summary = finding.get("summary")
        disposition = finding.get("programmer_disposition")
        if severity not in SEVERITIES:
            errors.append(f"{label} severity must be BLOCKER, CRITICAL, or MAJOR")
        if not isinstance(summary, str) or not summary.strip():
            errors.append(f"{label} summary must be non-empty")
        if disposition not in DISPOSITIONS:
            errors.append(f"{label} programmer_disposition must be fixed, accepted, explained, rejected, or ignored")
    return errors


def validate_clean_passes(value: object) -> list[str]:
    if not isinstance(value, list) or len(value) != 3:
        return ["sop_clean_passes must record exactly three consecutive clean passes"]
    if any(item != "clean" for item in value):
        return ["sop_clean_passes may contain only 'clean'"]
    return []


def validate_receipt(receipt: dict, parent: str, expected_tree: dict[str, dict[str, str]], label: str) -> list[str]:
    errors: list[str] = []
    unknown = set(receipt) - RECEIPT_KEYS
    missing = RECEIPT_KEYS - set(receipt)
    if unknown:
        errors.append(f"{label}: unknown receipt field(s): {', '.join(sorted(unknown))}")
    if missing:
        errors.append(f"{label}: missing receipt field(s): {', '.join(sorted(missing))}")
    if receipt.get("schema") != 3:
        errors.append(f"{label}: schema must be 3")
    if receipt.get("reviewer") != REVIEWER:
        errors.append(f"{label}: reviewer identity must be '{REVIEWER}'")
    if receipt.get("reviewed_parent") != parent:
        errors.append(f"{label}: reviewed_parent does not match the exact parent commit")
    if receipt.get("reviewed_tree") != expected_tree:
        errors.append(f"{label}: reviewed_tree does not match the complete tracked path/mode/object snapshot")
    if receipt.get("manual_reads") != ["deep", "adversarial"]:
        errors.append(f"{label}: manual_reads must be exactly deep then adversarial")
    errors.extend(f"{label}: {error}" for error in validate_clean_passes(receipt.get("sop_clean_passes")))
    if receipt.get("review_scope") != SCOPE:
        errors.append(f"{label}: review_scope must attest the complete latest disk-copy review")
    errors.extend(f"{label}: {error}" for error in validate_findings(receipt.get("findings")))
    return errors


def staged_check() -> list[str]:
    paths = staged_paths()
    if not paths:
        return []
    substantive = [path for path in paths if path != RECEIPT]
    if not substantive:
        return ["receipt-only commits are not accepted"]
    if RECEIPT not in paths:
        return [f"staged commit changes project files but does not update {RECEIPT}"]
    parent = git_text("rev-parse", "HEAD")
    receipt, errors = read_staged_receipt()
    if errors or receipt is None:
        return errors
    return validate_receipt(receipt, parent, staged_tree_snapshot(), "staged receipt")


def commits_in_range(base: str | None, head: str) -> list[str]:
    ensure_commit(head)
    if base and set(base) != {"0"}:
        ensure_commit(base)
        return git_text("rev-list", "--reverse", f"{base}..{head}").splitlines()
    return [head]


def parent_of(commit: str) -> str | None:
    parents = git_text("rev-list", "--parents", "-n", "1", commit).split()
    if len(parents) == 1:
        return None
    if len(parents) != 2:
        raise RuntimeError(f"commit {commit[:12]} has {len(parents) - 1} parents; merge commits are not accepted")
    return parents[1]


def range_check(base: str | None, head: str) -> list[str]:
    errors: list[str] = []
    for commit in commits_in_range(base, head):
        parent = parent_of(commit)
        if parent is None:
            errors.append(f"commit {commit[:12]} has no parent; reviewer gate requires a parent")
            continue
        paths = changed_paths(parent, commit)
        if not paths:
            continue
        substantive = [path for path in paths if path != RECEIPT]
        if not substantive:
            errors.append(f"commit {commit[:12]} changes only {RECEIPT}; receipt-only commits are not accepted")
            continue
        if RECEIPT not in paths:
            errors.append(f"commit {commit[:12]} changes project files but does not update {RECEIPT}")
            continue
        receipt, load_errors = read_commit_receipt(commit)
        errors.extend(load_errors)
        if receipt is None:
            continue
        errors.extend(validate_receipt(receipt, parent, commit_tree_snapshot(commit), f"commit {commit[:12]} receipt"))
    return errors


def print_staged_template() -> int:
    parent = git_text("rev-parse", "HEAD")
    template = {
        "schema": 3,
        "reviewer": REVIEWER,
        "review_scope": SCOPE,
        "reviewed_parent": parent,
        "reviewed_tree": staged_tree_snapshot(),
        "manual_reads": ["deep", "adversarial"],
        "sop_clean_passes": ["clean", "clean", "clean"],
        "findings": [],
    }
    json.dump(template, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Enforce independent check-in review evidence.")
    parser.add_argument("--staged", action="store_true")
    parser.add_argument("--template", action="store_true")
    parser.add_argument("--base")
    parser.add_argument("--head", default="HEAD")
    args = parser.parse_args()
    try:
        if args.template:
            if not args.staged:
                parser.error("--template requires --staged")
            return print_staged_template()
        errors = staged_check() if args.staged else range_check(args.base, args.head)
    except (subprocess.CalledProcessError, RuntimeError) as exc:
        print(f"paranoid-review gate: {exc}", file=sys.stderr)
        return 1
    if errors:
        for error in errors:
            print(f"paranoid-review gate: {error}", file=sys.stderr)
        return 1
    print("paranoid-review gate: independent review receipt is current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
