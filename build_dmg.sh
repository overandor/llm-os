#!/bin/bash
# Create DMG disk image from .app bundle

set -e

APP_NAME="LLM OS"
APP_PATH="dist/${APP_NAME}.app"
DMG_NAME="LLM-OS-0.1.0"
DMG_PATH="dist/${DMG_NAME}.dmg"
VOLUME_NAME="LLM OS"

echo "📦 Creating DMG disk image..."

# Check if app exists
if [ ! -d "$APP_PATH" ]; then
    echo "❌ Error: $APP_PATH not found. Run ./build_app.sh first."
    exit 1
fi

# Create temporary directory for DMG contents
TEMP_DIR="dist/dmg_temp"
rm -rf "$TEMP_DIR"
mkdir -p "$TEMP_DIR"

# Copy app to temp directory
cp -R "$APP_PATH" "$TEMP_DIR/"

# Create Applications symlink for easy installation
ln -s /Applications "$TEMP_DIR/Applications"

# Create DMG
hdiutil create -volname "$VOLUME_NAME" \
    -srcfolder "$TEMP_DIR" \
    -ov \
    -format UDZO \
    "$DMG_PATH"

# Clean up
rm -rf "$TEMP_DIR"

echo "✅ DMG created at $DMG_PATH"
echo "📊 Size: $(du -h "$DMG_PATH" | cut -f1)"
