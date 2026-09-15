from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from backend.app.graph.workflow import invoke_new, resume
from backend.app.models import AgentDeployment, ApprovalRequest, EvalCase, WorkflowRun
from backend.app.schemas import ApprovalDecision, Principal, Rung


def trigger_run(db: Session, *, tenant_id: str, alert_id: str, rung: Rung | None = None) -> WorkflowRun:
    dep = (
        db.query(AgentDeployment)
        .filter_by(tenant_id=tenant_id, workflow_id="ransomware-isolate-restore")
        .one_or_none()
    )
    autonomy = rung or (dep.autonomy_rung if dep else "L2")
    run = WorkflowRun(
        id=f"EXR-{uuid.uuid4().hex[:6].upper()}",
        tenant_id=tenant_id,
        workflow_id="ransomware-isolate-restore",
        alert_id=alert_id,
        autonomy_rung=autonomy,
        status="running",
    )
    db.add(run)
    db.commit()
    invoke_new(
        {
            "run_id": run.id,
            "tenant_id": tenant_id,
            "alert_id": alert_id,
            "autonomy_rung": autonomy,
            "workflow_id": "ransomware-isolate-restore",
            "status": "running",
        }
    )
    db.refresh(run)
    return run


def decide(
    db: Session,
    *,
    principal: Principal,
    approval_id: str,
    body: ApprovalDecision,
) -> dict[str, Any]:
    req = db.get(ApprovalRequest, approval_id)
    if req is None or req.tenant_id != principal.tenant_id:
        raise LookupError("approval not found")
    if req.status != "pending":
        raise ValueError("already decided")
    req.status = body.decision
    req.decided_by = principal.user_id
    req.decision = body.decision
    req.reason = body.reason
    if body.decision == "reject":
        db.add(
            EvalCase(
                id=f"rej-{uuid.uuid4().hex[:10]}",
                tenant_id=principal.tenant_id,
                source="rejection",
                label="human_reject",
                payload={"approval_id": req.id, "reason": body.reason, "run_id": req.run_id},
            )
        )
    db.commit()
    result = resume(
        req.run_id,
        {"decision": body.decision, "user_id": principal.user_id, "reason": body.reason, "approval_id": req.id},
    )
    return {"approval_id": req.id, "run_id": req.run_id, "graph": result}
