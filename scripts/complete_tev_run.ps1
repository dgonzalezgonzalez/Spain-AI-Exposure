# Run the frozen model experiment and requested paper checks, with resumable caches.
param(
    [int]$WaitForPilotPid = 0,
    [string]$PythonExe = 'python'
)
$ErrorActionPreference = 'Stop'
$tevRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $tevRoot
if ($WaitForPilotPid -gt 0) {
    $tevPilot = Get-Process -Id $WaitForPilotPid -ErrorAction SilentlyContinue
    if ($tevPilot) { Wait-Process -Id $WaitForPilotPid }
    if (-not (Test-Path -LiteralPath '.tmp_tests\tev_pilot\manifest.json')) {
        throw 'Pilot did not complete; production run was not started.'
    }
}
& $PythonExe scripts/audit_tev_production_batches.py
if ($LASTEXITCODE -ne 0) { throw 'Fresh production repeatability failed.' }
& $PythonExe scripts/build_tev_occupation_exposure.py
if ($LASTEXITCODE -ne 0) { throw 'TEV inference stopped; cached responses remain resumable.' }
& $PythonExe scripts/run_occupation_paper_checks.py --model-family tev
if ($LASTEXITCODE -ne 0) { throw 'TEV paper checks failed.' }
Write-Output 'TEV appendices and internal shareout source ready. Compile and insert in Prism through Codex.'
