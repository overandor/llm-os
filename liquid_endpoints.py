from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Literal
from datetime import datetime, timezone
from uuid import uuid4
import hashlib
import os

from liquid_endpoint_store import (
    LiquidEndpoint,
    EndpointStakePosition,
    InferenceReceipt,
    EndpointHeartbeat,
    LiquidEndpointStore
)
from inference_adapters import get_adapter, InferenceResult
from receipt_signer import get_signer, ReceiptFactory

router = APIRouter(prefix="/api/liquid-endpoints", tags=["Liquid Staked Endpoints"])

# Initialize store
store = LiquidEndpointStore()

# Initialize receipt signer
signer = get_signer()
receipt_factory = ReceiptFactory(signer)

# Ledger mode: local | solana_devnet
LEDGER_MODE = os.getenv("LEDGER_MODE", "local")

EndpointStatus = Literal["active", "paused", "slashed", "retired"]
StakeStatus = Literal["active", "unstaking", "withdrawn"]
UsageTier = Literal["free", "staker", "premium", "validator"]
RuntimeType = Literal["ollama", "llama_cpp", "openai_proxy", "custom"]


class EndpointCreateRequest(BaseModel):
    owner_wallet: str
    name: str
    model_name: str = "llama2"
    runtime_type: RuntimeType = "ollama"
    endpoint_url: str = "http://localhost:11434"
    description: Optional[str] = None
    price_per_request: float = Field(default=1.0, ge=0.0)
    price_per_1k_tokens: float = Field(default=0.1, ge=0.0)
    revenue_share_bps: int = Field(default=7000, ge=0, le=10000)


class EndpointResponse(BaseModel):
    endpoint_id: str
    owner_wallet: str
    endpoint_url: str
    model_name: str
    runtime_type: str
    price_per_request: float
    price_per_1k_tokens: float
    revenue_share_bps: int
    total_staked: float
    liquid_supply: float
    exchange_rate: float
    status: EndpointStatus
    created_at: str
    last_heartbeat: Optional[str]
    uptime_score: float
    total_requests: int
    total_tokens: int
    total_revenue: float
    pending_rewards: float


class StakeRequest(BaseModel):
    wallet: str
    amount: float = Field(gt=0)
    lock_days: int = Field(default=0, ge=0)


class StakeResponse(BaseModel):
    stake_id: str
    endpoint_id: str
    wallet: str
    amount_staked: float
    liquid_tokens_minted: float
    exchange_rate: float
    status: StakeStatus
    created_at: str


class UnstakeRequest(BaseModel):
    wallet: str
    liquid_tokens: float = Field(gt=0)


class ClaimRequest(BaseModel):
    wallet: str


class InferenceRequest(BaseModel):
    wallet: str
    prompt: str
    tier: UsageTier = "free"
    max_tokens: int = Field(default=512, ge=1, le=8192)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)


class InferenceResponse(BaseModel):
    receipt_id: str
    endpoint_id: str
    wallet: str
    charged_tokens: float
    reward_routed_to_stakers: float
    result: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    signature: str
    created_at: str


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def hash_tx(*parts: str) -> str:
    raw = "|".join(parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def liquid_symbol(endpoint_id: str) -> str:
    return f"lsEND-{endpoint_id[:8]}"


def calculate_exchange_rate(total_staked: float, liquid_supply: float) -> float:
    total_staked = max(total_staked, 1.0)
    liquid_supply = max(liquid_supply, 1.0)
    return total_staked / liquid_supply


@router.post("/create", response_model=EndpointResponse)
async def create_liquid_staked_endpoint(req: EndpointCreateRequest):
    endpoint_id = f"end_{uuid4().hex[:16]}"

    endpoint = LiquidEndpoint(
        endpoint_id=endpoint_id,
        owner_wallet=req.owner_wallet,
        endpoint_url=req.endpoint_url,
        model_name=req.model_name,
        runtime_type=req.runtime_type,
        price_per_request=req.price_per_request,
        price_per_1k_tokens=req.price_per_1k_tokens,
        revenue_share_bps=req.revenue_share_bps,
        total_staked=0.0,
        liquid_supply=0.0,
        exchange_rate=1.0,
        status="active",
        created_at=now(),
    )

    store.create_endpoint(endpoint)

    return EndpointResponse(
        endpoint_id=endpoint.endpoint_id,
        owner_wallet=endpoint.owner_wallet,
        endpoint_url=endpoint.endpoint_url,
        model_name=endpoint.model_name,
        runtime_type=endpoint.runtime_type,
        price_per_request=endpoint.price_per_request,
        price_per_1k_tokens=endpoint.price_per_1k_tokens,
        revenue_share_bps=endpoint.revenue_share_bps,
        total_staked=endpoint.total_staked,
        liquid_supply=endpoint.liquid_supply,
        exchange_rate=endpoint.exchange_rate,
        status=endpoint.status,
        created_at=endpoint.created_at,
        last_heartbeat=endpoint.last_heartbeat,
        uptime_score=endpoint.uptime_score,
        total_requests=endpoint.total_requests,
        total_tokens=endpoint.total_tokens,
        total_revenue=endpoint.total_revenue,
        pending_rewards=endpoint.pending_rewards,
    )


@router.get("", response_model=List[EndpointResponse])
async def list_liquid_staked_endpoints(status: Optional[EndpointStatus] = None):
    endpoints = store.list_endpoints(status=status.value if status else None)
    return [
        EndpointResponse(
            endpoint_id=ep.endpoint_id,
            owner_wallet=ep.owner_wallet,
            endpoint_url=ep.endpoint_url,
            model_name=ep.model_name,
            runtime_type=ep.runtime_type,
            price_per_request=ep.price_per_request,
            price_per_1k_tokens=ep.price_per_1k_tokens,
            revenue_share_bps=ep.revenue_share_bps,
            total_staked=ep.total_staked,
            liquid_supply=ep.liquid_supply,
            exchange_rate=ep.exchange_rate,
            status=ep.status,
            created_at=ep.created_at,
            last_heartbeat=ep.last_heartbeat,
            uptime_score=ep.uptime_score,
            total_requests=ep.total_requests,
            total_tokens=ep.total_tokens,
            total_revenue=ep.total_revenue,
            pending_rewards=ep.pending_rewards,
        )
        for ep in endpoints
    ]


@router.get("/{endpoint_id}", response_model=EndpointResponse)
async def get_liquid_staked_endpoint(endpoint_id: str):
    endpoint = store.get_endpoint(endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    
    return EndpointResponse(
        endpoint_id=endpoint.endpoint_id,
        owner_wallet=endpoint.owner_wallet,
        endpoint_url=endpoint.endpoint_url,
        model_name=endpoint.model_name,
        runtime_type=endpoint.runtime_type,
        price_per_request=endpoint.price_per_request,
        price_per_1k_tokens=endpoint.price_per_1k_tokens,
        revenue_share_bps=endpoint.revenue_share_bps,
        total_staked=endpoint.total_staked,
        liquid_supply=endpoint.liquid_supply,
        exchange_rate=endpoint.exchange_rate,
        status=endpoint.status,
        created_at=endpoint.created_at,
        last_heartbeat=endpoint.last_heartbeat,
        uptime_score=endpoint.uptime_score,
        total_requests=endpoint.total_requests,
        total_tokens=endpoint.total_tokens,
        total_revenue=endpoint.total_revenue,
        pending_rewards=endpoint.pending_rewards,
    )


@router.post("/{endpoint_id}/stake", response_model=StakeResponse)
async def stake_endpoint(endpoint_id: str, req: StakeRequest):
    endpoint = store.get_endpoint(endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")

    if endpoint.status != "active":
        raise HTTPException(status_code=400, detail="Endpoint is not active")

    stake_id = f"stake_{uuid4().hex[:16]}"

    if endpoint.liquid_supply == 0:
        exchange_rate = 1.0
        liquid_tokens = req.amount
    else:
        exchange_rate = calculate_exchange_rate(endpoint.total_staked, endpoint.liquid_supply)
        liquid_tokens = req.amount / exchange_rate

    # Update endpoint
    store.update_endpoint(endpoint_id, {
        "total_staked": endpoint.total_staked + req.amount,
        "liquid_supply": endpoint.liquid_supply + liquid_tokens,
        "exchange_rate": calculate_exchange_rate(
            endpoint.total_staked + req.amount,
            endpoint.liquid_supply + liquid_tokens
        )
    })

    # Create stake position
    position = EndpointStakePosition(
        position_id=stake_id,
        endpoint_id=endpoint_id,
        staker_wallet=req.wallet,
        staked_amount=req.amount,
        liquid_tokens_minted=liquid_tokens,
        entry_exchange_rate=exchange_rate,
        created_at=now(),
        updated_at=now()
    )
    
    store.create_stake_position(position)

    # Update wallet balance in local ledger mode
    if LEDGER_MODE == "local":
        symbol = liquid_symbol(endpoint_id)
        store.set_balance(req.wallet, symbol, liquid_tokens)

    return StakeResponse(
        stake_id=position.position_id,
        endpoint_id=position.endpoint_id,
        wallet=position.staker_wallet,
        amount_staked=position.staked_amount,
        liquid_tokens_minted=position.liquid_tokens_minted,
        exchange_rate=position.entry_exchange_rate,
        status="active",
        created_at=position.created_at
    )


@router.post("/{endpoint_id}/unstake")
async def unstake_endpoint(endpoint_id: str, req: UnstakeRequest):
    endpoint = store.get_endpoint(endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")

    position = store.get_wallet_position(endpoint_id, req.wallet)
    if not position:
        raise HTTPException(status_code=400, detail="No stake position found")

    if position.liquid_tokens_minted < req.liquid_tokens:
        raise HTTPException(status_code=400, detail="Insufficient liquid endpoint tokens")

    exchange_rate = calculate_exchange_rate(endpoint.total_staked, endpoint.liquid_supply)
    underlying_amount = req.liquid_tokens * exchange_rate

    if endpoint.total_staked < underlying_amount:
        raise HTTPException(status_code=400, detail="Endpoint stake pool undercollateralized")

    # Update endpoint
    store.update_endpoint(endpoint_id, {
        "total_staked": endpoint.total_staked - underlying_amount,
        "liquid_supply": endpoint.liquid_supply - req.liquid_tokens,
        "exchange_rate": calculate_exchange_rate(
            endpoint.total_staked - underlying_amount,
            endpoint.liquid_supply - req.liquid_tokens
        )
    })

    # Update wallet balance in local ledger mode
    if LEDGER_MODE == "local":
        symbol = liquid_symbol(endpoint_id)
        store.adjust_balance(req.wallet, symbol, -req.liquid_tokens)

    tx_hash = hash_tx("unstake", endpoint_id, req.wallet, str(req.liquid_tokens), now())

    return {
        "success": True,
        "endpoint_id": endpoint_id,
        "wallet": req.wallet,
        "liquid_tokens_burned": req.liquid_tokens,
        "underlying_returned": underlying_amount,
        "exchange_rate": exchange_rate,
        "tx_hash": tx_hash,
        "created_at": now(),
    }


@router.post("/{endpoint_id}/infer", response_model=InferenceResponse)
async def liquid_endpoint_infer(endpoint_id: str, req: InferenceRequest):
    endpoint = store.get_endpoint(endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")

    if endpoint.status != "active":
        raise HTTPException(status_code=400, detail="Endpoint is not active")

    # Check wallet balance or access
    if LEDGER_MODE == "local":
        balance = store.get_balance(req.wallet, "INF")
        if balance < endpoint.price_per_request:
            raise HTTPException(status_code=402, detail="Insufficient token balance")
    
    # Get inference adapter
    try:
        adapter = get_adapter(endpoint.runtime_type, endpoint.model_name, endpoint.endpoint_url)
        if not adapter.is_available():
            raise HTTPException(status_code=503, detail="Inference backend not available")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Run inference
    result: InferenceResult = await adapter.generate(
        prompt=req.prompt,
        max_tokens=req.max_tokens,
        temperature=req.temperature
    )

    if not result.success:
        raise HTTPException(status_code=500, detail=f"Inference failed: {result.error}")

    # Calculate fee
    symbol = liquid_symbol(endpoint_id)
    wallet_liquid = store.get_balance(req.wallet, symbol) if LEDGER_MODE == "local" else 0
    
    discount = 0.0
    if wallet_liquid > 0:
        discount = 0.50
    if req.tier == "validator":
        discount = 0.75
    elif req.tier == "premium":
        discount = 0.25

    # Calculate fee based on token usage
    total_tokens = result.input_tokens + result.output_tokens
    fee = (total_tokens / 1000) * endpoint.price_per_1k_tokens * (1.0 - discount)
    staker_revenue = fee * (endpoint.revenue_share_bps / 10000.0)
    operator_revenue = fee - staker_revenue

    # Create and sign receipt
    signed_receipt = receipt_factory.create_receipt(
        endpoint_id=endpoint_id,
        requester_wallet=req.wallet,
        prompt=req.prompt,
        response=result.text,
        model_name=endpoint.model_name,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        fee_paid=fee,
        staker_revenue=staker_revenue,
        operator_revenue=operator_revenue
    )

    # Store receipt
    store.create_receipt(signed_receipt.receipt)

    # Update endpoint stats
    store.update_endpoint(endpoint_id, {
        "total_requests": endpoint.total_requests + 1,
        "total_tokens": endpoint.total_tokens + total_tokens,
        "total_revenue": endpoint.total_revenue + fee,
        "pending_rewards": endpoint.pending_rewards + staker_revenue
    })

    # Deduct fee in local ledger mode
    if LEDGER_MODE == "local":
        store.adjust_balance(req.wallet, "INF", -fee)

    return InferenceResponse(
        receipt_id=signed_receipt.receipt.receipt_id,
        endpoint_id=endpoint_id,
        wallet=req.wallet,
        charged_tokens=fee,
        reward_routed_to_stakers=staker_revenue,
        result=result.text,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        latency_ms=result.latency_ms,
        signature=signed_receipt.signature,
        created_at=now()
    )


@router.post("/{endpoint_id}/claim")
async def claim_endpoint_rewards(endpoint_id: str, req: ClaimRequest):
    endpoint = store.get_endpoint(endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")

    position = store.get_wallet_position(endpoint_id, req.wallet)
    if not position:
        raise HTTPException(status_code=400, detail="No stake position found")

    if position.liquid_tokens_minted <= 0:
        raise HTTPException(status_code=400, detail="No liquid tokens to claim rewards")

    if endpoint.liquid_supply <= 0:
        raise HTTPException(status_code=400, detail="No liquid supply exists")

    # Calculate claimable rewards based on ownership
    ownership = position.liquid_tokens_minted / endpoint.liquid_supply
    claimable = endpoint.pending_rewards * ownership

    if claimable <= 0:
        raise HTTPException(status_code=400, detail="No rewards to claim")

    # Update endpoint
    store.update_endpoint(endpoint_id, {
        "pending_rewards": endpoint.pending_rewards - claimable
    })

    # Add to wallet balance in local ledger mode
    if LEDGER_MODE == "local":
        store.adjust_balance(req.wallet, "INF", claimable)

    tx_hash = hash_tx("claim", endpoint_id, req.wallet, str(claimable), now())

    return {
        "success": True,
        "endpoint_id": endpoint_id,
        "wallet": req.wallet,
        "liquid_symbol": liquid_symbol(endpoint_id),
        "wallet_liquid_balance": position.liquid_tokens_minted,
        "ownership_percent": ownership * 100,
        "claimed_rewards": claimable,
        "remaining_rewards_pool": endpoint.pending_rewards,
        "tx_hash": tx_hash,
        "created_at": now(),
    }


@router.get("/{endpoint_id}/heartbeat")
async def record_heartbeat(endpoint_id: str, status: str, latency_ms: int, model_loaded: bool, available_memory: int, queue_depth: int):
    endpoint = store.get_endpoint(endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")

    heartbeat = EndpointHeartbeat(
        endpoint_id=endpoint_id,
        timestamp=now(),
        status=status,
        latency_ms=latency_ms,
        model_loaded=model_loaded,
        available_memory=available_memory,
        queue_depth=queue_depth
    )

    store.record_heartbeat(heartbeat)

    return {
        "success": True,
        "endpoint_id": endpoint_id,
        "timestamp": heartbeat.timestamp,
        "status": status
    }


@router.get("/{endpoint_id}/receipts")
async def get_endpoint_receipts(endpoint_id: str, limit: int = 100):
    endpoint = store.get_endpoint(endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")

    receipts = store.get_receipts(endpoint_id, limit)

    return {
        "endpoint_id": endpoint_id,
        "receipts": [
            {
                "receipt_id": r.receipt_id,
                "requester_wallet": r.requester_wallet,
                "model_name": r.model_name,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "fee_paid": r.fee_paid,
                "staker_revenue": r.staker_revenue,
                "timestamp": r.timestamp,
                "signature": r.signature
            }
            for r in receipts
        ],
        "count": len(receipts)
    }


@router.get("/{endpoint_id}/positions/{wallet}")
async def get_wallet_position(endpoint_id: str, wallet: str):
    endpoint = store.get_endpoint(endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")

    position = store.get_wallet_position(endpoint_id, wallet)
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")

    return {
        "position_id": position.position_id,
        "endpoint_id": position.endpoint_id,
        "staker_wallet": position.staker_wallet,
        "staked_amount": position.staked_amount,
        "liquid_tokens_minted": position.liquid_tokens_minted,
        "entry_exchange_rate": position.entry_exchange_rate,
        "rewards_claimed": position.rewards_claimed,
        "created_at": position.created_at,
        "updated_at": position.updated_at
    }


@router.get("/{endpoint_id}/stats")
async def get_endpoint_stats(endpoint_id: str):
    endpoint = store.get_endpoint(endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")

    positions = store.get_stake_positions(endpoint_id)
    
    # Calculate APR estimate
    apr_estimate = 0.0
    if endpoint.total_staked > 0 and endpoint.total_revenue > 0:
        # Simple APR: (revenue / staked) * 365 * 100 (assuming daily revenue)
        apr_estimate = (endpoint.total_revenue / endpoint.total_staked) * 365 * 100

    return {
        "endpoint_id": endpoint_id,
        "status": endpoint.status,
        "total_staked": endpoint.total_staked,
        "liquid_supply": endpoint.liquid_supply,
        "exchange_rate": endpoint.exchange_rate,
        "total_requests": endpoint.total_requests,
        "total_tokens": endpoint.total_tokens,
        "total_revenue": endpoint.total_revenue,
        "pending_rewards": endpoint.pending_rewards,
        "uptime_score": endpoint.uptime_score,
        "last_heartbeat": endpoint.last_heartbeat,
        "staker_count": len(positions),
        "apr_estimate": round(apr_estimate, 2)
    }


@router.post("/{endpoint_id}/pause")
async def pause_endpoint(endpoint_id: str):
    endpoint = store.get_endpoint(endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")

    store.update_endpoint(endpoint_id, {"status": "paused"})

    return {
        "success": True,
        "endpoint_id": endpoint_id,
        "status": "paused",
        "updated_at": now()
    }


@router.post("/{endpoint_id}/resume")
async def resume_endpoint(endpoint_id: str):
    endpoint = store.get_endpoint(endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")

    store.update_endpoint(endpoint_id, {"status": "active"})

    return {
        "success": True,
        "endpoint_id": endpoint_id,
        "status": "active",
        "updated_at": now()
    }


@router.post("/{endpoint_id}/slash")
async def slash_endpoint(endpoint_id: str, reason: str, amount_slashed: float):
    endpoint = store.get_endpoint(endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found")

    # Record slash event
    # In production, this would also update stake positions
    store.update_endpoint(endpoint_id, {
        "status": "slashed",
        "total_staked": max(0, endpoint.total_staked - amount_slashed)
    })

    return {
        "success": True,
        "endpoint_id": endpoint_id,
        "reason": reason,
        "amount_slashed": amount_slashed,
        "status": "slashed",
        "updated_at": now()
    }


