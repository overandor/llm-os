"""
Solana Integration for Inference Service
Token gating and payment processing
Supports both local ledger mode and Solana devnet mode
"""
from typing import Optional, Dict, Any
from pathlib import Path
import json
import os
from dataclasses import dataclass

# Try to import Solana dependencies
SOLANA_AVAILABLE = False
try:
    from solana.rpc.api import Client
    from solana.rpc.commitment import Confirmed
    from solana.publickey import PublicKey
    from solana.keypair import Keypair
    from solana.transaction import Transaction
    from solders.transaction import VersionedTransaction
    from anchorpy import Provider, Program, Wallet
    import asyncio
    SOLANA_AVAILABLE = True
except ImportError:
    pass


@dataclass
class SolanaConfig:
    """Solana configuration."""
    ledger_mode: str = "local"  # local | solana_devnet
    rpc_url: str = "https://api.devnet.solana.com"
    ws_url: str = "wss://api.devnet.solana.com"
    program_id: str = "INF7oken111111111111111111111111111111111"
    staking_program_id: str = "LStk1111111111111111111111111111111111111"
    token_mint: str = ""
    private_key_path: str = "~/.config/solana/id.json"
    local_db_path: str = "~/llm_liquid_endpoints.db"


class SolanaManager:
    """Manage token operations for inference service.
    
    Supports both local ledger mode (SQLite) and Solana devnet mode.
    """
    
    def __init__(self, config: SolanaConfig):
        self.config = config
        self.ledger_mode = config.ledger_mode or os.getenv("LEDGER_MODE", "local")
        
        if self.ledger_mode == "solana_devnet":
            if not SOLANA_AVAILABLE:
                raise RuntimeError("Solana dependencies not available. Install with: pip install solana anchorpy")
            self.client = Client(self.config.rpc_url)
            self.wallet = self._load_wallet()
            self.provider = Provider(self.wallet, self.client)
        else:
            # Local ledger mode - use SQLite
            from liquid_endpoint_store import LiquidEndpointStore
            self.store = LiquidEndpointStore(Path(config.local_db_path).expanduser())
        
    def _load_wallet(self) -> Keypair:
        """Load wallet from keypair file."""
        key_path = Path(self.config.private_key_path).expanduser()
        with open(key_path, 'r') as f:
            key_data = json.load(f)
        return Keypair.from_secret_key(bytes(key_data))
    
    async def get_token_balance(self, wallet_address: str, token_symbol: str = "INF") -> int:
        """Get token balance for a wallet."""
        if self.ledger_mode == "local":
            return self.store.get_balance(wallet_address, token_symbol)
        else:
            pubkey = PublicKey(wallet_address)
            response = await self.client.get_token_account_balance(pubkey)
            return int(response.value.amount) if response.value else 0
    
    async def transfer_tokens(
        self,
        from_address: str,
        to_address: str,
        amount: int,
        token_symbol: str = "INF",
        memo: Optional[str] = None
    ) -> str:
        """Transfer tokens to another address."""
        if self.ledger_mode == "local":
            self.store.adjust_balance(from_address, token_symbol, -amount)
            self.store.adjust_balance(to_address, token_symbol, amount)
            return f"local_tx_{hashlib.sha256(f"{from_address}{to_address}{amount}".encode()).hexdigest()[:16]}"
        else:
            # Placeholder for actual Solana token transfer
            # In production, this would:
            # - Create SPL token transfer instruction
            # - Sign with wallet
            # - Send transaction
            # - Return transaction signature
            return "mock_signature_123"
    
    async def burn_tokens_for_inference(
        self,
        wallet_address: str,
        amount: int,
        context_id: str
    ) -> str:
        """Burn tokens as payment for inference."""
        if self.ledger_mode == "local":
            self.store.adjust_balance(wallet_address, "INF", -amount)
            return f"local_burn_{hashlib.sha256(f"{wallet_address}{amount}{context_id}".encode()).hexdigest()[:16]}"
        else:
            # Placeholder for burn instruction
            # In production, this would call the inference-token program's burn_tokens instruction
            return "burn_signature_456"
    
    async def check_payment(
        self,
        signature: str,
        required_amount: int
    ) -> bool:
        """Verify a payment transaction."""
        if self.ledger_mode == "local":
            # Local mode: signatures are just hashes, assume valid if format matches
            return signature.startswith("local_")
        else:
            # Placeholder for payment verification
            # In production, this would:
            # - Get transaction from RPC
            # - Verify it's a burn or transfer
            # - Check amount matches required
            return True
    
    async def get_stake_info(self, wallet_address: str, endpoint_id: Optional[str] = None) -> Dict:
        """Get staking information for a wallet."""
        if self.ledger_mode == "local":
            if endpoint_id:
                from liquid_endpoint_store import liquid_symbol
                symbol = liquid_symbol(endpoint_id)
                balance = self.store.get_balance(wallet_address, symbol)
                return {
                    "staked_amount": balance,
                    "pending_rewards": 0,
                    "reward_rate": 100,
                }
            return {
                "staked_amount": 0,
                "pending_rewards": 0,
                "reward_rate": 100,
            }
        else:
            # Placeholder for staking info retrieval
            # In production, this would query the liquid-staking program
            return {
                "staked_amount": 0,
                "pending_rewards": 0,
                "reward_rate": 100,
            }
    
    async def stake_tokens(
        self,
        wallet_address: str,
        amount: int,
        pool_address: str
    ) -> str:
        """Stake tokens in the liquid staking pool."""
        if self.ledger_mode == "local":
            # Handled by liquid_endpoints.py store operations
            return f"local_stake_{hashlib.sha256(f"{wallet_address}{amount}{pool_address}".encode()).hexdigest()[:16]}"
        else:
            # Placeholder for staking instruction
            # In production, this would call the liquid-staking program's stake instruction
            return "stake_signature_789"
    
    async def unstake_tokens(
        self,
        wallet_address: str,
        amount: int,
        pool_address: str
    ) -> str:
        """Unstake tokens from the pool."""
        if self.ledger_mode == "local":
            # Handled by liquid_endpoints.py store operations
            return f"local_unstake_{hashlib.sha256(f"{wallet_address}{amount}{pool_address}".encode()).hexdigest()[:16]}"
        else:
            # Placeholder for unstaking instruction
            return "unstake_signature_012"
    
    async def claim_rewards(
        self,
        wallet_address: str,
        pool_address: str
    ) -> str:
        """Claim staking rewards."""
        if self.ledger_mode == "local":
            # Handled by liquid_endpoints.py store operations
            return f"local_claim_{hashlib.sha256(f"{wallet_address}{pool_address}".encode()).hexdigest()[:16]}"
        else:
            # Placeholder for claim rewards instruction
            return "claim_rewards_signature_345"


class TokenGating:
    """Token gating for inference access."""
    
    def __init__(self, solana_manager: SolanaManager):
        self.solana = solana_manager
        self.cost_per_request = 1  # Tokens per inference request
        self.staker_discount = 0.5  # 50% discount for stakers
        
    async def check_access(
        self,
        wallet_address: str,
        required_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """Check if wallet has sufficient tokens for access."""
        required = required_tokens or self.cost_per_request
        
        balance = await self.solana.get_token_balance(wallet_address)
        stake_info = await self.solana.get_stake_info(wallet_address)
        
        # Apply staker discount
        effective_cost = required
        if stake_info["staked_amount"] > 0:
            effective_cost = int(required * (1 - self.staker_discount))
        
        has_access = balance >= effective_cost
        
        return {
            "has_access": has_access,
            "balance": balance,
            "required": effective_cost,
            "staked": stake_info["staked_amount"],
            "pending_rewards": stake_info["pending_rewards"],
            "is_staker": stake_info["staked_amount"] > 0,
        }
    
    async def process_payment(
        self,
        wallet_address: str,
        conversation_id: str
    ) -> Dict[str, Any]:
        """Process payment for inference request."""
        access_info = await self.check_access(wallet_address)
        
        if not access_info["has_access"]:
            return {
                "success": False,
                "error": "Insufficient tokens",
                "required": access_info["required"],
                "balance": access_info["balance"],
            }
        
        # Burn tokens
        signature = await self.solana.burn_tokens_for_inference(
            access_info["required"],
            conversation_id
        )
        
        return {
            "success": True,
            "signature": signature,
            "amount_burned": access_info["required"],
            "balance_after": access_info["balance"] - access_info["required"],
        }


def create_solana_manager(
    ledger_mode: Optional[str] = None,
    rpc_url: str = "https://api.devnet.solana.com",
    private_key_path: str = "~/.config/solana/id.json",
    local_db_path: str = "~/llm_liquid_endpoints.db"
) -> SolanaManager:
    """Create Solana manager with default config."""
    config = SolanaConfig(
        ledger_mode=ledger_mode or os.getenv("LEDGER_MODE", "local"),
        rpc_url=rpc_url,
        private_key_path=private_key_path,
        local_db_path=local_db_path
    )
    return SolanaManager(config)


if __name__ == "__main__":
    # Test Solana integration
    import asyncio
    import hashlib
    
    async def test():
        print(f"Solana available: {SOLANA_AVAILABLE}")
        print(f"Ledger mode: {os.getenv('LEDGER_MODE', 'local')}")
        
        manager = create_solana_manager()
        print(f"Manager ledger mode: {manager.ledger_mode}")
        
        gating = TokenGating(manager)
        
        # Test access check
        wallet = "test_wallet_address"
        access = await gating.check_access(wallet)
        print(f"Access check: {access}")
        
        # Test payment processing
        payment = await gating.process_payment(wallet, "test_conv")
        print(f"Payment: {payment}")
    
    asyncio.run(test())
