"""
SQLite storage for liquid staked endpoints
"""
import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
import json


@dataclass
class LiquidEndpoint:
    endpoint_id: str
    owner_wallet: str
    endpoint_url: str
    model_name: str
    runtime_type: str  # ollama | llama_cpp | openai_proxy | custom
    price_per_request: float
    price_per_1k_tokens: float
    revenue_share_bps: int
    total_staked: float
    liquid_supply: float
    exchange_rate: float
    status: str  # active | paused | slashed | retired
    created_at: str
    last_heartbeat: Optional[str] = None
    uptime_score: float = 100.0
    total_requests: int = 0
    total_tokens: int = 0
    total_revenue: float = 0.0
    pending_rewards: float = 0.0


@dataclass
class EndpointStakePosition:
    position_id: str
    endpoint_id: str
    staker_wallet: str
    staked_amount: float
    liquid_tokens_minted: float
    entry_exchange_rate: float
    rewards_claimed: float = 0.0
    created_at: str = ""
    updated_at: str = ""


@dataclass
class InferenceReceipt:
    receipt_id: str
    endpoint_id: str
    requester_wallet: str
    prompt_hash: str
    response_hash: str
    model_name: str
    input_tokens: int
    output_tokens: int
    fee_paid: float
    staker_revenue: float
    operator_revenue: float
    timestamp: str
    signature: Optional[str] = None


@dataclass
class EndpointHeartbeat:
    endpoint_id: str
    timestamp: str
    status: str
    latency_ms: int
    model_loaded: bool
    available_memory: int
    queue_depth: int
    signature: Optional[str] = None


class LiquidEndpointStore:
    """SQLite store for liquid staked endpoints."""
    
    def __init__(self, db_path: Path = Path("~/llm_liquid_endpoints.db").expanduser()):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Endpoints table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS liquid_endpoints (
                endpoint_id TEXT PRIMARY KEY,
                owner_wallet TEXT NOT NULL,
                endpoint_url TEXT NOT NULL,
                model_name TEXT NOT NULL,
                runtime_type TEXT NOT NULL,
                price_per_request REAL NOT NULL,
                price_per_1k_tokens REAL NOT NULL,
                revenue_share_bps INTEGER NOT NULL,
                total_staked REAL DEFAULT 0.0,
                liquid_supply REAL DEFAULT 0.0,
                exchange_rate REAL DEFAULT 1.0,
                status TEXT DEFAULT 'active',
                created_at TEXT NOT NULL,
                last_heartbeat TEXT,
                uptime_score REAL DEFAULT 100.0,
                total_requests INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                total_revenue REAL DEFAULT 0.0,
                pending_rewards REAL DEFAULT 0.0
            )
        """)
        
        # Stake positions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stake_positions (
                position_id TEXT PRIMARY KEY,
                endpoint_id TEXT NOT NULL,
                staker_wallet TEXT NOT NULL,
                staked_amount REAL NOT NULL,
                liquid_tokens_minted REAL NOT NULL,
                entry_exchange_rate REAL NOT NULL,
                rewards_claimed REAL DEFAULT 0.0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (endpoint_id) REFERENCES liquid_endpoints(endpoint_id)
            )
        """)
        
        # Inference receipts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inference_receipts (
                receipt_id TEXT PRIMARY KEY,
                endpoint_id TEXT NOT NULL,
                requester_wallet TEXT NOT NULL,
                prompt_hash TEXT NOT NULL,
                response_hash TEXT NOT NULL,
                model_name TEXT NOT NULL,
                input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                fee_paid REAL NOT NULL,
                staker_revenue REAL NOT NULL,
                operator_revenue REAL NOT NULL,
                timestamp TEXT NOT NULL,
                signature TEXT,
                FOREIGN KEY (endpoint_id) REFERENCES liquid_endpoints(endpoint_id)
            )
        """)
        
        # Heartbeats table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS endpoint_heartbeats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                endpoint_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                status TEXT NOT NULL,
                latency_ms INTEGER NOT NULL,
                model_loaded INTEGER NOT NULL,
                available_memory INTEGER NOT NULL,
                queue_depth INTEGER NOT NULL,
                signature TEXT,
                FOREIGN KEY (endpoint_id) REFERENCES liquid_endpoints(endpoint_id)
            )
        """)
        
        # Reward events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reward_events (
                event_id TEXT PRIMARY KEY,
                endpoint_id TEXT NOT NULL,
                wallet TEXT NOT NULL,
                amount REAL NOT NULL,
                event_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (endpoint_id) REFERENCES liquid_endpoints(endpoint_id)
            )
        """)
        
        # Slash events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS slash_events (
                slash_id TEXT PRIMARY KEY,
                endpoint_id TEXT NOT NULL,
                reason TEXT NOT NULL,
                amount_slashed REAL NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (endpoint_id) REFERENCES liquid_endpoints(endpoint_id)
            )
        """)
        
        # Wallet balances table (for local ledger mode)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wallet_balances (
                wallet TEXT NOT NULL,
                token_symbol TEXT NOT NULL,
                balance REAL DEFAULT 0.0,
                PRIMARY KEY (wallet, token_symbol)
            )
        """)
        
        conn.commit()
        conn.close()
    
    # Endpoint operations
    def create_endpoint(self, endpoint: LiquidEndpoint) -> LiquidEndpoint:
        """Create a new endpoint."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            """
            INSERT INTO liquid_endpoints VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                endpoint.endpoint_id,
                endpoint.owner_wallet,
                endpoint.endpoint_url,
                endpoint.model_name,
                endpoint.runtime_type,
                endpoint.price_per_request,
                endpoint.price_per_1k_tokens,
                endpoint.revenue_share_bps,
                endpoint.total_staked,
                endpoint.liquid_supply,
                endpoint.exchange_rate,
                endpoint.status,
                endpoint.created_at,
                endpoint.last_heartbeat,
                endpoint.uptime_score,
                endpoint.total_requests,
                endpoint.total_tokens,
                endpoint.total_revenue,
                endpoint.pending_rewards,
            )
        )
        
        conn.commit()
        conn.close()
        return endpoint
    
    def get_endpoint(self, endpoint_id: str) -> Optional[LiquidEndpoint]:
        """Get endpoint by ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM liquid_endpoints WHERE endpoint_id = ?", (endpoint_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return LiquidEndpoint(
            endpoint_id=row[0],
            owner_wallet=row[1],
            endpoint_url=row[2],
            model_name=row[3],
            runtime_type=row[4],
            price_per_request=row[5],
            price_per_1k_tokens=row[6],
            revenue_share_bps=row[7],
            total_staked=row[8],
            liquid_supply=row[9],
            exchange_rate=row[10],
            status=row[11],
            created_at=row[12],
            last_heartbeat=row[13],
            uptime_score=row[14],
            total_requests=row[15],
            total_tokens=row[16],
            total_revenue=row[17],
            pending_rewards=row[18],
        )
    
    def list_endpoints(self, status: Optional[str] = None) -> List[LiquidEndpoint]:
        """List all endpoints, optionally filtered by status."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if status:
            cursor.execute("SELECT * FROM liquid_endpoints WHERE status = ?", (status,))
        else:
            cursor.execute("SELECT * FROM liquid_endpoints")
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            LiquidEndpoint(
                endpoint_id=row[0],
                owner_wallet=row[1],
                endpoint_url=row[2],
                model_name=row[3],
                runtime_type=row[4],
                price_per_request=row[5],
                price_per_1k_tokens=row[6],
                revenue_share_bps=row[7],
                total_staked=row[8],
                liquid_supply=row[9],
                exchange_rate=row[10],
                status=row[11],
                created_at=row[12],
                last_heartbeat=row[13],
                uptime_score=row[14],
                total_requests=row[15],
                total_tokens=row[16],
                total_revenue=row[17],
                pending_rewards=row[18],
            )
            for row in rows
        ]
    
    def update_endpoint(self, endpoint_id: str, updates: Dict[str, Any]):
        """Update endpoint fields."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [endpoint_id]
        
        cursor.execute(
            f"UPDATE liquid_endpoints SET {set_clause} WHERE endpoint_id = ?",
            values
        )
        
        conn.commit()
        conn.close()
    
    # Stake position operations
    def create_stake_position(self, position: EndpointStakePosition) -> EndpointStakePosition:
        """Create a new stake position."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            """
            INSERT INTO stake_positions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                position.position_id,
                position.endpoint_id,
                position.staker_wallet,
                position.staked_amount,
                position.liquid_tokens_minted,
                position.entry_exchange_rate,
                position.rewards_claimed,
                position.created_at,
                position.updated_at,
            )
        )
        
        conn.commit()
        conn.close()
        return position
    
    def get_stake_positions(self, endpoint_id: str) -> List[EndpointStakePosition]:
        """Get all stake positions for an endpoint."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM stake_positions WHERE endpoint_id = ?",
            (endpoint_id,)
        )
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            EndpointStakePosition(
                position_id=row[0],
                endpoint_id=row[1],
                staker_wallet=row[2],
                staked_amount=row[3],
                liquid_tokens_minted=row[4],
                entry_exchange_rate=row[5],
                rewards_claimed=row[6],
                created_at=row[7],
                updated_at=row[8],
            )
            for row in rows
        ]
    
    def get_wallet_position(self, endpoint_id: str, wallet: str) -> Optional[EndpointStakePosition]:
        """Get stake position for a specific wallet."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM stake_positions WHERE endpoint_id = ? AND staker_wallet = ?",
            (endpoint_id, wallet)
        )
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return EndpointStakePosition(
            position_id=row[0],
            endpoint_id=row[1],
            staker_wallet=row[2],
            staked_amount=row[3],
            liquid_tokens_minted=row[4],
            entry_exchange_rate=row[5],
            rewards_claimed=row[6],
            created_at=row[7],
            updated_at=row[8],
        )
    
    # Receipt operations
    def create_receipt(self, receipt: InferenceReceipt) -> InferenceReceipt:
        """Create an inference receipt."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            """
            INSERT INTO inference_receipts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                receipt.receipt_id,
                receipt.endpoint_id,
                receipt.requester_wallet,
                receipt.prompt_hash,
                receipt.response_hash,
                receipt.model_name,
                receipt.input_tokens,
                receipt.output_tokens,
                receipt.fee_paid,
                receipt.staker_revenue,
                receipt.operator_revenue,
                receipt.timestamp,
                receipt.signature,
            )
        )
        
        conn.commit()
        conn.close()
        return receipt
    
    def get_receipts(self, endpoint_id: str, limit: int = 100) -> List[InferenceReceipt]:
        """Get receipts for an endpoint."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM inference_receipts WHERE endpoint_id = ? ORDER BY timestamp DESC LIMIT ?",
            (endpoint_id, limit)
        )
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            InferenceReceipt(
                receipt_id=row[0],
                endpoint_id=row[1],
                requester_wallet=row[2],
                prompt_hash=row[3],
                response_hash=row[4],
                model_name=row[5],
                input_tokens=row[6],
                output_tokens=row[7],
                fee_paid=row[8],
                staker_revenue=row[9],
                operator_revenue=row[10],
                timestamp=row[11],
                signature=row[12],
            )
            for row in rows
        ]
    
    # Heartbeat operations
    def record_heartbeat(self, heartbeat: EndpointHeartbeat):
        """Record an endpoint heartbeat."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            """
            INSERT INTO endpoint_heartbeats 
            (endpoint_id, timestamp, status, latency_ms, model_loaded, available_memory, queue_depth, signature)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                heartbeat.endpoint_id,
                heartbeat.timestamp,
                heartbeat.status,
                heartbeat.latency_ms,
                1 if heartbeat.model_loaded else 0,
                heartbeat.available_memory,
                heartbeat.queue_depth,
                heartbeat.signature,
            )
        )
        
        # Update endpoint last_heartbeat
        cursor.execute(
            "UPDATE liquid_endpoints SET last_heartbeat = ? WHERE endpoint_id = ?",
            (heartbeat.timestamp, heartbeat.endpoint_id)
        )
        
        conn.commit()
        conn.close()
    
    # Wallet balance operations (local ledger mode)
    def get_balance(self, wallet: str, token_symbol: str = "INF") -> float:
        """Get wallet balance for a token."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT balance FROM wallet_balances WHERE wallet = ? AND token_symbol = ?",
            (wallet, token_symbol)
        )
        
        row = cursor.fetchone()
        conn.close()
        
        return row[0] if row else 0.0
    
    def set_balance(self, wallet: str, token_symbol: str, balance: float):
        """Set wallet balance."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            """
            INSERT OR REPLACE INTO wallet_balances (wallet, token_symbol, balance)
            VALUES (?, ?, ?)
            """,
            (wallet, token_symbol, balance)
        )
        
        conn.commit()
        conn.close()
    
    def adjust_balance(self, wallet: str, token_symbol: str, delta: float) -> float:
        """Adjust wallet balance by delta."""
        current = self.get_balance(wallet, token_symbol)
        new_balance = current + delta
        
        if new_balance < 0:
            raise ValueError("Insufficient balance")
        
        self.set_balance(wallet, token_symbol, new_balance)
        return new_balance
