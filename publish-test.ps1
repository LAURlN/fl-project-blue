[CmdletBinding(PositionalBinding = $false)]
param(
    [string]$Exe = "",
    [string]$Relay = "",
    [string[]]$ModDirs = @(),
    [string]$Label = "",
    [switch]$CopySavesFromStable,
    [string]$StableDir = (Join-Path $env:LOCALAPPDATA "FantasyLife-PC"),
    [string]$TargetDir = (Join-Path $env:LOCALAPPDATA "FantasyLife-PC-Test"),
    [switch]$NoShortcuts
)

$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path

# `powershell.exe -File ... -ModDirs a,b` binds the whole list as one string, so
# expand comma-separated values unless the string is itself an existing path.
$ExpandedModDirs = @()
foreach ($dirValue in $ModDirs) {
    if ($dirValue -and ($dirValue -notmatch ",")) {
        $ExpandedModDirs += $dirValue
    } elseif ($dirValue -and (Test-Path -LiteralPath $dirValue)) {
        $ExpandedModDirs += $dirValue
    } elseif ($dirValue) {
        $ExpandedModDirs += @($dirValue -split "," | Where-Object { $_.Trim() } | ForEach-Object { $_.Trim() })
    }
}
$ModDirs = $ExpandedModDirs

# This script only ever reads the stable install. Every write goes to TargetDir.
$StableFull = [System.IO.Path]::GetFullPath($StableDir).TrimEnd("\")
$TargetFull = [System.IO.Path]::GetFullPath($TargetDir).TrimEnd("\")
if ($TargetFull -eq $StableFull -or $TargetFull.StartsWith($StableFull + "\")) {
    throw "Refusing to use the stable install as the test target: $TargetFull"
}
if (-not (Test-Path -LiteralPath $StableFull)) {
    throw "Stable install not found: $StableFull"
}

if (-not $Label) { $Label = "test build" }

$BinDir    = Join-Path $TargetFull "bin"
$DataDir   = Join-Path $TargetFull "data\yw2-recomp"
$ModsRoot  = Join-Path $DataDir "mods\fantasylife"
$ShaderDir = Join-Path $DataDir "shader-cache-v3"
$GameDir   = Join-Path $TargetFull "game"
$SavesDir  = Join-Path $TargetFull "saves"
$LogsDir   = Join-Path $TargetFull "logs"
$TargetExe = Join-Path $BinDir "fl_eur.exe"
$VersionFile = Join-Path $TargetFull "test-version.json"

foreach ($d in @($BinDir, $DataDir, $ModsRoot, $ShaderDir, $GameDir, $SavesDir, $LogsDir)) {
    New-Item -ItemType Directory -Path $d -Force | Out-Null
}

# Keep the previous manifest so a re-run without -Exe can report the real source.
$PrevVersion = $null
if (Test-Path -LiteralPath $VersionFile) {
    try { $PrevVersion = Get-Content -LiteralPath $VersionFile -Raw | ConvertFrom-Json } catch {}
}

function Copy-FileSafe {
    param([string]$From, [string]$To)
    if (-not (Test-Path -LiteralPath $From -PathType Leaf)) { return $false }
    $parent = Split-Path -Parent $To
    if ($parent) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
    Copy-Item -LiteralPath $From -Destination $To -Force
    return $true
}

function Link-GameFile {
    param([string]$From, [string]$To)
    if (Test-Path -LiteralPath $To) { return "existing" }
    $parent = Split-Path -Parent $To
    if ($parent) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
    try {
        New-Item -ItemType HardLink -Path $To -Value $From -ErrorAction Stop | Out-Null
        return "hardlink"
    } catch {
        Copy-Item -LiteralPath $From -Destination $To -Force
        return "copy"
    }
}

Write-Host "==============================================================" -ForegroundColor Yellow
Write-Host " Fantasy Life PC - publish to local TEST install" -ForegroundColor Yellow
Write-Host " Stable (read only): $StableFull" -ForegroundColor Gray
Write-Host " Test target:        $TargetFull" -ForegroundColor Gray
Write-Host " Label:              $Label" -ForegroundColor Gray
Write-Host "==============================================================" -ForegroundColor Yellow

# 1. Launcher scripts (same play.ps1, channel-aware; no git repo, no updater)
foreach ($name in @("play.ps1", "play.bat", "play.sh", "README.txt")) {
    $src = Join-Path $Here $name
    if (Test-Path -LiteralPath $src) {
        Copy-FileSafe $src (Join-Path $TargetFull $name) | Out-Null
    }
}
$channelText = "# Local test install marker written by publish-test.ps1`r`nFL_CHANNEL=test`r`n"
Set-Content -Path (Join-Path $TargetFull "channel.env") -Value $channelText -Encoding ASCII
Write-Host "[Channel]  Wrote channel.env (FL_CHANNEL=test); auto-update is off" -ForegroundColor Green

# 2. Executable and runtime DLLs
$StableBin = Join-Path $StableFull "bin"
$StableExe = Join-Path $StableBin "fl_eur.exe"
$ExeToCopy = $null
$ExeSourceLabel = $null
$SourceDlls = @()
if ($Exe) {
    if (-not (Test-Path -LiteralPath $Exe -PathType Leaf)) { throw "-Exe not found: $Exe" }
    $ExeToCopy = (Resolve-Path -LiteralPath $Exe).Path
    $ExeSourceLabel = $ExeToCopy
} elseif (-not (Test-Path -LiteralPath $TargetExe -PathType Leaf)) {
    if (-not (Test-Path -LiteralPath $StableExe -PathType Leaf)) { throw "No test exe yet and stable exe missing: $StableExe" }
    $ExeToCopy = $StableExe
    $ExeSourceLabel = $StableExe
} elseif ($PrevVersion -and $PrevVersion.exe_source) {
    $ExeSourceLabel = $PrevVersion.exe_source
} else {
    $ExeSourceLabel = $TargetExe
}

if ($ExeToCopy) {
    Copy-FileSafe $ExeToCopy $TargetExe | Out-Null
    $exeDir = Split-Path -Parent $ExeToCopy
    $SourceDlls = @(Get-ChildItem -LiteralPath $exeDir -Filter "*.dll" -File -ErrorAction SilentlyContinue)
    foreach ($dll in $SourceDlls) {
        Copy-FileSafe $dll.FullName (Join-Path $BinDir $dll.Name) | Out-Null
    }
    Write-Host "[Bin]      Copied fl_eur.exe from $ExeToCopy ($($SourceDlls.Count) DLL(s) beside it)" -ForegroundColor Green
} else {
    Write-Host "[Bin]      Kept existing test fl_eur.exe" -ForegroundColor DarkGray
}

# Stable DLLs are the fallback: only DLLs the new exe did not bring are filled in.
$StableDlls = @(Get-ChildItem -LiteralPath $StableBin -Filter "*.dll" -File -ErrorAction SilentlyContinue)
foreach ($dll in $StableDlls) {
    $dst = Join-Path $BinDir $dll.Name
    if (-not (Test-Path -LiteralPath $dst)) {
        Copy-FileSafe $dll.FullName $dst | Out-Null
    }
}

$RelaySource = $null
$TargetRelay = Join-Path $BinDir "clockwork-relay.exe"
if ($Relay) {
    if (-not (Test-Path -LiteralPath $Relay -PathType Leaf)) { throw "-Relay not found: $Relay" }
    $RelaySource = (Resolve-Path -LiteralPath $Relay).Path
    Copy-FileSafe $RelaySource $TargetRelay | Out-Null
    Write-Host "[Bin]      Copied clockwork-relay.exe from $RelaySource" -ForegroundColor Green
} elseif (-not (Test-Path -LiteralPath $TargetRelay -PathType Leaf)) {
    $stableRelay = Join-Path $StableBin "clockwork-relay.exe"
    if (Copy-FileSafe $stableRelay $TargetRelay) {
        $RelaySource = $stableRelay
        Write-Host "[Bin]      Copied clockwork-relay.exe from stable" -ForegroundColor Green
    }
}

# Icon for the test shortcuts
$iconCandidates = @(
    (Join-Path $Here "bin\fantasy-life.ico"),
    (Join-Path $StableBin "fantasy-life.ico")
)
foreach ($icon in $iconCandidates) {
    if (Test-Path -LiteralPath $icon) {
        Copy-FileSafe $icon (Join-Path $BinDir "fantasy-life.ico") | Out-Null
        break
    }
}

# 3. Mod overlays (only these are enabled by play.ps1 in the test channel)
$DefaultModNames = @("story-skip", "eastern-plains-enemy", "castele-house", "wooden-sword")
$StableModRoot = Join-Path $StableFull "data\yw2-recomp\mods\fantasylife"
$ModSources = @()
if ($ModDirs.Count -gt 0) {
    foreach ($dir in $ModDirs) {
        if (-not (Test-Path -LiteralPath $dir -PathType Container)) { throw "-ModDirs entry not found: $dir" }
        $ModSources += (Resolve-Path -LiteralPath $dir).Path
    }
} else {
    foreach ($name in $DefaultModNames) {
        $candidate = Join-Path $StableModRoot $name
        if (Test-Path -LiteralPath $candidate -PathType Container) { $ModSources += $candidate }
    }
}

if (Test-Path -LiteralPath $ModsRoot) { Remove-Item -LiteralPath $ModsRoot -Recurse -Force }
New-Item -ItemType Directory -Path $ModsRoot -Force | Out-Null
$ModNames = @()
$ModSourcePaths = @()
foreach ($src in $ModSources) {
    $trimmed = $src.TrimEnd("\", "/")
    $name = Split-Path -Leaf $trimmed
    if (-not $name) { throw "Cannot determine a mod name from: $src" }
    Copy-Item -LiteralPath $trimmed -Destination (Join-Path $ModsRoot $name) -Recurse -Force
    $ModNames += $name
    $ModSourcePaths += $trimmed
}
if ($ModNames.Count -gt 0) {
    Write-Host ("[Mods]     Installed {0}: {1}" -f $ModNames.Count, ($ModNames -join ", ")) -ForegroundColor Green
} else {
    Write-Host "[Mods]     No mod overlays found; the test build runs without mods." -ForegroundColor Yellow
}

# 4. Game dumps: hard links on the same volume, copy as fallback. Never copied twice.
$linkCount = 0
$copyCount = 0
$StableGame = Join-Path $StableFull "game"
if (Test-Path -LiteralPath $StableGame) {
    $gameFiles = @(Get-ChildItem -LiteralPath $StableGame -Recurse -File -ErrorAction SilentlyContinue)
    foreach ($file in $gameFiles) {
        $relative = $file.FullName.Substring($StableGame.Length).TrimStart("\")
        $dst = Join-Path $GameDir $relative
        $how = Link-GameFile $file.FullName $dst
        if ($how -eq "hardlink") { $linkCount++ } elseif ($how -eq "copy") { $copyCount++ }
    }
    Write-Host ("[Game]     {0} game file(s): {1} hard link(s), {2} copy/copies, {3} already present" -f $gameFiles.Count, $linkCount, $copyCount, ($gameFiles.Count - $linkCount - $copyCount)) -ForegroundColor Green
} else {
    Write-Host "[Game]     Stable game/ folder not found; the test install has no dump yet." -ForegroundColor Yellow
}

# 5. Shared data: settings.default.ini, shader cache, seeded settings.ini.
#    console_id is deliberately never copied (each install needs its own identity).
$StableData = Join-Path $StableFull "data\yw2-recomp"
Copy-FileSafe (Join-Path $StableData "settings.default.ini") (Join-Path $DataDir "settings.default.ini") | Out-Null

$StableShader = Join-Path $StableData "shader-cache-v3"
$shaderCount = 0
if (Test-Path -LiteralPath $StableShader) {
    $shaderFiles = @(Get-ChildItem -LiteralPath $StableShader -Recurse -File -ErrorAction SilentlyContinue | Where-Object {
        $_.Extension -notin @(".log", ".tmp") -and $_.Name -notlike "*.tmp*"
    })
    foreach ($file in $shaderFiles) {
        $relative = $file.FullName.Substring($StableShader.Length).TrimStart("\")
        Copy-FileSafe $file.FullName (Join-Path $ShaderDir $relative) | Out-Null
        $shaderCount++
    }
}
Write-Host "[Data]     Synced shader cache ($shaderCount file(s)); console_id untouched" -ForegroundColor Green

$SettingsIni = Join-Path $DataDir "settings.ini"
$DefaultIni = Join-Path $DataDir "settings.default.ini"
if (-not (Test-Path -LiteralPath $SettingsIni) -and (Test-Path -LiteralPath $DefaultIni)) {
    Copy-Item -LiteralPath $DefaultIni -Destination $SettingsIni -Force
    Write-Host "[Data]     Seeded settings.ini from settings.default.ini" -ForegroundColor Green
}

# 6. Saves: one-way copy only when explicitly requested. Never test -> stable.
if ($CopySavesFromStable) {
    $StableSaves = Join-Path $StableFull "saves"
    if (Test-Path -LiteralPath $StableSaves) {
        $stableSaveFiles = @(Get-ChildItem -LiteralPath $StableSaves -Recurse -File -ErrorAction SilentlyContinue)
        if ($stableSaveFiles.Count -gt 0) {
            Copy-Item -Path (Join-Path $StableSaves "*") -Destination $SavesDir -Recurse -Force
            Write-Host ("[Saves]    Copied {0} stable save file(s) into the test install (one-way)" -f $stableSaveFiles.Count) -ForegroundColor Green
        } else {
            Write-Host "[Saves]    Stable saves folder is empty; nothing copied." -ForegroundColor Yellow
        }
    } else {
        Write-Host "[Saves]    Stable saves folder missing; nothing copied." -ForegroundColor Yellow
    }
} else {
    Write-Host "[Saves]    Test saves left alone (use -CopySavesFromStable for a one-way copy)" -ForegroundColor DarkGray
}

# 7. Manifest read by play.ps1/play.sh in the test channel
$exeHash = ""
if (Test-Path -LiteralPath $TargetExe -PathType Leaf) {
    $exeHash = (Get-FileHash -LiteralPath $TargetExe -Algorithm SHA256).Hash.ToLowerInvariant()
}
$relayHash = ""
if (Test-Path -LiteralPath $TargetRelay -PathType Leaf) {
    $relayHash = (Get-FileHash -LiteralPath $TargetRelay -Algorithm SHA256).Hash.ToLowerInvariant()
}

$versionObj = [ordered]@{
    channel                = "test"
    label                  = $Label
    date                   = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    exe                    = $TargetExe
    exe_source             = $ExeSourceLabel
    exe_sha256             = $exeHash
    relay                  = $TargetRelay
    relay_source           = $RelaySource
    relay_sha256           = $relayHash
    mods                   = @($ModNames)
    mod_sources            = @($ModSourcePaths)
    copy_saves_from_stable = [bool]$CopySavesFromStable
    stable_install         = $StableFull
}
$versionJson = $versionObj | ConvertTo-Json -Depth 4
[System.IO.File]::WriteAllText($VersionFile, $versionJson, (New-Object System.Text.UTF8Encoding($false)))
Write-Host "[Manifest] Wrote test-version.json (label: $Label, exe sha256: $exeHash)" -ForegroundColor Cyan

# 8. Shortcuts for the test install
if (-not $NoShortcuts) {
    $WshShell = New-Object -ComObject WScript.Shell
    $DesktopDir  = [Environment]::GetFolderPath("Desktop")
    $ProgramsDir = [Environment]::GetFolderPath("Programs")
    foreach ($dir in @($DesktopDir, $ProgramsDir)) {
        if ($dir -and (Test-Path -LiteralPath $dir)) {
            $lnkPath = Join-Path $dir "Fantasy Life (Test).lnk"
            $sc = $WshShell.CreateShortcut($lnkPath)
            $sc.TargetPath       = Join-Path $TargetFull "play.bat"
            $sc.WorkingDirectory = $TargetFull
            $sc.IconLocation     = (Join-Path $BinDir "fantasy-life.ico") + ",0"
            $sc.Description      = "Fantasy Life PC - TEST build (local only, no auto-update)"
            $sc.Save()
            Write-Host "[Shortcut] $lnkPath" -ForegroundColor Green
        }
    }
}

Write-Host ""
Write-Host "Test install ready: $TargetFull" -ForegroundColor Green
Write-Host "  Shortcut:         Fantasy Life (Test)" -ForegroundColor Green
Write-Host "  Auto-update:      Off (local test channel)" -ForegroundColor Green
Write-Host "  Test saves:       $SavesDir" -ForegroundColor Green
Write-Host "  Manifest:         $VersionFile" -ForegroundColor Green
