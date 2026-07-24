[CmdletBinding()]
param(
    [ValidatePattern('^\d{8}$')]
    [string]$Start = '20100101',
    [ValidatePattern('^\d{8}$')]
    [string]$End = '20260717',
    [switch]$SkipDaily,
    [switch]$SkipFinancial
)

$ErrorActionPreference = 'Stop'
$researchRoot = Split-Path -Parent $PSScriptRoot
$platformRoot = Join-Path (Split-Path -Parent $researchRoot) 'DyadTetrade'
$platformPython = Join-Path $platformRoot '.venv\Scripts\python.exe'
$researchPython = Join-Path $researchRoot '.venv\Scripts\python.exe'
$config = Join-Path $platformRoot 'config\market_data.yaml'

foreach ($path in @($platformPython, $researchPython, $config)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Required path is missing: $path"
    }
}
if (-not (Get-Process -Name XtMiniQmt -ErrorAction SilentlyContinue)) {
    throw 'MiniQMT is not running. Log in to QMT before starting the backfill.'
}

$failed = $false
$env:PYTHONPATH = Join-Path $platformRoot 'src'
$officialReport = Join-Path $researchRoot 'reports\data\official-delisted-universe-2010.json'
Push-Location $platformRoot
try {
    if (-not $SkipDaily) {
        & $platformPython (Join-Path $platformRoot 'scripts\seed_official_delisted_universe.py') `
            --config $config `
            --start $Start `
            --end $End `
            --output $officialReport
        if ($LASTEXITCODE -ne 0) {
            throw 'Official SSE/SZSE delisted-universe discovery failed.'
        }

        & $platformPython -m dyadtetrade.data.cli `
            --config $config `
            backfill `
            --start $Start `
            --end $End `
            --periods 1d `
            --include-delisted
        if ($LASTEXITCODE -ne 0) {
            Write-Warning 'Daily backfill completed in degraded state; financial work will continue.'
            $failed = $true
        }
    }

    if (-not $SkipFinancial) {
        & $platformPython -m dyadtetrade.data.cli `
            --config $config `
            backfill-financial `
            --start $Start `
            --end $End `
            --resume
        if ($LASTEXITCODE -ne 0) {
            Write-Warning 'Financial backfill completed in degraded state.'
            $failed = $true
        }
    }
}
finally {
    Pop-Location
}

$env:PYTHONPATH = Join-Path $researchRoot 'src'
$report = Join-Path $researchRoot 'reports\data\xtdata-2010-audit.json'
& $researchPython (Join-Path $researchRoot 'scripts\audit_xtdata_2010.py') `
    --root (Join-Path $researchRoot 'data\sqlite') `
    --start $Start `
    --end $End `
    --official-universe-report $officialReport `
    --output $report
if ($LASTEXITCODE -ne 0) {
    $failed = $true
}

Write-Host "Audit report: $report"
if ($failed) { exit 2 }
exit 0
