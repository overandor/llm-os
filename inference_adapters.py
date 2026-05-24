"""
Inference adapters for local model backends
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass
import time
import hashlib

# httpx is optional - only required for Ollama and llama.cpp adapters
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False


@dataclass
class InferenceResult:
    """Result from inference adapter."""
    text: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    model: str
    success: bool
    error: Optional[str] = None


class BaseInferenceAdapter(ABC):
    """Base class for inference adapters."""
    
    def __init__(self, model: str):
        self.model = model
    
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
        timeout: int = 30
    ) -> InferenceResult:
        """Generate text from prompt."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the backend is available."""
        pass
    
    def hash_text(self, text: str) -> str:
        """Hash text for receipt generation."""
        return hashlib.sha256(text.encode()).hexdigest()


class OllamaAdapter(BaseInferenceAdapter):
    """Adapter for Ollama local inference."""
    
    def __init__(self, model: str, base_url: str = "http://localhost:11434"):
        super().__init__(model)
        self.base_url = base_url
        self._client = None
        if not HTTPX_AVAILABLE:
            raise RuntimeError("httpx is required for OllamaAdapter. Install with: pip install httpx")
    
    @property
    def client(self) -> httpx.AsyncClient:
        """Lazy-load HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client
    
    async def generate(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
        timeout: int = 30
    ) -> InferenceResult:
        """Generate text using Ollama API."""
        start_time = time.time()
        
        try:
            response = await self.client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": max_tokens,
                        "temperature": temperature,
                    }
                },
                timeout=timeout
            )
            
            response.raise_for_status()
            data = response.json()
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            # Ollama doesn't always return token counts, estimate if missing
            input_tokens = data.get("prompt_eval_count", len(prompt.split()) * 1.3)
            output_tokens = data.get("eval_count", len(data.get("response", "").split()) * 1.3)
            
            return InferenceResult(
                text=data.get("response", ""),
                input_tokens=int(input_tokens),
                output_tokens=int(output_tokens),
                latency_ms=latency_ms,
                model=self.model,
                success=True
            )
            
        except httpx.TimeoutException:
            return InferenceResult(
                text="",
                input_tokens=0,
                output_tokens=0,
                latency_ms=int((time.time() - start_time) * 1000),
                model=self.model,
                success=False,
                error="Request timed out"
            )
        except httpx.HTTPError as e:
            return InferenceResult(
                text="",
                input_tokens=0,
                output_tokens=0,
                latency_ms=int((time.time() - start_time) * 1000),
                model=self.model,
                success=False,
                error=f"HTTP error: {str(e)}"
            )
        except Exception as e:
            return InferenceResult(
                text="",
                input_tokens=0,
                output_tokens=0,
                latency_ms=int((time.time() - start_time) * 1000),
                model=self.model,
                success=False,
                error=f"Unexpected error: {str(e)}"
            )
    
    def is_available(self) -> bool:
        """Check if Ollama is available."""
        try:
            import httpx
            client = httpx.Client(timeout=5.0)
            response = client.get(f"{self.base_url}/api/tags")
            client.close()
            return response.status_code == 200
        except Exception:
            return False


class LlamaCppAdapter(BaseInferenceAdapter):
    """Adapter for llama.cpp server."""
    
    def __init__(self, model: str, base_url: str = "http://localhost:8080"):
        super().__init__(model)
        self.base_url = base_url
        self._client = None
        if not HTTPX_AVAILABLE:
            raise RuntimeError("httpx is required for LlamaCppAdapter. Install with: pip install httpx")
    
    @property
    def client(self) -> httpx.AsyncClient:
        """Lazy-load HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client
    
    async def generate(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
        timeout: int = 30
    ) -> InferenceResult:
        """Generate text using llama.cpp server API."""
        start_time = time.time()
        
        try:
            response = await self.client.post(
                f"{self.base_url}/completion",
                json={
                    "prompt": prompt,
                    "n_predict": max_tokens,
                    "temperature": temperature,
                    "stream": False
                },
                timeout=timeout
            )
            
            response.raise_for_status()
            data = response.json()
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            # llama.cpp returns tokens_processed and tokens_predicted
            input_tokens = data.get("tokens_evaluated", len(prompt.split()))
            output_tokens = data.get("tokens_predicted", len(data.get("content", "").split()))
            
            return InferenceResult(
                text=data.get("content", ""),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
                model=self.model,
                success=True
            )
            
        except httpx.TimeoutException:
            return InferenceResult(
                text="",
                input_tokens=0,
                output_tokens=0,
                latency_ms=int((time.time() - start_time) * 1000),
                model=self.model,
                success=False,
                error="Request timed out"
            )
        except httpx.HTTPError as e:
            return InferenceResult(
                text="",
                input_tokens=0,
                output_tokens=0,
                latency_ms=int((time.time() - start_time) * 1000),
                model=self.model,
                success=False,
                error=f"HTTP error: {str(e)}"
            )
        except Exception as e:
            return InferenceResult(
                text="",
                input_tokens=0,
                output_tokens=0,
                latency_ms=int((time.time() - start_time) * 1000),
                model=self.model,
                success=False,
                error=f"Unexpected error: {str(e)}"
            )
    
    def is_available(self) -> bool:
        """Check if llama.cpp server is available."""
        try:
            import httpx
            client = httpx.Client(timeout=5.0)
            response = client.get(f"{self.base_url}/health")
            client.close()
            return response.status_code == 200
        except Exception:
            return False


class MockAdapter(BaseInferenceAdapter):
    """Mock adapter for testing only. Never use in production."""
    
    async def generate(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
        timeout: int = 30
    ) -> InferenceResult:
        """Generate mock response."""
        start_time = time.time()
        
        # Simulate latency
        await asyncio.sleep(0.1)
        
        latency_ms = int((time.time() - start_time) * 1000)
        
        return InferenceResult(
            text=f"[MOCK RESPONSE] This is a simulated response for: {prompt[:50]}...",
            input_tokens=len(prompt.split()),
            output_tokens=20,
            latency_ms=latency_ms,
            model=self.model,
            success=True
        )
    
    def is_available(self) -> bool:
        """Mock is always available."""
        return True


def get_adapter(runtime_type: str, model: str, base_url: Optional[str] = None) -> BaseInferenceAdapter:
    """Factory function to get appropriate adapter."""
    if runtime_type == "ollama":
        return OllamaAdapter(model, base_url or "http://localhost:11434")
    elif runtime_type == "llama_cpp":
        return LlamaCppAdapter(model, base_url or "http://localhost:8080")
    elif runtime_type == "mock":
        return MockAdapter(model)
    else:
        raise ValueError(f"Unknown runtime type: {runtime_type}")


import asyncio
