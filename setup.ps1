# Downloads the portable Python runtime (official embeddable package from python.org)
# into runtime\ and verifies its SHA-256. Only needed once, e.g. after a fresh git clone.

param(
    [switch]$Force,                                       # re-download even if runtime\ exists
    [string]$RuntimeDir = (Join-Path $PSScriptRoot 'runtime')
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'                  # makes Invoke-WebRequest much faster

# Stay on 3.13: from 3.14 on, Windows builds use zlib-ng, which compresses differently.
# Still valid, but 3.13's classic zlib keeps the output byte-identical to the original tool.
$Version = '3.13.16'
$Sha256  = '97dae5274cc54867065e8d5a3226e48c35017ed332a0fdb0e27d5b5821961297'
$Url     = "https://www.python.org/ftp/python/$Version/python-$Version-embed-amd64.zip"

$python = Join-Path $RuntimeDir 'python.exe'
if ((Test-Path $python) -and -not $Force) {
    Write-Host "  Runtime already installed: $(& $python --version)"
    exit 0
}

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$zip = Join-Path $env:TEMP "python-$Version-embed-amd64.zip"

Write-Host "  Downloading Python $Version (embeddable, ~12 MB) from python.org ..."
Invoke-WebRequest -Uri $Url -OutFile $zip -UseBasicParsing

$hash = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLower()
if ($hash -ne $Sha256) {
    Remove-Item $zip -Force
    throw "Checksum mismatch - download is corrupt or was modified. Expected $Sha256, got $hash"
}
Write-Host "  Checksum OK"

if (Test-Path $RuntimeDir) { Remove-Item $RuntimeDir -Recurse -Force }
Expand-Archive -Path $zip -DestinationPath $RuntimeDir
Remove-Item $zip -Force

Write-Host "  Installed $(& $python --version) to $RuntimeDir"
Write-Host "  Done - start the tool with: .\rxp"
