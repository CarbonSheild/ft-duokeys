#!/bin/bash
# Installs ft-duokeys for this user: a Python venv in this folder, and a systemd user
# service that starts and stops with SteamVR. Nothing outside the home folder changes.
#   ./install.sh            install (again), and start it if SteamVR is running
#   ./install.sh uninstall  stop and remove the service (this folder stays)
set -euo pipefail
dir=$(cd "$(dirname "$(readlink -f "$0")")" && pwd)
unit=ft-duokeys.service
units=$HOME/.config/systemd/user
# Run from a Frametop desktop, the session's own runtime folder hides the user bus.
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus

if [ "${1:-}" = uninstall ]; then
    systemctl --user disable --now "$unit" 2>/dev/null || true
    rm -f "$units/$unit"
    systemctl --user daemon-reload
    echo "removed $unit"
    exit 0
fi

lib=/opt/steamvr/bin/linuxarm64/libopenvr_api.so
[ -e "$lib" ] || { echo "no $lib: is this a Steam Frame with SteamVR?" >&2; exit 1; }
[ -w /dev/uinput ] || echo "warning: /dev/uinput isn't writable for $(id -un): no keys will be typed" >&2

if [ ! -x "$dir/.venv/bin/python" ]; then
    /usr/bin/python3 -m venv "$dir/.venv"
fi
"$dir/.venv/bin/pip" install --quiet --disable-pip-version-check -r "$dir/requirements.txt"
# pyopenvr has no arm64 build of OpenVR's client library: use SteamVR's own.
site=$("$dir/.venv/bin/python" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')
ln -sf "$lib" "$site/openvr/libopenvr_api_64.so"

mkdir -p "$units"
sed "s|@DIR@|$dir|g" "$dir/$unit" > "$units/$unit"
systemctl --user daemon-reload
systemctl --user enable "$unit"
if systemctl --user is-active --quiet steamvr.service; then
    systemctl --user restart "$unit"
    echo "installed and started: press both grips together to open the keyboard"
else
    echo "installed: it starts with SteamVR"
fi
