#!/bin/bash
# Start Enterprise LLM Suite Web Server

set -e

echo "🚀 Starting Enterprise LLM Suite Web Server..."

# Check if dependencies are installed
if ! python -c "import fastapi" 2>/dev/null; then
    echo "📦 Installing dependencies..."
    pip install -e ".[enterprise]"
fi

# Start server
python enterprise_server.py
