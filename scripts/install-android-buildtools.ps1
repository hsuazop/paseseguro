$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$tools = Get-Content -Encoding UTF8 -Raw (Join-Path $PSScriptRoot '..\outputs\android-tools.json') | ConvertFrom-Json
$target = Join-Path $tools.SdkDirectory 'build-tools\36.1.0'
if (Test-Path -LiteralPath (Join-Path $target 'zipalign.exe')) { Write-Output 'Android Build Tools 36.1.0 disponibles.'; exit 0 }
[xml]$repository = (Invoke-WebRequest -UseBasicParsing 'https://dl.google.com/android/repository/repository2-3.xml').Content
$package = $repository.SelectNodes("//*[local-name()='remotePackage' and @path='build-tools;36.1.0']") | Select-Object -First 1
$archive = $package.archives.archive | Where-Object { $_.'host-os' -eq 'windows' } | Select-Object -First 1
if (-not $archive) { throw 'No se encontró Android Build Tools 36.1.0 para Windows.' }
$downloads = Join-Path $env:USERPROFILE '.paseseguro\tools\downloads'
$zip = Join-Path $downloads ([System.IO.Path]::GetFileName($archive.complete.url))
if (-not (Test-Path -LiteralPath $zip)) { Invoke-WebRequest -UseBasicParsing ("https://dl.google.com/android/repository/" + $archive.complete.url) -OutFile $zip }
$algorithm = $archive.complete.checksum.type.ToUpper().Replace('-', '')
if ((Get-FileHash -LiteralPath $zip -Algorithm $algorithm).Hash -ne $archive.complete.checksum.InnerText) { throw 'El checksum de Android Build Tools no coincide.' }
$unpack = Join-Path $downloads ('buildtools-' + [System.IO.Path]::GetRandomFileName())
Expand-Archive -LiteralPath $zip -DestinationPath $unpack
$source = Get-ChildItem -LiteralPath $unpack -Directory | Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'zipalign.exe') } | Select-Object -First 1
if (-not $source) { throw 'No se encontró zipalign.exe en el archivo verificado.' }
[System.IO.Directory]::CreateDirectory($target) | Out-Null
Get-ChildItem -LiteralPath $source.FullName -Force | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $target -Recurse }
Write-Output 'Android Build Tools 36.1.0 descargados y verificados.'
