[CmdletBinding(PositionalBinding = $false)]
param(
    [string]$TargetDir = (Join-Path $env:LOCALAPPDATA "FantasyLife-PC-Test"),
    [string]$StableDir = (Join-Path $env:LOCALAPPDATA "FantasyLife-PC"),
    [string]$DumpDir = "",
    [switch]$CopyStableSaves,
    [switch]$NoShortcuts,
    [switch]$NoPrompt,
    [switch]$NoFirewall
)

$ErrorActionPreference = "Stop"

# This script lives at the root of a package exported by publish-test.ps1.
$SourceDir = $PSScriptRoot
if (-not $SourceDir) { $SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path }
$SourceFull = [System.IO.Path]::GetFullPath($SourceDir).TrimEnd("\")
if (-not (Test-Path -LiteralPath (Join-Path $SourceFull "bin\fl_eur.exe") -PathType Leaf) -and
    (Test-Path -LiteralPath (Join-Path $SourceFull "FantasyLife-PC-Test\bin\fl_eur.exe") -PathType Leaf)) {
    $SourceFull = [System.IO.Path]::GetFullPath((Join-Path $SourceFull "FantasyLife-PC-Test")).TrimEnd("\")
}

function Test-GameSource {
    param([string]$Dir)
    if (-not $Dir -or -not (Test-Path -LiteralPath $Dir -PathType Container)) { return $false }
    if (Test-Path -LiteralPath (Join-Path $Dir "FantasyLife_EU.3ds") -PathType Leaf) { return $true }
    $any3ds = @(Get-ChildItem -LiteralPath $Dir -File -Filter "*.3ds" -ErrorAction SilentlyContinue)
    return ($any3ds.Count -gt 0)
}

# Accept either a folder holding the dumps directly or a stable install root
# with a game\ subfolder.
function Resolve-GameSource {
    param([string]$Dir)
    if (-not $Dir) { return $null }
    $nested = Join-Path $Dir "game"
    if (Test-Path -LiteralPath $nested -PathType Container) {
        if (Test-GameSource $nested) { return $nested }
    }
    if (Test-GameSource $Dir) { return $Dir }
    return $null
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

function Sync-Directory {
    param([string]$From, [string]$To)
    if (-not (Test-Path -LiteralPath $From -PathType Container)) { return }
    if (-not (Test-Path -LiteralPath $To)) {
        New-Item -ItemType Directory -Path $To -Force | Out-Null
    }
    $fromFull = (Resolve-Path -LiteralPath $From).Path.TrimEnd("\")
    $toFull = (Resolve-Path -LiteralPath $To).Path.TrimEnd("\")
    if ($fromFull -eq $toFull) { return }
    $robo = Get-Command robocopy -ErrorAction SilentlyContinue
    if ($robo) {
        & robocopy $From $To /MIR /R:2 /W:1 /NP /NFL /NDL | Out-Null
        if ($LASTEXITCODE -ge 8) {
            throw "robocopy failed (exit $LASTEXITCODE) syncing $From -> $To"
        }
    } else {
        Get-ChildItem -LiteralPath $To -Force | Remove-Item -Recurse -Force
        Copy-Item -Path (Join-Path $From "*") -Destination $To -Recurse -Force
    }
}

# One-way merge: never overwrite an existing test save.
function Copy-MissingFiles {
    param([string]$From, [string]$To)
    if (-not (Test-Path -LiteralPath $From -PathType Container)) { return 0 }
    $copied = 0
    foreach ($file in @(Get-ChildItem -LiteralPath $From -Recurse -File -ErrorAction SilentlyContinue)) {
        $relative = $file.FullName.Substring($From.Length).TrimStart("\")
        $dst = Join-Path $To $relative
        if (Test-Path -LiteralPath $dst) { continue }
        $parent = Split-Path -Parent $dst
        if ($parent) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
        Copy-Item -LiteralPath $file.FullName -Destination $dst -Force
        $copied++
    }
    return $copied
}

$TargetFull = [System.IO.Path]::GetFullPath($TargetDir).TrimEnd("\")
$StableFull = [System.IO.Path]::GetFullPath($StableDir).TrimEnd("\")

if ($TargetFull -eq $StableFull -or $TargetFull.StartsWith($StableFull + "\")) {
    throw "Refusing to install the test build onto the stable install: $TargetFull"
}
if (-not (Test-Path -LiteralPath (Join-Path $SourceFull "bin\fl_eur.exe") -PathType Leaf)) {
    throw "This test package is incomplete: bin\fl_eur.exe was not found in $SourceFull"
}

Write-Host "==============================================================" -ForegroundColor Yellow
Write-Host " Fantasy Life PC - install the TEST build on this PC" -ForegroundColor Yellow
Write-Host " Package:            $SourceFull" -ForegroundColor Gray
Write-Host " Test install:       $TargetFull" -ForegroundColor Gray
Write-Host " Stable (read only): $StableFull" -ForegroundColor Gray
Write-Host "==============================================================" -ForegroundColor Yellow

# 1. Find the game dump: this PC's stable install first, then ask.
$GameSource = $null
if ($DumpDir) {
    if (-not (Test-Path -LiteralPath $DumpDir -PathType Container)) {
        throw "Dump path not found: $DumpDir"
    }
    $GameSource = Resolve-GameSource (Resolve-Path -LiteralPath $DumpDir).Path
    if (-not $GameSource) {
        throw "No .3ds game dump found in $DumpDir (expected FantasyLife_EU.3ds)."
    }
} else {
    $stableGame = Join-Path $StableFull "game"
    if (Test-GameSource $stableGame) { $GameSource = $stableGame }
}
if (-not $GameSource) {
    Write-Host ""
    Write-Host "No game dump found in this PC's stable install:" -ForegroundColor Yellow
    Write-Host "  $StableFull\game is missing or contains no .3ds file." -ForegroundColor Yellow
    Write-Host "The test install needs the same Fantasy Life 3DS dump." -ForegroundColor Yellow
    if ($NoPrompt -or [Console]::IsInputRedirected) {
        throw "Game dump not found. Re-run with: Install-Test.bat -DumpDir `"<folder containing FantasyLife_EU.3ds>`""
    }
    while (-not $GameSource) {
        $answer = Read-Host "Enter the folder that contains FantasyLife_EU.3ds (or press Enter to cancel)"
        if (-not $answer) { throw "Installation cancelled: a game dump is required." }
        $clean = $answer.Trim().Trim('"')
        if (-not (Test-Path -LiteralPath $clean -PathType Container)) {
            Write-Host "Not a folder: $clean" -ForegroundColor Yellow
            continue
        }
        $GameSource = Resolve-GameSource (Resolve-Path -LiteralPath $clean).Path
        if (-not $GameSource) {
            Write-Host "No .3ds file found there (expected FantasyLife_EU.3ds)." -ForegroundColor Yellow
        }
    }
}
Write-Host "[Game]     Using dumps from $GameSource" -ForegroundColor Green

# 2. Create the install layout. Existing saves, logs, settings.ini and
#    console_id are never deleted or overwritten.
$BinDir    = Join-Path $TargetFull "bin"
$DataDir   = Join-Path $TargetFull "data\yw2-recomp"
$ModsRoot  = Join-Path $DataDir "mods\fantasylife"
$ShaderDir = Join-Path $DataDir "shader-cache-v3"
$GameDir   = Join-Path $TargetFull "game"
$SavesDir  = Join-Path $TargetFull "saves"
$LogsDir   = Join-Path $TargetFull "logs"
$TargetExe = Join-Path $BinDir "fl_eur.exe"
$TargetRelay = Join-Path $BinDir "clockwork-relay.exe"

foreach ($d in @($BinDir, $DataDir, $ModsRoot, $ShaderDir, $GameDir, $SavesDir, $LogsDir)) {
    New-Item -ItemType Directory -Path $d -Force | Out-Null
}

$SameDir = ($SourceFull -eq $TargetFull)

# 3. Launchers, manifest and the test channel marker.
if (-not $SameDir) {
    foreach ($name in @("play.ps1", "play.bat", "play.sh", "setup-firewall.ps1", "channel.env", "test-version.json", "README.txt", "install-test.ps1", "Install-Test.bat")) {
        $src = Join-Path $SourceFull $name
        if (Test-Path -LiteralPath $src -PathType Leaf) {
            Copy-Item -LiteralPath $src -Destination (Join-Path $TargetFull $name) -Force
        }
    }
}
$channelText = "# Local test install marker written by publish-test.ps1`r`nFL_CHANNEL=test`r`n"
Set-Content -Path (Join-Path $TargetFull "channel.env") -Value $channelText -Encoding ASCII

# 4. Runtime: mirror bin/ (exe, DLLs, relay, icon) and the mod overlays.
if (-not $SameDir) {
    Sync-Directory (Join-Path $SourceFull "bin") $BinDir

    $srcMods = Join-Path $SourceFull "data\yw2-recomp\mods\fantasylife"
    if (Test-Path -LiteralPath $srcMods -PathType Container) {
        Sync-Directory $srcMods $ModsRoot
    } else {
        Get-ChildItem -LiteralPath $ModsRoot -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
    }

    $srcShader = Join-Path $SourceFull "data\yw2-recomp\shader-cache-v3"
    if (Test-Path -LiteralPath $srcShader -PathType Container) {
        $shaderCount = 0
        $shaderFiles = @(Get-ChildItem -LiteralPath $srcShader -Recurse -File -ErrorAction SilentlyContinue | Where-Object {
            $_.Extension -notin @(".log", ".tmp") -and $_.Name -notlike "*.tmp*"
        })
        foreach ($file in $shaderFiles) {
            $relative = $file.FullName.Substring($srcShader.Length).TrimStart("\")
            $dst = Join-Path $ShaderDir $relative
            $parent = Split-Path -Parent $dst
            if ($parent) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
            Copy-Item -LiteralPath $file.FullName -Destination $dst -Force
            $shaderCount++
        }
        Write-Host "[Data]     Synced shader cache ($shaderCount file(s))" -ForegroundColor Green
    }

    $defaultIni = Join-Path $SourceFull "data\yw2-recomp\settings.default.ini"
    if (Test-Path -LiteralPath $defaultIni -PathType Leaf) {
        Copy-Item -LiteralPath $defaultIni -Destination (Join-Path $DataDir "settings.default.ini") -Force
    }
}

# Seed settings.ini only on first install; never touch an existing one.
$SettingsIni = Join-Path $DataDir "settings.ini"
$DefaultIni = Join-Path $DataDir "settings.default.ini"
if (-not (Test-Path -LiteralPath $SettingsIni) -and (Test-Path -LiteralPath $DefaultIni)) {
    Copy-Item -LiteralPath $DefaultIni -Destination $SettingsIni -Force
    Write-Host "[Data]     Seeded settings.ini from settings.default.ini" -ForegroundColor Green
}

# 5. Game dumps: hard link on the same volume, copy as fallback. Existing game
#    files in the test install are kept.
$linkCount = 0
$copyCount = 0
$existingCount = 0
$gameFiles = @(Get-ChildItem -LiteralPath $GameSource -Recurse -File -ErrorAction SilentlyContinue)
foreach ($file in $gameFiles) {
    $relative = $file.FullName.Substring($GameSource.Length).TrimStart("\")
    $dst = Join-Path $GameDir $relative
    $how = Link-GameFile $file.FullName $dst
    if ($how -eq "hardlink") { $linkCount++ }
    elseif ($how -eq "copy") { $copyCount++ }
    else { $existingCount++ }
}
Write-Host ("[Game]     {0} file(s): {1} hard link(s), {2} copy/copies, {3} already present" -f $gameFiles.Count, $linkCount, $copyCount, $existingCount) -ForegroundColor Green

# 6. Optional one-way copy of this PC's stable saves. Existing test saves win.
$StableSaves = Join-Path $StableFull "saves"
$doCopySaves = [bool]$CopyStableSaves
if (-not $doCopySaves -and (Test-Path -LiteralPath $StableSaves -PathType Container) -and
    -not $NoPrompt -and -not [Console]::IsInputRedirected) {
    $answer = Read-Host "Copy this PC's stable saves into the test install? Existing test saves are kept; only missing files are copied. [y/N]"
    if ($answer -match "^(?i)y") { $doCopySaves = $true }
}
if ($doCopySaves) {
    if (Test-Path -LiteralPath $StableSaves -PathType Container) {
        $copiedSaves = Copy-MissingFiles $StableSaves $SavesDir
        Write-Host "[Saves]    Copied $copiedSaves missing stable save file(s) one-way (test saves kept)" -ForegroundColor Green
    } else {
        Write-Host "[Saves]    Stable saves folder not found; nothing copied." -ForegroundColor Yellow
    }
} else {
    Write-Host "[Saves]    Test saves left alone (use -CopyStableSaves for a one-way copy)" -ForegroundColor DarkGray
}

# 7. Update test-version.json with this PC's paths and the real hashes.
$manifestPath = Join-Path $TargetFull "test-version.json"
$manifest = $null
foreach ($candidateManifest in @($manifestPath, (Join-Path $SourceFull "test-version.json"))) {
    if (Test-Path -LiteralPath $candidateManifest -PathType Leaf) {
        try { $manifest = Get-Content -LiteralPath $candidateManifest -Raw | ConvertFrom-Json } catch { $manifest = $null }
        if ($manifest) { break }
    }
}
if (-not $manifest) {
    Write-Host "[Manifest] WARNING: no readable test-version.json; writing a minimal one." -ForegroundColor Yellow
    $manifest = [pscustomobject]@{ channel = "test"; label = "test build"; mods = @() }
}

$exeHash = ""
if (Test-Path -LiteralPath $TargetExe -PathType Leaf) {
    $exeHash = (Get-FileHash -LiteralPath $TargetExe -Algorithm SHA256).Hash.ToLowerInvariant()
}
$relayHash = ""
if (Test-Path -LiteralPath $TargetRelay -PathType Leaf) {
    $relayHash = (Get-FileHash -LiteralPath $TargetRelay -Algorithm SHA256).Hash.ToLowerInvariant()
}

$manifest | Add-Member -NotePropertyName channel -NotePropertyValue "test" -Force
$manifest | Add-Member -NotePropertyName exe -NotePropertyValue $TargetExe -Force
$manifest | Add-Member -NotePropertyName relay -NotePropertyValue $TargetRelay -Force
$manifest | Add-Member -NotePropertyName exe_sha256 -NotePropertyValue $exeHash -Force
$manifest | Add-Member -NotePropertyName relay_sha256 -NotePropertyValue $relayHash -Force
$manifest | Add-Member -NotePropertyName installed_from -NotePropertyValue $SourceFull -Force
$manifest | Add-Member -NotePropertyName install_date -NotePropertyValue ((Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")) -Force
$manifest | Add-Member -NotePropertyName stable_install -NotePropertyValue $StableFull -Force
if (-not ($manifest.PSObject.Properties.Name -contains "mods")) {
    $manifest | Add-Member -NotePropertyName mods -NotePropertyValue @() -Force
}
$manifestJson = $manifest | ConvertTo-Json -Depth 6
[System.IO.File]::WriteAllText($manifestPath, $manifestJson, (New-Object System.Text.UTF8Encoding($false)))
Write-Host "[Manifest] Updated test-version.json (exe sha256: $exeHash)" -ForegroundColor Cyan

# 8. "Fantasy Life (Test)" shortcuts.
if (-not $NoShortcuts) {
    # The shortcut opens the launcher window; the icon is generated from the
    # game dump (never shipped), with the neutral package icon as fallback.
    $iconPath = Join-Path $BinDir "fantasy-life.ico"
    if (-not (Test-Path -LiteralPath $iconPath)) { $iconPath = $TargetExe }
    $iconTool = Join-Path $BinDir "launcher\icon.ps1"
    $haveTool = Test-Path -LiteralPath $iconTool
    if ($haveTool) {
        . $iconTool
        $rom = Join-Path $GameDir "FantasyLife_EU.3ds"
        if (-not (Test-Path -LiteralPath $rom)) {
            $rom = @(Get-ChildItem -LiteralPath $GameDir -Filter "*.3ds" -File -ErrorAction SilentlyContinue | Select-Object -First 1 | ForEach-Object { $_.FullName })[0]
        }
        try { $iconPath = Get-FantasyLifeIconPath -InstallDir $TargetFull -RomPath $(if ($rom) { $rom } else { "" }) } catch {}
    }
    foreach ($dir in @([Environment]::GetFolderPath("Desktop"), [Environment]::GetFolderPath("Programs"))) {
        if ($dir -and (Test-Path -LiteralPath $dir)) {
            $lnkPath = Join-Path $dir "Fantasy Life (Test).lnk"
            if ($haveTool) {
                Set-FantasyLifeShortcut -Path $lnkPath -InstallDir $TargetFull -IconPath $iconPath -Description "Fantasy Life PC - TEST build (local only, no auto-update)"
            } else {
                $shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut($lnkPath)
                $shortcut.TargetPath = Join-Path $TargetFull "play.bat"
                $shortcut.WorkingDirectory = $TargetFull
                $shortcut.IconLocation = $iconPath + ",0"
                $shortcut.Description = "Fantasy Life PC - TEST build (local only, no auto-update)"
                $shortcut.Save()
            }
            Write-Host "[Shortcut] $lnkPath" -ForegroundColor Green
        }
    }
}

# Optional Firewall button in the launcher is the only elevation entry point.
Write-Host ""
Write-Host "Test install ready: $TargetFull" -ForegroundColor Green
Write-Host "  Shortcut:    Fantasy Life (Test)" -ForegroundColor Green
Write-Host "  Auto-update: Off (local test channel)" -ForegroundColor Green
Write-Host "  Test saves:  $SavesDir" -ForegroundColor Green
Write-Host "  Manifest:    $manifestPath" -ForegroundColor Green
