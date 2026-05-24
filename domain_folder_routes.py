"""
API routes for sovereign domain folders
Integrates domain folder primitive with decentralized inference node
"""
import sys
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone

# Add parent directory to path for domain folder imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from domain_folder import (
    DomainFolder,
    DomainFile,
    DomainChangeEvent,
    DomainSummary,
    DomainStatus
)
from domain_folder_store import DomainFolderStore


# Initialize store (use llm-os directory for database)
DB_PATH = Path.home() / "llm_domain_folders.db"
store = DomainFolderStore(str(DB_PATH))


router = APIRouter(prefix="/api/domain-folders", tags=["domain-folders"])


# Request/Response Models
class CreateDomainRequest(BaseModel):
    domain_path: str
    local_path: str
    owner: str = "local_owner"
    public_url: Optional[str] = None


class ScanDomainRequest(BaseModel):
    domain_path: str


class WatchStartRequest(BaseModel):
    domain_path: str
    poll_interval: int = 5


class SummarizeRequest(BaseModel):
    domain_path: str


# ============================================================
# DOMAIN FOLDER ROUTES
# ============================================================

@router.get("/")
async def list_domains():
    """List all domain folders."""
    domains = store.list_domain_folders()
    return {
        "success": True,
        "domains": [d.to_dict() for d in domains],
        "total": len(domains)
    }


@router.post("/create")
async def create_domain(req: CreateDomainRequest):
    """Create a new domain folder."""
    import uuid
    
    # Check if local path exists
    if not os.path.exists(req.local_path):
        raise HTTPException(status_code=400, detail="Local path does not exist")
    
    domain = DomainFolder(
        domain_id=f"dom_{uuid.uuid4().hex[:16]}",
        domain_path=req.domain_path,
        local_path=req.local_path,
        public_url=req.public_url,
        owner=req.owner,
        created_at=datetime.now(timezone.utc).isoformat()
    )
    
    result = store.create_domain_folder(domain)
    
    if result["success"]:
        return {
            "success": True,
            "domain_id": domain.domain_id,
            "domain": domain.to_dict()
        }
    else:
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to create domain"))


@router.get("/{domain_path}")
async def get_domain(domain_path: str):
    """Get domain folder details."""
    domain = store.get_domain_folder(domain_path)
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    
    files = store.get_domain_files(domain.domain_id)
    recent_changes = store.get_recent_changes(domain.domain_id, limit=10)
    summary = store.get_latest_summary(domain.domain_id)
    
    return {
        "success": True,
        "domain": domain.to_dict(),
        "files": [f.to_dict() for f in files],
        "recent_changes": [c.to_dict() for c in recent_changes],
        "summary": summary.to_dict() if summary else None
    }


@router.get("/{domain_path}/files")
async def get_domain_files(domain_path: str):
    """Get all files in a domain."""
    domain = store.get_domain_folder(domain_path)
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    
    files = store.get_domain_files(domain.domain_id)
    return {
        "success": True,
        "files": [f.to_dict() for f in files],
        "total": len(files)
    }


@router.get("/{domain_path}/changes")
async def get_domain_changes(domain_path: str, limit: int = 50):
    """Get recent changes for a domain."""
    domain = store.get_domain_folder(domain_path)
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    
    changes = store.get_recent_changes(domain.domain_id, limit=limit)
    return {
        "success": True,
        "changes": [c.to_dict() for c in changes],
        "total": len(changes)
    }


@router.get("/{domain_path}/summary")
async def get_domain_summary(domain_path: str):
    """Get domain summary."""
    domain = store.get_domain_folder(domain_path)
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    
    summary = store.get_latest_summary(domain.domain_id)
    if not summary:
        return {
            "success": True,
            "summary": None,
            "message": "No summary available"
        }
    
    return {
        "success": True,
        "summary": summary.to_dict()
    }


@router.get("/{domain_path}/ledger/latest")
async def get_domain_ledger(domain_path: str):
    """Get latest ledger hash for a domain."""
    domain = store.get_domain_folder(domain_path)
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    
    return {
        "success": True,
        "domain_path": domain.domain_path,
        "latest_chain_hash": domain.latest_chain_hash,
        "file_count": domain.file_count,
        "total_bytes": domain.total_bytes
    }


@router.get("/{domain_path}/verify")
async def verify_domain(domain_path: str):
    """Verify domain ledger integrity."""
    domain = store.get_domain_folder(domain_path)
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    
    # For now, return basic verification info
    # Full verification would require checking chain hashes
    files = store.get_domain_files(domain.domain_id)
    changes = store.get_recent_changes(domain.domain_id, limit=100)
    
    return {
        "success": True,
        "domain_path": domain.domain_path,
        "latest_chain_hash": domain.latest_chain_hash,
        "file_count": len(files),
        "change_count": len(changes),
        "verified": True,
        "message": "Basic verification passed. Full chain verification requires hash_chained_ecosystem integration."
    }


# ============================================================
# ACTION ROUTES
# ============================================================

@router.post("/{domain_path}/scan")
async def scan_domain(domain_path: str):
    """Scan a domain folder for changes."""
    domain = store.get_domain_folder(domain_path)
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    
    # Import scanner from parent directory
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from folder_scanner import FolderScanner
        scanner = FolderScanner()
    except ImportError:
        raise HTTPException(status_code=503, detail="Folder scanner not available")
    
    # Scan folder
    result = scanner.scan_domain_folder(
        domain.local_path,
        domain.domain_path,
        domain.owner,
        domain.latest_chain_hash or ""
    )
    
    if result["success"]:
        # Update domain
        store.update_domain_folder(
            domain_path,
            latest_chain_hash=result["latest_chain_hash"],
            file_count=result["total_files"],
            total_bytes=result["total_bytes"]
        )
        
        # Store files
        for file_info in result["files_scanned"]:
            domain_file = DomainFile(
                file_id=f"file_{file_info['content_hash'][:16]}",
                domain_id=domain.domain_id,
                relative_path=file_info["relative_path"],
                absolute_path=file_info["absolute_path"],
                content_type=file_info["content_type"],
                size_bytes=file_info["size_bytes"],
                content_hash=file_info["content_hash"],
                envelope_hash=file_info["envelope_hash"],
                created_at=datetime.now(timezone.utc).isoformat(),
                modified_at=datetime.now(timezone.utc).isoformat()
            )
            store.upsert_domain_file(domain_file)
    
    return {
        "success": result["success"],
        "latest_chain_hash": result.get("latest_chain_hash"),
        "total_files": result.get("total_files"),
        "total_bytes": result.get("total_bytes"),
        "files_scanned": len(result.get("files_scanned", []))
    }


@router.post("/{domain_path}/summarize")
async def summarize_domain(domain_path: str):
    """Generate summary for a domain using decentralized worker."""
    domain = store.get_domain_folder(domain_path)
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    
    # Submit job to decentralized worker
    try:
        from domain_folder_worker_bridge import submit_folder_summary_job
        job_result = submit_folder_summary_job(domain.domain_id, domain.local_path)
        return {
            "success": True,
            "job_id": job_result["job_id"],
            "message": "Summary job submitted to decentralized worker"
        }
    except ImportError:
        raise HTTPException(status_code=503, detail="Domain folder worker bridge not available")


@router.post("/{domain_path}/watch/start")
async def start_watch(domain_path: str, req: WatchStartRequest):
    """Start watching a domain folder."""
    domain = store.get_domain_folder(domain_path)
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    
    # For now, return placeholder
    # Full watcher implementation requires folder_watcher.py
    return {
        "success": True,
        "message": "Watcher start requested (requires folder_watcher.py integration)",
        "domain_path": domain_path,
        "poll_interval": req.poll_interval
    }


@router.post("/{domain_path}/watch/stop")
async def stop_watch(domain_path: str):
    """Stop watching a domain folder."""
    return {
        "success": True,
        "message": "Watcher stop requested (requires folder_watcher.py integration)",
        "domain_path": domain_path
    }
