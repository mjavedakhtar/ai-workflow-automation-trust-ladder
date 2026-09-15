"""Tool broker: agents only see tenant-scoped, schema-checked, logged tools."""

from __future__ import annotations

from typing import Any, Literal

from sqlalchemy.orm import Session

from backend.app import ledger
from backend.app.adapters import estate

AgentKind = Literal["triage", "remediation"]

TRIAGE_TOOLS = {"edr_snapshot", "backup_catalog", "mitre_context"}
REMEDIATION_TOOLS = {"edr_snapshot", "backup_catalog"}  # still read-only — mutating tools are execution-gateway only


def call(
    db: Session,
    *,
    tenant_id: str,
    run_id: str,
    agent: AgentKind,
    tool: str,
    args: dict[str, Any],
) -> Any:
    allowed = TRIAGE_TOOLS if agent == "triage" else REMEDIATION_TOOLS
    if tool not in allowed:
        raise PermissionError(f"{agent} cannot call {tool}")
    if tool == "edr_snapshot":
        result = estate.edr_snapshot(db, tenant_id, args["endpoint_id"])
    elif tool == "backup_catalog":
        result = estate.backup_catalog(db, tenant_id, args["endpoint_id"])
    elif tool == "mitre_context":
        result = {"channel": "data", **estate.load_mitre_excerpt()}
    else:
        raise PermissionError("unknown tool")
    ledger.append(
        db,
        tenant_id=tenant_id,
        run_id=run_id,
        event_type="tool_call",
        payload={"agent": agent, "tool": tool, "args": args},
    )
    return result
