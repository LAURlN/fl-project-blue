param(
    [string]$Save = "freelife",
    [switch]$NoUpdate,
    [switch]$Vanilla,
    [switch]$NoDlc,
    [switch]$Launcher
)

$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Here

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
if (-not $NoUpdate -and $env:FL_NO_UPDATE -ne "1") {
    $gitCmd = Get-Command git -ErrorAction SilentlyContinue
    if ($gitCmd -and (Test-Path "$Here\.git")) {
        $remotes = & git -c safe.directory=* remote 2>$null
        if ($remotes -contains "origin") {
            Write-Host "[Updater] Checking for updates from origin/$UpdateBranch..." -ForegroundColor Cyan
            & git -c safe.directory=* fetch origin $UpdateBranch --quiet 2>$null
            if ($LASTEXITCODE -eq 0) {
                $localRev = (& git -c safe.directory=* rev-parse HEAD 2>$null)
                $remoteRev = (& git -c safe.directory=* rev-parse "origin/$UpdateBranch" 2>$null)
                if ($remoteRev -and ($localRev -ne $remoteRev)) {
                    Write-Host "[Updater] Applying update ($($localRev.Substring(0,7)) -> $($remoteRev.Substring(0,7)))..." -ForegroundColor Green
                    & git -c safe.directory=* merge --ff-only "origin/$UpdateBranch" 2>$null
                    if ($LASTEXITCODE -ne 0) {
                        # Fallback: checkout tracked runtime/mod paths directly without touching local untracked files
                        & git -c safe.directory=* checkout "origin/$UpdateBranch" -- bin lib data/yw2-recomp/mods data/yw2-recomp/shader-cache-v3 data/yw2-recomp/settings.default.ini version.json 2>$null
                    }
                } else {
                    Write-Host "[Updater] Already up to date." -ForegroundColor DarkGray
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
}

# 2. Print version / mod compatibility digest
if (Test-Path "$Here\version.json") {
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
if (-not (Test-Path $ExePath)) {
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
    Write-Error "fl_eur.exe not found in $Here\bin\fl_eur.exe yet. Run publish-update.ps1 once the Windows build completes."
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
    $env:FL_MOD_DIRS = @(
        (Join-Path $ModRoot "story-skip"),
        (Join-Path $ModRoot "eastern-plains-enemy"),
        (Join-Path $ModRoot "castele-house"),
        (Join-Path $ModRoot "wooden-sword")
    ) -join ";"
}

# Ensure bin/ (and any local LLVM-MinGW compiler for Shader JIT) is on PATH
$BinDir = Split-Path -Parent $ExePath
$env:PATH = "$BinDir;$Here\bin;$env:PATH"

$LogFile = Join-Path $LogDir "play.log"
Write-Host "[Launch] Save profile: $Save ($SaveDir)" -ForegroundColor Green
Write-Host "[Launch] Log output:   $LogFile" -ForegroundColor DarkGray

# The game logs to stderr. Windows PowerShell 5.1 turns redirected native stderr into
# errors, which $ErrorActionPreference = "Stop" makes fatal, so let cmd do the redirect.
$Mode = if ($Launcher) { "--launcher" } else { "--play" }
$CmdLine = "/d /s /c `"`"$ExePath`" $Mode `"$RomPath`" > `"$LogFile`" 2>&1`""
$Game = Start-Process -FilePath $env:ComSpec -ArgumentList $CmdLine -NoNewWindow -Wait -PassThru
exit $Game.ExitCode
