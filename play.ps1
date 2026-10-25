param(
    [string]$Save = "freelife",
    [switch]$NoUpdate,
    [switch]$Vanilla,
    [switch]$NoDlc,
    [switch]$Launcher,
    [switch]$NoLaunch,
    [switch]$NoFirewall,
    [switch]$SetupFirewall
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
$UpdateVersionUrl = ""
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
            if ($parts[0].Trim() -eq "FL_UPDATE_VERSION_URL" -and $parts[1].Trim()) {
                $UpdateVersionUrl = $parts[1].Trim()
            }
        }
    }
}

# Derive a raw version.json URL for GitHub archive ZIPs so the gitless updater
# can compare versions before downloading the whole package.
if (-not $UpdateVersionUrl -and $UpdateZipUrl) {
    if ($UpdateZipUrl -match '^https?://github\.com/([^/]+)/([^/]+)/archive/refs/heads/(.+?)(?:\.zip)?/?$') {
        $UpdateVersionUrl = "https://raw.githubusercontent.com/$($Matches[1])/$($Matches[2])/$($Matches[3])/version.json"
    } elseif ($UpdateZipUrl -match '^https?://github\.com/([^/]+)/([^/]+)/archive/(.+?)(?:\.zip)?/?$') {
        $UpdateVersionUrl = "https://raw.githubusercontent.com/$($Matches[1])/$($Matches[2])/$($Matches[3])/version.json"
    } elseif ($UpdateZipUrl -match '^https?://codeload\.github\.com/([^/]+)/([^/]+)/zip/refs/heads/(.+?)/?$') {
        $UpdateVersionUrl = "https://raw.githubusercontent.com/$($Matches[1])/$($Matches[2])/$($Matches[3])/version.json"
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
        Write-Host "[Updater] Git not found; checking ZIP update..." -ForegroundColor Cyan
        # The PS 5.1 progress bar makes Invoke-WebRequest 10-50x slower.
        $PrevZipProgress = $ProgressPreference
        $ProgressPreference = "SilentlyContinue"
        # The outer updater block uses Continue so redirected git stderr cannot
        # abort the launch. ZIP file operations should fail loudly instead.
        $PrevZipEap = $ErrorActionPreference
        $ErrorActionPreference = "Stop"
        $tmpDir = Join-Path $Here ".update-tmp"
        $downloaded = $false
        try {
            $LocalVersion = $null
            if (Test-Path "$Here\version.json") {
                try { $LocalVersion = Get-Content "$Here\version.json" -Raw | ConvertFrom-Json } catch { $LocalVersion = $null }
            }

            $RemoteVersion = $null
            $VersionChecked = $false
            if ($UpdateVersionUrl) {
                try {
                    $versionResponse = Invoke-WebRequest -Uri $UpdateVersionUrl -UseBasicParsing -TimeoutSec 15
                    $RemoteVersion = $versionResponse.Content | ConvertFrom-Json
                    if ($RemoteVersion -and $RemoteVersion.version) { $VersionChecked = $true }
                } catch {
                    $VersionChecked = $false
                }
            }

            if (-not $VersionChecked) {
                # No network, 404, unparseable version.json, or no URL: never
                # block the launch, and never download the large ZIP blindly.
                Write-Host "[Updater] ZIP update check failed; continuing with local version." -ForegroundColor Yellow
            } elseif ($LocalVersion -and
                      ([string]$LocalVersion.version -eq [string]$RemoteVersion.version) -and
                      ([string]$LocalVersion.updated_at -eq [string]$RemoteVersion.updated_at)) {
                Write-Host "[Updater] Already up to date ($($RemoteVersion.version))" -ForegroundColor DarkGray
            } else {
                $sizeText = ""
                try {
                    $head = Invoke-WebRequest -Uri $UpdateZipUrl -Method Head -UseBasicParsing -TimeoutSec 20
                    $contentLength = $head.Headers["Content-Length"]
                    if ($contentLength) {
                        $sizeText = (" ({0:N1} MB)" -f ([double]$contentLength / 1MB))
                    }
                } catch {}
                Write-Host "[Updater] Downloading update$sizeText..." -ForegroundColor Cyan

                if (Test-Path $tmpDir) { Remove-Item -Recurse -Force $tmpDir }
                New-Item -ItemType Directory -Path $tmpDir | Out-Null
                $downloaded = $true
                $zipFile = Join-Path $tmpDir "update.zip"
                Invoke-WebRequest -Uri $UpdateZipUrl -OutFile $zipFile -UseBasicParsing -TimeoutSec 600
                $zipMB = (Get-Item -LiteralPath $zipFile).Length / 1MB
                Write-Host ("[Updater] Downloaded {0:N1} MB." -f $zipMB) -ForegroundColor DarkGray

                $extractDir = Join-Path $tmpDir "extract"
                Expand-Archive -Path $zipFile -DestinationPath $extractDir -Force

                # GitHub archive ZIPs have one top-level folder; portable
                # packages exported by publish-test.ps1 are flat.
                $packageRoot = $extractDir
                if (-not (Test-Path (Join-Path $packageRoot "version.json")) -and
                    -not (Test-Path (Join-Path $packageRoot "bin\fl_eur.exe"))) {
                    foreach ($candidate in @(Get-ChildItem -LiteralPath $extractDir -Directory -ErrorAction SilentlyContinue)) {
                        if ((Test-Path (Join-Path $candidate.FullName "version.json")) -or
                            (Test-Path (Join-Path $candidate.FullName "bin\fl_eur.exe"))) {
                            $packageRoot = $candidate.FullName
                            break
                        }
                    }
                }
                if (-not (Test-Path (Join-Path $packageRoot "version.json")) -and
                    -not (Test-Path (Join-Path $packageRoot "bin\fl_eur.exe"))) {
                    throw "update package has no version.json or bin\fl_eur.exe"
                }

                # Runtime/data first.
                foreach ($sub in @("bin", "lib", "data\yw2-recomp\shader-cache-v3")) {
                    $src = Join-Path $packageRoot $sub
                    $dst = Join-Path $Here $sub
                    if (Test-Path -LiteralPath $src -PathType Container) {
                        New-Item -ItemType Directory -Path $dst -Force | Out-Null
                        foreach ($item in @(Get-ChildItem -LiteralPath $src -Force -ErrorAction SilentlyContinue)) {
                            Copy-Item -LiteralPath $item.FullName -Destination (Join-Path $dst $item.Name) -Recurse -Force
                        }
                    }
                }

                # Mods are mirrored: overlays removed upstream must disappear.
                $srcMods = Join-Path $packageRoot "data\yw2-recomp\mods"
                $dstMods = Join-Path $Here "data\yw2-recomp\mods"
                if (Test-Path -LiteralPath $srcMods -PathType Container) {
                    if (Test-Path -LiteralPath $dstMods) { Remove-Item -LiteralPath $dstMods -Recurse -Force }
                    New-Item -ItemType Directory -Path $dstMods -Force | Out-Null
                    foreach ($item in @(Get-ChildItem -LiteralPath $srcMods -Force -ErrorAction SilentlyContinue)) {
                        Copy-Item -LiteralPath $item.FullName -Destination (Join-Path $dstMods $item.Name) -Recurse -Force
                    }
                } elseif (Test-Path -LiteralPath $dstMods) {
                    Remove-Item -LiteralPath $dstMods -Recurse -Force
                    New-Item -ItemType Directory -Path $dstMods -Force | Out-Null
                }

                foreach ($file in @("version.json", "data\yw2-recomp\settings.default.ini")) {
                    $src = Join-Path $packageRoot $file
                    $dst = Join-Path $Here $file
                    if (Test-Path -LiteralPath $src -PathType Leaf) {
                        $dstParent = Split-Path -Parent $dst
                        if ($dstParent) { New-Item -ItemType Directory -Path $dstParent -Force | Out-Null }
                        Copy-Item -LiteralPath $src -Destination $dst -Force
                    }
                }

                # Scripts last. channel.env, test-version.json, game/, saves/,
                # logs/, settings.ini and console_id are never in this list.
                foreach ($name in @(
                    "play.ps1", "play.bat", "play.sh", "setup-firewall.ps1",
                    "install-windows.ps1", "Install-Windows.bat",
                    "install-test.ps1", "Install-Test.bat", "install-linux.sh",
                    "publish-update.ps1", "publish-test.ps1",
                    "README.txt", "update-config.env"
                )) {
                    $src = Join-Path $packageRoot $name
                    $dst = Join-Path $Here $name
                    if (Test-Path -LiteralPath $src -PathType Leaf) {
                        Copy-Item -LiteralPath $src -Destination $dst -Force
                    }
                }

                Write-Host "[Updater] ZIP update applied." -ForegroundColor Green
            }
        } catch {
            Write-Host "[Updater] ZIP update skipped ($($_.Exception.Message))." -ForegroundColor Yellow
        } finally {
            $ProgressPreference = $PrevZipProgress
            $ErrorActionPreference = $PrevZipEap
            if ($downloaded -and (Test-Path $tmpDir)) {
                Remove-Item -Recurse -Force $tmpDir -ErrorAction SilentlyContinue
            }
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

# 5b. Windows Firewall for multiplayer. Reading rules works without admin, so the
#     check is cheap and silent when everything is already in place. Only a "yes"
#     starts setup-firewall.ps1 through one UAC prompt.
$FirewallScript   = Join-Path $Here "setup-firewall.ps1"
$FirewallDeclined = Join-Path $RecompDataDir "firewall-declined"
if ($NoFirewall -or $env:FL_NO_FIREWALL -eq "1") {
    Write-Host "[Firewall] Skipped (-NoFirewall/FL_NO_FIREWALL=1)." -ForegroundColor DarkGray
} elseif (-not (Test-Path -LiteralPath $FirewallScript -PathType Leaf)) {
    Write-Host "[Firewall] setup-firewall.ps1 not found; skipping network access check." -ForegroundColor DarkGray
} else {
    try {
        . $FirewallScript
        if ($SetupFirewall) {
            if (-not (Test-FantasyLifeInteractiveConsole)) {
                Write-Host "[Firewall] Non-interactive session; skipping network access setup." -ForegroundColor DarkGray
            } else {
                Write-Host "[Firewall] Setting up multiplayer network access (one UAC prompt)..." -ForegroundColor Cyan
                if (Invoke-FantasyLifeFirewallSetupElevated -InstallDir $Here) {
                    Remove-Item -LiteralPath $FirewallDeclined -Force -ErrorAction SilentlyContinue
                    Write-Host "[Firewall] Network access is ready." -ForegroundColor Green
                }
            }
        } elseif (Test-Path -LiteralPath $FirewallDeclined) {
            Write-Host "[Firewall] Network access setup was declined earlier; retry with play.bat -SetupFirewall." -ForegroundColor DarkGray
        } elseif (-not (Test-FantasyLifeInteractiveConsole)) {
            Write-Host "[Firewall] Non-interactive session; skipping network access setup." -ForegroundColor DarkGray
        } else {
            $FirewallStatus = Get-FantasyLifeFirewallStatus -InstallDir $Here
            if ($FirewallStatus.Ready) {
                Remove-Item -LiteralPath $FirewallDeclined -Force -ErrorAction SilentlyContinue
            } else {
                $FirewallAnswer = Read-Host "Set up network access for multiplayer now? [Y/n]"
                if ($FirewallAnswer -match "^(?i)\s*n") {
                    Set-Content -LiteralPath $FirewallDeclined -Encoding ASCII -Value ("Declined " + (Get-Date).ToString("s") + " for " + $Here)
                    Write-Host "[Firewall] OK - skipping. Hamachi/LAN multiplayer may be blocked. Retry with play.bat -SetupFirewall." -ForegroundColor Yellow
                } else {
                    Write-Host "[Firewall] Setting up multiplayer network access (one UAC prompt)..." -ForegroundColor Cyan
                    if (Invoke-FantasyLifeFirewallSetupElevated -InstallDir $Here) {
                        Remove-Item -LiteralPath $FirewallDeclined -Force -ErrorAction SilentlyContinue
                        Write-Host "[Firewall] Network access is ready." -ForegroundColor Green
                    }
                }
            }
        }
    } catch {
        Write-Host "[Firewall] Check skipped ($($_.Exception.Message))." -ForegroundColor Yellow
    }
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
