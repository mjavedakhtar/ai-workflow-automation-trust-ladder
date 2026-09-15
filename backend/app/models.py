from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db import Base


def _now() -> datetime:
    return datetime.utcnow()


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    risk_tier: Mapped[str] = mapped_column(String(32), default="standard")
    compliance: Mapped[list[str]] = mapped_column(JSON, default=list)


class Endpoint(Base):
    __tablename__ = "endpoints"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    hostname: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(64), default="workstation")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    isolated: Mapped[bool] = mapped_column(Boolean, default=False)
    health: Mapped[str] = mapped_column(String(32), default="healthy")


class Backup(Base):
    __tablename__ = "backups"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    endpoint_id: Mapped[str] = mapped_column(ForeignKey("endpoints.id"), index=True)
    taken_at: Mapped[datetime] = mapped_column(DateTime)
    integrity_verified: Mapped[bool] = mapped_column(Boolean, default=True)
    encrypted: Mapped[bool] = mapped_column(Boolean, default=False)
    age_hours: Mapped[float] = mapped_column(Float, default=0)


class AgentDeployment(Base):
    __tablename__ = "agent_deployments"
    __table_args__ = (UniqueConstraint("tenant_id", "workflow_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    workflow_id: Mapped[str] = mapped_column(String(64), default="ransomware-isolate-restore")
    autonomy_rung: Mapped[str] = mapped_column(String(8), default="L2")
    status: Mapped[str] = mapped_column(String(32), default="canary")
    scope: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    guardrails: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    paused: Mapped[bool] = mapped_column(Boolean, default=False)


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    workflow_id: Mapped[str] = mapped_column(String(64))
    alert_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="running")
    current_node: Mapped[str] = mapped_column(String(64), default="ingest")
    autonomy_rung: Mapped[str] = mapped_column(String(8), default="L2")
    classification: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    action_plan: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    policy_eval: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    approval: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    execution: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32))  # remediation | triage | policy_block
    status: Mapped[str] = mapped_column(String(32), default="pending")
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    sla_minutes: Mapped[int] = mapped_column(Integer, default=15)
    decided_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class ExecutionRecord(Base):
    __tablename__ = "execution_records"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id"), index=True)
    snapshot_id: Mapped[str] = mapped_column(String(64))
    actions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    verify_status: Mapped[str] = mapped_column(String(32), default="ok")
    rolled_back: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    run_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    event_type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    prev_hash: Mapped[str] = mapped_column(String(64))
    entry_hash: Mapped[str] = mapped_column(String(64), unique=True)
    signature: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class EvalCase(Base):
    __tablename__ = "eval_cases"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source: Mapped[str] = mapped_column(String(32))  # golden | rejection | dry_run
    label: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class ControlPlane(Base):
    __tablename__ = "control_plane"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    global_pause: Mapped[bool] = mapped_column(Boolean, default=False)
    paused_workflows: Mapped[list[str]] = mapped_column(JSON, default=list)


class IsolationEvent(Base):
    """Used by the policy rate limiter (max isolations / hour / tenant)."""

    __tablename__ = "isolation_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    endpoint_id: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
