"""Tests for llm_os.governance module."""

import pytest

from llm_os.governance import (
    ActionClass,
    ActionRequest,
    ApprovalState,
    Governance,
    Policy,
)


class TestPolicy:
    def test_default_policy_is_conservative(self):
        p = Policy(name="default", action_classes={ActionClass.SAFE, ActionClass.STANDARD})
        assert p.simulation_mode is True
        assert p.allow_real_payments is False
        assert p.allow_production_deploy is False
        assert p.allow_self_modification is False
        assert p.daily_cost_limit_usd == 100.0
        assert p.single_action_cost_limit_usd == 50.0

    def test_action_class_allowed(self):
        p = Policy(name="test", action_classes={ActionClass.SAFE, ActionClass.STANDARD})
        assert p.is_allowed(ActionClass.SAFE) is True
        assert p.is_allowed(ActionClass.RISKY) is False

    def test_approval_required(self):
        p = Policy(
            name="test",
            action_classes={ActionClass.SAFE, ActionClass.STANDARD, ActionClass.CRITICAL},
            simulation_mode=False,
            require_human_approval_for={ActionClass.CRITICAL},
        )
        assert p.requires_approval(ActionClass.CRITICAL) is True
        assert p.requires_approval(ActionClass.STANDARD) is False

    def test_simulation_bypasses_approval(self):
        p = Policy(
            name="test",
            action_classes={ActionClass.SAFE, ActionClass.CRITICAL},
            simulation_mode=True,
            require_human_approval_for={ActionClass.CRITICAL},
        )
        assert p.requires_approval(ActionClass.CRITICAL) is False  # Bypassed in simulation


class TestGovernance:
    def test_request_safe_action_auto_approved(self):
        g = Governance()
        req = g.request_action(
            action_type="read_status",
            action_class=ActionClass.SAFE,
            description="Read system status",
            estimated_cost_usd=0.0,
            actor="test",
        )
        assert req.approval_state in (ApprovalState.APPROVED, ApprovalState.BYPASSED_SIMULATION)

    def test_request_over_cost_limit_rejected(self):
        g = Governance()
        req = g.request_action(
            action_type="expensive_op",
            action_class=ActionClass.STANDARD,
            description="Too expensive",
            estimated_cost_usd=9999.0,
            actor="test",
        )
        assert req.approval_state == ApprovalState.REJECTED

    def test_request_disallowed_action_class_rejected(self):
        policy = Policy(name="test", action_classes={ActionClass.SAFE})
        g = Governance(policy=policy)
        req = g.request_action(
            action_type="risky_op",
            action_class=ActionClass.RISKY,
            description="Risky op",
            estimated_cost_usd=1.0,
            actor="test",
        )
        assert req.approval_state == ApprovalState.REJECTED

    def test_human_approval_flow(self):
        policy = Policy(
            name="test",
            action_classes={ActionClass.SAFE, ActionClass.STANDARD, ActionClass.CRITICAL},
            simulation_mode=False,
            require_human_approval_for={ActionClass.CRITICAL},
        )
        g = Governance(policy=policy)
        req = g.request_action(
            action_type="critical_op",
            action_class=ActionClass.CRITICAL,
            description="Critical operation",
            estimated_cost_usd=1.0,
            actor="test",
        )
        assert req.approval_state == ApprovalState.PENDING
        assert req.request_id in g.pending_requests

        # Approve
        assert g.approve_request(req.request_id) is True
        assert req.approval_state == ApprovalState.APPROVED
        assert req.request_id in g.approved_requests

    def test_reject_request(self):
        policy = Policy(
            name="test",
            action_classes={ActionClass.SAFE, ActionClass.CRITICAL},
            simulation_mode=False,
            require_human_approval_for={ActionClass.CRITICAL},
        )
        g = Governance(policy=policy)
        req = g.request_action(
            action_type="critical_op",
            action_class=ActionClass.CRITICAL,
            description="Critical operation",
            estimated_cost_usd=1.0,
            actor="test",
        )
        assert g.reject_request(req.request_id, "too risky") is True
        assert req.approval_state == ApprovalState.REJECTED
        assert "too risky" in str(req.result)

    def test_halt_and_resume(self):
        g = Governance()
        g.halt("emergency")
        assert g.is_halted() is True

        req = g.request_action(
            action_type="safe_op",
            action_class=ActionClass.SAFE,
            description="Should be blocked",
            estimated_cost_usd=0.0,
            actor="test",
        )
        assert req.approval_state == ApprovalState.REJECTED
        assert "halted" in str(req.result).lower()

        g.resume()
        assert g.is_halted() is False

    def test_record_execution(self):
        g = Governance()
        req = g.request_action(
            action_type="safe_op",
            action_class=ActionClass.SAFE,
            description="Safe op",
            estimated_cost_usd=0.0,
            actor="test",
        )
        g.record_execution(req.request_id, {"status": "ok"}, actual_cost_usd=0.5)
        assert req.result == {"status": "ok"}

    def test_daily_spent_tracking(self):
        g = Governance()
        req = g.request_action(
            action_type="safe_op",
            action_class=ActionClass.SAFE,
            description="Safe op",
            estimated_cost_usd=0.0,
            actor="test",
        )
        g.record_execution(req.request_id, {"status": "ok"}, actual_cost_usd=5.0)
        status = g.get_status()
        assert status["daily_spent_usd"] == 5.0

    def test_status_fields(self):
        g = Governance()
        status = g.get_status()
        assert "policy" in status
        assert "halted" in status
        assert "daily_spent_usd" in status
        assert "daily_limit_usd" in status
        assert "pending_approvals" in status
