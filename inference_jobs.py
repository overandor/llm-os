"""
Inference job queue for decentralized workers
"""
import sqlite3
import uuid
import hashlib
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, List


@dataclass
class InferenceJob:
    """An inference job in the queue."""
    job_id: str
    requester_wallet: str
    endpoint_id: str
    node_id: Optional[str]  # None until claimed
    model_name: str
    prompt_hash: str
    encrypted_prompt: Optional[str]  # Optional encrypted prompt
    status: str  # queued | running | completed | failed | expired
    max_fee: float
    created_at: str
    claimed_at: Optional[str]
    completed_at: Optional[str]
    failed_at: Optional[str]
    error_message: Optional[str]


@dataclass
class JobResult:
    """Result of a completed inference job."""
    job_id: str
    response_hash: str
    output_tokens: int
    latency_ms: int
    fee_charged: float
    receipt_id: str
    node_signature: str
    completed_at: str


class InferenceJobQueue:
    """Queue for managing inference jobs."""
    
    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = Path.home() / "llm_inference_jobs.db"
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inference_jobs (
                job_id TEXT PRIMARY KEY,
                requester_wallet TEXT NOT NULL,
                endpoint_id TEXT NOT NULL,
                node_id TEXT,
                model_name TEXT NOT NULL,
                prompt_hash TEXT NOT NULL,
                encrypted_prompt TEXT,
                status TEXT DEFAULT 'queued',
                max_fee REAL NOT NULL,
                created_at TEXT NOT NULL,
                claimed_at TEXT,
                completed_at TEXT,
                failed_at TEXT,
                error_message TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS job_results (
                job_id TEXT PRIMARY KEY,
                response_hash TEXT NOT NULL,
                output_tokens INTEGER NOT NULL,
                latency_ms INTEGER NOT NULL,
                fee_charged REAL NOT NULL,
                receipt_id TEXT NOT NULL,
                node_signature TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                FOREIGN KEY (job_id) REFERENCES inference_jobs(job_id)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def submit_job(
        self,
        requester_wallet: str,
        endpoint_id: str,
        model_name: str,
        prompt: str,
        max_fee: float,
        encrypted_prompt: Optional[str] = None
    ) -> InferenceJob:
        """Submit a new inference job."""
        job_id = f"job_{uuid.uuid4().hex[:16]}"
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
        now = datetime.now(timezone.utc).isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO inference_jobs VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, (
            job_id,
            requester_wallet,
            endpoint_id,
            None,  # node_id
            model_name,
            prompt_hash,
            encrypted_prompt,
            "queued",
            max_fee,
            now,  # created_at
            None,  # claimed_at
            None,  # completed_at
            None,  # failed_at
            None   # error_message
        ))
        
        conn.commit()
        conn.close()
        
        return self.get_job(job_id)
    
    def claim_next_job(self, node_id: str, model_name: str) -> Optional[InferenceJob]:
        """Claim the next queued job for a specific model."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Find next queued job for this model
        cursor.execute("""
            SELECT job_id FROM inference_jobs
            WHERE status = 'queued' AND model_name = ?
            ORDER BY created_at ASC
            LIMIT 1
        """, (model_name,))
        
        row = cursor.fetchone()
        if not row:
            conn.close()
            return None
        
        job_id = row[0]
        now = datetime.now(timezone.utc).isoformat()
        
        # Claim the job
        cursor.execute("""
            UPDATE inference_jobs
            SET node_id = ?, status = 'running', claimed_at = ?
            WHERE job_id = ?
        """, (node_id, now, job_id))
        
        conn.commit()
        conn.close()
        
        return self.get_job(job_id)
    
    def complete_job(
        self,
        job_id: str,
        response: str,
        output_tokens: int,
        latency_ms: int,
        fee_charged: float,
        receipt_id: str,
        node_signature: str
    ) -> JobResult:
        """Complete a job and store the result."""
        response_hash = hashlib.sha256(response.encode()).hexdigest()
        now = datetime.now(timezone.utc).isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Update job status
        cursor.execute("""
            UPDATE inference_jobs
            SET status = 'completed', completed_at = ?
            WHERE job_id = ?
        """, (now, job_id))
        
        # Store result
        cursor.execute("""
            INSERT INTO job_results VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            job_id,
            response_hash,
            output_tokens,
            latency_ms,
            fee_charged,
            receipt_id,
            node_signature,
            now
        ))
        
        conn.commit()
        conn.close()
        
        return self.get_job_result(job_id)
    
    def fail_job(self, job_id: str, error_message: str) -> InferenceJob:
        """Mark a job as failed."""
        now = datetime.now(timezone.utc).isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE inference_jobs
            SET status = 'failed', failed_at = ?, error_message = ?
            WHERE job_id = ?
        """, (now, error_message, job_id))
        
        conn.commit()
        conn.close()
        
        return self.get_job(job_id)
    
    def expire_old_jobs(self, max_age_seconds: int = 3600) -> int:
        """Expire jobs older than max_age_seconds."""
        cutoff = datetime.now(timezone.utc).timestamp() - max_age_seconds
        cutoff_iso = datetime.fromtimestamp(cutoff, timezone.utc).isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE inference_jobs
            SET status = 'expired', failed_at = ?
            WHERE status = 'queued' AND created_at < ?
        """, (cutoff_iso, cutoff_iso))
        
        expired_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        return expired_count
    
    def get_job(self, job_id: str) -> Optional[InferenceJob]:
        """Get a job by ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM inference_jobs WHERE job_id = ?", (job_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return InferenceJob(
            job_id=row[0],
            requester_wallet=row[1],
            endpoint_id=row[2],
            node_id=row[3],
            model_name=row[4],
            prompt_hash=row[5],
            encrypted_prompt=row[6],
            status=row[7],
            max_fee=row[8],
            created_at=row[9],
            claimed_at=row[10],
            completed_at=row[11],
            failed_at=row[12],
            error_message=row[13]
        )
    
    def get_job_result(self, job_id: str) -> Optional[JobResult]:
        """Get the result of a completed job."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM job_results WHERE job_id = ?", (job_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return JobResult(
            job_id=row[0],
            response_hash=row[1],
            output_tokens=row[2],
            latency_ms=row[3],
            fee_charged=row[4],
            receipt_id=row[5],
            node_signature=row[6],
            completed_at=row[7]
        )
    
    def list_jobs(
        self,
        status: Optional[str] = None,
        requester_wallet: Optional[str] = None,
        node_id: Optional[str] = None,
        limit: int = 100
    ) -> List[InferenceJob]:
        """List jobs with optional filters."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = "SELECT * FROM inference_jobs WHERE 1=1"
        params = []
        
        if status:
            query += " AND status = ?"
            params.append(status)
        
        if requester_wallet:
            query += " AND requester_wallet = ?"
            params.append(requester_wallet)
        
        if node_id:
            query += " AND node_id = ?"
            params.append(node_id)
        
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [
            InferenceJob(
                job_id=row[0],
                requester_wallet=row[1],
                endpoint_id=row[2],
                node_id=row[3],
                model_name=row[4],
                prompt_hash=row[5],
                encrypted_prompt=row[6],
                status=row[7],
                max_fee=row[8],
                created_at=row[9],
                claimed_at=row[10],
                completed_at=row[11],
                failed_at=row[12],
                error_message=row[13]
            )
            for row in rows
        ]
    
    def get_queued_count(self, model_name: Optional[str] = None) -> int:
        """Get count of queued jobs."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if model_name:
            cursor.execute(
                "SELECT COUNT(*) FROM inference_jobs WHERE status = 'queued' AND model_name = ?",
                (model_name,)
            )
        else:
            cursor.execute("SELECT COUNT(*) FROM inference_jobs WHERE status = 'queued'")
        
        count = cursor.fetchone()[0]
        conn.close()
        
        return count


if __name__ == "__main__":
    # Test job queue
    print("Testing inference job queue...")
    
    queue = InferenceJobQueue()
    
    # Submit jobs
    job1 = queue.submit_job(
        requester_wallet="wallet1",
        endpoint_id="end_001",
        model_name="llama2",
        prompt="Explain quantum computing",
        max_fee=0.01
    )
    print(f"Submitted job: {job1.job_id}")
    
    job2 = queue.submit_job(
        requester_wallet="wallet2",
        endpoint_id="end_001",
        model_name="llama2",
        prompt="What is machine learning?",
        max_fee=0.01
    )
    print(f"Submitted job: {job2.job_id}")
    
    # Check queue
    queued = queue.list_jobs(status="queued")
    print(f"Queued jobs: {len(queued)}")
    
    # Claim a job
    claimed = queue.claim_next_job(node_id="node_001", model_name="llama2")
    if claimed:
        print(f"Claimed job: {claimed.job_id}")
        print(f"Status: {claimed.status}")
        print(f"Node: {claimed.node_id}")
    
    # Complete the job
    result = queue.complete_job(
        job_id=claimed.job_id,
        response="Quantum computing uses quantum bits...",
        output_tokens=50,
        latency_ms=100,
        fee_charged=0.005,
        receipt_id="rcpt_001",
        node_signature="sig_001"
    )
    print(f"Completed job: {result.job_id}")
    print(f"Fee charged: {result.fee_charged}")
    
    # Get result
    retrieved_result = queue.get_job_result(claimed.job_id)
    print(f"Retrieved result: {retrieved_result.response_hash}")
    
    # List completed jobs
    completed = queue.list_jobs(status="completed")
    print(f"Completed jobs: {len(completed)}")
    
    print("Job queue test passed!")
