"""Tests for llm_os.treasury module."""

import os
import tempfile

import pytest

from llm_os.treasury import LedgerEntryType, Treasury


class TestTreasury:
    def test_initial_balance(self, temp_storage_path):
        t = Treasury(storage_path=temp_storage_path, starting_balance_usd=100.0)
        assert t.balance_usd == 100.0

    def test_record_cost_reduces_balance(self, temp_storage_path):
        t = Treasury(storage_path=temp_storage_path, starting_balance_usd=100.0)
        t.record_cost("test", "activity", 10.0, "Test cost")
        assert t.balance_usd == 90.0

    def test_record_revenue_increases_balance(self, temp_storage_path):
        t = Treasury(storage_path=temp_storage_path, starting_balance_usd=100.0)
        t.record_revenue("test", "activity", 25.0, "Test revenue")
        assert t.balance_usd == 125.0

    def test_record_estimate_does_not_affect_balance(self, temp_storage_path):
        t = Treasury(storage_path=temp_storage_path, starting_balance_usd=100.0)
        t.record_estimate("test", "activity", 50.0, "Test estimate")
        assert t.balance_usd == 100.0
        assert len(t.ledger) == 1
        assert t.ledger[0].confirmed is False

    def test_pnl_calculation(self, temp_storage_path):
        t = Treasury(storage_path=temp_storage_path, starting_balance_usd=0.0)
        t.record_revenue("test", "sales", 100.0, "Sales")
        t.record_cost("test", "infra", 30.0, "Infrastructure")
        t.record_cost("test", "api", 20.0, "API calls")

        pnl = t.get_pnl(subsystem="test", days=7)
        assert pnl["revenue_usd"] == 100.0
        assert pnl["costs_usd"] == 50.0
        assert pnl["profit_usd"] == 50.0
        assert pnl["roi_percent"] == 100.0

    def test_pnl_no_costs(self, temp_storage_path):
        t = Treasury(storage_path=temp_storage_path, starting_balance_usd=0.0)
        pnl = t.get_pnl(days=7)
        assert pnl["profit_usd"] == 0.0
        assert pnl["roi_percent"] == 0.0

    def test_subsystem_breakdown(self, temp_storage_path):
        t = Treasury(storage_path=temp_storage_path, starting_balance_usd=0.0)
        t.record_revenue("trading", "profit", 50.0, "Trading profit")
        t.record_cost("trading", "loss", 10.0, "Trading loss")
        t.record_revenue("marketplace", "sale", 30.0, "Build sale")

        breakdown = t.get_subsystem_breakdown(days=7)
        assert "trading" in breakdown
        assert "marketplace" in breakdown
        assert breakdown["trading"]["profit_usd"] == 40.0
        assert breakdown["marketplace"]["profit_usd"] == 30.0

    def test_allocate_to_reserve(self, temp_storage_path):
        t = Treasury(storage_path=temp_storage_path, starting_balance_usd=100.0)
        assert t.allocate_to_reserve("risk", 20.0) is True
        assert t.balance_usd == 80.0
        assert t.reserves_usd["risk"] == 20.0

    def test_allocate_over_balance_fails(self, temp_storage_path):
        t = Treasury(storage_path=temp_storage_path, starting_balance_usd=10.0)
        assert t.allocate_to_reserve("risk", 20.0) is False
        assert t.balance_usd == 10.0

    def test_budget_for_profitable_subsystem(self, temp_storage_path):
        t = Treasury(storage_path=temp_storage_path, starting_balance_usd=100.0)
        t.record_revenue("trading", "profit", 100.0, "Profit")
        t.record_cost("trading", "cost", 10.0, "Cost")

        budget = t.get_budget_for("trading")
        assert budget > 0.0
        assert budget <= t.balance_usd

    def test_budget_for_unprofitable_subsystem(self, temp_storage_path):
        t = Treasury(storage_path=temp_storage_path, starting_balance_usd=100.0)
        t.record_cost("factory", "training", 50.0, "Training cost")

        budget = t.get_budget_for("factory")
        assert budget <= 10.0  # Minimal budget for unprofitable subsystem

    def test_get_status(self, temp_storage_path):
        t = Treasury(storage_path=temp_storage_path, starting_balance_usd=100.0)
        status = t.get_status()
        assert "balance_usd" in status
        assert "runway_days" in status
        assert "pnl_7d" in status
        assert "pnl_30d" in status

    def test_persistence(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as f:
            path = f.name
        try:
            t = Treasury(storage_path=path, starting_balance_usd=50.0)
            t.record_cost("test", "activity", 5.0, "Test")
            del t

            t2 = Treasury(storage_path=path, starting_balance_usd=999.0)
            assert t2.balance_usd == 45.0  # Loaded from file
        finally:
            os.unlink(path)
