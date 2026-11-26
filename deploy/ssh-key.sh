# Sourced by onsite-update.sh / push-snapshot.sh (macOS or Linux).
# Makes sure this laptop can log in to admin@<host> with its own SSH key, so
# later steps don't ask for a password. The first time per host it asks for
# that host's admin password once (the Pi: its Linux admin password;
# staging: the greenpi web admin password).
ensure_greenpi_key() {
    target="$1"
    if ssh -o BatchMode=yes -o ConnectTimeout=10 "admin@$target" true 2>/dev/null; then
        return 0
    fi
    key="$HOME/.ssh/id_ed25519"
    if [ ! -f "$key.pub" ]; then
        echo "Creating an SSH key for this laptop (just press Enter at the passphrase prompts) ..."
        mkdir -p "$HOME/.ssh" && chmod 700 "$HOME/.ssh"
        ssh-keygen -t ed25519 -f "$key" -C "$(hostname -s) greenpi"
    fi
    echo "Adding this laptop's key to admin@$target (enter that admin password once) ..."
    ssh "admin@$target" 'umask 077; mkdir -p ~/.ssh; cat >> ~/.ssh/authorized_keys' < "$key.pub" \
        || { echo "could not add the key on $target" >&2; return 1; }
}
