from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.orm import Session

from backend.app.adapters.estate import seed_estate
from backend.app.db import Base, engine
from backend.app.models import AgentDeployment, ControlPlane, EvalCase, Tenant
from backend.app.schemas import GuardrailConfig

GOLDEN = Path(__file__).resolve().parent.parent / "data" / "golden_set.json"


def init_db(db: Session) -> None:
    Base.metadata.create_all(bind=engine)
    seed_estate(db)
    if db.query(ControlPlane).first() is None:
        db.add(ControlPlane(global_pause=False, paused_workflows=[]))
    for tenant in db.query(Tenant).all():
        exists = (
            db.query(AgentDeployment)
            .filter_by(tenant_id=tenant.id, workflow_id="ransomware-isolate-restore")
            .one_or_none()
        )
        if exists is None:
            db.add(
                AgentDeployment(
                    tenant_id=tenant.id,
                    workflow_id="ransomware-isolate-restore",
                    autonomy_rung="L2",
                    status="canary",
                    scope={"tenants": [tenant.id]},
                    guardrails=GuardrailConfig().model_dump(),
                )
            )
    if db.query(EvalCase).count() == 0:
        for case in json.loads(GOLDEN.read_text()):
            db.add(
                EvalCase(
                    id=case["id"],
                    tenant_id=None,
                    source="golden",
                    label=case["label"],
                    payload=case,
                )
            )
    db.commit()
