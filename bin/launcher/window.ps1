# Fantasy Life PC - launcher window (WPF, Windows PowerShell 5.1, no extra dependencies).
#
# Dot-sourced by play.ps1, which defines $Here, $PlayScript and the Get-FL*/Start-FL*/
# Invoke-FL* library functions. Slow work (update check, update, firewall, icon) runs
# in background runspaces that dot-source "play.ps1 -LibraryOnly"; the UI polls their
# results with a DispatcherTimer, so the window never freezes and Play is always
# available, even offline.
#
# This file is saved as UTF-8 with BOM (Windows PowerShell reads BOM-less files as ANSI).

$script:FLLauncherXaml = @'
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Title="Fantasy Life" Width="660" SizeToContent="Height" WindowStyle="None"
        AllowsTransparency="True" Background="Transparent" ResizeMode="CanMinimize"
        WindowStartupLocation="CenterScreen" FontFamily="Segoe UI" FontSize="13"
        UseLayoutRounding="True" SnapsToDevicePixels="True">
  <Window.Resources>
    <SolidColorBrush x:Key="Ink" Color="#4A3420"/>
    <SolidColorBrush x:Key="InkSoft" Color="#8A6E50"/>
    <SolidColorBrush x:Key="CardLine" Color="#E7D2A6"/>

    <Style x:Key="BaseButton" TargetType="Button">
      <Setter Property="Cursor" Value="Hand"/>
      <Setter Property="Foreground" Value="#4A3420"/>
      <Setter Property="Background" Value="#FFFDF7"/>
      <Setter Property="BorderBrush" Value="#D6BC8C"/>
      <Setter Property="BorderThickness" Value="1.5"/>
      <Setter Property="Padding" Value="16,9"/>
      <Setter Property="HorizontalContentAlignment" Value="Center"/>
      <Setter Property="FocusVisualStyle" Value="{x:Null}"/>
      <Setter Property="Template">
        <Setter.Value>
          <ControlTemplate TargetType="Button">
            <Grid>
              <Border CornerRadius="14" Background="#2A5A3A1A" Margin="0,3,0,-3"/>
              <Grid x:Name="Lift">
                <Grid.RenderTransform><TranslateTransform x:Name="LiftShift" Y="0"/></Grid.RenderTransform>
                <Border x:Name="Face" CornerRadius="14" Background="{TemplateBinding Background}"
                        BorderBrush="{TemplateBinding BorderBrush}" BorderThickness="{TemplateBinding BorderThickness}"
                        Padding="{TemplateBinding Padding}">
                  <ContentPresenter HorizontalAlignment="{TemplateBinding HorizontalContentAlignment}" VerticalAlignment="Center"/>
                </Border>
                <Border x:Name="Shine" CornerRadius="14" Background="White" Opacity="0" IsHitTestVisible="False"/>
              </Grid>
            </Grid>
            <ControlTemplate.Triggers>
              <Trigger Property="IsMouseOver" Value="True"><Setter TargetName="Shine" Property="Opacity" Value="0.16"/></Trigger>
              <Trigger Property="IsKeyboardFocused" Value="True"><Setter TargetName="Shine" Property="Opacity" Value="0.12"/></Trigger>
              <Trigger Property="IsPressed" Value="True">
                <Setter TargetName="Lift" Property="RenderTransform"><Setter.Value><TranslateTransform Y="2"/></Setter.Value></Setter>
              </Trigger>
              <Trigger Property="IsEnabled" Value="False"><Setter Property="Opacity" Value="0.45"/></Trigger>
            </ControlTemplate.Triggers>
          </ControlTemplate>
        </Setter.Value>
      </Setter>
    </Style>

    <Style x:Key="PlayButton" TargetType="Button" BasedOn="{StaticResource BaseButton}">
      <Setter Property="Foreground" Value="White"/>
      <Setter Property="BorderBrush" Value="#3E7D24"/>
      <Setter Property="Background">
        <Setter.Value>
          <LinearGradientBrush StartPoint="0,0" EndPoint="0,1">
            <GradientStop Color="#8CCB5A" Offset="0"/>
            <GradientStop Color="#56A133" Offset="1"/>
          </LinearGradientBrush>
        </Setter.Value>
      </Setter>
    </Style>

    <Style x:Key="GoldButton" TargetType="Button" BasedOn="{StaticResource BaseButton}">
      <Setter Property="Foreground" Value="#4A2E0C"/>
      <Setter Property="FontWeight" Value="SemiBold"/>
      <Setter Property="BorderBrush" Value="#C98A16"/>
      <Setter Property="Padding" Value="18,8"/>
      <Setter Property="Background">
        <Setter.Value>
          <LinearGradientBrush StartPoint="0,0" EndPoint="0,1">
            <GradientStop Color="#FFDB7A" Offset="0"/>
            <GradientStop Color="#F2AE2E" Offset="1"/>
          </LinearGradientBrush>
        </Setter.Value>
      </Setter>
    </Style>

    <Style x:Key="LinkButton" TargetType="Button">
      <Setter Property="Cursor" Value="Hand"/>
      <Setter Property="Foreground" Value="#7A5A34"/>
      <Setter Property="FocusVisualStyle" Value="{x:Null}"/>
      <Setter Property="Template">
        <Setter.Value>
          <ControlTemplate TargetType="Button">
            <Border x:Name="Pill" CornerRadius="9" Background="Transparent" Padding="8,4">
              <ContentPresenter VerticalAlignment="Center"/>
            </Border>
            <ControlTemplate.Triggers>
              <Trigger Property="IsMouseOver" Value="True"><Setter TargetName="Pill" Property="Background" Value="#22B07A2E"/></Trigger>
              <Trigger Property="IsEnabled" Value="False"><Setter Property="Opacity" Value="0.45"/></Trigger>
            </ControlTemplate.Triggers>
          </ControlTemplate>
        </Setter.Value>
      </Setter>
    </Style>

    <Style x:Key="ChromeButton" TargetType="Button">
      <Setter Property="Cursor" Value="Hand"/>
      <Setter Property="Foreground" Value="White"/>
      <Setter Property="Width" Value="30"/>
      <Setter Property="Height" Value="30"/>
      <Setter Property="FocusVisualStyle" Value="{x:Null}"/>
      <Setter Property="Template">
        <Setter.Value>
          <ControlTemplate TargetType="Button">
            <Border x:Name="Disc" CornerRadius="15" Background="#26FFFFFF">
              <ContentPresenter HorizontalAlignment="Center" VerticalAlignment="Center"/>
            </Border>
            <ControlTemplate.Triggers>
              <Trigger Property="IsMouseOver" Value="True"><Setter TargetName="Disc" Property="Background" Value="#55FFFFFF"/></Trigger>
            </ControlTemplate.Triggers>
          </ControlTemplate>
        </Setter.Value>
      </Setter>
    </Style>

    <Style x:Key="ProfileToggle" TargetType="RadioButton">
      <Setter Property="Cursor" Value="Hand"/>
      <Setter Property="Foreground" Value="#6B4F2E"/>
      <Setter Property="FontWeight" Value="SemiBold"/>
      <Setter Property="Margin" Value="0,0,8,0"/>
      <Setter Property="FocusVisualStyle" Value="{x:Null}"/>
      <Setter Property="Template">
        <Setter.Value>
          <ControlTemplate TargetType="RadioButton">
            <Border x:Name="Pill" CornerRadius="15" Padding="16,6" Background="#FFFDF7" BorderBrush="#DCC398" BorderThickness="1.5">
              <ContentPresenter VerticalAlignment="Center"/>
            </Border>
            <ControlTemplate.Triggers>
              <Trigger Property="IsMouseOver" Value="True"><Setter TargetName="Pill" Property="BorderBrush" Value="#C99A45"/></Trigger>
              <Trigger Property="IsChecked" Value="True">
                <Setter TargetName="Pill" Property="Background" Value="#FFE29A"/>
                <Setter TargetName="Pill" Property="BorderBrush" Value="#D69A22"/>
                <Setter Property="Foreground" Value="#4A2E0C"/>
              </Trigger>
            </ControlTemplate.Triggers>
          </ControlTemplate>
        </Setter.Value>
      </Setter>
    </Style>

    <Style x:Key="Card" TargetType="Border">
      <Setter Property="CornerRadius" Value="16"/>
      <Setter Property="Background" Value="#D9FFFFFF"/>
      <Setter Property="BorderBrush" Value="{StaticResource CardLine}"/>
      <Setter Property="BorderThickness" Value="1"/>
      <Setter Property="Padding" Value="18,14"/>
      <Setter Property="Margin" Value="0,0,0,12"/>
    </Style>
  </Window.Resources>

  <Border x:Name="Frame" Margin="16" CornerRadius="22" BorderBrush="#C9A56B" BorderThickness="1">
    <Border.Effect><DropShadowEffect BlurRadius="22" ShadowDepth="4" Opacity="0.35" Color="#3A2410"/></Border.Effect>
    <Border.Background>
      <LinearGradientBrush StartPoint="0,0" EndPoint="0,1">
        <GradientStop Color="#FFFCF3" Offset="0"/>
        <GradientStop Color="#F7E8C8" Offset="1"/>
      </LinearGradientBrush>
    </Border.Background>
    <Grid>
      <Grid.RowDefinitions>
        <RowDefinition Height="Auto"/>
        <RowDefinition Height="Auto"/>
        <RowDefinition Height="Auto"/>
      </Grid.RowDefinitions>

      <!-- Header: sky, clouds, hills, emblem and title -->
      <Grid x:Name="Header" Height="168" ClipToBounds="True">
        <Border CornerRadius="21,21,0,0">
          <Border.Background>
            <LinearGradientBrush StartPoint="0,0" EndPoint="0,1">
              <GradientStop x:Name="SkyTop" Color="#7FC8F2" Offset="0"/>
              <GradientStop x:Name="SkyBottom" Color="#CDEBFA" Offset="1"/>
            </LinearGradientBrush>
          </Border.Background>
        </Border>
        <Canvas IsHitTestVisible="False">
          <Ellipse Canvas.Left="300" Canvas.Top="26" Width="96" Height="30" Fill="White" Opacity="0.55"/>
          <Ellipse Canvas.Left="330" Canvas.Top="12" Width="64" Height="38" Fill="White" Opacity="0.55"/>
          <Ellipse Canvas.Left="470" Canvas.Top="58" Width="110" Height="28" Fill="White" Opacity="0.45"/>
          <Ellipse Canvas.Left="505" Canvas.Top="44" Width="58" Height="34" Fill="White" Opacity="0.45"/>
          <Path Data="M -20,168 C 120,112 240,118 360,140 C 470,160 560,120 680,128 L 680,190 L -20,190 Z">
            <Path.Fill>
              <LinearGradientBrush StartPoint="0,0" EndPoint="0,1">
                <GradientStop x:Name="HillBackTop" Color="#A9D97A" Offset="0"/>
                <GradientStop x:Name="HillBackBottom" Color="#86C25A" Offset="1"/>
              </LinearGradientBrush>
            </Path.Fill>
          </Path>
          <Path Data="M -20,176 C 160,140 300,150 420,162 C 520,172 600,150 680,152 L 680,190 L -20,190 Z">
            <Path.Fill>
              <LinearGradientBrush StartPoint="0,0" EndPoint="0,1">
                <GradientStop x:Name="HillFrontTop" Color="#7DBE4E" Offset="0"/>
                <GradientStop x:Name="HillFrontBottom" Color="#5FA238" Offset="1"/>
              </LinearGradientBrush>
            </Path.Fill>
          </Path>
        </Canvas>
        <StackPanel Orientation="Horizontal" Margin="26,24,0,0" VerticalAlignment="Top">
          <Border Width="96" Height="96" CornerRadius="22" Background="White" BorderBrush="#E8D3A8" BorderThickness="2">
            <Border.Effect><DropShadowEffect BlurRadius="10" ShadowDepth="2" Opacity="0.3" Color="#2A4A6A"/></Border.Effect>
            <Image x:Name="Logo" Margin="3" RenderOptions.BitmapScalingMode="HighQuality"/>
          </Border>
          <StackPanel Margin="20,10,0,0">
            <TextBlock Text="Fantasy Life" FontFamily="Georgia" FontSize="40" FontWeight="Bold" Foreground="White">
              <TextBlock.Effect><DropShadowEffect BlurRadius="6" ShadowDepth="2" Opacity="0.55" Color="#1E3A5A"/></TextBlock.Effect>
            </TextBlock>
            <TextBlock x:Name="Subtitle" Text="PC Edition" FontSize="15" FontWeight="SemiBold" Foreground="White" Margin="2,0,0,0">
              <TextBlock.Effect><DropShadowEffect BlurRadius="4" ShadowDepth="1" Opacity="0.5" Color="#1E3A5A"/></TextBlock.Effect>
            </TextBlock>
          </StackPanel>
        </StackPanel>
        <Border x:Name="ChannelBadge" HorizontalAlignment="Right" VerticalAlignment="Top" Margin="0,54,26,0"
                CornerRadius="12" Padding="14,5" Background="#E4572E" Visibility="Collapsed">
          <Border.Effect><DropShadowEffect BlurRadius="6" ShadowDepth="1" Opacity="0.35"/></Border.Effect>
          <TextBlock x:Name="ChannelText" Text="TEST BUILD" Foreground="White" FontWeight="Bold" FontSize="13"/>
        </Border>
        <StackPanel Orientation="Horizontal" HorizontalAlignment="Right" VerticalAlignment="Top" Margin="0,12,14,0">
          <Button x:Name="MinButton" Style="{StaticResource ChromeButton}" ToolTip="Minimize" Margin="0,0,6,0">
            <TextBlock Text="&#xE921;" FontFamily="Segoe MDL2 Assets" FontSize="10"/>
          </Button>
          <Button x:Name="CloseButton" Style="{StaticResource ChromeButton}" ToolTip="Close">
            <TextBlock Text="&#xE8BB;" FontFamily="Segoe MDL2 Assets" FontSize="10"/>
          </Button>
        </StackPanel>
      </Grid>

      <!-- Content -->
      <StackPanel Grid.Row="1" Margin="24,16,24,4">

        <!-- Notice: update hints, results, errors -->
        <Border x:Name="Notice" CornerRadius="14" Padding="14,10" Margin="0,0,0,12" BorderThickness="1.5"
                Background="#FFF3CF" BorderBrush="#E8B64A" Visibility="Collapsed">
          <Grid>
            <Grid.ColumnDefinitions>
              <ColumnDefinition Width="Auto"/>
              <ColumnDefinition Width="*"/>
              <ColumnDefinition Width="Auto"/>
            </Grid.ColumnDefinitions>
            <TextBlock x:Name="NoticeGlyph" Text="&#xE7BA;" FontFamily="Segoe MDL2 Assets" FontSize="18"
                       Foreground="#B7791F" Margin="0,1,12,0" VerticalAlignment="Top"/>
            <StackPanel Grid.Column="1">
              <TextBlock x:Name="NoticeTitle" FontWeight="Bold" FontSize="14" Foreground="#5A3A10" TextWrapping="Wrap"/>
              <TextBlock x:Name="NoticeText" Foreground="#6B4F2E" TextWrapping="Wrap" Margin="0,2,0,0"/>
              <TextBlock x:Name="NoticeLog" FontFamily="Consolas" FontSize="11" Foreground="#7A3B2E" TextWrapping="Wrap"
                         Margin="0,6,0,0" Visibility="Collapsed"/>
            </StackPanel>
            <StackPanel Grid.Column="2" Orientation="Horizontal" VerticalAlignment="Top" Margin="8,0,0,0">
              <Button x:Name="NoticeAction" Style="{StaticResource LinkButton}" Visibility="Collapsed">
                <TextBlock x:Name="NoticeActionText" Text="Open log" FontWeight="SemiBold"/>
              </Button>
              <Button x:Name="NoticeClose" Style="{StaticResource LinkButton}" ToolTip="Dismiss">
                <TextBlock Text="&#xE711;" FontFamily="Segoe MDL2 Assets" FontSize="11"/>
              </Button>
            </StackPanel>
          </Grid>
        </Border>

        <!-- Version and update -->
        <Border Style="{StaticResource Card}">
          <Grid>
            <Grid.ColumnDefinitions>
              <ColumnDefinition Width="*"/>
              <ColumnDefinition Width="Auto"/>
            </Grid.ColumnDefinitions>
            <Grid.RowDefinitions>
              <RowDefinition Height="Auto"/>
              <RowDefinition Height="Auto"/>
            </Grid.RowDefinitions>
            <StackPanel>
              <StackPanel Orientation="Horizontal">
                <Ellipse x:Name="StatusDot" Width="11" Height="11" Fill="#B9A88E" Margin="0,1,9,0" VerticalAlignment="Center"/>
                <TextBlock x:Name="StatusTitle" Text="Checking for updates..." FontSize="16" FontWeight="Bold" Foreground="{StaticResource Ink}"/>
              </StackPanel>
              <TextBlock x:Name="StatusDetail" Foreground="{StaticResource InkSoft}" TextWrapping="Wrap" Margin="20,3,0,0"/>
              <TextBox x:Name="VersionText" IsReadOnly="True" BorderThickness="0" Background="Transparent" Padding="0"
                       Foreground="#A68D6C" FontSize="11" Margin="20,3,0,0" TextWrapping="Wrap" Cursor="IBeam"/>
            </StackPanel>
            <Button x:Name="UpdateButton" Grid.Column="1" Style="{StaticResource GoldButton}" VerticalAlignment="Center"
                    Margin="14,0,0,0" Visibility="Collapsed">
              <StackPanel Orientation="Horizontal">
                <TextBlock Text="&#xE896;" FontFamily="Segoe MDL2 Assets" FontSize="14" Margin="0,1,8,0"/>
                <TextBlock x:Name="UpdateButtonText" Text="Update now"/>
              </StackPanel>
            </Button>
            <StackPanel x:Name="ProgressPanel" Grid.Row="1" Grid.ColumnSpan="2" Margin="20,10,0,0" Visibility="Collapsed">
              <ProgressBar x:Name="Progress" Height="10" Minimum="0" Maximum="100" Foreground="#F2AE2E" Background="#F3E4C2" BorderThickness="0"/>
              <TextBlock x:Name="ProgressText" Foreground="{StaticResource InkSoft}" FontSize="12" Margin="0,4,0,0"/>
            </StackPanel>
          </Grid>
        </Border>

        <!-- Save profile and mods -->
        <Border Style="{StaticResource Card}">
          <StackPanel>
            <Grid>
              <Grid.ColumnDefinitions>
                <ColumnDefinition Width="92"/>
                <ColumnDefinition Width="*"/>
              </Grid.ColumnDefinitions>
              <TextBlock Text="Save" FontWeight="Bold" Foreground="{StaticResource Ink}" VerticalAlignment="Center" FontSize="14"/>
              <WrapPanel x:Name="ProfilePanel" Grid.Column="1"/>
            </Grid>
            <Grid Margin="0,12,0,0">
              <Grid.ColumnDefinitions>
                <ColumnDefinition Width="92"/>
                <ColumnDefinition Width="*"/>
              </Grid.ColumnDefinitions>
              <TextBlock Text="Mods" FontWeight="Bold" Foreground="{StaticResource Ink}" VerticalAlignment="Top" Margin="0,4,0,0" FontSize="14"/>
              <WrapPanel x:Name="ModChips" Grid.Column="1"/>
            </Grid>
          </StackPanel>
        </Border>

        <!-- Play -->
        <Grid Margin="0,2,0,6">
          <Grid.ColumnDefinitions>
            <ColumnDefinition Width="3*"/>
            <ColumnDefinition Width="12"/>
            <ColumnDefinition Width="2*"/>
          </Grid.ColumnDefinitions>
          <Button x:Name="PlayModsButton" Style="{StaticResource PlayButton}" IsDefault="True" MinHeight="74">
            <StackPanel Orientation="Horizontal" HorizontalAlignment="Center">
              <TextBlock Text="&#xE768;" FontFamily="Segoe MDL2 Assets" FontSize="24" VerticalAlignment="Center" Margin="0,0,14,0"/>
              <StackPanel VerticalAlignment="Center">
                <TextBlock Text="Play" FontSize="24" FontWeight="Bold" FontFamily="Georgia"/>
                <TextBlock x:Name="PlayModsSub" Text="with mods" FontSize="12" Opacity="0.95"/>
              </StackPanel>
            </StackPanel>
          </Button>
          <Button x:Name="PlayVanillaButton" Grid.Column="2" Style="{StaticResource BaseButton}" MinHeight="74">
            <StackPanel HorizontalAlignment="Center">
              <TextBlock Text="Play vanilla" FontSize="17" FontWeight="Bold" FontFamily="Georgia" HorizontalAlignment="Center"/>
              <TextBlock Text="original game, no mods" FontSize="12" Foreground="{StaticResource InkSoft}" HorizontalAlignment="Center"/>
            </StackPanel>
          </Button>
        </Grid>
        <TextBlock x:Name="PlayHint" Foreground="{StaticResource InkSoft}" FontSize="12" TextWrapping="Wrap" Margin="4,4,4,0"
                   Text="Multiplayer works between players on the same build who all play with mods, or all play vanilla."/>
      </StackPanel>

      <!-- Footer -->
      <Border Grid.Row="2" BorderBrush="#E4CFA3" BorderThickness="0,1,0,0" Margin="18,10,18,0" Padding="0,8,0,12">
        <Grid>
          <Grid.ColumnDefinitions>
            <ColumnDefinition Width="Auto"/>
            <ColumnDefinition Width="*"/>
          </Grid.ColumnDefinitions>
          <StackPanel Orientation="Horizontal">
            <Button x:Name="SettingsButton" Style="{StaticResource LinkButton}" ToolTip="Controls, resolution and online (relay) settings">
              <StackPanel Orientation="Horizontal">
                <TextBlock Text="&#xE713;" FontFamily="Segoe MDL2 Assets" Margin="0,2,6,0"/>
                <TextBlock Text="Game settings"/>
              </StackPanel>
            </Button>
            <Button x:Name="FirewallButton" Style="{StaticResource LinkButton}" ToolTip="Allow LAN / Hamachi / Radmin / ZeroTier multiplayer through Windows Firewall (one admin prompt)">
              <StackPanel Orientation="Horizontal">
                <TextBlock Text="&#xE83D;" FontFamily="Segoe MDL2 Assets" Margin="0,2,6,0"/>
                <TextBlock Text="Firewall"/>
              </StackPanel>
            </Button>
            <Button x:Name="LogButton" Style="{StaticResource LinkButton}" ToolTip="Open the game log">
              <StackPanel Orientation="Horizontal">
                <TextBlock Text="&#xE9F9;" FontFamily="Segoe MDL2 Assets" Margin="0,2,6,0"/>
                <TextBlock Text="Log"/>
              </StackPanel>
            </Button>
            <Button x:Name="FolderButton" Style="{StaticResource LinkButton}" ToolTip="Open the install folder">
              <StackPanel Orientation="Horizontal">
                <TextBlock Text="&#xE838;" FontFamily="Segoe MDL2 Assets" Margin="0,2,6,0"/>
                <TextBlock Text="Folder"/>
              </StackPanel>
            </Button>
          </StackPanel>
          <StackPanel Grid.Column="1" Orientation="Horizontal" HorizontalAlignment="Right" VerticalAlignment="Center">
            <Ellipse x:Name="NetDot" Width="8" Height="8" Fill="#B9A88E" Margin="0,1,6,0"/>
            <TextBlock x:Name="NetText" Text="Network: checking..." Foreground="{StaticResource InkSoft}" FontSize="12"/>
          </StackPanel>
        </Grid>
      </Border>
    </Grid>
  </Border>
</Window>
'@

# Body of every background job: load the library, then run the job text.
$script:FLJobPrelude = {
    param($PlayScript, $Queue, $JobName, $Body, $Params)
    $ErrorActionPreference = "Stop"
    . $PlayScript -LibraryOnly
    $Report = {
        param($Text, $Percent)
        $Queue.Enqueue([pscustomobject]@{ Job = $JobName; Text = [string]$Text; Percent = [int]$Percent })
    }.GetNewClosure()
    $job = [scriptblock]::Create($Body)
    if ($Params) { & $job @Params } else { & $job }
}

function Show-FLLauncherWindow {
    param(
        $Config,
        [string]$InitialSave = "",
        [switch]$NoUpdateCheck,
        [switch]$NoDlc,
        [switch]$NoFirewall,
        [string]$AfterUpdate = "",
        [switch]$Preview,
        [string]$Screenshot = ""
    )

    Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase, System.Xaml

    $window = [Windows.Markup.XamlReader]::Parse($script:FLLauncherXaml)
    $ui = @{}
    foreach ($name in @("Frame", "Header", "SkyTop", "SkyBottom", "HillBackTop", "HillBackBottom", "HillFrontTop", "HillFrontBottom",
                        "Logo", "Subtitle", "ChannelBadge", "ChannelText", "MinButton", "CloseButton",
                        "Notice", "NoticeGlyph", "NoticeTitle", "NoticeText", "NoticeLog", "NoticeAction", "NoticeActionText", "NoticeClose",
                        "StatusDot", "StatusTitle", "StatusDetail", "VersionText", "UpdateButton", "UpdateButtonText",
                        "ProgressPanel", "Progress", "ProgressText", "ProfilePanel", "ModChips",
                        "PlayModsButton", "PlayModsSub", "PlayVanillaButton", "PlayHint",
                        "SettingsButton", "FirewallButton", "LogButton", "FolderButton", "NetDot", "NetText")) {
        $ui[$name] = $window.FindName($name)
    }

    $script:FL = @{
        Window       = $window
        UI           = $ui
        Config       = $Config
        Queue        = New-Object 'System.Collections.Concurrent.ConcurrentQueue[object]'
        Jobs         = New-Object System.Collections.ArrayList
        Game         = $null
        GameKind     = ""
        ExitCode     = 0
        Busy         = $false
        Preview      = [bool]$Preview
        Screenshot   = $Screenshot
        NoDlc        = [bool]$NoDlc
        NoFirewall   = [bool]($NoFirewall -or $env:FL_NO_FIREWALL -eq "1")
        Status       = $null
        StatusDone   = $false
        Prefs        = $null
        PrefsFile    = Join-Path $Here "data\yw2-recomp\launcher.json"
        NoticeAction = $null
        Demo         = [string]$env:FL_LAUNCHER_DEMO
    }

    $brush = { param($hex) New-Object Windows.Media.SolidColorBrush ([Windows.Media.ColorConverter]::ConvertFromString($hex)) }
    $script:FL.Brush = $brush

    # ---- helpers -------------------------------------------------------
    $script:FL.SetNotice = {
        param([string]$Kind, [string]$Title, [string]$Text, [string]$LogText = "", [string]$ActionText = "", [scriptblock]$Action = $null)
        $u = $script:FL.UI
        $b = $script:FL.Brush
        switch ($Kind) {
            "error"   { $u.Notice.Background = & $b "#FDE6DF"; $u.Notice.BorderBrush = & $b "#E07A5F"; $u.NoticeGlyph.Text = [string][char]0xE783; $u.NoticeGlyph.Foreground = & $b "#C0452A"; $u.NoticeTitle.Foreground = & $b "#7A2414" }
            "success" { $u.Notice.Background = & $b "#E7F5DC"; $u.Notice.BorderBrush = & $b "#8CC46A"; $u.NoticeGlyph.Text = [string][char]0xE930; $u.NoticeGlyph.Foreground = & $b "#4E8F2E"; $u.NoticeTitle.Foreground = & $b "#2F5A1A" }
            "info"    { $u.Notice.Background = & $b "#E6F2FB"; $u.Notice.BorderBrush = & $b "#8BBCE3"; $u.NoticeGlyph.Text = [string][char]0xE946; $u.NoticeGlyph.Foreground = & $b "#2F6FA6"; $u.NoticeTitle.Foreground = & $b "#1F4A70" }
            default   { $u.Notice.Background = & $b "#FFF3CF"; $u.Notice.BorderBrush = & $b "#E8B64A"; $u.NoticeGlyph.Text = [string][char]0xE7BA; $u.NoticeGlyph.Foreground = & $b "#B7791F"; $u.NoticeTitle.Foreground = & $b "#5A3A10" }
        }
        $u.NoticeTitle.Text = $Title
        $u.NoticeText.Text = $Text
        $u.NoticeText.Visibility = $(if ($Text) { "Visible" } else { "Collapsed" })
        $u.NoticeLog.Text = $LogText
        $u.NoticeLog.Visibility = $(if ($LogText) { "Visible" } else { "Collapsed" })
        $script:FL.NoticeAction = $Action
        $u.NoticeActionText.Text = $ActionText
        $u.NoticeAction.Visibility = $(if ($Action) { "Visible" } else { "Collapsed" })
        $u.Notice.Visibility = "Visible"
    }

    $script:FL.StartJob = {
        param([string]$Name, [string]$Body, [hashtable]$Params, [scriptblock]$OnDone)
        $rs = [runspacefactory]::CreateRunspace()
        $rs.Open()
        $ps = [powershell]::Create()
        $ps.Runspace = $rs
        [void]$ps.AddScript($script:FLJobPrelude.ToString()).AddArgument($PlayScript).AddArgument($script:FL.Queue).AddArgument($Name).AddArgument($Body).AddArgument($Params)
        $handle = $ps.BeginInvoke()
        [void]$script:FL.Jobs.Add(@{ Name = $Name; PS = $ps; Handle = $handle; OnDone = $OnDone; Runspace = $rs })
    }

    $script:FL.FormatDate = {
        param($Text)
        if (-not $Text) { return "" }
        try {
            $d = [DateTime]::Parse([string]$Text, [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::AdjustToUniversal -bor [Globalization.DateTimeStyles]::AssumeUniversal)
            return $d.ToLocalTime().ToString("d MMM yyyy, HH:mm", [Globalization.CultureInfo]::InvariantCulture)
        } catch { return [string]$Text }
    }

    $script:FL.LoadLogo = {
        $candidates = @((Join-Path $Here "data\yw2-recomp\icon.png"), (Join-Path $Here "bin\fantasy-life.png"))
        foreach ($png in $candidates) {
            if (Test-Path -LiteralPath $png) {
                try {
                    $img = New-Object Windows.Media.Imaging.BitmapImage
                    $img.BeginInit()
                    $img.CacheOption = [Windows.Media.Imaging.BitmapCacheOption]::OnLoad
                    $img.CreateOptions = [Windows.Media.Imaging.BitmapCreateOptions]::IgnoreImageCache
                    $img.UriSource = New-Object Uri $png
                    $img.EndInit()
                    $script:FL.UI.Logo.Source = $img
                    $script:FL.Window.Icon = $img
                    return
                } catch {}
            }
        }
    }

    $script:FL.SetBusy = {
        param([bool]$Busy)
        $script:FL.Busy = $Busy
        $u = $script:FL.UI
        foreach ($c in @($u.PlayModsButton, $u.PlayVanillaButton, $u.SettingsButton, $u.UpdateButton, $u.FirewallButton)) { $c.IsEnabled = -not $Busy }
        if (-not $Busy) { & $script:FL.RefreshPlayButtons }
    }

    $script:FL.SavePrefs = {
        try {
            $obj = [ordered]@{ save = $script:FL.SelectedSave }
            New-Item -ItemType Directory -Path (Split-Path -Parent $script:FL.PrefsFile) -Force | Out-Null
            [IO.File]::WriteAllText($script:FL.PrefsFile, ($obj | ConvertTo-Json), (New-Object Text.UTF8Encoding($false)))
        } catch {}
    }

    # ---- static info: version, mods, profiles ------------------------------
    $local = Get-FLLocalVersion -Config $Config
    $script:FL.LocalVersion = $local
    $modInfo = Get-FLMods -Config $Config -LocalVersion $local
    $script:FL.Mods = @($modInfo.Mods)

    if ($Config.IsTest) {
        $ui.SkyTop.Color = [Windows.Media.ColorConverter]::ConvertFromString("#F7A35C")
        $ui.SkyBottom.Color = [Windows.Media.ColorConverter]::ConvertFromString("#FDE1B8")
        $ui.ChannelBadge.Visibility = "Visible"
        $ui.ChannelText.Text = "TEST BUILD"
        $label = if ($local -and $local.label) { [string]$local.label } else { "unlabeled" }
        $ui.Subtitle.Text = "Test: $label"
        $window.Title = "Fantasy Life (Test)"
        $ui.Frame.BorderBrush = & $brush "#E4572E"
        $ui.Frame.BorderThickness = New-Object Windows.Thickness 2
    }

    # Save profiles: freelife and story, plus any other existing profile folder.
    $profiles = New-Object System.Collections.ArrayList
    foreach ($p in @("freelife", "story")) { [void]$profiles.Add($p) }
    foreach ($dir in @(Get-ChildItem -LiteralPath (Join-Path $Here "saves") -Directory -ErrorAction SilentlyContinue | Sort-Object Name)) {
        if ((Test-FLSaveName $dir.Name) -and -not $profiles.Contains($dir.Name) -and $profiles.Count -lt 6) { [void]$profiles.Add($dir.Name) }
    }
    $prefs = Read-FLJson $script:FL.PrefsFile
    $selected = "freelife"
    if ($prefs -and $prefs.save -and (Test-FLSaveName ([string]$prefs.save))) { $selected = [string]$prefs.save }
    if ($InitialSave) {
        if (-not (Test-FLSaveName $InitialSave)) { throw "Invalid save profile name: $InitialSave" }
        $selected = $InitialSave
    }
    if (-not $profiles.Contains($selected)) { [void]$profiles.Add($selected) }
    $script:FL.SelectedSave = $selected
    foreach ($p in $profiles) {
        $rb = New-Object Windows.Controls.RadioButton
        $rb.Style = $window.FindResource("ProfileToggle")
        $rb.GroupName = "Save"
        $rb.Tag = $p
        $rb.Content = $(switch ($p) { "freelife" { "Free Life" } "story" { "Story" } default { $p } })
        $rb.ToolTip = "saves\$p"
        $rb.Margin = New-Object Windows.Thickness 0, 0, 8, 6
        if ($p -eq $selected) { $rb.IsChecked = $true }
        $rb.Add_Checked({ param($s, $e) $script:FL.SelectedSave = [string]$s.Tag })
        [void]$ui.ProfilePanel.Children.Add($rb)
    }

    # Mod chips (later: make these toggles for per-mod picking).
    $missing = @($script:FL.Mods | Where-Object { -not $_.Present })
    if ($script:FL.Mods.Count -eq 0) {
        $t = New-Object Windows.Controls.TextBlock
        $t.Text = "This build has no mods."
        $t.Foreground = & $brush "#8A6E50"
        $t.Margin = New-Object Windows.Thickness 0, 4, 0, 0
        [void]$ui.ModChips.Children.Add($t)
    }
    foreach ($mod in $script:FL.Mods) {
        $chip = New-Object Windows.Controls.Border
        $chip.CornerRadius = New-Object Windows.CornerRadius 11
        $chip.Padding = New-Object Windows.Thickness 11, 4, 11, 4
        $chip.Margin = New-Object Windows.Thickness 0, 0, 6, 6
        $chip.BorderThickness = New-Object Windows.Thickness 1
        if ($mod.Present) {
            $chip.Background = & $brush "#EAF5DD"; $chip.BorderBrush = & $brush "#A9CF86"
        } else {
            $chip.Background = & $brush "#FDE6DF"; $chip.BorderBrush = & $brush "#E07A5F"
        }
        $t = New-Object Windows.Controls.TextBlock
        $t.Text = $(if ($mod.Present) { $mod.Name } else { "$($mod.Name) (missing)" })
        $t.Foreground = & $brush "#3F5E26"
        $t.FontSize = 12
        $t.FontWeight = "SemiBold"
        $chip.Child = $t
        $chip.ToolTip = "data\yw2-recomp\mods\fantasylife\$($mod.Folder)"
        [void]$ui.ModChips.Children.Add($chip)
    }
    $count = $script:FL.Mods.Count
    $ui.PlayModsSub.Text = $(if ($count -eq 0) { "this build has no mods" } elseif ($count -eq 1) { "with 1 mod" } else { "with $count mods" })
    $script:FL.ModsBlocked = ($missing.Count -gt 0)

    $script:FL.RefreshPlayButtons = {
        $u = $script:FL.UI
        $u.PlayModsButton.IsEnabled = -not $script:FL.ModsBlocked
        $u.PlayVanillaButton.IsEnabled = $true
        $u.SettingsButton.IsEnabled = $true
        $u.FirewallButton.IsEnabled = $true
    }
    & $script:FL.RefreshPlayButtons

    # Installed version line
    if ($Config.IsTest) {
        $ui.StatusDot.Fill = & $brush "#E4572E"
        $ui.StatusTitle.Text = "Test build"
        $parts = @()
        if ($local -and $local.date) { $parts += "published " + (& $script:FL.FormatDate $local.date) }
        $parts += "local only, never updates"
        $ui.StatusDetail.Text = ($parts -join " - ")
        $vt = @()
        if ($local -and $local.label) { $vt += "Label: $($local.label)" }
        if ($local -and $local.exe_sha256) { $vt += "exe $(([string]$local.exe_sha256).Substring(0, [Math]::Min(12, ([string]$local.exe_sha256).Length)))" }
        $ui.VersionText.Text = ($vt -join "  |  ")
    } else {
        if ($local) {
            $ui.StatusDetail.Text = "Installed build from " + (& $script:FL.FormatDate $local.updated_at)
            $ui.VersionText.Text = "Build $($local.version)  |  mod digest $($local.mod_digest)"
        } else {
            $ui.StatusDetail.Text = "No version.json found."
        }
    }

    if ($modInfo.Note) { & $script:FL.SetNotice "warn" "Mod list" $modInfo.Note }
    if ($missing.Count -gt 0) {
        & $script:FL.SetNotice "error" "Some mods are missing" ("Missing: " + (@($missing | ForEach-Object { $_.Folder }) -join ", ") + ". Update the game, or play vanilla.")
    }
    if ($AfterUpdate) {
        $now = if ($local -and $local.version) { [string]$local.version } else { "the latest build" }
        & $script:FL.SetNotice "success" "Updated!" "You are now on $now."
    }

    & $script:FL.LoadLogo

    # ---- update status -------------------------------------------------
    $script:FL.ApplyStatus = {
        param($Status)
        $u = $script:FL.UI
        $b = $script:FL.Brush
        $script:FL.Status = $Status
        $script:FL.StatusDone = $true
        $u.UpdateButton.Visibility = "Collapsed"
        switch ($Status.State) {
            "Test" { return }
            "UpToDate" {
                $u.StatusDot.Fill = & $b "#58A83A"
                $u.StatusTitle.Text = "Up to date"
            }
            "Available" {
                $u.StatusDot.Fill = & $b "#F0A020"
                $u.StatusTitle.Text = "Update available"
                $u.UpdateButtonText.Text = "Update now"
                $u.UpdateButton.Visibility = "Visible"
                $newText = "A new build is ready."
                if ($Status.RemoteVersion) {
                    $when = & $script:FL.FormatDate $Status.RemoteVersion.updated_at
                    $newText = "New build from $when is ready."
                    $u.VersionText.Text = $u.VersionText.Text + "`nNew: $($Status.RemoteVersion.version)"
                }
                if ($u.Notice.Visibility -ne "Visible") {
                    & $script:FL.SetNotice "warn" "Your game is out of date" ($newText + " Update before playing together: multiplayer needs everyone on the same build and mods.")
                }
            }
            "Ahead" {
                $u.StatusDot.Fill = & $b "#3D8BD9"
                $u.StatusTitle.Text = "Local build (not published yet)"
            }
            "Offline" {
                $u.StatusDot.Fill = & $b "#B9A88E"
                $u.StatusTitle.Text = "Couldn't check for updates"
                $u.StatusDetail.Text = $Status.Message + " You can still play."
                $u.UpdateButtonText.Text = "Check again"
                $u.UpdateButton.Visibility = "Visible"
            }
            "Skipped" {
                $u.StatusDot.Fill = & $b "#B9A88E"
                $u.StatusTitle.Text = "Update check skipped"
            }
            default {
                $u.StatusDot.Fill = & $b "#B9A88E"
                $u.StatusTitle.Text = "Updates not set up"
                if ($Status.Message) { $u.StatusDetail.Text = $Status.Message }
            }
        }
    }

    $script:FL.CheckUpdates = {
        $u = $script:FL.UI
        $script:FL.StatusDone = $false
        $u.StatusDot.Fill = & $script:FL.Brush "#B9A88E"
        $u.StatusTitle.Text = "Checking for updates..."
        $u.UpdateButton.Visibility = "Collapsed"
        & $script:FL.StartJob "status" 'Get-FLUpdateStatus -Config (Get-FLConfig)' $null {
            param($Result, $ErrorText)
            if ($ErrorText -or -not $Result) {
                & $script:FL.ApplyStatus ([pscustomobject]@{ State = "Offline"; Message = "Update check failed." })
            } else {
                & $script:FL.ApplyStatus $Result
            }
        }
    }

    # ---- game launch -------------------------------------------------------
    $script:FL.Launch = {
        param([string]$Kind)   # mods | vanilla | settings
        $u = $script:FL.UI
        $cfg = $script:FL.Config
        $rom = Get-FLRomPath
        $exe = Get-FLExePath -Config $cfg
        if (-not $rom) {
            & $script:FL.SetNotice "error" "Game dump not found" "Place FantasyLife_EU.3ds in $(Join-Path $Here 'game')\ and try again."
            return
        }
        if (-not $exe) {
            & $script:FL.SetNotice "error" "Game program not found" "bin\fl_eur.exe is missing. Update the game (or re-run publish-test.ps1 for a test install)."
            return
        }
        $mods = @()
        if ($Kind -ne "vanilla") { $mods = @($script:FL.Mods | Where-Object { $_.Present } | ForEach-Object { $_.Path }) }
        & $script:FL.SavePrefs
        $save = $script:FL.SelectedSave
        $what = $(switch ($Kind) { "mods" { "with $($mods.Count) mod(s)" } "vanilla" { "vanilla (no mods)" } default { "game settings" } })
        Write-FLLauncherLog "Launch $Kind save=$save mods=$($mods -join ';')"
        if ($script:FL.Preview) {
            & $script:FL.SetNotice "info" "Preview mode" "Would start $what with save '$save'. FL_MOD_DIRS=`"$($mods -join ';')`""
            return
        }
        Initialize-FLSettings
        $dlc = Get-FLDlcPath
        try {
            $started = Start-FLGame -SaveName $save -ModDirs $mods -SettingsLauncher:($Kind -eq "settings") -NoDlc:$script:FL.NoDlc `
                -ExePath $exe -RomPath $rom -DlcPath $(if ($dlc) { $dlc } else { "" }) -NoWindow
        } catch {
            & $script:FL.SetNotice "error" "Could not start the game" $_.Exception.Message
            Write-FLLauncherLog "Launch failed: $($_.Exception.Message)"
            return
        }
        $script:FL.Game = $started
        $script:FL.GameKind = $Kind
        $script:FL.Window.Hide()
    }

    $script:FL.OnGameExit = {
        $started = $script:FL.Game
        $kind = $script:FL.GameKind
        $script:FL.Game = $null
        $code = 0
        try { $code = $started.Process.ExitCode } catch { $code = 0 }
        Write-FLLauncherLog "Game ($kind) exited with code $code"
        if ($code -eq 0 -and $kind -ne "settings") {
            $script:FL.ExitCode = 0
            $script:FL.Window.Close()
            return
        }
        if ($code -ne 0) {
            $tail = ""
            try { $tail = (Get-Content -LiteralPath $started.LogFile -Tail 8 -ErrorAction Stop) -join "`n" } catch {}
            $logFile = $started.LogFile
            & $script:FL.SetNotice "error" "Fantasy Life closed with an error (code $code)" "The last lines of $(Split-Path -Leaf $logFile):" $tail "Open log" ({ Start-Process notepad.exe -ArgumentList "`"$logFile`"" }.GetNewClosure())
        }
        $script:FL.Window.Show()
        $script:FL.Window.Activate() | Out-Null
    }

    # ---- update -------------------------------------------------------
    $script:FL.RunUpdate = {
        $u = $script:FL.UI
        if ($script:FL.Status -and $script:FL.Status.State -eq "Offline") { & $script:FL.CheckUpdates; return }
        if ((Get-FLRunningGames).Count -gt 0) {
            & $script:FL.SetNotice "warn" "Close Fantasy Life first" "The game is still running from this install; close it, then update."
            return
        }
        & $script:FL.SetBusy $true
        $u.Notice.Visibility = "Collapsed"
        $u.ProgressPanel.Visibility = "Visible"
        $u.Progress.IsIndeterminate = $true
        $u.ProgressText.Text = "Starting update..."
        $u.StatusTitle.Text = "Updating..."
        $script:FL.OldVersion = $(if ($script:FL.LocalVersion -and $script:FL.LocalVersion.version) { [string]$script:FL.LocalVersion.version } else { "previous" })
        & $script:FL.StartJob "update" 'Invoke-FLUpdate -Config (Get-FLConfig) -Report $Report' $null {
            param($Result, $ErrorText)
            $u = $script:FL.UI
            $u.ProgressPanel.Visibility = "Collapsed"
            if ($Result -and $Result.Applied) {
                Write-FLLauncherLog "Update: $($Result.Message)"
                # play.ps1 and this window were replaced: restart the launcher from disk.
                $u.StatusTitle.Text = "Updated - restarting the launcher..."
                $ps = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
                $relaunch = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File", "`"$PlayScript`"", "-Window", "-Hidden",
                              "-AfterUpdate", "`"$($script:FL.OldVersion)`"")
                if ($script:FL.SelectedSave) { $relaunch += @("-Save", $script:FL.SelectedSave) }
                Start-Process -FilePath $ps -ArgumentList $relaunch -WorkingDirectory $Here -WindowStyle Hidden
                $script:FL.ExitCode = 0
                $script:FL.Window.Close()
                return
            }
            $msg = if ($Result) { $Result.Message } elseif ($ErrorText) { $ErrorText } else { "Unknown error." }
            Write-FLLauncherLog "Update not applied: $msg"
            & $script:FL.SetBusy $false
            & $script:FL.SetNotice "warn" "Update not installed" "$msg You can still play the installed version."
            & $script:FL.CheckUpdates
        }
    }

    # ---- firewall -------------------------------------------------------
    $script:FL.CheckFirewall = {
        $u = $script:FL.UI
        if ($script:FL.NoFirewall) { $u.NetText.Text = "Network check off"; return }
        $u.NetText.Text = "Network: checking..."
        & $script:FL.StartJob "firewall" @'
. (Join-Path $Here "setup-firewall.ps1")
$s = Get-FantasyLifeFirewallStatus -InstallDir $Here
[pscustomobject]@{ Ready = [bool]$s.Ready; Declined = (Test-Path -LiteralPath (Join-Path $Here "data\yw2-recomp\firewall-declined")) }
'@ $null {
            param($Result, $ErrorText)
            $u = $script:FL.UI
            $b = $script:FL.Brush
            if ($Result -and $Result.Ready) {
                $u.NetDot.Fill = & $b "#58A83A"; $u.NetText.Text = "Multiplayer network ready"
            } elseif ($Result) {
                $u.NetDot.Fill = & $b "#F0A020"; $u.NetText.Text = "Firewall not set up for multiplayer"
            } else {
                $u.NetDot.Fill = & $b "#B9A88E"; $u.NetText.Text = "Network check unavailable"
            }
        }
    }

    $script:FL.SetupFirewall = {
        & $script:FL.SetBusy $true
        $script:FL.UI.NetText.Text = "Waiting for the admin prompt..."
        & $script:FL.StartJob "firewall-setup" @'
. (Join-Path $Here "setup-firewall.ps1")
$ok = Invoke-FantasyLifeFirewallSetupElevated -InstallDir $Here
if ($ok) { Remove-Item -LiteralPath (Join-Path $Here "data\yw2-recomp\firewall-declined") -Force -ErrorAction SilentlyContinue }
[bool]$ok
'@ $null {
            param($Result, $ErrorText)
            & $script:FL.SetBusy $false
            if ($Result -eq $true) {
                & $script:FL.SetNotice "success" "Multiplayer network ready" "Windows Firewall now allows LAN, Hamachi, Radmin and ZeroTier play for this install."
            } else {
                & $script:FL.SetNotice "warn" "Firewall not changed" "The admin prompt was cancelled or setup failed. LAN/Hamachi multiplayer may be blocked; try again any time."
            }
            & $script:FL.CheckFirewall
        }
    }

    # ---- events -------------------------------------------------------
    $ui.Header.Add_MouseLeftButtonDown({ try { $script:FL.Window.DragMove() } catch {} })
    $ui.CloseButton.Add_Click({ $script:FL.Window.Close() })
    $ui.MinButton.Add_Click({ $script:FL.Window.WindowState = "Minimized" })
    $ui.NoticeClose.Add_Click({ $script:FL.UI.Notice.Visibility = "Collapsed" })
    $ui.NoticeAction.Add_Click({ if ($script:FL.NoticeAction) { & $script:FL.NoticeAction } })
    $ui.PlayModsButton.Add_Click({ & $script:FL.Launch "mods" })
    $ui.PlayVanillaButton.Add_Click({ & $script:FL.Launch "vanilla" })
    $ui.SettingsButton.Add_Click({ & $script:FL.Launch "settings" })
    $ui.UpdateButton.Add_Click({ & $script:FL.RunUpdate })
    $ui.FirewallButton.Add_Click({ & $script:FL.SetupFirewall })
    $ui.LogButton.Add_Click({
        $log = Get-FLLogFile $script:FL.SelectedSave
        if (-not (Test-Path -LiteralPath $log)) { $log = Join-Path $Here "logs\launcher.log" }
        if (Test-Path -LiteralPath $log) { Start-Process notepad.exe -ArgumentList "`"$log`"" }
        else { & $script:FL.SetNotice "info" "No log yet" "Logs appear in $(Join-Path $Here 'logs') after the first start." }
    })
    $ui.FolderButton.Add_Click({ Start-Process explorer.exe -ArgumentList "`"$Here`"" })
    $window.Add_KeyDown({ param($s, $e) if ($e.Key -eq "Escape") { $script:FL.Window.Close() } })

    # Poll background jobs, progress messages and the running game.
    $timer = New-Object Windows.Threading.DispatcherTimer
    $timer.Interval = [TimeSpan]::FromMilliseconds(150)
    $timer.Add_Tick({
        try {
            $msg = $null
            while ($script:FL.Queue.TryDequeue([ref]$msg)) {
                if ($msg.Job -eq "update") {
                    $u = $script:FL.UI
                    $u.ProgressText.Text = $msg.Text
                    if ($msg.Percent -ge 0) { $u.Progress.IsIndeterminate = $false; $u.Progress.Value = $msg.Percent }
                    else { $u.Progress.IsIndeterminate = $true }
                }
            }
            foreach ($job in @($script:FL.Jobs)) {
                if (-not $job.Handle.IsCompleted) { continue }
                [void]$script:FL.Jobs.Remove($job)
                $result = $null
                $errorText = $null
                try {
                    $out = $job.PS.EndInvoke($job.Handle)
                    if ($out.Count -gt 0) { $result = $out[$out.Count - 1] }
                    if ($job.PS.Streams.Error.Count -gt 0) { $errorText = [string]$job.PS.Streams.Error[0] }
                } catch {
                    $errorText = $_.Exception.Message
                }
                if ($errorText) { Write-FLLauncherLog "Job $($job.Name): $errorText" }
                try { $job.PS.Dispose(); $job.Runspace.Dispose() } catch {}
                if ($job.OnDone) { & $job.OnDone $result $errorText }
            }
            if ($script:FL.Game -and $script:FL.Game.Process.HasExited) { & $script:FL.OnGameExit }
        } catch {
            Write-FLLauncherLog "Timer: $($_.Exception.Message)"
        }
    })
    $timer.Start()

    # ---- start-up work ------------------------------------------------------
    $demo = $script:FL.Demo
    if ($demo) {
        # Developer previews of each state (used for screenshots; never in normal use).
        switch ($demo) {
            "available" { & $script:FL.ApplyStatus ([pscustomobject]@{ State = "Available"; Message = ""; RemoteVersion = [pscustomobject]@{ version = "next-build-demo"; updated_at = (Get-Date).ToUniversalTime().ToString("s") + "Z" } }) }
            "offline"   { & $script:FL.ApplyStatus ([pscustomobject]@{ State = "Offline"; Message = "Offline or update server unreachable." }) }
            "updating"  { & $script:FL.ApplyStatus ([pscustomobject]@{ State = "Available"; Message = "" }); $ui.Notice.Visibility = "Collapsed"; $ui.ProgressPanel.Visibility = "Visible"; $ui.Progress.Value = 42; $ui.ProgressText.Text = "Downloading 31.4 / 74.9 MB"; $ui.StatusTitle.Text = "Updating..."; $ui.UpdateButton.Visibility = "Collapsed" }
            "error"     { & $script:FL.ApplyStatus ([pscustomobject]@{ State = "UpToDate"; Message = "" }); & $script:FL.SetNotice "error" "Fantasy Life closed with an error (code 1)" "The last lines of play.log:" "fatal: example error line from the game log`nmods: example" "Open log" { } }
            default     { & $script:FL.ApplyStatus ([pscustomobject]@{ State = "UpToDate"; Message = "" }) }
        }
        $ui.NetDot.Fill = & $brush "#58A83A"; $ui.NetText.Text = "Multiplayer network ready"
    } else {
        if ($Config.IsTest) {
            & $script:FL.ApplyStatus ([pscustomobject]@{ State = "Test"; Message = "" })
        } elseif ($NoUpdateCheck -or $env:FL_NO_UPDATE -eq "1") {
            & $script:FL.ApplyStatus ([pscustomobject]@{ State = "Skipped"; Message = "" })
        } else {
            & $script:FL.CheckUpdates
        }
        & $script:FL.CheckFirewall
        # Desktop icon from the player's dump and shortcut repair (first start after the update).
        & $script:FL.StartJob "desktop" 'Update-FLDesktopIntegration -Config (Get-FLConfig) -RomPath (Get-FLRomPath)' $null {
            param($Result, $ErrorText)
            Write-FLLauncherLog "Desktop: $Result $ErrorText"
            & $script:FL.LoadLogo
        }
    }

    if ($Screenshot) {
        $shotTimer = New-Object Windows.Threading.DispatcherTimer
        $shotTimer.Interval = [TimeSpan]::FromMilliseconds(400)
        $script:FL.ShotStart = [DateTime]::UtcNow
        $script:FL.ShotTimer = $shotTimer
        $shotTimer.Add_Tick({
            $waited = ([DateTime]::UtcNow - $script:FL.ShotStart).TotalSeconds
            if ((-not $script:FL.StatusDone -or $script:FL.Jobs.Count -gt 0) -and $waited -lt 20) { return }
            $script:FL.ShotTimer.Stop()
            try {
                $root = $script:FL.Window.Content
                $root.UpdateLayout()
                $w = [int][Math]::Ceiling($script:FL.Window.ActualWidth)
                $h = [int][Math]::Ceiling($script:FL.Window.ActualHeight)
                $rtb = New-Object Windows.Media.Imaging.RenderTargetBitmap ($w, $h, 96, 96, [Windows.Media.PixelFormats]::Pbgra32)
                $rtb.Render($root)
                $enc = New-Object Windows.Media.Imaging.PngBitmapEncoder
                $enc.Frames.Add([Windows.Media.Imaging.BitmapFrame]::Create($rtb))
                $fs = [IO.File]::Create($script:FL.Screenshot)
                try { $enc.Save($fs) } finally { $fs.Dispose() }
            } catch {
                Write-FLLauncherLog "Screenshot failed: $($_.Exception.Message)"
            }
            $script:FL.Window.Close()
        })
        $window.Add_ContentRendered({ $script:FL.ShotTimer.Start() })
    }

    $window.Add_Closed({
        foreach ($job in @($script:FL.Jobs)) { try { [void]$job.PS.BeginStop($null, $null) } catch {} }
    })

    [void]$window.ShowDialog()
    $timer.Stop()
    return $script:FL.ExitCode
}
