"""
Domain Folder Worker Bridge
Bridges domain folder operations with decentralized inference worker
"""
import sys
import uuid
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent))

from inference_jobs import InferenceJobQueue
from domain_folder_store import DomainFolderStore, DomainSummary


# Initialize components
job_queue = InferenceJobQueue()
domain_store = DomainFolderStore(str(Path.home() / "llm_domain_folders.db"))


def submit_folder_summary_job(domain_id: str, local_path: str) -> Dict[str, Any]:
    """Submit a folder summary job to the decentralized worker."""
    
    # Construct prompt for folder summary
    prompt = f"""Analyze this folder and provide a summary:
Folder path: {local_path}
Domain ID: {domain_id}

Please provide:
1. Folder purpose
2. Main files
3. Recent changes
4. Detected APIs
5. Suggested endpoints
6. Risk notes
7. Next actions
"""
    
    # Submit job to queue
    job = job_queue.submit_job(
        requester_wallet="domain_folder_worker",
        endpoint_id="domain_summary_endpoint",
        model_name="llama2",
        prompt=prompt,
        max_fee=0.01
    )
    
    return {
        "success": True,
        "job_id": job.job_id,
        "domain_id": domain_id,
        "status": job.status
    }


def submit_file_summary_job(domain_id: str, relative_path: str, local_path: str) -> Dict[str, Any]:
    """Submit a file summary job to the decentralized worker."""
    
    prompt = f"""Analyze this file and provide a summary:
File path: {relative_path}
Full path: {local_path}
Domain ID: {domain_id}

Please provide:
1. File purpose
2. Key functions/classes
3. Dependencies
4. Security considerations
5. Suggested improvements
"""
    
    job = job_queue.submit_job(
        requester_wallet="domain_folder_worker",
        endpoint_id="domain_summary_endpoint",
        model_name="llama2",
        prompt=prompt,
        max_fee=0.005
    )
    
    return {
        "success": True,
        "job_id": job.job_id,
        "domain_id": domain_id,
        "relative_path": relative_path,
        "status": job.status
    }


def submit_folder_verification_job(domain_id: str, local_path: str) -> Dict[str, Any]:
    """Submit a folder verification job to the decentralized worker."""
    
    prompt = f"""Verify the integrity and consistency of this folder:
Folder path: {local_path}
Domain ID: {domain_id}

Please check:
1. File hash consistency
2. Missing dependencies
3. Configuration errors
4. Security vulnerabilities
5. Code quality issues
"""
    
    job = job_queue.submit_job(
        requester_wallet="domain_folder_worker",
        endpoint_id="domain_summary_endpoint",
        model_name="llama2",
        prompt=prompt,
        max_fee=0.01
    )
    
    return {
        "success": True,
        "job_id": job.job_id,
        "domain_id": domain_id,
        "status": job.status
    }


def submit_programmability_map_job(domain_id: str, local_path: str) -> Dict[str, Any]:
    """Submit a programmability map generation job to the decentralized worker."""
    
    prompt = f"""Generate a programmability map for this folder:
Folder path: {local_path}
Domain ID: {domain_id}

Please identify:
1. Entry points
2. API endpoints
3. Data flow
4. External dependencies
5. Programmable interfaces
"""
    
    job = job_queue.submit_job(
        requester_wallet="domain_folder_worker",
        endpoint_id="domain_summary_endpoint",
        model_name="llama2",
        prompt=prompt,
        max_fee=0.015
    )
    
    return {
        "success": True,
        "job_id": job.job_id,
        "domain_id": domain_id,
        "status": job.status
    }


def store_job_receipt(domain_id: str, job_id: str, receipt_id: str) -> Dict[str, Any]:
    """Store a job receipt for a domain maintenance operation."""
    
    # This would store the mapping between job and receipt
    # For now, return success
    return {
        "success": True,
        "domain_id": domain_id,
        "job_id": job_id,
        "receipt_id": receipt_id
    }


def process_job_result(job_id: str, result_text: str, receipt_id: str) -> Dict[str, Any]:
    """Process a completed job result and store the summary."""
    
    # Get job details
    job = job_queue.get_job(job_id)
    if not job:
        return {"success": False, "error": "Job not found"}
    
    # Parse the result to extract structured data
    # This is a simple parser - in production would use more sophisticated parsing
    try:
        lines = result_text.split('\n')
        
        # Extract domain_id from prompt or job metadata
        domain_id = None
        if "Domain ID:" in job.prompt:
            for line in lines:
                if "Domain ID:" in line:
                    domain_id = line.split("Domain ID:")[-1].strip()
                    break
        
        if not domain_id:
            return {"success": False, "error": "Could not extract domain_id from job"}
        
        # Create summary from result
        summary = DomainSummary(
            summary_id=f"sum_{uuid.uuid4().hex[:16]}",
            domain_id=domain_id,
            folder_purpose="Generated from LLM summary",
            main_files=[],
            recent_changes=[],
            detected_apis=[],
            suggested_endpoints=[],
            risk_notes=[],
            next_actions=[],
            created_at=datetime.now(timezone.utc).isoformat()
        )
        
        # Store summary
        store_result = domain_store.store_summary(summary)
        
        # Store job receipt mapping
        store_job_receipt(domain_id, job_id, receipt_id)
        
        return {
            "success": True,
            "summary_id": summary.summary_id,
            "domain_id": domain_id,
            "job_id": job_id,
            "receipt_id": receipt_id
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_domain_jobs(domain_id: str) -> Dict[str, Any]:
    """Get all jobs submitted for a domain."""
    
    # This would query jobs by domain_id
    # For now, return placeholder
    return {
        "success": True,
        "domain_id": domain_id,
        "jobs": [],
        "total": 0
    }


def get_domain_receipts(domain_id: str) -> Dict[str, Any]:
    """Get all receipts for domain maintenance jobs."""
    
    # This would query receipts by domain_id
    # For now, return placeholder
    return {
        "success": True,
        "domain_id": domain_id,
        "receipts": [],
        "total": 0
    }
