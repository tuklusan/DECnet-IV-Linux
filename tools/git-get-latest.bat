@echo off
setlocal EnableExtensions DisableDelayedExpansion

rem ============================================================================
rem git-get-latest.bat
rem
rem Safely fast-forward the CURRENT branch to its CONFIGURED upstream while
rem preserving staged, unstaged, untracked, and ignored local files.
rem
rem Deliberately does NOT:
rem   - switch branches
rem   - create merge commits
rem   - rebase
rem   - reset
rem   - force-update the current branch
rem   - pop/drop any stash it cannot prove belongs to this invocation
rem
rem This file must be named exactly "git-get-latest.bat" and live at the
rem repository root. It must remain untracked. It does NOT need to be ignored:
rem the stash pathspec explicitly excludes this file.
rem
rem PRECONDITION: do not run another Git-mutating process against this worktree
rem or its stash stack while this utility is running. Git does not provide one
rem global transaction spanning fetch, stash, fast-forward, restore, and drop.
rem ============================================================================

if not "%~nx0"=="git-get-latest.bat" (
    echo ERROR: This file must be named exactly git-get-latest.bat.
    exit /b 1
)

pushd "%~dp0" >nul 2>&1
if errorlevel 1 (
    echo ERROR: Cannot enter the directory containing this script.
    exit /b 1
)

set "RC=1"
set "LOCAL_OID="
set "UPSTREAM_OID="
set "FETCHED_OID="
set "OLD_STASH_OID="
set "STASH_OID="
set "STASH_TAG="
set "STASH_RC="
set "FETCH_HEAD_PATH="
set "PS_EXE="
set "TMP_BASE="
set "TMP_BRANCH_A="
set "TMP_BRANCH_B="
set "TMP_FETCH_OID="
set "TMP_SCAN_A="

call :make_temp_names
if errorlevel 1 goto :temp_failed


rem ============================================================================
rem PRE-FLIGHT: repository/root/self checks.
rem ============================================================================

git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 goto :not_repo

set "ROOT="
for /f "delims=" %%R in ('git rev-parse --show-toplevel 2^>nul') do set "ROOT=%%R"
if not defined ROOT goto :not_repo

for %%R in ("%ROOT%") do set "ROOT=%%~fR"
set "HERE=%CD%"
for %%R in ("%HERE%") do set "HERE=%%~fR"

if /I not "%ROOT%"=="%HERE%" goto :not_root

if not exist "git-get-latest.bat" goto :self_missing

git ls-files > "%TMP_SCAN_A%" 2>nul
if errorlevel 1 goto :index_inspection_failed

findstr /I /L /X /C:"git-get-latest.bat" "%TMP_SCAN_A%" >nul 2>&1
if errorlevel 2 goto :temp_inspection_failed
if not errorlevel 1 goto :script_tracked


rem ============================================================================
rem BRANCH SAFETY: require a real checked-out branch and a real HEAD commit.
rem Store the symbolic HEAD in a temp file so even exotic legal branch names
rem are never interpolated back into cmd.exe command text.
rem ============================================================================

git symbolic-ref -q HEAD > "%TMP_BRANCH_A%" 2>nul
if errorlevel 1 goto :detached_head

set "LOCAL_OID="
for /f "delims=" %%H in ('git rev-parse -q --verify "HEAD^{commit}" 2^>nul') do set "LOCAL_OID=%%H"
if not defined LOCAL_OID goto :no_head_commit


rem ============================================================================
rem Refuse unfinished Git operations and an unmerged index.
rem ============================================================================

call :git_path_exists MERGE_HEAD
if errorlevel 2 goto :git_path_failed
if errorlevel 1 goto :operation_in_progress

call :git_path_exists CHERRY_PICK_HEAD
if errorlevel 2 goto :git_path_failed
if errorlevel 1 goto :operation_in_progress

call :git_path_exists REVERT_HEAD
if errorlevel 2 goto :git_path_failed
if errorlevel 1 goto :operation_in_progress

call :git_path_exists REBASE_HEAD
if errorlevel 2 goto :git_path_failed
if errorlevel 1 goto :operation_in_progress

call :git_path_exists rebase-apply
if errorlevel 2 goto :git_path_failed
if errorlevel 1 goto :operation_in_progress

call :git_path_exists rebase-merge
if errorlevel 2 goto :git_path_failed
if errorlevel 1 goto :operation_in_progress

call :git_path_exists sequencer
if errorlevel 2 goto :git_path_failed
if errorlevel 1 goto :operation_in_progress

call :git_path_exists BISECT_LOG
if errorlevel 2 goto :git_path_failed
if errorlevel 1 goto :operation_in_progress

git ls-files -u > "%TMP_SCAN_A%" 2>nul
if errorlevel 1 goto :index_inspection_failed

findstr . "%TMP_SCAN_A%" >nul 2>&1
if errorlevel 2 goto :temp_inspection_failed
if not errorlevel 1 goto :operation_in_progress


rem ============================================================================
rem Require a CONFIGURED upstream before touching local work.
rem Porcelain-v2 exposes branch.upstream even if the local remote-tracking ref
rem is currently missing/stale, so the fetch can repair it.
rem ============================================================================

git status --porcelain=v2 --branch --untracked-files=no --ignore-submodules=none > "%TMP_SCAN_A%" 2>nul
if errorlevel 1 goto :status_failed

findstr /B /L /C:"# branch.upstream " "%TMP_SCAN_A%" >nul 2>&1
if errorlevel 2 goto :temp_inspection_failed
if errorlevel 1 goto :no_upstream

rem Refuse any submodule whose checked-out commit or nested worktree differs
rem from the superproject index. Superproject stash does not safely normalize
rem submodule worktrees, so detect this before any parent-repo work is stashed.
findstr /R /C:"^[12] [^ ]* S" "%TMP_SCAN_A%" >nul 2>&1
if errorlevel 2 goto :temp_inspection_failed
if not errorlevel 1 goto :submodule_local_state

where powershell.exe >nul 2>&1
if not errorlevel 1 set "PS_EXE=powershell.exe"
if defined PS_EXE goto :powershell_ready

where pwsh.exe >nul 2>&1
if not errorlevel 1 set "PS_EXE=pwsh.exe"
if not defined PS_EXE goto :powershell_missing

:powershell_ready

rem ============================================================================
rem FETCH exactly once, BEFORE stashing local work.
rem
rem No repository name is supplied: Git therefore selects the configured
rem upstream remote for the current branch. The one-command fetch.all override
rem prevents a newer global/repository fetch.all=true setting from expanding
rem the fetch to all remotes; negative options also prevent pruning, automatic
rem tag following, and submodule recursion.
rem ============================================================================

echo.
echo Fetching the configured upstream...

git -c fetch.all=false fetch --atomic --no-prune --no-tags --no-recurse-submodules
if errorlevel 1 goto :fetch_failed

call :branch_stable
if errorlevel 1 goto :branch_changed

call :head_matches_local
if errorlevel 1 goto :head_changed


rem ============================================================================
rem Freeze and cross-check the exact upstream fetched by THIS fetch.
rem
rem 1. @{upstream}^{commit} is the configured tracking ref after fetch.
rem 2. FETCH_HEAD must contain exactly one merge-marked record.
rem 3. Those two OIDs must be identical.
rem
rem Parsing FETCH_HEAD with PowerShell preserves its empty tab field; this
rem avoids confusing a stale/deleted upstream with some unrelated
rem "not-for-merge" record.
rem ============================================================================

set "UPSTREAM_OID="
for /f "delims=" %%U in ('git rev-parse -q --verify "@{upstream}^{commit}" 2^>nul') do set "UPSTREAM_OID=%%U"
if not defined UPSTREAM_OID goto :upstream_not_resolved

set "FETCH_HEAD_PATH="
for /f "delims=" %%F in ('git rev-parse --git-path FETCH_HEAD 2^>nul') do set "FETCH_HEAD_PATH=%%F"
if not defined FETCH_HEAD_PATH goto :fetch_head_path_failed

set "GGL_FETCH_HEAD=%FETCH_HEAD_PATH%"

"%PS_EXE%" -NoLogo -NoProfile -NonInteractive -Command "$m=@(Get-Content -LiteralPath $env:GGL_FETCH_HEAD | ForEach-Object { $p=$_.Split([char]9); if($p.Length -ge 3 -and $p[1] -eq '') { $p[0] } }); if($m.Count -ne 1 -or $m[0] -notmatch '^[0-9A-Fa-f]+$') { exit 3 }; [Console]::Write($m[0])" > "%TMP_FETCH_OID%" 2>nul
if errorlevel 1 goto :fetched_upstream_ambiguous

set "FETCHED_OID="
set /p "FETCHED_OID="<"%TMP_FETCH_OID%"
if not defined FETCHED_OID goto :fetched_upstream_ambiguous

if /I not "%FETCHED_OID%"=="%UPSTREAM_OID%" goto :fetched_upstream_mismatch

git cat-file -e "%FETCHED_OID%^{commit}" >nul 2>&1
if errorlevel 1 goto :fetched_object_invalid


rem ============================================================================
rem TOPOLOGY: current HEAD must be equal to or behind the exact fetched OID.
rem Local-ahead and diverged histories are refused.
rem ============================================================================

git merge-base --is-ancestor "%LOCAL_OID%" "%FETCHED_OID%"
if errorlevel 2 goto :graph_failed
if errorlevel 1 goto :local_not_ancestor


rem ============================================================================
rem SELF-SAFETY against the TARGET tree.
rem On Windows the filesystem is normally case-insensitive, so reject any root
rem tree entry whose name equals git-get-latest.bat ignoring case.
rem ============================================================================

if /I not "%LOCAL_OID%"=="%FETCHED_OID%" goto :target_tree_check

call :branch_stable
if errorlevel 1 goto :branch_changed_before_noop

call :head_matches_local
if errorlevel 1 goto :head_changed_before_noop

goto :success

:target_tree_check
git ls-tree --name-only "%FETCHED_OID%" > "%TMP_SCAN_A%" 2>nul
if errorlevel 1 goto :target_tree_failed

findstr /I /L /X /C:"git-get-latest.bat" "%TMP_SCAN_A%" >nul 2>&1
if errorlevel 2 goto :temp_inspection_failed
if not errorlevel 1 goto :target_tracks_script

call :branch_stable
if errorlevel 1 goto :branch_changed_before_stash

call :head_matches_local
if errorlevel 1 goto :head_changed_before_stash


rem ============================================================================
rem STASH local state.
rem
rem --all preserves tracked/staged/untracked/ignored local files.
rem The top-level exclusion keeps this running batch file in place whether it
rem is ignored or not.
rem ============================================================================

set "OLD_STASH_OID="
for /f "delims=" %%S in ('git rev-parse -q --verify refs/stash 2^>nul') do set "OLD_STASH_OID=%%S"

set "STASH_TAG=git-get-latest-%RANDOM%-%RANDOM%-%RANDOM%-%RANDOM%"

echo.
echo Saving local work, if any...

set "STASH_RC="
git stash push -a -m "%STASH_TAG%" -- . ":(top,exclude)git-get-latest.bat"
set "STASH_RC=%ERRORLEVEL%"

set "STASH_OID="
for /f "delims=" %%S in ('git rev-parse -q --verify refs/stash 2^>nul') do set "STASH_OID=%%S"

if not "%STASH_RC%"=="0" goto :stash_failed

if not defined OLD_STASH_OID goto :stash_old_absent
if not defined STASH_OID goto :stash_identity_failed
if /I "%STASH_OID%"=="%OLD_STASH_OID%" goto :no_new_stash
goto :verify_new_stash

:stash_old_absent
if not defined STASH_OID goto :no_new_stash

:verify_new_stash
git log -1 --format=%%B "%STASH_OID%" 2>nul | findstr /L /C:"%STASH_TAG%" >nul
if errorlevel 1 goto :stash_identity_failed
goto :stash_identity_done

:no_new_stash
set "STASH_OID="

:stash_identity_done
call :verify_quiescent
if errorlevel 3 goto :self_missing_after_stash
if errorlevel 2 goto :status_failed_after_stash
if errorlevel 1 goto :stash_incomplete

call :branch_stable
if errorlevel 1 goto :branch_changed_after_stash

call :head_matches_local
if errorlevel 1 goto :head_changed_after_stash


rem ============================================================================
rem FAST-FORWARD to the immutable OID captured from this invocation's fetch.
rem ============================================================================

echo.
echo Fast-forwarding current branch to:
echo %FETCHED_OID%

git merge --ff-only "%FETCHED_OID%"
if errorlevel 1 goto :update_failed

set "HEAD_OID="
for /f "delims=" %%H in ('git rev-parse -q --verify "HEAD^{commit}" 2^>nul') do set "HEAD_OID=%%H"
if not defined HEAD_OID goto :head_verify_failed
if /I not "%HEAD_OID%"=="%FETCHED_OID%" goto :head_verify_failed

call :branch_stable
if errorlevel 1 goto :branch_changed_after_update

call :verify_superproject_quiescent
if errorlevel 3 goto :self_missing_after_update
if errorlevel 2 goto :status_failed_after_update
if errorlevel 1 goto :post_update_dirty

call :branch_stable
if errorlevel 1 goto :branch_changed_before_restore

call :head_matches_fetched
if errorlevel 1 goto :head_changed_before_restore


rem ============================================================================
rem RESTORE exact stash object with --index so prior staged state is restored.
rem ============================================================================

if not defined STASH_OID goto :success

echo.
echo Restoring local work from stash object:
echo %STASH_OID%

git stash apply --index "%STASH_OID%"
if errorlevel 1 goto :restore_conflict

call :branch_stable
if errorlevel 1 goto :restored_but_state_changed

call :head_matches_fetched
if errorlevel 1 goto :restored_but_state_changed

git status --porcelain=v1 --untracked-files=all --ignore-submodules=none >nul 2>&1
if errorlevel 1 goto :restored_but_state_unverified


rem ============================================================================
rem DROP only if refs/stash is STILL exactly our stash and still bears our
rem unique marker. Otherwise leave the stash stack untouched.
rem ============================================================================

set "TOP_STASH="
for /f "delims=" %%S in ('git rev-parse -q --verify refs/stash 2^>nul') do set "TOP_STASH=%%S"

if not defined TOP_STASH goto :restored_but_stash_changed
if /I not "%TOP_STASH%"=="%STASH_OID%" goto :restored_but_stash_changed

git log -1 --format=%%B "%TOP_STASH%" 2>nul | findstr /L /C:"%STASH_TAG%" >nul
if errorlevel 1 goto :restored_but_stash_changed

git stash drop "stash@{0}"
if errorlevel 1 goto :restored_but_drop_failed


rem ============================================================================
rem SUCCESS
rem ============================================================================

:success
echo.
echo ============================================================================
echo SUCCESS
echo ============================================================================
echo Current branch is exactly at fetched upstream commit:
echo %FETCHED_OID%
if defined STASH_OID echo Local work was restored, including staged state and ignored files.
echo.
git status --short --branch
set "RC=0"
goto :finish


rem ============================================================================
rem FAILURE / CONSERVATIVE-STOP PATHS
rem ============================================================================

:not_repo
echo ERROR: This script is not running from a Git working tree.
goto :finish

:not_root
echo ERROR: git-get-latest.bat must be located in the repository root.
goto :finish

:self_missing
echo ERROR: git-get-latest.bat is missing from the repository root.
goto :finish

:index_inspection_failed
echo ERROR: Git could not inspect the index safely.
goto :finish

:script_tracked
echo ERROR: git-get-latest.bat is tracked by Git, possibly with different letter case.
echo Keep this updater untracked.
goto :finish

:detached_head
echo ERROR: HEAD is detached. Nothing was changed.
goto :finish

:no_head_commit
echo ERROR: The current branch has no HEAD commit yet. Nothing was changed.
goto :finish

:operation_in_progress
echo ERROR: An unfinished merge/rebase/cherry-pick/revert/bisect/sequencer or unmerged index is present.
echo Finish or abort that Git operation before running this updater.
goto :finish

:git_path_failed
echo ERROR: Git could not inspect its operation-state paths.
goto :finish

:status_failed
echo ERROR: Git status inspection failed.
goto :finish

:no_upstream
echo ERROR: The current branch has no configured upstream.
echo Configure an upstream first; no branch switch or guessed remote was attempted.
goto :finish

:submodule_local_state
echo ERROR: A submodule has a changed commit, tracked modification, or untracked content.
echo Nothing was stashed and the current branch was not moved.
echo Make the submodule state clean or handle it separately before running this updater.
goto :finish

:powershell_missing
echo ERROR: PowerShell ^(powershell.exe or pwsh.exe^) is required for safe FETCH_HEAD parsing.
echo Nothing was changed.
goto :finish

:fetch_failed
echo ERROR: Fetch from the configured upstream failed.
echo Local working files were not stashed and the current branch was not moved.
goto :finish

:branch_changed
echo ERROR: The checked-out branch changed unexpectedly during fetch.
echo No local work was stashed and no fast-forward was attempted.
goto :finish

:head_changed
echo ERROR: HEAD changed unexpectedly during fetch.
echo No local work was stashed and no fast-forward was attempted.
goto :finish

:upstream_not_resolved
echo ERROR: The configured upstream could not be resolved to a commit after fetch.
echo It may have been deleted or the fetch configuration may be inconsistent.
goto :finish

:fetch_head_path_failed
echo ERROR: Git could not locate FETCH_HEAD after fetch.
goto :finish

:fetched_upstream_ambiguous
echo ERROR: FETCH_HEAD does not contain exactly one merge-marked upstream commit.
echo The configured upstream may be deleted, ambiguous, or unusually configured.
goto :finish

:fetched_upstream_mismatch
echo ERROR: The fetched merge candidate does not match @{upstream} after fetch.
echo No fast-forward was attempted.
goto :finish

:fetched_object_invalid
echo ERROR: The fetched upstream object is not a valid commit.
goto :finish

:graph_failed
echo ERROR: Git could not verify commit ancestry.
goto :finish

:local_not_ancestor
echo ERROR: Local HEAD is not an ancestor of the fetched upstream commit.
echo The current branch is ahead or histories have diverged.
echo No reset, rebase, merge commit, or force operation was attempted.
goto :finish

:branch_changed_before_noop
echo ERROR: The checked-out branch changed unexpectedly before no-op completion.
echo No local work was stashed and no fast-forward was attempted.
goto :finish

:head_changed_before_noop
echo ERROR: HEAD changed unexpectedly before no-op completion.
echo No local work was stashed and no fast-forward was attempted.
goto :finish

:target_tree_failed
echo ERROR: Git could not inspect the fetched target tree.
goto :finish

:target_tracks_script
echo ERROR: The fetched target tree contains git-get-latest.bat ^(case-insensitive^).
echo Refusing the update because Windows could overwrite this running script.
goto :finish

:branch_changed_before_stash
echo ERROR: The checked-out branch changed unexpectedly before stashing.
echo No local work was stashed and no fast-forward was attempted.
goto :finish

:head_changed_before_stash
echo ERROR: HEAD changed unexpectedly before stashing.
echo No local work was stashed and no fast-forward was attempted.
goto :finish

:stash_failed
echo ERROR: Saving local work failed.
echo The current branch was not moved.
echo Because Git may have changed refs/stash before reporting failure, inspect git stash list.
if defined STASH_OID echo Current top stash object after the failed command: %STASH_OID%
goto :finish

:stash_identity_failed
echo ERROR: A stash change occurred, but this invocation cannot prove ownership of the top stash.
echo The current branch was not moved. No stash entry was deleted.
if defined STASH_OID echo Current top stash object: %STASH_OID%
goto :finish

:self_missing_after_stash
echo ERROR: The updater disappeared while local work was being saved.
echo The branch was not moved. Any created stash was NOT deleted.
if defined STASH_OID echo Exact stash object: %STASH_OID%
goto :finish

:status_failed_after_stash
echo ERROR: Post-stash worktree verification failed.
echo The branch was not moved. Any created stash was NOT deleted.
if defined STASH_OID echo Exact stash object: %STASH_OID%
goto :finish

:stash_incomplete
echo ERROR: Local repository content remains after the protective stash.
echo This can include dirty submodules or unusual untracked/ignored content.
echo The branch was NOT moved. Any created stash was NOT deleted.
if defined STASH_OID echo Exact stash object: %STASH_OID%
git status --short --branch --ignore-submodules=none
goto :finish

:branch_changed_after_stash
echo ERROR: The checked-out branch changed unexpectedly after stashing.
echo No fast-forward was attempted. The stash was NOT deleted.
if defined STASH_OID echo Exact stash object: %STASH_OID%
goto :finish

:head_changed_after_stash
echo ERROR: HEAD changed unexpectedly after stashing.
echo No fast-forward was attempted. The stash was NOT deleted.
if defined STASH_OID echo Exact stash object: %STASH_OID%
goto :finish

:update_failed
echo ERROR: The exact fast-forward failed.
if defined STASH_OID echo Local work remains safely stored in stash object %STASH_OID%.
goto :finish

:head_verify_failed
echo ERROR: Fast-forward returned, but HEAD is not the exact fetched upstream OID.
if defined STASH_OID echo The stash was NOT applied or deleted: %STASH_OID%
goto :finish

:branch_changed_after_update
echo ERROR: The checked-out branch changed unexpectedly during the update.
if defined STASH_OID echo The stash was NOT applied or deleted: %STASH_OID%
goto :finish

:self_missing_after_update
echo ERROR: The updater disappeared during the fast-forward.
if defined STASH_OID echo The stash was NOT applied or deleted: %STASH_OID%
goto :finish

:branch_changed_before_restore
echo ERROR: The checked-out branch changed unexpectedly before local-work restoration.
if defined STASH_OID echo The stash was NOT applied or deleted: %STASH_OID%
goto :finish

:head_changed_before_restore
echo ERROR: HEAD changed unexpectedly before local-work restoration.
if defined STASH_OID echo The stash was NOT applied or deleted: %STASH_OID%
goto :finish

:status_failed_after_update
echo ERROR: The branch reached the fetched commit, but worktree verification failed.
if defined STASH_OID echo The stash was NOT applied or deleted: %STASH_OID%
goto :finish

:post_update_dirty
echo ERROR: The branch reached %FETCHED_OID%, but repository content became dirty before restoration.
echo The protective stash was NOT applied or deleted.
if defined STASH_OID echo Exact stash object: %STASH_OID%
git status --short --branch --ignore-submodules=none
goto :finish

:restore_conflict
echo.
echo WARNING: The branch is now %FETCHED_OID%, but restoring local work produced conflicts.
echo The stash was NOT dropped.
echo Exact stash object: %STASH_OID%
git status --short --branch --ignore-submodules=none
set "RC=2"
goto :finish

:restored_but_state_changed
echo.
echo WARNING: Local work was restored, but the checked-out branch or HEAD changed unexpectedly.
echo The temporary stash was NOT dropped.
echo Exact stash object: %STASH_OID%
git status --short --branch --ignore-submodules=none
set "RC=2"
goto :finish

:restored_but_state_unverified
echo.
echo WARNING: Local work was restored, but Git status could not verify repository state.
echo The temporary stash was NOT dropped.
echo Exact stash object: %STASH_OID%
set "RC=2"
goto :finish

:restored_but_stash_changed
echo.
echo WARNING: Local work was restored, but the stash stack changed unexpectedly.
echo NO stash entry was deleted.
echo Exact stash object: %STASH_OID%
git status --short --branch --ignore-submodules=none
set "RC=2"
goto :finish

:restored_but_drop_failed
echo.
echo WARNING: Local work was restored, but the temporary stash could not be dropped.
echo Inspect git stash list. No further stash deletion was attempted.
echo Exact stash object: %STASH_OID%
git status --short --branch --ignore-submodules=none
set "RC=2"
goto :finish

:temp_inspection_failed
echo ERROR: A temporary verification file could not be inspected reliably.
goto :finish

:temp_failed
echo ERROR: Could not allocate safe temporary filenames.
goto :finish


rem ============================================================================
rem EXIT
rem ============================================================================

:finish
if defined TMP_BRANCH_A del /q "%TMP_BRANCH_A%" >nul 2>&1
if defined TMP_BRANCH_B del /q "%TMP_BRANCH_B%" >nul 2>&1
if defined TMP_FETCH_OID del /q "%TMP_FETCH_OID%" >nul 2>&1
if defined TMP_SCAN_A del /q "%TMP_SCAN_A%" >nul 2>&1
set "GGL_FETCH_HEAD="
popd >nul 2>&1
exit /b %RC%


rem ============================================================================
rem SUBROUTINES
rem ============================================================================

:make_temp_names
if not defined TEMP exit /b 1

:make_temp_names_retry
set "TMP_BASE=%TEMP%\git-get-latest-%RANDOM%-%RANDOM%-%RANDOM%-%RANDOM%"
set "TMP_BRANCH_A=%TMP_BASE%-branch-a.tmp"
set "TMP_BRANCH_B=%TMP_BASE%-branch-b.tmp"
set "TMP_FETCH_OID=%TMP_BASE%-fetch-oid.tmp"
set "TMP_SCAN_A=%TMP_BASE%-scan-a.tmp"

if exist "%TMP_BRANCH_A%" goto :make_temp_names_retry
if exist "%TMP_BRANCH_B%" goto :make_temp_names_retry
if exist "%TMP_FETCH_OID%" goto :make_temp_names_retry
if exist "%TMP_SCAN_A%" goto :make_temp_names_retry

(> "%TMP_SCAN_A%" echo git-get-latest-temp-write-test) 2>nul
if errorlevel 1 exit /b 1
del /q "%TMP_SCAN_A%" >nul 2>&1
if exist "%TMP_SCAN_A%" exit /b 1
exit /b 0

:git_path_exists
set "GGL_GIT_PATH="
rem --git-path is worktree-aware and may return either a root-relative or an
rem absolute path. Avoid --path-format=absolute so this probe also works with
rem Git versions predating that newer rev-parse option.
git rev-parse --git-path "%~1" > "%TMP_SCAN_A%" 2>nul
if errorlevel 1 exit /b 2
set /p "GGL_GIT_PATH="<"%TMP_SCAN_A%"
if not defined GGL_GIT_PATH exit /b 2
if exist "%GGL_GIT_PATH%" exit /b 1
exit /b 0

:branch_stable
git symbolic-ref -q HEAD > "%TMP_BRANCH_B%" 2>nul
if errorlevel 1 exit /b 1
fc /b "%TMP_BRANCH_A%" "%TMP_BRANCH_B%" >nul 2>&1
if errorlevel 1 exit /b 1
exit /b 0

:head_matches_local
set "GGL_HEAD_NOW="
for /f "delims=" %%H in ('git rev-parse -q --verify "HEAD^{commit}" 2^>nul') do set "GGL_HEAD_NOW=%%H"
if not defined GGL_HEAD_NOW exit /b 1
if /I not "%GGL_HEAD_NOW%"=="%LOCAL_OID%" exit /b 1
exit /b 0

:head_matches_fetched
set "GGL_HEAD_NOW="
for /f "delims=" %%H in ('git rev-parse -q --verify "HEAD^{commit}" 2^>nul') do set "GGL_HEAD_NOW=%%H"
if not defined GGL_HEAD_NOW exit /b 1
if /I not "%GGL_HEAD_NOW%"=="%FETCHED_OID%" exit /b 1
exit /b 0

:verify_quiescent
if not exist "git-get-latest.bat" exit /b 3

rem Ask Git to inspect every path except this updater. This avoids parsing
rem porcelain output merely to whitelist the updater itself, and works whether
rem the updater is untracked or ignored.
git status --porcelain=v1 --ignored=matching --untracked-files=all --ignore-submodules=none -- . ":(top,exclude)git-get-latest.bat" > "%TMP_SCAN_A%" 2>nul
if errorlevel 1 exit /b 2

findstr . "%TMP_SCAN_A%" >nul 2>&1
if errorlevel 2 exit /b 2
if errorlevel 1 exit /b 0
exit /b 1


:verify_superproject_quiescent
rem Before the branch moved, :verify_quiescent proved submodules were clean.
rem A fast-forward can legitimately change gitlink OIDs without checking out the
rem corresponding submodule commits. Ignore submodule worktree mismatch here,
rem while still requiring the superproject itself to contain only this updater.
if not exist "git-get-latest.bat" exit /b 3

git status --porcelain=v1 --ignored=matching --untracked-files=all --ignore-submodules=all -- . ":(top,exclude)git-get-latest.bat" > "%TMP_SCAN_A%" 2>nul
if errorlevel 1 exit /b 2

findstr . "%TMP_SCAN_A%" >nul 2>&1
if errorlevel 2 exit /b 2
if errorlevel 1 exit /b 0
exit /b 1
