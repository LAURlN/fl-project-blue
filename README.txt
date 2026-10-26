Fantasy Life PC - Standalone Dual-OS (Windows + Linux) Auto-Updating Build
==========================================================================

1. HOW TO PLAY (Brothers' PCs)
------------------------------
* Windows: Double-click the "Fantasy Life" desktop shortcut (or `play.bat`).
  The Fantasy Life launcher window opens:
  - It shows your installed build and checks for updates in the background
    (a few seconds; offline never blocks playing). When a new build is out you see
    "Update available" and an "Update now" button with a progress bar. Update
    before playing together: multiplayer needs everyone on the same build.
  - "Play" starts the game with all mods of this build (shown as chips).
  - "Play vanilla" starts the original game data without any mods.
    Vanilla players can play together; vanilla and modded players cannot.
  - Pick the save profile (Free Life / Story). The window remembers your choice.
  - Footer: Game settings (controls, resolution, online relay = the Clockwork
    launcher), Firewall (one admin prompt), Log, install folder.
  - The window hides while you play and closes when the game ends normally.
    If the game stops with an error, the window comes back with the last log lines.
* Linux: `bash play.sh` opens the same choices as a zenity dialog (if installed) or a
  terminal menu. `bash play.sh story` / `bash play.sh --direct` play right away.

Updates are no longer applied silently on start; you choose in the window.
Your personal saves (`saves/`), controller/audio settings (`settings.ini`),
unique multiplayer console ID (`console_id`), and game dumps (`game/`) are
NEVER overwritten by updates.

On PCs without Git, the ZIP updater first reads the small remote `version.json` and
only downloads the full ZIP when `version` or `updated_at` changed. The version URL is
derived automatically for GitHub archive ZIPs; set `FL_UPDATE_VERSION_URL` in
`update-config.env` for a different host. If the check is unreachable, the local build
still launches normally.

What "Play vanilla" means exactly
- No data mods: FL_MOD_DIRS is passed EMPTY, so none of the overlays in
  `data\yw2-recomp\mods\fantasylife` are loaded. (Before this launcher, `-Vanilla` on
  Windows silently loaded every installed overlay; that is fixed.)
- Everything else stays the same: the same PC runtime with its technical fixes,
  the Origin Island DLC (if present), your settings.ini and your saves.
- Co-op freedom options (Change Life, report, requests, makeover in multiplayer)
  are runtime settings in settings.ini, not data mods. They stay as you set them in
  Game settings and are part of the multiplayer compatibility check, so vanilla
  players must also use the same co-op freedom settings (the defaults match).
- Vanilla multiplayer therefore needs: the same build (exe), vanilla on every
  player, the same DLC presence and the same co-op freedom settings.
- Save profiles are shared between modded and vanilla play; mod content in a save
  may behave differently without the mod.

Command-line launcher (scripts, shortcuts of your own):
  play.bat                     launcher window (same as the desktop shortcut)
  play.bat -Save story         launcher window with the story save selected
  play.bat -Direct             play right away (updates first, like the old launcher)
  play.bat -Direct -NoUpdate   play right away without the update check
  play.bat -Vanilla            play right away without mods
  play.bat -Launcher           Clockwork launcher (controller bindings, resolution, relay)
  play.bat -NoLaunch           update check and environment only; never starts the game
  play.bat -SetupFirewall      set up the multiplayer firewall, then play
  play.bat -NoDlc / -NoFirewall
  (`.\play.ps1 <flags>` works the same in PowerShell. FL_DIRECT=1 always skips the window.)
  Linux: FL_NO_UPDATE=1, FL_NO_LAUNCH=1, FL_MOD_DIRS= (vanilla) and FL_DIRECT=1 work
  as environment variables; `bash play.sh --vanilla [save]`.

Desktop icon: the launcher draws the real Fantasy Life icon from YOUR game dump
(`data\yw2-recomp\icon.ico`, never uploaded) and points the shortcut at it on the
next start. Without a dump the shortcut uses the neutral `bin\fantasy-life.ico`.
The shortcut starts `bin\launcher\FantasyLife.vbs` (no console window); if VBScript
is missing it falls back to `play.bat`.

2. FIRST-TIME USB STICK SETUP (Your PC)
---------------------------------------
1. Populate the folder (binaries, mods, shaders, and gitignored game dumps):
     powershell -ExecutionPolicy Bypass -File .\publish-update.ps1 -IncludeDumps -Commit
2. Connect this folder to a private GitHub repository (contains ONLY the runtime,
   mods, and shader cache — `game/` and `saves/` are strictly `.gitignore`d):
     git remote add origin <YOUR_REPO_URL>
     git push -u origin main
   (Optional: if a brother doesn't have Git installed, also set `FL_UPDATE_ZIP_URL`
   in `update-config.env`.)
3. Copy this `FantasyLife-USB` folder onto the USB stick, and copy it onto each
   brother's PC.

3. PUSHING UPDATES LATER (Your PC)
----------------------------------
Whenever you change a mod or rebuild `fl_eur.exe`, run:
     powershell -ExecutionPolicy Bypass -File .\publish-update.ps1 -RebuildMods -Commit -Push
Your brothers see "Update available" in the launcher window and click "Update now".

`-Push` only runs in an interactive PowerShell window. It prints the exe source and
SHA-256, the commit range that will be pushed, and asks you to type `publish`;
redirected or non-interactive sessions are refused.

Publishing the exact build you tested
-------------------------------------
When the build in `%LOCALAPPDATA%\FantasyLife-PC-Test` is the one you tested, publish
exactly that install instead of whatever binary happens to be in a build folder:
     powershell -ExecutionPolicy Bypass -File .\publish-update.ps1 -FromTest -Commit -Push
`-FromTest` copies the test install's `bin\fl_eur.exe`, its DLLs, `clockwork-relay.exe`
and only the mod overlays listed in `test-version.json`, strips debug symbols, and writes
`version.json` with the sanitized test label as `version` and a fresh `mod_digest`.
You can point it elsewhere with `-TestDir <path>`.
Without `-FromTest` the script behaves as before; either way it prints the published exe
source and SHA-256. The Linux `bin/fl_eur` cannot be rebuilt on Windows, so it is kept as
the previous Linux build; a yellow warning appears when it is older than the Windows exe.

4. STABLE VS TEST INSTALLS
--------------------------
* Stable = `%LOCALAPPDATA%\FantasyLife-PC`, shortcut "Fantasy Life". It follows
  `origin/main` and only changes when you publish (section 3).

  Update rule (launcher "Update now", or every `play.bat -Direct` start):
  - fetch `origin/main`; if it equals HEAD, it reports "Already up to date";
  - if HEAD is strictly ahead (a local hotfix you have not published yet), it keeps
    your version and prints one yellow `[Updater] Local hotfix not yet published ...`
    line;
  - otherwise (origin ahead, or the histories diverged) it mirrors origin exactly with
    `git reset --hard origin/main` and prints `[Updater] Updated <old> -> <new>`.
  That reset only touches tracked files. Ignored files (`game/`, `saves/`, `logs/`,
  `settings.ini`, `console_id`, shader logs) are never touched, and the updater never
  runs `git clean`.
  Offline, it launches the local version with a yellow note.

* Test = `%LOCALAPPDATA%\FantasyLife-PC-Test`, shortcut "Fantasy Life (Test)".
  It is local only: no git repo/remote, no auto-update, never pushed, so your brothers
  never see it. Its launcher window is orange and marked TEST BUILD with the label. Put whatever is currently under test there:
     powershell -ExecutionPolicy Bypass -File .\publish-test.ps1 -Exe <built fl_eur.exe> -Label "<branch> <commit>"
  Optional: `-Relay <clockwork-relay.exe>`, `-ModDirs <overlay dirs>` (default: the
  stable install's version.json mods, falling back to installed folders), and `-CopySavesFromStable` (one-way copy of the stable
  saves into the test saves; never the other way).
  The script hard-links `game/` from the stable install, seeds its own `settings.ini`,
  and never copies `console_id`, so each install keeps its own multiplayer identity.
  Re-running it never touches test saves, `settings.ini`, or `console_id`, and never
  writes to the stable install.

5. TESTING ON A SECOND PC (e.g. laptop)
---------------------------------------
On your PC, export the current test install as a portable ZIP:
     powershell -ExecutionPolicy Bypass -File .\publish-test.ps1 -ExportZip D:\fl-test.zip
Add `-Exe`, `-Relay`, `-ModDirs`, or `-Label` to update the local test install first;
with only `-ExportZip` the existing test install is exported unchanged.

Copy the ZIP to the second PC, extract it, and double-click `Install-Test.bat`.
The installer:
- installs to `%LOCALAPPDATA%\FantasyLife-PC-Test`;
- hard-links the game dumps from that PC's stable install
  `%LOCALAPPDATA%\FantasyLife-PC\game` (copy fallback); if that is missing it asks for
  the folder that contains `FantasyLife_EU.3ds` (or pass `-DumpDir <path>`);
- keeps existing test saves, `settings.ini`, and `console_id`;
- creates the "Fantasy Life (Test)" shortcuts;
- optionally copies stable saves one-way, only when a test save does not already exist.

The exported ZIP contains no game dumps, saves, logs, `settings.ini`, or `console_id`,
so it is safe to move between PCs.

6. MULTIPLAYER NETWORK ACCESS (WINDOWS FIREWALL)
------------------------------------------------
The installer or the first launch offers to add Windows Firewall rules with one UAC
prompt. The rules live in the group `Fantasy Life PC` and only apply to this install's
`bin\fl_eur.exe`:

- Inbound UDP allow on the Domain and Private profiles, remote `LocalSubnet`, for
  normal LAN play.
- Inbound UDP allow on the Public profile, remote only `25.0.0.0/8` (Hamachi) and
  `26.0.0.0/8` (Radmin VPN). Public is never opened to RFC1918 ranges or `Any`:
  cafés and other public Wi-Fi also use RFC1918 addresses.
- If a ZeroTier adapter exists, an inbound UDP allow scoped to that adapter
  (Public + Private), not to an address range.
- When `bin\clockwork-relay.exe` is present, an optional inbound UDP 47830 allow on
  the Domain and Private profiles for relay hosts.

The setup is idempotent. Rules you created by hand (for example
`Fantasy Life (Hamachi)`) are treated as compatible and are kept. Inbound Block rules
for `fl_eur.exe` (created when someone clicked Cancel in a Windows prompt) are removed
because they override allow rules.

If you declined, or multiplayer is blocked later, click "Firewall" in the launcher
window, or run:
  play.bat -SetupFirewall

Preview without changing anything:
  powershell -ExecutionPolicy Bypass -File .\setup-firewall.ps1 -WhatIf -InstallDir "$env:LOCALAPPDATA\FantasyLife-PC"
Check only:
  powershell -ExecutionPolicy Bypass -File .\setup-firewall.ps1 -Check -InstallDir "$env:LOCALAPPDATA\FantasyLife-PC"
Remove only the rules managed by this package (your own rules stay):
  powershell -ExecutionPolicy Bypass -File .\setup-firewall.ps1 -Remove -InstallDir "$env:LOCALAPPDATA\FantasyLife-PC"
Use the same commands with `FantasyLife-PC-Test` for the test install. The decline
marker is `data\yw2-recomp\firewall-declined`; deleting it also makes the next launch
ask again.

Linux: this package does not change Linux firewall settings. If `ufw` or a similar
firewall is enabled and multiplayer does not work, allow the game and UDP 47830, for
example:
  sudo ufw allow 47830/udp
(only needed on the player who hosts a relay).

7. MODS
-------
Mods are added through the launcher's Mod Manager (ZIP or GameBanana). Never upload source dumps or extracted
game resources.
Stable Windows play.ps1 reads version.json's mods array (old packages fall back
to installed overlay folders); an empty array disables all packaged mods.
For maintainers: -RebuildMods reads the source repo's mods/enabled.json in order,
builds each source with fl_mod.py and checks the entire stack before continuing.
The ordinary publish command mirrors every built overlay from FantasyLife-Windows
(or FantasyLife-Linux when no Windows mod directory exists), removes stale package
overlays, and records the exact set in version.json. From FantasyLife-USB, run:
  powershell -ExecutionPolicy Bypass -File .\publish-update.ps1 -Push
Do not add -FromTest unless you intend to publish exactly the overlays listed by
the test install's test-version.json; that mode replaces the package's mod set.
