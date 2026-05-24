#!/bin/bash

# Sovereign Domain Node Launcher
# This script initializes and starts the integrated domain node with decentralized inference

set -e

# Configuration
LLM_OS_DIR="/Users/alep/Downloads/llm-os"
DOMAIN_DIR="$HOME/.llm-os/domain_folders"
NODE_IDENTITY_DIR="$HOME/.llm-os/node_identity"
RECEIPTS_DIR="$HOME/.llm-os/receipts"
PORT=8000

echo "=========================================="
echo "  Sovereign Domain Node"
echo "=========================================="
echo ""

# Change to llm-os directory
cd "$LLM_OS_DIR"
echo "✓ Working directory: $LLM_OS_DIR"

# Create local directories
echo ""
echo "Creating local directories..."
mkdir -p "$DOMAIN_DIR"
mkdir -p "$NODE_IDENTITY_DIR"
mkdir -p "$RECEIPTS_DIR"
echo "✓ Directories created"

# Generate node identity if missing
echo ""
echo "Checking node identity..."
IDENTITY_FILE="$HOME/.llm_os/node_identity.json"
if [ ! -f "$IDENTITY_FILE" ]; then
    echo "Node identity not found. Generating..."
    python3 -c "
from node_identity import generate_node_identity
identity = generate_node_identity(
    machine_name='domain-node',
    models_available=['llama2', 'mock'],
    endpoint_url='http://localhost:8000',
    wallet_address='domain_operator_wallet',
    use_mock=True
)
print(f'✓ Node ID: {identity.metadata.node_id}')
print(f'✓ Public Key: {identity.metadata.public_key[:32]}...')
"
else
    echo "✓ Node identity exists"
fi

# Initialize domain folder store
echo ""
echo "Initializing domain folder store..."
DOMAIN_DB="$HOME/llm_domain_folders.db"
if [ ! -f "$DOMAIN_DB" ]; then
    echo "Creating new domain folder store..."
    python3 -c "
from domain_folder_store import DomainFolderStore
store = DomainFolderStore('$DOMAIN_DB')
print('✓ Domain folder store initialized')
"
else
    echo "✓ Domain folder store exists"
fi

# Start enterprise server
echo ""
echo "=========================================="
echo "  Starting Enterprise Server"
echo "=========================================="
echo ""
echo "Server will be available at:"
echo "  • http://localhost:$PORT"
echo "  • http://localhost:$PORT/liquid-endpoints"
echo "  • http://localhost:$PORT/decentralized-node"
echo "  • http://localhost:$PORT/domain-folder"
echo "  • http://localhost:$PORT/staking"
echo ""
echo "Honest Status:"
echo "  • Local mode active"
echo "  • Public tunnel disabled unless configured"
echo "  • Solana devnet not active unless deployed config exists"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start the server
python3 enterprise_server.py
