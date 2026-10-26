# Built-in input editor. Values use SDL names, shared with the native runtime.
function Get-FLControlDefaults {
    $values = [ordered]@{ pad_mapping = 'by_label'; pad_deadzone = '18'; pad_sensitivity = '100'; pad_trigger_shoulders = '1'; pad_camera = '1'; pad_cursor_speed = '240'; key_swap_screens = 'Tab'; key_layout = 'F5' }
    $ids = @('a','b','x','y','l','r','zl','zr','start','select','up','down','left','right','circle_up','circle_down','circle_left','circle_right','touch_toggle','touch_press')
    $keys = @('K','J','I','U','Q','E','1','3','Return','Backspace','Up','Down','Left','Right','W','S','A','D','','')
    for ($i=0; $i -lt $ids.Count; $i++) { $values['key_'+$ids[$i]]=$keys[$i]; $values['pad_'+$ids[$i]]='auto' }
    return $values
}

function Get-FLControlSettings {
    $values = Get-FLControlDefaults
    $path = Join-Path $Here 'data\yw2-recomp\settings.ini'
    if (Test-Path -LiteralPath $path) {
        foreach ($line in [IO.File]::ReadAllLines($path)) {
            if ($line -match '^\s*(pad_mapping|key_\w+|pad_\w+)\s*=(.*)$') { $values[$matches[1]]=$matches[2].Trim() }
        }
    }
    return $values
}

function Set-FLControlSettings {
    param($Values)
    $path = Join-Path $Here 'data\yw2-recomp\settings.ini'
    New-Item -ItemType Directory -Path (Split-Path $path) -Force | Out-Null
    $lines = if (Test-Path -LiteralPath $path) { @([IO.File]::ReadAllLines($path)) } else { @() }
    # Replace existing entries in place; retain unknown settings, sections and comments.
    $seen = @{}
    $lines = @($lines | ForEach-Object {
        if ($_ -match '^\s*([^;#=]+?)\s*=' -and $Values.Contains($matches[1])) {
            $key=$matches[1]; $seen[$key]=$true; "$key=$($Values[$key])"
        } else { $_ }
    })
    foreach ($key in $Values.Keys) { if (-not $seen[$key]) { $lines += "$key=$($Values[$key])" } }
    $temp = $path + '.tmp-' + [guid]::NewGuid().ToString('N')
    [IO.File]::WriteAllLines($temp, [string[]]$lines, (New-Object Text.UTF8Encoding $false))
    Move-Item -LiteralPath $temp -Destination $path -Force
}

function ConvertTo-FLSDLKey {
    param($Key)
    $name=[string]$Key
    $map=@{ Enter='Return'; Back='Backspace'; Capital='CapsLock'; Prior='PageUp'; Next='PageDown'; LeftCtrl='Left Ctrl'; RightCtrl='Right Ctrl'; LeftShift='Left Shift'; RightShift='Right Shift'; LeftAlt='Left Alt'; RightAlt='Right Alt'; OemComma=','; OemPeriod='.'; OemMinus='-'; OemPlus='='; OemQuestion='/'; OemSemicolon=';'; OemQuotes="'"; OemOpenBrackets='['; OemCloseBrackets=']'; OemPipe='\'; OemTilde='`' }
    if ($map.ContainsKey($name)) { return $map[$name] }
    if ($name -match '^D([0-9])$') { return $matches[1] }
    if ($name -match '^NumPad([0-9])$') { return 'Keypad '+$matches[1] }
    return $name
}

function Show-FLInputSettings {
    param([switch]$Preview)
    Add-Type -AssemblyName PresentationFramework
    $w=[Windows.Markup.XamlReader]::Parse(@'
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation" Title="Input / Controls" Width="760" Height="720" WindowStartupLocation="CenterOwner" Background="#FFFCF3">
 <DockPanel Margin="18" Background="#FFFCF3">
  <StackPanel DockPanel.Dock="Top">
   <TextBlock Text="Input / Controls" FontSize="24" FontWeight="Bold" Foreground="#4A3420"/>
   <TextBlock Text="Click a keyboard binding, then press a key. Escape cancels; Delete clears." Margin="0,8"/>
   <ComboBox Name="Convention" Margin="0,4"/>
   <WrapPanel Margin="0,8"><ComboBox Name="Preset" Width="330"/><Button Name="ApplyPreset" Content="Apply preset" Margin="8,0" Padding="12,5"/></WrapPanel>
   <Grid Margin="0,4,0,6"><Grid.ColumnDefinitions><ColumnDefinition Width="2*"/><ColumnDefinition Width="*"/><ColumnDefinition Width="*"/></Grid.ColumnDefinitions><TextBlock Text="3DS action" FontWeight="Bold"/><TextBlock Text="Keyboard" Grid.Column="1" FontWeight="Bold"/><TextBlock Text="Controller" Grid.Column="2" FontWeight="Bold"/></Grid>
  </StackPanel>
  <StackPanel DockPanel.Dock="Bottom" Margin="0,12,0,0">
   <TextBlock Name="Status" TextWrapping="Wrap" Margin="0,0,0,8"/>
   <WrapPanel><Button Name="Reset" Content="Reset to Defaults" Padding="12,7"/><Button Name="Advanced" Content="Open Advanced SDL Input Tester" Padding="12,7" Margin="8,0"/><Button Name="Save" Content="Save" Padding="20,7"/><Button Name="Cancel" Content="Cancel" Padding="12,7" Margin="8,0"/></WrapPanel>
  </StackPanel>
  <ScrollViewer Background="#FFFCF3" VerticalScrollBarVisibility="Auto"><StackPanel Name="Rows"/></ScrollViewer>
 </DockPanel>
</Window>
'@)
    if ($script:FL -and $script:FL.Window) { $w.Owner=$script:FL.Window }
    $script:FLInput=@{ Window=$w; Values=(Get-FLControlSettings); Keys=@{}; Pads=@{}; Preview=[bool]$Preview; Waiting=$null }
    foreach ($n in @('Convention','Preset','Rows','Status')) { $script:FLInput[$n]=$w.FindName($n) }
    $c=$script:FLInput.Convention
    [void]$c.Items.Add('By Position (Nintendo: East=A, South=B)')
    [void]$c.Items.Add('By Label (Xbox/PC: South=Confirm, East=Back)')
    $c.SelectedIndex=if ($script:FLInput.Values.pad_mapping -eq 'by_position') { 0 } else { 1 }
    foreach ($p in @('Xbox Controller','PlayStation (DualShock/DualSense)','Nintendo Switch Pro','Keyboard (WASD + J/K/U/I)','Keyboard (Arrow Keys + J/K/U/I)')) { [void]$script:FLInput.Preset.Items.Add($p) }
    $script:FLInput.Preset.SelectedIndex=0
    $padChoices=@('auto','','south','east','west','north','back','guide','start','leftstick','rightstick','leftshoulder','rightshoulder','dpup','dpdown','dpleft','dpright','lefttrigger','righttrigger','leftx-','leftx+','lefty-','lefty+','rightx-','rightx+','righty-','righty+')
    $labels=[ordered]@{ a='A'; b='B'; x='X'; y='Y'; l='L'; r='R'; zl='ZL'; zr='ZR'; start='Start'; select='Select'; up='D-Pad Up'; down='D-Pad Down'; left='D-Pad Left'; right='D-Pad Right'; circle_up='Circle Pad Up (left stick)'; circle_down='Circle Pad Down (left stick)'; circle_left='Circle Pad Left (left stick)'; circle_right='Circle Pad Right (left stick)'; touch_toggle='Touch cursor'; touch_press='Touch / drag'; swap_screens='Swap Screens'; layout='Layout' }
    foreach ($id in $labels.Keys) {
        $row=New-Object Windows.Controls.Grid; $row.Margin='0,3'
        foreach ($width in @('2*','*','*')) { $col=New-Object Windows.Controls.ColumnDefinition; $col.Width=$width; [void]$row.ColumnDefinitions.Add($col) }
        $label=New-Object Windows.Controls.TextBlock; $label.Text=$labels[$id]; $label.VerticalAlignment='Center'; [void]$row.Children.Add($label)
        $key=New-Object Windows.Controls.Button; $key.Tag=$id; $key.Content=[string]$script:FLInput.Values['key_'+$id]; $key.MinHeight=28; [Windows.Controls.Grid]::SetColumn($key,1)
        $key.Add_Click({ param($sender) $script:FLInput.Waiting=$sender.Tag; $sender.Content='Press a key...'; $script:FLInput.Status.Text='Press a key (Escape cancels, Delete clears).' })
        $script:FLInput.Keys[$id]=$key; [void]$row.Children.Add($key)
        if ($id -notin @('swap_screens','layout')) {
            $pad=New-Object Windows.Controls.ComboBox; $pad.Tag=$id; $pad.Margin='8,0,0,0'
            foreach ($choice in $padChoices) { [void]$pad.Items.Add($choice) }
            $pad.SelectedItem=[string]$script:FLInput.Values['pad_'+$id]
            $script:FLInput.Pads[$id]=$pad; [Windows.Controls.Grid]::SetColumn($pad,2); [void]$row.Children.Add($pad)
        } else {
            $hint=New-Object Windows.Controls.TextBlock; $hint.Text='Keyboard shortcut'; $hint.Margin='8,5,0,0'; [Windows.Controls.Grid]::SetColumn($hint,2); [void]$row.Children.Add($hint)
        }
        [void]$script:FLInput.Rows.Children.Add($row)
    }
    $script:FLInput.Refresh={
        foreach ($id in $script:FLInput.Keys.Keys) { $script:FLInput.Keys[$id].Content=[string]$script:FLInput.Values['key_'+$id] }
        foreach ($id in $script:FLInput.Pads.Keys) { $script:FLInput.Pads[$id].SelectedItem=[string]$script:FLInput.Values['pad_'+$id] }
        $script:FLInput.Convention.SelectedIndex=if ($script:FLInput.Values.pad_mapping -eq 'by_position') { 0 } else { 1 }
    }
    $w.Add_PreviewKeyDown({ param($sender,$e)
        if (-not $script:FLInput.Waiting) { return }
        $id=$script:FLInput.Waiting
        if ($e.Key -ne 'Escape') { $script:FLInput.Values['key_'+$id]=if ($e.Key -eq 'Delete') { '' } else { ConvertTo-FLSDLKey $(if ($e.Key -eq 'System') { $e.SystemKey } else { $e.Key }) } }
        $script:FLInput.Waiting=$null; & $script:FLInput.Refresh; $e.Handled=$true
    })
    $w.FindName('Reset').Add_Click({ $script:FLInput.Values=Get-FLControlDefaults; & $script:FLInput.Refresh })
    $w.FindName('ApplyPreset').Add_Click({
        $v=Get-FLControlDefaults; $p=[string]$script:FLInput.Preset.SelectedItem
        # SDL normalizes Xbox, PlayStation and Nintendo devices to physical positions;
        # Presets pin their face buttons; other auto bindings use the detected device.
        $v.pad_mapping=if ($script:FLInput.Convention.SelectedIndex -eq 0) { 'by_position' } else { 'by_label' }
        if ($p -notlike 'Keyboard*') {
            $eastA=($v.pad_mapping -eq 'by_position' -or $p -eq 'Nintendo Switch Pro')
            $v.pad_a=if ($eastA) { 'east' } else { 'south' }
            $v.pad_b=if ($eastA) { 'south' } else { 'east' }
            $v.pad_x='north'; $v.pad_y='west'; $v.pad_touch_press=$v.pad_a
        }
        if ($p -like 'Keyboard*') {
            foreach ($id in $script:FLInput.Pads.Keys) { $v['pad_'+$id]='' }
            if ($p -like '*Arrow*') { $v.key_circle_up='Up'; $v.key_circle_down='Down'; $v.key_circle_left='Left'; $v.key_circle_right='Right'; $v.key_up='W'; $v.key_down='S'; $v.key_left='A'; $v.key_right='D' }
        }
        $script:FLInput.Values=$v; & $script:FLInput.Refresh; $script:FLInput.Status.Text="$p preset applied. Save to keep it."
    })
    $w.FindName('Save').Add_Click({
        if ($script:FLInput.Preview) { $script:FLInput.Status.Text='Preview: settings are not written.'; return }
        $v=$script:FLInput.Values; $v.pad_mapping=if ($script:FLInput.Convention.SelectedIndex -eq 0) { 'by_position' } else { 'by_label' }
        foreach ($id in $script:FLInput.Pads.Keys) { $v['pad_'+$id]=[string]$script:FLInput.Pads[$id].SelectedItem }
        Set-FLControlSettings $v; $script:FLInput.Window.Close()
    })
    $w.FindName('Cancel').Add_Click({ $script:FLInput.Window.Close() })
    $w.FindName('Advanced').Add_Click({
        if ($script:FLInput.Preview) { return }
        & $script:FL.Launch 'settings'
    })
    if ($Preview) { $w.Show(); return $w }
    [void]$w.ShowDialog()
}
