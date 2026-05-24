#!/bin/bash
# Build Enterprise LLM Suite macOS .app bundle

set -e

echo "🔨 Building Enterprise LLM Suite for macOS..."

# Install dependencies
pip install -e ".[macos,enterprise]" || pip install py2app pyobjc-framework-Cocoa

# Clean previous builds
rm -rf build dist

# Build the app
python setup_enterprise.py py2app

echo "✅ Enterprise app bundle created at dist/Enterprise LLM Suite.app"
echo "📦 Run ./build_enterprise_dmg.sh to create DMG disk image"
