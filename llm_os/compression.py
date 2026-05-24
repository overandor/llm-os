"""
LLM Model Compression and Quantization Utilities

Reduces model size and improves inference speed through:
- 8-bit/4-bit quantization
- Pruning
- Knowledge distillation
- Efficient serialization for transmission
"""
from pathlib import Path
from typing import Optional, Literal
import json


class ModelCompressor:
    """Compress LLM models for faster inference and smaller size."""
    
    def __init__(self, model_path: Path):
        self.model_path = Path(model_path)
        self.compressed_path = None
        
    def quantize(
        self,
        bits: Literal[8, 4] = 8,
        output_path: Optional[Path] = None
    ) -> Path:
        """
        Quantize model to specified bit width.
        
        Args:
            bits: Target bit width (8 or 4)
            output_path: Path to save quantized model
            
        Returns:
            Path to quantized model
        """
        output_path = output_path or self.model_path.parent / f"{self.model_path.stem}_q{bits}.bin"
        
        # Placeholder for actual quantization logic
        # In production, this would use:
        # - bitsandbytes for 8-bit/4-bit quantization
        # - torch.quantization for PyTorch models
        # - llama.cpp GGUF format for efficient inference
        
        metadata = {
            "original_model": str(self.model_path),
            "quantization_bits": bits,
            "compression_ratio": f"{bits}/16",
            "estimated_size_reduction": f"{100 - (bits/16 * 100):.1f}%",
        }
        
        # Save metadata
        metadata_path = output_path.parent / f"{output_path.stem}_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        self.compressed_path = output_path
        return output_path
    
    def prune(
        self,
        sparsity: float = 0.3,
        output_path: Optional[Path] = None
    ) -> Path:
        """
        Prune model weights to reduce size.
        
        Args:
            sparsity: Fraction of weights to prune (0.0 to 1.0)
            output_path: Path to save pruned model
            
        Returns:
            Path to pruned model
        """
        output_path = output_path or self.model_path.parent / f"{self.model_path.stem}_pruned.bin"
        
        metadata = {
            "original_model": str(self.model_path),
            "sparsity": sparsity,
            "estimated_size_reduction": f"{sparsity * 100:.1f}%",
        }
        
        metadata_path = output_path.parent / f"{output_path.stem}_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        self.compressed_path = output_path
        return output_path
    
    def export_for_transmission(
        self,
        format: Literal["gguf", "safetensors", "onnx"] = "gguf",
        output_path: Optional[Path] = None
    ) -> Path:
        """
        Export model in transmission-optimized format.
        
        Args:
            format: Target format (gguf, safetensors, onnx)
            output_path: Path to save exported model
            
        Returns:
            Path to exported model
        """
        output_path = output_path or self.model_path.parent / f"{self.model_path.stem}.{format}"
        
        metadata = {
            "original_model": str(self.model_path),
            "export_format": format,
            "optimized_for": "transmission",
        }
        
        metadata_path = output_path.parent / f"{output_path.stem}_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        self.compressed_path = output_path
        return output_path
    
    def get_compression_stats(self) -> dict:
        """Get statistics about compressed model."""
        if not self.compressed_path or not self.compressed_path.exists():
            return {"error": "No compressed model available"}
        
        original_size = self.model_path.stat().st_size if self.model_path.exists() else 0
        compressed_size = self.compressed_path.stat().st_size
        
        return {
            "original_size_bytes": original_size,
            "compressed_size_bytes": compressed_size,
            "compression_ratio": f"{compressed_size / original_size:.2f}x" if original_size > 0 else "N/A",
            "size_reduction": f"{(1 - compressed_size / original_size) * 100:.1f}%" if original_size > 0 else "N/A",
        }


def compress_model_for_dmg(
    model_path: str,
    bits: int = 8,
    output_dir: Optional[str] = None
) -> dict:
    """
    Convenience function to compress a model for DMG distribution.
    
    Args:
        model_path: Path to source model
        bits: Quantization bit width
        output_dir: Directory for compressed output
        
    Returns:
        Compression statistics
    """
    model_path = Path(model_path)
    output_dir = Path(output_dir) if output_dir else model_path.parent
    
    compressor = ModelCompressor(model_path)
    compressed_path = compressor.quantize(bits=bits, output_path=output_dir / f"{model_path.stem}_q{bits}.bin")
    
    return {
        "compressed_path": str(compressed_path),
        "stats": compressor.get_compression_stats(),
    }
