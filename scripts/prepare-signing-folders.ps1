$ErrorActionPreference = 'Stop'
$signing = Join-Path $env:USERPROFILE '.paseseguro\signing'
$documents = [Environment]::GetFolderPath('MyDocuments')
if (-not $documents) { $documents = Join-Path $env:USERPROFILE 'Documents' }
$backup = Join-Path $documents 'PaseSeguro-Firma'
$sid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
foreach ($directory in @($signing, $backup)) {
    [System.IO.Directory]::CreateDirectory($directory) | Out-Null
    $acl = New-Object System.Security.AccessControl.DirectorySecurity
    $acl.SetOwner($sid)
    $acl.SetAccessRuleProtection($true, $false)
    foreach ($identity in @($sid, [System.Security.Principal.SecurityIdentifier]::new('S-1-5-18'), [System.Security.Principal.SecurityIdentifier]::new('S-1-5-32-544'))) {
        $rule = [System.Security.AccessControl.FileSystemAccessRule]::new($identity, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
        $acl.AddAccessRule($rule)
    }
    Set-Acl -LiteralPath $directory -AclObject $acl
}
@{ SigningDirectory = $signing; BackupDirectory = $backup } | ConvertTo-Json | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $PSScriptRoot '..\outputs\signing-locations.json')
Write-Output 'Carpetas de firma y respaldo creadas con acceso restringido al usuario, administradores y SYSTEM.'
