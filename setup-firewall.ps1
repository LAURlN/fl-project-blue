[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string[]]$InstallDir = @(),
    [switch]$Remove,
    [switch]$Check
)

$ErrorActionPreference = "Stop"

# This file is both a runnable script and a small library. The launchers
# (play.ps1) and installers dot-source it to reuse the status/elevation helpers.
# When dot-sourced the main block at the bottom is skipped.
$script:FantasyLifeFirewallGroup = "Fantasy Life PC"
$script:FantasyLifeFirewallScriptPath = $PSCommandPath
$script:FantasyLifeHamachiRange = "25.0.0.0/8"
$script:FantasyLifeRadminRange = "26.0.0.0/8"

# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------

function Test-FantasyLifeIsElevated {
    try {
        $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
        $principal = New-Object Security.Principal.WindowsPrincipal($identity)
        return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    } catch {
        return $false
    }
}

function Test-FantasyLifeInteractiveConsole {
    try {
        if ([Console]::IsInputRedirected) { return $false }
        if (-not [Environment]::UserInteractive) { return $false }
        return $true
    } catch {
        return $false
    }
}

function Get-FantasyLifeShortHash {
    param([Parameter(Mandatory = $true)][string]$Text)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($Text.ToLowerInvariant())
        $hash = [System.BitConverter]::ToString($sha.ComputeHash($bytes)).Replace("-", "")
        return $hash.Substring(0, 8).ToLowerInvariant()
    } finally {
        $sha.Dispose()
    }
}

function Test-FantasyLifeSamePath {
    param([string]$Left, [string]$Right)
    if (-not $Left -or -not $Right) { return $false }
    return [string]::Equals($Left.Trim(), $Right.Trim(), [System.StringComparison]::OrdinalIgnoreCase)
}

function Write-FantasyLifeFirewallLine {
    param([string]$Text, [string]$Color = "Gray")
    Write-Host $Text -ForegroundColor $Color
}

# ---------------------------------------------------------------------------
# Install discovery
# ---------------------------------------------------------------------------

function Get-FantasyLifeInstallInfo {
    param(
        [string[]]$InstallDir = @(),
        [switch]$AllowMissing
    )

    # `powershell -File ... -InstallDir "a,b"` binds the whole list as one
    # string, so expand comma-separated values unless that string is a real path.
    $rawDirs = @()
    foreach ($rawDir in @($InstallDir)) {
        if (-not $rawDir) { continue }
        $text = [string]$rawDir
        if ($text -match "," -and -not (Test-Path -LiteralPath $text)) {
            $rawDirs += @($text -split "," | ForEach-Object { $_.Trim().Trim('"') } | Where-Object { $_ })
        } else {
            $rawDirs += $text
        }
    }

    $installs = @()
    $seen = @{}
    foreach ($rawDir in $rawDirs) {
        if (-not $rawDir) { continue }
        $expanded = [Environment]::ExpandEnvironmentVariables($rawDir.Trim().Trim('"'))
        if (-not $expanded) { continue }
        $full = [System.IO.Path]::GetFullPath($expanded).TrimEnd("\")
        $key = $full.ToLowerInvariant()
        if ($seen.ContainsKey($key)) { continue }
        $seen[$key] = $true

        $exe = Join-Path $full "bin\fl_eur.exe"
        if (-not $AllowMissing) {
            if (-not (Test-Path -LiteralPath $full -PathType Container)) {
                throw "Install directory not found: $full"
            }
            if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
                throw "fl_eur.exe not found in $full\bin"
            }
        }

        $label = Split-Path -Leaf $full
        if (-not $label) { $label = $full }
        $hash = Get-FantasyLifeShortHash $full
        $installs += [pscustomobject]@{
            InstallDir = $full
            Exe        = $exe
            Relay      = (Join-Path $full "bin\clockwork-relay.exe")
            Label      = $label
            Key        = $hash
            RulePrefix = "FLPC-$hash"
        }
    }
    return $installs
}

# ---------------------------------------------------------------------------
# Adapter detection
# ---------------------------------------------------------------------------

function Select-FantasyLifeZeroTierAdapters {
    param([object[]]$Adapters = @())
    $match = @($Adapters | Where-Object {
        if (-not $_) { return $false }
        $name = [string]$_.Name
        $desc = [string]$_.InterfaceDescription
        return (($desc -match "(?i)ZeroTier") -or ($name -match "(?i)ZeroTier"))
    })
    if ($match.Count -eq 0) { return @() }
    return @($match | Sort-Object Name)
}

function Get-FantasyLifeZeroTierAdapters {
    try {
        return @(Select-FantasyLifeZeroTierAdapters -Adapters @(Get-NetAdapter -ErrorAction Stop))
    } catch {
        return @()
    }
}

# ---------------------------------------------------------------------------
# Firewall snapshot (read-only; works without admin)
# ---------------------------------------------------------------------------

function ConvertFrom-FantasyLifeProfileMask {
    param($Mask)
    $value = [int64]$Mask
    if ($value -eq 0 -or $value -lt 0 -or $value -ge 2147483647) { return @("Any") }
    $profiles = @()
    if (($value -band 1) -ne 0) { $profiles += "Domain" }
    if (($value -band 2) -ne 0) { $profiles += "Private" }
    if (($value -band 4) -ne 0) { $profiles += "Public" }
    if ($profiles.Count -eq 0) { return @("Any") }
    return $profiles
}

function ConvertFrom-FantasyLifeProfileText {
    param([string]$Text)
    if (-not $Text) { return @("Any") }
    $profiles = @($Text -split "\s*,\s*" | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    if ($profiles.Count -eq 0) { return @("Any") }
    if (@($profiles | Where-Object { $_ -match "^(?i)any$" }).Count -gt 0) { return @("Any") }
    return $profiles
}

function New-FantasyLifeExistingRuleRecord {
    param(
        $Name,
        $DisplayName,
        $Group,
        $Enabled,
        $Direction,
        $Action,
        $Profiles,
        $Program,
        $RemoteAddress,
        $Protocol,
        $LocalPort,
        $InterfaceAlias,
        $Identity,
        $InterfaceAliasKnown = $true
    )

    $profileList = @($Profiles | ForEach-Object { [string]$_ } | Where-Object { $_ })
    if ($profileList.Count -eq 0) { $profileList = @("Any") }

    $remote = @($RemoteAddress | ForEach-Object { [string]$_ } | Where-Object { $_ })
    if ($remote.Count -eq 0) { $remote = @("Any") }

    $ports = @($LocalPort | ForEach-Object { [string]$_ } | Where-Object { $_ })
    if ($ports.Count -eq 0) { $ports = @("Any") }

    $ifaces = @($InterfaceAlias | ForEach-Object { [string]$_ } | Where-Object { $_ })
    if ($ifaces.Count -eq 0) { $ifaces = @("Any") }

    return [pscustomobject]@{
        Name               = [string]$Name
        DisplayName        = [string]$DisplayName
        Group              = [string]$Group
        Enabled            = [bool]$Enabled
        Direction          = [string]$Direction
        Action             = [string]$Action
        Profiles           = $profileList
        Program            = [string]$Program
        RemoteAddress      = $remote
        Protocol           = $(if ($Protocol) { [string]$Protocol } else { "Any" })
        LocalPort          = $ports
        InterfaceAlias     = $ifaces
        Identity           = [string]$Identity
        InterfaceAliasKnown = [bool]$InterfaceAliasKnown
    }
}

function ConvertFrom-FantasyLifeProtocolNumber {
    param($Protocol)
    switch ([int64]$Protocol) {
        1   { return "ICMPv4" }
        6   { return "TCP" }
        17  { return "UDP" }
        58  { return "ICMPv6" }
        256 { return "Any" }
        default { return ("Protocol" + [string]$Protocol) }
    }
}

function Get-FantasyLifeBlockRuleIdentity {
    param([string]$DisplayName, [string]$Program)
    # COM does not expose the cmdlet rule identity, so resolve it only when a
    # block rule actually exists (rare, and not performance-sensitive).
    try {
        $candidates = @(Get-NetFirewallRule -Direction Inbound -Action Block -DisplayName $DisplayName -ErrorAction SilentlyContinue)
        foreach ($candidate in $candidates) {
            $app = $candidate | Get-NetFirewallApplicationFilter -ErrorAction SilentlyContinue
            if ($app -and (Test-FantasyLifeSamePath $app.Program $Program)) {
                return [string]$candidate.Name
            }
        }
    } catch {}
    return ""
}

function Get-FantasyLifeFirewallSnapshot {
    param([string[]]$Program = @())

    $programSet = @{}
    foreach ($p in @($Program)) {
        if ($p) { $programSet[[string]$p.ToLowerInvariant()] = $true }
    }
    if ($programSet.Count -eq 0) { return @() }

    $records = @()

    # The COM policy object is fast (milliseconds) and, unlike the bulk filter
    # cmdlets, includes user-created rules without admin rights. It exposes the
    # display name (not the cmdlet's internal Name) and no interface alias.
    $policy = $null
    try { $policy = New-Object -ComObject HNetCfg.FwPolicy2 } catch { $policy = $null }

    if ($policy) {
        foreach ($rule in @($policy.Rules)) {
            $app = [string]$rule.ApplicationName
            if (-not $app) { continue }
            if (-not $programSet.ContainsKey($app.ToLowerInvariant())) { continue }

            $enabled = [bool]$rule.Enabled
            $directionValue = [int64]$rule.Direction
            if ($directionValue -eq 1) { $direction = "Inbound" }
            elseif ($directionValue -eq 2) { $direction = "Outbound" }
            else { $direction = "Direction$directionValue" }

            $actionValue = [int64]$rule.Action
            if ($actionValue -eq 1) { $action = "Allow" }
            elseif ($actionValue -eq 0) { $action = "Block" }
            else { $action = "Action$actionValue" }

            $remote = @([string]$rule.RemoteAddresses -split "\s*,\s*" | ForEach-Object {
                $value = $_.Trim()
                if ($value -eq "*") { "Any" } elseif ($value) { $value }
            })
            $ports = @([string]$rule.LocalPorts -split "\s*,\s*" | ForEach-Object {
                $value = $_.Trim()
                if ($value -eq "*") { "Any" } elseif ($value) { $value }
            })
            $display = [string]$rule.Name
            $identity = ""
            if ($action -eq "Block" -and $direction -eq "Inbound") {
                $identity = Get-FantasyLifeBlockRuleIdentity -DisplayName $display -Program $app
            }

            $records += New-FantasyLifeExistingRuleRecord `
                -Name $display `
                -DisplayName $display `
                -Group ([string]$rule.Grouping) `
                -Enabled $enabled `
                -Direction $direction `
                -Action $action `
                -Profiles (ConvertFrom-FantasyLifeProfileMask $rule.Profiles) `
                -Program $app `
                -RemoteAddress $remote `
                -Protocol (ConvertFrom-FantasyLifeProtocolNumber $rule.Protocol) `
                -LocalPort $ports `
                -InterfaceAlias @() `
                -Identity $identity `
                -InterfaceAliasKnown $false
        }
        return $records
    }

    # Fallback if the COM policy object is unavailable: the cmdlets still work,
    # but filter reads need one query per rule.
    $appMap = @{}
    foreach ($a in @(Get-NetFirewallApplicationFilter -ErrorAction SilentlyContinue)) {
        $id = [string]$a.InstanceID
        if ($id) { $appMap[$id] = [string]$a.Program }
    }
    foreach ($r in @(Get-NetFirewallRule -ErrorAction SilentlyContinue)) {
        $id = [string]$r.InstanceID
        if (-not $id) { continue }
        $prog = [string]$appMap[$id]
        if (-not $prog) { continue }
        if (-not $programSet.ContainsKey($prog.ToLowerInvariant())) { continue }
        $addressFilter = $r | Get-NetFirewallAddressFilter -ErrorAction SilentlyContinue
        $portFilter = $r | Get-NetFirewallPortFilter -ErrorAction SilentlyContinue
        $interfaceFilter = $r | Get-NetFirewallInterfaceFilter -ErrorAction SilentlyContinue
        $records += New-FantasyLifeExistingRuleRecord `
            -Name ([string]$r.Name) `
            -DisplayName ([string]$r.DisplayName) `
            -Group ([string]$r.Group) `
            -Enabled ($r.Enabled -eq $true -or [string]$r.Enabled -eq "True") `
            -Direction ([string]$r.Direction) `
            -Action ([string]$r.Action) `
            -Profiles (ConvertFrom-FantasyLifeProfileText ([string]$r.Profile)) `
            -Program $prog `
            -RemoteAddress $(if ($addressFilter) { @($addressFilter.RemoteAddress) } else { @() }) `
            -Protocol $(if ($portFilter) { [string]$portFilter.Protocol } else { "Any" }) `
            -LocalPort $(if ($portFilter) { @($portFilter.LocalPort) } else { @() }) `
            -InterfaceAlias $(if ($interfaceFilter) { @($interfaceFilter.InterfaceAlias) } else { @() }) `
            -Identity ([string]$r.Name) `
            -InterfaceAliasKnown $true
    }
    return $records
}

# ---------------------------------------------------------------------------
# Desired rules
# ---------------------------------------------------------------------------

function New-FantasyLifeDesiredRule {
    param(
        $Install,
        [string]$Name,
        [string]$DisplayName,
        [string]$Kind,
        [string[]]$Profiles,
        [string[]]$RemoteAddresses,
        [string[]]$InterfaceAliases,
        [string[]]$LocalPorts
    )

    return [pscustomobject]@{
        Name             = $Name
        DisplayName      = $DisplayName
        Kind             = $Kind
        Group            = $script:FantasyLifeFirewallGroup
        Description      = "Managed by Fantasy Life PC setup-firewall.ps1 for $($Install.InstallDir)"
        Program          = $Install.Exe
        Direction        = "Inbound"
        Action           = "Allow"
        Protocol         = "UDP"
        Profiles         = @($Profiles)
        RemoteAddresses  = @($RemoteAddresses)
        InterfaceAliases = @($InterfaceAliases)
        LocalPorts       = @($LocalPorts)
        InstallDir       = $Install.InstallDir
        InstallLabel     = $Install.Label
    }
}

function Get-FantasyLifeDesiredRules {
    param(
        [Parameter(Mandatory = $true)]$Install,
        [object[]]$Adapters = @()
    )

    $rules = @()
    $prefix = $Install.RulePrefix
    $label = $Install.Label
    $labelWithKey = "$label $($Install.Key)"

    # Normal LAN play. Domain is included because it is harmless and makes the
    # rule work on domain-joined machines too.
    $rules += New-FantasyLifeDesiredRule -Install $Install `
        -Name "$prefix-LAN" `
        -DisplayName "Fantasy Life PC - LAN ($labelWithKey)" `
        -Kind "LAN" `
        -Profiles @("Domain", "Private") `
        -RemoteAddresses @("LocalSubnet") `
        -InterfaceAliases @() `
        -LocalPorts @("Any")

    # Hamachi and Radmin VPN. Public is deliberately limited to their own fixed
    # ranges: never RFC1918 or Any, because cafés and other public Wi-Fi use
    # RFC1918 addresses too.
    $rules += New-FantasyLifeDesiredRule -Install $Install `
        -Name "$prefix-Hamachi" `
        -DisplayName "Fantasy Life PC - Hamachi ($labelWithKey)" `
        -Kind "Hamachi" `
        -Profiles @("Public") `
        -RemoteAddresses @($script:FantasyLifeHamachiRange) `
        -InterfaceAliases @() `
        -LocalPorts @("Any")

    $rules += New-FantasyLifeDesiredRule -Install $Install `
        -Name "$prefix-Radmin" `
        -DisplayName "Fantasy Life PC - Radmin VPN ($labelWithKey)" `
        -Kind "Radmin" `
        -Profiles @("Public") `
        -RemoteAddresses @($script:FantasyLifeRadminRange) `
        -InterfaceAliases @() `
        -LocalPorts @("Any")

    # ZeroTier uses custom address ranges, so scope the rule to the adapter
    # instead of guessing a range.
    $zeroTier = @(Select-FantasyLifeZeroTierAdapters -Adapters $Adapters)
    $index = 0
    foreach ($adapter in $zeroTier) {
        $index++
        $alias = [string]$adapter.Name
        $safeAlias = ($alias -replace "[^A-Za-z0-9]+", "-").Trim("-")
        if (-not $safeAlias) { $safeAlias = "adapter" }
        if ($safeAlias.Length -gt 24) { $safeAlias = $safeAlias.Substring(0, 24).Trim("-") }
        if (-not $safeAlias) { $safeAlias = "adapter" }
        $rules += New-FantasyLifeDesiredRule -Install $Install `
            -Name "$prefix-ZT$index-$safeAlias" `
            -DisplayName "Fantasy Life PC - ZeroTier $alias ($labelWithKey)" `
            -Kind "ZeroTier" `
            -Profiles @("Public", "Private") `
            -RemoteAddresses @() `
            -InterfaceAliases @($alias) `
            -LocalPorts @("Any")
    }

    # Optional relay hosting.
    if (Test-Path -LiteralPath $Install.Relay -PathType Leaf) {
        $rules += New-FantasyLifeDesiredRule -Install $Install `
            -Name "$prefix-Relay" `
            -DisplayName "Fantasy Life PC - Relay ($labelWithKey)" `
            -Kind "Relay" `
            -Profiles @("Domain", "Private") `
            -RemoteAddresses @() `
            -InterfaceAliases @() `
            -LocalPorts @("47830")
    }

    return $rules
}

# ---------------------------------------------------------------------------
# Address helpers (coverage checking)
# ---------------------------------------------------------------------------

function ConvertTo-FantasyLifeIPv4 {
    param([string]$Text)
    $value = $Text.Trim()
    if (-not $value) { return $null }
    $address = $null
    if (-not [System.Net.IPAddress]::TryParse($value, [ref]$address)) { return $null }
    if ($address.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork) { return $null }
    [uint64]$number = 0
    foreach ($b in $address.GetAddressBytes()) {
        $number = ($number * 256) + [uint64]$b
    }
    return $number
}

function Get-FantasyLifeMaskPrefix {
    param([uint64]$Mask)
    $prefix = 0
    for ($bit = 31; $bit -ge 0; $bit--) {
        if (($Mask -band ([uint64]1 -shl $bit)) -ne 0) { $prefix++ } else { break }
    }
    return $prefix
}

function ConvertTo-FantasyLifeAddressRange {
    param([string]$Text)
    $value = $Text.Trim()
    if (-not $value) { return $null }
    if ($value -eq "Any" -or $value -eq "*") { return [pscustomobject]@{ Any = $true; Start = [uint64]0; End = [uint64]4294967295 } }
    if ($value -eq "LocalSubnet") { return [pscustomobject]@{ LocalSubnet = $true; Start = [uint64]0; End = [uint64]0 } }

    if ($value -match "^(.+?)\s*-\s*(.+)$") {
        $first = ConvertTo-FantasyLifeIPv4 $Matches[1]
        $second = ConvertTo-FantasyLifeIPv4 $Matches[2]
        if ($null -eq $first -or $null -eq $second) { return $null }
        if ($first -le $second) { return [pscustomobject]@{ Start = $first; End = $second } }
        return [pscustomobject]@{ Start = $second; End = $first }
    }

    if ($value -match "^(.+)/(.+)$") {
        $ip = ConvertTo-FantasyLifeIPv4 $Matches[1]
        if ($null -eq $ip) { return $null }
        $maskText = $Matches[2].Trim()
        if ($maskText -match "^\d+$") {
            $prefix = [int]$maskText
        } else {
            $mask = ConvertTo-FantasyLifeIPv4 $maskText
            if ($null -eq $mask) { return $null }
            $prefix = Get-FantasyLifeMaskPrefix $mask
        }
        if ($prefix -lt 0 -or $prefix -gt 32) { return $null }
        [uint64]$hostBits = [uint64]([math]::Pow(2, 32 - $prefix) - 1)
        [uint64]$maskValue = [uint64]4294967295 - $hostBits
        $start = [uint64]($ip -band $maskValue)
        $end = [uint64]($start + $hostBits)
        return [pscustomobject]@{ Start = $start; End = $end }
    }

    $single = ConvertTo-FantasyLifeIPv4 $value
    if ($null -eq $single) { return $null }
    return [pscustomobject]@{ Start = $single; End = $single }
}

function Get-FantasyLifeAddressCanonical {
    param([string]$Text)
    $value = [string]$Text
    $value = $value.Trim()
    if (-not $value) { return "Any" }
    if ($value -eq "Any" -or $value -eq "*") { return "Any" }
    if ($value -eq "LocalSubnet") { return "LocalSubnet" }
    $range = ConvertTo-FantasyLifeAddressRange $value
    if ($range -and -not $range.Any -and -not $range.LocalSubnet) {
        return ("{0}-{1}" -f $range.Start, $range.End)
    }
    return $value.ToLowerInvariant()
}

function Test-FantasyLifeAddressCovers {
    param([string]$Existing, [string]$Desired)
    $left = ([string]$Existing).Trim()
    $right = ([string]$Desired).Trim()
    if (-not $left) { $left = "Any" }
    if (-not $right) { $right = "Any" }
    if ($left -eq "Any" -or $left -eq "*") { return $true }
    if ([string]::Equals($left, $right, [System.StringComparison]::OrdinalIgnoreCase)) { return $true }
    if ($right -eq "LocalSubnet") { return $false }
    if ($left -eq "LocalSubnet") { return $false }

    $existingRange = ConvertTo-FantasyLifeAddressRange $left
    $desiredRange = ConvertTo-FantasyLifeAddressRange $right
    if ($null -eq $existingRange -or $null -eq $desiredRange) { return $false }
    if ($existingRange.Any) { return $true }
    if ($desiredRange.Any -or $desiredRange.LocalSubnet) { return $false }
    return ($existingRange.Start -le $desiredRange.Start -and $existingRange.End -ge $desiredRange.End)
}

# ---------------------------------------------------------------------------
# Coverage / equality checks
# ---------------------------------------------------------------------------

function Test-FantasyLifeProfilesCover {
    param($Existing, $Desired)
    $have = @($Existing | ForEach-Object { ([string]$_).Trim().ToLowerInvariant() } | Where-Object { $_ })
    if ($have.Count -eq 0) { return $true }
    if ($have -contains "any") { return $true }
    foreach ($wanted in @($Desired)) {
        $token = ([string]$wanted).Trim().ToLowerInvariant()
        if (-not $token) { continue }
        if (-not ($have -contains $token)) { return $false }
    }
    return $true
}

function Test-FantasyLifeProfilesEqual {
    param($Left, $Right)
    $a = @($Left | ForEach-Object { ([string]$_).Trim().ToLowerInvariant() } | Where-Object { $_ } | Sort-Object -Unique)
    $b = @($Right | ForEach-Object { ([string]$_).Trim().ToLowerInvariant() } | Where-Object { $_ } | Sort-Object -Unique)
    if ($a.Count -ne $b.Count) { return $false }
    for ($i = 0; $i -lt $a.Count; $i++) {
        if ($a[$i] -ne $b[$i]) { return $false }
    }
    return $true
}

function Test-FantasyLifePortsCover {
    param($Existing, $Desired)
    $have = @($Existing | ForEach-Object { ([string]$_).Trim() } | Where-Object { $_ })
    if ($have.Count -eq 0) { $have = @("Any") }
    $wanted = @($Desired | ForEach-Object { ([string]$_).Trim() } | Where-Object { $_ })
    if ($wanted.Count -eq 0) { $wanted = @("Any") }

    foreach ($desiredPort in $wanted) {
        if ($desiredPort -match "^(?i)any$") {
            if (-not (@($have | Where-Object { $_ -match "^(?i)any$" }).Count -gt 0)) { return $false }
            continue
        }
        if (@($have | Where-Object { $_ -match "^(?i)any$" }).Count -gt 0) { continue }
        $covered = $false
        foreach ($existingPort in $have) {
            if ([string]::Equals($existingPort, $desiredPort, [System.StringComparison]::OrdinalIgnoreCase)) {
                $covered = $true
                break
            }
            if ($existingPort -match "^(\d+)-(\d+)$" -and $desiredPort -match "^\d+$") {
                $low = [int]$Matches[1]
                $high = [int]$Matches[2]
                $number = [int]$desiredPort
                if ($number -ge $low -and $number -le $high) { $covered = $true; break }
            }
        }
        if (-not $covered) { return $false }
    }
    return $true
}

function Test-FantasyLifeInterfacesCover {
    param($Existing, $Desired)
    $have = @($Existing | ForEach-Object { ([string]$_).Trim() } | Where-Object { $_ })
    if ($have.Count -eq 0) { $have = @("Any") }
    $wanted = @($Desired | ForEach-Object { ([string]$_).Trim() } | Where-Object { $_ })
    if ($wanted.Count -eq 0) { $wanted = @("Any") }

    foreach ($desiredIface in $wanted) {
        if ($desiredIface -match "^(?i)any$") {
            if (-not (@($have | Where-Object { $_ -match "^(?i)any$" }).Count -gt 0)) { return $false }
            continue
        }
        if (@($have | Where-Object { $_ -match "^(?i)any$" }).Count -gt 0) { continue }
        $covered = $false
        foreach ($existingIface in $have) {
            if ([string]::Equals($existingIface, $desiredIface, [System.StringComparison]::OrdinalIgnoreCase)) {
                $covered = $true
                break
            }
            if ($existingIface -match "[\*\?\[]" -and $desiredIface -like $existingIface) {
                $covered = $true
                break
            }
        }
        if (-not $covered) { return $false }
    }
    return $true
}

function Test-FantasyLifeRemoteCover {
    param($Existing, $Desired)
    $have = @($Existing | ForEach-Object { ([string]$_).Trim() } | Where-Object { $_ })
    if ($have.Count -eq 0) { $have = @("Any") }
    $wanted = @($Desired | ForEach-Object { ([string]$_).Trim() } | Where-Object { $_ })
    if ($wanted.Count -eq 0) { $wanted = @("Any") }

    foreach ($desiredAddress in $wanted) {
        if ($desiredAddress -match "^(?i)any$" -or $desiredAddress -eq "*") {
            if (@($have | Where-Object { $_ -match "^(?i)any$" -or $_ -eq "*" }).Count -eq 0) { return $false }
            continue
        }
        if (@($have | Where-Object { $_ -match "^(?i)any$" -or $_ -eq "*" }).Count -gt 0) { continue }
        $covered = $false
        foreach ($existingAddress in $have) {
            if (Test-FantasyLifeAddressCovers $existingAddress $desiredAddress) {
                $covered = $true
                break
            }
        }
        if (-not $covered) { return $false }
    }
    return $true
}

function Test-FantasyLifeProtocolCovers {
    param([string]$Existing, [string]$Desired)
    $left = ([string]$Existing).Trim()
    if (-not $left) { $left = "Any" }
    if ($left -match "^(?i)any$" -or $left -match "^(?i)all$") { return $true }
    return [string]::Equals($left, ([string]$Desired).Trim(), [System.StringComparison]::OrdinalIgnoreCase)
}

function Test-FantasyLifeRuleCovers {
    param($Existing, $Desired)
    if (-not $Existing -or -not $Desired) { return $false }
    if (-not $Existing.Enabled) { return $false }
    if ($Existing.Direction -ne "Inbound") { return $false }
    if ($Existing.Action -ne "Allow") { return $false }
    if (-not (Test-FantasyLifeSamePath $Existing.Program $Desired.Program)) { return $false }
    if (-not (Test-FantasyLifeProtocolCovers $Existing.Protocol $Desired.Protocol)) { return $false }
    if (-not (Test-FantasyLifeProfilesCover $Existing.Profiles $Desired.Profiles)) { return $false }
    if (-not (Test-FantasyLifePortsCover $Existing.LocalPort $Desired.LocalPorts)) { return $false }
    if (-not $Existing.InterfaceAliasKnown -and @($Desired.InterfaceAliases).Count -gt 0) {
        # COM did not expose the adapter scope. Only an exact name match can
        # safely satisfy an adapter-scoped rule; that path is handled before
        # coverage is considered.
        return $false
    }
    if (-not (Test-FantasyLifeInterfacesCover $Existing.InterfaceAlias $Desired.InterfaceAliases)) { return $false }
    if (-not (Test-FantasyLifeRemoteCover $Existing.RemoteAddress $Desired.RemoteAddresses)) { return $false }
    return $true
}

function Test-FantasyLifeRuleEquivalent {
    param($Existing, $Desired)
    if (-not $Existing -or -not $Desired) { return $false }
    if (-not $Existing.Enabled) { return $false }
    if ($Existing.Direction -ne "Inbound") { return $false }
    if ($Existing.Action -ne "Allow") { return $false }
    if (-not (Test-FantasyLifeSamePath $Existing.Program $Desired.Program)) { return $false }
    if (-not (Test-FantasyLifeProtocolCovers $Existing.Protocol $Desired.Protocol)) { return $false }
    if (-not (Test-FantasyLifeProtocolCovers $Desired.Protocol $Existing.Protocol)) { return $false }
    if (-not (Test-FantasyLifeProfilesEqual $Existing.Profiles $Desired.Profiles)) { return $false }

    $existingPorts = @($Existing.LocalPort | ForEach-Object { ([string]$_).Trim().ToLowerInvariant() } | Sort-Object -Unique)
    $desiredPorts = @($Desired.LocalPorts | ForEach-Object { ([string]$_).Trim().ToLowerInvariant() } | Sort-Object -Unique)
    if (($existingPorts -join "|") -ne ($desiredPorts -join "|")) { return $false }

    if ($Existing.InterfaceAliasKnown -or @($Desired.InterfaceAliases).Count -eq 0) {
        $existingIfaces = @($Existing.InterfaceAlias | ForEach-Object { ([string]$_).Trim().ToLowerInvariant() } | Sort-Object -Unique)
        $desiredIfaces = @($Desired.InterfaceAliases | ForEach-Object { ([string]$_).Trim().ToLowerInvariant() } | Sort-Object -Unique)
        if ($desiredIfaces.Count -eq 0) { $desiredIfaces = @("any") }
        if ($existingIfaces.Count -eq 0) { $existingIfaces = @("any") }
        if (($existingIfaces -join "|") -ne ($desiredIfaces -join "|")) { return $false }
    }

    $existingRemote = @($Existing.RemoteAddress | ForEach-Object { Get-FantasyLifeAddressCanonical ([string]$_) } | Sort-Object -Unique)
    $desiredRemote = @($Desired.RemoteAddresses | ForEach-Object { Get-FantasyLifeAddressCanonical ([string]$_) } | Sort-Object -Unique)
    if ($desiredRemote.Count -eq 0) { $desiredRemote = @("Any") }
    if ($existingRemote.Count -eq 0) { $existingRemote = @("Any") }
    if (($existingRemote -join "|") -ne ($desiredRemote -join "|")) { return $false }

    return $true
}

# ---------------------------------------------------------------------------
# Planning
# ---------------------------------------------------------------------------

function New-FantasyLifeFirewallPlan {
    param(
        [object[]]$Installs = @(),
        [object[]]$Adapters = @(),
        [object[]]$ExistingRules = @(),
        [switch]$Remove
    )

    $group = $script:FantasyLifeFirewallGroup
    $desired = @()
    foreach ($install in @($Installs)) {
        $desired += @(Get-FantasyLifeDesiredRules -Install $install -Adapters $Adapters)
    }

    $create = @()
    $update = @()
    $keep = @()
    $covered = @()
    $obsolete = @()
    $removeRules = @()
    $blocks = @()

    $installPrograms = @($Installs | ForEach-Object { $_.Exe })
    $programMatches = {
        param([string]$program)
        foreach ($candidate in $installPrograms) {
            if (Test-FantasyLifeSamePath $program $candidate) { return $true }
        }
        return $false
    }

    if (-not $Remove) {
        foreach ($rule in @($ExistingRules)) {
            if (-not $rule) { continue }
            if ($rule.Direction -ne "Inbound" -or $rule.Action -ne "Block") { continue }
            if (-not (& $programMatches $rule.Program)) { continue }
            $blocks += $rule
        }
    }

    if ($Remove) {
        foreach ($rule in @($ExistingRules)) {
            if (-not $rule) { continue }
            if ($rule.Group -ne $group) { continue }
            if (-not (& $programMatches $rule.Program)) { continue }
            $removeRules += $rule
        }
        return [pscustomobject]@{
            Installs      = @($Installs)
            Desired       = $desired
            Create        = @()
            Update        = @()
            Keep          = @()
            Covered       = @()
            Obsolete      = @()
            RemoveRules   = $removeRules
            Blocks        = @()
            Ready         = $false
            RemoveRequested = $true
        }
    }

    foreach ($install in @($Installs)) {
        $installDesired = @($desired | Where-Object { Test-FantasyLifeSamePath $_.Program $install.Exe })
        $installGroupRules = @($ExistingRules | Where-Object {
            $_ -and $_.Group -eq $group -and (Test-FantasyLifeSamePath $_.Program $install.Exe)
        })
        $desiredNames = @($installDesired | ForEach-Object { $_.DisplayName })

        foreach ($spec in $installDesired) {
            $ours = @($installGroupRules | Where-Object { $_.DisplayName -eq $spec.DisplayName } | Select-Object -First 1)
            if ($ours.Count -gt 0) {
                $entry = [pscustomobject]@{ Install = $install; Desired = $spec; Existing = $ours[0] }
                if (Test-FantasyLifeRuleEquivalent $ours[0] $spec) {
                    $keep += $entry
                } else {
                    $update += $entry
                }
                continue
            }

            $covering = @($ExistingRules | Where-Object {
                $_ -and (Test-FantasyLifeRuleCovers $_ $spec)
            } | Select-Object -First 1)
            if ($covering.Count -gt 0) {
                $covered += [pscustomobject]@{ Install = $install; Desired = $spec; Existing = $covering[0] }
            } else {
                $create += [pscustomobject]@{ Install = $install; Desired = $spec }
            }
        }

        foreach ($rule in $installGroupRules) {
            if (-not ($desiredNames -contains $rule.DisplayName)) {
                $obsolete += [pscustomobject]@{ Install = $install; Existing = $rule }
            }
        }
    }

    $ready = ($blocks.Count -eq 0 -and $create.Count -eq 0 -and $update.Count -eq 0 -and $obsolete.Count -eq 0)
    return [pscustomobject]@{
        Installs        = @($Installs)
        Desired         = $desired
        Create          = $create
        Update          = $update
        Keep            = $keep
        Covered         = $covered
        Obsolete        = $obsolete
        RemoveRules     = @()
        Blocks          = $blocks
        Ready           = $ready
        RemoveRequested = $false
    }
}

# ---------------------------------------------------------------------------
# Applying
# ---------------------------------------------------------------------------

function New-FantasyLifeFirewallRule {
    param([Parameter(Mandatory = $true)]$Spec)
    $params = @{
        Name        = $Spec.Name
        DisplayName = $Spec.DisplayName
        Group       = $Spec.Group
        Description = $Spec.Description
        Direction   = "Inbound"
        Action      = "Allow"
        Protocol    = "UDP"
        Profile     = @($Spec.Profiles)
        Program     = $Spec.Program
    }
    if (@($Spec.RemoteAddresses).Count -gt 0) {
        $params.RemoteAddress = @($Spec.RemoteAddresses)
    }
    if (@($Spec.InterfaceAliases).Count -gt 0) {
        $params.InterfaceAlias = @($Spec.InterfaceAliases)
    }
    $ports = @($Spec.LocalPorts)
    if ($ports.Count -gt 0 -and -not ($ports.Count -eq 1 -and ([string]$ports[0]) -match "^(?i)any$")) {
        $params.LocalPort = @($ports)
    }
    New-NetFirewallRule @params | Out-Null
}

function Remove-FantasyLifeFirewallRuleRecord {
    param($Rule)
    try {
        if ($Rule.Identity) {
            Remove-NetFirewallRule -Name $Rule.Identity -ErrorAction Stop
        } elseif ($Rule.Group) {
            Remove-NetFirewallRule -Group $Rule.Group -DisplayName $Rule.DisplayName -ErrorAction Stop
        } else {
            Remove-NetFirewallRule -DisplayName $Rule.DisplayName -Direction Inbound -Action Block -ErrorAction Stop
        }
        return $null
    } catch {
        if ($_.Exception.Message -match "No MSFT_NetFirewallRule|not found|0x80320003") { return $null }
        return $_.Exception.Message
    }
}

function Invoke-FantasyLifeFirewallPlan {
    param($Plan, [switch]$DryRun)

    $failures = @()
    if ($DryRun) { return $failures }

    # Remove Block rules first: they override every allow rule.
    foreach ($block in @($Plan.Blocks)) {
        $problem = Remove-FantasyLifeFirewallRuleRecord $block
        if ($problem) { $failures += "could not remove block rule '$($block.DisplayName)': $problem" }
    }

    foreach ($entry in @($Plan.Update)) {
        $problem = Remove-FantasyLifeFirewallRuleRecord $entry.Existing
        if ($problem) { $failures += "could not remove old rule '$($entry.Existing.DisplayName)': $problem"; continue }
        try { New-FantasyLifeFirewallRule -Spec $entry.Desired }
        catch { $failures += "could not create '$($entry.Desired.DisplayName)': $($_.Exception.Message)" }
    }

    foreach ($entry in @($Plan.Obsolete)) {
        $problem = Remove-FantasyLifeFirewallRuleRecord $entry.Existing
        if ($problem) { $failures += "could not remove obsolete rule '$($entry.Existing.DisplayName)': $problem" }
    }

    foreach ($entry in @($Plan.Create)) {
        try { New-FantasyLifeFirewallRule -Spec $entry.Desired }
        catch { $failures += "could not create '$($entry.Desired.DisplayName)': $($_.Exception.Message)" }
    }

    foreach ($rule in @($Plan.RemoveRules)) {
        $problem = Remove-FantasyLifeFirewallRuleRecord $rule
        if ($problem) { $failures += "could not remove '$($rule.DisplayName)': $problem" }
    }

    return $failures
}

# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

function Get-FantasyLifeRuleScopeText {
    param($Spec)
    $parts = @("Inbound UDP allow")
    $parts += ("profile " + (@($Spec.Profiles) -join ","))
    if (@($Spec.RemoteAddresses).Count -gt 0) {
        $parts += ("remote " + (@($Spec.RemoteAddresses) -join ","))
    } else {
        $parts += "remote Any"
    }
    if (@($Spec.InterfaceAliases).Count -gt 0) {
        $parts += ("interface " + (@($Spec.InterfaceAliases) -join ","))
    }
    $ports = @($Spec.LocalPorts)
    if ($ports.Count -gt 0 -and -not ($ports.Count -eq 1 -and ([string]$ports[0]) -match "^(?i)any$")) {
        $parts += ("local port " + ($ports -join ","))
    }
    $parts += ("program " + $Spec.Program)
    return ($parts -join "; ")
}

function Get-FantasyLifeExistingScopeText {
    param($Rule)
    $parts = @("$($Rule.Direction) $($Rule.Action)")
    $parts += ("profile " + (@($Rule.Profiles) -join ","))
    $parts += ("remote " + (@($Rule.RemoteAddress) -join ","))
    if (@($Rule.InterfaceAlias).Count -gt 0 -and -not (@($Rule.InterfaceAlias)[0] -match "^(?i)any$")) {
        $parts += ("interface " + (@($Rule.InterfaceAlias) -join ","))
    }
    $parts += ("protocol " + $Rule.Protocol)
    return ($parts -join "; ")
}

function Write-FantasyLifeFirewallPlan {
    param($Plan, [switch]$WhatIf, [switch]$CheckOnly)

    $hadOutput = $false
    foreach ($install in @($Plan.Installs)) {
        Write-FantasyLifeFirewallLine ""
        Write-FantasyLifeFirewallLine ("[Firewall] Install: " + $install.InstallDir) "Cyan"
        Write-FantasyLifeFirewallLine ("[Firewall]   exe:   " + $install.Exe) "DarkGray"

        $installDesired = @($Plan.Desired | Where-Object { Test-FantasyLifeSamePath $_.Program $install.Exe })
        foreach ($spec in $installDesired) {
            $entry = $null
            $kind = $spec.Kind

            $entry = @($Plan.Keep | Where-Object { $_.Desired.Name -eq $spec.Name } | Select-Object -First 1)
            if ($entry.Count -gt 0) {
                Write-FantasyLifeFirewallLine ("[Firewall]   {0,-12} already present as {1}" -f $kind, $spec.Name) "DarkGray"
                $hadOutput = $true
                continue
            }

            $entry = @($Plan.Covered | Where-Object { $_.Desired.Name -eq $spec.Name } | Select-Object -First 1)
            if ($entry.Count -gt 0) {
                $existing = $entry[0].Existing
                Write-FantasyLifeFirewallLine ("[Firewall]   {0,-12} covered by existing rule `"{1}`" ({2})" -f $kind, $existing.DisplayName, (Get-FantasyLifeExistingScopeText $existing)) "DarkGray"
                $hadOutput = $true
                continue
            }

            $entry = @($Plan.Update | Where-Object { $_.Desired.Name -eq $spec.Name } | Select-Object -First 1)
            if ($entry.Count -gt 0) {
                $verb = if ($WhatIf) { "WOULD UPDATE" } elseif ($CheckOnly) { "MISSING" } else { "UPDATED" }
                Write-FantasyLifeFirewallLine ("[Firewall]   {0,-12} {1}: {2}" -f $kind, $verb, (Get-FantasyLifeRuleScopeText $spec)) "Yellow"
                $hadOutput = $true
                continue
            }

            $entry = @($Plan.Create | Where-Object { $_.Desired.Name -eq $spec.Name } | Select-Object -First 1)
            if ($entry.Count -gt 0) {
                $verb = if ($WhatIf) { "WOULD CREATE" } elseif ($CheckOnly) { "MISSING" } else { "CREATED" }
                Write-FantasyLifeFirewallLine ("[Firewall]   {0,-12} {1}: {2}" -f $kind, $verb, (Get-FantasyLifeRuleScopeText $spec)) $(if ($CheckOnly) { "Yellow" } else { "Green" })
                $hadOutput = $true
            }
        }

        $installObsolete = @($Plan.Obsolete | Where-Object { Test-FantasyLifeSamePath $_.Existing.Program $install.Exe })
        foreach ($entry in $installObsolete) {
            $verb = if ($WhatIf) { "WOULD REMOVE obsolete rule" } elseif ($CheckOnly) { "OBSOLETE rule" } else { "REMOVED obsolete rule" }
            Write-FantasyLifeFirewallLine ("[Firewall]   {0} `"{1}`" ({2})" -f $verb, $entry.Existing.DisplayName, (Get-FantasyLifeExistingScopeText $entry.Existing)) "Yellow"
            $hadOutput = $true
        }
    }

    foreach ($block in @($Plan.Blocks)) {
        $verb = if ($WhatIf) { "WOULD REMOVE block rule" } elseif ($CheckOnly) { "BLOCK rule" } else { "REMOVED block rule" }
        Write-FantasyLifeFirewallLine ("[Firewall]   {0} `"{1}`" ({2})" -f $verb, $block.DisplayName, (Get-FantasyLifeExistingScopeText $block)) "Red"
        $hadOutput = $true
    }

    foreach ($rule in @($Plan.RemoveRules)) {
        $verb = if ($WhatIf) { "WOULD REMOVE" } else { "REMOVED" }
        Write-FantasyLifeFirewallLine ("[Firewall]   {0}: `"{1}`" ({2})" -f $verb, $rule.DisplayName, (Get-FantasyLifeExistingScopeText $rule)) "Yellow"
        $hadOutput = $true
    }

    if (-not $hadOutput) {
        if ($Plan.RemoveRequested) {
            Write-FantasyLifeFirewallLine "[Firewall]   No managed rules found for these installs." "DarkGray"
        } else {
            Write-FantasyLifeFirewallLine "[Firewall]   All required rules are already present." "Green"
        }
    }
}

function Get-FantasyLifePlanCounts {
    param($Plan)
    return [pscustomobject]@{
        Create   = @($Plan.Create).Count
        Update   = @($Plan.Update).Count
        Keep     = @($Plan.Keep).Count
        Covered  = @($Plan.Covered).Count
        Obsolete = @($Plan.Obsolete).Count
        Blocks   = @($Plan.Blocks).Count
        Remove   = @($Plan.RemoveRules).Count
    }
}

# ---------------------------------------------------------------------------
# Public helpers used by play.ps1 / installers
# ---------------------------------------------------------------------------

function Get-FantasyLifeFirewallStatus {
    param([Parameter(Mandatory = $true)][string[]]$InstallDir)

    $installs = @(Get-FantasyLifeInstallInfo -InstallDir $InstallDir)
    $adapters = @(Get-FantasyLifeZeroTierAdapters)
    $programs = @($installs | ForEach-Object { $_.Exe })
    $existing = @(Get-FantasyLifeFirewallSnapshot -Program $programs)
    $plan = New-FantasyLifeFirewallPlan -Installs $installs -Adapters $adapters -ExistingRules $existing

    return [pscustomobject]@{
        Ready        = [bool]$plan.Ready
        Installs     = $installs
        Plan         = $plan
        MissingCount = (@($plan.Create).Count + @($plan.Update).Count + @($plan.Obsolete).Count + @($plan.Blocks).Count)
    }
}

function Invoke-FantasyLifeFirewallSetupElevated {
    param(
        [Parameter(Mandatory = $true)][string[]]$InstallDir,
        [switch]$Remove
    )

    $scriptPath = $script:FantasyLifeFirewallScriptPath
    if (-not $scriptPath -or -not (Test-Path -LiteralPath $scriptPath -PathType Leaf)) {
        Write-FantasyLifeFirewallLine "[Firewall] setup-firewall.ps1 was not found; cannot change firewall rules." "Yellow"
        return $false
    }

    if (Test-FantasyLifeIsElevated) {
        $code = Invoke-FantasyLifeFirewallMain -InstallDir $InstallDir -Remove:$Remove
        return ($code -eq 0)
    }

    $quotedScript = $scriptPath.Replace("'", "''")
    $quotedDirs = @($InstallDir | ForEach-Object { "'" + ([string]$_).Replace("'", "''") + "'" }) -join ","
    $command = "& '$quotedScript' -InstallDir @($quotedDirs)"
    if ($Remove) { $command += " -Remove" }

    $encoded = [Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($command))
    $powershell = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"

    try {
        $process = Start-Process -FilePath $powershell `
            -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", $encoded) `
            -Verb RunAs -Wait -PassThru -ErrorAction Stop
    } catch {
        Write-FantasyLifeFirewallLine "[Firewall] Setup was not completed (UAC declined); Hamachi/LAN multiplayer may be blocked. Retry with: play.bat -SetupFirewall" "Yellow"
        return $false
    }

    if ($process.ExitCode -ne 0) {
        Write-FantasyLifeFirewallLine ("[Firewall] Setup exited with code {0}. Retry with: play.bat -SetupFirewall" -f $process.ExitCode) "Yellow"
        return $false
    }
    return $true
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

function Invoke-FantasyLifeFirewallMain {
    param(
        [string[]]$InstallDir = @(),
        [switch]$Remove,
        [switch]$Check
    )

    $dryRun = [bool]$WhatIfPreference
    # Keep -WhatIf from leaking into read-only cmdlets (Get-CimInstance and
    # friends) and into the write path; we report and apply explicitly below.
    $WhatIfPreference = $false

    if (-not $InstallDir -or @($InstallDir).Count -eq 0) {
        Write-FantasyLifeFirewallLine "Usage: setup-firewall.ps1 -InstallDir <path> [<path> ...] [-Remove] [-WhatIf]" "Yellow"
        Write-FantasyLifeFirewallLine "  Example: setup-firewall.ps1 -InstallDir `"$env:LOCALAPPDATA\FantasyLife-PC`"" "DarkGray"
        return 2
    }

    Write-FantasyLifeFirewallLine ""
    Write-FantasyLifeFirewallLine "==============================================================" "DarkCyan"
    if ($Remove) {
        Write-FantasyLifeFirewallLine " Fantasy Life PC - remove managed Windows Firewall rules" "Cyan"
    } elseif ($Check) {
        Write-FantasyLifeFirewallLine " Fantasy Life PC - check Windows Firewall rules" "Cyan"
    } elseif ($dryRun) {
        Write-FantasyLifeFirewallLine " Fantasy Life PC - Windows Firewall setup (dry run)" "Cyan"
    } else {
        Write-FantasyLifeFirewallLine " Fantasy Life PC - Windows Firewall setup" "Cyan"
    }
    Write-FantasyLifeFirewallLine (" Group: " + $script:FantasyLifeFirewallGroup) "Gray"
    Write-FantasyLifeFirewallLine "==============================================================" "DarkCyan"

    try {
        $installs = @(Get-FantasyLifeInstallInfo -InstallDir $InstallDir -AllowMissing:$Remove)
    } catch {
        Write-FantasyLifeFirewallLine ("[Firewall] " + $_.Exception.Message) "Red"
        return 1
    }

    if ($installs.Count -eq 0) {
        Write-FantasyLifeFirewallLine "[Firewall] No install directories were given." "Yellow"
        return 2
    }

    $adapters = @()
    if (-not $Remove) {
        $adapters = @(Get-FantasyLifeZeroTierAdapters)
        if ($adapters.Count -gt 0) {
            Write-FantasyLifeFirewallLine ("[Firewall] ZeroTier adapter(s): " + (@($adapters | ForEach-Object { $_.Name }) -join ", ")) "DarkGray"
        }
    }

    $programs = @($installs | ForEach-Object { $_.Exe })
    try {
        $existing = @(Get-FantasyLifeFirewallSnapshot -Program $programs)
    } catch {
        Write-FantasyLifeFirewallLine ("[Firewall] Could not read firewall rules: " + $_.Exception.Message) "Red"
        return 1
    }

    $plan = New-FantasyLifeFirewallPlan -Installs $installs -Adapters $adapters -ExistingRules $existing -Remove:$Remove
    Write-FantasyLifeFirewallPlan -Plan $plan -WhatIf:$dryRun -CheckOnly:$Check
    $counts = Get-FantasyLifePlanCounts $plan

    if ($Check) {
        Write-FantasyLifeFirewallLine ""
        if ($plan.Ready) {
            Write-FantasyLifeFirewallLine "[Firewall] OK - all required multiplayer rules are present." "Green"
            return 0
        }
        Write-FantasyLifeFirewallLine ("[Firewall] Missing/blocked: {0} rule(s) to create, {1} to update, {2} obsolete, {3} block(s)." -f $counts.Create, $counts.Update, $counts.Obsolete, $counts.Blocks) "Yellow"
        Write-FantasyLifeFirewallLine "[Firewall] Run play.bat -SetupFirewall (one UAC prompt) to fix this." "Yellow"
        return 2
    }

    if ($Remove) {
        if (-not $dryRun -and -not (Test-FantasyLifeIsElevated)) {
            Write-FantasyLifeFirewallLine "[Firewall] Administrator rights are required to remove firewall rules." "Red"
            Write-FantasyLifeFirewallLine "[Firewall] Re-run from an elevated PowerShell, or use play.bat -SetupFirewall." "Yellow"
            return 3
        }
        $failures = @(Invoke-FantasyLifeFirewallPlan -Plan $plan -DryRun:$dryRun)
        Write-FantasyLifeFirewallLine ""
        if ($failures.Count -gt 0) {
            foreach ($failure in $failures) { Write-FantasyLifeFirewallLine ("[Firewall] " + $failure) "Red" }
            return 1
        }
        if ($dryRun) {
            Write-FantasyLifeFirewallLine ("[Firewall] Would remove {0} managed rule(s)." -f $counts.Remove) "Yellow"
        } elseif ($counts.Remove -eq 0) {
            Write-FantasyLifeFirewallLine "[Firewall] No managed rules were present." "DarkGray"
        } else {
            Write-FantasyLifeFirewallLine ("[Firewall] Removed {0} managed rule(s). Other firewall rules were left alone." -f $counts.Remove) "Green"
        }
        return 0
    }

    if (-not $dryRun -and -not (Test-FantasyLifeIsElevated)) {
        Write-FantasyLifeFirewallLine "" 
        Write-FantasyLifeFirewallLine "[Firewall] Administrator rights are required to change firewall rules." "Red"
        Write-FantasyLifeFirewallLine "[Firewall] Re-run from an elevated PowerShell, or use play.bat -SetupFirewall (one UAC prompt)." "Yellow"
        return 3
    }

    $failures = @(Invoke-FantasyLifeFirewallPlan -Plan $plan -DryRun:$dryRun)
    Write-FantasyLifeFirewallLine ""
    if ($failures.Count -gt 0) {
        foreach ($failure in $failures) { Write-FantasyLifeFirewallLine ("[Firewall] " + $failure) "Red" }
        return 1
    }

    if ($dryRun) {
        Write-FantasyLifeFirewallLine ("[Firewall] Dry run: would create {0}, update {1}, keep {2}, use {3} existing rule(s), remove {4} obsolete, remove {5} block(s)." -f $counts.Create, $counts.Update, $counts.Keep, $counts.Covered, $counts.Obsolete, $counts.Blocks) "Yellow"
        Write-FantasyLifeFirewallLine "[Firewall] No changes were made (-WhatIf)." "DarkGray"
    } else {
        Write-FantasyLifeFirewallLine ("[Firewall] Created {0}; updated {1}; already present {2}; covered by existing rules {3}; removed {4} obsolete and {5} block(s)." -f $counts.Create, $counts.Update, $counts.Keep, $counts.Covered, $counts.Obsolete, $counts.Blocks) "Green"
        Write-FantasyLifeFirewallLine "[Firewall] Multiplayer network access is ready." "Green"
    }
    return 0
}

if ($MyInvocation.InvocationName -ne ".") {
    exit (Invoke-FantasyLifeFirewallMain -InstallDir $InstallDir -Remove:$Remove -Check:$Check)
}
