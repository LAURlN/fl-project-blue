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
    [switch]$PreviewModManager,
    [string]$Screenshot = ""
)

# Fantasy Life PC launcher: local setup, controls, mods and user-space launching.
# No automatic update checks or elevation. Firewall setup is an explicit UI action.
# -NoUpdate remains accepted for compatibility with existing shortcuts.

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

# Launcher preferences (data\yw2-recomp\launcher.json): the selected save profile,
# mods the player toggled off (disabled_mods), and folders installed from ZIPs
# (user_mods). Read-merge-write always, so the window, install/uninstall helpers
# and background jobs never clobber keys the other side owns.
function Read-FLPrefs {
    param([string]$Path = (Join-Path $Here "data\yw2-recomp\launcher.json"))
    $obj = Read-FLJson $Path
    $save = "freelife"
    $disabled = @()
    $user = @()
    if ($obj) {
        if ($obj.PSObject.Properties.Name -contains "save" -and $obj.save) { $save = [string]$obj.save }
        if ($obj.PSObject.Properties.Name -contains "disabled_mods" -and $obj.disabled_mods) {
            $disabled = @($obj.disabled_mods | Where-Object { $_ -is [string] } | ForEach-Object { [string]$_ })
        }
        if ($obj.PSObject.Properties.Name -contains "user_mods" -and $obj.user_mods) {
            $user = @($obj.user_mods | Where-Object { $_ -is [string] } | ForEach-Object { [string]$_ })
        }
    }
    return [pscustomobject]@{ save = $save; disabled_mods = $disabled; user_mods = $user }
}

function Write-FLPrefs {
    param([string]$Path, $Prefs)
    $obj = [ordered]@{
        save          = [string]$Prefs.save
        disabled_mods = @($Prefs.disabled_mods)
        user_mods     = @($Prefs.user_mods)
    }
    New-Item -ItemType Directory -Path (Split-Path -Parent $Path) -Force | Out-Null
    [IO.File]::WriteAllText($Path, ($obj | ConvertTo-Json), (New-Object Text.UTF8Encoding($false)))
    $statePath = Join-Path $Here "data\yw2-recomp\mods-state.json"
    $state = Read-FLJson $statePath
    if ($state -and $state.order) { Set-FLModOrder @($state.order) }
}

function Get-FLPrefsPath {
    return (Join-Path $Here "data\yw2-recomp\launcher.json")
}

# What is installed: stable version.json or test-version.json.
function Get-FLLocalVersion {
    param($Config)
    if ($Config.IsTest) { return Read-FLJson (Join-Path $Here "test-version.json") }
    return Read-FLJson (Join-Path $Here "version.json")
}

# What is installed: stable version.json or test-version.json, unioned with
# every overlay folder actually on disk (so user-installed mods always show up
# in the Mod Manager). Each entry has Folder, Name (from overlay.json or
# mod.json), Path, Present (a built overlay.json exists), SourceOnly (only an
# unbuilt mod.json), Listed (in the manifest's mods array), Author, Version,
# Enabled (not in launcher.json's disabled_mods) and Shipped (part of the
# build's manifest, i.e. core).
function Get-FLMods {
    param($Config, $LocalVersion)
    $modRoot = Join-Path $Here "data\yw2-recomp\mods\fantasylife"
    $names = @()
    $note = ""
    $haveList = $false
    if ($Config.IsTest) {
        if ($LocalVersion -and ($LocalVersion.PSObject.Properties.Name -contains "mods") -and $LocalVersion.mods) {
            $names = @($LocalVersion.mods)
            $haveList = $true
        }
    } else {
        # An explicit empty list means vanilla. Missing/old manifests fall back
        # to installed overlays; never infer fixed names from a build date.
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
                Where-Object { Test-FLModFolder $_.FullName } |
                Sort-Object Name | ForEach-Object { $_.Name })
        }
    }
    $prefs = Read-FLPrefs
    $manifestSet = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
    foreach ($n in $names) { [void]$manifestSet.Add([string]$n) }
    $userSet = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
    foreach ($u in @($prefs.user_mods)) { [void]$userSet.Add([string]$u) }
    $disabledSet = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
    foreach ($d in @($prefs.disabled_mods)) { [void]$disabledSet.Add([string]$d) }
    # Union manifest order first, then any extra installed folder (sorted) so
    # user-installed mods are always visible and toggleable.
    $extra = @(Get-ChildItem -LiteralPath $modRoot -Directory -ErrorAction SilentlyContinue |
        Where-Object { -not $manifestSet.Contains($_.Name) } | Sort-Object Name | ForEach-Object { $_.Name })
    $all = @($names) + @($extra)
    $state = Read-FLJson (Join-Path $Here "data\yw2-recomp\mods-state.json")
    if ($state -and $state.order) {
        $all = @(@($state.order | Where-Object { $all -contains $_ }) + @($all | Where-Object { $state.order -notcontains $_ }) | Select-Object -Unique)
    }
    $mods = @()
    foreach ($folder in $all) {
        $path = Join-Path $modRoot $folder
        if ($folder -notmatch '^[a-zA-Z0-9][a-zA-Z0-9._-]*$') { continue }
        if (-not (Test-FLModFolder $path) -and -not $manifestSet.Contains([string]$folder)) { continue }
        $overlay = Read-FLJson (Join-Path $path "overlay.json")
        $gb = Read-FLJson (Join-Path $path "gamebanana.json")
        $lua = (Test-Path -LiteralPath (Join-Path $path "script.lua")) -or @(Get-ChildItem -Path (Join-Path $path "scripts\*.lua") -File -ErrorAction SilentlyContinue).Count -gt 0
        $plugin = (Test-Path -LiteralPath (Join-Path $path "plugin.dll")) -or @(Get-ChildItem -Path (Join-Path $path "plugins\*.dll") -File -ErrorAction SilentlyContinue).Count -gt 0
        $kinds = @()
        if ($overlay) { if (@($overlay.sources).Count -gt 1) { $kinds += "Merged Stack" } else { $kinds += "Overlay" } }
        if ($lua) { $kinds += "Lua Script" }
        if ($plugin) { $kinds += "Plugin" }
        if (-not $kinds.Count) { $kinds += "Source" }
        $source = $null
        if (-not $overlay) { $source = Read-FLJson (Join-Path $path "mod.json") }
        $display = if ($overlay -and $overlay.name) { [string]$overlay.name }
                   elseif ($source -and $source.name) { [string]$source.name }
                   elseif ($gb -and $gb.mod_name) { [string]$gb.mod_name }
                   else { [string]$folder }
        $author = ""
        if ($overlay -and ($overlay.PSObject.Properties.Name -contains "author") -and $overlay.author) { $author = [string]$overlay.author }
        elseif ($source -and ($source.PSObject.Properties.Name -contains "author") -and $source.author) { $author = [string]$source.author }
        $version = ""
        if ($overlay -and ($overlay.PSObject.Properties.Name -contains "version") -and $overlay.version) { $version = [string]$overlay.version }
        elseif ($source -and ($source.PSObject.Properties.Name -contains "version") -and $source.version) { $version = [string]$source.version }
        $shipped = $manifestSet.Contains([string]$folder)
        # Core protection: manifest mods stay until the manifest drops them;
        # without a manifest only ZIP-installed folders (user_mods) are removable.
        $removable = if ($haveList) { (-not $shipped) -or $userSet.Contains([string]$folder) } else { $userSet.Contains([string]$folder) }
        # Default enabled: manifest mods always; with a manifest, extra folders
        # only when the player installed them (user_mods) or already enabled
        # them; without a manifest every installed overlay is the mod list.
        $defaultOn = if ($haveList) { $shipped -or $userSet.Contains([string]$folder) } else { $true }
        $mods += [pscustomobject]@{
            Kind       = $kinds -join " + "
            Submitter  = $(if ($gb) { [string]$gb.submitter } elseif ($overlay) { [string]$overlay.submitter })
            GameBananaId = $(if ($gb) { $gb.mod_id } elseif ($overlay) { $overlay.GameBananaId })
            FileId     = $(if ($gb) { $gb.file_id } elseif ($overlay) { $overlay.FileId })
            Description = $(if ($gb -and $gb.description) { [string]$gb.description } elseif ($overlay) { [string]$overlay.description })
            Folder     = [string]$folder
            Name       = $display
            Path       = $path
            Present    = ([bool]$overlay -or $lua -or $plugin)
            SourceOnly = (-not $overlay -and -not $lua -and -not $plugin) -and [bool]$source
            Listed     = $shipped
            Author     = $author
            Version    = $version
            Enabled    = $defaultOn -and (-not $disabledSet.Contains([string]$folder))
            Shipped    = $shipped
            Removable  = [bool]$removable
        }
    }
    return [pscustomobject]@{ Mods = $mods; Note = $note; Prefs = $prefs }
}

# Enabled overlay stack check, matching fl_mod.py check-stack and the runtime
# (port/runtime/src/games/fantasylife/mods.cpp): any resource id (resources[].id
# or a virtual_sizes key) claimed by two enabled folders is fatal. A single
# pre-merged overlay folder trivially has no pairwise conflicts. Returns an
# array of collisions: Id, Kind ("resource"|"virtual"), FolderA/NameA (first
# claim, load order), FolderB/NameB.
function Get-FLModConflicts {
    param([object[]]$Mods)
    $claim = @{}
    $conflicts = @()
    foreach ($mod in @($Mods)) {
        if (-not $mod -or -not $mod.Present) { continue }
        $overlay = Read-FLJson (Join-Path $mod.Path "overlay.json")
        if (-not $overlay) { continue }
        $ids = New-Object System.Collections.Generic.List[object]
        if ($overlay.PSObject.Properties.Name -contains "resources" -and $overlay.resources) {
            foreach ($r in @($overlay.resources)) {
                if ($null -ne $r -and ($r.PSObject.Properties.Name -contains "id") -and $null -ne $r.id) {
                    $ids.Add(@{ Id = [int]$r.id; Kind = "resource" })
                }
            }
        }
        if ($overlay.PSObject.Properties.Name -contains "virtual_sizes" -and $overlay.virtual_sizes) {
            foreach ($p in $overlay.virtual_sizes.PSObject.Properties) {
                $vid = 0
                if ([int]::TryParse([string]$p.Name, [ref]$vid)) { $ids.Add(@{ Id = $vid; Kind = "virtual" }) }
            }
        }
        foreach ($entry in $ids) {
            $key = [string]$entry.Id
            if ($claim.ContainsKey($key)) {
                $prev = $claim[$key]
                $conflicts += [pscustomobject]@{
                    Id = $entry.Id; Kind = $entry.Kind
                    FolderA = $prev.Folder; NameA = $prev.Name
                    FolderB = [string]$mod.Folder; NameB = [string]$mod.Name
                }
            } else {
                $claim[$key] = @{ Folder = [string]$mod.Folder; Name = [string]$mod.Name }
            }
        }
    }
    return $conflicts
}

# One call for launch decisions: enabled+present mods, pairwise conflicts, and
# listed+enabled mods whose overlay is missing (source-only mods never block).
function Test-FLModStack {
    param($ModInfo)
    $mods = @($ModInfo.Mods)
    $enabled = @($mods | Where-Object { $_.Enabled -and $_.Present })
    $conflicts = @(Get-FLModConflicts -Mods $enabled)
    $missing = @($mods | Where-Object { $_.Listed -and $_.Enabled -and -not $_.Present -and -not $_.SourceOnly })
    return [pscustomobject]@{
        Enabled   = $enabled
        Conflicts = $conflicts
        Missing   = $missing
        Blocked   = ($conflicts.Count -gt 0 -or $missing.Count -gt 0)
    }
}

# Sibling-discovery for the source-mod build toolchain (same pattern as
# Get-FLRomPath / Get-FLExePath). $null when python, fl_mod.py or the
# extracted archive is unavailable (standalone end-user package).
function Get-FLModToolchain {
    $python = $null
    foreach ($cmd in @("python", "py", "python3")) {
        $c = Get-Command $cmd -ErrorAction SilentlyContinue
        if ($c -and $c.Source -and $c.Source -notmatch "WindowsApps") { $python = $c.Source; break }
    }
    if (-not $python) { return $null }
    $flMod = $null
    foreach ($candidate in @(
        (Join-Path $Here "tools\fl_mod.py"),
        (Join-Path $Here "..\..\fl-wt\mod-stack\tools\fl_mod.py"),
        (Join-Path $Here "..\fl-project-blue\tools\fl_mod.py"),
        (Join-Path $Here "..\..\fl-project-blue\tools\fl_mod.py")
    )) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { $flMod = (Resolve-Path -LiteralPath $candidate).Path; break }
    }
    if (-not $flMod) { return $null }
    $archive = $null
    foreach ($candidate in @(
        (Join-Path $Here "extracted\fl_eu\archive"),
        (Join-Path $Here "..\fl-project-blue\extracted\fl_eu\archive"),
        (Join-Path $Here "..\..\fl-project-blue\extracted\fl_eu\archive")
    )) {
        if (Test-Path -LiteralPath $candidate -PathType Container) { $archive = (Resolve-Path -LiteralPath $candidate).Path; break }
    }
    if (-not $archive) { $archive = Join-Path $Here "extracted\fl_eu\archive" }
    return [pscustomobject]@{ Python = $python; FlMod = $flMod; Archive = $archive }
}

function ConvertTo-FLModSlug {
    param([string]$Name)
    $slug = ([string]$Name).Trim() -replace '[^a-zA-Z0-9._-]', '-'
    $slug = $slug -replace '-{2,}', '-'
    $slug = $slug.Trim('.', '-', '_')
    if (-not $slug -or $slug -notmatch '^[a-zA-Z0-9]') { $slug = "mod" }
    if ($slug.Length -gt 64) { $slug = $slug.Substring(0, 64) }
    if ($slug -notmatch '^[a-zA-Z0-9][a-zA-Z0-9._-]*$') { $slug = "mod-" + [Guid]::NewGuid().ToString("N").Substring(0, 8) }
    return $slug
}

function Test-FLModFolder {
    param([string]$Path)
    foreach ($leaf in @("overlay.json", "script.lua", "plugin.dll", "mod.json")) {
        if (Test-Path -LiteralPath (Join-Path $Path $leaf) -PathType Leaf) { return $true }
    }
    return (@(Get-ChildItem -Path (Join-Path $Path "scripts\*.lua"), (Join-Path $Path "plugins\*.dll") -File -ErrorAction SilentlyContinue).Count -gt 0)
}

function Set-FLModOrder {
    param([string[]]$Folders)
    $path = Join-Path $Here "data\yw2-recomp\mods-state.json"
    $state = Read-FLJson $path
    if (-not $state) { $state = [pscustomobject]@{} }
    $state | Add-Member NoteProperty order @($Folders | Select-Object -Unique) -Force
    New-Item -ItemType Directory -Path (Split-Path $path) -Force | Out-Null
    $disabled = @((Read-FLPrefs).disabled_mods)
    $state | Add-Member NoteProperty enabled @($Folders | Where-Object { $disabled -notcontains $_ }) -Force
    $state | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $path -Encoding UTF8
}

# Validate and stage every constituent before publishing. Never overwrite installs.
function Install-FLModZip {
    param([Parameter(Mandatory = $true)][string]$ZipPath, [string]$DefaultName = "")
    $stage = Join-Path ([IO.Path]::GetTempPath()) ("fl-mod-" + [guid]::NewGuid().ToString("N"))
    $root = Join-Path $Here "data\yw2-recomp\mods\fantasylife"
    $published = @(); $zip = $null
    $prefsPath = Get-FLPrefsPath
    $prefsBefore = $null
    $statePath = Join-Path $Here "data\yw2-recomp\mods-state.json"
    $stateBefore = $null
    try {
        if (-not (Test-Path -LiteralPath $ZipPath -PathType Leaf)) { throw "ZIP not found." }
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $zip = [IO.Compression.ZipFile]::OpenRead($ZipPath)
        New-Item -ItemType Directory -Path $stage -Force | Out-Null
        $stageFull = [IO.Path]::GetFullPath($stage).TrimEnd('\') + '\'
        $total = [long]0
        foreach ($entry in $zip.Entries) {
            $rel = $entry.FullName.Replace('\','/')
            if ($rel -match '(^/|:|(^|/)\.\.?(/|$)|[<>|?*])' -or $rel -match '(^|/)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\.|/|$)' -or $rel -match '[. ](/|$)') { throw "Unsafe ZIP path: $rel" }
            if (($entry.ExternalAttributes -band 0xA0000000) -eq 0xA0000000) { throw "Links are not supported in mod archives." }
            $total += $entry.Length
            if ($total -gt 2GB -or $zip.Entries.Count -gt 20000) { throw "Archive exceeds the 2 GB / 20,000 file limit." }
            if ($rel.EndsWith('/')) { continue }
            $ext = [IO.Path]::GetExtension($rel).ToLowerInvariant()
            if ($ext -in @('.exe','.bat','.cmd','.ps1','.psm1','.psd1','.vbs','.vbe','.js','.jse','.wsf','.wsh','.msi','.msp','.scr','.com','.pif','.reg','.lnk','.hta','.cpl','.jar')) { throw "Unsupported executable file: $rel" }
            if ($ext -eq '.dll' -and $rel -notmatch '(^|/)(plugin\.dll|plugins/[^/]+\.dll)$') { throw "DLLs must be plugin.dll or plugins/*.dll." }
            $target = [IO.Path]::GetFullPath((Join-Path $stage $rel))
            if (-not $target.StartsWith($stageFull, [StringComparison]::OrdinalIgnoreCase)) { throw "Unsafe ZIP path." }
            if (Test-Path -LiteralPath $target) { throw "Duplicate ZIP entry: $rel" }
            New-Item -ItemType Directory -Path (Split-Path $target) -Force | Out-Null
            [IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $target)
        }
        $zip.Dispose(); $zip = $null
        $base = $stage
        while (-not (Test-FLModFolder $base) -and -not (Test-Path -LiteralPath (Join-Path $base 'modpack.json'))) {
            $dirs = @(Get-ChildItem -LiteralPath $base -Directory)
            if ($dirs.Count -ne 1) { break }
            $base = $dirs[0].FullName
        }
        $manifestPath = Join-Path $base 'modpack.json'
        $sources = @()
        $isPack = Test-Path -LiteralPath $manifestPath
        if ($isPack) {
            $pack = Read-FLJson $manifestPath
            if (-not $pack -or $pack.format -ne 'fl-modpack-v1' -or $pack.mods -isnot [array] -or -not $pack.mods.Count) { throw "Invalid fl-modpack-v1 manifest." }
            if (@($pack.mods | Select-Object -Unique).Count -ne $pack.mods.Count) { throw "Duplicate folder in modpack." }
            foreach ($folder in $pack.mods) {
                if ($folder -isnot [string] -or $folder -notmatch '^[a-zA-Z0-9][a-zA-Z0-9._-]*$') { throw "Invalid modpack folder." }
                $sources += Get-Item -LiteralPath (Join-Path $base $folder)
            }
        } elseif (Test-FLModFolder $base) { $sources = @(Get-Item -LiteralPath $base) }
        else { $sources = @(Get-ChildItem -LiteralPath $base -Directory | Where-Object { Test-FLModFolder $_.FullName } | Sort-Object Name) }
        if (-not $sources.Count) { throw "No overlay, Lua script, plugin or source mod found in this ZIP." }
        $plan = @()
        New-Item -ItemType Directory -Path $root -Force | Out-Null
        foreach ($source in $sources) {
            if (-not (Test-FLModFolder $source.FullName)) { throw "Invalid mod folder: $($source.Name)" }
            foreach ($metaFile in @('overlay.json','mod.json')) {
                $mp = Join-Path $source.FullName $metaFile
                if ((Test-Path -LiteralPath $mp) -and -not (Read-FLJson $mp)) { throw "Unreadable $metaFile in $($source.Name)." }
            }
            $meta = Read-FLJson (Join-Path $source.FullName 'overlay.json')
            if (-not $meta) { $meta = Read-FLJson (Join-Path $source.FullName 'mod.json') }
            $name = if ($meta -and $meta.name) { [string]$meta.name } elseif ($DefaultName -and $sources.Count -eq 1) { $DefaultName } elseif ($source.FullName -eq $stage) { [IO.Path]::GetFileNameWithoutExtension($ZipPath) } else { $source.Name }
            $slug = if ($isPack -or $sources.Count -gt 1) { ConvertTo-FLModSlug $source.Name } else { ConvertTo-FLModSlug $name }
            $folder = $slug; $n = 2
            while ((Test-Path -LiteralPath (Join-Path $root $folder)) -or @($plan | Where-Object { $_.Folder -eq $folder }).Count) { $folder = "$slug-$n"; $n++ }
            $plan += [pscustomobject]@{ Source = $source.FullName; Folder = $folder; Name = $name }
        }
        if (Test-Path -LiteralPath $prefsPath) { $prefsBefore = [IO.File]::ReadAllText($prefsPath) }
        if (Test-Path -LiteralPath $statePath) { $stateBefore = [IO.File]::ReadAllText($statePath) }
        $info = Get-FLMods -Config (Get-FLConfig) -LocalVersion (Get-FLLocalVersion -Config (Get-FLConfig))
        foreach ($item in $plan) {
            $dest = [IO.Path]::GetFullPath((Join-Path $root $item.Folder))
            if (-not $dest.StartsWith([IO.Path]::GetFullPath($root).TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) { throw "Unsafe destination." }
            $published += $item.Folder
            Copy-Item -LiteralPath $item.Source -Destination $dest -Recurse
            if ((Test-Path -LiteralPath (Join-Path $dest 'mod.json')) -and -not (Test-Path -LiteralPath (Join-Path $dest 'overlay.json'))) {
                $tool=Get-FLModToolchain
                if ($tool) {
                Initialize-FLModArchive -Toolchain $tool
                $built=Join-Path $stage ('built-'+$item.Folder)
                [void](Invoke-FLPythonTool $tool.Python @('-I',$tool.FlMod,'build',$tool.Archive,$dest,$built))
                Copy-Item -Path (Join-Path $built '*') -Destination $dest -Recurse -Force
                }
            }
        }
        $prefs = Read-FLPrefs
        $prefs.user_mods = @(@($prefs.user_mods) + $published | Select-Object -Unique)
        $prefs.disabled_mods = @($prefs.disabled_mods | Where-Object { $published -notcontains $_ })
        Write-FLPrefs -Path $prefsPath -Prefs $prefs
        Set-FLModOrder (@($info.Mods | ForEach-Object { $_.Folder }) + $published)
        return [pscustomobject]@{ Ok = $true; Message = "Installed $($published.Count) mod(s): $($published -join ', ')."; Folders = $published; Folder = $published[0]; Name = $plan[0].Name }
    } catch {
        foreach ($folder in $published) {
            $dest = [IO.Path]::GetFullPath((Join-Path $root $folder))
            if ($dest.StartsWith([IO.Path]::GetFullPath($root).TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) { Remove-Item -LiteralPath $dest -Recurse -Force }
        }
        if ($published.Count) {
            if ($null -ne $prefsBefore) { [IO.File]::WriteAllText($prefsPath, $prefsBefore) } else { Remove-Item -LiteralPath $prefsPath -Force -ErrorAction SilentlyContinue }
            if ($null -ne $stateBefore) { [IO.File]::WriteAllText($statePath, $stateBefore) } else { Remove-Item -LiteralPath $statePath -Force -ErrorAction SilentlyContinue }
        }
        return [pscustomobject]@{ Ok = $false; Message = "Install failed: $($_.Exception.Message)"; Folders = @(); Folder = ""; Name = "" }
    } finally {
        if ($zip) { $zip.Dispose() }
        if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
    }
}
function Build-FLMergedStack {
    param([string]$OutputDirectory = "", [object[]]$Mods)
    $tool = Get-FLModToolchain
    if (-not $tool) { throw "Install Python 3.10 or newer to build source mods." }
    Initialize-FLModArchive -Toolchain $tool
    if (-not $Mods) { $Mods = @((Get-FLMods -Config (Get-FLConfig) -LocalVersion (Get-FLLocalVersion -Config (Get-FLConfig))).Mods | Where-Object Enabled) }
    $sources = @($Mods | Where-Object { Test-Path -LiteralPath (Join-Path $_.Path 'mod.json') })
    if ($sources.Count -lt 2) { throw "Enable at least two source mods containing mod.json." }
    if (-not $OutputDirectory) { $OutputDirectory = Join-Path $Here ("data\yw2-recomp\mods\fantasylife\merged-" + [guid]::NewGuid().ToString('N').Substring(0,8)) }
    if (Test-Path -LiteralPath $OutputDirectory) { throw "Merge output must be a new folder." }
    $argsList = @('-I', $tool.FlMod, 'build-stack', $tool.Archive, $OutputDirectory) + @($sources | ForEach-Object { $_.Path })
    $psi = New-Object Diagnostics.ProcessStartInfo
    $psi.FileName = $tool.Python
    $psi.Arguments = ($argsList | ForEach-Object { '"' + $_.Replace('"','\"') + '"' }) -join ' '
    $psi.UseShellExecute = $false; $psi.CreateNoWindow = $true
    $psi.RedirectStandardOutput = $true; $psi.RedirectStandardError = $true
    $proc = [Diagnostics.Process]::Start($psi)
    $stdoutTask = $proc.StandardOutput.ReadToEndAsync()
    $stderrTask = $proc.StandardError.ReadToEndAsync()
    $proc.WaitForExit()
    $stdout = $stdoutTask.Result; $stderr = $stderrTask.Result
    $exitCode = $proc.ExitCode; $proc.Dispose()
    if ($exitCode -ne 0 -or -not (Test-Path -LiteralPath (Join-Path $OutputDirectory 'overlay.json'))) { throw "Merge failed: $stderr $stdout" }
    return $OutputDirectory
}

function Export-FLModpackZip {
    param([Parameter(Mandatory = $true)][string]$OutputPath, [switch]$MergeSources)
    $mods = @((Get-FLMods -Config (Get-FLConfig) -LocalVersion (Get-FLLocalVersion -Config (Get-FLConfig))).Mods | Where-Object { $_.Enabled -and (Test-FLModFolder $_.Path) })
    if (-not $mods.Count) { throw "Enable at least one installed mod to export." }
    if (Test-Path -LiteralPath $OutputPath) { throw "Choose a new ZIP filename; the existing file was preserved." }
    $tmp = Join-Path ([IO.Path]::GetTempPath()) ("fl-pack-" + [guid]::NewGuid().ToString('N'))
    try {
        New-Item -ItemType Directory -Path $tmp | Out-Null
        $folders = @()
        if ($MergeSources) {
            $mergedFolder = "merged-stack"
            while (@($mods | Where-Object { $_.Folder -eq $mergedFolder }).Count) { $mergedFolder += "-merged" }
            $merged = Join-Path $tmp $mergedFolder
            [void](Build-FLMergedStack -OutputDirectory $merged -Mods $mods)
            $folders += $mergedFolder
        }
        foreach ($mod in $mods) {
            if (($mod.Path | Get-Item -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Cannot export filesystem links." }
            if (@(Get-ChildItem -LiteralPath $mod.Path -Recurse -Force | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }).Count) { throw "Cannot export a mod containing filesystem links." }
            if ($MergeSources -and (Test-Path -LiteralPath (Join-Path $mod.Path 'mod.json'))) {
                # Preserve script/plugin assets, but do not load their old data overlays.
                if ($mod.Kind -match 'Lua|Plugin') {
                    $dest = Join-Path $tmp $mod.Folder
                    Copy-Item -LiteralPath $mod.Path -Destination $dest -Recurse
                    $oldOverlay = Join-Path $dest 'overlay.json'
                    if (Test-Path -LiteralPath $oldOverlay) { Remove-Item -LiteralPath $oldOverlay }
                    $folders += $mod.Folder
                }
                continue
            }
            Copy-Item -LiteralPath $mod.Path -Destination (Join-Path $tmp $mod.Folder) -Recurse
            $folders += $mod.Folder
        }
        [ordered]@{ format = 'fl-modpack-v1'; name = [IO.Path]::GetFileNameWithoutExtension($OutputPath); created_at = [DateTime]::UtcNow.ToString('o'); mods = @($folders) } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $tmp 'modpack.json') -Encoding UTF8
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $zip = [IO.Compression.ZipFile]::Open([IO.Path]::GetFullPath($OutputPath), 'Create')
        try {
            foreach ($file in Get-ChildItem -LiteralPath $tmp -Recurse -File -Force) {
                $entryName = $file.FullName.Substring($tmp.TrimEnd('\').Length + 1).Replace('\','/')
                [void][IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $file.FullName, $entryName)
            }
        } finally { $zip.Dispose() }
        return [pscustomobject]@{ Ok = $true; Message = "Exported $($folders.Count) mods to $OutputPath"; Path = $OutputPath }
    } finally {
        if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Recurse -Force }
    }
}

function Get-FLGameBananaGameId {
    $value = $env:FL_GAMEBANANA_GAME_ID
    if (-not $value) { $value = (Read-FLKeyValueFile (Join-Path $Here 'update-config.env'))['FL_GAMEBANANA_GAME_ID'] }
    if (-not $value) { return 22668 }
    $id = 0
    if (-not [int]::TryParse($value, [ref]$id) -or $id -le 0) { throw "FL_GAMEBANANA_GAME_ID must be a positive number." }
    return $id
}

function Assert-FLHttpsUrl {
    param([string]$Url)
    $uri = $null
    if (-not [uri]::TryCreate($Url, [UriKind]::Absolute, [ref]$uri) -or $uri.Scheme -ne 'https' -or $uri.UserInfo) { throw "Only HTTPS URLs are supported." }
}

# Follow redirects explicitly so a redirect cannot downgrade to HTTP.
function Invoke-FLGameBananaRequest {
    param([string]$Url, [string]$OutFile = "")
    Enable-FLTls12
    try {
        for ($redirect = 0; $redirect -lt 6; $redirect++) {
            Assert-FLHttpsUrl $Url
            $response = $null
            try {
                $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 15 -MaximumRedirection 0 -ErrorAction Stop
            } catch {
                if ($_.Exception.Response -and [int]$_.Exception.Response.StatusCode -in @(301,302,303,307,308)) {
                    $Url = ([uri]::new([uri]$Url, [string]$_.Exception.Response.Headers['Location'])).AbsoluteUri
                    continue
                }
                throw
            }
            if ([int]$response.StatusCode -in @(301,302,303,307,308)) {
                $Url = ([uri]::new([uri]$Url, [string]$response.Headers['Location'])).AbsoluteUri
                continue
            }
            if ($OutFile) {
                $stream = [IO.File]::Create($OutFile)
                try { $response.RawContentStream.Position = 0; $response.RawContentStream.CopyTo($stream) } finally { $stream.Dispose() }
                return
            }
            return ($response.Content | ConvertFrom-Json)
        }
        throw "Too many redirects."
    } catch { throw "GameBanana is unavailable (offline, timeout, or invalid response). $($_.Exception.Message)" }
}

function Search-FLGameBananaMods {
    param([int]$GameId = (Get-FLGameBananaGameId), [ValidateRange(1,100000)][int]$Page = 1, [string]$Search = "", [string]$Category = "")
    if ($GameId -le 0) { throw "Invalid GameBanana game ID." }
    $url = "https://gamebanana.com/apiv11/Mod/Index?_aFilters%5BGeneric_Game%5D=$GameId&_nPerpage=20&_nPage=$Page"
    if ($Search) { $url += '&_aFilters%5B_sName%5D=' + [uri]::EscapeDataString($Search) }
    $data = Invoke-FLGameBananaRequest $url
    $installed = @((Get-FLMods -Config (Get-FLConfig) -LocalVersion (Get-FLLocalVersion -Config (Get-FLConfig))).Mods)
    foreach ($r in @($data._aRecords)) {
        if (-not $r) { continue }
        if ($Category -and $r._aRootCategory._sName -notlike "*$Category*") { continue }
        $match = @($installed | Where-Object { $_.GameBananaId -eq $r._idRow }) | Select-Object -First 1
        [pscustomobject]@{ Id = $r._idRow; Name = $r._sName; Category = $r._aRootCategory._sName; Submitter = $r._aSubmitter._sName; Likes = $r._nLikeCount; Views = $r._nViewCount; ProfileUrl = $r._sProfileUrl; DateUpdated = $r._tsDateUpdated; InstalledFolder = $(if ($match) { $match.Folder } else { "" }) }
    }
}

function Get-FLGameBananaModFiles {
    param([Parameter(Mandatory = $true)][ValidateRange(1,2147483647)][int]$ModId)
    $data = Invoke-FLGameBananaRequest "https://gamebanana.com/apiv11/Mod/$ModId/ProfilePage"
    foreach ($f in @($data._aFiles)) {
        try { Assert-FLHttpsUrl $f._sDownloadUrl } catch { continue }
        [pscustomobject]@{ Id = $f._idRow; Name = $f._sFile; Description = $f._sDescription; DownloadUrl = $f._sDownloadUrl; Size = $f._nFilesize; DateAdded = $f._tsDateAdded }
    }
}

function Install-FLGameBananaMod {
    param([Parameter(Mandatory = $true)]$Mod, [Parameter(Mandatory = $true)]$File)
    $tmp = Join-Path ([IO.Path]::GetTempPath()) ("fl-gb-" + [guid]::NewGuid().ToString('N') + '.zip')
    try {
        Assert-FLHttpsUrl $File.DownloadUrl
        Invoke-FLGameBananaRequest -Url $File.DownloadUrl -OutFile $tmp
        $result = Install-FLModZip -ZipPath $tmp -DefaultName $Mod.Name
        if (-not $result.Ok) { return $result }
        foreach ($folder in $result.Folders) {
            [ordered]@{ mod_id = $Mod.Id; mod_name = $Mod.Name; submitter = $Mod.Submitter; file_id = $File.Id; file_name = $File.Name; description = $File.Description; installed_at = [DateTime]::UtcNow.ToString('o') } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Here "data\yw2-recomp\mods\fantasylife\$folder\gamebanana.json") -Encoding UTF8
        }
        # Retire previous user installs only after the replacement succeeds.
        $previous = @((Get-FLMods -Config (Get-FLConfig) -LocalVersion (Get-FLLocalVersion -Config (Get-FLConfig))).Mods | Where-Object { $_.GameBananaId -eq $Mod.Id -and $_.Removable -and $result.Folders -notcontains $_.Folder })
        foreach ($old in $previous) { [void](Remove-FLMod -Folder $old.Folder) }
        return $result
    } catch { return [pscustomobject]@{ Ok = $false; Message = $_.Exception.Message; Folders = @() } }
    finally { if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Force } }
}
# Uninstall a mod folder (user-installed or, with -Force, any non-running one).
# Core/shipped mods are refused unless -Force; the folder must live under
# data\yw2-recomp\mods\fantasylife. Prefs (disabled_mods/user_mods) are cleaned.
function Remove-FLMod {
    param(
        [Parameter(Mandatory = $true)][string]$Folder,
        [switch]$Force
    )
    if ($Folder -notmatch '^[a-zA-Z0-9][a-zA-Z0-9._-]*$') { throw "Invalid mod folder name: $Folder" }
    $prefsPath = Get-FLPrefsPath
    $prefs = Read-FLPrefs -Path $prefsPath
    $modRoot = Join-Path $Here "data\yw2-recomp\mods\fantasylife"
    $path = Join-Path $modRoot $Folder
    if (-not (Test-Path -LiteralPath $path -PathType Container)) { throw "Mod folder not found: $Folder" }
    $full = [IO.Path]::GetFullPath($path)
    $rootFull = [IO.Path]::GetFullPath($modRoot).TrimEnd('\') + '\'
    if (-not $full.StartsWith($rootFull, [StringComparison]::OrdinalIgnoreCase)) { throw "Refusing to delete outside the mods folder." }
    $isUser = @($prefs.user_mods) -contains $Folder
    if (-not $isUser -and -not $Force) {
        $info = Get-FLMods -Config (Get-FLConfig) -LocalVersion (Get-FLLocalVersion -Config (Get-FLConfig)) -LocalVersion (Get-FLLocalVersion -Config (Get-FLConfig))
        $mod = @($info.Mods | Where-Object { $_.Folder -eq $Folder }) | Select-Object -First 1
        if ($mod -and -not $mod.Removable) { throw "'$Folder' ships with this build and cannot be uninstalled. Toggle it off instead." }
    }
    Remove-Item -LiteralPath $full -Recurse -Force
    $prefs.user_mods = @($prefs.user_mods | Where-Object { $_ -ne $Folder })
    $prefs.disabled_mods = @($prefs.disabled_mods | Where-Object { $_ -ne $Folder })
    $state = Read-FLJson (Join-Path $Here "data\yw2-recomp\mods-state.json")
    if ($state -and $state.order) { Set-FLModOrder @($state.order | Where-Object { $_ -ne $Folder }) }
    Write-FLPrefs -Path $prefsPath -Prefs $prefs
    return [pscustomobject]@{ Ok = $true; Message = "Uninstalled '$Folder'."; Folder = $Folder }
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
        foreach ($sub in @("bin", "lib", "data\yw2-recomp\shader-cache-v3", "contrib", "tools")) {
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
    $vars["FL_STATE_DIR"] = $saveDir
    $vars["FL_DATA_DIR"] = Join-Path $Here "data\yw2-recomp"
    $vars["FL_WIDESCREEN"] = "0"
    $vars["FL_INTERP"] = "0"
    $vars["FL_SCALE"] = "1"
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

. (Join-Path $Here 'bin\launcher\setup.ps1')
. (Join-Path $Here 'bin\launcher\controls.ps1')

if ($LibraryOnly) { return }

# ---------------------------------------------------------------------------
# Launcher window (default for the desktop shortcut and play.bat without arguments)
# ---------------------------------------------------------------------------

$Config = Get-FLConfig
$ActionFlags = $Direct -or $Vanilla -or $Launcher -or $NoLaunch -or $SetupFirewall
$WindowMode = $Window -or $Preview -or $PreviewModManager -or $Screenshot -or (-not $ActionFlags -and $env:FL_DIRECT -ne "1" -and [Environment]::UserInteractive)

if ($WindowMode) {
    $WindowScript = Join-Path $Here "bin\launcher\window.ps1"
    $windowError = $null
    if (Test-Path -LiteralPath $WindowScript -PathType Leaf) {
        try {
            . $WindowScript
            $code = Show-FLLauncherWindow -Config $Config -InitialSave $Save -NoUpdateCheck:$NoUpdate -NoDlc:$NoDlc `
                -NoFirewall:$NoFirewall -AfterUpdate $AfterUpdate -Preview:($Preview -or $PreviewModManager) -PreviewModManager:$PreviewModManager -Screenshot $Screenshot
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

# Firewall setup is available only through the optional launcher button.

# 6. Mods: -Vanilla = none; an FL_MOD_DIRS set in the calling environment wins;
#    otherwise the enabled subset of the build's mod list (version.json /
#    test-version.json), honouring disabled_mods from launcher.json.
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
    $stack = Test-FLModStack -ModInfo $ModInfo
    foreach ($mod in $stack.Missing) {
        throw "Enabled mod '$($mod.Folder)' is missing. Update the normal game before playing, or disable the mod."
    }
    if ($stack.Conflicts.Count -gt 0) {
        $c = $stack.Conflicts[0]
        $extra = if ($stack.Conflicts.Count -gt 1) { " (+$(($stack.Conflicts.Count - 1)) more)" } else { "" }
        $labelA = if ($c.NameA -eq $c.NameB) { $c.FolderA } else { $c.NameA }
        $labelB = if ($c.NameA -eq $c.NameB) { $c.FolderB } else { $c.NameB }
        throw "Mod conflict on resource $($c.Id): '$labelA' and '$labelB'$extra. Disable one or use a merged stack."
    }
    $off = @($ModInfo.Mods | Where-Object { -not $_.Enabled } | ForEach-Object { $_.Folder })
    if ($off.Count -gt 0) { Write-Host "[Mods] Disabled: $($off -join ', ')" -ForegroundColor DarkGray }
    $ModDirs = @($stack.Enabled | Where-Object { -not $_.SourceOnly } | ForEach-Object { $_.Path })
    if ($ModDirs.Count -gt 0) {
        Write-Host ("[Mods] {0}" -f (@($stack.Enabled | Where-Object { -not $_.SourceOnly } | ForEach-Object { $_.Name }) -join ", ")) -ForegroundColor Cyan
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
