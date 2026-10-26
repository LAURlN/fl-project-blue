# Fantasy Life PC - desktop icon from the player's own game dump.
#
# The package repository is public, so it never ships game artwork. Instead this
# script reads the 3DS SMDH icon from the player's dump (NCSD -> NCCH partition 0
# -> ExeFS "icon"), decodes it and writes an untracked multi-size icon:
#   data\yw2-recomp\icon.ico  (16, 24, 32, 48, 64, 128, 256)
#   data\yw2-recomp\icon.png  (256x256, used by the launcher window)
#
# SMDH layout: large icon 48x48 at 0x24C0, small icon 24x24 at 0x2040, both RGB565
# little-endian, stored as 8x8 tiles in row-major tile order with the pixels inside a
# tile in Morton (Z) order (x in the even bits, y in the odd bits).
#
# Dot-source this file; it only defines functions. Windows PowerShell 5.1 compatible.

$script:FantasyLifeIconVersion = "2"

function Read-FantasyLifeSmdh {
    param([Parameter(Mandatory = $true)][string]$RomPath)
    $fs = [System.IO.File]::Open($RomPath, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
    try {
        $br = New-Object System.IO.BinaryReader($fs)
        $readAt = {
            param([long]$Offset, [int]$Count)
            $fs.Position = $Offset
            $buf = $br.ReadBytes($Count)
            if ($buf.Length -ne $Count) { throw "dump is truncated" }
            return , $buf
        }
        $magic = & $readAt 0x100 4
        $ncchBase = 0
        if ([System.Text.Encoding]::ASCII.GetString($magic) -eq "NCSD") {
            $part = & $readAt 0x120 8
            $ncchBase = [long][BitConverter]::ToUInt32($part, 0) * 0x200
        }
        $ncchMagic = & $readAt ($ncchBase + 0x100) 4
        if ([System.Text.Encoding]::ASCII.GetString($ncchMagic) -ne "NCCH") { throw "no NCCH partition found" }
        $flags = & $readAt ($ncchBase + 0x188) 8
        if (($flags[7] -band 0x04) -eq 0) { throw "the dump is encrypted (decrypted dumps only)" }
        $exefsInfo = & $readAt ($ncchBase + 0x1A0) 8
        $exefsBase = $ncchBase + [long][BitConverter]::ToUInt32($exefsInfo, 0) * 0x200
        $header = & $readAt $exefsBase 0x200
        for ($i = 0; $i -lt 10; $i++) {
            $name = [System.Text.Encoding]::ASCII.GetString($header, $i * 16, 8).TrimEnd([char]0)
            if ($name -eq "icon") {
                $offset = [BitConverter]::ToUInt32($header, $i * 16 + 8)
                $size = [BitConverter]::ToUInt32($header, $i * 16 + 12)
                if ($size -lt 0x36C0) { throw "SMDH icon is too small ($size bytes)" }
                $smdh = & $readAt ($exefsBase + 0x200 + $offset) ([int]$size)
                if ([System.Text.Encoding]::ASCII.GetString($smdh, 0, 4) -ne "SMDH") { throw "ExeFS icon is not SMDH" }
                return , $smdh
            }
        }
        throw "no icon in ExeFS"
    } finally {
        $fs.Dispose()
    }
}

# Decode one SMDH icon into an int[] of ARGB pixels (row-major).
function ConvertFrom-FantasyLifeSmdhIcon {
    param([byte[]]$Smdh, [int]$Offset, [int]$Size)
    $pixels = New-Object int[] ($Size * $Size)
    $tiles = [int]($Size / 8)
    # Morton index -> (x, y) inside an 8x8 tile
    $mx = New-Object int[] 64
    $my = New-Object int[] 64
    for ($m = 0; $m -lt 64; $m++) {
        $mx[$m] = ($m -band 1) -bor (($m -shr 1) -band 2) -bor (($m -shr 2) -band 4)
        $my[$m] = (($m -shr 1) -band 1) -bor (($m -shr 2) -band 2) -bor (($m -shr 3) -band 4)
    }
    $i = $Offset
    for ($ty = 0; $ty -lt $tiles; $ty++) {
        for ($tx = 0; $tx -lt $tiles; $tx++) {
            for ($m = 0; $m -lt 64; $m++) {
                $v = [int]$Smdh[$i] -bor ([int]$Smdh[$i + 1] -shl 8)
                $i += 2
                $r = ($v -shr 11) -band 31; $g = ($v -shr 5) -band 63; $b = $v -band 31
                $r = ($r -shl 3) -bor ($r -shr 2); $g = ($g -shl 2) -bor ($g -shr 4); $b = ($b -shl 3) -bor ($b -shr 2)
                $x = $tx * 8 + $mx[$m]; $y = $ty * 8 + $my[$m]
                $pixels[$y * $Size + $x] = [int](-16777216 -bor ($r -shl 16) -bor ($g -shl 8) -bor $b)
            }
        }
    }
    return , $pixels
}

# EPX / Scale2x: doubles the size and keeps the ink lines crisp before smoothing.
function Invoke-FantasyLifeScale2x {
    param([int[]]$Src, [int]$Size)
    $n = $Size * 2
    $dst = New-Object int[] ($n * $n)
    $last = $Size - 1
    for ($y = 0; $y -lt $Size; $y++) {
        $row = $y * $Size
        $up = [Math]::Max($y - 1, 0) * $Size
        $down = [Math]::Min($y + 1, $last) * $Size
        for ($x = 0; $x -lt $Size; $x++) {
            $P = $Src[$row + $x]
            $A = $Src[$up + $x]
            $B = $Src[$row + [Math]::Min($x + 1, $last)]
            $C = $Src[$row + [Math]::Max($x - 1, 0)]
            $D = $Src[$down + $x]
            $o = (2 * $y) * $n + 2 * $x
            $dst[$o]          = $(if ($C -eq $A -and $C -ne $D -and $A -ne $B) { $A } else { $P })
            $dst[$o + 1]      = $(if ($A -eq $B -and $A -ne $C -and $B -ne $D) { $B } else { $P })
            $dst[$o + $n]     = $(if ($D -eq $C -and $D -ne $B -and $C -ne $A) { $C } else { $P })
            $dst[$o + $n + 1] = $(if ($B -eq $D -and $B -ne $A -and $D -ne $C) { $D } else { $P })
        }
    }
    return , $dst
}

function New-FantasyLifeBitmapFromPixels {
    param([int[]]$Pixels, [int]$Size)
    $bmp = New-Object System.Drawing.Bitmap($Size, $Size, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $rect = New-Object System.Drawing.Rectangle(0, 0, $Size, $Size)
    $data = $bmp.LockBits($rect, [System.Drawing.Imaging.ImageLockMode]::WriteOnly, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    try {
        [System.Runtime.InteropServices.Marshal]::Copy($Pixels, 0, $data.Scan0, $Pixels.Length)
    } finally {
        $bmp.UnlockBits($data)
    }
    return $bmp
}

function New-FantasyLifeRoundedPath {
    param([float]$Size, [float]$Radius)
    $path = New-Object System.Drawing.Drawing2D.GraphicsPath
    $d = $Radius * 2
    $e = $Size - 0.5
    $path.AddArc(0.5, 0.5, $d, $d, 180, 90)
    $path.AddArc($e - $d, 0.5, $d, $d, 270, 90)
    $path.AddArc($e - $d, $e - $d, $d, $d, 0, 90)
    $path.AddArc(0.5, $e - $d, $d, $d, 90, 90)
    $path.CloseFigure()
    return $path
}

# Scale the source onto a transparent canvas, clipped to an anti-aliased rounded square.
function New-FantasyLifeTile {
    param([System.Drawing.Bitmap]$Source, [int]$Size, [switch]$Pixelated)
    $scaled = New-Object System.Drawing.Bitmap($Size, $Size, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g = [System.Drawing.Graphics]::FromImage($scaled)
    try {
        $g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::Half
        $g.InterpolationMode = $(if ($Pixelated) { [System.Drawing.Drawing2D.InterpolationMode]::NearestNeighbor } else { [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic })
        $attr = New-Object System.Drawing.Imaging.ImageAttributes
        $attr.SetWrapMode([System.Drawing.Drawing2D.WrapMode]::TileFlipXY)
        $g.DrawImage($Source, (New-Object System.Drawing.Rectangle(0, 0, $Size, $Size)), 0, 0, $Source.Width, $Source.Height, [System.Drawing.GraphicsUnit]::Pixel, $attr)
    } finally { $g.Dispose() }

    $tile = New-Object System.Drawing.Bitmap($Size, $Size, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g = [System.Drawing.Graphics]::FromImage($tile)
    try {
        $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
        $g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::Half
        $brush = New-Object System.Drawing.TextureBrush($scaled)
        $path = New-FantasyLifeRoundedPath -Size $Size -Radius ([Math]::Max(2.0, $Size * 0.18))
        $g.FillPath($brush, $path)
        $brush.Dispose(); $path.Dispose()
    } finally { $g.Dispose(); $scaled.Dispose() }
    return $tile
}

function ConvertTo-FantasyLifePngBytes {
    param([System.Drawing.Bitmap]$Bitmap)
    $ms = New-Object System.IO.MemoryStream
    try {
        $Bitmap.Save($ms, [System.Drawing.Imaging.ImageFormat]::Png)
        return , $ms.ToArray()
    } finally { $ms.Dispose() }
}

# 32-bit BMP (DIB) icon entry: BITMAPINFOHEADER + bottom-up BGRA + 1-bit AND mask.
function ConvertTo-FantasyLifeDibBytes {
    param([System.Drawing.Bitmap]$Bitmap)
    $s = $Bitmap.Width
    $rect = New-Object System.Drawing.Rectangle(0, 0, $s, $s)
    $data = $Bitmap.LockBits($rect, [System.Drawing.Imaging.ImageLockMode]::ReadOnly, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $argb = New-Object byte[] ($s * $s * 4)
    try { [System.Runtime.InteropServices.Marshal]::Copy($data.Scan0, $argb, 0, $argb.Length) } finally { $Bitmap.UnlockBits($data) }
    $maskStride = [int]([Math]::Ceiling($s / 32.0) * 4)
    $ms = New-Object System.IO.MemoryStream
    $w = New-Object System.IO.BinaryWriter($ms)
    $w.Write([int]40); $w.Write([int]$s); $w.Write([int]($s * 2)); $w.Write([int16]1); $w.Write([int16]32)
    $w.Write([int]0); $w.Write([int]($s * $s * 4 + $maskStride * $s)); $w.Write([int]0); $w.Write([int]0); $w.Write([int]0); $w.Write([int]0)
    for ($y = $s - 1; $y -ge 0; $y--) { $w.Write($argb, $y * $s * 4, $s * 4) }
    for ($y = $s - 1; $y -ge 0; $y--) {
        $row = New-Object byte[] $maskStride
        for ($x = 0; $x -lt $s; $x++) {
            if ($argb[($y * $s + $x) * 4 + 3] -eq 0) { $row[$x -shr 3] = $row[$x -shr 3] -bor (0x80 -shr ($x -band 7)) }
        }
        $w.Write($row)
    }
    $w.Flush()
    $bytes = $ms.ToArray()
    $w.Dispose()
    return , $bytes
}

function Write-FantasyLifeIco {
    param([string]$Path, [System.Drawing.Bitmap[]]$Images)
    $entries = @()
    foreach ($img in $Images) {
        $bytes = if ($img.Width -ge 256) { ConvertTo-FantasyLifePngBytes $img } else { ConvertTo-FantasyLifeDibBytes $img }
        $entries += , @($img.Width, $bytes)
    }
    $ms = New-Object System.IO.MemoryStream
    $w = New-Object System.IO.BinaryWriter($ms)
    $w.Write([int16]0); $w.Write([int16]1); $w.Write([int16]$entries.Count)
    $offset = 6 + 16 * $entries.Count
    foreach ($e in $entries) {
        $dim = if ($e[0] -ge 256) { 0 } else { $e[0] }
        $w.Write([byte]$dim); $w.Write([byte]$dim); $w.Write([byte]0); $w.Write([byte]0)
        $w.Write([int16]1); $w.Write([int16]32); $w.Write([int]$e[1].Length); $w.Write([int]$offset)
        $offset += $e[1].Length
    }
    foreach ($e in $entries) { $w.Write([byte[]]$e[1]) }
    $w.Flush()
    $tmp = "$Path.tmp"
    [System.IO.File]::WriteAllBytes($tmp, $ms.ToArray())
    $w.Dispose()
    Move-Item -LiteralPath $tmp -Destination $Path -Force
}

# Returns the icon path (generated, or $null when the dump cannot be read).
# Regenerates only when the icon is missing, older than the generator, or -Force.
function Update-FantasyLifeIcon {
    param(
        [string]$RomPath = "",
        [Parameter(Mandatory = $true)][string]$OutDir,
        [switch]$Force
    )
    $ico = Join-Path $OutDir "icon.ico"
    $png = Join-Path $OutDir "icon.png"
    $stamp = Join-Path $OutDir "icon.version"
    $current = $false
    if (-not $Force -and (Test-Path -LiteralPath $ico) -and (Test-Path -LiteralPath $png) -and (Test-Path -LiteralPath $stamp)) {
        $current = ((Get-Content -LiteralPath $stamp -Raw -ErrorAction SilentlyContinue) -as [string]).Trim() -eq $script:FantasyLifeIconVersion
    }
    if ($current) { return $ico }
    if (-not $RomPath -or -not (Test-Path -LiteralPath $RomPath -PathType Leaf)) { return $null }

    Add-Type -AssemblyName System.Drawing
    $smdh = Read-FantasyLifeSmdh -RomPath $RomPath
    $large = ConvertFrom-FantasyLifeSmdhIcon -Smdh $smdh -Offset 0x24C0 -Size 48
    $small = ConvertFrom-FantasyLifeSmdhIcon -Smdh $smdh -Offset 0x2040 -Size 24
    $x2 = Invoke-FantasyLifeScale2x -Src $large -Size 48
    $bmpLarge = New-FantasyLifeBitmapFromPixels -Pixels $large -Size 48
    $bmpSmall = New-FantasyLifeBitmapFromPixels -Pixels $small -Size 24
    $bmpX2 = New-FantasyLifeBitmapFromPixels -Pixels $x2 -Size 96
    $images = @()
    try {
        # The 24x24 SMDH icon is drawn for small sizes; use it below 32 px.
        $images += New-FantasyLifeTile -Source $bmpSmall -Size 16
        $images += New-FantasyLifeTile -Source $bmpSmall -Size 24 -Pixelated
        $images += New-FantasyLifeTile -Source $bmpLarge -Size 32
        $images += New-FantasyLifeTile -Source $bmpLarge -Size 48 -Pixelated
        $images += New-FantasyLifeTile -Source $bmpX2 -Size 64
        $images += New-FantasyLifeTile -Source $bmpX2 -Size 128
        $images += New-FantasyLifeTile -Source $bmpX2 -Size 256
        New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
        Write-FantasyLifeIco -Path $ico -Images $images
        $images[-1].Save("$png.tmp", [System.Drawing.Imaging.ImageFormat]::Png)
        Move-Item -LiteralPath "$png.tmp" -Destination $png -Force
        Set-Content -LiteralPath $stamp -Value $script:FantasyLifeIconVersion -Encoding ASCII
    } finally {
        foreach ($img in $images) { $img.Dispose() }
        $bmpLarge.Dispose(); $bmpSmall.Dispose(); $bmpX2.Dispose()
    }
    return $ico
}

# What a shortcut should start: the console-less launcher (wscript + FantasyLife.vbs)
# when VBScript is available, otherwise play.bat (shows a console briefly).
function Get-FantasyLifeLaunchTarget {
    param([Parameter(Mandatory = $true)][string]$InstallDir)
    $installFull = [System.IO.Path]::GetFullPath($InstallDir).TrimEnd("\")
    $vbs = Join-Path $installFull "bin\launcher\FantasyLife.vbs"
    $wscript = Join-Path $env:SystemRoot "System32\wscript.exe"
    $vbsEngine = Join-Path $env:SystemRoot "System32\vbscript.dll"
    if ((Test-Path -LiteralPath $vbs) -and (Test-Path -LiteralPath $wscript) -and (Test-Path -LiteralPath $vbsEngine)) {
        return [pscustomobject]@{ TargetPath = $wscript; Arguments = "`"$vbs`"" }
    }
    return [pscustomobject]@{ TargetPath = (Join-Path $installFull "play.bat"); Arguments = "" }
}

# The best icon for an install: the one generated from the dump, else the
# neutral fallback shipped in bin\.
function Get-FantasyLifeIconPath {
    param([Parameter(Mandatory = $true)][string]$InstallDir, [string]$RomPath = "")
    $dataDir = Join-Path $InstallDir "data\yw2-recomp"
    if ($RomPath) {
        try {
            $generated = Update-FantasyLifeIcon -RomPath $RomPath -OutDir $dataDir
            if ($generated) { return $generated }
        } catch {}
    }
    $existing = Join-Path $dataDir "icon.ico"
    if (Test-Path -LiteralPath $existing) { return $existing }
    return (Join-Path $InstallDir "bin\fantasy-life.ico")
}

# Create (or overwrite) one shortcut for an install. Used by the installers.
function Set-FantasyLifeShortcut {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$InstallDir,
        [Parameter(Mandatory = $true)][string]$IconPath,
        [string]$Description = "Fantasy Life PC"
    )
    $installFull = [System.IO.Path]::GetFullPath($InstallDir).TrimEnd("\")
    $target = Get-FantasyLifeLaunchTarget -InstallDir $installFull
    $shell = New-Object -ComObject WScript.Shell
    $sc = $shell.CreateShortcut($Path)
    $sc.TargetPath = $target.TargetPath
    $sc.Arguments = $target.Arguments
    $sc.WorkingDirectory = $installFull
    $sc.IconLocation = $IconPath + ",0"
    $sc.Description = $Description
    $sc.Save()
}

# Point this install's "Fantasy Life" shortcuts at $IconPath (and optionally a new
# target). Only shortcuts that already belong to $InstallDir are touched.
# Returns the number of shortcuts that changed.
function Repair-FantasyLifeShortcuts {
    param(
        [Parameter(Mandatory = $true)][string]$InstallDir,
        [Parameter(Mandatory = $true)][string]$IconPath,
        [Parameter(Mandatory = $true)][string]$TargetPath,
        [string]$Arguments = "",
        [string]$Description = "",
        [string[]]$Names = @("Fantasy Life.lnk", "Fantasy Life (Test).lnk")
    )
    $installFull = [System.IO.Path]::GetFullPath($InstallDir).TrimEnd("\")
    $changed = 0
    $shell = New-Object -ComObject WScript.Shell
    $dirs = @([Environment]::GetFolderPath("Desktop"), [Environment]::GetFolderPath("Programs"),
              [Environment]::GetFolderPath("CommonDesktopDirectory"))
    foreach ($dir in $dirs) {
        if (-not $dir -or -not (Test-Path -LiteralPath $dir)) { continue }
        foreach ($name in $Names) {
            $lnk = Join-Path $dir $name
            if (-not (Test-Path -LiteralPath $lnk -PathType Leaf)) { continue }
            try {
                $sc = $shell.CreateShortcut($lnk)
                $owner = ($sc.TargetPath + " " + $sc.Arguments + " " + $sc.WorkingDirectory)
                if ($owner.IndexOf($installFull, [StringComparison]::OrdinalIgnoreCase) -lt 0) { continue }
                $wantIcon = $IconPath + ",0"
                if ($sc.IconLocation -ieq $wantIcon -and $sc.TargetPath -ieq $TargetPath -and $sc.Arguments -eq $Arguments) { continue }
                $sc.TargetPath = $TargetPath
                $sc.Arguments = $Arguments
                $sc.WorkingDirectory = $installFull
                $sc.IconLocation = $wantIcon
                if ($Description) { $sc.Description = $Description }
                $sc.Save()
                $changed++
            } catch {
                # A read-only or foreign shortcut is not worth failing the launch for.
            }
        }
    }
    if ($changed -gt 0) {
        # Ask Explorer to drop cached icons for the changed shortcuts.
        $ie4 = Join-Path $env:SystemRoot "System32\ie4uinit.exe"
        if (Test-Path -LiteralPath $ie4) {
            try { Start-Process -FilePath $ie4 -ArgumentList "-show" -WindowStyle Hidden -ErrorAction Stop | Out-Null } catch {}
        }
    }
    return $changed
}
