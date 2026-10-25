# Windows PowerShell 5.1. DryRun still creates/repairs the local workspace and
# clones the supplied repository; it skips installs, gh, extraction and test setup.
[CmdletBinding()]
param(
    [string]$WorkspaceDir = (Join-Path $env:APPDATA 'FantasyLife-Contrib'),
    [string]$StableDir = (Join-Path $env:LOCALAPPDATA 'FantasyLife-PC'),
    [string]$RepoUrl = '',
    [switch]$DryRun,
    [string]$TestDir = (Join-Path $env:LOCALAPPDATA 'FantasyLife-PC-Test'),
    [switch]$NoShortcuts
)
$ErrorActionPreference = 'Stop'
$KitDir = $PSScriptRoot

function Invoke-Checked {
    param([string]$Program, [string[]]$Arguments)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program stopped (code $LASTEXITCODE). Show this message to Leo; no automatic cleanup was done." }
}
function Refresh-ToolPath {
    # Include the usual per-user locations even when WinGet's parent terminal
    # still has its old PATH. Do not replace PATH or other environment settings.
    $extra = @([Environment]::GetEnvironmentVariable('Path', 'Machine'),
        [Environment]::GetEnvironmentVariable('Path', 'User'),
        "$env:ProgramFiles\Git\cmd", "$env:LOCALAPPDATA\Programs\Git\cmd",
        "$env:LOCALAPPDATA\Programs\Python\Python312", "$env:ProgramFiles\Python312",
        "$env:ProgramFiles\GitHub CLI", "$env:LOCALAPPDATA\Microsoft\WinGet\Links")
    $env:Path = ($extra + $env:Path) -join ';'
}
function Find-Python312 {
    foreach ($candidate in @((Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'),
            (Join-Path $env:ProgramFiles 'Python312\python.exe'), 'python', 'py')) {
        $command = Get-Command $candidate -ErrorAction SilentlyContinue
        if (-not $command) { continue }
        $prefix = @()
        if ($candidate -eq 'py') { $prefix = @('-3.12') }
        $oldEap = $ErrorActionPreference
        try {
            $ErrorActionPreference = 'Continue'
            $found = & $command.Source @prefix -I -c 'import sys; print(sys.executable if sys.version_info[:2] == (3,12) else str())' 2>$null
            if ($LASTEXITCODE -eq 0 -and $found -and (Test-Path -LiteralPath ([string]$found))) { return [string]$found }
        } finally { $ErrorActionPreference = $oldEap }
    }
    return $null
}
function Require-Tool {
    param([string]$Name, [string]$Package, [scriptblock]$Detect)
    Write-Host "Checking $Name / Pruefe $Name."
    $found = & $Detect
    if ($found) { return $found }
    if ($DryRun) { Write-Host "[DryRun] Would offer to install $Name with WinGet."; return $null }
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw 'WinGet is missing. Ask Leo to install Microsoft App Installer, then run Setup-Contrib.bat again.'
    }
    $answer = Read-Host "Install $Name now? / $Name jetzt installieren? [y/j = yes, anything else = stop]"
    if ($answer -notmatch '^(?i:y|yes|j|ja)$') { throw "$Name was not installed. Run Setup-Contrib.bat when you are ready." }
    Invoke-Checked 'winget' @('install', '--id', $Package, '--exact', '--source', 'winget')
    Refresh-ToolPath
    $found = & $Detect
    if (-not $found) { throw "$Name is not available yet. Close this window and run Setup-Contrib.bat again. If that fails, ask Leo." }
    return $found
}
function Assert-SeparatePath {
    param([string]$Left, [string]$Right)
    if ($Left -eq $Right -or $Left.StartsWith($Right + '\', [StringComparison]::OrdinalIgnoreCase) -or
        $Right.StartsWith($Left + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw "These folders must be separate: $Left and $Right. Ask Leo to check the setup paths."
    }
}

try {
    Write-Host 'Preparing your mod workshop / Deine Mod-Werkstatt wird vorbereitet.'
    if (-not $RepoUrl) {
        $config = Join-Path $KitDir 'config.env'
        if (Test-Path -LiteralPath $config) {
            foreach ($line in Get-Content -LiteralPath $config) {
                if ($line -match '^\s*FL_CONTRIB_REPO\s*=(.*)$') { $RepoUrl = $Matches[1].Trim() }
            }
        }
    }
    if (-not $RepoUrl) { throw 'Leo must fill in FL_CONTRIB_REPO in contrib\config.env with the PRIVATE modding-kit repository URL, then publish the kit. / Leo muss zuerst die private Repo-Adresse eintragen.' }
    if ($RepoUrl -match '(?i)github\.com[:/]LAURlN/fl-project-blue(?:\.git)?/?$') { throw 'This is the PUBLIC game package repository. Ask Leo for the PRIVATE modding-kit repository URL.' }
    if ($RepoUrl -match '^https?://' -and ([uri]$RepoUrl).UserInfo) { throw 'Use a repository URL without a password or token. Sign in through the browser instead.' }
    $WorkspaceDir = [IO.Path]::GetFullPath($WorkspaceDir).TrimEnd('\')
    $StableDir = [IO.Path]::GetFullPath($StableDir).TrimEnd('\')
    $TestDir = [IO.Path]::GetFullPath($TestDir).TrimEnd('\')
    Assert-SeparatePath $WorkspaceDir $StableDir
    Assert-SeparatePath $WorkspaceDir $TestDir
    Assert-SeparatePath $StableDir $TestDir
    if (-not (Test-Path -LiteralPath (Join-Path $StableDir 'bin\fl_eur.exe') -PathType Leaf)) { throw "Your normal game is missing: $StableDir\bin\fl_eur.exe. Ask Leo to finish the normal installation first." }
    if (-not (Test-Path -LiteralPath (Join-Path $StableDir 'game\FantasyLife_EU.3ds') -PathType Leaf)) { throw "Your own game dump is missing from $StableDir\game\FantasyLife_EU.3ds. Ask Leo." }
    Refresh-ToolPath
    $git = Require-Tool 'Git' 'Git.Git' { $cmd = Get-Command git -ErrorAction SilentlyContinue; if ($cmd) { $cmd.Source } }
    $python = Require-Tool 'Python 3.12' 'Python.Python.3.12' { Find-Python312 }
    $gh = Require-Tool 'GitHub CLI' 'GitHub.cli' { $cmd = Get-Command gh -ErrorAction SilentlyContinue; if ($cmd) { $cmd.Source } }
    if (-not $git) { throw '[DryRun] Git is required to exercise the local clone. No software was installed.' }
    Write-Host 'Signing in to GitHub in your browser / Anmeldung bei GitHub im Browser.'
    if ($DryRun) { Write-Host '[DryRun] Skipping every gh command, login and installation.' } else {
        $oldEap = $ErrorActionPreference
        try {
            $ErrorActionPreference = 'Continue'
            & $gh auth status --hostname github.com *> $null
            $signedIn = ($LASTEXITCODE -eq 0)
        } finally { $ErrorActionPreference = $oldEap }
        if (-not $signedIn) { Invoke-Checked $gh @('auth', 'login', '--web', '--hostname', 'github.com', '--git-protocol', 'https') }
        Invoke-Checked $gh @('auth', 'setup-git', '--hostname', 'github.com')
    }
    Write-Host 'Opening your private modding kit / Dein privates Modding-Kit wird vorbereitet.'
    New-Item -ItemType Directory -Path $WorkspaceDir -Force | Out-Null
    $clone = Join-Path $WorkspaceDir 'modkit'
    if (-not (Test-Path -LiteralPath $clone)) {
        Invoke-Checked $git @('clone', '--branch', 'main', '--', $RepoUrl, $clone)
    } else {
        if (-not (Test-Path -LiteralPath (Join-Path $clone '.git'))) { throw "$clone already exists but is not a Git clone. Ask Leo; setup will not replace it." }
        $actualOrigin = & $git -C $clone remote get-url origin
        if ($LASTEXITCODE -ne 0 -or ([string]$actualOrigin).TrimEnd('/') -ne $RepoUrl.TrimEnd('/')) { throw 'The existing workspace points at a different repository. Ask Leo; setup will not change remotes or branches.' }
        Write-Host 'Keeping your work and branch; no pull, reset or checkout / Deine Arbeit bleibt erhalten.'
    }
    foreach ($required in @('tools\phase0_extract.py', 'tools\fl_archive.py', 'tools\fl_mod.py', 'docs\modding-guide.md')) {
        if (-not (Test-Path -LiteralPath (Join-Path $clone $required))) { throw "The private modding kit is incomplete ($required missing). Ask Leo." }
    }
    Write-Host 'Reading your own dump locally; this can take a while / Dein eigener Dump wird lokal gelesen.'
    $extracted = Join-Path $clone 'extracted\fl_eu'
    $archive = Join-Path $extracted 'archive'
    $readyMarker = Join-Path $extracted '.contrib-extraction-complete'
    if ($DryRun) {
        Write-Host "[DryRun] Would extract $StableDir\game\FantasyLife_EU.3ds to $extracted, then unpack romfs\_file_archive.bin to archive. No dump copied or extracted."
    } elseif (-not (Test-Path -LiteralPath $readyMarker)) {
        if (Test-Path -LiteralPath $extracted) {
            # Never erase an existing/partial extraction. Retain it for diagnosis.
            # A fresh sibling allows an interrupted run to be repaired safely.
            $saved = "$extracted.incomplete-$(Get-Date -Format 'yyyyMMdd-HHmmss')-$([guid]::NewGuid().ToString('N').Substring(0,6))"
            if (-not $saved.StartsWith($clone + '\extracted\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Extraction backup path check failed.' }
            Move-Item -LiteralPath $extracted -Destination $saved
            Write-Host "Previous extraction kept at $saved / Bisherige Dateien bleiben dort erhalten."
        }
        Invoke-Checked $python @('-I', (Join-Path $clone 'tools\phase0_extract.py'), (Join-Path $StableDir 'game\FantasyLife_EU.3ds'), '--output', $extracted)
        Invoke-Checked $python @('-I', (Join-Path $clone 'tools\fl_archive.py'), 'extract', (Join-Path $extracted 'romfs\_file_archive.bin'), $archive)
        Set-Content -LiteralPath $readyMarker -Encoding ASCII -Value 'Completed by setup-contrib.ps1; no dump is copied into the workspace.'
    } elseif (-not (Test-Path -LiteralPath (Join-Path $archive '.fl_archive\manifest.json')) -or
              -not (Test-Path -LiteralPath (Join-Path $archive '.fl_archive\original.bin'))) {
        throw 'Extraction metadata is missing. Ask Leo to check it; setup will not erase your files.'
    } else { Write-Host 'Your local extraction is already ready / Die lokalen Spieldaten sind bereits bereit.' }
    Write-Host 'Refreshing instructions for your agent / Die Anleitung fuer deinen Agenten wird erneuert.'
    foreach ($name in @('AGENTS.md', 'knowledge.md')) {
        Copy-Item -LiteralPath (Join-Path $KitDir 'AGENT-PROTOCOL.md') -Destination (Join-Path $WorkspaceDir $name) -Force
    }
    # A local descriptor is outside Git, includes no credentials, and lets agents
    # use custom paths instead of guessing paths from environment variables.
    [ordered]@{ workspace = $WorkspaceDir; clone = $clone; stable = $StableDir; test = $TestDir; dry_run = [bool]$DryRun } |
        ConvertTo-Json | Set-Content -LiteralPath (Join-Path $WorkspaceDir 'contrib-local.json') -Encoding UTF8
    @'
# Fantasy Life Mod Workshop / Mod-Werkstatt

Open THIS folder in Freebuff. / Diesen Ordner in Freebuff oeffnen.
Tell the agent what you want to add. / Sag dem Agenten, was du hinzufuegen willst.
Example: "Ich moechte ein Feuerschwert wie das Holzschwert."
Agent: read AGENTS.md (identical to knowledge.md) and contrib-local.json first.
Kit is in modkit/. Only your own mods/<topic>/ authoring sources belong in its repo.
Run Setup-Contrib.bat again after a normal game update to refresh instructions.
Never upload this whole folder or extracted game files.
'@ | Set-Content -LiteralPath (Join-Path $WorkspaceDir 'README.md') -Encoding UTF8
    Write-Host 'Preparing Fantasy Life (Test) / Die getrennte Testversion wird vorbereitet.'
    if (-not (Test-Path -LiteralPath $TestDir)) {
        if ($DryRun) { Write-Host '[DryRun] Would call the stable publish-test.ps1 with contrib-baseline; no test install or shortcut changed.' } else {
            $publisher = Join-Path $StableDir 'publish-test.ps1'
            if (-not (Test-Path -LiteralPath $publisher)) { throw 'publish-test.ps1 is missing. Update the normal game, then run setup again.' }
            $publishArgs = @{ Exe = (Join-Path $StableDir 'bin\fl_eur.exe'); StableDir = $StableDir; TargetDir = $TestDir; Label = 'contrib-baseline' }
            if ($NoShortcuts) { $publishArgs.NoShortcuts = $true }
            # Suppress unrelated software/firewall prompts during contributor setup.
            $publishArgs.NoFirewall = $true
            & $publisher @publishArgs
            if (-not (Test-Path -LiteralPath (Join-Path $TestDir 'test-version.json'))) { throw 'Test setup did not finish. Show its message to Leo.' }
        }
    } else { Write-Host 'Your existing test install is kept / Deine vorhandene Testversion bleibt erhalten.' }
    $wantShortcut = $false
    if (-not $NoShortcuts -and -not $DryRun) {
        $wantShortcut = (Read-Host 'Add workshop desktop shortcut? / Werkstatt-Verknuepfung erstellen? [y/j = yes]') -match '^(?i:y|yes|j|ja)$'
    }
    if ($wantShortcut) {
        Write-Host 'Adding the workshop desktop shortcut / Die Werkstatt bekommt eine Desktop-Verknuepfung.'
        $desktop = [Environment]::GetFolderPath('Desktop')
        if ($desktop -and (Test-Path -LiteralPath $desktop)) {
            $shell = New-Object -ComObject WScript.Shell
            $link = $shell.CreateShortcut((Join-Path $desktop 'Fantasy Life Mod Workshop.lnk'))
            $link.TargetPath = Join-Path $env:WINDIR 'explorer.exe'
            $link.Arguments = '"' + $WorkspaceDir + '"'
            $link.Description = 'Open this folder in Freebuff / Diesen Ordner in Freebuff oeffnen'
            $link.Save()
        }
    }
    if ($DryRun) { Write-Host 'Dry run complete; authentication, extraction and the test install still need real setup.' } else { Write-Host "You're ready! / Du bist bereit!" -ForegroundColor Green }
    Write-Host "Open this folder in Freebuff / Diesen Ordner in Freebuff oeffnen: $WorkspaceDir"
} catch {
    Write-Host "Setup stopped / Einrichtung gestoppt: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
