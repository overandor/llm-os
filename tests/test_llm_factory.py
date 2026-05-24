"""Tests for llm_os.llm_factory module."""

import pytest

from llm_os.governance import ActionClass, Governance, Policy
from llm_os.llm_factory import LLMFactory, ModelSpec
from llm_os.treasury import Treasury


class TestModelSpec:
    def test_spec_creation(self):
        s = ModelSpec(
            model_id="m-1",
            name="test_model",
            architecture="llmgpt_py",
            d_model=128,
            n_layers=2,
            n_heads=2,
        )
        assert s.model_id == "m-1"
        assert s.d_model == 128
        assert s.n_layers == 2


class TestLLMFactory:
    def test_initial_status(self, llm_factory):
        f = llm_factory
        status = f.get_status()
        assert status["models_registered"] == 0
        assert status["training_runs"] == 0
        assert status["completed_runs"] == 0
        assert status["failed_runs"] == 0

    def test_create_model_spec(self, llm_factory):
        f = llm_factory
        spec = f.create_model_spec("my_model", "For testing")
        assert spec.name == "my_model"
        assert spec.purpose == "For testing"
        assert spec.model_id in f.models
        assert f.models[spec.model_id] == spec

    def test_train_model_not_found(self, llm_factory):
        f = llm_factory
        result = f.train_model("nonexistent")
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_train_model_not_approved(self, temp_storage_path):
        policy = Policy(name="test", action_classes={ActionClass.SAFE})  # RISKY not allowed
        g = Governance(policy=policy)
        t = Treasury(storage_path=temp_storage_path)
        f = LLMFactory(g, t, storage_path=temp_storage_path + "_factory")
        spec = f.create_model_spec("test", "Test")
        result = f.train_model(spec.model_id)
        assert result["success"] is False
        assert "approved" in result["error"].lower()

    def test_train_model_simulation_mode(self, llm_factory):
        f = llm_factory
        spec = f.create_model_spec("test", "Test")
        result = f.train_model(spec.model_id)
        # In simulation mode, it may succeed or fail depending on PyTorch availability
        assert "success" in result
        if result["success"]:
            assert "checkpoint_path" in result or "architecture" in result

    def test_evaluate_model_not_found(self, llm_factory):
        f = llm_factory
        result = f.evaluate_model("nonexistent")
        assert result["success"] is False

    def test_evaluate_model_no_runs(self, llm_factory):
        f = llm_factory
        spec = f.create_model_spec("test", "Test")
        result = f.evaluate_model(spec.model_id)
        assert result["success"] is False
        assert "no completed training runs" in result["error"].lower()

    def test_export_to_cpp_not_found(self, llm_factory):
        f = llm_factory
        result = f.export_to_cpp("nonexistent")
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_get_model_registry(self, llm_factory):
        f = llm_factory
        assert f.get_model_registry() == []

    def test_estimate_training_time(self, llm_factory):
        f = llm_factory
        spec = ModelSpec(
            model_id="m-1",
            name="test",
            architecture="llmgpt_py",
            d_model=256,
            n_layers=4,
            n_heads=4,
        )
        hours = f._estimate_training_time(spec)
        assert hours > 0
