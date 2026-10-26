param([Parameter(ValueFromRemainingArguments=$true)][string[]]$ArgumentList)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'scripts/push-gate.ps1') -CommandLine @('gh') + $ArgumentList
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& gh @ArgumentList
exit $LASTEXITCODE
