param(
    [string]$Base = '',
    [switch]$All,
    [string[]]$CommandLine = @(),
    [switch]$Audit
)

$ErrorActionPreference = 'Stop'

# The terms are encoded so this gate does not trip over its own rule set.
$encoded = @(
    'Y2xhdWRl','YW50aHJvcGlj','Y29kZXg=','Y2hhdGdwdA==','b3BlbmFp','c3BkeA==',
    'YXJ0aWZpY2lhbCBpbnRlbGxpZ2VuY2U=','bWFjaGluZSBsZWFybmluZw==','c2RsYw==',
    'YXV0aG9yaXR5','YXV0aG9yaXRpZXM=','YXJ0aWZhY3Q=','YXJ0aWZhY3Rz','cHJvdmVuYW5jZQ==',
    'cHJvdmVuYW5jZXM=','cGlubmVk','cGlubmluZw==','aW1tdXRhYmxl','aW1tdXRhYmlsaXR5',
    'ZXZpZGVuY2U=','ZXZpZGVuY2Vz','Y2VydGlmaWNhdGU=','Y2VydGlmaWNhdGVz','Y2VydGlmaWNhdGlvbg==',
    'Y2VydGlmaWNhdGlvbnM=','Y2VydGlmaWVk','cHJvamVjdCBtYW5hZ2VtZW50','YnVyZWF1Y3JhdA==',
    'YnVyZWF1Y3JhdHM=','YnVyZWF1Y3JhdGlj','cXVhbGlmaWNhdGlvbg==','cXVhbGlmaWNhdGlvbnM=',
    'cXVhbGlmaWVk','cXVhbGlmeQ==','cXVhbGlmaWVz','cXVhbGlmeWluZw==','cXVhbGlmaWVy',
    'cXVhbGlmaWVycw==','cXVhbGlm','cnVuaXg=','b3JhY2xl','YWJp','Y29udHJhY3Q='
)
$terms = $encoded | ForEach-Object { [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($_)) }
$violations = New-Object System.Collections.Generic.List[string]

function Test-Value([string]$Value, [string]$Location) {
    $normalized = $Value.Normalize([Text.NormalizationForm]::FormKC).ToLowerInvariant()
    foreach ($term in $terms) {
        $needle = $term.Normalize([Text.NormalizationForm]::FormKC).ToLowerInvariant()
        $pattern = '(?<![a-z0-9])' + [regex]::Escape($needle) + '(?![a-z0-9])'
        if ($normalized -match $pattern) {
            $violations.Add(("{0}: {1}" -f $Location, $term))
        }
    }
}

$files = if ($All) {
    git ls-files --cached --others --exclude-standard
} elseif ($Base) {
    git diff --name-only --diff-filter=ACMR "$Base...HEAD"
} else {
    git diff --cached --name-only --diff-filter=ACMR
}

foreach ($file in ($files | Sort-Object -Unique)) {
    Test-Value $file 'pathname'
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { continue }
    $leafName = [IO.Path]::GetFileName($file)
    if ($leafName -ieq 'LICENSE' -or $leafName -ieq 'README.md') { continue }
    $bytes = [IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $file))
    if ($bytes -contains 0) { continue }
    $text = [Text.Encoding]::UTF8.GetString($bytes)
    Test-Value $text "content: $file"
}

if ($CommandLine.Count -gt 0) { Test-Value ($CommandLine -join "`n") 'command-line' }

if ($violations.Count -gt 0) {
    $violations | Sort-Object -Unique | ForEach-Object { Write-Output ("Push gate: $_") }
    if (-not $Audit) { exit 1 }
} 
if ($Audit) {
    if ($violations.Count -eq 0) { Write-Output 'Audit passed.' }
    else { Write-Output ("Audit found {0} violation(s)." -f (($violations | Sort-Object -Unique).Count)) }
    exit 0
}
Write-Output 'Push gate passed.'
