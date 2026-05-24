"""Tests for llm_os.system_builder module."""

import pytest

from llm_os.governance import ActionClass, Governance, Policy
from llm_os.system_builder import BuildPlan, SystemBuilder
from llm_os.treasury import Treasury


class TestBuildPlan:
    def test_plan_creation(self):
        p = BuildPlan(
            plan_id="plan-1",
            description="Test plan",
            target_type="web_app",
            requirements=["fast", "secure"],
            estimated_cost_usd=5.0,
            estimated_time_hours=2.0,
            expected_revenue_usd=50.0,
        )
        assert p.plan_id == "plan-1"
        assert p.target_type == "web_app"


class TestSystemBuilder:
    def test_initial_status(self, system_builder):
        b = system_builder
        status = b.get_status()
        assert status["active_builds"] == 0
        assert status["build_history"] == 0

    def test_analyze_requirements_web_app(self, system_builder):
        b = system_builder
        plan = b.analyze_requirements({
            "type": "web_app",
            "description": "A web app",
            "requirements": ["responsive", "fast"],
            "budget_usd": 100.0,
        })
        assert plan.target_type == "web_app"
        assert plan.estimated_cost_usd > 0
        assert plan.estimated_time_hours > 0
        assert "html" in plan.tech_stack

    def test_analyze_requirements_api_service(self, system_builder):
        b = system_builder
        plan = b.analyze_requirements({
            "type": "api_service",
            "description": "An API",
            "requirements": ["REST", "auth"],
            "budget_usd": 200.0,
        })
        assert plan.target_type == "api_service"
        assert "fastapi" in plan.tech_stack

    def test_generate_code_api_service(self, system_builder):
        b = system_builder
        plan = b.analyze_requirements({
            "type": "api_service",
            "description": "Test API",
            "requirements": [],
            "budget_usd": 50.0,
        })
        result = b.generate_code(plan)
        assert result["success"] is True
        assert result["files_generated"] == 3
        assert "main.py" in result["files"]
        assert "requirements.txt" in result["files"]
        assert "Dockerfile" in result["files"]

    def test_generate_code_trading_bot(self, system_builder):
        b = system_builder
        plan = b.analyze_requirements({
            "type": "trading_bot",
            "description": "Test bot",
            "requirements": [],
            "budget_usd": 50.0,
        })
        result = b.generate_code(plan)
        assert result["success"] is True
        assert "bot.py" in result["files"]
        assert "config.json" in result["files"]

    def test_run_tests(self, system_builder):
        b = system_builder
        plan = b.analyze_requirements({
            "type": "api_service",
            "description": "Test API",
            "requirements": [],
            "budget_usd": 50.0,
        })
        b.generate_code(plan)
        test_result = b.run_tests(plan.plan_id)
        assert test_result["success"] is True
        assert test_result["tests_run"] > 0
        assert test_result["tests_passed"] > 0

    def test_run_tests_nonexistent_plan(self, system_builder):
        b = system_builder
        result = b.run_tests("nonexistent")
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_finalize_build(self, system_builder):
        b = system_builder
        plan = b.analyze_requirements({
            "type": "api_service",
            "description": "Test API",
            "requirements": [],
            "budget_usd": 50.0,
        })
        b.generate_code(plan)
        b.run_tests(plan.plan_id)
        result = b.finalize_build(plan.plan_id)
        assert result["success"] is True
        assert "bundle_hash" in result
        assert result["status"] == "ready_for_submission"

    def test_finalize_build_without_tests(self, system_builder):
        b = system_builder
        plan = b.analyze_requirements({
            "type": "api_service",
            "description": "Test API",
            "requirements": [],
            "budget_usd": 50.0,
        })
        b.generate_code(plan)
        # Don't run tests
        result = b.finalize_build(plan.plan_id)
        assert result["success"] is True

    def test_generate_code_unapproved(self, temp_storage_path):
        policy = Policy(name="test", action_classes={ActionClass.SAFE})  # STANDARD not allowed
        g = Governance(policy=policy)
        t = Treasury(storage_path=temp_storage_path)
        b = SystemBuilder(g, t, storage_path=temp_storage_path + "_builder")
        plan = b.analyze_requirements({
            "type": "api_service",
            "description": "Test API",
            "requirements": [],
            "budget_usd": 50.0,
        })
        result = b.generate_code(plan)
        assert result["success"] is False

    def test_build_history_tracking(self, system_builder):
        b = system_builder
        plan = b.analyze_requirements({
            "type": "api_service",
            "description": "Test API",
            "requirements": [],
            "budget_usd": 50.0,
        })
        b.generate_code(plan)
        b.run_tests(plan.plan_id)
        b.finalize_build(plan.plan_id)

        status = b.get_status()
        assert status["build_history"] == 1
