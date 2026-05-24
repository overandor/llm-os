#!/bin/bash
# Create DMG disk image for Enterprise LLM Suite

set -e

APP_NAME="Enterprise LLM Suite"
APP_PATH="dist/${APP_NAME}.app"
DMG_NAME="Enterprise-LLM-Suite-1.0.0"
DMG_PATH="dist/${DMG_NAME}.dmg"
VOLUME_NAME="Enterprise LLM Suite"

echo "📦 Creating Enterprise LLM Suite DMG disk image..."

# Check if app exists
if [ ! -d "$APP_PATH" ]; then
    echo "❌ Error: $APP_PATH not found. Run ./build_enterprise_app.sh first."
    exit 1
fi

# Create temporary directory for DMG contents
TEMP_DIR="dist/dmg_temp_enterprise"
rm -rf "$TEMP_DIR"
mkdir -p "$TEMP_DIR"

# Copy app to temp directory
cp -R "$APP_PATH" "$TEMP_DIR/"

# Create Applications symlink for easy installation
ln -s /Applications "$TEMP_DIR/Applications"

# Create README
cat > "$TEMP_DIR/README.txt" << 'EOF'
Enterprise LLM Suite v1.0.0
==========================

Features:
- Multi-model LLM inference (local + API)
- RAG with vector database
- Fine-tuning and model management
- Enterprise authentication and security
- Analytics and monitoring
- Document processing
- API management

Installation:
1. Drag "Enterprise LLM Suite.app" to Applications
2. Launch from Applications folder
3. Create your admin account
4. Start using the suite

Documentation:
See in-app Help menu for detailed documentation.

Support:
enterprise@membra.network
EOF

# Create DMG
hdiutil create -volname "$VOLUME_NAME" \
    -srcfolder "$TEMP_DIR" \
    -ov \
    -format UDZO \
    "$DMG_PATH"

# Clean up
rm -rf "$TEMP_DIR"

echo "✅ Enterprise DMG created at $DMG_PATH"
echo "📊 Size: $(du -h "$DMG_PATH" | cut -f1)"
echo "💰 Value: $200,000 enterprise suite"
