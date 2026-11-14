$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
Add-Type -AssemblyName System.IO.Compression.FileSystem
$tools = Get-Content -Encoding UTF8 -Raw (Join-Path $PSScriptRoot '..\outputs\android-tools.json') | ConvertFrom-Json
$downloads = Join-Path $env:USERPROFILE '.paseseguro\tools\downloads'
function Install-VerifiedArchive($archive, $baseUrl, $destination, $marker) {
    $verified = $marker + '.paseseguro-verified'
    if (Test-Path -LiteralPath $verified) { return }
    $zip = Join-Path $downloads ([System.IO.Path]::GetFileName($archive.complete.url))
    Write-Output ("Descargando " + $archive.complete.url)
    if (-not (Test-Path -LiteralPath $zip)) { Invoke-WebRequest -UseBasicParsing ($baseUrl + $archive.complete.url) -OutFile $zip }
    $algorithm = $archive.complete.checksum.type.ToUpper().Replace('-', '')
    if ((Get-FileHash -LiteralPath $zip -Algorithm $algorithm).Hash -ne $archive.complete.checksum.InnerText) { throw 'Checksum del emulador o imagen incorrecto.' }
    [System.IO.Directory]::CreateDirectory($destination) | Out-Null
    Write-Output ("Extrayendo " + $archive.complete.url)
    & tar.exe -xf $zip -C $destination
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo extraer el paquete Android verificado.' }
    if (-not (Test-Path -LiteralPath $marker)) { throw "No se encontró el archivo esperado: $marker" }
    [System.IO.File]::WriteAllText($verified, 'Verified official Android archive')
}
[xml]$repository = (Invoke-WebRequest -UseBasicParsing 'https://dl.google.com/android/repository/repository2-3.xml').Content
$package = $repository.SelectNodes("//*[local-name()='remotePackage' and @path='emulator']") | Select-Object -First 1
$archive = $package.archives.archive | Where-Object { $_.'host-os' -eq 'windows' } | Select-Object -First 1
Install-VerifiedArchive $archive 'https://dl.google.com/android/repository/' $tools.SdkDirectory (Join-Path $tools.SdkDirectory 'emulator\emulator.exe')
[xml]$images = (Invoke-WebRequest -UseBasicParsing 'https://dl.google.com/android/repository/sys-img/google_apis/sys-img2-3.xml').Content
$image = $images.SelectNodes("//*[local-name()='remotePackage' and @path='system-images;android-36;google_apis;x86_64']") | Select-Object -First 1
$imageParent = Join-Path $tools.SdkDirectory 'system-images\android-36\google_apis'
$imageDirectory = Join-Path $imageParent 'x86_64'
Install-VerifiedArchive $image.archives.archive 'https://dl.google.com/android/repository/sys-img/google_apis/' $imageParent (Join-Path $imageDirectory 'system.img')
@{ SdkDirectory=$tools.SdkDirectory; Emulator=(Join-Path $tools.SdkDirectory 'emulator\emulator.exe'); ImageDirectory=$imageDirectory } | ConvertTo-Json | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $PSScriptRoot '..\outputs\android\emulator-tools.json')
Write-Output 'Emulador e imagen Android 16 instalados y verificados.'
