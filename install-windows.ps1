param(
    [string]$TargetDir = (Join-Path $env:LOCALAPPDATA "FantasyLife-PC"),
    [switch]$NoFirewall
)

$ErrorActionPreference = "Stop"
$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not (Test-Path (Join-Path $SourceDir "bin\fl_eur.exe")) -and (Test-Path (Join-Path $SourceDir "FantasyLife-PC\bin\fl_eur.exe"))) {
    $SourceDir = Join-Path $SourceDir "FantasyLife-PC"
}

Write-Host "==============================================================" -ForegroundColor Cyan
Write-Host " Fantasy Life PC - Windows Installer" -ForegroundColor Cyan
Write-Host " Source:      $SourceDir" -ForegroundColor Gray
Write-Host " Destination: $TargetDir" -ForegroundColor Gray
Write-Host "==============================================================" -ForegroundColor Cyan

New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null

# Copy files with robocopy (preserves .git for auto-updates, skips overwriting existing saves/settings/console_id)
Write-Host "`n[1/3] Copying game files, runtime, mods, and update repository (~1.1 GB)..." -ForegroundColor Yellow
$roboArgs = @(
    $SourceDir,
    $TargetDir,
    "/E",
    "/R:2",
    "/W:1",
    "/NP",
    "/NFL",
    "/NDL",
    "/XD", "saves", "logs", ".update-tmp", ".freebuff",
    "/XF", "console_id", "settings.ini", "instance-*.lock", "channel.env", "test-version.json"
)
& robocopy @roboArgs | Out-Null
if ($LASTEXITCODE -ge 8) {
    Write-Error "Robocopy failed with exit code $LASTEXITCODE"
    exit 1
}

# Seed saves directory (and copy starter saves only if destination saves don't exist yet)
foreach ($slot in @("freelife", "story")) {
    $dstSlot = Join-Path $TargetDir "saves\$slot"
    $srcSlot = Join-Path $SourceDir "saves\$slot"
    if (-not (Test-Path $dstSlot)) {
        New-Item -ItemType Directory -Path $dstSlot -Force | Out-Null
        if (Test-Path $srcSlot) {
            Copy-Item -Path "$srcSlot\*" -Destination $dstSlot -Recurse -Force
        }
    }
}

# Seed settings.ini on first install (never copy console_id so each PC gets a unique 3DS ID)
$SettingsIni = Join-Path $TargetDir "data\yw2-recomp\settings.ini"
$DefaultIni  = Join-Path $TargetDir "data\yw2-recomp\settings.default.ini"
if (-not (Test-Path $SettingsIni) -and (Test-Path $DefaultIni)) {
    Copy-Item -Path $DefaultIni -Destination $SettingsIni -Force
}

Write-Host "[2/3] Creating Desktop and Start Menu shortcuts..." -ForegroundColor Yellow
$DesktopDir  = [Environment]::GetFolderPath("Desktop")
$ProgramsDir = [Environment]::GetFolderPath("Programs")
# The shortcut opens the launcher window (update, play with mods, play vanilla).
# Its icon is generated from this PC's own game dump; the package itself only
# ships a neutral fallback icon.
$IconPath = Join-Path $TargetDir "bin\fantasy-life.ico"
$IconTool = Join-Path $TargetDir "bin\launcher\icon.ps1"
$HaveIconTool = Test-Path -LiteralPath $IconTool
if ($HaveIconTool) {
    . $IconTool
    try { $IconPath = Get-FantasyLifeIconPath -InstallDir $TargetDir -RomPath (Join-Path $TargetDir "game\FantasyLife_EU.3ds") } catch {}
}

foreach ($dir in @($DesktopDir, $ProgramsDir)) {
    if ($dir -and (Test-Path $dir)) {
        $lnkPath = Join-Path $dir "Fantasy Life.lnk"
        if ($HaveIconTool) {
            Set-FantasyLifeShortcut -Path $lnkPath -InstallDir $TargetDir -IconPath $IconPath -Description "Fantasy Life PC"
        } else {
            $sc = (New-Object -ComObject WScript.Shell).CreateShortcut($lnkPath)
            $sc.TargetPath       = Join-Path $TargetDir "play.bat"
            $sc.WorkingDirectory = $TargetDir
            $sc.IconLocation     = $IconPath + ",0"
            $sc.Description      = "Fantasy Life PC"
            $sc.Save()
        }
    }
}

Write-Host "[3/3] Installation complete!" -ForegroundColor Green
Write-Host ""
Write-Host "  Installed to:     $TargetDir" -ForegroundColor Cyan
Write-Host "  Desktop Shortcut: $DesktopDir\Fantasy Life.lnk" -ForegroundColor Cyan
Write-Host "  Updates:          The launcher window shows when an update is ready (one click)" -ForegroundColor Cyan
Write-Host ""

# Optional Firewall button in the launcher is the only elevation entry point.

