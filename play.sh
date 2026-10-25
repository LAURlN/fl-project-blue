#!/usr/bin/env bash
# Fantasy Life PC (Windows + Linux auto-updating standalone build)
# Start:        bash play.sh              -> Free Life save (saves/freelife)
#               bash play.sh story        -> original story save (saves/story)
# Skip update:  FL_NO_UPDATE=1 bash play.sh
# Without mods: FL_MOD_DIRS= bash play.sh
# Without DLC:  FL_DLC_CIA= bash play.sh
set -euo pipefail
cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")"
here="$PWD"
save="${1:-freelife}"

# Load update-config.env if present
FL_UPDATE_BRANCH="${FL_UPDATE_BRANCH:-main}"
FL_UPDATE_ZIP_URL="${FL_UPDATE_ZIP_URL:-}"
if [ -f "$here/update-config.env" ]; then
    # shellcheck disable=SC1091
    source <(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "$here/update-config.env" | tr -d '\r')
fi

# 1. Auto-update check (never touches game/, saves/, settings.ini, or console_id)
if [ "${FL_NO_UPDATE:-0}" != "1" ]; then
    if command -v git >/dev/null 2>&1 && [ -d "$here/.git" ] && git -c safe.directory='*' remote | grep -qx origin; then
        echo "[Updater] Checking for updates from origin/$FL_UPDATE_BRANCH..."
        if git -c safe.directory='*' fetch origin "$FL_UPDATE_BRANCH" --quiet 2>/dev/null; then
            local_rev="$(git -c safe.directory='*' rev-parse HEAD 2>/dev/null || true)"
            remote_rev="$(git -c safe.directory='*' rev-parse "origin/$FL_UPDATE_BRANCH" 2>/dev/null || true)"
            if [ -n "$remote_rev" ] && [ "$local_rev" != "$remote_rev" ]; then
                echo "[Updater] Applying update (${local_rev:0:7} -> ${remote_rev:0:7})..."
                git -c safe.directory='*' merge --ff-only "origin/$FL_UPDATE_BRANCH" 2>/dev/null || \
                    git -c safe.directory='*' checkout "origin/$FL_UPDATE_BRANCH" -- bin lib data/yw2-recomp/mods data/yw2-recomp/shader-cache-v3 data/yw2-recomp/settings.default.ini version.json 2>/dev/null || true
                chmod +x "$here/bin/fl_eur" "$here/play.sh" 2>/dev/null || true
            else
                echo "[Updater] Already up to date."
            fi
        else
            echo "[Updater] Offline or remote unreachable; continuing with local version."
        fi
    elif [ -n "$FL_UPDATE_ZIP_URL" ] && command -v curl >/dev/null 2>&1 && command -v unzip >/dev/null 2>&1; then
        echo "[Updater] Checking ZIP update from $FL_UPDATE_ZIP_URL..."
        tmp="$here/.update-tmp"
        rm -rf "$tmp" && mkdir -p "$tmp"
        if curl -fsSL --connect-timeout 10 "$FL_UPDATE_ZIP_URL" -o "$tmp/update.zip" && unzip -q "$tmp/update.zip" -d "$tmp"; then
            extracted="$(find "$tmp" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
            if [ -n "$extracted" ]; then
                for sub in bin lib data/yw2-recomp/mods data/yw2-recomp/shader-cache-v3; do
                    [ -d "$extracted/$sub" ] && mkdir -p "$here/$sub" && cp -rf "$extracted/$sub/." "$here/$sub/"
                done
                [ -f "$extracted/version.json" ] && cp -f "$extracted/version.json" "$here/version.json"
                chmod +x "$here/bin/fl_eur" "$here/play.sh" 2>/dev/null || true
                echo "[Updater] ZIP update applied."
            fi
        fi
        rm -rf "$tmp"
    fi
fi

# 2. Print version / mod compatibility digest
if [ -f "$here/version.json" ]; then
    echo "=============================================================="
    grep -E '"(version|updated_at|mod_digest)"' "$here/version.json" | sed 's/^[[:space:]]*/  /' || true
    echo "=============================================================="
fi

# 3. Seed per-machine settings on first run (never share console_id!)
mkdir -p "$here/data/yw2-recomp"
if [ ! -f "$here/data/yw2-recomp/settings.ini" ] && [ -f "$here/data/yw2-recomp/settings.default.ini" ]; then
    cp "$here/data/yw2-recomp/settings.default.ini" "$here/data/yw2-recomp/settings.ini"
fi

# 4. Locate game dump and DLC CIA
rom="$here/game/FantasyLife_EU.3ds"
if [ ! -f "$rom" ] && [ -f "$here/../FantasyLife-Linux/game/FantasyLife_EU.3ds" ]; then
    rom="$here/../FantasyLife-Linux/game/FantasyLife_EU.3ds"
fi
dlc_default="$here/game/OriginIsland_DLC.cia"
if [ ! -f "$dlc_default" ] && [ -f "$here/../FantasyLife-Linux/game/OriginIsland_DLC.cia" ]; then
    dlc_default="$here/../FantasyLife-Linux/game/OriginIsland_DLC.cia"
fi

export LD_LIBRARY_PATH="$here/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export XDG_DATA_HOME="$here/data"
export YW2_STATE_DIR="$here/saves/$save"
export YW2_WIDESCREEN=0 YW2_INTERP=0 YW2_SCALE=1 FL_FPS="${FL_FPS:-0}" YW2_FPS="${YW2_FPS:-0}"
export FL_DLC_CIA="${FL_DLC_CIA-$dlc_default}"
M="$here/data/yw2-recomp/mods/fantasylife"
export FL_MOD_DIRS="${FL_MOD_DIRS-$M/story-skip:$M/eastern-plains-enemy:$M/castele-house:$M/wooden-sword}"
mkdir -p "$YW2_STATE_DIR" "$here/logs"
exec "$here/bin/fl_eur" --play "$rom" "$@" > "$here/logs/play.log" 2>&1
