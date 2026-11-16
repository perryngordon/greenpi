# Push this repo's current branch to the greenhouse Pi and run the installer.
# Works without internet: the laptop talks straight to the Pi.
#
#   On site (laptop joined to GreenPi_WiFi):   .\deploy\onsite-update.ps1
#   From anywhere on the VPN:                   .\deploy\onsite-update.ps1 -PiHost 10.8.0.21
#
# Needs Git for Windows (winget install Git.Git). Logs in as admin on the Pi
# (password, or an SSH key you've added to the Pi).
param(
    [string]$PiHost = "10.42.0.1",
    [string]$Branch = ""
)
$ErrorActionPreference = "Stop"

if (-not $Branch) { $Branch = (git rev-parse --abbrev-ref HEAD).Trim() }
$dirty = git status --porcelain
if ($dirty) { Write-Warning "Uncommitted changes are NOT sent; commit them first if you want them on the Pi." }

Write-Host "Pushing $Branch to admin@${PiHost}:greenpi ..."
git push "admin@${PiHost}:greenpi" "${Branch}:${Branch}"
if ($LASTEXITCODE -ne 0) { throw "git push failed (on site? check you're joined to GreenPi_WiFi)" }

Write-Host "Running the installer on the Pi ..."
ssh "admin@$PiHost" "cd ~/greenpi && git checkout -q $Branch && deploy/install.sh"
if ($LASTEXITCODE -ne 0) { throw "install.sh failed on the Pi" }
Write-Host "Done. Open http://$PiHost/"
