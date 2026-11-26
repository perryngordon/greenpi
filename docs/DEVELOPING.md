# Developing GreenPi on your own laptop

This is the guide for a second maintainer: everything needed to keep
developing and deploying GreenPi from a Mac (Linux works the same), with
Claude Code as a helper, without the repo owner's servers or VPN.

You'll work in three places:

| Where | What happens there |
|---|---|
| **Your laptop** | Code changes, testing with simulated sensors + real greenhouse data |
| **The greenhouse** | The Pi. Your laptop joins its `GreenPi_WiFi` hotspot (no internet needed) to install updates and bring data home |
| **GitHub** | Where the code lives (`perryngordon/greenpi`, branch `step1-services`). Ask the owner for collaborator access to push |

## 1. One-time setup

1. **Tools** (Terminal):
   ```bash
   xcode-select --install             # git + compilers, if not already there
   brew install python@3.12           # https://brew.sh first if you don't have Homebrew
   ```
2. **Claude Code**: needs a Claude subscription (Pro or Max) or an
   Anthropic Console account. Install from https://claude.com/claude-code
   (e.g. `curl -fsSL https://claude.ai/install.sh | bash`), then run `claude`
   once to log in.
3. **The code and a local copy of the app:**
   ```bash
   git clone -b step1-services https://github.com/perryngordon/greenpi.git ~/greenpi
   cd ~/greenpi
   deploy/setup-local.sh       # makes venv/, installs packages, builds the database, runs the tests
   ```
   It asks you to choose a password for the local `admin` web account (only
   on your laptop).
4. **Passwords to keep in your password manager** (get them from the owner):
   - `GreenPi_WiFi` hotspot password (also on the QR sign)
   - the Pi's Linux `admin` password (needed once, the first time your laptop
     connects; after that your SSH key is used)
   - your own web account on the Pi (an admin creates it on the People page)

## 2. Everyday development

```bash
cd ~/greenpi
deploy/run-local.sh          # app at http://127.0.0.1:8000/ with simulated sensors; Ctrl-C stops it
claude                       # in another Terminal tab, in ~/greenpi
```

- "Staging mode" (`GREENPI_STAGING=1`, set by the scripts) means: sensors are
  simulated (a believable Ward winter, an outside sensor with pressure, a soil
  probe that dries out over 4 days), network changes are saved but never
  applied, and a yellow banner says it's not the real greenhouse.
- Claude Code reads `CLAUDE.md` automatically: architecture, hardware,
  gotchas. Ask it to make a change, run `venv/bin/python manage.py test`, and
  click through the page before deploying.
- Commit when something works: `git add -A && git commit -m "what changed"`.
  When you have internet, `git push` so the change is backed up on GitHub.

## 3. A greenhouse visit

1. At home (internet): `git pull` so you have the latest code.
2. At the greenhouse: join **GreenPi_WiFi** (the Mac will say "no internet";
   that's expected), then:
   ```bash
   cd ~/greenpi
   deploy/onsite-update.sh
   ```
   That one command:
   - sets the Pi's clock from your laptop if it has drifted,
   - sends your committed code to the Pi and runs its installer,
   - takes a fresh database snapshot and copies it, the photos and the Wi-Fi
     surveys to `~/greenpi-snapshots/<date-time>/`.

   The first time it asks to trust the Pi (`yes`) and for the Pi's admin
   password once. Options: `--data-only` (no code update), `--no-data`.
3. Check http://10.42.0.1/ (or http://greenhouse.lan/) on your phone.
4. Back home: `deploy/load-local.sh` loads that data into your laptop's copy
   (it never touches the Pi; Wi-Fi passwords are blanked), then
   `deploy/run-local.sh` to develop against the real readings.

## 4. If an update goes wrong

The Pi keeps working on the old code if the installer fails partway. To go
back to the previous version: `git revert HEAD` (makes a commit that undoes
the last one), then `deploy/onsite-update.sh --no-data` again.

Things that can lock you out of the Pi over Wi-Fi, so be careful with them:
the hotspot settings on the Config page, and anything in `network/` or
`deploy/network/`. Test those with the Pi on a bench with a screen/keyboard or
Ethernet first.

## 5. Rules of thumb

- The repo is **public**: never commit passwords, `db.sqlite3` (it holds
  Wi-Fi passwords), or `/etc/greenpi/greenpi.env`.
- Run the tests before deploying. Click-test on your laptop first.
- New sensor? Plug it into the Pi, check the Sensors page, then write a
  driver in `sensors/drivers.py` + a simulated twin in `sensors/simulated.py`
  (see the BME688 and soil drivers for the pattern: read on the real board
  first, then save one real raw reading as a test).

## What still depends on the owner

- Remote access over the owner's VPN (the Pi's `wg0`; leave it alone) and the
  owner's always-on staging copy.
- GitHub repo admin (collaborator access, merging the pull request).
- Without those you can still do everything above: develop locally, update
  the Pi on site, bring data home.
