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

# 0. Load the optional channel marker (channel.env). A test install sets
#    FL_CHANNEL=test; a stable install has no file and follows origin/main.
channel="stable"
if [ -f "$here/channel.env" ]; then
    channel="$(sed -n 's/^[[:space:]]*FL_CHANNEL[[:space:]]*=[[:space:]]*//p' "$here/channel.env" | tail -n1 | tr -d '\r"[:space:]' || true)"
    [ -n "$channel" ] || channel="stable"
fi

# Load update-config.env if present
FL_UPDATE_BRANCH="${FL_UPDATE_BRANCH:-main}"
FL_UPDATE_ZIP_URL="${FL_UPDATE_ZIP_URL:-}"
if [ -f "$here/update-config.env" ]; then
    # shellcheck disable=SC1091
    source <(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "$here/update-config.env" | tr -d '\r')
fi

# 1. Auto-update check (never touches game/, saves/, settings.ini, or console_id)
#    Test installs are local-only and never auto-update.
if [ "$channel" != "test" ] && [ "${FL_NO_UPDATE:-0}" != "1" ]; then
    if command -v git >/dev/null 2>&1 && [ -d "$here/.git" ] && git -c safe.directory='*' remote | grep -qx origin; then
        if git -c safe.directory='*' fetch origin "$FL_UPDATE_BRANCH" --quiet 2>/dev/null; then
            local_rev="$(git -c safe.directory='*' rev-parse HEAD 2>/dev/null || true)"
            remote_rev="$(git -c safe.directory='*' rev-parse "origin/$FL_UPDATE_BRANCH" 2>/dev/null || true)"
            if [ -n "$remote_rev" ] && [ -n "$local_rev" ]; then
                if [ "$local_rev" = "$remote_rev" ]; then
                    echo "[Updater] Already up to date (${local_rev:0:7})."
                elif git -c safe.directory='*' merge-base --is-ancestor "origin/$FL_UPDATE_BRANCH" HEAD 2>/dev/null; then
                    # Keep a local, unpublished hotfix: HEAD strictly ahead of origin.
                    echo "[Updater] Local hotfix not yet published (${local_rev:0:7} ahead of ${remote_rev:0:7})"
                else
                    # origin is ahead or the branches diverged: mirror origin exactly.
                    # reset --hard only touches tracked files; ignored game/, saves/,
                    # logs/, settings.ini and console_id stay untouched. Never git clean.
                    if git -c safe.directory='*' reset --hard "origin/$FL_UPDATE_BRANCH" >/dev/null 2>&1; then
                        echo "[Updater] Updated ${local_rev:0:7} -> ${remote_rev:0:7}"
                        chmod +x "$here/bin/fl_eur" "$here/play.sh" 2>/dev/null || true
                    else
                        echo "[Updater] Update failed; continuing with local version."
                    fi
                fi
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
test_mods_json=""
if [ "$channel" = "test" ]; then
    if [ -f "$here/test-version.json" ]; then
        tv="$(tr -d '\r' < "$here/test-version.json" | tr '\n' ' ')"
        jstr() { printf '%s' "$tv" | sed -n "s/.*\"$1\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/p" | head -n1; }
        test_label="$(jstr label)"
        test_exe_source="$(jstr exe_source)"
        test_exe_sha="$(jstr exe_sha256)"
        test_date="$(jstr date)"
        test_mods_json="$(printf '%s' "$tv" | sed -n 's/.*"mods"[[:space:]]*:[[:space:]]*\[\([^]]*\)\].*/\1/p' | head -n1)"
        echo "=============================================================="
        echo " TEST BUILD | ${test_label:-(unlabeled)}"
        if [ -n "$test_exe_source" ]; then echo " Exe source:  $test_exe_source"; fi
        if [ -n "$test_exe_sha" ]; then echo " Exe SHA-256: $test_exe_sha"; fi
        mods_display="$(printf '%s' "$test_mods_json" | tr ',' '\n' | sed 's/^[[:space:]]*"//; s/"[[:space:]]*$//' | grep -v '^$' | tr '\n' ',' | sed 's/,$//; s/,/, /g')"
        if [ -n "$mods_display" ]; then echo " Mods:        $mods_display"; fi
        if [ -n "$test_date" ]; then echo " Published:   $test_date"; fi
        echo " Local test install - auto-update disabled."
        echo "=============================================================="
    else
        echo "[Test] Missing test-version.json. Run publish-test.ps1 to fill this test install."
    fi
elif [ -f "$here/version.json" ]; then
    echo "=============================================================="
    grep -E '"(version|updated_at|mod_digest)"' "$here/version.json" | sed 's/^[[:space:]]*/  /' || true
    echo "=============================================================="
fi

mod_names=()
if [ -n "$test_mods_json" ]; then
    while IFS= read -r mod_name; do
        mod_name="$(printf '%s' "$mod_name" | sed 's/^[[:space:]]*"//; s/"[[:space:]]*$//' | tr -d '\r')"
        if [ -n "$mod_name" ]; then mod_names+=("$mod_name"); fi
    done < <(printf '%s' "$test_mods_json" | tr ',' '\n')
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
if [ -z "${FL_MOD_DIRS+x}" ]; then
    if [ "$channel" = "test" ]; then
        mod_dirs=""
        if [ "${#mod_names[@]}" -gt 0 ]; then
            for mod_name in "${mod_names[@]}"; do
                if [ -n "$mod_dirs" ]; then mod_dirs="$mod_dirs:"; fi
                mod_dirs="$mod_dirs$M/$mod_name"
            done
        fi
        export FL_MOD_DIRS="$mod_dirs"
    else
        export FL_MOD_DIRS="$M/story-skip:$M/eastern-plains-enemy:$M/castele-house:$M/wooden-sword"
    fi
fi
mkdir -p "$YW2_STATE_DIR" "$here/logs"
if [ "${FL_NO_LAUNCH:-0}" = "1" ]; then
    echo "[Launch] FL_NO_LAUNCH=1; exiting without starting the game."
    exit 0
fi
exec "$here/bin/fl_eur" --play "$rom" "$@" > "$here/logs/play.log" 2>&1
