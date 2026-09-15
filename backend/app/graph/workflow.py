from __future__ import annotations

import uuid
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from sqlalchemy.orm import Session

from backend.app import ledger
from backend.app.adapters.estate import get_alert, psa_close
from backend.app.db import SessionLocal
from backend.app.graph.llm import classify, plan
from backend.app.graph.state import GraphState
from backend.app.models import AgentDeployment, ApprovalRequest, ControlPlane, WorkflowRun
from backend.app.policy.engine import evaluate
from backend.app.schemas import ActionPlan, GuardrailConfig
from backend.app.services.execution import execute_plan

WORKFLOW_ID = "ransomware-isolate-restore"


def _db() -> Session:
    return SessionLocal()


def _run(db: Session, run_id: str) -> WorkflowRun:
    run = db.get(WorkflowRun, run_id)
    if run is None:
        raise RuntimeError("run missing")
    return run


def _paused(db: Session, workflow_id: str) -> bool:
    cp = db.query(ControlPlane).first()
    if cp is None:
        return False
    return bool(cp.global_pause or workflow_id in (cp.paused_workflows or []))


def _guardrails(db: Session, tenant_id: str) -> GuardrailConfig:
    dep = (
        db.query(AgentDeployment)
        .filter_by(tenant_id=tenant_id, workflow_id=WORKFLOW_ID)
        .one_or_none()
    )
    if dep and dep.guardrails:
        return GuardrailConfig.model_validate(dep.guardrails)
    return GuardrailConfig()


def ingest(state: GraphState) -> GraphState:
    db = _db()
    try:
        run = _run(db, state["run_id"])
        if _paused(db, state.get("workflow_id") or WORKFLOW_ID):
            run.status = "paused"
            run.current_node = "ingest"
            run.error = "Kill switch engaged — fail closed."
            ledger.append(db, tenant_id=run.tenant_id, run_id=run.id, event_type="paused", payload={"reason": "kill_switch"})
            db.commit()
            return {**state, "status": "paused", "current_node": "ingest", "error": run.error}
        alert = get_alert(state["alert_id"])
        if alert is None or alert["tenant_id"] != state["tenant_id"]:
            run.status = "failed"
            run.error = "Unknown or cross-tenant alert"
            db.commit()
            return {**state, "status": "failed", "error": run.error}
        run.current_node = "triage"
        db.commit()
        return {**state, "status": "running", "current_node": "triage", "error": None}
    finally:
        db.close()


def triage(state: GraphState) -> GraphState:
    db = _db()
    try:
        run = _run(db, state["run_id"])
        alert = get_alert(state["alert_id"])
        assert alert is not None
        result = classify(db, tenant_id=run.tenant_id, run_id=run.id, alert=alert)
        run.classification = result.model_dump()
        run.current_node = "route_triage"
        ledger.append(
            db,
            tenant_id=run.tenant_id,
            run_id=run.id,
            event_type="triage",
            payload=result.model_dump(),
        )
        db.commit()
        return {**state, "classification": result.model_dump(), "current_node": "route_triage"}
    finally:
        db.close()


def route_triage(state: GraphState) -> str:
    verdict = (state.get("classification") or {}).get("verdict")
    if verdict == "true_positive":
        return "remediate"
    if verdict == "false_positive":
        return "close_fp"
    return "triage_hitl"


def close_fp(state: GraphState) -> GraphState:
    db = _db()
    try:
        run = _run(db, state["run_id"])
        run.status = "closed_false_positive"
        run.current_node = "end"
        psa_close(state["alert_id"], "Closed as false positive by Triage Agent")
        ledger.append(db, tenant_id=run.tenant_id, run_id=run.id, event_type="close", payload={"verdict": "false_positive"})
        db.commit()
        return {**state, "status": "closed_false_positive", "current_node": "end"}
    finally:
        db.close()


def _open_approval(db: Session, run: WorkflowRun, kind: str, payload: dict[str, Any]) -> ApprovalRequest:
    req = ApprovalRequest(
        id=f"ap-{uuid.uuid4().hex[:10]}",
        tenant_id=run.tenant_id,
        run_id=run.id,
        kind=kind,
        payload=payload,
    )
    db.add(req)
    db.flush()
    return req


def triage_hitl(state: GraphState) -> GraphState:
    db = _db()
    try:
        run = _run(db, state["run_id"])
        payload = {
            "kind": "triage",
            "classification": state.get("classification"),
            "alert_id": state["alert_id"],
        }
        req = _open_approval(db, run, "triage", payload)
        run.status = "awaiting_human"
        run.current_node = "triage_hitl"
        ledger.append(db, tenant_id=run.tenant_id, run_id=run.id, event_type="hitl", payload={"kind": "triage", "approval_id": req.id})
        db.commit()
        decision = interrupt({"approval_id": req.id, **payload})
        run = _run(db, state["run_id"])
        run.approval = decision
        run.status = "running"
        db.commit()
        return {**state, "approval": decision, "status": "running"}
    finally:
        db.close()


def remediate(state: GraphState) -> GraphState:
    db = _db()
    try:
        run = _run(db, state["run_id"])
        from backend.app.schemas import Classification

        cls = Classification.model_validate(state["classification"])
        action_plan = plan(db, tenant_id=run.tenant_id, run_id=run.id, classification=cls)
        run.action_plan = action_plan.model_dump()
        run.current_node = "policy"
        ledger.append(db, tenant_id=run.tenant_id, run_id=run.id, event_type="action_plan", payload=action_plan.model_dump())
        db.commit()
        return {**state, "action_plan": action_plan.model_dump(), "current_node": "policy"}
    finally:
        db.close()


def policy_gate(state: GraphState) -> GraphState:
    db = _db()
    try:
        run = _run(db, state["run_id"])
        action_plan = ActionPlan.model_validate(state["action_plan"])
        evaluation = evaluate(db, tenant_id=run.tenant_id, plan=action_plan, guardrails=_guardrails(db, run.tenant_id))
        run.policy_eval = evaluation.model_dump()
        run.current_node = "rung_gate"
        ledger.append(db, tenant_id=run.tenant_id, run_id=run.id, event_type="policy", payload=evaluation.model_dump())
        db.commit()
        return {**state, "policy_eval": evaluation.model_dump(), "current_node": "rung_gate"}
    finally:
        db.close()


def rung_route(state: GraphState) -> str:
    passed = (state.get("policy_eval") or {}).get("passed")
    if not passed:
        return "policy_hitl"
    rung = state.get("autonomy_rung") or "L2"
    if rung in {"L0", "L1"}:
        return "record_only"
    if rung == "L3":
        return "execute"
    return "remediation_hitl"


def record_only(state: GraphState) -> GraphState:
    db = _db()
    try:
        run = _run(db, state["run_id"])
        run.status = "shadow" if run.autonomy_rung == "L0" else "suggested"
        run.current_node = "end"
        ledger.append(db, tenant_id=run.tenant_id, run_id=run.id, event_type="no_execute", payload={"rung": run.autonomy_rung})
        db.commit()
        return {**state, "status": run.status, "current_node": "end"}
    finally:
        db.close()


def policy_hitl(state: GraphState) -> GraphState:
    db = _db()
    try:
        run = _run(db, state["run_id"])
        payload = {
            "kind": "policy_block",
            "action_plan": state.get("action_plan"),
            "policy_eval": state.get("policy_eval"),
            "classification": state.get("classification"),
        }
        req = _open_approval(db, run, "policy_block", payload)
        run.status = "awaiting_human"
        run.current_node = "policy_hitl"
        db.commit()
        decision = interrupt({"approval_id": req.id, **payload})
        run = _run(db, state["run_id"])
        run.approval = decision
        if decision.get("decision") != "approve":
            run.status = "blocked"
            run.current_node = "end"
            db.commit()
            return {**state, "approval": decision, "status": "blocked", "current_node": "end"}
        run.status = "running"
        db.commit()
        return {**state, "approval": decision, "status": "running"}
    finally:
        db.close()


def remediation_hitl(state: GraphState) -> GraphState:
    db = _db()
    try:
        run = _run(db, state["run_id"])
        payload = {
            "kind": "remediation",
            "action_plan": state.get("action_plan"),
            "policy_eval": state.get("policy_eval"),
            "classification": state.get("classification"),
        }
        req = _open_approval(db, run, "remediation", payload)
        run.status = "awaiting_human"
        run.current_node = "remediation_hitl"
        db.commit()
        decision = interrupt({"approval_id": req.id, **payload})
        run = _run(db, state["run_id"])
        run.approval = decision
        if decision.get("decision") != "approve":
            run.status = "rejected" if decision.get("decision") == "reject" else "escalated"
            run.current_node = "end"
            db.commit()
            return {**state, "approval": decision, "status": run.status, "current_node": "end"}
        run.status = "running"
        db.commit()
        return {**state, "approval": decision, "status": "running"}
    finally:
        db.close()


def execute_node(state: GraphState) -> GraphState:
    db = _db()
    try:
        run = _run(db, state["run_id"])
        if _paused(db, WORKFLOW_ID):
            run.status = "paused"
            run.error = "Kill switch engaged at execution"
            db.commit()
            return {**state, "status": "paused", "error": run.error}
        from backend.app.schemas import Principal

        authoriser = (state.get("approval") or {}).get("user_id") or "system-l3"
        principal = Principal(user_id=authoriser, role="admin", tenant_id=run.tenant_id)
        action_plan = ActionPlan.model_validate(state["action_plan"])
        result = execute_plan(
            db,
            tenant_id=run.tenant_id,
            run_id=run.id,
            plan=action_plan,
            principal=principal,
            guardrails=_guardrails(db, run.tenant_id),
        )
        run.execution = result
        run.status = "executed"
        run.current_node = "close"
        ledger.append(db, tenant_id=run.tenant_id, run_id=run.id, event_type="execution", payload=result)
        db.commit()
        return {**state, "execution": result, "status": "executed", "current_node": "close"}
    except Exception as exc:
        db.rollback()
        run = _run(db, state["run_id"])
        run.status = "failed"
        run.error = str(exc)
        db.commit()
        return {**state, "status": "failed", "error": str(exc)}
    finally:
        db.close()


def close_node(state: GraphState) -> GraphState:
    db = _db()
    try:
        run = _run(db, state["run_id"])
        psa_close(state["alert_id"], "Ticket auto-resolved after isolate+restore")
        run.status = "closed"
        run.current_node = "end"
        ledger.append(db, tenant_id=run.tenant_id, run_id=run.id, event_type="close", payload={"psa": True})
        db.commit()
        return {**state, "status": "closed", "current_node": "end"}
    finally:
        db.close()


def build_graph(checkpointer: Any | None = None):
    g = StateGraph(GraphState)
    g.add_node("ingest", ingest)
    g.add_node("triage", triage)
    g.add_node("close_fp", close_fp)
    g.add_node("triage_hitl", triage_hitl)
    g.add_node("remediate", remediate)
    g.add_node("policy_gate", policy_gate)
    g.add_node("record_only", record_only)
    g.add_node("policy_hitl", policy_hitl)
    g.add_node("remediation_hitl", remediation_hitl)
    g.add_node("execute", execute_node)
    g.add_node("close", close_node)

    g.add_edge(START, "ingest")
    g.add_conditional_edges(
        "ingest",
        lambda s: "triage" if s.get("status") != "paused" and s.get("status") != "failed" else "end",
        {"triage": "triage", "end": END},
    )
    g.add_conditional_edges("triage", route_triage, {"remediate": "remediate", "close_fp": "close_fp", "triage_hitl": "triage_hitl"})
    g.add_edge("close_fp", END)
    g.add_edge("triage_hitl", END)
    g.add_edge("remediate", "policy_gate")
    g.add_conditional_edges(
        "policy_gate",
        rung_route,
        {"policy_hitl": "policy_hitl", "record_only": "record_only", "execute": "execute", "remediation_hitl": "remediation_hitl"},
    )
    g.add_edge("record_only", END)
    g.add_conditional_edges(
        "policy_hitl",
        lambda s: "execute" if (s.get("approval") or {}).get("decision") == "approve" else "end",
        {"execute": "execute", "end": END},
    )
    g.add_conditional_edges(
        "remediation_hitl",
        lambda s: "execute" if (s.get("approval") or {}).get("decision") == "approve" else "end",
        {"execute": "execute", "end": END},
    )
    g.add_edge("execute", "close")
    g.add_edge("close", END)
    return g.compile(checkpointer=checkpointer or MemorySaver())


_GRAPH = None


def get_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = _compile()
    return _GRAPH


def _compile():
    from pathlib import Path

    from backend.app.config import get_settings

    settings = get_settings()
    path = Path(settings.checkpoint_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
        import sqlite3

        conn = sqlite3.connect(str(path), check_same_thread=False)
        return build_graph(SqliteSaver(conn))
    except Exception:
        return build_graph(MemorySaver())


def invoke_new(state: GraphState) -> dict[str, Any]:
    graph = get_graph()
    config = {"configurable": {"thread_id": state["run_id"]}}
    try:
        return graph.invoke(state, config)
    except Exception as exc:
        if exc.__class__.__name__ in {"GraphInterrupt", "NodeInterrupt"}:
            snap = graph.get_state(config)
            return dict(snap.values)
        raise


def resume(run_id: str, decision: dict[str, Any]) -> dict[str, Any]:
    graph = get_graph()
    config = {"configurable": {"thread_id": run_id}}
    try:
        return graph.invoke(Command(resume=decision), config)
    except Exception as exc:
        if exc.__class__.__name__ in {"GraphInterrupt", "NodeInterrupt"}:
            snap = graph.get_state(config)
            return dict(snap.values)
        raise
