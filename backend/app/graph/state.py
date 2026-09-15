from typing import Any, Literal, TypedDict


class GraphState(TypedDict, total=False):
    run_id: str
    tenant_id: str
    alert_id: str
    autonomy_rung: str
    workflow_id: str
    current_node: str
    classification: dict[str, Any] | None
    action_plan: dict[str, Any] | None
    policy_eval: dict[str, Any] | None
    approval: dict[str, Any] | None
    execution: dict[str, Any] | None
    status: str
    error: str | None
    approval_payload: dict[str, Any]


Route = Literal["true_positive", "false_positive", "ambiguous", "policy_pass", "policy_fail", "await_human"]
