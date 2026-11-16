[CmdletBinding()]
param([string]$LanIp = '127.0.0.1', [switch]$Offline, [string]$Wheelhouse = 'vendor\wheels')
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
Push-Location $repoRoot
try {
    $nodeExe = (Get-Command node.exe -ErrorAction Stop).Source
    $npmCli = Join-Path (Split-Path (Get-Command npm.cmd -ErrorAction Stop).Source) 'node_modules\npm\bin\npm-cli.js'
    $nodeVersion = & $nodeExe --version
    if ($LASTEXITCODE -ne 0 -or $nodeVersion -notmatch '^v22\.' -or [version]$nodeVersion.TrimStart('v') -lt [version]'22.13') {
        throw 'Se requiere Node.js 22 (22.13 o posterior).'
    }
    if (-not (Test-Path '.venv\Scripts\python.exe')) {
        & python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear el entorno virtual. Se requiere Python 3.12.' }
    }
    if ($Offline) { & .\.venv\Scripts\python.exe -m pip install --no-index --find-links $Wheelhouse -r requirements-lock.txt }
    else { & .\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt }
    if ($LASTEXITCODE -ne 0) { throw 'Falló la instalación de Python.' }
    Push-Location frontend
    try {
        if ($Offline) { & $nodeExe $npmCli ci --offline --cache ..\vendor\npm-cache } else { & $nodeExe $npmCli ci }
        if ($LASTEXITCODE -ne 0) { throw 'Falló la instalación del frontend.' }
        & $nodeExe $npmCli run build
        if ($LASTEXITCODE -ne 0) { throw 'Falló la compilación del frontend.' }
    } finally { Pop-Location }
    & "$PSScriptRoot\post_pull_sync.ps1" -LanIp $LanIp
} finally { Pop-Location }
