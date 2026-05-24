#!/bin/bash
# Deploy Solana programs to devnet

set -e

echo "🚀 Deploying Enterprise LLM Suite to Solana Devnet"

# Check if Anchor is installed
if ! command -v anchor &> /dev/null; then
    echo "❌ Anchor not found. Install with: cargo install anchor-cli"
    exit 1
fi

# Check if Solana CLI is installed
if ! command -v solana &> /dev/null; then
    echo "❌ Solana CLI not found. Install with: sh -c \"$(curl -sSfL https://release.solana.com/stable/install)\""
    exit 1
fi

# Set to devnet
echo "📡 Setting cluster to devnet..."
solana config set --url devnet

# Check wallet balance
echo "💰 Checking wallet balance..."
solana balance

# Airdrop if needed (devnet only)
BALANCE=$(solana balance | awk '{print $1}')
if (( $(echo "$BALANCE < 1" | bc -l) )); then
    echo "💸 Airdropping 2 SOL..."
    solana airdrop 2
fi

# Build programs
echo "🔨 Building programs..."
anchor build

# Deploy inference token program
echo "🪙 Deploying Inference Token program..."
anchor deploy --program-name inference-token

# Deploy liquid staking program
echo "💎 Deploying Liquid Staking program..."
anchor deploy --program-name liquid-staking

# Get program IDs
INFERENCE_TOKEN_ID=$(anchor keys list | grep inference_token | awk '{print $3}')
LIQUID_STAKING_ID=$(anchor keys list | grep liquid_staking | awk '{print $3}')

echo "✅ Deployment complete!"
echo ""
echo "Program IDs:"
echo "  Inference Token: $INFERENCE_TOKEN_ID"
echo "  Liquid Staking: $LIQUID_STAKING_ID"
echo ""
echo "Update Anchor.toml with these program IDs"
echo ""
echo "Next steps:"
echo "  1. Initialize the token mint"
echo "  2. Initialize the staking pool"
echo "  3. Update Python integration with program IDs"
