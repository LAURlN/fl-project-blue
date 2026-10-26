param(
    [string]$Save = "",
    [switch]$NoUpdate,
    [switch]$Vanilla,
    [switch]$NoDlc,
    [switch]$Launcher,
    [switch]$NoLaunch,
    [switch]$NoFirewall,
    [switch]$SetupFirewall,
    # Skip the launcher window and play right away (scripts, shortcuts of your own).
    [switch]$Direct,
    # Open the launcher window even when other flags are given.
    [switch]$Window,
    # Internal: started without a console (desktop shortcut / play.bat without arguments).
    [switch]$Hidden,
    # Internal: the launcher relaunched itself after an update; value = previous version.
    [string]$AfterUpdate = "",
    # Internal: define the functions only (used by the window's background jobs).
    [switch]$LibraryOnly,
    # Developer: open the window but never start the game; optionally save a PNG of it.
    [switch]$Preview,
    [string]$Screenshot = ""
)

# Fantasy Life PC launcher.
#
#   play.bat / desktop shortcut     -> launcher window (update, play with mods, play vanilla)
#   play.ps1 -Direct [flags]        -> play right away without the window (old behaviour,
#                                      including the update check unless -NoUpdate)
#   play.ps1 -Vanilla | -Launcher | -NoLaunch | -SetupFirewall  -> direct mode as well
#
# The update logic never touches game/, saves/, logs/, settings.ini or console_id,
# never runs git clean, and never blocks the launch when offline.

$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Here
$PlayScript = Join-Path $Here "play.ps1"

# ---------------------------------------------------------------------------
# Library
# ---------------------------------------------------------------------------

function Read-FLKeyValueFile {
    param([string]$Path)
    $map = @{}
    if (Test-Path -LiteralPath $Path -PathType Leaf) {
        foreach ($raw in (Get-Content -LiteralPath $Path)) {
            $line = $raw.Trim()
            if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
                $parts = $line.Split("=", 2)
                if ($parts[1].Trim()) { $map[$parts[0].Trim()] = $parts[1].Trim().Trim('"') }
            }
        }
    }
    return $map
}

# Channel (stable/test) and update settings of this install.
function Get-FLConfig {
    $channelVars = Read-FLKeyValueFile (Join-Path $Here "channel.env")
    $channel = "stable"
    if ($channelVars["FL_CHANNEL"]) { $channel = $channelVars["FL_CHANNEL"].ToLowerInvariant() }

    $upd = Read-FLKeyValueFile (Join-Path $Here "update-config.env")
    $branch = if ($upd["FL_UPDATE_BRANCH"]) { $upd["FL_UPDATE_BRANCH"] } else { "main" }
    $zipUrl = [string]$upd["FL_UPDATE_ZIP_URL"]
    $versionUrl = [string]$upd["FL_UPDATE_VERSION_URL"]
    # Derive a raw version.json URL for GitHub archive ZIPs so the gitless updater
    # can compare versions before downloading the whole package.
    if (-not $versionUrl -and $zipUrl) {
        if ($zipUrl -match '^https?://github\.com/([^/]+)/([^/]+)/archive/refs/heads/(.+?)(?:\.zip)?/?$') {
            $versionUrl = "https://raw.githubusercontent.com/$($Matches[1])/$($Matches[2])/$($Matches[3])/version.json"
        } elseif ($zipUrl -match '^https?://github\.com/([^/]+)/([^/]+)/archive/(.+?)(?:\.zip)?/?$') {
            $versionUrl = "https://raw.githubusercontent.com/$($Matches[1])/$($Matches[2])/$($Matches[3])/version.json"
        } elseif ($zipUrl -match '^https?://codeload\.github\.com/([^/]+)/([^/]+)/zip/refs/heads/(.+?)/?$') {
            $versionUrl = "https://raw.githubusercontent.com/$($Matches[1])/$($Matches[2])/$($Matches[3])/version.json"
        }
    }
    return [pscustomobject]@{
        Channel    = $channel
        IsTest     = ($channel -eq "test")
        Branch     = $branch
        ZipUrl     = $zipUrl
        VersionUrl = $versionUrl
    }
}

function Read-FLJson {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    try { return (Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json) } catch { return $null }
}

# What is installed: stable version.json or test-version.json.
function Get-FLLocalVersion {
    param($Config)
    if ($Config.IsTest) { return Read-FLJson (Join-Path $Here "test-version.json") }
    return Read-FLJson (Join-Path $Here "version.json")
}

# The mod overlays this build plays with. Each entry has Folder, Name (from
# overlay.json), Path and Present. Per-mod picking can later filter this list.
function Get-FLMods {
    param($Config, $LocalVersion)
    $modRoot = Join-Path $Here "data\yw2-recomp\mods\fantasylife"
    $names = @()
    $note = ""
    if ($Config.IsTest) {
        if ($LocalVersion -and $LocalVersion.mods) { $names = @($LocalVersion.mods) }
    } else {
        # An explicit empty list means vanilla. Missing/old manifests fall back
        # to installed overlays; never infer fixed names from a build date.
        $haveList = $false
        $manifest = Read-FLJson (Join-Path $Here "version.json")
        if ($manifest -and ($manifest.PSObject.Properties.Name -contains "mods")) {
            try {
                if ($null -eq $manifest.mods -or $manifest.mods -isnot [System.Array]) { throw "mods must be an array" }
                $names = @($manifest.mods)
                foreach ($mod in $names) {
                    if ($mod -isnot [string] -or $mod -notmatch '^[a-zA-Z0-9][a-zA-Z0-9._-]*$') { throw "invalid mod folder name" }
                }
                if (@($names | Select-Object -Unique).Count -ne $names.Count) { throw "duplicate mod name" }
                $haveList = $true
            } catch {
                $names = @()
                $note = "version.json mod list unreadable; using installed folders."
            }
        }
        if (-not $haveList) {
            $names = @(Get-ChildItem -LiteralPath $modRoot -Directory -ErrorAction SilentlyContinue |
                Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName "overlay.json") } |
                Sort-Object Name | ForEach-Object { $_.Name })
        }
    }
    $mods = @()
    foreach ($folder in $names) {
        $path = Join-Path $modRoot $folder
        $overlay = Read-FLJson (Join-Path $path "overlay.json")
        $display = if ($overlay -and $overlay.name) { [string]$overlay.name } else { [string]$folder }
        $mods += [pscustomobject]@{
            Folder  = [string]$folder
            Name    = $display
            Path    = $path
            Present = [bool]$overlay
        }
    }
    return [pscustomobject]@{ Mods = $mods; Note = $note }
}

function Get-FLRomPath {
    $rom = Join-Path $Here "game\FantasyLife_EU.3ds"
    if (Test-Path -LiteralPath $rom) { return $rom }
    foreach ($candidate in @(
        (Join-Path $Here "game\0004000000113100_v00.trim.3ds"),
        (Join-Path $Here "..\FantasyLife-Linux\game\FantasyLife_EU.3ds"),
        (Join-Path $Here "..\Game_Dumps\0004000000113100_v00.trim.3ds"),
        (Join-Path $Here "..\fl-project-blue\dumps\0004000000113100_v00.trim.3ds")
    )) {
        if (Test-Path -LiteralPath $candidate) { return (Resolve-Path -LiteralPath $candidate).Path }
    }
    return $null
}

function Get-FLDlcPath {
    $dlc = Join-Path $Here "game\OriginIsland_DLC.cia"
    if (Test-Path -LiteralPath $dlc) { return $dlc }
    foreach ($candidate in @(
        (Join-Path $Here "..\FantasyLife-Linux\game\OriginIsland_DLC.cia"),
        (Join-Path $Here "..\fl-project-blue\dumps\OriginIsland_DLC.cia")
    )) {
        if (Test-Path -LiteralPath $candidate) { return (Resolve-Path -LiteralPath $candidate).Path }
    }
    return $null
}

function Get-FLExePath {
    param($Config)
    $exe = Join-Path $Here "bin\fl_eur.exe"
    if (Test-Path -LiteralPath $exe) { return $exe }
    if (-not $Config.IsTest) {
        foreach ($candidate in @(
            (Join-Path $Here "..\FantasyLife-Windows\bin\fl_eur.exe"),
            (Join-Path $Here "..\fl-project-blue\port-wt\windows-port\build\windows-native\fl_eur.exe"),
            (Join-Path $Here "..\fl-project-blue\port\build\windows-native\fl_eur.exe"),
            (Join-Path $Here "..\fl-project-blue\port\build\native\fl_eur.exe")
        )) {
            if (Test-Path -LiteralPath $candidate) { return (Resolve-Path -LiteralPath $candidate).Path }
        }
    }
    return $null
}

# Game processes started from this install (an update must not replace a running exe).
function Get-FLRunningGames {
    $prefix = [System.IO.Path]::GetFullPath($Here).TrimEnd("\") + "\"
    return @(Get-Process -Name "fl_eur" -ErrorAction SilentlyContinue | Where-Object {
        try { $_.Path -and $_.Path.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase) } catch { $false }
    })
}

function Test-FLGitInstall {
    if (-not (Test-Path -LiteralPath (Join-Path $Here ".git"))) { return $false }
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) { return $false }
    $remotes = & git -c safe.directory=* remote 2>$null
    return (@($remotes) -contains "origin")
}

function Enable-FLTls12 {
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    } catch {}
}

# Fast, read-only update check. State is one of:
#   Test, UpToDate, Available, Ahead (local unpublished hotfix), Offline, NoUpdater
# Never throws; never changes installed files (git fetch only updates origin/*).
function Get-FLUpdateStatus {
    param($Config)
    $ErrorActionPreference = "Continue"
    $status = [ordered]@{
        State = "NoUpdater"; Method = ""; LocalRev = ""; RemoteRev = ""
        RemoteVersion = $null; Message = ""
    }
    if ($Config.IsTest) {
        $status.State = "Test"
        $status.Message = "Local test install; it never updates."
        return [pscustomobject]$status
    }
    try {
        if (Test-FLGitInstall) {
            $status.Method = "git"
            & git -c safe.directory=* -c http.lowSpeedLimit=1000 -c http.lowSpeedTime=15 fetch origin $Config.Branch --quiet 2>$null
            if ($LASTEXITCODE -ne 0) {
                $status.State = "Offline"
                $status.Message = "Offline or update server unreachable."
                return [pscustomobject]$status
            }
            $localRev = [string](& git -c safe.directory=* rev-parse HEAD 2>$null)
            $remoteRev = [string](& git -c safe.directory=* rev-parse "origin/$($Config.Branch)" 2>$null)
            $status.LocalRev = $localRev.Trim()
            $status.RemoteRev = $remoteRev.Trim()
            if (-not $status.LocalRev -or -not $status.RemoteRev) {
                $status.State = "Offline"
                $status.Message = "Could not read the update branch."
            } elseif ($status.LocalRev -eq $status.RemoteRev) {
                $status.State = "UpToDate"
            } else {
                & git -c safe.directory=* merge-base --is-ancestor "origin/$($Config.Branch)" HEAD 2>$null
                if ($LASTEXITCODE -eq 0) {
                    $status.State = "Ahead"
                    $status.Message = "Local hotfix not yet published."
                } else {
                    $status.State = "Available"
                    try {
                        $text = (& git -c safe.directory=* show "origin/$($Config.Branch):version.json" 2>$null) -join "`n"
                        if ($text) { $status.RemoteVersion = $text.TrimStart([char]0xFEFF) | ConvertFrom-Json }
                    } catch {}
                }
            }
        } elseif ($Config.ZipUrl -and $Config.VersionUrl) {
            $status.Method = "zip"
            Enable-FLTls12
            $remote = $null
            try {
                $prevProgress = $ProgressPreference
                $ProgressPreference = "SilentlyContinue"
                $response = Invoke-WebRequest -Uri $Config.VersionUrl -UseBasicParsing -TimeoutSec 15
                $ProgressPreference = $prevProgress
                $remote = ([string]$response.Content).TrimStart([char]0xFEFF) | ConvertFrom-Json
            } catch { $remote = $null }
            if (-not $remote -or -not $remote.version) {
                $status.State = "Offline"
                $status.Message = "Offline or update server unreachable."
                return [pscustomobject]$status
            }
            $status.RemoteVersion = $remote
            $local = Read-FLJson (Join-Path $Here "version.json")
            if ($local -and ([string]$local.version -eq [string]$remote.version) -and
                ([string]$local.updated_at -eq [string]$remote.updated_at)) {
                $status.State = "UpToDate"
            } else {
                $status.State = "Available"
            }
        } elseif ($Config.ZipUrl) {
            $status.Method = "zip"
            $status.State = "Offline"
            $status.Message = "No version URL configured for the ZIP updater."
        } else {
            $status.Message = "This install has no update source."
        }
    } catch {
        $status.State = "Offline"
        $status.Message = "Update check failed: $($_.Exception.Message)"
    }
    return [pscustomobject]$status
}

# Download with progress reports (Report: scriptblock text, percent [-1 = unknown]).
function Invoke-FLDownload {
    param([string]$Url, [string]$OutFile, [scriptblock]$Report)
    Enable-FLTls12
    $request = [System.Net.WebRequest]::Create($Url)
    $request.Timeout = 30000
    if ($request -is [System.Net.HttpWebRequest]) {
        $request.ReadWriteTimeout = 60000
        $request.UserAgent = "FantasyLife-PC-Launcher"
    }
    $response = $request.GetResponse()
    try {
        $total = $response.ContentLength
        $in = $response.GetResponseStream()
        $out = [System.IO.File]::Create($OutFile)
        try {
            $buffer = New-Object byte[] 262144
            $done = [long]0
            $lastReport = [DateTime]::MinValue
            while (($n = $in.Read($buffer, 0, $buffer.Length)) -gt 0) {
                $out.Write($buffer, 0, $n)
                $done += $n
                if ($Report -and ([DateTime]::UtcNow - $lastReport).TotalMilliseconds -gt 200) {
                    $lastReport = [DateTime]::UtcNow
                    if ($total -gt 0) {
                        & $Report ("Downloading {0:N1} / {1:N1} MB" -f ($done / 1MB), ($total / 1MB)) ([int](100 * $done / $total))
                    } else {
                        & $Report ("Downloading {0:N1} MB" -f ($done / 1MB)) -1
                    }
                }
            }
        } finally {
            $out.Dispose()
            $in.Dispose()
        }
    } finally {
        $response.Close()
    }
}

# Apply an available update. Returns @{ Applied; Message }. Safety: only tracked
# files (git reset --hard) or the package folders/scripts below (ZIP) change;
# game/, saves/, logs/, settings.ini, console_id, channel.env and launcher
# preferences are never touched, and git clean is never run.
function Invoke-FLUpdate {
    param($Config, [scriptblock]$Report)
    $ErrorActionPreference = "Continue"
    if (-not $Report) { $Report = { param($Text, $Percent) Write-Host "[Updater] $Text" -ForegroundColor Cyan } }
    if ($Config.IsTest) { return [pscustomobject]@{ Applied = $false; Message = "Test installs never update." } }
    if ((Get-FLRunningGames).Count -gt 0) {
        return [pscustomobject]@{ Applied = $false; Message = "Close Fantasy Life before updating." }
    }

    if (Test-FLGitInstall) {
        & $Report "Checking the update server..." -1
        & git -c safe.directory=* -c http.lowSpeedLimit=1000 -c http.lowSpeedTime=30 fetch origin $Config.Branch --quiet 2>$null
        if ($LASTEXITCODE -ne 0) { return [pscustomobject]@{ Applied = $false; Message = "Offline or update server unreachable." } }
        $localRev = ([string](& git -c safe.directory=* rev-parse HEAD 2>$null)).Trim()
        $remoteRev = ([string](& git -c safe.directory=* rev-parse "origin/$($Config.Branch)" 2>$null)).Trim()
        if (-not $localRev -or -not $remoteRev) { return [pscustomobject]@{ Applied = $false; Message = "Could not read the update branch." } }
        if ($localRev -eq $remoteRev) { return [pscustomobject]@{ Applied = $false; Message = "Already up to date ($($localRev.Substring(0, 7)))." } }
        # Keep a local, unpublished hotfix: HEAD strictly ahead of origin.
        & git -c safe.directory=* merge-base --is-ancestor "origin/$($Config.Branch)" HEAD 2>$null
        if ($LASTEXITCODE -eq 0) {
            return [pscustomobject]@{ Applied = $false; Message = "Local hotfix not yet published ($($localRev.Substring(0, 7)) ahead of $($remoteRev.Substring(0, 7)))." }
        }
        # origin is ahead or the branches diverged: mirror origin exactly.
        # reset --hard only touches tracked files; game/, saves/, logs/,
        # settings.ini and console_id are ignored and stay untouched. Never git clean.
        & $Report "Installing the new build..." -1
        & git -c safe.directory=* reset --hard "origin/$($Config.Branch)" 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0) { return [pscustomobject]@{ Applied = $false; Message = "Update failed (git reset); the previous version stays installed." } }
        return [pscustomobject]@{ Applied = $true; Message = "Updated $($localRev.Substring(0, 7)) -> $($remoteRev.Substring(0, 7))." }
    }

    if (-not $Config.ZipUrl) { return [pscustomobject]@{ Applied = $false; Message = "This install has no update source." } }

    $ErrorActionPreference = "Stop"
    $tmpDir = Join-Path $Here ".update-tmp"
    $downloaded = $false
    try {
        $local = Read-FLJson (Join-Path $Here "version.json")
        & $Report "Checking the update server..." -1
        $remote = $null
        if ($Config.VersionUrl) {
            try {
                Enable-FLTls12
                $prevProgress = $ProgressPreference
                $ProgressPreference = "SilentlyContinue"
                $response = Invoke-WebRequest -Uri $Config.VersionUrl -UseBasicParsing -TimeoutSec 15
                $ProgressPreference = $prevProgress
                $remote = ([string]$response.Content).TrimStart([char]0xFEFF) | ConvertFrom-Json
            } catch { $remote = $null }
        }
        if (-not $remote -or -not $remote.version) {
            # No network, 404, unparseable version.json, or no URL: never
            # download the large ZIP blindly.
            return [pscustomobject]@{ Applied = $false; Message = "Offline or update server unreachable." }
        }
        if ($local -and ([string]$local.version -eq [string]$remote.version) -and
            ([string]$local.updated_at -eq [string]$remote.updated_at)) {
            return [pscustomobject]@{ Applied = $false; Message = "Already up to date ($($remote.version))." }
        }

        if (Test-Path -LiteralPath $tmpDir) { Remove-Item -LiteralPath $tmpDir -Recurse -Force }
        New-Item -ItemType Directory -Path $tmpDir | Out-Null
        $downloaded = $true
        $zipFile = Join-Path $tmpDir "update.zip"
        Invoke-FLDownload -Url $Config.ZipUrl -OutFile $zipFile -Report $Report

        & $Report "Unpacking..." -1
        $extractDir = Join-Path $tmpDir "extract"
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        [System.IO.Compression.ZipFile]::ExtractToDirectory($zipFile, $extractDir)

        # GitHub archive ZIPs have one top-level folder; portable packages are flat.
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

        & $Report "Installing the new build..." -1
        # Runtime/data first (bin\ includes the launcher window and icon tools).
        foreach ($sub in @("bin", "lib", "data\yw2-recomp\shader-cache-v3", "contrib")) {
            $src = Join-Path $packageRoot $sub
            $dst = Join-Path $Here $sub
            if (Test-Path -LiteralPath $src -PathType Container) {
                New-Item -ItemType Directory -Path $dst -Force | Out-Null
                foreach ($item in @(Get-ChildItem -LiteralPath $src -Force -ErrorAction SilentlyContinue)) {
                    Copy-Item -LiteralPath $item.FullName -Destination $dst -Recurse -Force
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

        # Scripts last. channel.env, test-version.json, game/, saves/, logs/,
        # settings.ini, console_id and launcher.json are never in this list.
        # New launcher files live under bin\launcher\ so older updaters (which
        # only know this fixed list) still deliver them.
        foreach ($name in @(
            "play.ps1", "play.bat", "play.sh", "setup-firewall.ps1",
            "install-windows.ps1", "Install-Windows.bat",
            "install-test.ps1", "Install-Test.bat", "install-linux.sh",
            "publish-update.ps1", "publish-test.ps1",
            "README.txt", "update-config.env", ".gitignore"
        )) {
            $src = Join-Path $packageRoot $name
            $dst = Join-Path $Here $name
            if (Test-Path -LiteralPath $src -PathType Leaf) {
                Copy-Item -LiteralPath $src -Destination $dst -Force
            }
        }
        return [pscustomobject]@{ Applied = $true; Message = "Updated to $($remote.version)." }
    } catch {
        return [pscustomobject]@{ Applied = $false; Message = "Update skipped ($($_.Exception.Message)); the previous version stays installed." }
    } finally {
        if ($downloaded -and (Test-Path -LiteralPath $tmpDir)) {
            Remove-Item -LiteralPath $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

# Seed per-machine settings on first run (never share console_id!).
function Initialize-FLSettings {
    $dataDir = Join-Path $Here "data\yw2-recomp"
    New-Item -ItemType Directory -Path $dataDir -Force | Out-Null
    $ini = Join-Path $dataDir "settings.ini"
    $default = Join-Path $dataDir "settings.default.ini"
    if (-not (Test-Path -LiteralPath $ini) -and (Test-Path -LiteralPath $default)) {
        Copy-Item -LiteralPath $default -Destination $ini
    }
}

function Test-FLSaveName {
    param([string]$Name)
    return ($Name -match '^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$')
}

function Get-FLLogFile {
    param([string]$SaveName)
    $logDir = Join-Path $Here "logs"
    # One log per save profile, so two windows (e.g. a multiplayer test) don't share one.
    return (Join-Path $logDir $(if ($SaveName -eq "freelife") { "play.log" } else { "play-$SaveName.log" }))
}

# Start the game (or the Clockwork settings launcher). ModDirs empty = vanilla.
# The environment is passed through ProcessStartInfo: Windows PowerShell deletes a
# variable assigned "" ($env:X = ""), and the runtime treats a MISSING FL_MOD_DIRS
# as "load every installed overlay". An explicitly empty FL_MOD_DIRS means no mods.
function Start-FLGame {
    param(
        [Parameter(Mandatory = $true)][string]$SaveName,
        [string[]]$ModDirs = @(),
        [switch]$SettingsLauncher,
        [switch]$NoDlc,
        [Parameter(Mandatory = $true)][string]$ExePath,
        [Parameter(Mandatory = $true)][string]$RomPath,
        [string]$DlcPath = "",
        [switch]$NoWindow
    )
    if (-not (Test-FLSaveName $SaveName)) { throw "Invalid save profile name: $SaveName" }
    $saveDir = Join-Path $Here "saves\$SaveName"
    $logDir = Join-Path $Here "logs"
    New-Item -ItemType Directory -Path $saveDir -Force | Out-Null
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
    $logFile = Get-FLLogFile $SaveName

    $mode = if ($SettingsLauncher) { "--launcher" } else { "--play" }
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $env:ComSpec
    # The game logs to stderr; let cmd do the redirect.
    $psi.Arguments = "/d /s /c `"`"$ExePath`" $mode `"$RomPath`" > `"$logFile`" 2>&1`""
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = [bool]$NoWindow
    $psi.WorkingDirectory = $Here
    $vars = $psi.EnvironmentVariables
    $vars["APPDATA"] = Join-Path $Here "data"
    $vars["XDG_DATA_HOME"] = Join-Path $Here "data"
    $vars["YW2_STATE_DIR"] = $saveDir
    $vars["YW2_WIDESCREEN"] = "0"
    $vars["YW2_INTERP"] = "0"
    $vars["YW2_SCALE"] = "1"
    if (-not $env:FL_FPS) { $vars["FL_FPS"] = "0" }
    if (-not $env:YW2_FPS) { $vars["YW2_FPS"] = "0" }
    $vars["FL_DLC_CIA"] = $(if ($NoDlc -or -not $DlcPath) { "" } else { $DlcPath })
    $vars["FL_MOD_DIRS"] = (@($ModDirs | Where-Object { $_ }) -join ";")
    if ($vars.ContainsKey("FL_MOD_DIR")) { $vars.Remove("FL_MOD_DIR") }
    $binDir = Split-Path -Parent $ExePath
    $vars["PATH"] = "$binDir;$(Join-Path $Here 'bin');$env:PATH"

    $process = [System.Diagnostics.Process]::Start($psi)
    return [pscustomobject]@{ Process = $process; LogFile = $logFile; SaveDir = $saveDir }
}

# Desktop integration: generate the icon from the player's own dump (never shipped
# in the public package) and point this install's shortcuts at it and at the
# console-less launcher. Returns a short status line. Never throws.
function Update-FLDesktopIntegration {
    param($Config, [string]$RomPath)
    try {
        $iconTool = Join-Path $Here "bin\launcher\icon.ps1"
        if (-not (Test-Path -LiteralPath $iconTool)) { return "icon tools missing" }
        . $iconTool
        $icon = $null
        $iconNote = ""
        try {
            if ($RomPath) { $icon = Update-FantasyLifeIcon -RomPath $RomPath -OutDir (Join-Path $Here "data\yw2-recomp") }
            else { $iconNote = " (no game dump found for the icon)" }
        } catch {
            $iconNote = " (game icon unavailable: $($_.Exception.Message))"
        }
        if (-not $icon) { $icon = Join-Path $Here "bin\fantasy-life.ico" }
        $names = if ($Config.IsTest) { @("Fantasy Life (Test).lnk") } else { @("Fantasy Life.lnk") }
        $desc = if ($Config.IsTest) { "Fantasy Life PC - TEST build (local only, no auto-update)" } else { "Fantasy Life PC" }
        $target = Get-FantasyLifeLaunchTarget -InstallDir $Here
        $changed = Repair-FantasyLifeShortcuts -InstallDir $Here -IconPath $icon -TargetPath $target.TargetPath `
            -Arguments $target.Arguments -Description $desc -Names $names
        return ("icon {0}; {1} shortcut(s) updated{2}" -f (Split-Path -Leaf $icon), $changed, $iconNote)
    } catch {
        return "desktop integration skipped: $($_.Exception.Message)"
    }
}

function Write-FLLauncherLog {
    param([string]$Text)
    try {
        $logDir = Join-Path $Here "logs"
        New-Item -ItemType Directory -Path $logDir -Force | Out-Null
        $file = Join-Path $logDir "launcher.log"
        if ((Test-Path -LiteralPath $file) -and (Get-Item -LiteralPath $file).Length -gt 512KB) {
            Move-Item -LiteralPath $file -Destination "$file.old" -Force
        }
        Add-Content -LiteralPath $file -Value ("{0:yyyy-MM-dd HH:mm:ss} {1}" -f (Get-Date), $Text) -Encoding UTF8
    } catch {}
}

if ($LibraryOnly) { return }

# ---------------------------------------------------------------------------
# Launcher window (default for the desktop shortcut and play.bat without arguments)
# ---------------------------------------------------------------------------

$Config = Get-FLConfig
$ActionFlags = $Direct -or $Vanilla -or $Launcher -or $NoLaunch -or $SetupFirewall
$WindowMode = $Window -or $Preview -or $Screenshot -or (-not $ActionFlags -and $env:FL_DIRECT -ne "1" -and [Environment]::UserInteractive)

if ($WindowMode) {
    $WindowScript = Join-Path $Here "bin\launcher\window.ps1"
    $windowError = $null
    if (Test-Path -LiteralPath $WindowScript -PathType Leaf) {
        try {
            . $WindowScript
            $code = Show-FLLauncherWindow -Config $Config -InitialSave $Save -NoUpdateCheck:$NoUpdate -NoDlc:$NoDlc `
                -NoFirewall:$NoFirewall -AfterUpdate $AfterUpdate -Preview:$Preview -Screenshot $Screenshot
            exit $code
        } catch {
            $windowError = $_
            Write-FLLauncherLog ("Launcher window failed: " + $_.Exception.Message + "`n" + $_.ScriptStackTrace)
        }
    } else {
        $windowError = "bin\launcher\window.ps1 is missing"
    }
    # The window could not open: fall back to direct play in a visible console so
    # errors stay readable.
    if ($Hidden) {
        try {
            Add-Type -AssemblyName PresentationFramework -ErrorAction SilentlyContinue
            [System.Windows.MessageBox]::Show("The launcher window could not open ($windowError). The game starts directly instead; see logs\launcher.log.", "Fantasy Life", "OK", "Warning") | Out-Null
        } catch {}
        Start-Process -FilePath (Join-Path $Here "play.bat") -ArgumentList "-Direct" -WorkingDirectory $Here
        exit 0
    }
    Write-Host "[Launcher] Window unavailable ($windowError); starting directly." -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# Direct mode (play.ps1 -Direct, -Vanilla, -Launcher, -NoLaunch, -SetupFirewall)
# ---------------------------------------------------------------------------

if (-not $Save) { $Save = "freelife" }
if (-not (Test-FLSaveName $Save)) { Write-Error "Invalid save profile name: $Save"; exit 1 }

# 1. Update check (direct mode keeps the old automatic update unless -NoUpdate).
if (-not $Config.IsTest -and -not $NoUpdate -and $env:FL_NO_UPDATE -ne "1") {
    $status = Get-FLUpdateStatus -Config $Config
    switch ($status.State) {
        "UpToDate" { Write-Host "[Updater] Already up to date." -ForegroundColor DarkGray }
        "Ahead"    { Write-Host "[Updater] $($status.Message)" -ForegroundColor Yellow }
        "Available" {
            $result = Invoke-FLUpdate -Config $Config
            $color = if ($result.Applied) { "Green" } else { "Yellow" }
            Write-Host "[Updater] $($result.Message)" -ForegroundColor $color
            Write-FLLauncherLog "Direct update: $($result.Message)"
        }
        default    { if ($status.Message) { Write-Host "[Updater] $($status.Message) Continuing with the local version." -ForegroundColor Yellow } }
    }
}

# 2. Print version / mod compatibility digest
$LocalVersion = Get-FLLocalVersion -Config $Config
if ($Config.IsTest) {
    if ($LocalVersion) {
        $TestLabel = if ($LocalVersion.label) { $LocalVersion.label } else { "(unlabeled)" }
        Write-Host ("==============================================================") -ForegroundColor DarkYellow
        Write-Host (" TEST BUILD | {0}" -f $TestLabel) -ForegroundColor Yellow
        if ($LocalVersion.exe_source) { Write-Host (" Exe source:  {0}" -f $LocalVersion.exe_source) -ForegroundColor Yellow }
        if ($LocalVersion.exe_sha256) { Write-Host (" Exe SHA-256: {0}" -f $LocalVersion.exe_sha256) -ForegroundColor Yellow }
        if ($LocalVersion.mods)       { Write-Host (" Mods:        {0}" -f (@($LocalVersion.mods) -join ", ")) -ForegroundColor Yellow }
        if ($LocalVersion.date)       { Write-Host (" Published:   {0}" -f $LocalVersion.date) -ForegroundColor Yellow }
        Write-Host (" Local test install - auto-update disabled.") -ForegroundColor DarkYellow
        Write-Host ("==============================================================") -ForegroundColor DarkYellow
    } else {
        Write-Host "[Test] Missing or unreadable test-version.json. Run publish-test.ps1 to fill this test install." -ForegroundColor Yellow
    }
} elseif ($LocalVersion) {
    Write-Host ("==============================================================") -ForegroundColor DarkCyan
    Write-Host (" Fantasy Life PC | Build: {0} | Updated: {1}" -f $LocalVersion.version, $LocalVersion.updated_at) -ForegroundColor Cyan
    Write-Host (" Mod Digest:     {0} ({1})" -f $LocalVersion.mod_digest, (@($LocalVersion.mods) -join ", ")) -ForegroundColor Cyan
    Write-Host ("==============================================================") -ForegroundColor DarkCyan
}

# 3. Seed per-machine settings on first run (never share console_id!)
Initialize-FLSettings
$RecompDataDir = Join-Path $Here "data\yw2-recomp"

# 4. Locate game dump, DLC CIA and executable
$RomPath = Get-FLRomPath
if (-not $RomPath) {
    Write-Error "Missing Fantasy Life 3DS dump! Place FantasyLife_EU.3ds in $Here\game\"
    exit 1
}
$DlcPath = Get-FLDlcPath
$ExePath = Get-FLExePath -Config $Config
if (-not $ExePath) {
    if ($Config.IsTest) {
        Write-Error "fl_eur.exe not found in $Here\bin\fl_eur.exe. Run publish-test.ps1 -Exe <built fl_eur.exe> to fill this test install."
    } else {
        Write-Error "fl_eur.exe not found in $Here\bin\fl_eur.exe yet. Run publish-update.ps1 once the Windows build completes."
    }
    exit 1
}

# 4b. Desktop icon from the player's dump + shortcut repair (quiet, never fatal).
$Integration = Update-FLDesktopIntegration -Config $Config -RomPath $RomPath
Write-Host "[Desktop] $Integration" -ForegroundColor DarkGray

# 5. Windows Firewall for multiplayer. Reading rules works without admin, so the
#    check is cheap and silent when everything is already in place. Only a "yes"
#    starts setup-firewall.ps1 through one UAC prompt.
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
# 6. Mods: -Vanilla = none; an FL_MOD_DIRS set in the calling environment wins;
#    otherwise the build's mod list (version.json / test-version.json).
$ModDirs = @()
if ($Vanilla) {
    $ModDirs = @()
    Write-Host "[Mods] Vanilla: no data mods (FL_MOD_DIRS is passed empty)." -ForegroundColor Cyan
} elseif ($null -ne [Environment]::GetEnvironmentVariable("FL_MOD_DIRS")) {
    $ModDirs = @(([string]$env:FL_MOD_DIRS).Split(";") | Where-Object { $_ })
    Write-Host "[Mods] Using FL_MOD_DIRS from the environment ($($ModDirs.Count) dir(s))." -ForegroundColor Cyan
} else {
    $ModInfo = Get-FLMods -Config $Config -LocalVersion $LocalVersion
    if ($ModInfo.Note) { Write-Host "[Mods] $($ModInfo.Note)" -ForegroundColor Yellow }
    foreach ($mod in $ModInfo.Mods) {
        if (-not $mod.Present) { throw "Installed mod '$($mod.Folder)' is missing. Update the normal game before playing." }
    }
    $ModDirs = @($ModInfo.Mods | ForEach-Object { $_.Path })
    if ($ModInfo.Mods.Count -gt 0) {
        Write-Host ("[Mods] {0}" -f (@($ModInfo.Mods | ForEach-Object { $_.Name }) -join ", ")) -ForegroundColor Cyan
    }
}

if ($NoLaunch) {
    Write-Host ("[Launch] Save profile: {0}; mods: {1}; DLC: {2}" -f $Save, $(if ($ModDirs.Count) { $ModDirs -join ";" } else { "(none - vanilla)" }), $(if ($NoDlc -or -not $DlcPath) { "(off)" } else { $DlcPath })) -ForegroundColor DarkGray
    Write-Host "[Launch] -NoLaunch set; exiting without starting the game." -ForegroundColor DarkGray
    exit 0
}

$Started = Start-FLGame -SaveName $Save -ModDirs $ModDirs -SettingsLauncher:$Launcher -NoDlc:$NoDlc `
    -ExePath $ExePath -RomPath $RomPath -DlcPath $(if ($DlcPath) { $DlcPath } else { "" })
Write-Host "[Launch] Save profile: $Save ($($Started.SaveDir))" -ForegroundColor Green
Write-Host "[Launch] Log output:   $($Started.LogFile)" -ForegroundColor DarkGray
$Started.Process.WaitForExit()
exit $Started.Process.ExitCode
