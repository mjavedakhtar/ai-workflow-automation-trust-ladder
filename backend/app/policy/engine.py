"""Deterministic policy engine. Fail closed. Never trusts the model."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models import Backup, Endpoint, IsolationEvent
from backend.app.policy.linter import lint
from backend.app.schemas import ActionPlan, GuardrailConfig, PolicyEvaluation, RuleResult

POLICY_VERSION = "guardrails-v1"


def evaluate(
    db: Session,
    *,
    tenant_id: str,
    plan: ActionPlan,
    guardrails: GuardrailConfig | None = None,
    now: datetime | None = None,
) -> PolicyEvaluation:
    try:
        return _evaluate(db, tenant_id=tenant_id, plan=plan, guardrails=guardrails or GuardrailConfig(), now=now or datetime.utcnow())
    except Exception as exc:  # fail closed
        return PolicyEvaluation(
            policy_version=POLICY_VERSION,
            passed=False,
            results=[RuleResult(rule="fail_closed", passed=False, detail=str(exc))],
        )


def _evaluate(
    db: Session,
    *,
    tenant_id: str,
    plan: ActionPlan,
    guardrails: GuardrailConfig,
    now: datetime,
) -> PolicyEvaluation:
    results: list[RuleResult] = []

    if guardrails.block_injected_text:
        ok = not plan.derived_from_untrusted_text
        results.append(
            RuleResult(
                rule="block_injected_text",
                passed=ok,
                detail="ok" if ok else "Plan was derived from untrusted ticket/alert text — treated as data, never as a command.",
            )
        )

    if guardrails.require_reversible:
        ok = all(a.reversible for a in plan.actions)
        results.append(
            RuleResult(
                rule="require_reversible",
                passed=ok,
                detail="ok" if ok else "A proposed action is not reversible.",
            )
        )

    if guardrails.min_confidence:
        ok = plan.confidence >= guardrails.min_confidence
        results.append(
            RuleResult(
                rule="min_confidence",
                passed=ok,
                detail="ok" if ok else f"Confidence {plan.confidence:.2f} below {guardrails.min_confidence:.2f}.",
            )
        )

    isolate_count = 0
    for action in plan.actions:
        ep = db.get(Endpoint, action.target_id)
        if ep is None or ep.tenant_id != tenant_id:
            results.append(RuleResult(rule="scope", passed=False, detail=f"Target {action.target_id} is outside tenant scope."))
            continue
        results.append(RuleResult(rule="scope", passed=True, detail=f"{action.target_id} in tenant {tenant_id}."))

        if action.type == "isolate":
            isolate_count += 1
            if guardrails.never_isolate_critical_infra:
                critical = ep.role == "critical-infra" or "role:critical-infra" in (ep.tags or [])
                results.append(
                    RuleResult(
                        rule="never_isolate_critical_infra",
                        passed=not critical,
                        detail="ok" if not critical else f"{ep.hostname} is tagged role:critical-infra — isolate blocked.",
                    )
                )

        if action.type == "restore":
            if not action.backup_id:
                results.append(RuleResult(rule="require_verified_backup", passed=False, detail="Restore without a backup id."))
                continue
            backup = db.get(Backup, action.backup_id)
            ok = (
                backup is not None
                and backup.tenant_id == tenant_id
                and backup.endpoint_id == action.target_id
                and backup.integrity_verified
                and not backup.encrypted
                and backup.taken_at >= now - timedelta(hours=guardrails.require_verified_backup_hours)
            )
            results.append(
                RuleResult(
                    rule="require_verified_backup",
                    passed=bool(ok),
                    detail="ok" if ok else "Backup missing, encrypted, unverified, or older than the configured window.",
                )
            )

        if action.type == "script":
            lint_result = lint(action.script or "")
            results.append(
                RuleResult(
                    rule="script_allowlist",
                    passed=bool(lint_result["passed"]),
                    detail=lint_result["detail"],
                )
            )

    if isolate_count:
        since = now - timedelta(hours=1)
        recent = db.scalar(
            select(func.count(IsolationEvent.id)).where(
                IsolationEvent.tenant_id == tenant_id, IsolationEvent.created_at >= since
            )
        ) or 0
        ok = (recent + isolate_count) <= guardrails.max_isolations_per_hour
        results.append(
            RuleResult(
                rule="rate_limit_isolations",
                passed=ok,
                detail="ok" if ok else f"Would exceed {guardrails.max_isolations_per_hour} isolations/hour (recent={recent}).",
            )
        )

    return PolicyEvaluation(policy_version=POLICY_VERSION, passed=all(r.passed for r in results), results=results)
