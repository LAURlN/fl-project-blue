#!/usr/bin/env bash
# Fantasy Life PC (Windows + Linux standalone build)
#
# Start:        bash play.sh              -> launcher menu (zenity dialog, or a terminal menu):
#                                            update, play with mods, play vanilla, save profile
#               bash play.sh story        -> play right away with the story save (no menu)
#               bash play.sh --direct     -> play right away with the Free Life save (no menu)
# Without mods: bash play.sh --vanilla [save]   (or FL_MOD_DIRS= bash play.sh)
# Skip update:  FL_NO_UPDATE=1 bash play.sh story   (direct mode updates automatically)
# Without DLC:  FL_DLC_CIA= bash play.sh
# Dry run:      FL_NO_LAUNCH=1 bash play.sh [...]
# Force menu:   FL_MENU=1 / FL_MENU=terminal (no zenity) / FL_DIRECT=1 (never a menu)
set -euo pipefail
cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")"
here="$PWD"

save="freelife"
vanilla=0
direct=0
game_args=()
while [ "$#" -gt 0 ]; do
    case "$1" in
        --vanilla) vanilla=1; direct=1 ;;
        --direct)  direct=1 ;;
        --menu)    FL_MENU="${FL_MENU:-1}" ;;
        --)        shift; game_args+=("$@"); break ;;
        -*)        game_args+=("$1") ;;
        *)         save="$1"; direct=1 ;;
    esac
    shift
done
case "$save" in
    ""|*/*|.*|*[!A-Za-z0-9._-]*) echo "Invalid save profile name: $save" >&2; exit 1 ;;
esac

# 0. Channel marker (channel.env). A test install sets FL_CHANNEL=test; a stable
#    install has no file and follows origin/main.
channel="stable"
if [ -f "$here/channel.env" ]; then
    channel="$(sed -n 's/^[[:space:]]*FL_CHANNEL[[:space:]]*=[[:space:]]*//p' "$here/channel.env" | tail -n1 | tr -d '\r"[:space:]' || true)"
    [ -n "$channel" ] || channel="stable"
fi

FL_UPDATE_BRANCH="${FL_UPDATE_BRANCH:-main}"
FL_UPDATE_ZIP_URL="${FL_UPDATE_ZIP_URL:-}"
FL_UPDATE_VERSION_URL="${FL_UPDATE_VERSION_URL:-}"
if [ -f "$here/update-config.env" ]; then
    # shellcheck disable=SC1091
    source <(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "$here/update-config.env" | tr -d '\r')
fi
if [ -z "$FL_UPDATE_VERSION_URL" ] && [[ "$FL_UPDATE_ZIP_URL" =~ ^https?://github\.com/([^/]+)/([^/]+)/archive/refs/heads/(.+)\.zip$ ]]; then
    FL_UPDATE_VERSION_URL="https://raw.githubusercontent.com/${BASH_REMATCH[1]}/${BASH_REMATCH[2]}/${BASH_REMATCH[3]}/version.json"
fi

git_fl() { git -c safe.directory='*' "$@"; }
json_str() { # json_str <file-or-text> <key>  (flat string values only)
    printf '%s' "$1" | tr -d '\r' | tr '\n' ' ' | sed -n "s/.*\"$2\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/p" | head -n1
}
json_list() { # json_list <text> <key> -> one item per line
    printf '%s' "$1" | tr -d '\r' | tr '\n' ' ' | sed -n "s/.*\"$2\"[[:space:]]*:[[:space:]]*\[\([^]]*\)\].*/\1/p" | head -n1 |
        tr ',' '\n' | sed 's/^[[:space:]]*"//; s/"[[:space:]]*$//' | grep -v '^[[:space:]]*$' || true
}
have_git_updater() {
    command -v git >/dev/null 2>&1 && [ -d "$here/.git" ] && git_fl remote 2>/dev/null | grep -qx origin
}

# ---------------------------------------------------------------------------
# Update check / update (never touches game/, saves/, settings.ini or console_id;
# never git clean; offline never blocks the launch)
# ---------------------------------------------------------------------------
update_state="unknown"   # uptodate | available | ahead | offline | none | test
update_remote=""
check_update() {
    update_remote=""
    if [ "$channel" = "test" ]; then update_state="test"; return; fi
    if have_git_updater; then
        if ! git_fl fetch origin "$FL_UPDATE_BRANCH" --quiet 2>/dev/null; then update_state="offline"; return; fi
        local l r
        l="$(git_fl rev-parse HEAD 2>/dev/null || true)"
        r="$(git_fl rev-parse "origin/$FL_UPDATE_BRANCH" 2>/dev/null || true)"
        if [ -z "$l" ] || [ -z "$r" ]; then update_state="offline"
        elif [ "$l" = "$r" ]; then update_state="uptodate"
        elif git_fl merge-base --is-ancestor "origin/$FL_UPDATE_BRANCH" HEAD 2>/dev/null; then update_state="ahead"
        else
            update_state="available"
            update_remote="$(json_str "$(git_fl show "origin/$FL_UPDATE_BRANCH:version.json" 2>/dev/null || true)" version)"
        fi
    elif [ -n "$FL_UPDATE_VERSION_URL" ] && command -v curl >/dev/null 2>&1; then
        local remote
        if ! remote="$(curl -fsSL --connect-timeout 8 --max-time 20 "$FL_UPDATE_VERSION_URL" 2>/dev/null)"; then update_state="offline"; return; fi
        update_remote="$(json_str "$remote" version)"
        local lv=""; [ -f "$here/version.json" ] && lv="$(cat "$here/version.json")"
        if [ -n "$update_remote" ] && [ "$update_remote" = "$(json_str "$lv" version)" ] &&
           [ "$(json_str "$remote" updated_at)" = "$(json_str "$lv" updated_at)" ]; then
            update_state="uptodate"
        elif [ -n "$update_remote" ]; then update_state="available"
        else update_state="offline"; fi
    else
        update_state="none"
    fi
}

apply_update() {
    if [ "$channel" = "test" ]; then echo "[Updater] Test installs never update."; return 0; fi
    if pgrep -f "$here/bin/fl_eur" >/dev/null 2>&1; then echo "[Updater] Close Fantasy Life before updating."; return 1; fi
    if have_git_updater; then
        if ! git_fl fetch origin "$FL_UPDATE_BRANCH" --quiet 2>/dev/null; then
            echo "[Updater] Offline or remote unreachable; continuing with local version."; return 1
        fi
        local l r
        l="$(git_fl rev-parse HEAD 2>/dev/null || true)"
        r="$(git_fl rev-parse "origin/$FL_UPDATE_BRANCH" 2>/dev/null || true)"
        if [ -z "$r" ] || [ -z "$l" ]; then return 1; fi
        if [ "$l" = "$r" ]; then echo "[Updater] Already up to date (${l:0:7})."; return 0; fi
        if git_fl merge-base --is-ancestor "origin/$FL_UPDATE_BRANCH" HEAD 2>/dev/null; then
            # Keep a local, unpublished hotfix: HEAD strictly ahead of origin.
            echo "[Updater] Local hotfix not yet published (${l:0:7} ahead of ${r:0:7})"; return 0
        fi
        # origin ahead or diverged: mirror origin exactly. reset --hard only touches
        # tracked files; ignored game/, saves/, logs/, settings.ini, console_id stay.
        if git_fl reset --hard "origin/$FL_UPDATE_BRANCH" >/dev/null 2>&1; then
            echo "[Updater] Updated ${l:0:7} -> ${r:0:7}"
            chmod +x "$here/bin/fl_eur" "$here/play.sh" 2>/dev/null || true
            return 0
        fi
        echo "[Updater] Update failed; continuing with local version."; return 1
    elif [ -n "$FL_UPDATE_ZIP_URL" ] && command -v curl >/dev/null 2>&1 && command -v unzip >/dev/null 2>&1; then
        echo "[Updater] Downloading $FL_UPDATE_ZIP_URL ..."
        local tmp="$here/.update-tmp"
        rm -rf "$tmp" && mkdir -p "$tmp"
        if curl -fL --connect-timeout 10 --progress-bar "$FL_UPDATE_ZIP_URL" -o "$tmp/update.zip" && unzip -q "$tmp/update.zip" -d "$tmp/x"; then
            local extracted="$tmp/x"
            if [ ! -f "$extracted/version.json" ]; then extracted="$(find "$tmp/x" -mindepth 1 -maxdepth 1 -type d | head -n 1)"; fi
            if [ -n "$extracted" ] && [ -f "$extracted/version.json" ]; then
                for sub in bin lib data/yw2-recomp/shader-cache-v3 contrib; do
                    if [ -d "$extracted/$sub" ]; then mkdir -p "$here/$sub" && cp -rf "$extracted/$sub/." "$here/$sub/"; fi
                done
                if [ -d "$extracted/data/yw2-recomp/mods" ]; then
                    rm -rf "$here/data/yw2-recomp/mods" && mkdir -p "$here/data/yw2-recomp/mods"
                    cp -rf "$extracted/data/yw2-recomp/mods/." "$here/data/yw2-recomp/mods/"
                fi
                for f in version.json data/yw2-recomp/settings.default.ini play.ps1 play.bat play.sh setup-firewall.ps1 \
                         install-windows.ps1 Install-Windows.bat install-test.ps1 Install-Test.bat install-linux.sh \
                         publish-update.ps1 publish-test.ps1 README.txt update-config.env .gitignore; do
                    if [ -f "$extracted/$f" ]; then mkdir -p "$(dirname "$here/$f")" && cp -f "$extracted/$f" "$here/$f"; fi
                done
                chmod +x "$here/bin/fl_eur" "$here/play.sh" 2>/dev/null || true
                rm -rf "$tmp"
                echo "[Updater] ZIP update applied."
                return 0
            fi
        fi
        rm -rf "$tmp"
        echo "[Updater] ZIP update failed; continuing with local version."; return 1
    fi
    return 1
}

# ---------------------------------------------------------------------------
# Version, mods
# ---------------------------------------------------------------------------
manifest=""
if [ "$channel" = "test" ]; then
    [ -f "$here/test-version.json" ] && manifest="$(cat "$here/test-version.json")"
else
    [ -f "$here/version.json" ] && manifest="$(cat "$here/version.json")"
fi
M="$here/data/yw2-recomp/mods/fantasylife"
load_mods() {
    mod_names=()
    local text=""
    if [ "$channel" = "test" ]; then
        [ -f "$here/test-version.json" ] && text="$(cat "$here/test-version.json")"
    else
        [ -f "$here/version.json" ] && text="$(cat "$here/version.json")"
    fi
    if printf '%s' "$text" | grep -q '"mods"'; then
        while IFS= read -r name; do
            if [ -n "$name" ]; then mod_names+=("$name"); fi
        done < <(json_list "$text" mods)
    elif [ "$channel" != "test" ]; then
        # Old manifests without a mods list: every installed overlay.
        for d in "$M"/*/; do
            if [ -f "$d/overlay.json" ]; then mod_names+=("$(basename "$d")"); fi
        done
    fi
}
mod_display() {
    local out="" name n
    for name in "${mod_names[@]+"${mod_names[@]}"}"; do
        n="$(json_str "$(cat "$M/$name/overlay.json" 2>/dev/null || true)" name)"
        out="${out:+$out, }${n:-$name}"
    done
    printf '%s' "${out:-none}"
}
load_mods

print_banner() {
    echo "=============================================================="
    if [ "$channel" = "test" ]; then
        echo " TEST BUILD | $(json_str "$manifest" label)"
        echo " Published:   $(json_str "$manifest" date)"
        echo " Local test install - never updates."
    else
        echo " Fantasy Life PC | Build: $(json_str "$manifest" version)"
        echo " Updated:        $(json_str "$manifest" updated_at) | Mod digest: $(json_str "$manifest" mod_digest)"
    fi
    echo " Mods:           $(mod_display)"
    echo "=============================================================="
}

# ---------------------------------------------------------------------------
# Launch
# ---------------------------------------------------------------------------
launch() { # launch <mods|vanilla|settings>
    local kind="$1"
    mkdir -p "$here/data/yw2-recomp"
    if [ ! -f "$here/data/yw2-recomp/settings.ini" ] && [ -f "$here/data/yw2-recomp/settings.default.ini" ]; then
        cp "$here/data/yw2-recomp/settings.default.ini" "$here/data/yw2-recomp/settings.ini"
    fi
    local rom="$here/game/FantasyLife_EU.3ds"
    if [ ! -f "$rom" ] && [ -f "$here/../FantasyLife-Linux/game/FantasyLife_EU.3ds" ]; then
        rom="$here/../FantasyLife-Linux/game/FantasyLife_EU.3ds"
    fi
    local dlc_default="$here/game/OriginIsland_DLC.cia"
    if [ ! -f "$dlc_default" ] && [ -f "$here/../FantasyLife-Linux/game/OriginIsland_DLC.cia" ]; then
        dlc_default="$here/../FantasyLife-Linux/game/OriginIsland_DLC.cia"
    fi
    [ -f "$dlc_default" ] || dlc_default=""

    export LD_LIBRARY_PATH="$here/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    export XDG_DATA_HOME="$here/data"
    export YW2_STATE_DIR="$here/saves/$save"
    export YW2_WIDESCREEN=0 YW2_INTERP=0 YW2_SCALE=1 FL_FPS="${FL_FPS:-0}" YW2_FPS="${YW2_FPS:-0}"
    export FL_DLC_CIA="${FL_DLC_CIA-$dlc_default}"
    # An explicitly empty FL_MOD_DIRS means "no mods"; unset would load every overlay.
    if [ "$kind" = "vanilla" ]; then
        export FL_MOD_DIRS=""
    elif [ -z "${FL_MOD_DIRS+x}" ]; then
        local dirs="" name
        for name in "${mod_names[@]+"${mod_names[@]}"}"; do
            if [ ! -f "$M/$name/overlay.json" ]; then
                echo "Installed mod '$name' is missing. Update the game, or play vanilla." >&2; return 1
            fi
            dirs="${dirs:+$dirs:}$M/$name"
        done
        export FL_MOD_DIRS="$dirs"
    fi
    mkdir -p "$YW2_STATE_DIR" "$here/logs"
    local mode="--play"; [ "$kind" = "settings" ] && mode="--launcher"
    local log="$here/logs/play.log"; [ "$save" = freelife ] || log="$here/logs/play-$save.log"  # one log per save profile
    echo "[Launch] Save: $save | Mods: $([ -n "$FL_MOD_DIRS" ] && mod_display || echo 'none (vanilla)') | Log: $log"
    if [ "${FL_NO_LAUNCH:-0}" = "1" ]; then
        echo "[Launch] FL_NO_LAUNCH=1; exiting without starting the game. FL_MOD_DIRS='$FL_MOD_DIRS'"
        return 0
    fi
    if [ "${menu_kind:-}" = "zenity" ]; then
        "$here/bin/fl_eur" "$mode" "$rom" "${game_args[@]+"${game_args[@]}"}" > "$log" 2>&1 || {
            local code=$?
            zenity --error --title "Fantasy Life" --text "Fantasy Life closed with an error (code $code).\n\nLog: $log\n\n$(tail -n 8 "$log" | sed 's/[<>&]//g')" 2>/dev/null || true
            return "$code"
        }
        return 0
    fi
    exec "$here/bin/fl_eur" "$mode" "$rom" "${game_args[@]+"${game_args[@]}"}" > "$log" 2>&1
}

# ---------------------------------------------------------------------------
# Mode selection
# ---------------------------------------------------------------------------
menu_kind=""
if [ "$direct" = 0 ] && [ "${FL_DIRECT:-0}" != "1" ]; then
    if [ "${FL_MENU:-}" != "terminal" ] && command -v zenity >/dev/null 2>&1 && { [ -n "${DISPLAY:-}" ] || [ -n "${WAYLAND_DISPLAY:-}" ]; }; then
        menu_kind="zenity"
    elif { [ -t 0 ] && [ -t 1 ]; } || [ -n "${FL_MENU:-}" ]; then
        menu_kind="terminal"
    fi
fi

if [ -z "$menu_kind" ]; then
    # Direct mode (arguments, scripts, desktop entry without zenity): old behaviour,
    # including the automatic update unless FL_NO_UPDATE=1.
    if [ "$channel" != "test" ] && [ "${FL_NO_UPDATE:-0}" != "1" ]; then apply_update || true; load_mods; fi
    print_banner
    if [ "$vanilla" = 1 ]; then launch vanilla; else launch mods; fi
    exit $?
fi

update_line() {
    case "$update_state" in
        uptodate)  echo "Up to date" ;;
        available) echo "UPDATE AVAILABLE${update_remote:+: $update_remote} - update before playing together (same build needed for multiplayer)" ;;
        ahead)     echo "Local build (not published yet)" ;;
        offline)   echo "Couldn't check for updates (offline) - you can still play" ;;
        test)      echo "Test build - never updates" ;;
        skipped)   echo "Update check skipped (FL_NO_UPDATE=1)" ;;
        *)         echo "Updates not set up" ;;
    esac
}

if [ "${FL_NO_UPDATE:-0}" = "1" ] && [ "$channel" != "test" ]; then update_state="skipped"; else check_update; fi

if [ "$menu_kind" = "zenity" ]; then
    while true; do
        title="Fantasy Life"; [ "$channel" = "test" ] && title="Fantasy Life (TEST: $(json_str "$manifest" label))"
        rows=(play "Play with mods ($(mod_display))" vanilla "Play vanilla (original game, no mods)")
        [ "$update_state" = "available" ] && rows=(update "Update now" "${rows[@]}")
        [ "$update_state" = "offline" ] && rows+=(check "Check for updates again")
        other="story"; [ "$save" = "story" ] && other="freelife"
        rows+=(save "Switch save profile to '$other'" settings "Game settings (controls, resolution, online)")
        choice="$(zenity --list --title "$title" --width 560 --height 380 \
            --text "Build: $(json_str "$manifest" version)$(json_str "$manifest" label)\n$(update_line)\nSave profile: $save" \
            --column id --column Action --hide-column 1 --print-column 1 "${rows[@]}" 2>/dev/null)" || exit 0
        case "$choice" in
            play)     launch mods; exit $? ;;
            vanilla)  launch vanilla; exit $? ;;
            settings) launch settings || true ;;
            save)     save="$other" ;;
            check)    check_update ;;
            update)
                if apply_update 2>&1 | zenity --progress --pulsate --auto-close --no-cancel --title "Fantasy Life" --text "Updating..." 2>/dev/null; then :; fi
                exec bash "$here/play.sh" --menu
                ;;
            *) exit 0 ;;
        esac
    done
fi

# Terminal menu
while true; do
    echo
    print_banner
    echo " Update: $(update_line)"
    echo " Save profile: $save"
    echo "--------------------------------------------------------------"
    echo "  1) Play with mods"
    echo "  2) Play vanilla (original game, no mods; multiplayer only with vanilla players)"
    if [ "$update_state" = "available" ]; then echo "  u) Update now"; fi
    if [ "$update_state" = "offline" ]; then echo "  c) Check for updates again"; fi
    echo "  s) Switch save profile (freelife / story)"
    echo "  g) Game settings (controls, resolution, online)"
    echo "  q) Quit"
    printf "Choice [1]: "
    read -r choice || exit 0
    case "${choice:-1}" in
        1) launch mods; exit $? ;;
        2) launch vanilla; exit $? ;;
        u|U)
            if [ "$update_state" = "available" ]; then
                apply_update || true
                # play.sh may have been replaced by the update: restart the menu from disk.
                exec bash "$here/play.sh" --menu
            fi ;;
        c|C) check_update ;;
        s|S) if [ "$save" = "freelife" ]; then save="story"; else save="freelife"; fi ;;
        g|G) launch settings ;;
        q|Q) exit 0 ;;
        *) echo "Unknown choice: $choice" ;;
    esac
done
