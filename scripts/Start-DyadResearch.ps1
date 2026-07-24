[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$frontend = Join-Path $projectRoot "frontend\dist\index.html"
$url = "http://127.0.0.1:8000"
$healthUrl = "$url/api/health"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Python environment not found: $python"
}
if (-not (Test-Path -LiteralPath $frontend)) {
    throw "Frontend build not found. Run: pnpm --dir frontend build"
}

try {
    $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
    if ($health.ok) {
        Start-Process $url
        Write-Host "DyadResearch is already running at $url"
        exit 0
    }
}
catch {
    # The local service is not running yet.
}

$process = Start-Process `
    -FilePath $python `
    -ArgumentList @("-m", "dyadresearch.web") `
    -WorkingDirectory $projectRoot `
    -WindowStyle Hidden `
    -PassThru

for ($attempt = 0; $attempt -lt 30; $attempt++) {
    Start-Sleep -Milliseconds 250
    try {
        $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
        if ($health.ok) {
            Start-Process $url
            Write-Host "DyadResearch started at $url (PID $($process.Id))"
            exit 0
        }
    }
    catch {
        if ($process.HasExited) {
            throw "DyadResearch stopped before becoming ready."
        }
    }
}

Stop-Process -Id $process.Id -ErrorAction SilentlyContinue
throw "DyadResearch did not become ready within 7.5 seconds."
