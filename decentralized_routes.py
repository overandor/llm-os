"""
API routes for decentralized inference nodes
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone

from node_identity import generate_node_identity, load_node_identity, NodeMetadata
from node_registry import NodeRegistry
from inference_jobs import InferenceJobQueue
from public_access import PublicAccessManager


# In-memory worker status (mock controller - not true background process)
_worker_status = {
    "running": False,
    "node_id": None,
    "endpoint_id": None,
    "model_name": None,
    "runtime_type": None,
    "jobs_processed": 0,
    "total_revenue": 0.0,
    "last_job_at": None,
    "last_error": None,
    "started_at": None
}


router = APIRouter(prefix="/api/decentralized", tags=["decentralized"])


# Request/Response Models
class RegisterNodeRequest(BaseModel):
    machine_name: str
    models_available: List[str]
    endpoint_url: str
    wallet_address: str


class HeartbeatRequest(BaseModel):
    latency_ms: int
    model_loaded: bool
    available_memory: int
    queue_depth: int


class SubmitJobRequest(BaseModel):
    requester_wallet: str
    endpoint_id: str
    model_name: str
    prompt: str
    max_fee: float
    encrypted_prompt: Optional[str] = None


class CompleteJobRequest(BaseModel):
    response: str
    output_tokens: int
    latency_ms: int
    fee_charged: float
    receipt_id: str
    node_signature: str


class StartPublicLinkRequest(BaseModel):
    mode: str  # local | ngrok | cloudflared | custom
    domain: Optional[str] = None


class WorkerStartRequest(BaseModel):
    endpoint_id: str
    model_name: str
    runtime_type: str
    endpoint_url: str
    wallet_address: str


# Dependencies
def get_registry():
    return NodeRegistry(registry_mode="local")


def get_job_queue():
    return InferenceJobQueue()


def get_public_manager():
    return PublicAccessManager(local_port=8000)


# Node Routes
@router.post("/node/register")
async def register_node(req: RegisterNodeRequest, registry: NodeRegistry = Depends(get_registry)):
    """Register a new node in the registry."""
    try:
        identity = generate_node_identity(
            machine_name=req.machine_name,
            models_available=req.models_available,
            endpoint_url=req.endpoint_url,
            wallet_address=req.wallet_address
        )
        
        registration = registry.register_node(identity.metadata)
        
        return {
            "success": True,
            "node_id": registration.node_id,
            "public_key": registration.public_key,
            "created_at": registration.created_at,
            "status": registration.status
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/node/me")
async def get_my_node():
    """Get this node's identity."""
    try:
        identity = load_node_identity()
        return {
            "success": True,
            "node_id": identity.metadata.node_id,
            "machine_name": identity.metadata.machine_name,
            "models_available": identity.metadata.models_available,
            "endpoint_url": identity.metadata.endpoint_url,
            "wallet_address": identity.metadata.wallet_address,
            "public_key": identity.metadata.public_key,
            "created_at": identity.metadata.created_at
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Node identity not found. Register first.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/node/heartbeat")
async def send_heartbeat(req: HeartbeatRequest, registry: NodeRegistry = Depends(get_registry)):
    """Send heartbeat for this node."""
    try:
        identity = load_node_identity()
        
        registration = registry.update_heartbeat(
            node_id=identity.metadata.node_id,
            latency_ms=req.latency_ms,
            model_loaded=req.model_loaded,
            available_memory=req.available_memory,
            queue_depth=req.queue_depth
        )
        
        return {
            "success": True,
            "node_id": registration.node_id,
            "last_heartbeat": registration.last_heartbeat,
            "uptime_score": registration.uptime_score,
            "average_latency_ms": registration.average_latency_ms
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Node identity not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/nodes")
async def list_nodes(registry: NodeRegistry = Depends(get_registry)):
    """List all active nodes."""
    try:
        nodes = registry.list_active_nodes()
        return {
            "success": True,
            "nodes": [
                {
                    "node_id": n.node_id,
                    "machine_name": n.machine_name,
                    "models_available": n.models_available,
                    "endpoint_url": n.endpoint_url,
                    "wallet_address": n.wallet_address,
                    "last_heartbeat": n.last_heartbeat,
                    "status": n.status,
                    "uptime_score": n.uptime_score,
                    "jobs_completed": n.jobs_completed,
                    "total_fees_earned": n.total_fees_earned,
                    "average_latency_ms": n.average_latency_ms
                }
                for n in nodes
            ],
            "count": len(nodes)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/nodes/model/{model_name}")
async def find_nodes_by_model(model_name: str, registry: NodeRegistry = Depends(get_registry)):
    """Find nodes that have a specific model available."""
    try:
        nodes = registry.find_nodes_by_model(model_name)
        return {
            "success": True,
            "model_name": model_name,
            "nodes": [
                {
                    "node_id": n.node_id,
                    "machine_name": n.machine_name,
                    "endpoint_url": n.endpoint_url,
                    "last_heartbeat": n.last_heartbeat,
                    "average_latency_ms": n.average_latency_ms
                }
                for n in nodes
            ],
            "count": len(nodes)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Job Routes
@router.post("/jobs")
async def submit_job(req: SubmitJobRequest, queue: InferenceJobQueue = Depends(get_job_queue)):
    """Submit a new inference job."""
    try:
        job = queue.submit_job(
            requester_wallet=req.requester_wallet,
            endpoint_id=req.endpoint_id,
            model_name=req.model_name,
            prompt=req.prompt,
            max_fee=req.max_fee,
            encrypted_prompt=req.encrypted_prompt
        )
        
        return {
            "success": True,
            "job_id": job.job_id,
            "status": job.status,
            "created_at": job.created_at,
            "prompt_hash": job.prompt_hash
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, queue: InferenceJobQueue = Depends(get_job_queue)):
    """Get job details."""
    try:
        job = queue.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return {
            "success": True,
            "job_id": job.job_id,
            "requester_wallet": job.requester_wallet,
            "endpoint_id": job.endpoint_id,
            "node_id": job.node_id,
            "model_name": job.model_name,
            "prompt_hash": job.prompt_hash,
            "status": job.status,
            "max_fee": job.max_fee,
            "created_at": job.created_at,
            "claimed_at": job.claimed_at,
            "completed_at": job.completed_at,
            "failed_at": job.failed_at,
            "error_message": job.error_message
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/jobs/{job_id}/complete")
async def complete_job(
    job_id: str,
    req: CompleteJobRequest,
    queue: InferenceJobQueue = Depends(get_job_queue)
):
    """Complete a job with result."""
    try:
        result = queue.complete_job(
            job_id=job_id,
            response=req.response,
            output_tokens=req.output_tokens,
            latency_ms=req.latency_ms,
            fee_charged=req.fee_charged,
            receipt_id=req.receipt_id,
            node_signature=req.node_signature
        )
        
        return {
            "success": True,
            "job_id": result.job_id,
            "response_hash": result.response_hash,
            "output_tokens": result.output_tokens,
            "latency_ms": result.latency_ms,
            "fee_charged": result.fee_charged,
            "receipt_id": result.receipt_id,
            "completed_at": result.completed_at
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs")
async def list_jobs(
    status: Optional[str] = None,
    requester_wallet: Optional[str] = None,
    node_id: Optional[str] = None,
    limit: int = 100,
    queue: InferenceJobQueue = Depends(get_job_queue)
):
    """List jobs with optional filters."""
    try:
        jobs = queue.list_jobs(
            status=status,
            requester_wallet=requester_wallet,
            node_id=node_id,
            limit=limit
        )
        
        return {
            "success": True,
            "jobs": [
                {
                    "job_id": j.job_id,
                    "requester_wallet": j.requester_wallet,
                    "endpoint_id": j.endpoint_id,
                    "node_id": j.node_id,
                    "model_name": j.model_name,
                    "status": j.status,
                    "max_fee": j.max_fee,
                    "created_at": j.created_at,
                    "claimed_at": j.claimed_at,
                    "completed_at": j.completed_at
                }
                for j in jobs
            ],
            "count": len(jobs)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs/{job_id}/receipt")
async def get_job_receipt(job_id: str, queue: InferenceJobQueue = Depends(get_job_queue)):
    """Get job result/receipt."""
    try:
        result = queue.get_job_result(job_id)
        if not result:
            raise HTTPException(status_code=404, detail="Job result not found")
        
        return {
            "success": True,
            "job_id": result.job_id,
            "response_hash": result.response_hash,
            "output_tokens": result.output_tokens,
            "latency_ms": result.latency_ms,
            "fee_charged": result.fee_charged,
            "receipt_id": result.receipt_id,
            "node_signature": result.node_signature,
            "completed_at": result.completed_at
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Public Link Routes
@router.post("/public-link/start")
async def start_public_link(
    req: StartPublicLinkRequest,
    manager: PublicAccessManager = Depends(get_public_manager)
):
    """Start public access tunnel."""
    try:
        if req.mode == "local":
            access = manager.start_local()
        elif req.mode == "ngrok":
            access = manager.start_ngrok()
        elif req.mode == "cloudflared":
            access = manager.start_cloudflared()
        elif req.mode == "custom":
            if not req.domain:
                raise HTTPException(status_code=400, detail="Domain required for custom mode")
            access = manager.start_custom(req.domain)
        else:
            raise HTTPException(status_code=400, detail=f"Invalid mode: {req.mode}")
        
        return {
            "success": access.status == "active",
            "public_url": access.public_url,
            "mode": access.mode,
            "started_at": access.started_at,
            "status": access.status,
            "error_message": access.error_message
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/public-link/status")
async def get_public_link_status(manager: PublicAccessManager = Depends(get_public_manager)):
    """Get current public access status."""
    try:
        access = manager.get_status()
        if not access:
            return {
                "success": True,
                "status": "none",
                "message": "No public link active"
            }
        
        return {
            "success": True,
            "public_url": access.public_url,
            "mode": access.mode,
            "started_at": access.started_at,
            "status": access.status,
            "error_message": access.error_message
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/public-link/stop")
async def stop_public_link(manager: PublicAccessManager = Depends(get_public_manager)):
    """Stop public access tunnel."""
    try:
        success = manager.stop()
        return {
            "success": success,
            "status": "stopped"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Worker Control Routes
@router.post("/worker/start")
async def start_worker(req: WorkerStartRequest):
    """Start the worker (mock controller - not true background process)."""
    global _worker_status
    
    if _worker_status["running"]:
        raise HTTPException(status_code=400, detail="Worker already running")
    
    try:
        # Load node identity
        identity = load_node_identity()
        
        _worker_status = {
            "running": True,
            "node_id": identity.metadata.node_id,
            "endpoint_id": req.endpoint_id,
            "model_name": req.model_name,
            "runtime_type": req.runtime_type,
            "jobs_processed": 0,
            "total_revenue": 0.0,
            "last_job_at": None,
            "last_error": None,
            "started_at": datetime.now(timezone.utc).isoformat()
        }
        
        return {
            "success": True,
            "message": "Worker started (mock controller)",
            "worker_status": _worker_status
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Node identity not found. Register node first.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/worker/stop")
async def stop_worker():
    """Stop the worker (mock controller)."""
    global _worker_status
    
    if not _worker_status["running"]:
        raise HTTPException(status_code=400, detail="Worker not running")
    
    _worker_status["running"] = False
    _worker_status["stopped_at"] = datetime.now(timezone.utc).isoformat()
    
    return {
        "success": True,
        "message": "Worker stopped (mock controller)",
        "worker_status": _worker_status
    }


@router.get("/worker/status")
async def get_worker_status():
    """Get worker status."""
    return {
        "success": True,
        "worker_status": _worker_status,
        "note": "This is a mock controller. For true background processing, run decentralized_worker.py directly."
    }
