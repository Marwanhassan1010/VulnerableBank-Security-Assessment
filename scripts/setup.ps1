param([string]$Python = 'python', [string]$Node = 'node', [string]$Pnpm = 'pnpm')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $projectRoot
New-Item -ItemType Directory -Path '.runtime' -Force | Out-Null
$nodePath = (Get-Command $Node).Source
$pythonPath = (Get-Command $Python).Source
if (!(Test-Path '.venv/Scripts/python.exe')) { & $pythonPath -m venv .venv --without-pip; if ($LASTEXITCODE) { throw 'Could not create Python environment' } }
& $pythonPath -m pip --python '.venv/Scripts/python.exe' install -r backend/requirements.lock.txt
if ($LASTEXITCODE) { throw 'Python installation failed' }
$env:NODE_USE_SYSTEM_CA = '1'
& $Pnpm install --frozen-lockfile --dangerously-allow-all-builds --store-dir '.runtime/pnpm-store' --config.node-linker=hoisted
if ($LASTEXITCODE) { throw 'Frontend installation failed' }
& $nodePath node_modules/vite/bin/vite.js build --config frontend/vite.config.js
if ($LASTEXITCODE) { throw 'Frontend build failed' }
@{node=$nodePath;python=$pythonPath} | ConvertTo-Json | Set-Content '.runtime/tools.json'
Write-Host 'Ready. Run scripts/start.ps1.'
