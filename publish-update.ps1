param(
    [switch]$RebuildMods,
    [switch]$IncludeDumps,
    [switch]$CopySaves,
    [switch]$Commit,
    [switch]$Push,
    [switch]$FromTest,
    [string]$TestDir = (Join-Path $env:LOCALAPPDATA "FantasyLife-PC-Test"),
    [string]$Message = "",
    [string]$UsbDrive = ""
)

$ErrorActionPreference = "Stop"
$UsbRoot  = Split-Path -Parent $MyInvocation.MyCommand.Path
$WorkRoot = Split-Path -Parent $UsbRoot
$MainRepo = Join-Path $WorkRoot "fl-project-blue"
$LinuxPkg = Join-Path $WorkRoot "FantasyLife-Linux"
$WinPkg   = Join-Path $WorkRoot "FantasyLife-Windows"

# A test label such as "mp-local 85b09eb (multiplayer fix)" becomes a stable
# version string, so keep only characters that are safe in version.json.
function Get-VersionSlug {
    param([string]$Text)
    if (-not $Text) { return "" }
    $slug = $Text.ToLowerInvariant()
    $slug = [regex]::Replace($slug, "[^a-z0-9._-]+", "-")
    $slug = [regex]::Replace($slug, "-{2,}", "-")
    $slug = $slug.Trim("-", ".", "_")
    if ($slug.Length -gt 64) { $slug = $slug.Substring(0, 64).Trim("-", ".", "_") }
    return $slug
}

# llvm-strip does not always land on PATH. Prefer the LLVM-MinGW next to clang++,
# then PATH, then the WinGet package tree used by this machine.
function Find-LlvmStrip {
    $candidates = New-Object System.Collections.Generic.List[string]
    if ($env:LLVM_STRIP) { $candidates.Add($env:LLVM_STRIP) }
    $clangCmd = Get-Command clang++ -ErrorAction SilentlyContinue
    if ($clangCmd -and $clangCmd.Source) {
        $clangDir = Split-Path -Parent $clangCmd.Source
        $candidates.Add((Join-Path $clangDir "llvm-strip.exe"))
        $candidates.Add((Join-Path $clangDir "llvm-strip"))
    }
    $stripCmd = Get-Command llvm-strip -ErrorAction SilentlyContinue
    if ($stripCmd -and $stripCmd.Source) { $candidates.Add($stripCmd.Source) }
    $wingetRoot = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages"
    if (Test-Path -LiteralPath $wingetRoot) {
        foreach ($pkg in @(Get-ChildItem -LiteralPath $wingetRoot -Directory -Filter "*LLVM*" -ErrorAction SilentlyContinue)) {
            $found = @(Get-ChildItem -LiteralPath $pkg.FullName -Recurse -Filter "llvm-strip.exe" -File -ErrorAction SilentlyContinue | Select-Object -First 4)
            foreach ($f in $found) { $candidates.Add($f.FullName) }
        }
    }
    $candidates.Add("C:\Program Files\LLVM\bin\llvm-strip.exe")
    $candidates.Add("C:\Program Files (x86)\LLVM\bin\llvm-strip.exe")
    foreach ($cand in $candidates) {
        if ($cand -and (Test-Path -LiteralPath $cand -PathType Leaf)) {
            return (Resolve-Path -LiteralPath $cand).Path
        }
    }
    return $null
}

# -FromTest ships the exact install the user tested, so read and validate its
# manifest before touching the package.
$TestFull = $null
$TestManifest = $null
$TestExeSource = $null
$TestModNames = @()
$TestExePreHash = $null
if ($FromTest) {
    if ($RebuildMods) {
        Write-Host "[Mods]    -RebuildMods is ignored with -FromTest (shipping the test install's mods exactly)." -ForegroundColor Yellow
    }
    $TestFull = [System.IO.Path]::GetFullPath($TestDir).TrimEnd("\")
    if (-not (Test-Path -LiteralPath $TestFull -PathType Container)) {
        throw "-FromTest: test install not found: $TestFull"
    }
    $TestManifestPath = Join-Path $TestFull "test-version.json"
    if (-not (Test-Path -LiteralPath $TestManifestPath -PathType Leaf)) {
        throw "-FromTest: missing $TestManifestPath. Run publish-test.ps1 first."
    }
    try {
        $TestManifest = Get-Content -LiteralPath $TestManifestPath -Raw | ConvertFrom-Json
    } catch {
        throw "-FromTest: cannot parse $TestManifestPath ($($_.Exception.Message))"
    }
    $TestExeSource = Join-Path $TestFull "bin\fl_eur.exe"
    if (-not (Test-Path -LiteralPath $TestExeSource -PathType Leaf)) {
        throw "-FromTest: missing $TestExeSource"
    }
    if ($TestManifest.mods) {
        $TestModNames = @($TestManifest.mods | Where-Object { $_ })
    }
    if ($TestModNames.Count -eq 0) {
        Write-Host "[Mods]    test-version.json lists no mods; publishing without mod overlays." -ForegroundColor Yellow
    }
    $TestExePreHash = (Get-FileHash -LiteralPath $TestExeSource -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($TestManifest.exe_sha256 -and $TestExePreHash -ne ([string]$TestManifest.exe_sha256).ToLowerInvariant()) {
        Write-Host "[Source]  WARNING: test install's fl_eur.exe no longer matches test-version.json." -ForegroundColor Yellow
        Write-Host "          The test build changed since publish-test.ps1 wrote the manifest; re-run publish-test.ps1 to refresh it." -ForegroundColor Yellow
    }
    Write-Host "[Source]  Publishing the tested install at $TestFull" -ForegroundColor Cyan
}

# Publishing to the brothers' stable install must always be a deliberate,
# human-confirmed action. Refuse immediately when there is no interactive
# console (redirected stdin, -NonInteractive, service/agent session).
function Test-InteractivePublishSession {
    try {
        if ([Console]::IsInputRedirected) { return $false }
        if (-not [Environment]::UserInteractive) { return $false }
        $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId=$PID" -ErrorAction Stop).CommandLine
        if ($cmdLine -and ($cmdLine -match '(?i)(^|\s)-noninteractive(\s|$)')) { return $false }
        return $true
    } catch {
        return $false
    }
}

if ($Push) {
    if (-not (Test-InteractivePublishSession)) {
        Write-Host "ERROR: -Push requires an interactive session; stdin is redirected or PowerShell is non-interactive." -ForegroundColor Red
        Write-Host "Refusing to publish to the stable origin. Run this from an interactive PowerShell window." -ForegroundColor Red
        exit 1
    }
    $branch = (& git -C $UsbRoot rev-parse --abbrev-ref HEAD 2>$null)
    if ((Test-Path (Join-Path $UsbRoot ".git")) -and (($branch | Out-String).Trim() -ne "main")) {
        Write-Host "ERROR: -Push commits and pushes 'main', but the repository is on '$branch'. Switch to main first." -ForegroundColor Red
        exit 1
    }
}

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

# 3. Sync Windows binary & DLLs. With -FromTest this is the exact exe the user
#    tested; otherwise use the first built candidate as before.
$WinBinCandidates = @(
    (Join-Path $WinPkg "bin"),
    (Join-Path $MainRepo "port-wt\windows-port\build\windows-native"),
    (Join-Path $MainRepo "port\build\windows-native"),
    (Join-Path $MainRepo "port\build\native")
)
$FoundWinExe = $false
$ExeSource = $null
if ($FromTest) {
    $ExeSource = $TestExeSource
    $TestBin = Join-Path $TestFull "bin"
    Copy-Item -LiteralPath $ExeSource -Destination (Join-Path $BinDir "fl_eur.exe") -Force
    Get-ChildItem -LiteralPath $TestBin -Filter "*.dll" -File -ErrorAction SilentlyContinue | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $BinDir $_.Name) -Force
    }
    $testRelay = Join-Path $TestBin "clockwork-relay.exe"
    if (Test-Path -LiteralPath $testRelay -PathType Leaf) {
        Copy-Item -LiteralPath $testRelay -Destination (Join-Path $BinDir "clockwork-relay.exe") -Force
    } else {
        Write-Host "[Windows] WARNING: test install has no clockwork-relay.exe; keeping the existing bin/clockwork-relay.exe." -ForegroundColor Yellow
    }
    Write-Host "[Windows] Synced fl_eur.exe, runtime DLLs and relay from $TestBin (tested install)" -ForegroundColor Green
    $FoundWinExe = $true
} else {
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
            $ExeSource = $exe
            $FoundWinExe = $true
            break
        }
    }
}
if (-not $FoundWinExe) {
    Write-Host "[Windows] fl_eur.exe not built yet (re-run publish-update.ps1 once windows-port finishes)." -ForegroundColor Yellow
    if (Test-Path -LiteralPath (Join-Path $BinDir "fl_eur.exe")) {
        $ExeSource = (Join-Path $BinDir "fl_eur.exe") + " (kept existing, no new build found)"
    }
}

# 3b. Strip debug symbols from fl_eur and fl_eur.exe so binaries stay <35 MB for GitHub
$WinExePath = Join-Path $BinDir "fl_eur.exe"
$LinuxBinPath = Join-Path $BinDir "fl_eur"
$WinExeStamp = $null
$LinuxStamp = $null
if (Test-Path -LiteralPath $WinExePath) {
    $WinExeStamp = (Get-Item -LiteralPath $WinExePath).LastWriteTimeUtc
}
if (Test-Path -LiteralPath $LinuxBinPath) {
    $LinuxStamp = (Get-Item -LiteralPath $LinuxBinPath).LastWriteTimeUtc
}
$llvmStrip = Find-LlvmStrip
if ($llvmStrip) {
    foreach ($binFile in @($LinuxBinPath, $WinExePath)) {
        if (Test-Path -LiteralPath $binFile) {
            # Keep the build timestamp: llvm-strip rewrites the file, and the
            # Linux-vs-Windows age check must not compare two strip times.
            $buildStamp = (Get-Item -LiteralPath $binFile).LastWriteTimeUtc
            & $llvmStrip --strip-debug $binFile
            if ($LASTEXITCODE -ne 0) {
                throw "llvm-strip failed (exit $LASTEXITCODE) for $binFile"
            }
            (Get-Item -LiteralPath $binFile).LastWriteTimeUtc = $buildStamp
        }
    }
    Write-Host "[Strip]   Stripped debug symbols from bin/fl_eur and bin/fl_eur.exe" -ForegroundColor Green
} else {
    Write-Host "[Strip]   WARNING: llvm-strip not found; debug symbols were not removed." -ForegroundColor Yellow
}

$PublishedExeSha256 = $null
if (Test-Path -LiteralPath $WinExePath) {
    $PublishedExeSha256 = (Get-FileHash -LiteralPath $WinExePath -Algorithm SHA256).Hash.ToLowerInvariant()
    Write-Host "[Windows] Exe source: $ExeSource" -ForegroundColor Cyan
    Write-Host "[Windows] Exe SHA-256: $PublishedExeSha256 (published copy, after strip)" -ForegroundColor Cyan
}
$PublishedRelaySha256 = $null
$PublishedRelayPath = Join-Path $BinDir "clockwork-relay.exe"
if (Test-Path -LiteralPath $PublishedRelayPath) {
    $PublishedRelaySha256 = (Get-FileHash -LiteralPath $PublishedRelayPath -Algorithm SHA256).Hash.ToLowerInvariant()
    Write-Host "[Windows] Relay SHA-256: $PublishedRelaySha256" -ForegroundColor DarkGray
}

# The Linux binary cannot be rebuilt on this PC. Say so when it is older than
# the Windows exe we are about to publish (timestamps are the only version marker
# available; compare before stripping changes the Windows timestamp).
if ($LinuxStamp -and $WinExeStamp) {
    if ($LinuxStamp -lt $WinExeStamp) {
        Write-Host ("[Linux]   WARNING: bin/fl_eur is older ({0:yyyy-MM-dd HH:mm:ss} UTC) than the Windows build ({1:yyyy-MM-dd HH:mm:ss} UTC)." -f $LinuxStamp, $WinExeStamp) -ForegroundColor Yellow
        Write-Host "[Linux]   The Linux binary cannot be rebuilt on this PC; it still ships as the previous build." -ForegroundColor Yellow
    }
}

# 4. Sync or Rebuild Mod Overlays
$ModNames = @("story-skip", "eastern-plains-enemy", "castele-house", "wooden-sword")
$ArchiveDir = Join-Path $MainRepo "extracted\fl_eu\archive"
if ($FromTest) {
    # Mirror exactly the overlays listed in test-version.json; drop stale ones.
    if (Test-Path -LiteralPath $ModsDir) {
        Get-ChildItem -LiteralPath $ModsDir -Force | Remove-Item -Recurse -Force
    } else {
        New-Item -ItemType Directory -Path $ModsDir -Force | Out-Null
    }
    $TestModsRoot = Join-Path $TestFull "data\yw2-recomp\mods\fantasylife"
    $TestedMods = @()
    foreach ($mod in $TestModNames) {
        if (($mod -match "[\\/]") -or ($mod -eq ".") -or ($mod -eq "..")) {
            throw "-FromTest: invalid mod name in test-version.json: $mod"
        }
        $srcMod = Join-Path $TestModsRoot $mod
        if (-not (Test-Path -LiteralPath $srcMod -PathType Container)) {
            throw "-FromTest: test-version.json lists mod '$mod', but $srcMod does not exist."
        }
        if (-not (Test-Path -LiteralPath (Join-Path $srcMod "overlay.json") -PathType Leaf)) {
            Write-Host "[Mods]    WARNING: mod '$mod' has no overlay.json; mod_digest will not cover it." -ForegroundColor Yellow
        }
        Copy-Item -LiteralPath $srcMod -Destination (Join-Path $ModsDir $mod) -Recurse -Force
        $TestedMods += $mod
    }
    $ModNames = @($TestedMods)
    if ($ModNames.Count -gt 0) {
        Write-Host ("[Mods]    Mirrored {0} tested mod overlay(s): {1}" -f $ModNames.Count, ($ModNames -join ", ")) -ForegroundColor Green
    } else {
        Write-Host "[Mods]    Test install has no mods; the package ships without mod overlays." -ForegroundColor Yellow
    }
} elseif ($RebuildMods -and (Test-Path $ArchiveDir)) {
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

if ($FromTest) {
    $testLabel = "test build"
    if ($TestManifest -and $TestManifest.label) { $testLabel = [string]$TestManifest.label }
    $versionName = Get-VersionSlug $testLabel
    if (-not $versionName) { $versionName = "test-build" }
} else {
    $versionName = "fl-$mainRev-port-$portRev"
}
if ($FromTest -and ($activeMods.Count -ne $ModNames.Count)) {
    Write-Host "[Version] WARNING: only $($activeMods.Count) of $($ModNames.Count) tested mods contributed to mod_digest." -ForegroundColor Yellow
}

$versionObj = [ordered]@{
    version         = $versionName
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
    & git -C $UsbRoot add .gitignore update-config.env play.ps1 play.bat play.sh publish-update.ps1 publish-test.ps1 install-test.ps1 Install-Test.bat install-windows.ps1 Install-Windows.bat install-linux.sh README.txt version.json data/yw2-recomp/settings.default.ini data/yw2-recomp/mods data/yw2-recomp/shader-cache-v3 bin lib
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
        if (-not (Test-InteractivePublishSession)) {
            Write-Host "ERROR: -Push requires an interactive session. Refusing to publish." -ForegroundColor Red
            exit 1
        }
        $remotes = (& git -C $UsbRoot remote)
        if ($remotes -contains "origin") {
            & git -C $UsbRoot fetch origin main --quiet 2>$null
            $originRev = (& git -C $UsbRoot rev-parse --verify "origin/main" 2>$null)
            $headRev   = (& git -C $UsbRoot rev-parse HEAD 2>$null)
            $rangeArgs = if ($originRev) { "origin/main..HEAD" } else { "HEAD" }
            $rangeLog  = @(& git -C $UsbRoot log --oneline $rangeArgs 2>$null | Where-Object { $_ })

            $exeSourceLine = if ($ExeSource) { $ExeSource } else { "(no Windows exe)" }
            $exeShaLine = if ($PublishedExeSha256) { $PublishedExeSha256 } else { "n/a" }
            $relayShaLine = if ($PublishedRelaySha256) { $PublishedRelaySha256 } else { "n/a" }

            Write-Host ""
            Write-Host "=== About to push to origin/main ===" -ForegroundColor Yellow
            if ($originRev) {
                Write-Host ("  Range:   {0}..{1} (origin/main..HEAD)" -f $originRev.Substring(0,7), $headRev.Substring(0,7)) -ForegroundColor Yellow
            } else {
                Write-Host "  Range:   all commits (origin/main does not exist yet; first push)" -ForegroundColor Yellow
            }
            Write-Host ("  Exe:     {0}" -f $exeSourceLine) -ForegroundColor Yellow
            Write-Host ("  Exe SHA: {0}" -f $exeShaLine) -ForegroundColor Yellow
            Write-Host ("  Relay:   {0}" -f $relayShaLine) -ForegroundColor Yellow
            if ($rangeLog.Count -gt 0) {
                $rangeLog | ForEach-Object { Write-Host "    $_" -ForegroundColor Yellow }
            } else {
                Write-Host "    (no new commits)" -ForegroundColor Yellow
            }
            Write-Host "====================================" -ForegroundColor Yellow

            if ($rangeLog.Count -eq 0) {
                Write-Host "[Git]     Nothing new to push." -ForegroundColor DarkGray
            } else {
                $answer = Read-Host "Type 'publish' to push these commits to origin/main (anything else cancels)"
                if ($answer -cne "publish") {
                    Write-Host "[Git]     Publish cancelled; nothing was pushed." -ForegroundColor Yellow
                    exit 1
                }
                & git -C $UsbRoot push -u origin main
                if ($LASTEXITCODE -ne 0) {
                    Write-Host "[Git]     Push failed (exit $LASTEXITCODE); nothing else was changed." -ForegroundColor Red
                    exit 1
                }
                Write-Host "[Git]     Pushed to origin/main." -ForegroundColor Green
            }
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
        "/XF", "console_id", "settings.ini", "instance-*.lock", "channel.env", "test-version.json"
    )
    & robocopy @roboArgs | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "Robocopy to $UsbTarget failed with code $LASTEXITCODE" }
    Write-Host "[USB]     Synced $UsbTarget successfully!" -ForegroundColor Green
}
