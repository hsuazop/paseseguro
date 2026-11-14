$ErrorActionPreference = 'Stop'
$installation = Get-Content -Encoding UTF8 -Raw (Join-Path $PSScriptRoot '..\outputs\node-installation.json') | ConvertFrom-Json
$env:Path = "$($installation.NodeDirectory);$($installation.NpmGlobal);$env:Path"
& (Join-Path $installation.NodeDirectory 'npm.cmd') install --global @bubblewrap/cli
if ($LASTEXITCODE -ne 0) { throw 'No se pudo instalar Bubblewrap.' }
Write-Output 'Bubblewrap instalado para el usuario de Windows.'
