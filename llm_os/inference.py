"""LLM Inference Bridge — Groq, OpenRouter, and local adapters.

Provides synchronous and asynchronous text generation for the OS kernel
and subsystems. Falls back gracefully when APIs are unavailable.

Usage:
    from llm_os.inference import get_inference_bridge
    bridge = get_inference_bridge()
    result = bridge.generate("Build a Python FastAPI app for user auth")
    print(result["text"])
"""

import json
import os
import time
from typing import Dict, List, Optional


class InferenceResult:
    """Result from an LLM inference call."""

    def __init__(
        self,
        text: str = "",
        input_tokens: int = 0,
        output_tokens: int = 0,
        latency_ms: int = 0,
        model: str = "",
        success: bool = False,
        error: Optional[str] = None,
        cost_usd: float = 0.0,
    ):
        self.text = text
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.latency_ms = latency_ms
        self.model = model
        self.success = success
        self.error = error
        self.cost_usd = cost_usd

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "latency_ms": self.latency_ms,
            "model": self.model,
            "success": self.success,
            "error": self.error,
            "cost_usd": self.cost_usd,
        }


class BaseInferenceBridge:
    """Base class for LLM inference backends."""

    def __init__(self, model: str):
        self.model = model

    def generate(self, prompt: str, max_tokens: int = 2048, temperature: float = 0.7) -> InferenceResult:
        raise NotImplementedError

    def is_available(self) -> bool:
        raise NotImplementedError

    def _estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Rough cost estimate in USD. Override per provider."""
        return 0.0


class GroqBridge(BaseInferenceBridge):
    """Groq API bridge for fast LLM inference."""

    API_URL = "https://api.groq.com/openai/v1/chat/completions"
    # Pricing per 1M tokens (approximate, check groq.com/pricing)
    COST_PER_1M_INPUT = 0.59   # llama-3.3-70b-versatile
    COST_PER_1M_OUTPUT = 0.79

    def __init__(self, model: str = "llama-3.3-70b-versatile", api_key: str = None):
        super().__init__(model)
        self.api_key = api_key or os.environ.get("GROQ_API_KEY", "")
        self._client = None

    def _get_client(self):
        """Lazy-load httpx client."""
        if self._client is None:
            try:
                import httpx
                self._client = httpx.Client(timeout=60.0)
            except ImportError:
                pass
        return self._client

    def is_available(self) -> bool:
        if not self.api_key:
            return False
        client = self._get_client()
        if client is None:
            return False
        try:
            resp = client.get("https://api.groq.com/openai/v1/models", headers={
                "Authorization": f"Bearer {self.api_key}",
            }, timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False

    def generate(self, prompt: str, max_tokens: int = 2048, temperature: float = 0.7) -> InferenceResult:
        client = self._get_client()
        if client is None:
            return InferenceResult(error="httpx not installed")
        if not self.api_key:
            return InferenceResult(error="GROQ_API_KEY not set")

        start = time.time()
        try:
            resp = client.post(
                self.API_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "You are a senior software engineer. Write clean, production-ready code with no explanations unless asked."},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            choice = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            input_tok = usage.get("prompt_tokens", 0)
            output_tok = usage.get("completion_tokens", 0)
            latency = int((time.time() - start) * 1000)
            cost = self._estimate_cost(input_tok, output_tok)
            return InferenceResult(
                text=choice,
                input_tokens=input_tok,
                output_tokens=output_tok,
                latency_ms=latency,
                model=self.model,
                success=True,
                cost_usd=cost,
            )
        except Exception as e:
            return InferenceResult(
                error=str(e),
                latency_ms=int((time.time() - start) * 1000),
                model=self.model,
            )

    def _estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        return (
            (input_tokens / 1_000_000) * self.COST_PER_1M_INPUT +
            (output_tokens / 1_000_000) * self.COST_PER_1M_OUTPUT
        )


class OpenRouterBridge(BaseInferenceBridge):
    """OpenRouter API bridge for access to many models."""

    API_URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self, model: str = "meta-llama/llama-3.3-70b-instruct:free", api_key: str = None):
        super().__init__(model)
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import httpx
                self._client = httpx.Client(timeout=60.0)
            except ImportError:
                pass
        return self._client

    def is_available(self) -> bool:
        return bool(self.api_key)

    def generate(self, prompt: str, max_tokens: int = 2048, temperature: float = 0.7) -> InferenceResult:
        client = self._get_client()
        if client is None:
            return InferenceResult(error="httpx not installed")
        if not self.api_key:
            return InferenceResult(error="OPENROUTER_API_KEY not set")

        start = time.time()
        try:
            resp = client.post(
                self.API_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://llm-os.local",
                    "X-Title": "LLM OS",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "You are a senior software engineer."},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            choice = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            latency = int((time.time() - start) * 1000)
            return InferenceResult(
                text=choice,
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                latency_ms=latency,
                model=self.model,
                success=True,
            )
        except Exception as e:
            return InferenceResult(
                error=str(e),
                latency_ms=int((time.time() - start) * 1000),
                model=self.model,
            )


class StubBridge(BaseInferenceBridge):
    """Fallback bridge that returns stub responses. Costs $0."""

    def is_available(self) -> bool:
        return True

    def generate(self, prompt: str, max_tokens: int = 2048, temperature: float = 0.7) -> InferenceResult:
        return InferenceResult(
            text=f"[STUB] Would generate based on: {prompt[:80]}...",
            input_tokens=len(prompt.split()),
            output_tokens=10,
            latency_ms=1,
            model="stub",
            success=True,
            cost_usd=0.0,
        )


# Global registry of bridges
_BRIDGES: Dict[str, BaseInferenceBridge] = {}


def get_inference_bridge(prefer: str = None) -> BaseInferenceBridge:
    """Get the best available inference bridge.

    Priority: Groq -> OpenRouter -> Stub
    """
    # Check cached bridges by name preference
    if prefer and prefer in _BRIDGES:
        return _BRIDGES[prefer]

    # Return any existing cached bridge (first one wins)
    if _BRIDGES:
        return next(iter(_BRIDGES.values()))

    # Try Groq
    groq = GroqBridge()
    if groq.is_available():
        _BRIDGES["groq"] = groq
        return groq

    # Try OpenRouter
    orouter = OpenRouterBridge()
    if orouter.is_available():
        _BRIDGES["openrouter"] = orouter
        return orouter

    # Fallback
    stub = StubBridge("stub")
    _BRIDGES["stub"] = stub
    return stub


def generate_code_with_llm(prompt: str, target_type: str = "python") -> dict:
    """High-level helper: ask LLM to generate code and parse the response.

    Returns a dict with parsed files or an error.
    """
    bridge = get_inference_bridge()
    full_prompt = f"""Generate a complete {target_type} project based on this request.

Request: {prompt}

Rules:
- Output ONLY the code files, no explanations
- Wrap each file in markdown code blocks with the filename as the language tag, like:
  ```filename.py
  # code here
  ```
- Include all necessary files (main code, requirements.txt, Dockerfile if applicable)
- Make sure the code is functional and runnable
"""
    result = bridge.generate(full_prompt, max_tokens=4096, temperature=0.5)
    if not result.success:
        return {"success": False, "error": result.error, "cost_usd": result.cost_usd}

    files = _parse_code_blocks(result.text)
    return {
        "success": True,
        "files": files,
        "raw": result.text,
        "model": result.model,
        "cost_usd": result.cost_usd,
        "tokens": {"input": result.input_tokens, "output": result.output_tokens},
    }


def _parse_code_blocks(text: str) -> Dict[str, str]:
    """Parse markdown code blocks into filename -> content dict."""
    files = {}
    import re
    # Match ```filename.ext ... ``` blocks
    pattern = re.compile(r"```(\S+?)\n(.*?)```", re.DOTALL)
    for match in pattern.finditer(text):
        fname = match.group(1).strip()
        content = match.group(2).strip()
        if fname and content:
            files[fname] = content
    return files
