from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Role = Literal["owner", "admin", "tech", "auditor"]
Rung = Literal["L0", "L1", "L2", "L3"]
Verdict = Literal["true_positive", "false_positive", "ambiguous"]


class Principal(BaseModel):
    user_id: str
    role: Role
    tenant_id: str


class Classification(BaseModel):
    verdict: Verdict
    confidence: float = Field(ge=0, le=1)
    endpoint_id: str
    ransomware_family: str | None = None
    reasoning: str
    evidence: list[str]
    clean_backup_id: str | None = None
    derived_from_untrusted_text: bool = False


class ProposedAction(BaseModel):
    type: Literal["isolate", "restore", "script"]
    target_id: str
    reversible: bool = True
    backup_id: str | None = None
    script: str | None = None


class ActionPlan(BaseModel):
    actions: list[ProposedAction]
    confidence: float = Field(ge=0, le=1)
    reasoning: str
    evidence: list[str]
    derived_from_untrusted_text: bool = False


class RuleResult(BaseModel):
    rule: str
    passed: bool
    detail: str


class PolicyEvaluation(BaseModel):
    policy_version: str
    passed: bool
    results: list[RuleResult]


class TriggerRunRequest(BaseModel):
    tenant_id: str | None = None
    alert_id: str
    autonomy_rung: Rung | None = None


class ApprovalDecision(BaseModel):
    decision: Literal["approve", "reject", "escalate"]
    reason: str | None = None


class LintRequest(BaseModel):
    script: str


class KillSwitchRequest(BaseModel):
    scope: Literal["global", "workflow"] = "global"
    workflow_id: str = "ransomware-isolate-restore"
    paused: bool = True


class GuardrailConfig(BaseModel):
    never_isolate_critical_infra: bool = True
    require_verified_backup_hours: float = 24
    require_reversible: bool = True
    max_isolations_per_hour: int = 5
    min_confidence: float = 0.80
    block_injected_text: bool = True


class ActivationRequest(BaseModel):
    tenant_id: str | None = None
    autonomy_rung: Rung = "L2"
    guardrails: GuardrailConfig = Field(default_factory=GuardrailConfig)
    canary: bool = True


class RunOut(BaseModel):
    id: str
    tenant_id: str
    status: str
    current_node: str
    autonomy_rung: str
    alert_id: str
    classification: dict[str, Any] | None
    action_plan: dict[str, Any] | None
    policy_eval: dict[str, Any] | None
    approval: dict[str, Any] | None
    execution: dict[str, Any] | None
    error: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
