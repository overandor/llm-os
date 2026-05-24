"""
Decentralized node registry for inference workers
Supports local (SQLite) and Solana devnet modes
"""
import sqlite3
import os
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, List

from node_identity import NodeMetadata


@dataclass
class NodeRegistration:
    """A registered node in the registry."""
    node_id: str
    machine_name: str
    models_available: List[str]
    endpoint_url: str
    wallet_address: str
    public_key: str
    created_at: str
    last_heartbeat: str
    status: str  # active | inactive | slashed
    uptime_score: float
    jobs_completed: int
    total_fees_earned: float
    average_latency_ms: float


class NodeRegistry:
    """Registry for decentralized inference nodes."""
    
    def __init__(self, registry_mode: Optional[str] = None, db_path: Optional[Path] = None):
        self.registry_mode = registry_mode or os.getenv("REGISTRY_MODE", "local")
        
        if self.registry_mode == "local":
            if db_path is None:
                db_path = Path.home() / "llm_decentralized_nodes.db"
            self.db_path = db_path
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._init_db()
        elif self.registry_mode == "solana_devnet":
            # Placeholder for Solana integration
            self.solana_available = False
            try:
                from solana.rpc.api import Client
                from solana.publickey import PublicKey
                self.solana_available = True
            except ImportError:
                pass
        else:
            raise ValueError(f"Invalid registry mode: {self.registry_mode}")
    
    def _init_db(self):
        """Initialize SQLite database for local mode."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS decentralized_nodes (
                node_id TEXT PRIMARY KEY,
                machine_name TEXT NOT NULL,
                models_available TEXT NOT NULL,
                endpoint_url TEXT NOT NULL,
                wallet_address TEXT NOT NULL,
                public_key TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_heartbeat TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                uptime_score REAL DEFAULT 100.0,
                jobs_completed INTEGER DEFAULT 0,
                total_fees_earned REAL DEFAULT 0.0,
                average_latency_ms REAL DEFAULT 0.0
            )
        """)
        
        conn.commit()
        conn.close()
    
    def register_node(self, metadata: NodeMetadata) -> NodeRegistration:
        """Register a new node."""
        if self.registry_mode == "solana_devnet":
            if not self.solana_available:
                raise RuntimeError("Solana programs not deployed. Solana dependencies required.")
            # Placeholder for Solana registration
            raise NotImplementedError("Solana devnet registration not yet implemented")
        
        # Local mode
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now(timezone.utc).isoformat()
        
        cursor.execute("""
            INSERT OR REPLACE INTO decentralized_nodes VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, (
            metadata.node_id,
            metadata.machine_name,
            json.dumps(metadata.models_available),
            metadata.endpoint_url,
            metadata.wallet_address,
            metadata.public_key,
            metadata.created_at,
            now,  # last_heartbeat
            "active",
            100.0,  # uptime_score
            0,  # jobs_completed
            0.0,  # total_fees_earned
            0.0  # average_latency_ms
        ))
        
        conn.commit()
        conn.close()
        
        return self.get_node(metadata.node_id)
    
    def update_heartbeat(
        self,
        node_id: str,
        latency_ms: int,
        model_loaded: bool,
        available_memory: int,
        queue_depth: int
    ) -> NodeRegistration:
        """Update node heartbeat and status."""
        if self.registry_mode == "solana_devnet":
            raise NotImplementedError("Solana devnet heartbeat not yet implemented")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now(timezone.utc).isoformat()
        
        # Get current stats
        cursor.execute("SELECT jobs_completed, total_fees_earned, average_latency_ms FROM decentralized_nodes WHERE node_id = ?", (node_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Node {node_id} not found")
        
        jobs_completed, total_fees, avg_latency = row
        
        # Update average latency
        if jobs_completed > 0:
            new_avg = (avg_latency * jobs_completed + latency_ms) / (jobs_completed + 1)
        else:
            new_avg = latency_ms
        
        cursor.execute("""
            UPDATE decentralized_nodes
            SET last_heartbeat = ?, average_latency_ms = ?
            WHERE node_id = ?
        """, (now, new_avg, node_id))
        
        conn.commit()
        conn.close()
        
        return self.get_node(node_id)
    
    def get_node(self, node_id: str) -> Optional[NodeRegistration]:
        """Get a node by ID."""
        if self.registry_mode == "solana_devnet":
            raise NotImplementedError("Solana devnet get_node not yet implemented")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM decentralized_nodes WHERE node_id = ?", (node_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return NodeRegistration(
            node_id=row[0],
            machine_name=row[1],
            models_available=json.loads(row[2]),
            endpoint_url=row[3],
            wallet_address=row[4],
            public_key=row[5],
            created_at=row[6],
            last_heartbeat=row[7],
            status=row[8],
            uptime_score=row[9],
            jobs_completed=row[10],
            total_fees_earned=row[11],
            average_latency_ms=row[12]
        )
    
    def list_active_nodes(self) -> List[NodeRegistration]:
        """List all active nodes."""
        if self.registry_mode == "solana_devnet":
            raise NotImplementedError("Solana devnet list_active_nodes not yet implemented")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM decentralized_nodes WHERE status = 'active'")
        rows = cursor.fetchall()
        conn.close()
        
        return [
            NodeRegistration(
                node_id=row[0],
                machine_name=row[1],
                models_available=json.loads(row[2]),
                endpoint_url=row[3],
                wallet_address=row[4],
                public_key=row[5],
                created_at=row[6],
                last_heartbeat=row[7],
                status=row[8],
                uptime_score=row[9],
                jobs_completed=row[10],
                total_fees_earned=row[11],
                average_latency_ms=row[12]
            )
            for row in rows
        ]
    
    def find_nodes_by_model(self, model_name: str) -> List[NodeRegistration]:
        """Find nodes that have a specific model available."""
        if self.registry_mode == "solana_devnet":
            raise NotImplementedError("Solana devnet find_nodes_by_model not yet implemented")
        
        nodes = self.list_active_nodes()
        return [node for node in nodes if model_name in node.models_available]
    
    def update_node_stats(
        self,
        node_id: str,
        jobs_completed_delta: int = 0,
        fees_earned_delta: float = 0.0
    ):
        """Update node statistics."""
        if self.registry_mode == "solana_devnet":
            raise NotImplementedError("Solana devnet update_node_stats not yet implemented")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE decentralized_nodes
            SET jobs_completed = jobs_completed + ?,
                total_fees_earned = total_fees_earned + ?
            WHERE node_id = ?
        """, (jobs_completed_delta, fees_earned_delta, node_id))
        
        conn.commit()
        conn.close()


import json  # Import at module level for use in methods


if __name__ == "__main__":
    # Test node registry
    print("Testing node registry (local mode)...")
    
    from node_identity import generate_node_identity, load_node_identity
    
    # Generate test identity
    identity = generate_node_identity(
        machine_name="test-node-01",
        models_available=["llama2", "mistral"],
        endpoint_url="http://localhost:11434",
        wallet_address="test_wallet"
    )
    
    # Create registry
    registry = NodeRegistry(registry_mode="local")
    
    # Register node
    registration = registry.register_node(identity.metadata)
    print(f"Registered node: {registration.node_id}")
    print(f"Status: {registration.status}")
    print(f"Last heartbeat: {registration.last_heartbeat}")
    
    # Update heartbeat
    updated = registry.update_heartbeat(
        registration.node_id,
        latency_ms=50,
        model_loaded=True,
        available_memory=8192,
        queue_depth=0
    )
    print(f"Updated heartbeat: {updated.last_heartbeat}")
    print(f"Average latency: {updated.average_latency_ms}ms")
    
    # Find by model
    llama2_nodes = registry.find_nodes_by_model("llama2")
    print(f"Nodes with llama2: {len(llama2_nodes)}")
    
    # List all active
    all_nodes = registry.list_active_nodes()
    print(f"Total active nodes: {len(all_nodes)}")
    
    print("Registry test passed!")
