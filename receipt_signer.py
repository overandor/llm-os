"""
Receipt signing and verification for inference receipts
"""
import hashlib
import hmac
import json
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from liquid_endpoint_store import InferenceReceipt


def canonical_json(data: Dict[str, Any]) -> str:
    """Serialize data to canonical JSON for signing."""
    return json.dumps(data, sort_keys=True, separators=(',', ':'))


def sha256_hash(data: str) -> str:
    """Compute SHA256 hash."""
    return hashlib.sha256(data.encode()).hexdigest()


@dataclass
class SignedReceipt:
    """A signed inference receipt."""
    receipt: InferenceReceipt
    signature: str
    signing_method: str = "hmac-sha256"


class ReceiptSigner:
    """Sign and verify inference receipts."""
    
    def __init__(self, secret_key: str):
        """
        Initialize signer with secret key.
        
        In production, this should be a secure key stored in environment variables
        or a hardware security module.
        """
        self.secret_key = secret_key.encode()
    
    def sign_receipt(self, receipt: InferenceReceipt) -> SignedReceipt:
        """
        Sign an inference receipt.
        
        The signature covers all receipt fields except the signature itself.
        """
        # Create canonical representation
        receipt_dict = {
            "receipt_id": receipt.receipt_id,
            "endpoint_id": receipt.endpoint_id,
            "requester_wallet": receipt.requester_wallet,
            "prompt_hash": receipt.prompt_hash,
            "response_hash": receipt.response_hash,
            "model_name": receipt.model_name,
            "input_tokens": receipt.input_tokens,
            "output_tokens": receipt.output_tokens,
            "fee_paid": receipt.fee_paid,
            "staker_revenue": receipt.staker_revenue,
            "operator_revenue": receipt.operator_revenue,
            "timestamp": receipt.timestamp,
        }
        
        canonical = canonical_json(receipt_dict)
        signature = hmac.new(
            self.secret_key,
            canonical.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Update receipt with signature
        signed_receipt = InferenceReceipt(
            receipt_id=receipt.receipt_id,
            endpoint_id=receipt.endpoint_id,
            requester_wallet=receipt.requester_wallet,
            prompt_hash=receipt.prompt_hash,
            response_hash=receipt.response_hash,
            model_name=receipt.model_name,
            input_tokens=receipt.input_tokens,
            output_tokens=receipt.output_tokens,
            fee_paid=receipt.fee_paid,
            staker_revenue=receipt.staker_revenue,
            operator_revenue=receipt.operator_revenue,
            timestamp=receipt.timestamp,
            signature=signature
        )
        
        return SignedReceipt(
            receipt=signed_receipt,
            signature=signature
        )
    
    def verify_receipt(self, receipt: InferenceReceipt) -> bool:
        """
        Verify a signed receipt.
        
        Returns True if the signature is valid, False otherwise.
        """
        if not receipt.signature:
            return False
        
        # Recreate canonical representation
        receipt_dict = {
            "receipt_id": receipt.receipt_id,
            "endpoint_id": receipt.endpoint_id,
            "requester_wallet": receipt.requester_wallet,
            "prompt_hash": receipt.prompt_hash,
            "response_hash": receipt.response_hash,
            "model_name": receipt.model_name,
            "input_tokens": receipt.input_tokens,
            "output_tokens": receipt.output_tokens,
            "fee_paid": receipt.fee_paid,
            "staker_revenue": receipt.staker_revenue,
            "operator_revenue": receipt.operator_revenue,
            "timestamp": receipt.timestamp,
        }
        
        canonical = canonical_json(receipt_dict)
        expected_signature = hmac.new(
            self.secret_key,
            canonical.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Use constant-time comparison to prevent timing attacks
        return hmac.compare_digest(expected_signature, receipt.signature)
    
    def verify_receipt_with_public_key(
        self,
        receipt: InferenceReceipt,
        public_key_hash: str
    ) -> bool:
        """
        Verify receipt using public key hash (for distributed verification).
        
        In a production system with multiple signing nodes, each node would have
        its own secret key, and the public key hash would be used to verify
        which node signed the receipt.
        """
        # For now, this delegates to the regular verification
        # In production, this would look up the node's public key and verify
        return self.verify_receipt(receipt)


class ReceiptFactory:
    """Factory for creating and signing receipts."""
    
    def __init__(self, signer: ReceiptSigner):
        self.signer = signer
    
    def create_receipt(
        self,
        endpoint_id: str,
        requester_wallet: str,
        prompt: str,
        response: str,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
        fee_paid: float,
        staker_revenue: float,
        operator_revenue: float
    ) -> SignedReceipt:
        """
        Create and sign a new inference receipt.
        """
        from uuid import uuid4
        from datetime import datetime, timezone
        
        receipt_id = f"rcpt_{uuid4().hex[:16]}"
        timestamp = datetime.now(timezone.utc).isoformat()
        
        prompt_hash = sha256_hash(prompt)
        response_hash = sha256_hash(response)
        
        receipt = InferenceReceipt(
            receipt_id=receipt_id,
            endpoint_id=endpoint_id,
            requester_wallet=requester_wallet,
            prompt_hash=prompt_hash,
            response_hash=response_hash,
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            fee_paid=fee_paid,
            staker_revenue=staker_revenue,
            operator_revenue=operator_revenue,
            timestamp=timestamp
        )
        
        return self.signer.sign_receipt(receipt)
    
    def verify_and_parse(self, receipt_data: Dict[str, Any]) -> Optional[InferenceReceipt]:
        """
        Verify receipt from dict data and return parsed receipt if valid.
        """
        try:
            receipt = InferenceReceipt(**receipt_data)
            if self.signer.verify_receipt(receipt):
                return receipt
            return None
        except Exception:
            return None


def get_signer(secret_key: Optional[str] = None) -> ReceiptSigner:
    """
    Get a receipt signer.
    
    If no secret key is provided, uses a default for local development.
    In production, always provide a secure secret key via environment variable.
    """
    import os
    
    if secret_key is None:
        secret_key = os.getenv("RECEIPT_SIGNING_KEY", "default-dev-key-change-in-production")
    
    return ReceiptSigner(secret_key)
