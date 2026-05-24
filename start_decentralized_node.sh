#!/bin/bash

# Decentralized Local Inference Node Launcher
# This script initializes and starts the full decentralized inference stack

set -e

# Configuration
LLM_OS_DIR="/Users/alep/Downloads/llm-os"
DATA_DIR="$LLM_OS_DIR/.node"
LEDGER_DIR="$LLM_OS_DIR/.ledger"
RECEIPTS_DIR="$LLM_OS_DIR/.receipts"
RUNTIME_DIR="$LLM_OS_DIR/.runtime"
PORT=8000

echo "=========================================="
echo "  Decentralized Local Inference Node"
echo "=========================================="
echo ""

# Change to llm-os directory
cd "$LLM_OS_DIR"
echo "✓ Working directory: $LLM_OS_DIR"

# Create local data directories
echo ""
echo "Creating local data directories..."
mkdir -p "$DATA_DIR"
mkdir -p "$LEDGER_DIR"
mkdir -p "$RECEIPTS_DIR"
mkdir -p "$RUNTIME_DIR"
echo "✓ Data directories created"

# Generate node identity if missing
echo ""
echo "Checking node identity..."
IDENTITY_FILE="$HOME/.llm_os/node_identity.json"
if [ ! -f "$IDENTITY_FILE" ]; then
    echo "Node identity not found. Generating..."
    python3 -c "
from node_identity import generate_node_identity
identity = generate_node_identity(
    machine_name='local-worker',
    models_available=['llama2', 'mock'],
    endpoint_url='http://localhost:8000',
    wallet_address='local_operator_wallet',
    use_mock=True
)
print(f'✓ Node ID: {identity.metadata.node_id}')
print(f'✓ Public Key: {identity.metadata.public_key[:32]}...')
"
else
    echo "✓ Node identity exists"
fi

# Initialize local liquid endpoint ledger
echo ""
echo "Initializing local liquid endpoint ledger..."
LEDGER_DB="$HOME/llm_liquid_endpoints.db"
if [ ! -f "$LEDGER_DB" ]; then
    echo "Creating new ledger..."
    python3 -c "
from liquid_endpoint_store import LiquidEndpointStore
store = LiquidEndpointStore()
print('✓ Ledger initialized')
"
else
    echo "✓ Ledger exists"
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
echo "  • http://localhost:$PORT/staking"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start the server
python3 enterprise_server.py
