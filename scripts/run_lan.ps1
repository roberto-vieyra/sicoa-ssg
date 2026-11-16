[CmdletBinding()]
param([string]$LanIp = '127.0.0.1')
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
$pythonExe = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'frontend\dist\index.html'))) {
    throw 'Ejecute scripts/setup.ps1 para compilar la consola antes del arranque.'
}
& "$PSScriptRoot\post_pull_sync.ps1" -LanIp $LanIp
Push-Location $repoRoot
try {
    Write-Output "SICOA-SSG en http://${LanIp}:5173. Pulse Ctrl+C para detener."
    & $pythonExe -m uvicorn backend.app.main:create_app --factory --host 0.0.0.0 --port 5173
    if ($LASTEXITCODE -ne 0) { throw "La API terminó con código $LASTEXITCODE." }
} finally { Pop-Location }
