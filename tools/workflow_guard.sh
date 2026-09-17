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
    echo "usage: $0 STATE-DIR EXPECTED-SHA main|maintenance|event" >&2
    exit 2
fi
state_dir=$1
expected=$2
scope=$3
case "$scope" in main|maintenance|event) ;; *) echo "workflow-guard: invalid scope: $scope" >&2; exit 2 ;; esac

head=$(git rev-parse --verify 'HEAD^{commit}')
expected=$(git rev-parse --verify "$expected^{commit}")
[[ "$head" == "$expected" ]] || {
    echo "workflow-guard: checkout $head does not match requested $expected" >&2
    exit 1
}

if [[ "$scope" == main ]]; then
    [[ "${GITHUB_REF:-refs/heads/main}" == refs/heads/main ]] || {
        echo "workflow-guard: acceptance workflows must run from main" >&2
        exit 1
    }
fi

# Both acceptance and maintenance operate on the exact current main tree. The
# maintenance scope is used by branch-create cleanup jobs, whose immutable
# event metadata still names the non-main branch even after checkout switches
# to main and the branch is deleted.
if [[ "$scope" == main || "$scope" == maintenance ]]; then
    remote=$(git ls-remote origin refs/heads/main | awk 'NR == 1 {print $1}')
    [[ -n "$remote" && "$remote" == "$expected" ]] || {
        echo "workflow-guard: requested revision is not the current remote main" >&2
        exit 1
    }
fi

mkdir -p "$state_dir/integrity"
python3 tools/scratch_state.py verify --dir "$state_dir"
python3 tools/license_monkey.py --tree "$expected" | tee "$state_dir/integrity/license.log"
python3 tests/policy/test_workflow_budget_gate.py | tee "$state_dir/integrity/workflow-budget-regression.log"
python3 tools/workflow_budget_gate.py --tree "$expected" | tee "$state_dir/integrity/workflow-budget.log"
python3 tests/policy/test_image_builder_gate.py --tree "$expected" | tee "$state_dir/integrity/image-builder-regression.log"
python3 tests/policy/test_lab_stats_snapshot.py | tee "$state_dir/integrity/lab-stats-regression.log"
python3 tests/policy/test_e1_silence_window.py | tee "$state_dir/integrity/e1-silence-regression.log"
python3 tests/policy/test_project_state_gate.py | tee "$state_dir/integrity/project-state-regression.log"
python3 tests/policy/test_repo_policy_branch.py | tee "$state_dir/integrity/branch-policy-regression.log"
if [[ "$scope" == main || "$scope" == maintenance ]]; then
    python3 tools/project_state_gate.py --head "$expected" | tee "$state_dir/integrity/project-state.log"
    CI=false python3 tools/repo_policy.py | tee "$state_dir/integrity/repository-policy.log"
fi

# Routine workflow integrity checking is deliberately bounded to the exact
# parent-to-candidate diff. A complete tracked-tree machine scan remains
# available only through an explicit `tools/integrity_scan.py --full-tree` call.
python3 tools/integrity_scan.py --rev "$expected" --pass-id baseline \
    --output "$state_dir/integrity/pass-1.json"
python3 tools/scratch_state.py mark --dir "$state_dir" --status targeted-scan-green \
    --note "bounded parent-to-candidate integrity manifest recorded; automatic full-tree scan disabled"
