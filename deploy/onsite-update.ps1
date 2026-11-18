# Push this repo's current branch to the greenhouse Pi, run the installer, and
# bring the Pi's data home (database snapshot, photos, Wi-Fi surveys) for the
# staging copy. Works without internet: the laptop talks straight to the Pi.
#
#   On site (laptop joined to GreenPi_WiFi):   .\deploy\onsite-update.ps1
#   From anywhere on the VPN:                   .\deploy\onsite-update.ps1 -PiHost 10.8.0.21
#   Only fetch data, no code update:            .\deploy\onsite-update.ps1 -DataOnly
#   Back home, load the data into staging:      .\deploy\push-snapshot.ps1
#
# Needs Git for Windows (winget install Git.Git). The first run adds this
# laptop's SSH key to the Pi (asks for the Pi's admin password once).
param(
    [string]$PiHost = "10.42.0.1",
    [string]$Branch = "",
    [switch]$NoData,
    [switch]$DataOnly
)
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "ssh-key.ps1")
Ensure-GreenPiKey $PiHost

if (-not $DataOnly) {
    if (-not $Branch) { $Branch = (git rev-parse --abbrev-ref HEAD).Trim() }
    $dirty = git status --porcelain
    if ($dirty) { Write-Warning "Uncommitted changes are NOT sent; commit them first if you want them on the Pi." }

    Write-Host "Pushing $Branch to admin@${PiHost}:greenpi ..."
    git push "admin@${PiHost}:greenpi" "${Branch}:${Branch}"
    if ($LASTEXITCODE -ne 0) { throw "git push failed (on site? check you're joined to GreenPi_WiFi)" }

    Write-Host "Running the installer on the Pi ..."
    ssh "admin@$PiHost" "cd ~/greenpi && git checkout -q $Branch && deploy/install.sh"
    if ($LASTEXITCODE -ne 0) { throw "install.sh failed on the Pi" }
}

if (-not $NoData) {
    Write-Host "Taking a fresh database snapshot on the Pi ..."
    ssh "admin@$PiHost" "sudo systemctl start greenpi-backup.service"
    if ($LASTEXITCODE -ne 0) { throw "snapshot failed on the Pi" }
    $db = (ssh "admin@$PiHost" "ls -1 /srv/greenpi-data/backups/db/greenpi-*.sqlite3 | sort | tail -1").Trim()

    $dest = Join-Path $HOME ("greenpi-snapshots\" + (Get-Date -Format "yyyyMMdd-HHmm"))
    New-Item -ItemType Directory -Force "$dest\backups\db" | Out-Null
    Write-Host "Copying data to $dest ..."
    scp -q "admin@${PiHost}:$db" "$dest\backups\db\"
    if ($LASTEXITCODE -ne 0) { throw "copying the database failed" }
    scp -q -r "admin@${PiHost}:/srv/greenpi-data/media" "$dest\"
    scp -q -r "admin@${PiHost}:/srv/greenpi-data/surveys" "$dest\" 2>$null
    $size = "{0:N1} MB" -f ((Get-ChildItem $dest -Recurse -File | Measure-Object Length -Sum).Sum / 1MB)
    Write-Host "Saved $size. Back home on the VPN, run .\deploy\push-snapshot.ps1 to load it into staging."
}
Write-Host "Done. Open http://$PiHost/"
