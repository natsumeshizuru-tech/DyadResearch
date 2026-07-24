[CmdletBinding()]
param(
    [ValidateRange(1, 500)]
    [int]$BatchSize = 100,
    [ValidateSet("1d", "1m", "1d,1m")]
    [string]$Periods = "1d,1m"
)

$ErrorActionPreference = "Stop"
$researchRoot = Split-Path -Parent $PSScriptRoot
$platformRoot = Join-Path (Split-Path -Parent $researchRoot) "DyadTetrade"
$python = Join-Path $platformRoot ".venv\Scripts\python.exe"
$config = Join-Path $platformRoot "config\market_data.yaml"

if (-not (Test-Path -LiteralPath $python)) {
    throw "DyadTetrade Python environment not found: $python"
}

$env:PYTHONPATH = Join-Path $platformRoot "src"
Push-Location $platformRoot
try {
    & $python -m dyadtetrade.data.cli `
        --config $config `
        refresh-catalog `
        --start 20240101 `
        --end 20260718 `
        --sector "沪深ETF"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    if ($Periods -in @("1d", "1d,1m")) {
        $dailySelector = @"
from dyadtetrade.data.config import load_data_config
import sqlite3
settings = load_data_config(r'$config')
with sqlite3.connect(settings.storage.root / settings.storage.catalog) as connection:
    completed = {row[0] for row in connection.execute(
        "SELECT symbol FROM dataset_watermarks WHERE dataset='bars' AND period='1d' AND row_count>0"
    )}
    active = [row[0] for row in connection.execute(
        "SELECT symbol FROM instruments WHERE instrument_type='etf' AND is_active=1 ORDER BY symbol"
    )]
print(','.join([symbol for symbol in active if symbol not in completed][:$BatchSize]))
"@
        $dailySymbols = & $python -c $dailySelector
        if ($LASTEXITCODE -ne 0) { throw "Could not query daily ETF coverage." }
        if ($dailySymbols) {
            & $python -m dyadtetrade.data.cli `
                --config $config `
                backfill `
                --start 20240101 `
                --end 20260718 `
                --periods 1d `
                --sector "沪深ETF" `
                --symbols $dailySymbols
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        }
        else {
            Write-Host "ETF daily migration is complete."
        }
    }

    if ($Periods -in @("1m", "1d,1m")) {
        $minuteSelector = @"
from dyadtetrade.data.config import load_data_config
import sqlite3
settings = load_data_config(r'$config')
data_dir = settings.qmt.big_data_dir
with sqlite3.connect(settings.storage.root / settings.storage.catalog) as connection:
    completed = {row[0] for row in connection.execute(
        "SELECT symbol FROM dataset_watermarks WHERE dataset='bars' AND period='1m' AND row_count>0"
    )}
    active = [row[0] for row in connection.execute(
        "SELECT symbol FROM instruments WHERE instrument_type='etf' AND is_active=1 ORDER BY symbol"
    )]
available = []
for symbol in active:
    code, market = symbol.split('.')
    if data_dir is not None and (data_dir / market / '60' / f'{code}.DAT').is_file():
        available.append(symbol)
print(','.join([symbol for symbol in available if symbol not in completed][:$BatchSize]))
"@
        $minuteSymbols = & $python -c $minuteSelector
        if ($LASTEXITCODE -ne 0) { throw "Could not query local QMT DAT coverage." }
        if ($minuteSymbols) {
            & $python -m dyadtetrade.data.cli `
                --config $config `
                import-qmt-dat `
                --start 20240101 `
                --end 20260718 `
                --markets SH,SZ `
                --instrument-types etf `
                --symbols $minuteSymbols
            exit $LASTEXITCODE
        }
        Write-Host "All locally available ETF minute DAT files are migrated."
    }

    exit 0
}
finally {
    Pop-Location
}
