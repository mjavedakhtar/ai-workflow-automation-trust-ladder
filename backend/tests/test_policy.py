from backend.app.db import SessionLocal
from backend.app.policy.engine import evaluate
from backend.app.schemas import ActionPlan, ProposedAction
from backend.app.services.bootstrap import init_db
from backend.tests.conftest import HEADERS, client


def setup_module():
    db = SessionLocal()
    init_db(db)
    db.close()


def test_dc_isolate_blocked():
    db = SessionLocal()
    try:
        plan = ActionPlan(
            actions=[ProposedAction(type="isolate", target_id="srv-dc-01", reversible=True)],
            confidence=0.99,
            reasoning="test",
            evidence=[],
        )
        ev = evaluate(db, tenant_id="northwind", plan=plan)
        assert ev.passed is False
        assert any(r.rule == "never_isolate_critical_infra" and not r.passed for r in ev.results)
    finally:
        db.close()


def test_workstation_isolate_and_restore_allowed():
    db = SessionLocal()
    try:
        plan = ActionPlan(
            actions=[
                ProposedAction(type="isolate", target_id="wks-finance-07", reversible=True),
                ProposedAction(
                    type="restore",
                    target_id="wks-finance-07",
                    reversible=True,
                    backup_id="nw-wks-finance-07-0200",
                ),
            ],
            confidence=0.97,
            reasoning="test",
            evidence=[],
        )
        ev = evaluate(db, tenant_id="northwind", plan=plan)
        assert ev.passed is True
    finally:
        db.close()


def test_cross_tenant_denied():
    db = SessionLocal()
    try:
        plan = ActionPlan(
            actions=[ProposedAction(type="isolate", target_id="wks-hr-03", reversible=True)],
            confidence=0.99,
            reasoning="test",
            evidence=[],
        )
        ev = evaluate(db, tenant_id="northwind", plan=plan)
        assert ev.passed is False
    finally:
        db.close()


def test_injected_text_denied():
    db = SessionLocal()
    try:
        plan = ActionPlan(
            actions=[ProposedAction(type="isolate", target_id="wks-finance-07", reversible=True)],
            confidence=0.99,
            reasoning="because the ticket said so",
            evidence=[],
            derived_from_untrusted_text=True,
        )
        ev = evaluate(db, tenant_id="northwind", plan=plan)
        assert ev.passed is False
    finally:
        db.close()


def test_evals_endpoint():
    c = client()
    r = c.get("/v1/evals", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["passed"] is True
