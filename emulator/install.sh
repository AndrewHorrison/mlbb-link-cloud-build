#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_ROOT="$HOME/.local/share"
CONFIG_ROOT="$HOME/.config"
APP_DIR="$DATA_ROOT/mlbb-link-emulator"
CONFIG_DIR="$CONFIG_ROOT/mlbb-link-emulator"
VENV="$APP_DIR/venv"
DESKTOP_DIR="$HOME/.local/share/applications"
SETUP_UINPUT=0
INSTALL_KEYBOARD=0

for arg in "$@"; do
    case "$arg" in
        --setup-uinput) SETUP_UINPUT=1 ;;
        --keyboard) INSTALL_KEYBOARD=1 ;;
        --help)
            cat <<'HELP'
Usage: bash install.sh [--setup-uinput] [--keyboard]

Default: install the GUI and updater in ~/.local/share. No sudo.
--setup-uinput: create a dedicated uinput group and udev rule; needs sudo and a logout/login.
--keyboard: install optional python-evdev support for global key capture.
HELP
            exit 0
            ;;
        *) echo "Unknown option: $arg" >&2; exit 2 ;;
    esac
done

if [[ "$(uname -s)" != "Linux" ]]; then
    echo "MLBB Link Emulator Tools currently supports Linux hosts." >&2
    exit 2
fi
if [[ "$(uname -m)" != "x86_64" ]]; then
    echo "This build targets x86_64 Bazzite/Linux hosts; other architectures may require changes." >&2
    exit 2
fi
command -v python3 >/dev/null || { echo "python3 was not found on the host." >&2; exit 2; }

mkdir -p "$APP_DIR" "$CONFIG_DIR" "$DESKTOP_DIR"
for file in launcher.py overlay.py input_engine.py profiles.py updater.py profile_default.json requirements.txt requirements-keyboard.txt install.sh README.md package.json; do
    [[ -f "$SOURCE_DIR/$file" ]] || { echo "Required file missing: $SOURCE_DIR/$file" >&2; exit 2; }
    install -m 0644 "$SOURCE_DIR/$file" "$APP_DIR/$file"
done

if [[ ! -e "$CONFIG_DIR/settings.json" ]]; then
    cat > "$CONFIG_DIR/settings.json" <<'JSON'
{
  "schemaVersion": 1,
  "route": "bridge",
  "udpListenAddress": "127.0.0.1",
  "udpListenPort": 28743,
  "keyboardCaptureEnabled": false,
  "screenWidth": 1920,
  "screenHeight": 1080
}
JSON
    chmod 0600 "$CONFIG_DIR/settings.json"
fi
# Leave profile.json absent on first install; the Qt launcher will create it at the live screen resolution.

python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install --disable-pip-version-check --only-binary=:all: -r "$APP_DIR/requirements.txt"
if [[ "$INSTALL_KEYBOARD" -eq 1 ]]; then
    "$VENV/bin/python" -m pip install --disable-pip-version-check --only-binary=:all: -r "$APP_DIR/requirements-keyboard.txt"
fi

if [[ "$SETUP_UINPUT" -eq 1 ]]; then
    echo "Configuring a dedicated non-root uinput permission. This requires sudo."
    sudo groupadd --force mlbb-uinput
    printf '%s\n' 'KERNEL=="uinput", GROUP="mlbb-uinput", MODE="0660"' \
        | sudo tee /etc/udev/rules.d/99-mlbb-link-uinput.rules >/dev/null
    printf '%s\n' 'uinput' | sudo tee /etc/modules-load.d/mlbb-link-uinput.conf >/dev/null
    sudo modprobe uinput
    sudo udevadm control --reload-rules
    sudo udevadm trigger --action=add --sysname-match=uinput
    sudo usermod -aG mlbb-uinput "$USER"
    echo "The user was added to mlbb-uinput. Log out and back in before starting the input engine."
else
    echo "Touch injection is not configured automatically. Run: bash '$SOURCE_DIR/install.sh' --setup-uinput"
fi

DESKTOP_FILE="$DESKTOP_DIR/mlbb-link-emulator.desktop"
cat > "$DESKTOP_FILE" <<DESKTOP
[Desktop Entry]
Type=Application
Name=MLBB Link Emulator Tools
Comment=Android runtime helper, keymapping overlay, touch engine and updater
Exec="$VENV/bin/python" "$APP_DIR/launcher.py"
TryExec=$VENV/bin/python
Terminal=false
Categories=Game;Utility;
StartupNotify=true
DESKTOP
chmod 0644 "$DESKTOP_FILE"

echo
echo "Installed MLBB Link Emulator Tools into: $APP_DIR"
echo "User configuration is preserved separately in: $CONFIG_DIR"
echo "Launch it from GNOME Applications → MLBB Link Emulator Tools."
if [[ "$SETUP_UINPUT" -eq 0 ]]; then
    echo "For /dev/uinput setup, rerun with --setup-uinput and then log out/in."
fi
if [[ "$INSTALL_KEYBOARD" -eq 0 ]]; then
    echo "Global key capture is optional. To add its dependency later, run:"
    echo "  '$VENV/bin/python' -m pip install --only-binary=:all: -r '$APP_DIR/requirements-keyboard.txt'"
fi
