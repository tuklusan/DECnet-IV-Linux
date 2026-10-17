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

# Bounded GitHub Actions garbage collection. Never erase repository issue
# handovers or source. Historical workflow logs/artifacts/cache are ephemeral;
# verified results survive in SHA-bound issue evidence, not retained CI bytes.
set -euo pipefail

: "${GITHUB_REPOSITORY:?repository is required}"
: "${GH_TOKEN:?Actions write token is required}"
[[ "$GITHUB_REPOSITORY" == 'tuklusan/DECnet-IV-Linux' ]] || {
    echo 'Wrong repository: refusing deletions' >&2
    exit 2
}
command -v gh >/dev/null
command -v jq >/dev/null

api="repos/$GITHUB_REPOSITORY"
max_deletes="${DNIV_GC_MAX_DELETES:-650}"
[[ "$max_deletes" =~ ^[1-9][0-9]*$ ]] && (( max_deletes <= 800 )) || {
    echo 'Bad deletion budget' >&2
    exit 2
}
# Four hours are reserved for consumers to verify and record new run results.
# The initial historical sweep removes only runs before this fixed boundary.
initial_cutoff='2026-10-17T15:36:00Z'
hours="${DNIV_GC_GRACE_HOURS:-4}"
[[ "$hours" =~ ^[1-9][0-9]*$ ]] && (( hours <= 48 )) || exit 2
active_issue=$(gh api "$api/issues?state=open&per_page=100" --jq \
    '.[] | select(.title == "DNIV actions cleanup" and .user.login == "tuklusan" and .pull_request == null) | .number' | head -1)
if [[ -n "$active_issue" ]]; then
    cutoff="$initial_cutoff"
    mode='historical'
else
    cutoff=$(date -u -d "$hours hours ago" '+%Y-%m-%dT%H:%M:%SZ')
    mode='routine'
fi

used=0
removed_cache=0
removed_runs=0
available() {
    local quota
    quota=$(gh api rate_limit --jq '.resources.core.remaining')
    [[ "$quota" =~ ^[0-9]+$ ]] || return 1
    (( quota > 110 )) && (( used < max_deletes ))
}

# Deleting cache records is safe even when the foundation cache must be rebuilt.
while available; do
    list=$(gh api "$api/actions/caches?per_page=100" --jq '.actions_caches[].id')
    [[ -n "$list" ]] || break
    while IFS= read -r id; do
        [[ "$id" =~ ^[0-9]+$ ]] || exit 2
        gh api -X DELETE "$api/actions/caches/$id" >/dev/null
        used=$((used + 1))
        removed_cache=$((removed_cache + 1))
        (( used < max_deletes )) || break
    done <<< "$list"
done

# Completed run deletion also removes its logs and associated artifacts.
# Never cancel an in-progress job. This workflow cannot delete its own
# in-progress run; a subsequent sweep deletes it after its grace period.
while available; do
    list=$(gh api "$api/actions/runs?per_page=100&status=completed&created=..$cutoff" --jq '.workflow_runs[].id')
    [[ -n "$list" ]] || break
    while IFS= read -r id; do
        [[ "$id" =~ ^[0-9]+$ ]] || exit 2
        [[ "$id" == "${GITHUB_RUN_ID:-}" ]] && continue
        gh api -X DELETE "$api/actions/runs/$id" >/dev/null
        used=$((used + 1))
        removed_runs=$((removed_runs + 1))
        (( used < max_deletes )) || break
    done <<< "$list"
done

cache_left=$(gh api "$api/actions/caches?per_page=1" --jq '.total_count')
old_left=$(gh api "$api/actions/runs?per_page=1&status=completed&created=..$initial_cutoff" --jq '.total_count')
expired_left=$(gh api "$api/actions/runs?per_page=1&status=completed&created=..$cutoff" --jq '.total_count')
summary="Actions GC run ${GITHUB_RUN_ID:-local}: mode=$mode; removed caches=$removed_cache, completed runs=$removed_runs; cache entries left=$cache_left, runs before original cutoff left=$old_left, eligible runs left=$expired_left; current grace=$hours hours."
echo "$summary"
if [[ -n "$active_issue" ]]; then
    gh api -X POST "$api/issues/$active_issue/comments" -f "body=$summary" >/dev/null
    if [[ "$cache_left" == '0' && "$old_left" == '0' ]]; then
        gh api -X PATCH "$api/issues/$active_issue" -f state=closed >/dev/null
    fi
fi
