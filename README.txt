Fantasy Life PC - Standalone Dual-OS (Windows + Linux) Auto-Updating Build
==========================================================================

1. HOW TO PLAY (Brothers' PCs)
------------------------------
* Windows: Double-click `play.bat`
  - Or in PowerShell: `.\play.ps1` (Free Life save) or `.\play.ps1 story` (Story save)
* Linux:   Run `bash play.sh` (Free Life save) or `bash play.sh story` (Story save)

Every time you start the game via `play.bat` / `play.sh`:
- It automatically checks for updates (new mods, bugfixes, shader cache, binaries)
  from the update repository and applies them in 1-2 seconds.
- Your personal saves (`saves/`), controller/audio settings (`settings.ini`),
  unique multiplayer console ID (`console_id`), and game dumps (`game/`) are
  NEVER overwritten by updates.
- Before launching, it prints the current `Build` and `Mod Digest` so everyone can
  confirm they are on the exact same version before joining multiplayer.

Useful Launch Flags:
- Skip update check:
  - Windows: `.\play.ps1 -NoUpdate`
  - Linux:   `FL_NO_UPDATE=1 bash play.sh`
- Play without mods (vanilla):
  - Windows: `.\play.ps1 -Vanilla`
  - Linux:   `FL_MOD_DIRS= bash play.sh`
- Open Clockwork Launcher (change controller bindings, resolution, or relay room):
  - Windows: `.\play.ps1 -Launcher`

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
Your brothers simply close and re-open `play.bat` / `play.sh` to get the update!
