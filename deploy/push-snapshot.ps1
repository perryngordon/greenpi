# Load data brought home from the greenhouse (by onsite-update.ps1) into the
# staging copy on pve, so development uses the real greenhouse readings.
#
#   .\deploy\push-snapshot.ps1                 # newest folder in ~\greenpi-snapshots
#   .\deploy\push-snapshot.ps1 -Folder C:\Users\me\greenpi-snapshots\20261120-1430
#
# Needs the VPN up. The first run adds this laptop's SSH key to the staging
# copy (asks for its admin password once).
param(
    [string]$Folder = "",
    [string]$StagingHost = "10.8.0.22"
)
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "ssh-key.ps1")

if (-not $Folder) {
    $Folder = (Get-ChildItem (Join-Path $HOME "greenpi-snapshots") -Directory |
               Sort-Object Name | Select-Object -Last 1).FullName
}
if (-not $Folder -or -not (Test-Path "$Folder\backups\db")) { throw "No snapshot folder found (run onsite-update.ps1 at the greenhouse first)." }
$name = Split-Path $Folder -Leaf

Ensure-GreenPiKey $StagingHost
Write-Host "Uploading $name to staging ..."
ssh "admin@$StagingHost" "rm -rf ~/incoming/$name && mkdir -p ~/incoming"
scp -q -r "$Folder" "admin@${StagingHost}:incoming/"
if ($LASTEXITCODE -ne 0) { throw "upload failed (VPN up?)" }

Write-Host "Loading it ..."
ssh "admin@$StagingHost" "sudo /usr/local/sbin/greenpi-load-snapshot ~/incoming/$name 'laptop copy $name'"
if ($LASTEXITCODE -ne 0) { throw "loading failed on staging" }
Write-Host "Done. Open http://$StagingHost/"
