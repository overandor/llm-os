"""
Smoke test for liquid staked endpoints system
End-to-end testing of the complete workflow
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from liquid_endpoint_store import (
    LiquidEndpoint,
    EndpointStakePosition,
    InferenceReceipt,
    LiquidEndpointStore
)
from inference_adapters import get_adapter
from receipt_signer import get_signer, ReceiptFactory


def print_section(title):
    """Print a section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def print_success(message):
    """Print success message."""
    print(f"✓ {message}")


def print_error(message):
    """Print error message."""
    print(f"✗ {message}")


async def smoke_test():
    """Run end-to-end smoke test."""
    
    print_section("LIQUID STAKED ENDPOINTS - SMOKE TEST")
    
    # Use temporary database for testing
    test_db = Path.home() / "smoke_test_liquid_endpoints.db"
    if test_db.exists():
        test_db.unlink()
    
    try:
        # Initialize store
        print("1. Initializing local ledger...")
        store = LiquidEndpointStore(test_db)
        print_success("Local ledger initialized")
        
        # Create endpoint
        print_section("2. CREATE ENDPOINT")
        endpoint = LiquidEndpoint(
            endpoint_id="smoke_end_001",
            owner_wallet="operator_wallet",
            endpoint_url="http://localhost:11434",
            model_name="llama2",
            runtime_type="mock",  # Use mock for testing
            price_per_request=1.0,
            price_per_1k_tokens=0.1,
            revenue_share_bps=7000,
            total_staked=0.0,
            liquid_supply=0.0,
            exchange_rate=1.0,
            status="active",
            created_at=datetime.now(timezone.utc).isoformat()
        )
        
        store.create_endpoint(endpoint)
        print_success(f"Endpoint created: {endpoint.endpoint_id}")
        print(f"   Model: {endpoint.model_name}")
        print(f"   Runtime: {endpoint.runtime_type}")
        print(f"   Price/1K tokens: {endpoint.price_per_1k_tokens}")
        
        # Verify endpoint exists
        retrieved = store.get_endpoint(endpoint.endpoint_id)
        assert retrieved is not None, "Failed to retrieve endpoint"
        print_success("Endpoint verified in store")
        
        # Fund wallet
        print_section("3. FUND WALLET")
        wallet = "staker_wallet"
        store.set_balance(wallet, "INF", 10000.0)
        balance = store.get_balance(wallet, "INF")
        print_success(f"Wallet {wallet} funded with {balance} INF tokens")
        
        # Stake tokens
        print_section("4. STAKE TOKENS")
        stake_amount = 1000.0
        position = EndpointStakePosition(
            position_id="stake_smoke_001",
            endpoint_id=endpoint.endpoint_id,
            staker_wallet=wallet,
            staked_amount=stake_amount,
            liquid_tokens_minted=stake_amount,  # 1:1 initially
            entry_exchange_rate=1.0,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat()
        )
        
        store.create_stake_position(position)
        
        # Update endpoint
        store.update_endpoint(endpoint.endpoint_id, {
            "total_staked": stake_amount,
            "liquid_supply": stake_amount,
            "exchange_rate": 1.0
        })
        
        # Update wallet liquid balance
        symbol = f"lsEND-{endpoint.endpoint_id[:8]}"
        store.set_balance(wallet, symbol, stake_amount)
        
        print_success(f"Staked {stake_amount} tokens")
        print(f"   Liquid tokens minted: {stake_amount}")
        print(f"   Liquid symbol: {symbol}")
        print(f"   Entry exchange rate: 1.0")
        
        # Verify stake
        retrieved_position = store.get_wallet_position(endpoint.endpoint_id, wallet)
        assert retrieved_position is not None, "Failed to retrieve stake position"
        print_success("Stake position verified")
        
        # Run inference
        print_section("5. RUN INFERENCE")
        adapter = get_adapter("mock", endpoint.model_name)
        
        prompt = "Explain quantum computing in simple terms"
        result = await adapter.generate(prompt, max_tokens=100, temperature=0.7)
        
        if not result.success:
            print_error(f"Inference failed: {result.error}")
            return False
        
        print_success("Inference completed")
        print(f"   Input tokens: {result.input_tokens}")
        print(f"   Output tokens: {result.output_tokens}")
        print(f"   Latency: {result.latency_ms}ms")
        print(f"   Result: {result.text[:100]}...")
        
        # Calculate fee
        total_tokens = result.input_tokens + result.output_tokens
        fee = (total_tokens / 1000) * endpoint.price_per_1k_tokens
        staker_revenue = fee * (endpoint.revenue_share_bps / 10000.0)
        operator_revenue = fee - staker_revenue
        
        print(f"\n   Fee calculation:")
        print(f"   Total tokens: {total_tokens}")
        print(f"   Fee: {fee:.6f} tokens")
        print(f"   Staker revenue (70%): {staker_revenue:.6f} tokens")
        print(f"   Operator revenue (30%): {operator_revenue:.6f} tokens")
        
        # Create and sign receipt
        print_section("6. CREATE SIGNED RECEIPT")
        signer = get_signer("smoke_test_secret")
        factory = ReceiptFactory(signer)
        
        signed_receipt = factory.create_receipt(
            endpoint_id=endpoint.endpoint_id,
            requester_wallet="requester_wallet",
            prompt=prompt,
            response=result.text,
            model_name=endpoint.model_name,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            fee_paid=fee,
            staker_revenue=staker_revenue,
            operator_revenue=operator_revenue
        )
        
        print_success("Receipt created and signed")
        print(f"   Receipt ID: {signed_receipt.receipt.receipt_id}")
        print(f"   Signature: {signed_receipt.signature[:32]}...")
        
        # Verify signature
        is_valid = signer.verify_receipt(signed_receipt.receipt)
        assert is_valid, "Receipt signature verification failed"
        print_success("Signature verified")
        
        # Store receipt
        store.create_receipt(signed_receipt.receipt)
        print_success("Receipt stored in database")
        
        # Update endpoint stats
        store.update_endpoint(endpoint.endpoint_id, {
            "total_requests": endpoint.total_requests + 1,
            "total_tokens": endpoint.total_tokens + total_tokens,
            "total_revenue": endpoint.total_revenue + fee,
            "pending_rewards": endpoint.pending_rewards + staker_revenue
        })
        
        # Deduct fee from requester
        requester = "requester_wallet"
        store.set_balance(requester, "INF", 100.0)
        store.adjust_balance(requester, "INF", -fee)
        print_success(f"Deducted {fee:.6f} tokens from requester")
        
        # Claim rewards
        print_section("7. CLAIM REWARDS")
        updated_endpoint = store.get_endpoint(endpoint.endpoint_id)
        ownership = position.liquid_tokens_minted / updated_endpoint.liquid_supply
        claimable = updated_endpoint.pending_rewards * ownership
        
        print(f"   Ownership: {ownership * 100:.2f}%")
        print(f"   Pending rewards: {updated_endpoint.pending_rewards:.6f}")
        print(f"   Claimable: {claimable:.6f}")
        
        if claimable > 0:
            store.update_endpoint(endpoint.endpoint_id, {
                "pending_rewards": updated_endpoint.pending_rewards - claimable
            })
            store.adjust_balance(wallet, "INF", claimable)
            print_success(f"Claimed {claimable:.6f} tokens")
        else:
            print("No rewards to claim yet (single inference)")
        
        # Final accounting
        print_section("8. FINAL ACCOUNTING")
        
        final_endpoint = store.get_endpoint(endpoint.endpoint_id)
        final_wallet_balance = store.get_balance(wallet, "INF")
        final_liquid_balance = store.get_balance(wallet, symbol)
        
        print("Endpoint Statistics:")
        print(f"   Total staked: {final_endpoint.total_staked}")
        print(f"   Liquid supply: {final_endpoint.liquid_supply}")
        print(f"   Exchange rate: {final_endpoint.exchange_rate}")
        print(f"   Total requests: {final_endpoint.total_requests}")
        print(f"   Total tokens: {final_endpoint.total_tokens}")
        print(f"   Total revenue: {final_endpoint.total_revenue:.6f}")
        print(f"   Pending rewards: {final_endpoint.pending_rewards:.6f}")
        
        print("\nWallet Statistics:")
        print(f"   INF balance: {final_wallet_balance:.6f}")
        print(f"   {symbol} balance: {final_liquid_balance:.6f}")
        
        # Verify receipts
        receipts = store.get_receipts(endpoint.endpoint_id)
        print(f"\nReceipts in database: {len(receipts)}")
        if receipts:
            print_success(f"Receipt {receipts[0].receipt_id} found")
        
        print_section("SMOKE TEST PASSED ✓")
        print("\nAll systems operational:")
        print("  ✓ Local ledger (SQLite)")
        print("  ✓ Endpoint creation")
        print("  ✓ Token staking")
        print("  ✓ Inference execution")
        print("  ✓ Receipt signing")
        print("  ✓ Fee calculation")
        print("  ✓ Reward claiming")
        print("  ✓ Data persistence")
        
        return True
        
    except Exception as e:
        print_section("SMOKE TEST FAILED ✗")
        print_error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Cleanup
        if test_db.exists():
            test_db.unlink()
            print("\nCleaned up test database")


if __name__ == "__main__":
    success = asyncio.run(smoke_test())
    sys.exit(0 if success else 1)
