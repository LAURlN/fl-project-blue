[CmdletBinding(PositionalBinding = $false)]
param(
    [string]$Exe = "",
    [string]$Relay = "",
    [string[]]$ModDirs = @(),
    [string]$Label = "",
    [switch]$CopySavesFromStable,
    [string]$StableDir = (Join-Path $env:LOCALAPPDATA "FantasyLife-PC"),
    [string]$TargetDir = (Join-Path $env:LOCALAPPDATA "FantasyLife-PC-Test"),
    [string]$ExportZip = "",
    [switch]$NoShortcuts,
    [switch]$NoFirewall
)

$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path

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

# Add the test install to Windows Firewall only if a required rule is missing.
# Dot-sourcing setup-firewall.ps1 has a param block of its own, so keep this
# function's parameter name different from -InstallDir.
function Set-TestFirewallIfMissing {
    param([Parameter(Mandatory = $true)][string]$InstallPath)

    if ($NoFirewall -or $env:FL_NO_FIREWALL -eq "1") {
        Write-Host "[Firewall] Skipped (-NoFirewall/FL_NO_FIREWALL=1)." -ForegroundColor DarkGray
        return
    }
    $setup = Join-Path $Here "setup-firewall.ps1"
    if (-not (Test-Path -LiteralPath $setup -PathType Leaf)) {
        Write-Host "[Firewall] setup-firewall.ps1 not found; skipping network access setup." -ForegroundColor Yellow
        return
    }
    try {
        . $setup
        $status = Get-FantasyLifeFirewallStatus -InstallDir $InstallPath
        if ($status.Ready) {
            Write-Host "[Firewall] Multiplayer rules are already present." -ForegroundColor DarkGray
            return
        }
        if (-not (Test-FantasyLifeInteractiveConsole)) {
            Write-Host "[Firewall] Non-interactive session; skipped. Run play.bat -SetupFirewall in $InstallPath if multiplayer is blocked." -ForegroundColor Yellow
            return
        }
        Write-Host "[Firewall] Adding missing multiplayer rules (one UAC prompt)..." -ForegroundColor Yellow
        if (Invoke-FantasyLifeFirewallSetupElevated -InstallDir $InstallPath) {
            Remove-Item -LiteralPath (Join-Path $InstallPath "data\yw2-recomp\firewall-declined") -Force -ErrorAction SilentlyContinue
            Write-Host "[Firewall] Multiplayer rules are ready." -ForegroundColor Green
        }
    } catch {
        Write-Host "[Firewall] Skipped ($($_.Exception.Message)). Run play.bat -SetupFirewall to retry." -ForegroundColor Yellow
    }
}

# Build a portable test package for another PC. It deliberately contains only
# runtime files, mods, shaders, launchers and the installer: never game dumps,
# saves, logs, settings.ini or console_id.
function Export-TestPackage {
    param(
        [Parameter(Mandatory = $true)][string]$SourceDir,
        [Parameter(Mandatory = $true)][string]$ZipPath
    )
    $SourceFull = [System.IO.Path]::GetFullPath($SourceDir).TrimEnd("\")
    $SourceExe = Join-Path $SourceFull "bin\fl_eur.exe"
    if (-not (Test-Path -LiteralPath $SourceExe -PathType Leaf)) {
        throw "Cannot export: $SourceExe is missing."
    }
    $zipFull = [System.IO.Path]::GetFullPath($ZipPath)
    $zipParent = Split-Path -Parent $zipFull
    if ($zipParent -and -not (Test-Path -LiteralPath $zipParent)) {
        New-Item -ItemType Directory -Path $zipParent -Force | Out-Null
    }

    $stage = Join-Path ([System.IO.Path]::GetTempPath()) ("fl-test-export-" + [guid]::NewGuid().ToString("N"))
    $stageBin = Join-Path $stage "bin"
    $stageData = Join-Path $stage "data\yw2-recomp"
    $stageMods = Join-Path $stageData "mods\fantasylife"
    $stageShader = Join-Path $stageData "shader-cache-v3"
    foreach ($d in @($stageBin, $stageMods, $stageShader)) {
        New-Item -ItemType Directory -Path $d -Force | Out-Null
    }

    try {
        # bin/: exe, runtime DLLs, relay and icons
        $srcBin = Join-Path $SourceFull "bin"
        foreach ($f in @(Get-ChildItem -LiteralPath $srcBin -File -ErrorAction SilentlyContinue)) {
            Copy-Item -LiteralPath $f.FullName -Destination (Join-Path $stageBin $f.Name) -Force
        }
        # bin\launcher\ (launcher window, icon tools)
        foreach ($d in @(Get-ChildItem -LiteralPath $srcBin -Directory -ErrorAction SilentlyContinue)) {
            Copy-Item -LiteralPath $d.FullName -Destination (Join-Path $stageBin $d.Name) -Recurse -Force
        }

        # Root launchers, channel marker, manifest and installer. The installer and
        # README always come from this script's folder when available, so an
        # export-only run still ships the current installer.
        foreach ($name in @("play.ps1", "play.bat", "play.sh", "setup-firewall.ps1", "channel.env", "test-version.json", "README.txt", "install-test.ps1", "Install-Test.bat")) {
            if ($name -in @("README.txt", "install-test.ps1", "Install-Test.bat", "setup-firewall.ps1")) {
                $src = Join-Path $Here $name
                if (-not (Test-Path -LiteralPath $src -PathType Leaf)) { $src = Join-Path $SourceFull $name }
            } else {
                $src = Join-Path $SourceFull $name
                if (-not (Test-Path -LiteralPath $src -PathType Leaf)) { $src = Join-Path $Here $name }
            }
            if (Test-Path -LiteralPath $src -PathType Leaf) {
                Copy-Item -LiteralPath $src -Destination (Join-Path $stage $name) -Force
            } elseif ($name -in @("install-test.ps1", "Install-Test.bat", "play.ps1", "play.bat", "test-version.json", "setup-firewall.ps1")) {
                throw "Cannot export: required file '$name' was not found in $SourceFull or $Here."
            }
        }
        $channelText = "# Local test install marker written by publish-test.ps1`r`nFL_CHANNEL=test`r`n"
        Set-Content -Path (Join-Path $stage "channel.env") -Value $channelText -Encoding ASCII

        # Shared default settings (never settings.ini or console_id)
        $defaultIni = Join-Path $SourceFull "data\yw2-recomp\settings.default.ini"
        if (Test-Path -LiteralPath $defaultIni -PathType Leaf) {
            Copy-Item -LiteralPath $defaultIni -Destination (Join-Path $stageData "settings.default.ini") -Force
        } else {
            Write-Host "[Export]   WARNING: settings.default.ini not found in $SourceFull." -ForegroundColor Yellow
        }

        # Mod overlays
        $srcMods = Join-Path $SourceFull "data\yw2-recomp\mods\fantasylife"
        if (Test-Path -LiteralPath $srcMods) {
            foreach ($entry in @(Get-ChildItem -LiteralPath $srcMods -Force -ErrorAction SilentlyContinue)) {
                Copy-Item -LiteralPath $entry.FullName -Destination (Join-Path $stageMods $entry.Name) -Recurse -Force
            }
        }

        # Shader cache without logs or temp files
        $srcShader = Join-Path $SourceFull "data\yw2-recomp\shader-cache-v3"
        if (Test-Path -LiteralPath $srcShader) {
            $shaderFiles = @(Get-ChildItem -LiteralPath $srcShader -Recurse -File -ErrorAction SilentlyContinue | Where-Object {
                $_.Extension -notin @(".log", ".tmp") -and $_.Name -notlike "*.tmp*"
            })
            foreach ($f in $shaderFiles) {
                $relative = $f.FullName.Substring($srcShader.Length).TrimStart("\")
                $dst = Join-Path $stageShader $relative
                $dstParent = Split-Path -Parent $dst
                if ($dstParent) { New-Item -ItemType Directory -Path $dstParent -Force | Out-Null }
                Copy-Item -LiteralPath $f.FullName -Destination $dst -Force
            }
        }

        if (Test-Path -LiteralPath $zipFull) { Remove-Item -LiteralPath $zipFull -Force }
        Add-Type -AssemblyName System.IO.Compression
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        # PowerShell 5.1's ZipFile/Compress-Archive write backslash entry names,
        # which is non-standard. Write forward-slash names explicitly.
        $zipStream = [System.IO.File]::Open($zipFull, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write)
        try {
            $archive = New-Object System.IO.Compression.ZipArchive($zipStream, ([System.IO.Compression.ZipArchiveMode]::Create), $true)
            try {
                $stagePrefix = $stage.TrimEnd("\") + "\"
                foreach ($f in @(Get-ChildItem -LiteralPath $stage -Recurse -File -ErrorAction SilentlyContinue)) {
                    $entryName = $f.FullName.Substring($stagePrefix.Length).Replace("\", "/")
                    $entry = $archive.CreateEntry($entryName, [System.IO.Compression.CompressionLevel]::Optimal)
                    $inStream = [System.IO.File]::OpenRead($f.FullName)
                    try {
                        $outStream = $entry.Open()
                        try { $inStream.CopyTo($outStream) } finally { $outStream.Dispose() }
                    } finally {
                        $inStream.Dispose()
                    }
                }
            } finally {
                $archive.Dispose()
            }
        } finally {
            $zipStream.Dispose()
        }
        if (-not (Test-Path -LiteralPath $zipFull -PathType Leaf)) {
            throw "ZIP was not created: $zipFull"
        }

        $staged = @(Get-ChildItem -LiteralPath $stage -Recurse -File -ErrorAction SilentlyContinue)
        $stagedBytes = ($staged | Measure-Object -Property Length -Sum).Sum
        if (-not $stagedBytes) { $stagedBytes = 0 }
        $zipBytes = (Get-Item -LiteralPath $zipFull).Length
        Write-Host ("[Export]   Wrote {0}" -f $zipFull) -ForegroundColor Green
        Write-Host ("[Export]   {0} file(s), {1:N1} MB staged -> {2:N1} MB ZIP" -f $staged.Count, ($stagedBytes / 1MB), ($zipBytes / 1MB)) -ForegroundColor Green
        Write-Host "[Export]   Excludes game/, saves/, logs/, settings.ini and console_id." -ForegroundColor DarkGray
    } finally {
        if (Test-Path -LiteralPath $stage) {
            Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

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

# `-ExportZip` alone exports the current test install without touching it. Any
# parameter that installs a build also produces the ZIP after updating.
$UpdateRequested = [bool]($Exe -or $Relay -or ($ModDirs.Count -gt 0) -or $Label -or $CopySavesFromStable)
$ExportOnly = [bool]($ExportZip -and -not $UpdateRequested)

if (-not $ExportOnly -and -not (Test-Path -LiteralPath $StableFull)) {
    throw "Stable install not found: $StableFull"
}

if ($ExportOnly) {
    if (-not (Test-Path -LiteralPath (Join-Path $TargetFull "bin\fl_eur.exe") -PathType Leaf)) {
        throw "No test install to export at $TargetFull (missing bin\fl_eur.exe). Run with -Exe first."
    }
    Write-Host "==============================================================" -ForegroundColor Yellow
    Write-Host " Fantasy Life PC - export the current TEST install" -ForegroundColor Yellow
    Write-Host " From: $TargetFull" -ForegroundColor Gray
    Write-Host " To:   $([System.IO.Path]::GetFullPath($ExportZip))" -ForegroundColor Gray
    Write-Host "==============================================================" -ForegroundColor Yellow
    Set-TestFirewallIfMissing -InstallPath $TargetFull
    Export-TestPackage -SourceDir $TargetFull -ZipPath $ExportZip
    exit 0
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

Write-Host "==============================================================" -ForegroundColor Yellow
Write-Host " Fantasy Life PC - publish to local TEST install" -ForegroundColor Yellow
Write-Host " Stable (read only): $StableFull" -ForegroundColor Gray
Write-Host " Test target:        $TargetFull" -ForegroundColor Gray
Write-Host " Label:              $Label" -ForegroundColor Gray
if ($ExportZip) {
    Write-Host " Export ZIP:         $([System.IO.Path]::GetFullPath($ExportZip))" -ForegroundColor Gray
}
Write-Host "==============================================================" -ForegroundColor Yellow

# 1. Launcher scripts and the portable installer (same play.ps1, channel-aware;
#    no git repo, no updater)
foreach ($name in @("play.ps1", "play.bat", "play.sh", "setup-firewall.ps1", "README.txt", "install-test.ps1", "Install-Test.bat")) {
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

# Neutral fallback icon and the launcher window (bin\launcher\) from this package.
# The real game icon is generated from the dump into data\yw2-recomp\icon.ico.
foreach ($name in @("fantasy-life.ico", "fantasy-life.png")) {
    foreach ($icon in @((Join-Path $Here "bin\$name"), (Join-Path $StableBin $name))) {
        if (Test-Path -LiteralPath $icon) {
            Copy-FileSafe $icon (Join-Path $BinDir $name) | Out-Null
            break
        }
    }
}
$SrcLauncher = Join-Path $Here "bin\launcher"
$DstLauncher = Join-Path $BinDir "launcher"
if (Test-Path -LiteralPath $SrcLauncher -PathType Container) {
    if (Test-Path -LiteralPath $DstLauncher) { Remove-Item -LiteralPath $DstLauncher -Recurse -Force }
    Copy-Item -LiteralPath $SrcLauncher -Destination $DstLauncher -Recurse -Force
    Write-Host "[Launcher] Copied the launcher window (bin\launcher)" -ForegroundColor Green
}

# 3. Mod overlays (only these are enabled by play.ps1 in the test channel)
$StableModRoot = Join-Path $StableFull "data\yw2-recomp\mods\fantasylife"
$ModSources = @()
if ($ModDirs.Count -gt 0) {
    foreach ($dir in $ModDirs) {
        if (-not (Test-Path -LiteralPath $dir -PathType Container)) { throw "-ModDirs entry not found: $dir" }
        $ModSources += (Resolve-Path -LiteralPath $dir).Path
    }
} else {
    # Baseline tests follow the installed stable manifest, including future
    # contributor mods. An explicit [] stays empty; old packages use folders.
    $DefaultModNames = @()
    $HaveStableModList = $false
    $StableVersion = Join-Path $StableFull "version.json"
    if (Test-Path -LiteralPath $StableVersion) {
        $stableManifest = Get-Content -LiteralPath $StableVersion -Raw | ConvertFrom-Json
        if ($stableManifest.PSObject.Properties.Name -contains "mods") {
            if ($null -eq $stableManifest.mods -or $stableManifest.mods -isnot [System.Array]) { throw "Stable version.json mods must be an array." }
            $DefaultModNames = @($stableManifest.mods)
            $HaveStableModList = $true
        }
    }
    if (-not $HaveStableModList) {
        $DefaultModNames = @(Get-ChildItem -LiteralPath $StableModRoot -Directory -ErrorAction SilentlyContinue |
            Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName "overlay.json") } |
            Sort-Object Name | ForEach-Object { $_.Name })
    }
    if (@($DefaultModNames | Select-Object -Unique).Count -ne $DefaultModNames.Count) { throw "Duplicate stable mod name." }
    foreach ($name in $DefaultModNames) {
        if ($name -isnot [string] -or $name -notmatch '^[a-zA-Z0-9][a-zA-Z0-9._-]*$') { throw "Invalid stable mod name." }
        $candidate = Join-Path $StableModRoot $name
        if (-not (Test-Path -LiteralPath (Join-Path $candidate "overlay.json"))) { throw "Stable mod '$name' is missing; update the normal game first." }
        $ModSources += $candidate
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
    # The shortcut opens the launcher window; its icon comes from the game dump
    # (generated locally, never shipped) with the neutral icon as fallback.
    $IconTool = Join-Path $BinDir "launcher\icon.ps1"
    $IconPath = Join-Path $BinDir "fantasy-life.ico"
    $TestRom = Join-Path $GameDir "FantasyLife_EU.3ds"
    $HaveIconTool = Test-Path -LiteralPath $IconTool
    if ($HaveIconTool) {
        . $IconTool
        try { $IconPath = Get-FantasyLifeIconPath -InstallDir $TargetFull -RomPath $(if (Test-Path -LiteralPath $TestRom) { $TestRom } else { "" }) } catch {}
    }
    $DesktopDir  = [Environment]::GetFolderPath("Desktop")
    $ProgramsDir = [Environment]::GetFolderPath("Programs")
    foreach ($dir in @($DesktopDir, $ProgramsDir)) {
        if ($dir -and (Test-Path -LiteralPath $dir)) {
            $lnkPath = Join-Path $dir "Fantasy Life (Test).lnk"
            if ($HaveIconTool) {
                Set-FantasyLifeShortcut -Path $lnkPath -InstallDir $TargetFull -IconPath $IconPath -Description "Fantasy Life PC - TEST build (local only, no auto-update)"
            } else {
                $sc = (New-Object -ComObject WScript.Shell).CreateShortcut($lnkPath)
                $sc.TargetPath       = Join-Path $TargetFull "play.bat"
                $sc.WorkingDirectory = $TargetFull
                $sc.IconLocation     = $IconPath + ",0"
                $sc.Description      = "Fantasy Life PC - TEST build (local only, no auto-update)"
                $sc.Save()
            }
            Write-Host "[Shortcut] $lnkPath (icon: $IconPath)" -ForegroundColor Green
        }
    }
    $ie4 = Join-Path $env:SystemRoot "System32\ie4uinit.exe"
    if (Test-Path -LiteralPath $ie4) { try { Start-Process -FilePath $ie4 -ArgumentList "-show" -WindowStyle Hidden } catch {} }
}

# 9. Windows Firewall for the test install, only when a rule is missing. This
#    never prompts in a non-interactive/export session.
Set-TestFirewallIfMissing -InstallPath $TargetFull

# 10. Optional portable package for another PC (built from the finished install)
if ($ExportZip) {
    Export-TestPackage -SourceDir $TargetFull -ZipPath $ExportZip
}

Write-Host ""
Write-Host "Test install ready: $TargetFull" -ForegroundColor Green
Write-Host "  Shortcut:         Fantasy Life (Test)" -ForegroundColor Green
Write-Host "  Auto-update:      Off (local test channel)" -ForegroundColor Green
Write-Host "  Test saves:       $SavesDir" -ForegroundColor Green
Write-Host "  Manifest:         $VersionFile" -ForegroundColor Green
if ($ExportZip) {
    Write-Host "  Portable ZIP:     $([System.IO.Path]::GetFullPath($ExportZip))" -ForegroundColor Green
}
