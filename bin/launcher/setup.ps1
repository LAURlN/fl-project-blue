function Invoke-FLPythonTool {
    param([string]$Python, [string[]]$Arguments)
    $psi=New-Object Diagnostics.ProcessStartInfo
    $psi.FileName=$Python
    $psi.Arguments=($Arguments | ForEach-Object { '"'+$_.Replace('"','\"')+'"' }) -join ' '
    $psi.UseShellExecute=$false; $psi.CreateNoWindow=$true
    $psi.RedirectStandardOutput=$true; $psi.RedirectStandardError=$true
    $p=[Diagnostics.Process]::Start($psi)
    $out=$p.StandardOutput.ReadToEndAsync(); $err=$p.StandardError.ReadToEndAsync()
    $p.WaitForExit(); $code=$p.ExitCode; $p.Dispose()
    if ($code -ne 0) { throw ($err.Result+' '+$out.Result).Trim() }
    return $out.Result
}

function Install-FLGameFile {
    param([ValidateSet('rom','dlc')][string]$Kind, [string]$Path)
    $tool=Get-FLModToolchain
    if (-not $tool) { throw 'Install Python 3.10 or newer to validate your game dump.' }
    $validator=Join-Path (Split-Path $tool.FlMod) 'fl_3ds.py'
    $extension=if ($Kind -eq 'rom') { '.3ds' } else { '.cia' }
    if ([IO.Path]::GetExtension($Path) -ine $extension) { throw "Select a $extension file." }
    [void](Invoke-FLPythonTool $tool.Python @('-I',$validator,('check-'+$Kind),$Path))
    $game=Join-Path $Here 'game'
    New-Item -ItemType Directory -Path $game -Force | Out-Null
    $target=Join-Path $game $(if ($Kind -eq 'rom') { 'FantasyLife_EU.3ds' } else { 'OriginIsland_DLC.cia' })
    if ([IO.Path]::GetFullPath($Path) -ine [IO.Path]::GetFullPath($target)) {
        # Do not overwrite an existing dump or a hard link to the original source.
        if (Test-Path -LiteralPath $target) { throw "A dump already exists at $target. Move it aside before selecting a replacement." }
        $temp=$target+'.tmp-'+[guid]::NewGuid().ToString('N')
        try {
            Copy-Item -LiteralPath $Path -Destination $temp
            [void](Invoke-FLPythonTool $tool.Python @('-I',$validator,('check-'+$Kind),$temp))
            Move-Item -LiteralPath $temp -Destination $target
        } finally { if (Test-Path -LiteralPath $temp) { Remove-Item -LiteralPath $temp -Force } }
    }
    if ($Kind -eq 'rom') { [void](Update-FLDesktopIntegration -Config (Get-FLConfig) -RomPath $target) }
    return $target
}

function Initialize-FLModArchive {
    param($Toolchain)
    if (Test-Path -LiteralPath (Join-Path $Toolchain.Archive '.fl_archive\manifest.json')) { return }
    $approved=Join-Path $Here 'data\yw2-recomp\extract-mod-archive-approved'
    if (-not (Test-Path -LiteralPath $approved)) { throw 'Source mods need a one-time ROM extraction. Use the launcher to approve extraction first.' }
    $rom=Get-FLRomPath
    if (-not $rom) { throw 'Select your decrypted EU .3ds ROM first.' }
    $toolDir=Split-Path $Toolchain.FlMod
    $parent=Split-Path $Toolchain.Archive
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    $stage=Join-Path $parent ('extract-'+[guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $stage | Out-Null
    try {
        $raw=Join-Path $stage '_file_archive.bin'
        [void](Invoke-FLPythonTool $Toolchain.Python @('-I',(Join-Path $toolDir 'fl_3ds.py'),'extract-archive',$rom,$raw))
        [void](Invoke-FLPythonTool $Toolchain.Python @('-I',(Join-Path $toolDir 'fl_archive.py'),'extract',$raw,(Join-Path $stage 'archive')))
        if (Test-Path -LiteralPath $Toolchain.Archive) { throw 'Archive folder already exists but is incomplete. Preserve it and select a fresh extraction folder.' }
        Move-Item -LiteralPath (Join-Path $stage 'archive') -Destination $Toolchain.Archive
    } finally {
        $resolved=[IO.Path]::GetFullPath($stage)
        if ($resolved.StartsWith([IO.Path]::GetFullPath($parent).TrimEnd('\')+'\',[StringComparison]::OrdinalIgnoreCase)) { Remove-Item -LiteralPath $resolved -Recurse -Force }
    }
}

function Confirm-FLModExtraction {
    $tool=Get-FLModToolchain
    if (-not $tool) { [Windows.MessageBox]::Show('Install Python 3.10 or newer to build source mods.','Source mod tools') | Out-Null; return $false }
    if (Test-Path -LiteralPath (Join-Path $tool.Archive '.fl_archive\manifest.json')) { return $true }
    if ([Windows.MessageBox]::Show('Source mods need a one-time extraction from your configured decrypted EU ROM. Extract automatically when needed? This requires several GB of disk space. The ROM stays unchanged.','Prepare source mod tools','YesNo','Question') -ne 'Yes') { return $false }
    $approved=Join-Path $Here 'data\yw2-recomp\extract-mod-archive-approved'
    New-Item -ItemType Directory -Path (Split-Path $approved) -Force | Out-Null
    [IO.File]::WriteAllText($approved,'Approved by user')
    return $true
}

function Test-FLZipNeedsArchive {
    param([string]$Path)
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip=[IO.Compression.ZipFile]::OpenRead($Path)
    try { return @($zip.Entries | Where-Object { $_.FullName -match '(^|[\\/])mod\.json$' }).Count -gt 0 }
    finally { $zip.Dispose() }
}
