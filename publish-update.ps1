param(
    [switch]$RebuildMods,
    [switch]$IncludeDumps,
    [switch]$CopySaves,
    [switch]$Commit,
    [switch]$Push,
    [string]$Message = "",
    [string]$UsbDrive = ""
)

$ErrorActionPreference = "Stop"
$UsbRoot  = Split-Path -Parent $MyInvocation.MyCommand.Path
$WorkRoot = Split-Path -Parent $UsbRoot
$MainRepo = Join-Path $WorkRoot "fl-project-blue"
$LinuxPkg = Join-Path $WorkRoot "FantasyLife-Linux"
$WinPkg   = Join-Path $WorkRoot "FantasyLife-Windows"

Write-Host "=== Publishing to FantasyLife-USB ($UsbRoot) ===" -ForegroundColor Cyan

# 1. Ensure directory layout
$BinDir    = Join-Path $UsbRoot "bin"
$LibDir    = Join-Path $UsbRoot "lib"
$ModsDir   = Join-Path $UsbRoot "data\yw2-recomp\mods\fantasylife"
$ShaderDir = Join-Path $UsbRoot "data\yw2-recomp\shader-cache-v3"
$GameDir   = Join-Path $UsbRoot "game"
$SavesDir  = Join-Path $UsbRoot "saves"

foreach ($d in @($BinDir, $LibDir, $ModsDir, $ShaderDir, $GameDir, $SavesDir)) {
    New-Item -ItemType Directory -Path $d -Force | Out-Null
}

# 2. Sync Linux binary and shared libraries
if (Test-Path (Join-Path $LinuxPkg "bin\fl_eur")) {
    Copy-Item -Path (Join-Path $LinuxPkg "bin\fl_eur") -Destination (Join-Path $BinDir "fl_eur") -Force
    Write-Host "[Linux]   Synced bin/fl_eur" -ForegroundColor Green
}
if (Test-Path (Join-Path $LinuxPkg "lib")) {
    Copy-Item -Path (Join-Path $LinuxPkg "lib\*") -Destination $LibDir -Recurse -Force
    Write-Host "[Linux]   Synced lib/*.so" -ForegroundColor Green
}

# 3. Sync Windows binary & DLLs (if built yet)
$WinBinCandidates = @(
    (Join-Path $WinPkg "bin"),
    (Join-Path $MainRepo "port-wt\windows-port\build\windows-native"),
    (Join-Path $MainRepo "port\build\windows-native"),
    (Join-Path $MainRepo "port\build\native")
)
$FoundWinExe = $false
foreach ($cand in $WinBinCandidates) {
    $exe = Join-Path $cand "fl_eur.exe"
    if (Test-Path $exe) {
        Copy-Item -Path $exe -Destination (Join-Path $BinDir "fl_eur.exe") -Force
        Get-ChildItem -Path $cand -Filter "*.dll" -ErrorAction SilentlyContinue | ForEach-Object {
            Copy-Item -Path $_.FullName -Destination (Join-Path $BinDir $_.Name) -Force
        }
        $relay = Join-Path $cand "clockwork-relay.exe"
        if (Test-Path $relay) {
            Copy-Item -Path $relay -Destination (Join-Path $BinDir "clockwork-relay.exe") -Force
        }
        Write-Host "[Windows] Synced fl_eur.exe and runtime DLLs from $cand" -ForegroundColor Green
        $FoundWinExe = $true
        break
    }
}
if (-not $FoundWinExe) {
    Write-Host "[Windows] fl_eur.exe not built yet (re-run publish-update.ps1 once windows-port finishes)." -ForegroundColor Yellow
}

# 3b. Strip debug symbols from fl_eur and fl_eur.exe so binaries stay <35 MB for GitHub
$clangCmd = Get-Command clang++ -ErrorAction SilentlyContinue
if ($clangCmd) {
    $llvmStrip = Join-Path (Split-Path -Parent $clangCmd.Source) "llvm-strip.exe"
    if (Test-Path $llvmStrip) {
        foreach ($binFile in @((Join-Path $BinDir "fl_eur"), (Join-Path $BinDir "fl_eur.exe"))) {
            if (Test-Path $binFile) {
                & $llvmStrip --strip-debug $binFile
            }
        }
        Write-Host "[Strip]   Stripped debug symbols from bin/fl_eur and bin/fl_eur.exe" -ForegroundColor Green
    }
}

# 4. Sync or Rebuild Mod Overlays
$ModNames = @("story-skip", "eastern-plains-enemy", "castele-house", "wooden-sword")
$ArchiveDir = Join-Path $MainRepo "extracted\fl_eu\archive"
if ($RebuildMods -and (Test-Path $ArchiveDir)) {
    Write-Host "[Mods]    Rebuilding mod overlays from $MainRepo\mods..." -ForegroundColor Cyan
    foreach ($mod in $ModNames) {
        $outMod = Join-Path $ModsDir $mod
        if (Test-Path $outMod) { Remove-Item -Recurse -Force $outMod }
        if ($mod -eq "story-skip") {
            & python -I (Join-Path $MainRepo "tools\fl_story_skip.py") build $ArchiveDir $outMod
        } else {
            $spec = Join-Path $MainRepo "mods\$mod\mod.json"
            & python -I (Join-Path $MainRepo "tools\fl_mod.py") build $spec $ArchiveDir $outMod
        }
        if ($LASTEXITCODE -ne 0) { throw "Failed to build mod $mod" }
    }
    Write-Host "[Mods]    Rebuilt all 4 mod overlays." -ForegroundColor Green
} else {
    foreach ($srcModRoot in @(
        (Join-Path $WinPkg "data\yw2-recomp\mods\fantasylife"),
        (Join-Path $LinuxPkg "data\yw2-recomp\mods\fantasylife")
    )) {
        if (Test-Path $srcModRoot) {
            Copy-Item -Path "$srcModRoot\*" -Destination $ModsDir -Recurse -Force
            Write-Host "[Mods]    Synced built mod overlays from $srcModRoot" -ForegroundColor Green
            break
        }
    }
}

# 5. Sync precompiled Shader Cache (.cpp, .so, .dll; skip .log and .tmp)
foreach ($srcShader in @(
    (Join-Path $LinuxPkg "data\yw2-recomp\shader-cache-v3"),
    (Join-Path $WinPkg "data\yw2-recomp\shader-cache-v3"),
    (Join-Path $MainRepo "port\build\fl-data\yw2-recomp\shader-cache-v3")
)) {
    if (Test-Path $srcShader) {
        Get-ChildItem -Path $srcShader -File -ErrorAction SilentlyContinue | Where-Object {
            $_.Extension -in @(".cpp", ".so", ".dll")
        } | ForEach-Object {
            Copy-Item -Path $_.FullName -Destination (Join-Path $ShaderDir $_.Name) -Force
        }
    }
}
Write-Host "[Shaders] Synced shader-cache-v3 (.cpp/.so/.dll)" -ForegroundColor Green

# 6. Optional: copy game dumps & starter saves for USB stick seeding (gitignored)
if ($IncludeDumps) {
    $romSrc = @(
        (Join-Path $WorkRoot "Game_Dumps\0004000000113100_v00.trim.3ds"),
        (Join-Path $LinuxPkg "game\FantasyLife_EU.3ds"),
        (Join-Path $MainRepo "dumps\0004000000113100_v00.trim.3ds")
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($romSrc) {
        Copy-Item -Path $romSrc -Destination (Join-Path $GameDir "FantasyLife_EU.3ds") -Force
        Write-Host "[USB]     Copied FantasyLife_EU.3ds into game/ (gitignored)" -ForegroundColor Green
    }
    $dlcSrc = @(
        (Join-Path $LinuxPkg "game\OriginIsland_DLC.cia"),
        (Join-Path $MainRepo "dumps\OriginIsland_DLC.cia")
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $dlcSrc) {
        $dlcSrc = Get-ChildItem -Path (Join-Path $WorkRoot "Game_Dumps") -Filter "*.cia" -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
    }
    if ($dlcSrc) {
        Copy-Item -Path $dlcSrc -Destination (Join-Path $GameDir "OriginIsland_DLC.cia") -Force
        Write-Host "[USB]     Copied OriginIsland_DLC.cia into game/ (gitignored)" -ForegroundColor Green
    }
}

if ($CopySaves -and (Test-Path (Join-Path $LinuxPkg "saves"))) {
    Copy-Item -Path (Join-Path $LinuxPkg "saves\*") -Destination $SavesDir -Recurse -Force
    Write-Host "[USB]     Copied starter saves into saves/ (gitignored)" -ForegroundColor Green
}

# 7. Generate deterministic version.json & mod compatibility digest
$mainRev = "unknown"
$portRev = "unknown"
if (Test-Path (Join-Path $MainRepo ".git")) {
    $mainRev = (& git -C $MainRepo rev-parse --short HEAD 2>$null)
}
if (Test-Path (Join-Path $MainRepo "port\.git")) {
    $portRev = (& git -C (Join-Path $MainRepo "port") rev-parse --short HEAD 2>$null)
}

$hasher = [System.Security.Cryptography.SHA256]::Create()
$digestInput = New-Object System.Text.StringBuilder
$activeMods = @()
foreach ($mod in $ModNames) {
    $ov = Join-Path $ModsDir "$mod\overlay.json"
    if (Test-Path $ov) {
        $activeMods += $mod
        $fileHash = (Get-FileHash -Path $ov -Algorithm SHA256).Hash.ToLower()
        [void]$digestInput.Append("$mod=$fileHash;")
    }
}
$digestBytes = [System.Text.Encoding]::UTF8.GetBytes($digestInput.ToString())
$modDigest = ([System.BitConverter]::ToString($hasher.ComputeHash($digestBytes)).Replace("-", "").ToLower()).Substring(0, 12)

$versionObj = [ordered]@{
    version         = "fl-$mainRev-port-$portRev"
    updated_at      = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    mod_digest      = $modDigest
    mods            = $activeMods
    has_windows_bin = (Test-Path (Join-Path $BinDir "fl_eur.exe"))
    has_linux_bin   = (Test-Path (Join-Path $BinDir "fl_eur"))
}
$versionJson = $versionObj | ConvertTo-Json -Depth 4
Set-Content -Path (Join-Path $UsbRoot "version.json") -Value $versionJson -Encoding UTF8
Write-Host "[Version] Wrote version.json (Build: $($versionObj.version), Mod Digest: $modDigest)" -ForegroundColor Cyan

# 8. Initialize / Commit / Push Git update repo if requested
if (-not (Test-Path (Join-Path $UsbRoot ".git"))) {
    & git -C $UsbRoot init -b main | Out-Null
    & git -C $UsbRoot config core.autocrlf false
    & git -C $UsbRoot config core.fileMode false
    Write-Host "[Git]     Initialized Git repository in $UsbRoot" -ForegroundColor Green
}

if ($Commit -or $Push) {
    & git -C $UsbRoot add .gitignore update-config.env play.ps1 play.bat play.sh publish-update.ps1 install-windows.ps1 Install-Windows.bat install-linux.sh README.txt version.json data/yw2-recomp/settings.default.ini data/yw2-recomp/mods data/yw2-recomp/shader-cache-v3 bin lib
    $status = (& git -C $UsbRoot status --porcelain)
    if ($status) {
        if (-not $Message) {
            $Message = "Update build $($versionObj.version) (mods: $modDigest)"
        }
        & git -C $UsbRoot commit -m "$Message`n`nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
        Write-Host "[Git]     Committed update: $Message" -ForegroundColor Green
    } else {
        Write-Host "[Git]     Nothing new to commit." -ForegroundColor DarkGray
    }
    if ($Push) {
        $remotes = (& git -C $UsbRoot remote)
        if ($remotes -contains "origin") {
            & git -C $UsbRoot push -u origin main
            Write-Host "[Git]     Pushed to origin/main." -ForegroundColor Green
        } else {
            Write-Host "[Git]     No 'origin' remote configured yet. Add one with: git -C `"$UsbRoot`" remote add origin <URL>" -ForegroundColor Yellow
        }
    }
}

if ($UsbDrive) {
    if (-not (Test-Path $UsbDrive)) {
        throw "USB drive $UsbDrive not found!"
    }
    $UsbTarget = Join-Path $UsbDrive "FantasyLife-PC"
    Write-Host "[USB]     Syncing standalone package to $UsbTarget..." -ForegroundColor Cyan
    New-Item -ItemType Directory -Path $UsbTarget -Force | Out-Null
    $roboArgs = @(
        $UsbRoot,
        $UsbTarget,
        "/MIR",
        "/R:2",
        "/W:1",
        "/NP",
        "/NFL",
        "/NDL",
        "/XD", "saves", "logs", ".update-tmp", ".freebuff",
        "/XF", "console_id", "settings.ini", "instance-*.lock"
    )
    & robocopy @roboArgs | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "Robocopy to $UsbTarget failed with code $LASTEXITCODE" }
    Write-Host "[USB]     Synced $UsbTarget successfully!" -ForegroundColor Green
}
