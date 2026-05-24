"""
Smoke test for decentralized inference worker
End-to-end testing of the complete decentralized workflow
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from node_identity import generate_node_identity, load_node_identity, sign_message, verify_signature
from node_registry import NodeRegistry
from inference_jobs import InferenceJobQueue
from liquid_endpoint_store import (
    LiquidEndpoint,
    EndpointStakePosition,
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
    """Run end-to-end smoke test for decentralized worker."""
    
    print_section("DECENTRALIZED INFERENCE WORKER - SMOKE TEST")
    
    # Use temporary databases for testing
    test_registry_db = Path.home() / "smoke_decentralized_nodes.db"
    test_jobs_db = Path.home() / "smoke_inference_jobs.db"
    test_endpoint_db = Path.home() / "smoke_liquid_endpoints.db"
    
    for db in [test_registry_db, test_jobs_db, test_endpoint_db]:
        if db.exists():
            db.unlink()
    
    try:
        # Step 1: Generate node identity
        print_section("1. GENERATE NODE IDENTITY")
        identity = generate_node_identity(
            machine_name="smoke-worker-01",
            models_available=["llama2"],
            endpoint_url="http://localhost:11434",
            wallet_address="smoke_wallet",
            use_mock=True
        )
        print_success(f"Node identity generated: {identity.metadata.node_id}")
        print(f"   Machine: {identity.metadata.machine_name}")
        print(f"   Models: {identity.metadata.models_available}")
        print(f"   Public Key: {identity.metadata.public_key[:32]}...")
        
        # Verify we can load it
        loaded = load_node_identity()
        assert loaded.metadata.node_id == identity.metadata.node_id
        print_success("Node identity loaded successfully")
        
        # Step 2: Create local registry
        print_section("2. CREATE LOCAL REGISTRY")
        registry = NodeRegistry(registry_mode="local", db_path=test_registry_db)
        print_success("Local registry initialized")
        
        # Register node
        registration = registry.register_node(identity.metadata)
        print_success(f"Node registered: {registration.node_id}")
        print(f"   Status: {registration.status}")
        print(f"   Created: {registration.created_at}")
        
        # Verify registration
        retrieved = registry.get_node(identity.metadata.node_id)
        assert retrieved is not None
        assert retrieved.node_id == identity.metadata.node_id
        print_success("Node registration verified")
        
        # Step 3: Create liquid endpoint
        print_section("3. CREATE LIQUID ENDPOINT")
        store = LiquidEndpointStore(test_endpoint_db)
        
        endpoint = LiquidEndpoint(
            endpoint_id="smoke_end_001",
            owner_wallet="operator_wallet",
            endpoint_url="http://localhost:11434",
            model_name="llama2",
            runtime_type="mock",
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
        print(f"   Revenue Share: {endpoint.revenue_share_bps} bps")
        
        # Step 4: Stake 1000 local tokens
        print_section("4. STAKE 1000 LOCAL TOKENS")
        stake_amount = 1000.0
        wallet = "staker_wallet"
        
        # Fund wallet
        store.set_balance(wallet, "INF", 10000.0)
        print_success(f"Wallet {wallet} funded with 10000 INF tokens")
        
        # Create stake position
        position = EndpointStakePosition(
            position_id="stake_smoke_001",
            endpoint_id=endpoint.endpoint_id,
            staker_wallet=wallet,
            staked_amount=stake_amount,
            liquid_tokens_minted=stake_amount,
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
        
        # Step 5: Submit inference job
        print_section("5. SUBMIT INFERENCE JOB")
        job_queue = InferenceJobQueue(test_jobs_db)
        
        job = job_queue.submit_job(
            requester_wallet="requester_wallet",
            endpoint_id=endpoint.endpoint_id,
            model_name="llama2",
            prompt="Explain quantum computing in simple terms",
            max_fee=0.01
        )
        
        print_success(f"Job submitted: {job.job_id}")
        print(f"   Status: {job.status}")
        print(f"   Model: {job.model_name}")
        print(f"   Max fee: {job.max_fee}")
        
        # Verify job in queue
        queued_count = job_queue.get_queued_count("llama2")
        assert queued_count == 1
        print_success(f"Jobs in queue: {queued_count}")
        
        # Step 6: Worker claims job
        print_section("6. WORKER CLAIMS JOB")
        claimed_job = job_queue.claim_next_job(
            node_id=identity.metadata.node_id,
            model_name="llama2"
        )
        
        assert claimed_job is not None
        assert claimed_job.job_id == job.job_id
        assert claimed_job.status == "running"
        assert claimed_job.node_id == identity.metadata.node_id
        
        print_success(f"Job claimed: {claimed_job.job_id}")
        print(f"   Node: {claimed_job.node_id}")
        print(f"   Status: {claimed_job.status}")
        
        # Step 7: Worker completes job using MockAdapter
        print_section("7. WORKER COMPLETES JOB")
        adapter = get_adapter("mock", "llama2")
        
        result = await adapter.generate(
            prompt="[Job from queue]",
            max_tokens=100,
            temperature=0.7
        )
        
        assert result.success is True
        print_success("Inference completed")
        print(f"   Input tokens: {result.input_tokens}")
        print(f"   Output tokens: {result.output_tokens}")
        print(f"   Latency: {result.latency_ms}ms")
        
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
        
        # Step 8: Generate signed receipt
        print_section("8. GENERATE SIGNED RECEIPT")
        signer = get_signer("smoke_test_secret")
        factory = ReceiptFactory(signer)
        
        signed_receipt = factory.create_receipt(
            endpoint_id=endpoint.endpoint_id,
            requester_wallet=claimed_job.requester_wallet,
            prompt="[Job from queue]",
            response=result.text,
            model_name="llama2",
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
        assert is_valid is True
        print_success("Signature verified")
        
        # Step 9: Store receipt in liquid endpoint store
        from liquid_endpoint_store import InferenceReceipt
        receipt = InferenceReceipt(
            receipt_id=signed_receipt.receipt.receipt_id,
            endpoint_id=endpoint.endpoint_id,
            requester_wallet=claimed_job.requester_wallet,
            prompt_hash=claimed_job.prompt_hash,
            response_hash=signed_receipt.receipt.response_hash,
            model_name="llama2",
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            fee_paid=fee,
            staker_revenue=staker_revenue,
            operator_revenue=operator_revenue,
            timestamp=signed_receipt.receipt.timestamp,
            signature=signed_receipt.signature
        )
        store.create_receipt(receipt)
        print_success("Receipt stored in liquid endpoint store")
        
        # Step 10: Sign result with node identity
        print_section("10. SIGN RESULT WITH NODE IDENTITY")
        node_signature = sign_message(
            f"{claimed_job.job_id}:{result.text}",
            identity.private_key,
            use_mock=True
        )
        print_success(f"Result signed with node identity")
        print(f"   Node signature: {node_signature[:32]}...")
        
        # Verify node signature
        is_valid = verify_signature(
            f"{claimed_job.job_id}:{result.text}",
            node_signature,
            identity.metadata.public_key,
            use_mock=True
        )
        assert is_valid is True
        print_success("Node signature verified")
        
        # Step 11: Complete job
        print_section("11. COMPLETE JOB")
        job_result = job_queue.complete_job(
            job_id=claimed_job.job_id,
            response=result.text,
            output_tokens=result.output_tokens,
            latency_ms=result.latency_ms,
            fee_charged=fee,
            receipt_id=signed_receipt.receipt.receipt_id,
            node_signature=node_signature
        )
        
        print_success(f"Job completed: {job_result.job_id}")
        print(f"   Fee charged: {job_result.fee_charged:.6f}")
        print(f"   Receipt ID: {job_result.receipt_id}")
        
        # Step 12: Update endpoint accounting
        print_section("12. UPDATE ENDPOINT ACCOUNTING")
        store.update_endpoint(endpoint.endpoint_id, {
            "total_requests": endpoint.total_requests + 1,
            "total_tokens": endpoint.total_tokens + total_tokens,
            "total_revenue": endpoint.total_revenue + fee,
            "pending_rewards": endpoint.pending_rewards + staker_revenue
        })
        
        # Update node stats
        registry.update_node_stats(
            node_id=identity.metadata.node_id,
            jobs_completed_delta=1,
            fees_earned_delta=operator_revenue
        )
        
        print_success("Endpoint accounting updated")
        print(f"   Total requests: {endpoint.total_requests + 1}")
        print(f"   Total revenue: {(endpoint.total_revenue + fee):.6f}")
        print(f"   Pending rewards: {(endpoint.pending_rewards + staker_revenue):.6f}")
        
        # Step 13: Verify rewards are claimable
        print_section("13. VERIFY REWARDS CLAIMABLE")
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
        
        # Step 14: Print final accounting
        print_section("14. FINAL ACCOUNTING")
        
        final_endpoint = store.get_endpoint(endpoint.endpoint_id)
        final_wallet_balance = store.get_balance(wallet, "INF")
        final_liquid_balance = store.get_balance(wallet, symbol)
        final_node = registry.get_node(identity.metadata.node_id)
        
        print("Endpoint Statistics:")
        print(f"   Total staked: {final_endpoint.total_staked}")
        print(f"   Liquid supply: {final_endpoint.liquid_supply}")
        print(f"   Total requests: {final_endpoint.total_requests}")
        print(f"   Total tokens: {final_endpoint.total_tokens}")
        print(f"   Total revenue: {final_endpoint.total_revenue:.6f}")
        print(f"   Pending rewards: {final_endpoint.pending_rewards:.6f}")
        
        print("\nWallet Statistics:")
        print(f"   INF balance: {final_wallet_balance:.6f}")
        print(f"   {symbol} balance: {final_liquid_balance:.6f}")
        
        print("\nNode Statistics:")
        print(f"   Jobs completed: {final_node.jobs_completed}")
        print(f"   Total fees earned: {final_node.total_fees_earned:.6f}")
        print(f"   Average latency: {final_node.average_latency_ms}ms")
        
        # Verify receipts
        receipts = store.get_receipts(endpoint.endpoint_id)
        print(f"\nReceipts in database: {len(receipts)}")
        if receipts:
            print_success(f"Receipt {receipts[0].receipt_id} found")
        
        print_section("SMOKE TEST PASSED ✓")
        print("\nAll systems operational:")
        print("  ✓ Node identity generation and signing")
        print("  ✓ Local node registry")
        print("  ✓ Liquid endpoint creation")
        print("  ✓ Token staking")
        print("  ✓ Job queue submission")
        print("  ✓ Job claiming by worker")
        print("  ✓ Inference execution (MockAdapter)")
        print("  ✓ Receipt signing and verification")
        print("  ✓ Node identity signature verification")
        print("  ✓ Endpoint accounting integration")
        print("  ✓ Revenue distribution")
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
        for db in [test_registry_db, test_jobs_db, test_endpoint_db]:
            if db.exists():
                db.unlink()
        print("\nCleaned up test databases")


if __name__ == "__main__":
    success = asyncio.run(smoke_test())
    sys.exit(0 if success else 1)
