from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from backend.app.adapters import estate
from backend.app.models import ExecutionRecord
from backend.app.policy.engine import evaluate
from backend.app.schemas import ActionPlan, GuardrailConfig, Principal


def execute_plan(
    db: Session,
    *,
    tenant_id: str,
    run_id: str,
    plan: ActionPlan,
    principal: Principal | None,
    guardrails: GuardrailConfig | None = None,
) -> dict[str, Any]:
    """Only the execution gateway mutates the world. Re-checks policy first."""
    policy = evaluate(db, tenant_id=tenant_id, plan=plan, guardrails=guardrails)
    if not policy.passed:
        raise PermissionError("Execution denied — policy re-check failed (fail closed).")
    snapshots = []
    results = []
    for action in plan.actions:
        snap = estate.snapshot_endpoint(db, tenant_id, action.target_id)
        snapshots.append(snap)
        if action.type == "isolate":
            results.append({"type": "isolate", **estate.isolate(db, tenant_id, action.target_id)})
        elif action.type == "restore":
            results.append({"type": "restore", **estate.restore(db, tenant_id, action.target_id, action.backup_id or "")})
        elif action.type == "script":
            raise PermissionError("Free-form scripts are not executed; adapters only.")
    record = ExecutionRecord(
        id=f"ex-{uuid.uuid4().hex[:10]}",
        tenant_id=tenant_id,
        run_id=run_id,
        snapshot_id=snapshots[0]["endpoint_id"] + "-snap" if snapshots else "none",
        actions=[{"snapshot": s, "result": r} for s, r in zip(snapshots, results)],
        verify_status="ok",
    )
    db.add(record)
    db.flush()
    return {
        "record_id": record.id,
        "snapshots": snapshots,
        "results": results,
        "verify_status": "ok",
        "authoriser": principal.user_id if principal else None,
    }


def rollback(db: Session, *, tenant_id: str, run_id: str) -> dict[str, Any]:
    rec = db.query(ExecutionRecord).filter_by(tenant_id=tenant_id, run_id=run_id).order_by(ExecutionRecord.created_at.desc()).first()
    if rec is None:
        raise ValueError("No execution record to roll back")
    for item in rec.actions:
        estate.rollback_snapshot(db, tenant_id, item["snapshot"])
    rec.rolled_back = True
    rec.verify_status = "rolled_back"
    return {"ok": True, "record_id": rec.id}
