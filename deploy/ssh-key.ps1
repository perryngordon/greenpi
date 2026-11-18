# Dot-sourced by the other deploy scripts: make sure this laptop can log in to
# admin@<host> with its own SSH key, so later steps don't ask for a password.
# First time per host it asks for that host's admin password once.
function Ensure-GreenPiKey([string]$TargetHost) {
    ssh -o BatchMode=yes -o ConnectTimeout=10 "admin@$TargetHost" true 2>$null
    if ($LASTEXITCODE -eq 0) { return }
    $key = Join-Path $HOME ".ssh\id_ed25519"
    if (-not (Test-Path "$key.pub")) {
        Write-Host "Creating an SSH key for this laptop (just press Enter at the passphrase prompts) ..."
        New-Item -ItemType Directory -Force (Split-Path $key) | Out-Null
        ssh-keygen -t ed25519 -f $key -C "$env:COMPUTERNAME greenpi"
    }
    $pub = (Get-Content "$key.pub" -Raw).Trim()
    Write-Host "Adding this laptop's key to admin@$TargetHost (enter that admin password once) ..."
    # No embedded quotes (Windows PowerShell 5.1 mangles them for native commands);
    # tr strips the CR that PowerShell's pipe adds.
    $pub | ssh "admin@$TargetHost" "umask 077; mkdir -p ~/.ssh; tr -d \\r >> ~/.ssh/authorized_keys"
    if ($LASTEXITCODE -ne 0) { throw "could not add the key on $TargetHost" }
}
