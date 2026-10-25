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
