param(
    [string]$TargetDir = (Join-Path $env:LOCALAPPDATA "FantasyLife-PC")
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

if (-not (Test-Path (Join-Path $SourceDir "game\FantasyLife_EU.3ds"))) {
    Write-Error "Game dump (game\FantasyLife_EU.3ds) not found in $SourceDir!"
    exit 1
}

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
$WshShell = New-Object -ComObject WScript.Shell
$DesktopDir  = [Environment]::GetFolderPath("Desktop")
$ProgramsDir = [Environment]::GetFolderPath("Programs")

foreach ($dir in @($DesktopDir, $ProgramsDir)) {
    if ($dir -and (Test-Path $dir)) {
        $lnkPath = Join-Path $dir "Fantasy Life.lnk"
        $sc = $WshShell.CreateShortcut($lnkPath)
        $sc.TargetPath       = Join-Path $TargetDir "play.bat"
        $sc.WorkingDirectory = $TargetDir
        $sc.IconLocation     = (Join-Path $TargetDir "bin\fantasy-life.ico") + ",0"
        $sc.Description      = "Fantasy Life PC (Auto-Updating)"
        $sc.Save()
    }
}

Write-Host "[3/3] Installation complete!" -ForegroundColor Green
Write-Host ""
Write-Host "  Installed to:     $TargetDir" -ForegroundColor Cyan
Write-Host "  Desktop Shortcut: $DesktopDir\Fantasy Life.lnk" -ForegroundColor Cyan
Write-Host "  Auto-Update:      Active (checks automatically on every launch)" -ForegroundColor Cyan
Write-Host ""
