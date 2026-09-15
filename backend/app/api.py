from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app import ledger
from backend.app.adapters.estate import get_alert, load_estate_file
from backend.app.config import get_settings
from backend.app.db import get_db
from backend.app.models import AgentDeployment, ApprovalRequest, ControlPlane, LedgerEntry, WorkflowRun
from backend.app.policy.linter import lint
from backend.app.rbac import get_principal, require
from backend.app.schemas import (
    ActivationRequest,
    ApprovalDecision,
    KillSwitchRequest,
    LintRequest,
    Principal,
    RunOut,
    TriggerRunRequest,
)
from backend.app.services import evals as eval_service
from backend.app.services.execution import rollback
from backend.app.services.runs import decide, trigger_run

router = APIRouter(prefix="/v1")


@router.get("/health")
def health():
    s = get_settings()
    return {
        "ok": True,
        "llm": "gemini" if s.use_gemini else "mock",
        "model": s.gemini_model if s.use_gemini else None,
    }


@router.get("/estate/alerts")
def list_alerts(principal: Principal = Depends(get_principal)):
    require(principal, "read")
    alerts = [a for a in load_estate_file()["alerts"] if a["tenant_id"] == principal.tenant_id]
    return {"alerts": alerts}


@router.post("/runs", response_model=RunOut)
def create_run(body: TriggerRunRequest, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require(principal, "trigger")
    tenant_id = body.tenant_id or principal.tenant_id
    if tenant_id != principal.tenant_id and principal.role not in {"owner", "admin"}:
        raise HTTPException(403, "Cannot trigger for another tenant")
    alert = get_alert(body.alert_id)
    if alert is None or alert["tenant_id"] != tenant_id:
        raise HTTPException(404, "Alert not found in tenant")
    run = trigger_run(db, tenant_id=tenant_id, alert_id=body.alert_id, rung=body.autonomy_rung)
    db.refresh(run)
    return run


@router.get("/runs", response_model=list[RunOut])
def list_runs(db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require(principal, "read")
    rows = db.scalars(
        select(WorkflowRun).where(WorkflowRun.tenant_id == principal.tenant_id).order_by(WorkflowRun.created_at.desc())
    ).all()
    return rows


@router.get("/runs/{run_id}", response_model=RunOut)
def get_run(run_id: str, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require(principal, "read")
    run = db.get(WorkflowRun, run_id)
    if run is None or run.tenant_id != principal.tenant_id:
        raise HTTPException(404, "Run not found")
    return run


@router.get("/oversight")
def oversight(db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require(principal, "read")
    rows = db.scalars(
        select(ApprovalRequest)
        .where(ApprovalRequest.tenant_id == principal.tenant_id, ApprovalRequest.status == "pending")
        .order_by(ApprovalRequest.created_at.desc())
    ).all()
    items = []
    for r in rows:
        plan = (r.payload or {}).get("action_plan") or {}
        cls = (r.payload or {}).get("classification") or {}
        policy = (r.payload or {}).get("policy_eval") or {}
        items.append(
            {
                "id": r.id,
                "run_id": r.run_id,
                "kind": r.kind,
                "status": r.status,
                "action": _action_label(r.kind, plan, cls),
                "client": principal.tenant_id,
                "conf": (plan.get("confidence") if plan else None) or cls.get("confidence"),
                "reasoning": plan.get("reasoning") or cls.get("reasoning"),
                "evidence": plan.get("evidence") or cls.get("evidence") or [],
                "guards": policy.get("results") or [],
                "passed": policy.get("passed"),
                "payload": r.payload,
            }
        )
    return {"items": items, "can_approve": principal.role in {"admin", "tech"}}


def _action_label(kind: str, plan: dict, cls: dict) -> str:
    if kind == "triage":
        return f"Classify {cls.get('endpoint_id')} as {cls.get('verdict')}"
    actions = plan.get("actions") or []
    if actions:
        return ", ".join(f"{a.get('type')} {a.get('target_id')}" for a in actions)
    return kind


@router.post("/oversight/{approval_id}/decide")
def decide_item(
    approval_id: str,
    body: ApprovalDecision,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
):
    require(principal, "approve")
    try:
        return decide(db, principal=principal, approval_id=approval_id, body=body)
    except LookupError:
        raise HTTPException(404, "Approval not found") from None
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None


@router.get("/ledger")
def list_ledger(run_id: str | None = None, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require(principal, "read")
    q = select(LedgerEntry).where(LedgerEntry.tenant_id == principal.tenant_id).order_by(LedgerEntry.id.asc())
    if run_id:
        q = q.where(LedgerEntry.run_id == run_id)
    rows = db.scalars(q).all()
    return {
        "intact": ledger.verify_chain(db, principal.tenant_id),
        "entries": [
            {
                "id": e.id,
                "run_id": e.run_id,
                "event_type": e.event_type,
                "payload": e.payload,
                "prev_hash": e.prev_hash,
                "entry_hash": e.entry_hash,
                "signature": e.signature,
                "created_at": e.created_at.isoformat(),
            }
            for e in rows
        ],
    }


@router.post("/runs/{run_id}/rollback")
def rollback_run(run_id: str, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require(principal, "rollback")
    run = db.get(WorkflowRun, run_id)
    if run is None or run.tenant_id != principal.tenant_id:
        raise HTTPException(404, "Run not found")
    try:
        result = rollback(db, tenant_id=principal.tenant_id, run_id=run_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from None
    ledger.append(db, tenant_id=principal.tenant_id, run_id=run_id, event_type="rollback", payload=result)
    run.status = "rolled_back"
    return result


@router.post("/policy/lint")
def lint_script(body: LintRequest, principal: Principal = Depends(get_principal)):
    require(principal, "read")
    return lint(body.script)


@router.post("/activation")
def activate(body: ActivationRequest, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require(principal, "activate")
    tenant_id = body.tenant_id or principal.tenant_id
    dep = (
        db.query(AgentDeployment)
        .filter_by(tenant_id=tenant_id, workflow_id="ransomware-isolate-restore")
        .one_or_none()
    )
    if dep is None:
        raise HTTPException(404, "Deployment missing")
    dep.autonomy_rung = body.autonomy_rung
    dep.guardrails = body.guardrails.model_dump()
    dep.status = "canary" if body.canary else "active"
    dep.paused = False
    return {"ok": True, "tenant_id": tenant_id, "rung": dep.autonomy_rung, "status": dep.status}


@router.post("/activation/dry-run")
def activation_dry_run(db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require(principal, "activate")
    return eval_service.dry_run(db, principal.tenant_id)


@router.get("/evals")
def evals(db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require(principal, "read")
    return eval_service.run_eval_suite(db)


@router.post("/kill-switch")
def kill_switch(body: KillSwitchRequest, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    cp = db.query(ControlPlane).first()
    if cp is None:
        cp = ControlPlane(global_pause=False, paused_workflows=[])
        db.add(cp)
        db.flush()
    if body.scope == "global":
        require(principal, "kill_global")
        cp.global_pause = body.paused
    else:
        require(principal, "kill_scoped")
        paused = list(cp.paused_workflows or [])
        if body.paused and body.workflow_id not in paused:
            paused.append(body.workflow_id)
        if not body.paused:
            paused = [w for w in paused if w != body.workflow_id]
        cp.paused_workflows = paused
    ledger.append(
        db,
        tenant_id=principal.tenant_id,
        event_type="kill_switch",
        payload={"scope": body.scope, "paused": body.paused, "by": principal.user_id},
    )
    return {"global_pause": cp.global_pause, "paused_workflows": cp.paused_workflows}


@router.get("/control-plane")
def control_plane(db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    require(principal, "read")
    cp = db.query(ControlPlane).first()
    return {
        "global_pause": bool(cp and cp.global_pause),
        "paused_workflows": (cp.paused_workflows if cp else []),
        "role": principal.role,
        "tenant_id": principal.tenant_id,
        "roi_visible": principal.role in {"owner", "admin"},
    }
