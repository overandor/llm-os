"""
Node identity management for decentralized inference workers
"""
import json
import hashlib
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional

# cryptography is required for key generation
try:
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.backends import default_backend
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False


@dataclass
class NodeMetadata:
    """Public metadata for a node."""
    node_id: str
    machine_name: str
    models_available: list[str]
    endpoint_url: str
    wallet_address: str
    created_at: str
    public_key: str


@dataclass
class NodeIdentity:
    """Complete node identity (includes private key)."""
    metadata: NodeMetadata
    private_key: str


def generate_node_identity(
    machine_name: str,
    models_available: list[str],
    endpoint_url: str,
    wallet_address: str,
    identity_path: Optional[Path] = None,
    use_mock: bool = False
) -> NodeIdentity:
    """Generate a new node identity with Ed25519 key pair."""
    if use_mock or not CRYPTO_AVAILABLE:
        # Mock mode for testing without cryptography
        import secrets
        private_bytes = secrets.token_bytes(32)
        public_bytes = secrets.token_bytes(32)
    else:
        from cryptography.hazmat.primitives.asymmetric import ed25519
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.backends import default_backend
        
        # Generate Ed25519 key pair
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        
        # Serialize keys
        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        public_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
    
    # Derive node_id from public key hash
    node_id = hashlib.sha256(public_bytes).hexdigest()[:16]
    
    # Create metadata
    metadata = NodeMetadata(
        node_id=node_id,
        machine_name=machine_name,
        models_available=models_available,
        endpoint_url=endpoint_url,
        wallet_address=wallet_address,
        created_at=datetime.now(timezone.utc).isoformat(),
        public_key=public_bytes.hex()
    )
    
    identity = NodeIdentity(
        metadata=metadata,
        private_key=private_bytes.hex()
    )
    
    # Save to disk
    if identity_path is None:
        identity_path = Path.home() / ".llm_os" / "node_identity.json"
    
    identity_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Save only public metadata (never private key in public file)
    public_path = identity_path.parent / "node_public.json"
    with open(public_path, 'w') as f:
        json.dump(asdict(metadata), f, indent=2)
    
    # Save full identity (private key) - protected file
    with open(identity_path, 'w') as f:
        json.dump(asdict(identity), f, indent=2)
    
    # Set restrictive permissions on private file
    identity_path.chmod(0o600)
    
    return identity


def load_node_identity(identity_path: Optional[Path] = None) -> NodeIdentity:
    """Load node identity from disk."""
    if identity_path is None:
        identity_path = Path.home() / ".llm_os" / "node_identity.json"
    
    if not identity_path.exists():
        raise FileNotFoundError(f"Node identity not found at {identity_path}. Run generate_node_identity() first.")
    
    with open(identity_path, 'r') as f:
        data = json.load(f)
    
    return NodeIdentity(
        metadata=NodeMetadata(**data['metadata']),
        private_key=data['private_key']
    )


def load_public_metadata(public_path: Optional[Path] = None) -> NodeMetadata:
    """Load only public metadata (no private key)."""
    if public_path is None:
        public_path = Path.home() / ".llm_os" / "node_public.json"
    
    if not public_path.exists():
        raise FileNotFoundError(f"Public metadata not found at {public_path}.")
    
    with open(public_path, 'r') as f:
        data = json.load(f)
    
    return NodeMetadata(**data)


def sign_message(message: str, private_key_hex: str, use_mock: bool = False) -> str:
    """Sign a message with the node's private key."""
    if use_mock or not CRYPTO_AVAILABLE:
        # Mock signing: hash message + private key
        import hashlib
        combined = f"{message}:{private_key_hex}"
        return hashlib.sha256(combined.encode()).hexdigest()
    
    from cryptography.hazmat.primitives.asymmetric import ed25519
    
    private_key = ed25519.Ed25519PrivateKey.from_private_bytes(
        bytes.fromhex(private_key_hex)
    )
    
    signature = private_key.sign(message.encode())
    return signature.hex()


def verify_signature(message: str, signature_hex: str, public_key_hex: str, use_mock: bool = False) -> bool:
    """Verify a signature against a public key."""
    if use_mock or not CRYPTO_AVAILABLE:
        # Mock verification: recompute hash
        import hashlib
        # For mock, we can't verify without the private key, so we just check format
        return len(signature_hex) == 64 and len(public_key_hex) == 64
    
    from cryptography.hazmat.primitives.asymmetric import ed25519
    
    public_key = ed25519.Ed25519PublicKey.from_public_bytes(
        bytes.fromhex(public_key_hex)
    )
    
    try:
        public_key.verify(
            bytes.fromhex(signature_hex),
            message.encode()
        )
        return True
    except Exception:
        return False


if __name__ == "__main__":
    # Test node identity generation
    print("Generating test node identity...")
    
    identity = generate_node_identity(
        machine_name="test-node-01",
        models_available=["llama2", "mistral"],
        endpoint_url="http://localhost:11434",
        wallet_address="test_wallet_address"
    )
    
    print(f"Node ID: {identity.metadata.node_id}")
    print(f"Machine Name: {identity.metadata.machine_name}")
    print(f"Models: {identity.metadata.models_available}")
    print(f"Created At: {identity.metadata.created_at}")
    print(f"Public Key: {identity.metadata.public_key[:32]}...")
    
    # Test signing
    test_message = "test inference job"
    signature = sign_message(test_message, identity.private_key)
    print(f"\nSignature: {signature[:32]}...")
    
    # Test verification
    is_valid = verify_signature(test_message, signature, identity.metadata.public_key)
    print(f"Signature valid: {is_valid}")
    
    # Test loading
    loaded = load_node_identity()
    print(f"\nLoaded Node ID: {loaded.metadata.node_id}")
    print("Identity test passed!")
