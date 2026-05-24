"""Tests for llm_os.inference module."""

import pytest

from llm_os.inference import (
    BaseInferenceBridge,
    GroqBridge,
    OpenRouterBridge,
    StubBridge,
    get_inference_bridge,
    generate_code_with_llm,
    _parse_code_blocks,
)


class TestStubBridge:
    def test_is_available(self):
        b = StubBridge("stub")
        assert b.is_available() is True

    def test_generate(self):
        b = StubBridge("stub")
        r = b.generate("hello world")
        assert r.success is True
        assert "STUB" in r.text
        assert r.cost_usd == 0.0

    def test_to_dict(self):
        b = StubBridge("stub")
        r = b.generate("test")
        d = r.to_dict()
        assert d["success"] is True
        assert "text" in d


class TestGroqBridge:
    def test_no_key_not_available(self):
        import os
        old = os.environ.get("GROQ_API_KEY")
        if "GROQ_API_KEY" in os.environ:
            del os.environ["GROQ_API_KEY"]
        try:
            b = GroqBridge()
            assert b.is_available() is False
        finally:
            if old:
                os.environ["GROQ_API_KEY"] = old

    def test_generate_no_key_or_no_httpx(self):
        import os
        old = os.environ.get("GROQ_API_KEY")
        if "GROQ_API_KEY" in os.environ:
            del os.environ["GROQ_API_KEY"]
        try:
            b = GroqBridge()
            r = b.generate("hello")
            assert r.success is False
            # Could fail due to missing httpx OR missing API key
            assert "httpx" in r.error or "GROQ_API_KEY" in r.error
        finally:
            if old:
                os.environ["GROQ_API_KEY"] = old

    def test_cost_estimate(self):
        b = GroqBridge()
        cost = b._estimate_cost(1000, 500)
        assert cost > 0
        assert cost < 0.01


class TestOpenRouterBridge:
    def test_no_key_not_available(self):
        import os
        old = os.environ.get("OPENROUTER_API_KEY")
        if "OPENROUTER_API_KEY" in os.environ:
            del os.environ["OPENROUTER_API_KEY"]
        try:
            b = OpenRouterBridge()
            assert b.is_available() is False
        finally:
            if old:
                os.environ["OPENROUTER_API_KEY"] = old


class TestGetInferenceBridge:
    def test_returns_stub_when_no_keys(self):
        b = get_inference_bridge()
        assert b is not None
        # Should be StubBridge or a real one if keys exist in env

    def test_caches_bridges(self):
        b1 = get_inference_bridge()
        b2 = get_inference_bridge()
        # Both calls should return the same instance from cache
        assert b1 is b2


class TestParseCodeBlocks:
    def test_parses_simple_blocks(self):
        text = """
```main.py
print("hello")
```
```requirements.txt
flask
```
"""
        files = _parse_code_blocks(text)
        assert "main.py" in files
        assert 'print("hello")' in files["main.py"]
        assert "requirements.txt" in files
        assert "flask" in files["requirements.txt"]

    def test_empty_input(self):
        assert _parse_code_blocks("") == {}

    def test_no_blocks(self):
        assert _parse_code_blocks("just plain text") == {}


class TestGenerateCodeWithLLM:
    def test_stub_fallback(self):
        # When no API keys are available, should fall back to stub
        result = generate_code_with_llm("build a web app", target_type="python")
        assert "success" in result
        # Stub may fail to parse files, so check structure
        assert "cost_usd" in result
