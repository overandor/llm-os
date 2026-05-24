"""Tests for llm_os.economic_engine module."""

import pytest

from llm_os.economic_engine import EconomicEngine, Opportunity, RevenueActivity
from llm_os.governance import ActionClass, Governance, Policy
from llm_os.treasury import Treasury


class TestOpportunity:
    def test_expected_profit(self):
        o = Opportunity(
            opportunity_id="test-1",
            activity=RevenueActivity.MARKETPLACE_BUILD,
            description="Build job",
            estimated_revenue_usd=100.0,
            estimated_cost_usd=30.0,
            confidence=0.8,
        )
        assert o.expected_profit == 70.0
        assert o.expected_roi == (70.0 / 30.0) * 100

    def test_expected_roi_infinite_when_no_cost(self):
        o = Opportunity(
            opportunity_id="test-2",
            activity=RevenueActivity.COMPUTE_RENTAL,
            description="Free compute",
            estimated_revenue_usd=10.0,
            estimated_cost_usd=0.0,
            confidence=0.5,
        )
        assert o.expected_roi == float("inf")


class TestEconomicEngine:
    def test_initial_status(self, economic_engine):
        e = economic_engine
        e.trading_enabled = False
        status = e.get_status()
        assert status["trading_enabled"] is False
        assert status["trading_running"] is False
        assert status["active_opportunities"] == 0

    def test_scan_opportunities_no_trading_keys(self, economic_engine):
        e = economic_engine
        e.trading_enabled = False
        opps = e.scan_opportunities()
        assert isinstance(opps, list)

    def test_scan_opportunities_with_trading_enabled(self, economic_engine):
        e = economic_engine
        e.treasury.balance_usd = 200.0
        e.treasury._persist()
        e.trading_enabled = True
        opps = e.scan_opportunities()
        assert isinstance(opps, list)

    def test_evaluate_opportunity_over_budget(self, economic_engine):
        e = economic_engine
        opp = Opportunity(
            opportunity_id="test",
            activity=RevenueActivity.MARKETPLACE_BUILD,
            description="Expensive job",
            estimated_revenue_usd=1000.0,
            estimated_cost_usd=500.0,
            confidence=0.9,
        )
        result = e.evaluate_opportunity(opp)
        assert result["decision"] == "reject"
        assert "budget" in result["reason"].lower()

    def test_evaluate_opportunity_low_roi(self, economic_engine):
        e = economic_engine
        e.treasury.balance_usd = 1000.0
        opp = Opportunity(
            opportunity_id="test",
            activity=RevenueActivity.COMPUTE_RENTAL,
            description="Low value",
            estimated_revenue_usd=1.0,
            estimated_cost_usd=5.0,
            confidence=0.3,
        )
        result = e.evaluate_opportunity(opp)
        assert result["decision"] == "reject"

    def test_evaluate_opportunity_accept(self, economic_engine):
        e = economic_engine
        e.treasury.balance_usd = 1000.0
        opp = Opportunity(
            opportunity_id="test",
            activity=RevenueActivity.MARKETPLACE_BUILD,
            description="Good job",
            estimated_revenue_usd=100.0,
            estimated_cost_usd=10.0,
            confidence=0.8,
        )
        result = e.evaluate_opportunity(opp)
        assert result["decision"] == "accept"
        assert "profit" in result["reason"].lower()

    def test_execute_opportunity_not_approved(self, temp_storage_path):
        policy = Policy(name="test", action_classes=set())  # No actions allowed
        g = Governance(policy=policy)
        t = Treasury(storage_path=temp_storage_path)
        e = EconomicEngine(g, t, storage_path=temp_storage_path + "_econ")
        opp = Opportunity(
            opportunity_id="test",
            activity=RevenueActivity.COMPUTE_RENTAL,
            description="Test",
            estimated_revenue_usd=10.0,
            estimated_cost_usd=1.0,
            confidence=0.5,
        )
        result = e.execute_opportunity(opp)
        assert result["success"] is False
        assert "approved" in result["error"].lower() or "not approved" in result["error"].lower()

    def test_stop_trading_when_not_running(self, economic_engine):
        e = economic_engine
        result = e.stop_trading()
        assert result["status"] == "trading_not_running"
