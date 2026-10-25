param(
    [string]$Save = "freelife",
    [switch]$NoUpdate,
    [switch]$Vanilla,
    [switch]$NoDlc,
    [switch]$Launcher,
    [switch]$NoLaunch
)

$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Here

# 0. Load the optional channel marker (channel.env). A test install sets
#    FL_CHANNEL=test; a stable install has no file and follows origin/main.
$Channel = "stable"
$ChannelFile = Join-Path $Here "channel.env"
if (Test-Path $ChannelFile) {
    Get-Content $ChannelFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $parts = $line.Split("=", 2)
            if ($parts[0].Trim() -eq "FL_CHANNEL" -and $parts[1].Trim()) {
                $Channel = $parts[1].Trim().ToLowerInvariant()
            }
        }
    }
}
$IsTestChannel = ($Channel -eq "test")

# Load update-config.env if present
$UpdateBranch = "main"
$UpdateZipUrl = ""
if (Test-Path "$Here\update-config.env") {
    Get-Content "$Here\update-config.env" | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $parts = $line.Split("=", 2)
            if ($parts[0].Trim() -eq "FL_UPDATE_BRANCH" -and $parts[1].Trim()) {
                $UpdateBranch = $parts[1].Trim()
            }
            if ($parts[0].Trim() -eq "FL_UPDATE_ZIP_URL" -and $parts[1].Trim()) {
                $UpdateZipUrl = $parts[1].Trim()
            }
        }
    }
}

# 1. Auto-update check (safe: never touches game/, saves/, settings.ini, or console_id)
#    Test installs are local-only and never auto-update.
if (-not $IsTestChannel -and -not $NoUpdate -and $env:FL_NO_UPDATE -ne "1") {
    # Native git writes to stderr when there is no network or no remote. Windows
    # PowerShell 5.1 turns redirected native stderr into a terminating error while
    # $ErrorActionPreference is Stop, so run the updater with Continue (each git call
    # redirects stderr itself) and restore the previous setting afterwards.
    $PrevUpdateEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
    $gitCmd = Get-Command git -ErrorAction SilentlyContinue
    if ($gitCmd -and (Test-Path "$Here\.git")) {
        $remotes = & git -c safe.directory=* remote 2>$null
        if ($remotes -contains "origin") {
            & git -c safe.directory=* fetch origin $UpdateBranch --quiet 2>$null
            if ($LASTEXITCODE -eq 0) {
                $localRev = (& git -c safe.directory=* rev-parse HEAD 2>$null)
                $remoteRev = (& git -c safe.directory=* rev-parse "origin/$UpdateBranch" 2>$null)
                if ($localRev -and $remoteRev) {
                    $shortLocal  = $localRev.Substring(0, 7)
                    $shortRemote = $remoteRev.Substring(0, 7)
                    if ($localRev -eq $remoteRev) {
                        Write-Host "[Updater] Already up to date ($shortLocal)." -ForegroundColor DarkGray
                    } else {
                        # Keep a local, unpublished hotfix: HEAD strictly ahead of origin.
                        & git -c safe.directory=* merge-base --is-ancestor "origin/$UpdateBranch" HEAD 2>$null
                        if ($LASTEXITCODE -eq 0) {
                            Write-Host "[Updater] Local hotfix not yet published ($shortLocal ahead of $shortRemote)" -ForegroundColor Yellow
                        } else {
                            # origin is ahead or the branches diverged: mirror origin exactly.
                            # reset --hard only touches tracked files; game/, saves/, logs/,
                            # settings.ini and console_id are ignored and stay untouched.
                            # Never run git clean.
                            & git -c safe.directory=* reset --hard "origin/$UpdateBranch" 2>$null | Out-Null
                            if ($LASTEXITCODE -eq 0) {
                                Write-Host "[Updater] Updated $shortLocal -> $shortRemote" -ForegroundColor Green
                            } else {
                                Write-Host "[Updater] Update failed; continuing with local version." -ForegroundColor Yellow
                            }
                        }
                    }
                }
            } else {
                Write-Host "[Updater] Offline or remote unreachable; continuing with local version." -ForegroundColor Yellow
            }
        }
    } elseif ($UpdateZipUrl) {
        Write-Host "[Updater] Git not found; checking ZIP update from $UpdateZipUrl..." -ForegroundColor Cyan
        try {
            $tmpDir = Join-Path $Here ".update-tmp"
            if (Test-Path $tmpDir) { Remove-Item -Recurse -Force $tmpDir }
            New-Item -ItemType Directory -Path $tmpDir | Out-Null
            $zipFile = Join-Path $tmpDir "update.zip"
            Invoke-WebRequest -Uri $UpdateZipUrl -OutFile $zipFile -UseBasicParsing -TimeoutSec 15
            Expand-Archive -Path $zipFile -DestinationPath $tmpDir -Force
            $extractedRoot = Get-ChildItem -Path $tmpDir -Directory | Select-Object -First 1
            if ($extractedRoot) {
                foreach ($sub in @("bin", "lib", "data\yw2-recomp\mods", "data\yw2-recomp\shader-cache-v3")) {
                    $src = Join-Path $extractedRoot.FullName $sub
                    $dst = Join-Path $Here $sub
                    if (Test-Path $src) {
                        New-Item -ItemType Directory -Path $dst -Force | Out-Null
                        Copy-Item -Path "$src\*" -Destination $dst -Recurse -Force
                    }
                }
                foreach ($file in @("version.json", "data\yw2-recomp\settings.default.ini")) {
                    $src = Join-Path $extractedRoot.FullName $file
                    $dst = Join-Path $Here $file
                    if (Test-Path $src) { Copy-Item -Path $src -Destination $dst -Force }
                }
                Write-Host "[Updater] ZIP update applied." -ForegroundColor Green
            }
            Remove-Item -Recurse -Force $tmpDir -ErrorAction SilentlyContinue
        } catch {
            Write-Host "[Updater] ZIP update skipped ($($_.Exception.Message))." -ForegroundColor Yellow
        }
    }
    } finally {
        $ErrorActionPreference = $PrevUpdateEap
    }
}

# 2. Print version / mod compatibility digest
$TestVersion = $null
if ($IsTestChannel) {
    $TestVersionFile = Join-Path $Here "test-version.json"
    if (Test-Path $TestVersionFile) {
        try {
            $TestVersion = Get-Content $TestVersionFile -Raw | ConvertFrom-Json
            $TestLabel = if ($TestVersion.label) { $TestVersion.label } else { "(unlabeled)" }
            Write-Host ("==============================================================") -ForegroundColor DarkYellow
            Write-Host (" TEST BUILD | {0}" -f $TestLabel) -ForegroundColor Yellow
            if ($TestVersion.exe_source)   { Write-Host (" Exe source:  {0}" -f $TestVersion.exe_source) -ForegroundColor Yellow }
            if ($TestVersion.exe_sha256)   { Write-Host (" Exe SHA-256: {0}" -f $TestVersion.exe_sha256) -ForegroundColor Yellow }
            if ($TestVersion.mods)         { Write-Host (" Mods:        {0}" -f (@($TestVersion.mods) -join ", ")) -ForegroundColor Yellow }
            if ($TestVersion.date)         { Write-Host (" Published:   {0}" -f $TestVersion.date) -ForegroundColor Yellow }
            Write-Host (" Local test install - auto-update disabled.") -ForegroundColor DarkYellow
            Write-Host ("==============================================================") -ForegroundColor DarkYellow
        } catch {
            Write-Host "[Test] test-version.json is unreadable; launching anyway." -ForegroundColor Yellow
        }
    } else {
        Write-Host "[Test] Missing test-version.json. Run publish-test.ps1 to fill this test install." -ForegroundColor Yellow
    }
} elseif (Test-Path "$Here\version.json") {
    try {
        $v = Get-Content "$Here\version.json" -Raw | ConvertFrom-Json
        Write-Host ("==============================================================") -ForegroundColor DarkCyan
        Write-Host (" Fantasy Life PC | Build: {0} | Updated: {1}" -f $v.version, $v.updated_at) -ForegroundColor Cyan
        Write-Host (" Mod Digest:     {0} ({1})" -f $v.mod_digest, ($v.mods -join ", ")) -ForegroundColor Cyan
        Write-Host ("==============================================================") -ForegroundColor DarkCyan
    } catch {}
}

# 3. Seed per-machine settings on first run (never share console_id!)
$RecompDataDir = Join-Path $Here "data\yw2-recomp"
New-Item -ItemType Directory -Path $RecompDataDir -Force | Out-Null
$SettingsIni = Join-Path $RecompDataDir "settings.ini"
$DefaultIni  = Join-Path $RecompDataDir "settings.default.ini"
if (-not (Test-Path $SettingsIni) -and (Test-Path $DefaultIni)) {
    Copy-Item -Path $DefaultIni -Destination $SettingsIni
}

# 4. Locate game dump and DLC CIA
$RomPath = Join-Path $Here "game\FantasyLife_EU.3ds"
if (-not (Test-Path $RomPath)) {
    foreach ($candidate in @(
        (Join-Path $Here "game\0004000000113100_v00.trim.3ds"),
        (Join-Path $Here "..\FantasyLife-Linux\game\FantasyLife_EU.3ds"),
        (Join-Path $Here "..\Game_Dumps\0004000000113100_v00.trim.3ds"),
        (Join-Path $Here "..\fl-project-blue\dumps\0004000000113100_v00.trim.3ds")
    )) {
        if (Test-Path $candidate) { $RomPath = (Resolve-Path $candidate).Path; break }
    }
}
if (-not (Test-Path $RomPath)) {
    Write-Error "Missing Fantasy Life 3DS dump! Place FantasyLife_EU.3ds in $Here\game\"
    exit 1
}

$DlcPath = Join-Path $Here "game\OriginIsland_DLC.cia"
if (-not (Test-Path $DlcPath)) {
    foreach ($candidate in @(
        (Join-Path $Here "..\FantasyLife-Linux\game\OriginIsland_DLC.cia"),
        (Join-Path $Here "..\fl-project-blue\dumps\OriginIsland_DLC.cia")
    )) {
        if (Test-Path $candidate) { $DlcPath = (Resolve-Path $candidate).Path; break }
    }
}

# 5. Locate Windows executable
$ExePath = Join-Path $Here "bin\fl_eur.exe"
if (-not (Test-Path $ExePath) -and -not $IsTestChannel) {
    foreach ($candidate in @(
        (Join-Path $Here "..\FantasyLife-Windows\bin\fl_eur.exe"),
        (Join-Path $Here "..\fl-project-blue\port-wt\windows-port\build\windows-native\fl_eur.exe"),
        (Join-Path $Here "..\fl-project-blue\port\build\windows-native\fl_eur.exe"),
        (Join-Path $Here "..\fl-project-blue\port\build\native\fl_eur.exe")
    )) {
        if (Test-Path $candidate) { $ExePath = (Resolve-Path $candidate).Path; break }
    }
}
if (-not (Test-Path $ExePath)) {
    if ($IsTestChannel) {
        Write-Error "fl_eur.exe not found in $Here\bin\fl_eur.exe. Run publish-test.ps1 -Exe <built fl_eur.exe> to fill this test install."
    } else {
        Write-Error "fl_eur.exe not found in $Here\bin\fl_eur.exe yet. Run publish-update.ps1 once the Windows build completes."
    }
    exit 1
}

# 6. Configure environment variables
$SaveDir = Join-Path $Here "saves\$Save"
$LogDir  = Join-Path $Here "logs"
New-Item -ItemType Directory -Path $SaveDir -Force | Out-Null
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

$env:APPDATA       = Join-Path $Here "data"
$env:XDG_DATA_HOME = Join-Path $Here "data"
$env:YW2_STATE_DIR = $SaveDir
$env:YW2_WIDESCREEN = "0"
$env:YW2_INTERP     = "0"
$env:YW2_SCALE      = "1"
if (-not $env:FL_FPS)  { $env:FL_FPS  = "0" }
if (-not $env:YW2_FPS) { $env:YW2_FPS = "0" }

if ($NoDlc) {
    $env:FL_DLC_CIA = ""
} elseif (Test-Path $DlcPath) {
    $env:FL_DLC_CIA = $DlcPath
}

$ModRoot = Join-Path $Here "data\yw2-recomp\mods\fantasylife"
if ($Vanilla) {
    $env:FL_MOD_DIRS = ""
} elseif (-not $env:FL_MOD_DIRS) {
    if ($IsTestChannel) {
        $TestMods = @()
        if ($TestVersion -and $TestVersion.mods) { $TestMods = @($TestVersion.mods) }
        $env:FL_MOD_DIRS = (@($TestMods | ForEach-Object { Join-Path $ModRoot $_ }) -join ";")
        if ($TestMods.Count -eq 0) { $env:FL_MOD_DIRS = "" }
    } else {
        $env:FL_MOD_DIRS = @(
            (Join-Path $ModRoot "story-skip"),
            (Join-Path $ModRoot "eastern-plains-enemy"),
            (Join-Path $ModRoot "castele-house"),
            (Join-Path $ModRoot "wooden-sword")
        ) -join ";"
    }
}

# Ensure bin/ (and any local LLVM-MinGW compiler for Shader JIT) is on PATH
$BinDir = Split-Path -Parent $ExePath
$env:PATH = "$BinDir;$Here\bin;$env:PATH"

if ($NoLaunch) {
    Write-Host "[Launch] -NoLaunch set; exiting without starting the game." -ForegroundColor DarkGray
    exit 0
}

# One log per save profile, so two windows (e.g. a multiplayer test) don't share one
$LogFile = Join-Path $LogDir $(if ($Save -eq "freelife") { "play.log" } else { "play-$Save.log" })
Write-Host "[Launch] Save profile: $Save ($SaveDir)" -ForegroundColor Green
Write-Host "[Launch] Log output:   $LogFile" -ForegroundColor DarkGray

# The game logs to stderr. Windows PowerShell 5.1 turns redirected native stderr into
# errors, which $ErrorActionPreference = "Stop" makes fatal, so let cmd do the redirect.
$Mode = if ($Launcher) { "--launcher" } else { "--play" }
$CmdLine = "/d /s /c `"`"$ExePath`" $Mode `"$RomPath`" > `"$LogFile`" 2>&1`""
$Game = Start-Process -FilePath $env:ComSpec -ArgumentList $CmdLine -NoNewWindow -Wait -PassThru
exit $Game.ExitCode
