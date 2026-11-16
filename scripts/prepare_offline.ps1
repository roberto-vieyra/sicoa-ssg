$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
Push-Location $repoRoot
try {
    $nodeExe = (Get-Command node.exe -ErrorAction Stop).Source
    $npmCli = Join-Path (Split-Path (Get-Command npm.cmd -ErrorAction Stop).Source) 'node_modules\npm\bin\npm-cli.js'
    New-Item -ItemType Directory -Force -Path vendor\wheels | Out-Null
    & .\.venv\Scripts\python.exe -m pip download --only-binary=:all: -r requirements-lock.txt -d vendor\wheels
    if ($LASTEXITCODE -ne 0) { throw 'No se completó el almacén de paquetes Python.' }
    Push-Location frontend
    try {
        & $nodeExe $npmCli ci --cache ..\vendor\npm-cache
        if ($LASTEXITCODE -ne 0) { throw 'No se completó el almacén npm.' }
        & $nodeExe $npmCli run build
        if ($LASTEXITCODE -ne 0) { throw 'Falló la compilación.' }
    } finally { Pop-Location }
    Write-Output 'Copie el repositorio y vendor/ al equipo institucional. Ejecute setup.ps1 -Offline con Python 3.12 y Node 22 instalados.'
} finally { Pop-Location }
