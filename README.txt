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

`-Push` only runs in an interactive PowerShell window. It prints the commit range that
will be pushed and asks you to type `publish`; redirected or non-interactive sessions are
refused.

4. STABLE VS TEST INSTALLS
--------------------------
* Stable = `%LOCALAPPDATA%\FantasyLife-PC`, shortcut "Fantasy Life". It follows
  `origin/main` and only changes when you publish (section 3).

  Update rule on every launch:
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
  never see it. Put whatever is currently under test there:
     powershell -ExecutionPolicy Bypass -File .\publish-test.ps1 -Exe <built fl_eur.exe> -Label "<branch> <commit>"
  Optional: `-Relay <clockwork-relay.exe>`, `-ModDirs <overlay dirs>` (default: the
  stable install's four mods), and `-CopySavesFromStable` (one-way copy of the stable
  saves into the test saves; never the other way).
  The script hard-links `game/` from the stable install, seeds its own `settings.ini`,
  and never copies `console_id`, so each install keeps its own multiplayer identity.
  Re-running it never touches test saves, `settings.ini`, or `console_id`, and never
  writes to the stable install.
