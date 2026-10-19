$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$processFile = Join-Path $projectRoot '.runtime/processes.json'
if (!(Test-Path $processFile)) { Write-Host 'No managed app processes.'; exit 0 }
$managed = Get-Content $processFile -Raw | ConvertFrom-Json
$apiProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$($managed.api)" -ErrorAction SilentlyContinue
if ($apiProcess -and $apiProcess.CommandLine -like '*uvicorn backend.main:app*') { Stop-Process -Id $managed.api -ErrorAction SilentlyContinue }
$tools = Get-Content (Join-Path $projectRoot '.runtime/tools.json') -Raw | ConvertFrom-Json
$pgctl = Join-Path $projectRoot 'node_modules/@embedded-postgres/windows-x64/native/bin/pg_ctl.exe'
if (Test-Path $pgctl) { & $pgctl -D (Join-Path $projectRoot 'data/postgres') -m fast -w stop }
$dbProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$($managed.database)" -ErrorAction SilentlyContinue
if ($dbProcess -and $dbProcess.CommandLine -like '*scripts/database.mjs*') { Stop-Process -Id $managed.database -ErrorAction SilentlyContinue }
Remove-Item -LiteralPath $processFile
Write-Host 'VulnerableBank stopped. Data preserved.'
