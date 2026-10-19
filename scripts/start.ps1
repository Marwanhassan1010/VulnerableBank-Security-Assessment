$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $projectRoot
$runtimeFile = Join-Path $projectRoot '.runtime/tools.json'
if (!(Test-Path -LiteralPath $runtimeFile)) { throw 'Run scripts/setup.ps1 first.' }
$tools = Get-Content -LiteralPath $runtimeFile -Raw | ConvertFrom-Json
New-Item -ItemType Directory -Path '.runtime' -Force | Out-Null
# Prevent simultaneous double-clicks from starting two database processes.
try { $launchLock = [System.IO.File]::Open((Join-Path $projectRoot '.runtime/start.lock'), 'OpenOrCreate', 'ReadWrite', 'None') }
catch { throw 'VulnerableBank is already starting. Please wait for that launch to finish.' }
try {
    try {
        $health = Invoke-RestMethod 'http://127.0.0.1:8000/api/health' -TimeoutSec 3
        if ($health.status -eq 'ok' -and $health.mode -eq 'synthetic-local-baseline') {
            Write-Host 'VulnerableBank is already running at http://127.0.0.1:8000'
            exit 0
        }
    } catch {}
    if (Get-NetTCPConnection -State Listen -LocalPort 8000 -ErrorAction SilentlyContinue) { throw 'Port 8000 is already in use by another application.' }
    $readyFile = Join-Path $projectRoot '.runtime/database-ready'
    $pgctl = Join-Path $projectRoot 'node_modules/@embedded-postgres/windows-x64/native/bin/pg_ctl.exe'
    $dataPath = Join-Path $projectRoot 'data/postgres'
    $databaseProcessId = 0
    & $pgctl -D $dataPath status *> $null
    $databaseRunning = $LASTEXITCODE -eq 0
    if ($databaseRunning) {
        # Verify this exact cluster and reuse it after a partially completed launch.
        Write-Host 'Using the existing VulnerableBank PostgreSQL database.'
        if (Test-Path $readyFile) { [int]::TryParse((Get-Content $readyFile -Raw).Trim(), [ref]$databaseProcessId) | Out-Null }
    } else {
        if (Get-NetTCPConnection -State Listen -LocalPort 55432 -ErrorAction SilentlyContinue) { throw 'Port 55432 is in use by a different database. No process was stopped.' }
        if (Test-Path $readyFile) { Remove-Item -LiteralPath $readyFile }
        $dbProcess = Start-Process -FilePath $tools.node -ArgumentList 'scripts/database.mjs' -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput '.runtime/database.log' -RedirectStandardError '.runtime/database-error.log'
        $databaseProcessId = $dbProcess.Id
        $deadline = (Get-Date).AddSeconds(60)
        while (!(Test-Path $readyFile)) {
            $dbProcess.Refresh()
            if ($dbProcess.HasExited) {
                $details = Get-Content '.runtime/database-error.log' -Tail 20 -ErrorAction SilentlyContinue
                throw "Database failed to start:`n$($details -join [Environment]::NewLine)"
            }
            if ((Get-Date) -gt $deadline) { throw 'Database did not start within 60 seconds. See .runtime/database-error.log.' }
            Start-Sleep -Milliseconds 300
        }
    }
    $apiProcess = Start-Process -FilePath (Join-Path $projectRoot '.venv/Scripts/python.exe') -ArgumentList '-m','uvicorn','backend.main:app','--host','127.0.0.1','--port','8000' -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput '.runtime/api.log' -RedirectStandardError '.runtime/api-error.log'
    @{ database = $databaseProcessId; api = $apiProcess.Id } | ConvertTo-Json | Set-Content '.runtime/processes.json'
    $deadline = (Get-Date).AddSeconds(30)
    do {
        Start-Sleep -Milliseconds 300
        try { $health = Invoke-RestMethod 'http://127.0.0.1:8000/api/health' -TimeoutSec 2; break }
        catch {
            $apiProcess.Refresh()
            if ($apiProcess.HasExited -or (Get-Date) -gt $deadline) {
                $details = Get-Content '.runtime/api-error.log' -Tail 20 -ErrorAction SilentlyContinue
                throw "Web app failed to start:`n$($details -join [Environment]::NewLine)"
            }
        }
    } while ($true)
    Write-Host 'VulnerableBank is ready: http://127.0.0.1:8000'
    Write-Host 'Demo logins: .runtime/demo-accounts.json'
    Write-Host 'Stop: double-click Stop VulnerableBank.cmd'
} finally { $launchLock.Dispose() }
