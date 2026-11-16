[CmdletBinding()]
param([switch]$ForceSqlite, [string]$LanIp = '127.0.0.1')
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
$pythonExe = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Ejecute scripts/setup.ps1 para preparar Python y las dependencias.' }
$parsedIp = $null
if (-not [System.Net.IPAddress]::TryParse($LanIp, [ref]$parsedIp) -or $parsedIp.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork) { throw 'LanIp debe ser una dirección IPv4 válida.' }
$dataPath = Join-Path $repoRoot 'data'
$backupPath = Join-Path $dataPath ('backups\' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
New-Item -ItemType Directory -Force -Path $backupPath | Out-Null
$envPath = Join-Path $repoRoot '.env'
$frontendEnv = Join-Path $repoRoot 'frontend\.env.local'
foreach ($item in @($envPath, $frontendEnv)) {
    if (Test-Path -LiteralPath $item) {
        $backupName = if ($item -eq $envPath) { 'backend.env' } else { 'frontend.env.local' }
        Copy-Item -LiteralPath $item -Destination (Join-Path $backupPath $backupName)
    }
}
$sqlitePath = Join-Path $dataPath 'sicoa_ssg.db'
Push-Location $repoRoot
try {
    if (Test-Path -LiteralPath $sqlitePath) {
        & $pythonExe -m backend.app.cli backup --source $sqlitePath --target (Join-Path $backupPath 'sicoa_ssg.db')
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear el respaldo consistente de SQLite.' }
    }
    $encoding = [System.Text.UTF8Encoding]::new($false)
    $envText = if (Test-Path -LiteralPath $envPath) { [IO.File]::ReadAllText($envPath) } else { [IO.File]::ReadAllText((Join-Path $repoRoot '.env.example')) }
    function Set-EnvValue([string]$Content, [string]$Key, [string]$Value) {
        $pattern = '(?m)^' + [regex]::Escape($Key) + '=[^\r\n]*'
        $replacement = $Key + '=' + $Value
        if ([regex]::IsMatch($Content, $pattern)) {
            return [regex]::Replace($Content, $pattern, [System.Text.RegularExpressions.MatchEvaluator]{ param($match) $replacement })
        }
        $newline = if ($Content.Contains("`n") -and -not $Content.Contains("`r`n")) { "`n" } else { "`r`n" }
        if ($Content.Length -gt 0 -and -not $Content.EndsWith("`n")) { $Content += $newline }
        return $Content + $replacement + $newline
    }
    if ($ForceSqlite) { $envText = Set-EnvValue $envText 'DATABASE_URL' 'sqlite:///./data/sicoa_ssg.db' }
    $corsMatch = [regex]::Match($envText, '(?m)^CORS_ORIGINS=(.*)$')
    $origins = @()
    if ($corsMatch.Success) {
        $raw = $corsMatch.Groups[1].Value.Trim().Trim("'")
        if ($raw.StartsWith('[')) { $origins = @($raw | ConvertFrom-Json) } else { $origins = @($raw.Split(',') | ForEach-Object { $_.Trim() }) }
    }
    $origins = @($origins + @("http://${LanIp}:5173", 'http://127.0.0.1:5173') | Where-Object { $_ } | Select-Object -Unique)
    $corsJson = ConvertTo-Json -InputObject $origins -Compress
    $envText = Set-EnvValue $envText 'CORS_ORIGINS' $corsJson
    [IO.File]::WriteAllText($envPath, $envText, $encoding)
    $frontText = if (Test-Path -LiteralPath $frontendEnv) { [IO.File]::ReadAllText($frontendEnv) } else { '' }
    $frontText = Set-EnvValue $frontText 'VITE_API_BASE_URL' '/api'
    $frontText = Set-EnvValue $frontText 'API_PROXY_TARGET' 'http://127.0.0.1:8000'
    [IO.File]::WriteAllText($frontendEnv, $frontText, $encoding)
    # La configuración del archivo recién actualizado tiene prioridad para esta sincronización.
    $oldDatabase = $env:DATABASE_URL
    $oldCors = $env:CORS_ORIGINS
    try {
        Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
        Remove-Item Env:CORS_ORIGINS -ErrorAction SilentlyContinue
        & $pythonExe -m backend.app.cli sync
        if ($LASTEXITCODE -ne 0) { throw 'Falló la sincronización. El respaldo permanece disponible.' }
    } finally {
        if ($null -ne $oldDatabase) { $env:DATABASE_URL = $oldDatabase }
        if ($null -ne $oldCors) { $env:CORS_ORIGINS = $oldCors }
    }
    Write-Output "Sincronización completada. Respaldo: $backupPath"
    Write-Output "Acceso LAN: http://${LanIp}:5173"
} finally { Pop-Location }
