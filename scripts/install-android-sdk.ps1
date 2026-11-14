$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$toolsRoot = Join-Path $env:USERPROFILE '.paseseguro\tools'
$downloads = Join-Path $toolsRoot 'downloads'
[System.IO.Directory]::CreateDirectory($downloads) | Out-Null

$jdkAssets = Invoke-RestMethod 'https://api.adoptium.net/v3/assets/latest/17/hotspot?architecture=x64&image_type=jdk&os=windows&vendor=eclipse'
$jdkAsset = $jdkAssets | Select-Object -First 1
$jdkZip = Join-Path $downloads $jdkAsset.binary.package.name
Write-Output "Descargando JDK $($jdkAsset.version.semver) de Adoptium."
if (-not (Test-Path -LiteralPath $jdkZip)) {
    Invoke-WebRequest -UseBasicParsing $jdkAsset.binary.package.link -OutFile $jdkZip
}
if ((Get-FileHash -LiteralPath $jdkZip -Algorithm SHA256).Hash -ne $jdkAsset.binary.package.checksum) { throw 'El SHA-256 del JDK no coincide.' }
$jdkDirectory = Join-Path $toolsRoot "jdk-$($jdkAsset.version.openjdk_version)"
if (-not (Test-Path -LiteralPath (Join-Path $jdkDirectory 'bin\java.exe'))) {
    Expand-Archive -LiteralPath $jdkZip -DestinationPath $toolsRoot
}
if (-not (Test-Path -LiteralPath (Join-Path $jdkDirectory 'bin\java.exe'))) { throw 'No se encontró el JDK extraído.' }
Write-Output 'JDK verificado e instalado.'

[xml]$repository = (Invoke-WebRequest -UseBasicParsing 'https://dl.google.com/android/repository/repository2-3.xml').Content
$package = $repository.SelectNodes("//*[local-name()='remotePackage' and @path='cmdline-tools;latest']") | Select-Object -First 1
$archive = $package.archives.archive | Where-Object { $_.'host-os' -eq 'windows' } | Select-Object -First 1
if (-not $archive) { throw 'No se encontraron herramientas oficiales Android para Windows.' }
$sdkZip = Join-Path $downloads $archive.complete.url
Write-Output 'Descargando Android Command Line Tools de Google.'
if (-not (Test-Path -LiteralPath $sdkZip)) {
    Invoke-WebRequest -UseBasicParsing ("https://dl.google.com/android/repository/" + $archive.complete.url) -OutFile $sdkZip
}
$algorithm = $archive.complete.checksum.type.ToUpper().Replace('-', '')
if ((Get-FileHash -LiteralPath $sdkZip -Algorithm $algorithm).Hash -ne $archive.complete.checksum.InnerText) { throw 'El checksum de Android SDK no coincide.' }
$sdkDirectory = Join-Path $toolsRoot 'android-sdk'
$commandLineDirectory = Join-Path $sdkDirectory 'cmdline-tools\latest'
if (-not (Test-Path -LiteralPath (Join-Path $commandLineDirectory 'bin\sdkmanager.bat'))) {
    $unpack = Join-Path $toolsRoot ('unpack-' + [System.IO.Path]::GetRandomFileName())
    Expand-Archive -LiteralPath $sdkZip -DestinationPath $unpack
    [System.IO.Directory]::CreateDirectory($commandLineDirectory) | Out-Null
    Get-ChildItem -LiteralPath (Join-Path $unpack 'cmdline-tools') -Force | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $commandLineDirectory -Recurse
    }
}
$bubblewrapDirectory = Join-Path $env:USERPROFILE '.bubblewrap'
[System.IO.Directory]::CreateDirectory($bubblewrapDirectory) | Out-Null
# Keep the standard SDK layout and provide the entry point expected by Bubblewrap.
$compatibilityBin = Join-Path $sdkDirectory 'bin'
[System.IO.Directory]::CreateDirectory($compatibilityBin) | Out-Null
@('@echo off', 'call "%~dp0..\cmdline-tools\latest\bin\sdkmanager.bat" %*') | Set-Content -Encoding ASCII -LiteralPath (Join-Path $compatibilityBin 'sdkmanager.bat')
$config = @{ jdkPath = $jdkDirectory; androidSdkPath = $sdkDirectory }
$config | ConvertTo-Json | Set-Content -Encoding ASCII -LiteralPath (Join-Path $bubblewrapDirectory 'config.json')
@{ JdkDirectory=$jdkDirectory; SdkDirectory=$sdkDirectory; CommandLineDirectory=$commandLineDirectory } | ConvertTo-Json | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $PSScriptRoot '..\outputs\android-tools.json')
Write-Output "JDK: $jdkDirectory"
Write-Output "SDK: $sdkDirectory"
Write-Output 'Herramientas Android descargadas y verificadas.'
