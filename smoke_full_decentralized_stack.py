"""
Full stack smoke test for decentralized inference node
Tests the complete flow from node registration to revenue claiming
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timezone

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
from accounting_audit import run_accounting_audit


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


async def smoke_full_stack():
    """Run full stack smoke test."""
    
    print_section("FULL DECENTRALIZED STACK SMOKE TEST")
    
    # Use temporary databases for testing
    test_registry_db = Path.home() / "smoke_full_registry.db"
    test_jobs_db = Path.home() / "smoke_full_jobs.db"
    test_endpoint_db = Path.home() / "smoke_full_endpoints.db"
    
    for db in [test_registry_db, test_jobs_db, test_endpoint_db]:
        if db.exists():
            db.unlink()
    
    try:
        # Step 1: Generate node identity
        print_section("1. GENERATE NODE IDENTITY")
        identity = generate_node_identity(
            machine_name="full-stack-worker",
            models_available=["llama2", "mock"],
            endpoint_url="http://localhost:8000",
            wallet_address="full_stack_operator",
            use_mock=True
        )
        print_success(f"Node identity generated: {identity.metadata.node_id}")
        print(f"   Machine: {identity.metadata.machine_name}")
        print(f"   Models: {identity.metadata.models_available}")
        print(f"   Public Key: {identity.metadata.public_key[:32]}...")
        
        # Step 2: Register node in local registry
        print_section("2. REGISTER NODE IN LOCAL REGISTRY")
        registry = NodeRegistry(registry_mode="local", db_path=test_registry_db)
        registration = registry.register_node(identity.metadata)
        print_success(f"Node registered: {registration.node_id}")
        print(f"   Status: {registration.status}")
        print(f"   Created: {registration.created_at}")
        
        # Step 3: Create liquid endpoint
        print_section("3. CREATE LIQUID ENDPOINT")
        store = LiquidEndpointStore(test_endpoint_db)
        
        endpoint = LiquidEndpoint(
            endpoint_id="full_stack_end_001",
            owner_wallet="operator_wallet",
            endpoint_url="http://localhost:8000",
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
        
        # Step 4: Fund wallets
        print_section("4. FUND REQUESTER AND STAKER WALLETS")
        requester_wallet = "requester_wallet"
        staker_wallet = "staker_wallet"
        
        store.set_balance(requester_wallet, "INF", 10000.0)
        store.set_balance(staker_wallet, "INF", 10000.0)
        print_success(f"Wallets funded with 10000 INF tokens each")
        
        # Step 5: Stake into endpoint
        print_section("5. STAKE INTO ENDPOINT")
        stake_amount = 1000.0
        
        position = EndpointStakePosition(
            position_id="stake_full_001",
            endpoint_id=endpoint.endpoint_id,
            staker_wallet=staker_wallet,
            staked_amount=stake_amount,
            liquid_tokens_minted=stake_amount,
            entry_exchange_rate=1.0,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat()
        )
        
        store.create_stake_position(position)
        
        store.update_endpoint(endpoint.endpoint_id, {
            "total_staked": stake_amount,
            "liquid_supply": stake_amount,
            "exchange_rate": 1.0
        })
        
        symbol = f"lsEND-{endpoint.endpoint_id[:8]}"
        store.set_balance(staker_wallet, symbol, stake_amount)
        
        print_success(f"Staked {stake_amount} tokens")
        print(f"   Liquid tokens minted: {stake_amount}")
        print(f"   Liquid symbol: {symbol}")
        
        # Step 6: Submit inference job
        print_section("6. SUBMIT INFERENCE JOB")
        job_queue = InferenceJobQueue(test_jobs_db)
        
        job = job_queue.submit_job(
            requester_wallet=requester_wallet,
            endpoint_id=endpoint.endpoint_id,
            model_name="llama2",
            prompt="Explain quantum computing in simple terms",
            max_fee=0.01
        )
        
        print_success(f"Job submitted: {job.job_id}")
        print(f"   Status: {job.status}")
        print(f"   Model: {job.model_name}")
        print(f"   Max fee: {job.max_fee}")
        
        # Step 7: Worker claims job
        print_section("7. WORKER CLAIMS JOB")
        claimed_job = job_queue.claim_next_job(
            node_id=identity.metadata.node_id,
            model_name="llama2"
        )
        
        assert claimed_job is not None
        assert claimed_job.job_id == job.job_id
        assert claimed_job.status == "running"
        
        print_success(f"Job claimed: {claimed_job.job_id}")
        print(f"   Node: {claimed_job.node_id}")
        print(f"   Status: {claimed_job.status}")
        
        # Step 8: Worker completes job
        print_section("8. WORKER COMPLETES JOB")
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
        
        # Step 9: Calculate fee and revenue
        total_tokens = result.input_tokens + result.output_tokens
        fee = (total_tokens / 1000) * endpoint.price_per_1k_tokens
        staker_revenue = fee * (endpoint.revenue_share_bps / 10000.0)
        operator_revenue = fee - staker_revenue
        
        print(f"\n   Fee calculation:")
        print(f"   Total tokens: {total_tokens}")
        print(f"   Fee: {fee:.6f} tokens")
        print(f"   Staker revenue (70%): {staker_revenue:.6f} tokens")
        print(f"   Operator revenue (30%): {operator_revenue:.6f} tokens")
        
        # Step 10: Generate signed receipt
        print_section("9. GENERATE SIGNED RECEIPT")
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
        
        # Step 11: Store receipt
        print_section("10. STORE RECEIPT IN LEDGER")
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
        
        # Step 12: Sign result with node identity
        print_section("11. SIGN RESULT WITH NODE IDENTITY")
        node_signature = sign_message(
            f"{claimed_job.job_id}:{result.text}",
            identity.private_key,
            use_mock=True
        )
        print_success("Result signed with node identity")
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
        
        # Step 13: Complete job
        print_section("12. COMPLETE JOB")
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
        
        # Step 14: Update endpoint accounting
        print_section("13. UPDATE ENDPOINT ACCOUNTING")
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
        
        # Step 15: Claim staker rewards
        print_section("14. CLAIM STAKER REWARDS")
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
            store.adjust_balance(staker_wallet, "INF", claimable)
            print_success(f"Claimed {claimable:.6f} tokens")
        
        # Step 16: Run accounting audit
        print_section("15. RUN ACCOUNTING AUDIT")
        audit_passed = run_accounting_audit(test_endpoint_db)
        
        if not audit_passed:
            print_error("Accounting audit failed")
            return False
        
        # Step 17: Verify receipt signature
        print_section("16. VERIFY RECEIPT SIGNATURE")
        endpoint_receipts = store.get_receipts(endpoint.endpoint_id)
        stored_receipt = next((r for r in endpoint_receipts if r.receipt_id == signed_receipt.receipt.receipt_id), None)
        assert stored_receipt is not None
        assert stored_receipt.signature == signed_receipt.signature
        print_success("Receipt signature verified in ledger")
        
        # Step 18: Print final URLs
        print_section("17. SYSTEM URLS")
        print("Server URLs (when running):")
        print("  • http://localhost:8000")
        print("  • http://localhost:8000/liquid-endpoints")
        print("  • http://localhost:8000/decentralized-node")
        print("  • http://localhost:8000/staking")
        print("\nAPI Endpoints:")
        print("  • POST /api/decentralized/node/register")
        print("  • GET /api/decentralized/node/me")
        print("  • POST /api/decentralized/node/heartbeat")
        print("  • GET /api/decentralized/nodes")
        print("  • POST /api/decentralized/jobs")
        print("  • GET /api/decentralized/jobs/{job_id}")
        print("  • GET /api/decentralized/jobs/{job_id}/receipt")
        print("  • POST /api/decentralized/worker/start")
        print("  • POST /api/decentralized/worker/stop")
        print("  • GET /api/decentralized/worker/status")
        
        # Final summary
        print_section("FULL DECENTRALIZED STACK SMOKE TEST PASSED ✓")
        print("\nAll systems operational:")
        print("  ✓ Node identity generation and signing")
        print("  ✓ Local node registry")
        print("  ✓ Liquid endpoint creation")
        print("  ✓ Wallet funding")
        print("  ✓ Token staking")
        print("  ✓ Job queue submission")
        print("  ✓ Job claiming by worker")
        print("  ✓ Inference execution (MockAdapter)")
        print("  ✓ Fee and revenue calculation")
        print("  ✓ Receipt signing and verification")
        print("  ✓ Node identity signature verification")
        print("  ✓ Receipt storage in ledger")
        print("  ✓ Job completion")
        print("  ✓ Endpoint accounting integration")
        print("  ✓ Node stats update")
        print("  ✓ Revenue distribution")
        print("  ✓ Reward claiming")
        print("  ✓ Accounting audit")
        print("  ✓ Receipt signature verification")
        print("  ✓ Data persistence")
        
        return True
        
    except Exception as e:
        print_section("FULL STACK SMOKE TEST FAILED ✗")
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
    success = asyncio.run(smoke_full_stack())
    sys.exit(0 if success else 1)
