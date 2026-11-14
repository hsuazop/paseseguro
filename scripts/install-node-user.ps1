$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$nodeRoot = Join-Path $env:LOCALAPPDATA 'Programs\NodeJS'
$npmGlobal = Join-Path $env:APPDATA 'npm'
$releases = Invoke-RestMethod -Uri 'https://nodejs.org/dist/index.json'
$release = $releases | Where-Object { $_.lts -and $_.files -contains 'win-x64-zip' } | Select-Object -First 1
if (-not $release) { throw 'No se encontró una versión LTS de Node.js para Windows x64.' }
$archiveName = "node-$($release.version)-win-x64.zip"
$baseUrl = "https://nodejs.org/dist/$($release.version)"
$nodeDirectory = Join-Path $nodeRoot "node-$($release.version)-win-x64"
$downloadDirectory = Join-Path $env:TEMP ([System.IO.Path]::GetRandomFileName())
[System.IO.Directory]::CreateDirectory($downloadDirectory) | Out-Null
$archivePath = Join-Path $downloadDirectory $archiveName
Invoke-WebRequest -UseBasicParsing -Uri "$baseUrl/$archiveName" -OutFile $archivePath
$sums = (Invoke-WebRequest -UseBasicParsing -Uri "$baseUrl/SHASUMS256.txt").Content
if ($sums -is [byte[]]) { $sums = [System.Text.Encoding]::UTF8.GetString($sums) }
$expectedLine = ($sums -split "`n" | Where-Object { $_.Trim().EndsWith("  $archiveName") })
if (-not $expectedLine) { throw 'No se encontró el SHA-256 oficial del archivo de Node.js.' }
$expected = ($expectedLine.Trim() -split '\s+')[0]
$actual = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash
if ($actual -ne $expected) { throw 'El SHA-256 de Node.js no coincide con el oficial.' }
if (-not (Test-Path -LiteralPath $nodeDirectory)) {
    Expand-Archive -LiteralPath $archivePath -DestinationPath $nodeRoot
}
if (-not (Test-Path -LiteralPath (Join-Path $nodeDirectory 'node.exe'))) { throw 'No se encontró node.exe tras extraer Node.js.' }
$oldUserPath = [Environment]::GetEnvironmentVariable('Path', 'User')
$backupPath = Join-Path $PSScriptRoot '..\.env.node-path-backup.json'
if (-not (Test-Path -LiteralPath $backupPath)) {
    @{ OriginalUserPath = $oldUserPath } | ConvertTo-Json | Set-Content -Encoding UTF8 -LiteralPath $backupPath
}
$entries = @($nodeDirectory, $npmGlobal) + @($oldUserPath -split ';' | Where-Object { $_ -and $_ -ne $nodeDirectory -and $_ -ne $npmGlobal })
[Environment]::SetEnvironmentVariable('Path', ($entries -join ';'), 'User')
$env:Path = "$nodeDirectory;$npmGlobal;$env:Path"
[System.IO.Directory]::CreateDirectory($npmGlobal) | Out-Null
& (Join-Path $nodeDirectory 'npm.cmd') config set prefix $npmGlobal
if ($LASTEXITCODE -ne 0) { throw 'No se pudo configurar el directorio global de npm.' }
$version = & (Join-Path $nodeDirectory 'node.exe') --version
$npmVersion = & (Join-Path $nodeDirectory 'npm.cmd') --version
@{ NodeDirectory = $nodeDirectory; NodeVersion = $version; NpmVersion = $npmVersion; NpmGlobal = $npmGlobal } | ConvertTo-Json | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $PSScriptRoot '..\outputs\node-installation.json')
Write-Output "Node.js $version y npm $npmVersion instalados para el usuario de Windows."
Write-Output "Directorio: $nodeDirectory"
Write-Output "Globales npm: $npmGlobal"
