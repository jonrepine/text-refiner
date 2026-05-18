#!/bin/bash
# Build TextRefiner.app from source, install it to /Applications, and register
# the LaunchAgent that keeps it running across reboots.
#
# Idempotent. Safe to re-run after a `git pull`.

set -e

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="$HOME/.text-refiner"
ENV_DIR="$INSTALL_DIR/env"
APP_BUNDLE="/Applications/TextRefiner.app"
PLIST_PATH="$HOME/Library/LaunchAgents/com.textrefiner.plist"
LOG_PATH="$INSTALL_DIR/text-refiner.log"
BUILD_DIR="$APP_DIR/build"
BUILD_BUNDLE="$BUILD_DIR/TextRefiner.app"

echo "Setting up Text Refiner..."

mkdir -p "$INSTALL_DIR" "$HOME/Library/LaunchAgents" "$BUILD_DIR"

# 1. Seed user-editable config + modes only on first install. Existing files
#    are preserved so `git pull && setup.sh` doesn't wipe local edits.
if [ ! -f "$INSTALL_DIR/config.json" ]; then
  cp "$APP_DIR/config/config.json" "$INSTALL_DIR/config.json"
fi
if [ ! -f "$INSTALL_DIR/modes.json" ]; then
  cp "$APP_DIR/config/modes.default.json" "$INSTALL_DIR/modes.json"
fi

# 2. Python virtualenv + deps
python3 -m venv "$ENV_DIR"
source "$ENV_DIR/bin/activate"
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r "$APP_DIR/requirements.txt"

# 3. Build the .app bundle
rm -rf "$BUILD_BUNDLE"
mkdir -p "$BUILD_BUNDLE/Contents/MacOS" "$BUILD_BUNDLE/Contents/Resources"

xcrun swiftc $APP_DIR/native/*.swift \
  -framework AppKit \
  -framework ApplicationServices \
  -framework Carbon \
  -framework IOKit \
  -o "$BUILD_BUNDLE/Contents/MacOS/TextRefiner"

cp "$APP_DIR/refiner_cli.py" "$BUILD_BUNDLE/Contents/Resources/"
cp -R "$APP_DIR/refiner" "$BUILD_BUNDLE/Contents/Resources/"
cp -R "$APP_DIR/utils"   "$BUILD_BUNDLE/Contents/Resources/"
cp -R "$APP_DIR/config"  "$BUILD_BUNDLE/Contents/Resources/"
cp "$APP_DIR/requirements.txt" "$BUILD_BUNDLE/Contents/Resources/"

cat > "$BUILD_BUNDLE/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>en</string>
    <key>CFBundleExecutable</key>
    <string>TextRefiner</string>
    <key>CFBundleIdentifier</key>
    <string>com.textrefiner.app</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>Text Refiner</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>LSMinimumSystemVersion</key>
    <string>13.0</string>
    <key>LSUIElement</key>
    <true/>
    <key>NSAccessibilityUsageDescription</key>
    <string>Text Refiner needs Accessibility access to detect the trigger shortcut and replace selected text in any app.</string>
    <key>NSHumanReadableCopyright</key>
    <string>Copyright \u00a9 2026 jonrepine. MIT License.</string>
</dict>
</plist>
PLIST

# Stable code identifier so Accessibility + Input Monitoring permissions
# persist across rebuilds.
codesign --force --sign - --identifier com.textrefiner.app "$BUILD_BUNDLE"

# 4. Stop the running daemon (if any), replace the installed app, restart.
launchctl bootout "gui/$(id -u)" "$PLIST_PATH" 2>/dev/null || true
pkill -9 -f "TextRefiner" 2>/dev/null || true
sleep 1

# Install into /Applications. If that fails due to permissions, fall back to
# ~/Applications so the install works without sudo.
INSTALL_TARGET="$APP_BUNDLE"
if ! rm -rf "$APP_BUNDLE" 2>/dev/null || ! cp -R "$BUILD_BUNDLE" "$APP_BUNDLE" 2>/dev/null; then
  INSTALL_TARGET="$HOME/Applications/TextRefiner.app"
  mkdir -p "$HOME/Applications"
  rm -rf "$INSTALL_TARGET"
  cp -R "$BUILD_BUNDLE" "$INSTALL_TARGET"
fi

# 5. LaunchAgent points at the installed binary.
sed \
  -e "s#__PROGRAM__#$INSTALL_TARGET/Contents/MacOS/TextRefiner#g" \
  -e "s#__LOG__#$LOG_PATH#g" \
  -e "s#__PATH__#$PATH#g" \
  "$APP_DIR/com.textrefiner.plist" > "$PLIST_PATH"

launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH"
launchctl kickstart -k "gui/$(id -u)/com.textrefiner"

echo ""
echo "✓ Text Refiner installed at $INSTALL_TARGET"
echo "  Shortcut: double-tap Right Option over selected text"
echo ""
echo "  Grant permissions when prompted, or open System Settings and look"
echo "  for \"Text Refiner\":"
echo "    → Privacy & Security › Accessibility"
echo "    → Privacy & Security › Input Monitoring"
echo ""
echo "  Then click the TR icon in your menu bar → Preferences… → enter your"
echo "  API key."
