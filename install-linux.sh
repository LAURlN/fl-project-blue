#!/usr/bin/env bash
# Fantasy Life PC - Linux Installer (copies from USB stick, sets up auto-updater & Desktop/App shortcuts)
set -euo pipefail

here="$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")"
if [ ! -f "$here/bin/fl_eur" ] && [ -f "$here/FantasyLife-PC/bin/fl_eur" ]; then
    here="$here/FantasyLife-PC"
fi

target="${1:-$HOME/Games/FantasyLife-PC}"

echo "=============================================================="
echo " Fantasy Life PC - Linux Installer"
echo " Source:      $here"
echo " Destination: $target"
echo "=============================================================="

if [ ! -f "$here/game/FantasyLife_EU.3ds" ]; then
    echo "Error: game/FantasyLife_EU.3ds not found in $here!" >&2
    exit 1
fi

echo ""
echo "[1/3] Copying game files, runtime, mods, and update repository (~1.1 GB)..."
mkdir -p "$target"

# Copy tracked/game directories without overwriting existing user saves, settings.ini, or console_id
for item in .git .gitignore README.txt update-config.env version.json play.sh play.ps1 play.bat publish-update.ps1 install-linux.sh install-windows.ps1 Install-Windows.bat bin lib game; do
    if [ -e "$here/$item" ]; then
        cp -rf "$here/$item" "$target/"
    fi
done

mkdir -p "$target/data/yw2-recomp"
for sub in mods shader-cache-v3 settings.default.ini; do
    if [ -e "$here/data/yw2-recomp/$sub" ]; then
        cp -rf "$here/data/yw2-recomp/$sub" "$target/data/yw2-recomp/"
    fi
done

# Seed settings.ini on first install (never copy console_id so each PC gets a unique 3DS ID)
if [ ! -f "$target/data/yw2-recomp/settings.ini" ] && [ -f "$target/data/yw2-recomp/settings.default.ini" ]; then
    cp "$target/data/yw2-recomp/settings.default.ini" "$target/data/yw2-recomp/settings.ini"
fi

# Seed saves only if not present yet
for slot in freelife story; do
    if [ ! -d "$target/saves/$slot" ]; then
        mkdir -p "$target/saves/$slot"
        if [ -d "$here/saves/$slot" ]; then
            cp -rf "$here/saves/$slot/." "$target/saves/$slot/"
        fi
    fi
done

chmod +x "$target/bin/fl_eur" "$target/play.sh" "$target/install-linux.sh" 2>/dev/null || true

echo "[2/3] Creating Desktop and Application Menu shortcuts..."
desktop_entry="[Desktop Entry]
Type=Application
Name=Fantasy Life
Comment=Fantasy Life PC (EU Remaster & Mods, Auto-Updating)
Exec=/usr/bin/env bash \"$target/play.sh\"
Path=$target
Icon=$target/bin/fantasy-life.png
Terminal=false
Categories=Game;RolePlaying;
StartupNotify=true
"

app_dir="$HOME/.local/share/applications"
mkdir -p "$app_dir"
printf "%s" "$desktop_entry" > "$app_dir/fantasy-life.desktop"
chmod +x "$app_dir/fantasy-life.desktop"

# Detect user's Desktop folder (handles ~/Desktop and German ~/Schreibtisch)
desktop_dir="$HOME/Desktop"
if command -v xdg-user-dir >/dev/null 2>&1; then
    xdg_desk="$(xdg-user-dir DESKTOP 2>/dev/null || true)"
    [ -n "$xdg_desk" ] && [ -d "$xdg_desk" ] && desktop_dir="$xdg_desk"
elif [ ! -d "$desktop_dir" ] && [ -d "$HOME/Schreibtisch" ]; then
    desktop_dir="$HOME/Schreibtisch"
fi

if [ -d "$desktop_dir" ]; then
    desk_file="$desktop_dir/Fantasy Life.desktop"
    printf "%s" "$desktop_entry" > "$desk_file"
    chmod +x "$desk_file"
    if command -v gio >/dev/null 2>&1; then
        gio set "$desk_file" metadata::trusted true 2>/dev/null || true
    fi
fi

echo "[3/3] Installation complete!"
echo ""
echo "  Installed to:     $target"
echo "  Desktop Shortcut: $desktop_dir/Fantasy Life.desktop"
echo "  App Menu Entry:   $app_dir/fantasy-life.desktop"
echo "  Auto-Update:      Active (checks automatically on every launch)"
echo ""
