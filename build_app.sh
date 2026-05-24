#!/bin/bash
# Build macOS .app bundle for LLM OS

set -e

echo "🔨 Building LLM OS for macOS..."

# Install py2app if not already installed
pip install -e ".[macos]" || pip install py2app

# Clean previous builds
rm -rf build dist

# Build the app
python setup.py py2app

echo "✅ App bundle created at dist/LLM OS.app"
echo "📦 Run ./build_dmg.sh to create DMG disk image"
