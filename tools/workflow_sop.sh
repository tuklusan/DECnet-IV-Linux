#!/usr/bin/env bash
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

set -euo pipefail

if [[ $# -ne 3 ]]; then
    echo "usage: $0 STATE-DIR EXPECTED-SHA main|event" >&2
    exit 2
fi
state_dir=$1
expected=$2
scope=$3
case "$scope" in main|event) ;; *) echo "workflow-sop: invalid scope: $scope" >&2; exit 2 ;; esac

head=$(git rev-parse --verify 'HEAD^{commit}')
expected=$(git rev-parse --verify "$expected^{commit}")
[[ "$head" == "$expected" ]] || {
    echo "workflow-sop: checkout $head does not match requested $expected" >&2
    exit 1
}

if [[ "$scope" == main ]]; then
    [[ "${GITHUB_REF:-refs/heads/main}" == refs/heads/main ]] || {
        echo "workflow-sop: acceptance workflows must run from main" >&2
        exit 1
    }
    remote=$(git ls-remote origin refs/heads/main | awk 'NR == 1 {print $1}')
    [[ -n "$remote" && "$remote" == "$expected" ]] || {
        echo "workflow-sop: requested revision is not the current remote main" >&2
        exit 1
    }
fi

mkdir -p "$state_dir/sop"
python3 tools/scratch_state.py verify --dir "$state_dir"
python3 tools/license_monkey.py --tree "$expected" | tee "$state_dir/sop/license.log"
python3 tools/workflow_budget_gate.py | tee "$state_dir/sop/workflow-budget.log"
python3 tests/policy/test_project_state_gate.py | tee "$state_dir/sop/project-state-regression.log"
if [[ "$scope" == main ]]; then
    python3 tools/project_state_gate.py --head "$expected" | tee "$state_dir/sop/project-state.log"
    CI=false python3 tools/repo_policy.py | tee "$state_dir/sop/repository-policy.log"
fi

python3 tools/sop_scan.py --rev "$expected" --pass-id 1 \
    --output "$state_dir/sop/pass-1.json"
python3 tools/sop_scan.py --rev "$expected" --pass-id 2 \
    --baseline "$state_dir/sop/pass-1.json" --output "$state_dir/sop/pass-2.json"
python3 tools/sop_scan.py --rev "$expected" --pass-id 3 \
    --baseline "$state_dir/sop/pass-1.json" --output "$state_dir/sop/pass-3.json"
python3 tools/scratch_state.py mark --dir "$state_dir" --status sop-scan-green \
    --note "three byte-complete exact-tree scans matched"
