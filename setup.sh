#!/bin/bash
set -e

echo "Setting up Text Refiner..."

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="$HOME/.text-refiner"
ENV_DIR="$INSTALL_DIR/env"
PLIST_PATH="$HOME/Library/LaunchAgents/com.textrefiner.plist"
LOG_PATH="$INSTALL_DIR/text-refiner.log"
NATIVE_BIN="$INSTALL_DIR/TextRefinerNative"

# 1. Virtual environment + user data
mkdir -p "$INSTALL_DIR" "$HOME/Library/LaunchAgents"

# Seed user-editable config + modes on first install. Existing files are
# preserved so a `git pull && setup.sh` doesn't overwrite local edits.
if [ ! -f "$INSTALL_DIR/config.json" ]; then
  cp "$APP_DIR/config/config.json" "$INSTALL_DIR/config.json"
fi
if [ ! -f "$INSTALL_DIR/modes.json" ]; then
  cp "$APP_DIR/config/modes.default.json" "$INSTALL_DIR/modes.json"
fi

python3 -m venv "$ENV_DIR"
source "$ENV_DIR/bin/activate"

# 2. Dependencies
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r "$APP_DIR/requirements.txt"

# 3. Native daemon
xcrun swiftc $APP_DIR/native/*.swift \
  -framework AppKit \
  -framework ApplicationServices \
  -framework Carbon \
  -o "$NATIVE_BIN"

# Sign with a stable identifier so macOS keeps Accessibility / Input Monitoring
# grants across rebuilds (otherwise TCC treats every recompile as a new app).
codesign --force --sign - --identifier com.textrefiner.native "$NATIVE_BIN"

# 4. LaunchAgent
sed \
  -e "s#__PROGRAM__#$NATIVE_BIN#g" \
  -e "s#__APP_DIR__#$APP_DIR#g" \
  -e "s#__PYTHON__#$ENV_DIR/bin/python3#g" \
  -e "s#__LOG__#$LOG_PATH#g" \
  -e "s#__PATH__#$PATH#g" \
  "$APP_DIR/com.textrefiner.plist" > "$PLIST_PATH"

launchctl bootout "gui/$(id -u)" "$PLIST_PATH" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH"
launchctl kickstart -k "gui/$(id -u)/com.textrefiner"

echo ""
echo "✓ Text Refiner installed."
echo "  Shortcut: double-tap Right Option over any selected text"
echo ""
echo "  Grant permissions when prompted:"
echo "  → System Settings › Privacy & Security › Accessibility"
echo "  → System Settings › Privacy & Security › Input Monitoring"
