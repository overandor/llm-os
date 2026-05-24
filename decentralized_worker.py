"""
Decentralized inference worker daemon
Runs local LLM inference, claims jobs, signs receipts, distributes revenue
"""
import asyncio
import argparse
import signal
import sys
from pathlib import Path
from datetime import datetime, timezone

from node_identity import generate_node_identity, load_node_identity, sign_message
from node_registry import NodeRegistry
from inference_jobs import InferenceJobQueue
from inference_adapters import get_adapter
from receipt_signer import get_signer, ReceiptFactory
from liquid_endpoint_store import LiquidEndpointStore


class DecentralizedWorker:
    """Decentralized inference worker daemon."""
    
    def __init__(
        self,
        endpoint_id: str,
        model_name: str,
        runtime_type: str,
        endpoint_url: str,
        wallet_address: str,
        heartbeat_interval: int = 30
    ):
        self.endpoint_id = endpoint_id
        self.model_name = model_name
        self.runtime_type = runtime_type
        self.endpoint_url = endpoint_url
        self.wallet_address = wallet_address
        self.heartbeat_interval = heartbeat_interval
        
        self.running = False
        self.jobs_completed = 0
        self.total_fees_earned = 0.0
        
        # Initialize components
        self._init_components()
    
    def _init_components(self):
        """Initialize worker components."""
        # Load or generate node identity
        try:
            self.identity = load_node_identity()
            print(f"Loaded existing node identity: {self.identity.metadata.node_id}")
        except FileNotFoundError:
            print("Generating new node identity...")
            self.identity = generate_node_identity(
                machine_name=f"worker-{self.endpoint_id[:8]}",
                models_available=[self.model_name],
                endpoint_url=self.endpoint_url,
                wallet_address=self.wallet_address
            )
            print(f"Generated node identity: {self.identity.metadata.node_id}")
        
        # Initialize registry
        self.registry = NodeRegistry(registry_mode="local")
        
        # Initialize job queue
        self.job_queue = InferenceJobQueue()
        
        # Initialize inference adapter
        self.adapter = get_adapter(self.runtime_type, self.model_name)
        print(f"Initialized {self.runtime_type} adapter for {self.model_name}")
        
        # Initialize receipt signer
        self.receipt_signer = get_signer("worker_signing_key")
        self.receipt_factory = ReceiptFactory(self.receipt_signer)
        
        # Initialize liquid endpoint store
        self.store = LiquidEndpointStore()
    
    async def register_node(self):
        """Register node in the registry."""
        registration = self.registry.register_node(self.identity.metadata)
        print(f"Node registered: {registration.node_id}")
        print(f"Status: {registration.status}")
        return registration
    
    async def send_heartbeat(self):
        """Send heartbeat to registry."""
        registration = self.registry.update_heartbeat(
            node_id=self.identity.metadata.node_id,
            latency_ms=0,  # Will be updated after job
            model_loaded=True,
            available_memory=8192,
            queue_depth=self.job_queue.get_queued_count(self.model_name)
        )
        print(f"Heartbeat sent at {registration.last_heartbeat}")
        return registration
    
    async def claim_and_process_job(self):
        """Claim next job and process it."""
        # Claim next job
        job = self.job_queue.claim_next_job(
            node_id=self.identity.metadata.node_id,
            model_name=self.model_name
        )
        
        if not job:
            return None
        
        print(f"Claimed job: {job.job_id}")
        print(f"  Requester: {job.requester_wallet}")
        print(f"  Max fee: {job.max_fee}")
        
        # Get endpoint details
        endpoint = self.store.get_endpoint(self.endpoint_id)
        if not endpoint:
            print(f"Error: Endpoint {self.endpoint_id} not found")
            self.job_queue.fail_job(job.job_id, "Endpoint not found")
            return None
        
        # Run inference (use mock prompt since we only have hash)
        # In production, would decrypt encrypted_prompt
        start_time = datetime.now(timezone.utc)
        
        try:
            result = await self.adapter.generate(
                prompt="[Job from queue]",  # Placeholder
                max_tokens=512,
                temperature=0.7
            )
            
            if not result.success:
                self.job_queue.fail_job(job.job_id, result.error or "Inference failed")
                return None
            
            latency_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            
            # Calculate fee
            total_tokens = result.input_tokens + result.output_tokens
            fee = (total_tokens / 1000) * endpoint.price_per_1k_tokens
            fee = min(fee, job.max_fee)  # Respect max fee
            
            # Split revenue
            staker_revenue = fee * (endpoint.revenue_share_bps / 10000.0)
            operator_revenue = fee - staker_revenue
            
            # Create signed receipt
            signed_receipt = self.receipt_factory.create_receipt(
                endpoint_id=self.endpoint_id,
                requester_wallet=job.requester_wallet,
                prompt="[Job from queue]",
                response=result.text,
                model_name=self.model_name,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                fee_paid=fee,
                staker_revenue=staker_revenue,
                operator_revenue=operator_revenue
            )
            
            # Store receipt in liquid endpoint store
            from liquid_endpoint_store import InferenceReceipt
            receipt = InferenceReceipt(
                receipt_id=signed_receipt.receipt.receipt_id,
                endpoint_id=self.endpoint_id,
                requester_wallet=job.requester_wallet,
                prompt_hash=job.prompt_hash,
                response_hash=signed_receipt.receipt.response_hash,
                model_name=self.model_name,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                fee_paid=fee,
                staker_revenue=staker_revenue,
                operator_revenue=operator_revenue,
                timestamp=signed_receipt.receipt.timestamp,
                signature=signed_receipt.signature
            )
            self.store.create_receipt(receipt)
            
            # Update endpoint stats
            self.store.update_endpoint(self.endpoint_id, {
                "total_requests": endpoint.total_requests + 1,
                "total_tokens": endpoint.total_tokens + total_tokens,
                "total_revenue": endpoint.total_revenue + fee,
                "pending_rewards": endpoint.pending_rewards + staker_revenue
            })
            
            # Sign result with node identity
            node_signature = sign_message(
                f"{job.job_id}:{result.text}",
                self.identity.private_key
            )
            
            # Complete job
            job_result = self.job_queue.complete_job(
                job_id=job.job_id,
                response=result.text,
                output_tokens=result.output_tokens,
                latency_ms=latency_ms,
                fee_charged=fee,
                receipt_id=signed_receipt.receipt.receipt_id,
                node_signature=node_signature
            )
            
            # Update node stats
            self.registry.update_node_stats(
                node_id=self.identity.metadata.node_id,
                jobs_completed_delta=1,
                fees_earned_delta=operator_revenue
            )
            
            self.jobs_completed += 1
            self.total_fees_earned += operator_revenue
            
            print(f"Job completed: {job.job_id}")
            print(f"  Tokens: {total_tokens}")
            print(f"  Fee: {fee:.6f}")
            print(f"  Staker revenue: {staker_revenue:.6f}")
            print(f"  Operator revenue: {operator_revenue:.6f}")
            print(f"  Latency: {latency_ms}ms")
            
            return job_result
            
        except Exception as e:
            print(f"Error processing job: {e}")
            self.job_queue.fail_job(job.job_id, str(e))
            return None
    
    async def run(self):
        """Main worker loop."""
        self.running = True
        
        # Register node
        await self.register_node()
        
        print(f"\nWorker started:")
        print(f"  Node ID: {self.identity.metadata.node_id}")
        print(f"  Model: {self.model_name}")
        print(f"  Runtime: {self.runtime_type}")
        print(f"  Endpoint: {self.endpoint_id}")
        print(f"  Heartbeat interval: {self.heartbeat_interval}s")
        print()
        
        # Main loop
        while self.running:
            try:
                # Send heartbeat
                await self.send_heartbeat()
                
                # Claim and process job
                await self.claim_and_process_job()
                
                # Wait for next cycle
                await asyncio.sleep(self.heartbeat_interval)
                
            except KeyboardInterrupt:
                print("\nShutting down worker...")
                self.running = False
                break
            except Exception as e:
                print(f"Error in worker loop: {e}")
                await asyncio.sleep(self.heartbeat_interval)
        
        print(f"Worker stopped. Jobs completed: {self.jobs_completed}, Fees earned: {self.total_fees_earned:.6f}")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Decentralized inference worker")
    parser.add_argument("--endpoint", required=True, help="Liquid endpoint ID")
    parser.add_argument("--model", required=True, help="Model name")
    parser.add_argument("--runtime", required=True, choices=["ollama", "llama_cpp", "mock"], help="Runtime type")
    parser.add_argument("--url", required=True, help="Endpoint URL")
    parser.add_argument("--wallet", required=True, help="Wallet address")
    parser.add_argument("--heartbeat", type=int, default=30, help="Heartbeat interval in seconds")
    
    args = parser.parse_args()
    
    # Create worker
    worker = DecentralizedWorker(
        endpoint_id=args.endpoint,
        model_name=args.model,
        runtime_type=args.runtime,
        endpoint_url=args.url,
        wallet_address=args.wallet,
        heartbeat_interval=args.heartbeat
    )
    
    # Run worker
    asyncio.run(worker.run())


if __name__ == "__main__":
    main()
