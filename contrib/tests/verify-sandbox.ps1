# Offline integration checks. Never calls gh/winget, runs the game, or invokes
# publish-update.ps1. The publisher's mod block is exercised in isolation.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$SourceRepo,
    [string]$Archive = ''
)
$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -ne 5) { throw 'Run this with Windows PowerShell 5.1.' }
$Package = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Root = Join-Path ([IO.Path]::GetTempPath()) ('fl-contrib-qa-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $Root | Out-Null
Write-Host "SANDBOX: $Root"

function Assert([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw "FAIL: $Message" }
    Write-Host "PASS: $Message"
}
function Native([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program failed ($LASTEXITCODE)" }
}
function TextFile([string]$Path, [string]$Text) {
    New-Item -ItemType Directory -Path (Split-Path -Parent $Path) -Force | Out-Null
    [IO.File]::WriteAllText($Path, $Text, (New-Object Text.UTF8Encoding($false)))
}
function Snapshot([string]$Path) {
    return (@(Get-ChildItem -LiteralPath $Path -Recurse -File | Sort-Object FullName |
        ForEach-Object { $_.FullName + '=' + (Get-FileHash -LiteralPath $_.FullName).Hash }) -join "`n")
}
function ChildScript([string]$Text) {
    $script = Join-Path $Root ('child-' + [guid]::NewGuid().ToString('N') + '.ps1')
    TextFile $script ("`$ErrorActionPreference = 'Stop'`n" + $Text)
    Native powershell.exe @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $script)
}

# Parse all package scripts with the 5.1 parser (no script execution).
$scripts = @(Get-ChildItem -LiteralPath $Package -Recurse -Filter '*.ps1' -File |
    Where-Object { $_.FullName -notmatch '[\\/]\.git[\\/]' })
foreach ($script in $scripts) {
    $tokens = $null; $errors = $null
    [void][Management.Automation.Language.Parser]::ParseFile($script.FullName, [ref]$tokens, [ref]$errors)
    Assert ($errors.Count -eq 0) "PowerShell 5.1 parse $($script.Name)"
}

# Only this tiny fake stable install is used. The non-executable text file means
# an accidental game launch cannot launch the actual runtime.
$Stable = Join-Path $Root 'stable'
TextFile (Join-Path $Stable 'bin\fl_eur.exe') 'not an executable: sandbox fixture'
TextFile (Join-Path $Stable 'game\FantasyLife_EU.3ds') 'not a game dump: extraction skipped by DryRun'
TextFile (Join-Path $Stable 'game\OriginIsland_DLC.cia') 'not a DLC dump'
TextFile (Join-Path $Stable 'data\yw2-recomp\settings.default.ini') '[test]'
foreach ($name in @('play.ps1', 'play.bat', 'play.sh', 'publish-test.ps1', 'install-test.ps1', 'Install-Test.bat')) {
    Copy-Item -LiteralPath (Join-Path $Package $name) -Destination (Join-Path $Stable $name)
}
$ModRoot = Join-Path $Stable 'data\yw2-recomp\mods\fantasylife'
foreach ($name in @('alpha', 'beta', 'fifth-mod')) {
    TextFile (Join-Path $ModRoot "$name\overlay.json") '{"format":"sandbox"}'
}
TextFile (Join-Path $Stable 'version.json') '{"version":"sandbox","mods":["beta","fifth-mod","alpha"]}'
$StableBefore = Snapshot $Stable
$KitExport = Join-Path $Root 'kit-export'
Native git @('init', '-b', 'main', $KitExport)
Native python @('-I', (Join-Path $SourceRepo 'tools\export_modkit.py'), $KitExport)
Native git @('-C', $KitExport, 'add', '--', '.modkit-export.json', '.gitignore', '.gitattributes', 'README.md', 'docs/modding-guide.md', 'tools', 'mods')
Native git @('-C', $KitExport, '-c', 'user.name=Sandbox', '-c', 'user.email=sandbox@example.invalid', 'commit', '-m', 'Temporary exported kit fixture')
$LocalUrl = ([uri]($KitExport + '\')).AbsoluteUri.TrimEnd('/')
$Workspace = Join-Path $Root 'work shop'
$Target = Join-Path $Root 'test'
$Setup = Join-Path $Package 'contrib\setup-contrib.ps1'
$SetupArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $Setup,
    '-WorkspaceDir', $Workspace, '-StableDir', $Stable, '-TestDir', $Target,
    '-RepoUrl', $LocalUrl, '-DryRun', '-NoShortcuts')
Native powershell.exe $SetupArgs
Assert (Test-Path -LiteralPath (Join-Path $Workspace 'modkit\.git')) 'setup cloned only the exported kit over file://'
Assert (-not (Test-Path -LiteralPath (Join-Path $Workspace 'modkit\extracted'))) 'DryRun left extraction untouched'
Assert (-not (Test-Path -LiteralPath $Target)) 'DryRun did not create any test install'
foreach ($name in @('AGENTS.md', 'knowledge.md')) {
    Assert ((Get-FileHash (Join-Path $Workspace $name)).Hash -eq (Get-FileHash (Join-Path $Package 'contrib\AGENT-PROTOCOL.md')).Hash) "setup copied identical $name"
}
$WorkshopClone = Join-Path $Workspace 'modkit'
Native git @('-C', $WorkshopClone, 'switch', '-c', 'contrib/keep-my-work')
TextFile (Join-Path $WorkshopClone 'uncommitted-note.txt') 'do not lose this work'
TextFile (Join-Path $Workspace 'AGENTS.md') 'old protocol'
Native powershell.exe $SetupArgs
$branch = & git -C $WorkshopClone branch --show-current
Assert ($branch -eq 'contrib/keep-my-work') 'rerun preserves the active contribution branch'
Assert ((Get-Content -LiteralPath (Join-Path $WorkshopClone 'uncommitted-note.txt') -Raw) -eq 'do not lose this work') 'rerun preserves uncommitted work'
Assert ((Get-FileHash (Join-Path $Workspace 'AGENTS.md')).Hash -eq (Get-FileHash (Join-Path $Package 'contrib\AGENT-PROTOCOL.md')).Hash) 'rerun repairs outdated protocol'
Assert ((Snapshot $Stable) -eq $StableBefore) 'setup left fake stable byte-for-byte unchanged'

# Run play.ps1 -NoLaunch in an isolated child process; capture chosen env paths.
$Play = Join-Path $Stable 'play.ps1'
$Result = Join-Path $Root 'launch-result.txt'
function Check-Launch([string[]]$Expected, [string]$Message) {
    $body = @'
$env:FL_MOD_DIRS = $null
& '__PLAY__' -NoUpdate -NoLaunch -NoFirewall
[IO.File]::WriteAllText('__RESULT__', [string]$env:FL_MOD_DIRS)
'@
    ChildScript ($body.Replace('__PLAY__', $Play.Replace("'", "''")).Replace('__RESULT__', $Result.Replace("'", "''")))
    $actual = [IO.File]::ReadAllText($Result)
    $wanted = @($Expected | ForEach-Object { Join-Path $ModRoot $_ }) -join ';'
    Assert ($actual -eq $wanted) $Message
}
Check-Launch @('beta', 'fifth-mod', 'alpha') 'stable -NoLaunch follows version.json order including an extra mod'
TextFile (Join-Path $Stable 'version.json') '{"mods":[]}'
Check-Launch @() 'explicit empty mods array stays empty'
TextFile (Join-Path $Stable 'version.json') '{"version":"old"}'
Check-Launch @('alpha', 'beta', 'fifth-mod') 'old manifest falls back to present overlay folders'
TextFile (Join-Path $Stable 'version.json') '{broken'
Check-Launch @('alpha', 'beta', 'fifth-mod') 'malformed stable manifest falls back to present overlays'
TextFile (Join-Path $Stable 'channel.env') 'FL_CHANNEL=test'
TextFile (Join-Path $Stable 'test-version.json') '{"label":"sandbox-test","mods":["fifth-mod"]}'
Check-Launch @('fifth-mod') 'test channel still uses test-version.json only'

# The fake stable's baseline publisher must include the future third mod; no
# shortcuts, network/firewall work, game process or real install is involved.
TextFile (Join-Path $Stable 'version.json') '{"mods":["beta","fifth-mod","alpha"]}'
$StableBefore = Snapshot $Stable
Native powershell.exe @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $Stable 'publish-test.ps1'),
    '-StableDir', $Stable, '-TargetDir', $Target, '-Exe', (Join-Path $Stable 'bin\fl_eur.exe'),
    '-Label', 'contrib-baseline', '-NoFirewall', '-NoShortcuts')
$testManifest = Get-Content (Join-Path $Target 'test-version.json') -Raw | ConvertFrom-Json
Assert (($testManifest.mods -join ',') -eq 'beta,fifth-mod,alpha') 'test baseline includes every stable manifest mod'
TextFile (Join-Path $Target 'saves\keep.txt') 'my save'
Native powershell.exe @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $Stable 'publish-test.ps1'),
    '-StableDir', $Stable, '-TargetDir', $Target, '-Label', 'contrib-baseline', '-NoFirewall', '-NoShortcuts')
Assert ((Get-Content (Join-Path $Target 'saves\keep.txt') -Raw) -eq 'my save') 'baseline reset preserves test saves'
Assert ((Snapshot $Stable) -eq $StableBefore) 'test publisher left fake stable unchanged'

# Execute the protocol's literal ONE -Command call, including its quoting and
# in-process array. Only fixture paths, with shortcut creation suppressed.
$descriptor = Join-Path $Workspace 'contrib-local.json'
$config = Get-Content -LiteralPath $descriptor -Raw | ConvertFrom-Json
$config.dry_run = $false
$config | ConvertTo-Json | Set-Content -LiteralPath $descriptor -Encoding UTF8
TextFile (Join-Path $WorkshopClone 'tools\build\contrib\overlays\fire-sword\overlay.json') '{"format":"sandbox"}'
$protocol = Get-Content -LiteralPath (Join-Path $Package 'contrib\AGENT-PROTOCOL.md') -Raw
$publishCommand = @($protocol -split "`r?`n" | Where-Object { $_ -like 'powershell.exe*' -and $_ -like '*-ModDirs $mods*' })
Assert ($publishCommand.Count -eq 1) 'one unambiguous protocol publish command found'
$outer = "Set-Location -LiteralPath '" + $Workspace.Replace("'", "''") + "'`n" + $publishCommand[0].Replace('-NoFirewall;', '-NoFirewall -NoShortcuts;')
ChildScript $outer
$testManifest = Get-Content (Join-Path $Target 'test-version.json') -Raw | ConvertFrom-Json
Assert (($testManifest.mods -join ',') -eq 'alpha,beta,fifth-mod,fire-sword') 'protocol -Command passes every stable mod plus new overlay as an array'
Assert ($testManifest.label -like 'contrib fire-sword *') 'protocol writes the contrib topic and SHA label'
Assert ((Snapshot $Stable) -eq $StableBefore) 'protocol publishing left fake stable unchanged'

# Extract ONLY the mod section from the publisher, never invoke the publisher.
# A shim records command argument order and provides minimal overlay manifests.
# This tests arbitrary new names, order, empty/single arrays, validation/cleanup
# and stack checking without needing real game resources or publishing artifacts.
$PublisherText = Get-Content -LiteralPath (Join-Path $Package 'publish-update.ps1') -Raw
$start = $PublisherText.IndexOf('# 4. Sync or Rebuild Mod Overlays')
$end = $PublisherText.IndexOf('# 5. Sync precompiled Shader Cache')
Assert ($start -ge 0 -and $end -gt $start) 'isolated publisher mod block located'
$ModBlock = [scriptblock]::Create($PublisherText.Substring($start, $end - $start))
$MainRepo = Join-Path $Root 'staging-source'
Native git @('init', '-b', 'main', $MainRepo)
$ModsDir = Join-Path $Root 'staged-mods'
$WinPkg = Join-Path $Root 'no-windows-package'
$LinuxPkg = Join-Path $Root 'no-linux-package'
$FromTest = $false
$RebuildMods = $true
New-Item -ItemType Directory -Path $ModsDir -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $MainRepo 'extracted\fl_eu\archive') -Force | Out-Null
foreach ($name in @('arbitrary-one', 'arbitrary-two')) { TextFile (Join-Path $MainRepo "mods\$name\mod.json") '{"format":"fl-mod-source-v1","name":"fixture"}' }
$script:Calls = @()
function python {
    $script:Calls += ,@($args)
    $global:LASTEXITCODE = 0
    if ($args[2] -eq 'build') {
        if ($args[3] -ne (Join-Path $MainRepo 'extracted\fl_eu\archive') -or $args[6] -ne '--replace') { throw 'Wrong build arguments' }
        TextFile (Join-Path ([string]$args[5]) 'overlay.json') '{"format":"sandbox"}'
    } elseif ($args[2] -ne 'check-stack') { throw 'Unexpected python command' }
}
TextFile (Join-Path $MainRepo 'mods\enabled.json') '["arbitrary-two","arbitrary-one"]'
TextFile (Join-Path $ModsDir 'obsolete\overlay.json') '{}'
. $ModBlock
Assert (($ModNames -join ',') -eq 'arbitrary-two,arbitrary-one') 'rebuild reads enabled.json in order with no fixed mod names'
Assert ($script:Calls.Count -eq 3 -and $script:Calls[2][2] -eq 'check-stack') 'rebuild checks complete stack after both builds'
Assert (-not (Test-Path (Join-Path $ModsDir 'obsolete'))) 'staging drops obsolete overlays'
TextFile (Join-Path $MainRepo 'mods\enabled.json') '["arbitrary-one"]'
. $ModBlock
Assert ($ModNames.Count -eq 1 -and $ModNames[0] -eq 'arbitrary-one') 'single-element enabled array works under 5.1'
TextFile (Join-Path $MainRepo 'mods\enabled.json') '[]'
. $ModBlock
Assert ($ModNames.Count -eq 0 -and @(Get-ChildItem -LiteralPath $ModsDir -Directory).Count -eq 0) 'empty enabled array removes staged mods'
foreach ($bad in @('["../escape"]', '["arbitrary-one","arbitrary-one"]', '"not-an-array"')) {
    TextFile (Join-Path $MainRepo 'mods\enabled.json') $bad
    $rejected = $false
    try { . $ModBlock } catch { $rejected = $true }
    Assert $rejected "invalid enabled list rejected: $bad"
}
Remove-Item Function:\python
Assert ($PublisherText -match 'git -C \$UsbRoot add [^\r\n]*\bcontrib\b') 'package staging includes contrib/'

# Exercise the ZIP updater copy block with a fixture archive, no HTTP request.
$ZipRoot = Join-Path $Root 'zip-source'
TextFile (Join-Path $ZipRoot 'contrib\sentinel.md') 'new contributor instructions'
TextFile (Join-Path $ZipRoot 'contrib\tests\nested.md') 'nested instructions'
TextFile (Join-Path $ZipRoot 'version.json') '{"mods":[]}'
Compress-Archive -Path (Join-Path $ZipRoot '*') -DestinationPath (Join-Path $Root 'fixture.zip')
Expand-Archive -LiteralPath (Join-Path $Root 'fixture.zip') -DestinationPath (Join-Path $Root 'zip-extract')
$PlayText = Get-Content -LiteralPath (Join-Path $Package 'play.ps1') -Raw
$start = $PlayText.IndexOf('# Runtime/data first.')
$end = $PlayText.IndexOf('# Mods are mirrored:')
$CopyBlock = [scriptblock]::Create($PlayText.Substring($start, $end - $start))
$Here = Join-Path $Root 'zip-installed'
$packageRoot = Join-Path $Root 'zip-extract'
& $CopyBlock
Assert ((Get-Content (Join-Path $Here 'contrib\sentinel.md') -Raw) -eq 'new contributor instructions') 'ZIP updater copies contrib/'
& $CopyBlock
Assert ((Get-Content (Join-Path $Here 'contrib\tests\nested.md') -Raw) -eq 'nested instructions') 'ZIP updater refreshes nested contributor files'
Assert (-not (Test-Path (Join-Path $Here 'contrib\tests\tests'))) 'repeated ZIP updates do not nest directories'

# Optional real rebuild of all enabled source mods in this TEMP staging root.
if ($Archive) {
    $Archive = (Resolve-Path -LiteralPath $Archive).Path
    $MainRepo = Join-Path $Root 'real-source-clone'
    Native git @('clone', '--no-hardlinks', '--single-branch', $SourceRepo, $MainRepo)
    Copy-Item -LiteralPath (Join-Path $SourceRepo 'mods\enabled.json') -Destination (Join-Path $MainRepo 'mods\enabled.json') -Force
    $ModsDir = Join-Path $Root 'real-staged-mods'
    New-Item -ItemType Directory -Path $ModsDir -Force | Out-Null
    # Keep the actual staging block; substitute only its archive lookup so the
    # real dump/extraction stays at its original read-only path outside TEMP.
    $realBlockText = $PublisherText.Substring($PublisherText.IndexOf('# 4. Sync or Rebuild Mod Overlays'),
        $PublisherText.IndexOf('# 5. Sync precompiled Shader Cache') - $PublisherText.IndexOf('# 4. Sync or Rebuild Mod Overlays'))
    $realBlockText = $realBlockText.Replace('$ArchiveDir = Join-Path $MainRepo "extracted\fl_eu\archive"',
        ('$ArchiveDir = ''' + $Archive.Replace("'", "''") + ''''))
    . ([scriptblock]::Create($realBlockText))
    Assert (($ModNames -join ',') -eq 'story-skip,eastern-plains-enemy,castele-house,wooden-sword') 'real publisher staging built all four enabled sources in order and stack checked in TEMP clone'
}
Write-Host "ALL SANDBOX CHECKS PASSED. Kept local logs/fixtures in $Root"
Write-Host 'Real authentication, installation and dump extraction were skipped; never upload this sandbox if real overlays were built.'
