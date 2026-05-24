"""
Comprehensive tests for liquid staked endpoints
"""
import pytest
import asyncio
from datetime import datetime, timezone
from pathlib import Path
import os

from liquid_endpoint_store import (
    LiquidEndpoint,
    EndpointStakePosition,
    InferenceReceipt,
    EndpointHeartbeat,
    LiquidEndpointStore
)
from inference_adapters import get_adapter, MockAdapter
from receipt_signer import ReceiptSigner, ReceiptFactory


class TestLiquidEndpointStore:
    """Test SQLite store operations."""
    
    @pytest.fixture
    def store(self, tmp_path):
        """Create a temporary store for testing."""
        db_path = tmp_path / "test.db"
        return LiquidEndpointStore(db_path)
    
    def test_create_endpoint(self, store):
        """Test endpoint creation."""
        endpoint = LiquidEndpoint(
            endpoint_id="test_end_001",
            owner_wallet="wallet1",
            endpoint_url="http://localhost:11434",
            model_name="llama2",
            runtime_type="ollama",
            price_per_request=1.0,
            price_per_1k_tokens=0.1,
            revenue_share_bps=7000,
            total_staked=0.0,
            liquid_supply=0.0,
            exchange_rate=1.0,
            status="active",
            created_at=datetime.now(timezone.utc).isoformat()
        )
        
        result = store.create_endpoint(endpoint)
        assert result.endpoint_id == "test_end_001"
        
        retrieved = store.get_endpoint("test_end_001")
        assert retrieved is not None
        assert retrieved.owner_wallet == "wallet1"
    
    def test_get_nonexistent_endpoint(self, store):
        """Test getting non-existent endpoint."""
        result = store.get_endpoint("nonexistent")
        assert result is None
    
    def test_list_endpoints(self, store):
        """Test listing endpoints."""
        # Create multiple endpoints
        for i in range(3):
            endpoint = LiquidEndpoint(
                endpoint_id=f"test_end_{i:03d}",
                owner_wallet=f"wallet{i}",
                endpoint_url="http://localhost:11434",
                model_name="llama2",
                runtime_type="ollama",
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
        
        endpoints = store.list_endpoints()
        assert len(endpoints) == 3
    
    def test_update_endpoint(self, store):
        """Test endpoint update."""
        endpoint = LiquidEndpoint(
            endpoint_id="test_end_001",
            owner_wallet="wallet1",
            endpoint_url="http://localhost:11434",
            model_name="llama2",
            runtime_type="ollama",
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
        
        store.update_endpoint("test_end_001", {"status": "paused"})
        
        updated = store.get_endpoint("test_end_001")
        assert updated.status == "paused"
    
    def test_create_stake_position(self, store):
        """Test stake position creation."""
        # First create an endpoint
        endpoint = LiquidEndpoint(
            endpoint_id="test_end_001",
            owner_wallet="wallet1",
            endpoint_url="http://localhost:11434",
            model_name="llama2",
            runtime_type="ollama",
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
        
        position = EndpointStakePosition(
            position_id="stake_001",
            endpoint_id="test_end_001",
            staker_wallet="wallet2",
            staked_amount=100.0,
            liquid_tokens_minted=100.0,
            entry_exchange_rate=1.0,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat()
        )
        
        result = store.create_stake_position(position)
        assert result.position_id == "stake_001"
    
    def test_get_stake_positions(self, store):
        """Test getting stake positions for an endpoint."""
        endpoint = LiquidEndpoint(
            endpoint_id="test_end_001",
            owner_wallet="wallet1",
            endpoint_url="http://localhost:11434",
            model_name="llama2",
            runtime_type="ollama",
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
        
        position = EndpointStakePosition(
            position_id="stake_001",
            endpoint_id="test_end_001",
            staker_wallet="wallet2",
            staked_amount=100.0,
            liquid_tokens_minted=100.0,
            entry_exchange_rate=1.0,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat()
        )
        store.create_stake_position(position)
        
        positions = store.get_stake_positions("test_end_001")
        assert len(positions) == 1
        assert positions[0].staker_wallet == "wallet2"
    
    def test_create_receipt(self, store):
        """Test receipt creation."""
        endpoint = LiquidEndpoint(
            endpoint_id="test_end_001",
            owner_wallet="wallet1",
            endpoint_url="http://localhost:11434",
            model_name="llama2",
            runtime_type="ollama",
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
        
        receipt = InferenceReceipt(
            receipt_id="rcpt_001",
            endpoint_id="test_end_001",
            requester_wallet="wallet3",
            prompt_hash="abc123",
            response_hash="def456",
            model_name="llama2",
            input_tokens=10,
            output_tokens=20,
            fee_paid=0.003,
            staker_revenue=0.0021,
            operator_revenue=0.0009,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
        result = store.create_receipt(receipt)
        assert result.receipt_id == "rcpt_001"
    
    def test_get_receipts(self, store):
        """Test getting receipts for an endpoint."""
        endpoint = LiquidEndpoint(
            endpoint_id="test_end_001",
            owner_wallet="wallet1",
            endpoint_url="http://localhost:11434",
            model_name="llama2",
            runtime_type="ollama",
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
        
        receipt = InferenceReceipt(
            receipt_id="rcpt_001",
            endpoint_id="test_end_001",
            requester_wallet="wallet3",
            prompt_hash="abc123",
            response_hash="def456",
            model_name="llama2",
            input_tokens=10,
            output_tokens=20,
            fee_paid=0.003,
            staker_revenue=0.0021,
            operator_revenue=0.0009,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        store.create_receipt(receipt)
        
        receipts = store.get_receipts("test_end_001")
        assert len(receipts) == 1
        assert receipts[0].requester_wallet == "wallet3"
    
    def test_record_heartbeat(self, store):
        """Test heartbeat recording."""
        endpoint = LiquidEndpoint(
            endpoint_id="test_end_001",
            owner_wallet="wallet1",
            endpoint_url="http://localhost:11434",
            model_name="llama2",
            runtime_type="ollama",
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
        
        heartbeat = EndpointHeartbeat(
            endpoint_id="test_end_001",
            timestamp=datetime.now(timezone.utc).isoformat(),
            status="healthy",
            latency_ms=50,
            model_loaded=True,
            available_memory=8192,
            queue_depth=0
        )
        
        store.record_heartbeat(heartbeat)
        
        updated = store.get_endpoint("test_end_001")
        assert updated.last_heartbeat is not None
    
    def test_wallet_balance_operations(self, store):
        """Test wallet balance operations."""
        store.set_balance("wallet1", "INF", 100.0)
        
        balance = store.get_balance("wallet1", "INF")
        assert balance == 100.0
        
        new_balance = store.adjust_balance("wallet1", "INF", 50.0)
        assert new_balance == 150.0
        
        balance = store.get_balance("wallet1", "INF")
        assert balance == 150.0
    
    def test_insufficient_balance(self, store):
        """Test insufficient balance error."""
        store.set_balance("wallet1", "INF", 10.0)
        
        with pytest.raises(ValueError, match="Insufficient balance"):
            store.adjust_balance("wallet1", "INF", -20.0)


class TestInferenceAdapters:
    """Test inference adapters."""
    
    def test_get_adapter_ollama(self):
        """Test getting Ollama adapter."""
        adapter = get_adapter("ollama", "llama2")
        assert adapter is not None
        assert adapter.model == "llama2"
    
    def test_get_adapter_llama_cpp(self):
        """Test getting llama.cpp adapter."""
        adapter = get_adapter("llama_cpp", "llama2")
        assert adapter is not None
        assert adapter.model == "llama2"
    
    def test_get_adapter_mock(self):
        """Test getting mock adapter."""
        adapter = get_adapter("mock", "llama2")
        assert adapter is not None
        assert isinstance(adapter, MockAdapter)
    
    def test_invalid_adapter_type(self):
        """Test invalid adapter type."""
        with pytest.raises(ValueError):
            get_adapter("invalid", "llama2")
    
    @pytest.mark.asyncio
    async def test_mock_adapter_generate(self):
        """Test mock adapter generation."""
        adapter = get_adapter("mock", "llama2")
        result = await adapter.generate("test prompt")
        
        assert result.success is True
        assert result.text is not None
        assert result.input_tokens > 0
        assert result.output_tokens > 0
    
    def test_hash_text(self):
        """Test text hashing."""
        adapter = get_adapter("mock", "llama2")
        hash1 = adapter.hash_text("test")
        hash2 = adapter.hash_text("test")
        hash3 = adapter.hash_text("different")
        
        assert hash1 == hash2
        assert hash1 != hash3


class TestReceiptSigner:
    """Test receipt signing and verification."""
    
    @pytest.fixture
    def signer(self):
        """Create a test signer."""
        return ReceiptSigner("test_secret_key")
    
    @pytest.fixture
    def factory(self, signer):
        """Create a test factory."""
        return ReceiptFactory(signer)
    
    def test_sign_receipt(self, signer):
        """Test receipt signing."""
        from liquid_endpoint_store import InferenceReceipt
        from datetime import datetime, timezone
        
        receipt = InferenceReceipt(
            receipt_id="rcpt_001",
            endpoint_id="test_end_001",
            requester_wallet="wallet1",
            prompt_hash="abc123",
            response_hash="def456",
            model_name="llama2",
            input_tokens=10,
            output_tokens=20,
            fee_paid=0.003,
            staker_revenue=0.0021,
            operator_revenue=0.0009,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
        signed = signer.sign_receipt(receipt)
        assert signed.signature is not None
        assert len(signed.signature) > 0
    
    def test_verify_receipt(self, signer):
        """Test receipt verification."""
        from liquid_endpoint_store import InferenceReceipt
        from datetime import datetime, timezone
        
        receipt = InferenceReceipt(
            receipt_id="rcpt_001",
            endpoint_id="test_end_001",
            requester_wallet="wallet1",
            prompt_hash="abc123",
            response_hash="def456",
            model_name="llama2",
            input_tokens=10,
            output_tokens=20,
            fee_paid=0.003,
            staker_revenue=0.0021,
            operator_revenue=0.0009,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
        signed = signer.sign_receipt(receipt)
        assert signer.verify_receipt(signed.receipt) is True
    
    def test_verify_invalid_receipt(self, signer):
        """Test verification of invalid receipt."""
        from liquid_endpoint_store import InferenceReceipt
        from datetime import datetime, timezone
        
        receipt = InferenceReceipt(
            receipt_id="rcpt_001",
            endpoint_id="test_end_001",
            requester_wallet="wallet1",
            prompt_hash="abc123",
            response_hash="def456",
            model_name="llama2",
            input_tokens=10,
            output_tokens=20,
            fee_paid=0.003,
            staker_revenue=0.0021,
            operator_revenue=0.0009,
            timestamp=datetime.now(timezone.utc).isoformat(),
            signature="invalid_signature"
        )
        
        assert signer.verify_receipt(receipt) is False
    
    def test_factory_create_receipt(self, factory):
        """Test factory receipt creation."""
        signed = factory.create_receipt(
            endpoint_id="test_end_001",
            requester_wallet="wallet1",
            prompt="test prompt",
            response="test response",
            model_name="llama2",
            input_tokens=10,
            output_tokens=20,
            fee_paid=0.003,
            staker_revenue=0.0021,
            operator_revenue=0.0009
        )
        
        assert signed.receipt.receipt_id is not None
        assert signed.signature is not None
        assert factory.signer.verify_receipt(signed.receipt) is True


class TestExchangeRate:
    """Test exchange rate calculations."""
    
    def test_initial_exchange_rate(self):
        """Test initial exchange rate when supply is 0."""
        from liquid_endpoints import calculate_exchange_rate
        rate = calculate_exchange_rate(100.0, 0.0)
        assert rate == 1.0
    
    def test_normal_exchange_rate(self):
        """Test normal exchange rate calculation."""
        from liquid_endpoints import calculate_exchange_rate
        rate = calculate_exchange_rate(100.0, 100.0)
        assert rate == 1.0
    
    def test_high_demand_exchange_rate(self):
        """Test high demand (more staked than liquid)."""
        from liquid_endpoints import calculate_exchange_rate
        rate = calculate_exchange_rate(200.0, 100.0)
        assert rate == 2.0
    
    def test_low_demand_exchange_rate(self):
        """Test low demand (more liquid than staked)."""
        from liquid_endpoints import calculate_exchange_rate
        rate = calculate_exchange_rate(100.0, 200.0)
        assert rate == 0.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
