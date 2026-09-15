"""Read-only and mutating adapters. Agents never call these directly — only the tool broker / execution gateway."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import Backup, Endpoint, IsolationEvent, Tenant

ESTATE_PATH = Path(__file__).resolve().parent.parent / "data" / "estate.json"
MITRE_PATH = Path(__file__).resolve().parent.parent / "data" / "mitre_t1486.json"


def load_estate_file() -> dict[str, Any]:
    return json.loads(ESTATE_PATH.read_text())


def load_mitre_excerpt() -> dict[str, Any]:
    return json.loads(MITRE_PATH.read_text())


def seed_estate(db: Session) -> None:
    raw = load_estate_file()
    now = datetime.utcnow()
    if db.get(Tenant, raw["tenants"][0]["id"]):
        return
    for t in raw["tenants"]:
        db.add(Tenant(**t))
    db.flush()
    for e in raw["endpoints"]:
        db.add(Endpoint(**e))
    db.flush()
    for b in raw["backups"]:
        offset = b.pop("taken_at_offset_hours")
        db.add(
            Backup(
                **b,
                taken_at=now + timedelta(hours=offset),
                age_hours=abs(offset),
            )
        )
    db.flush()


def get_alert(alert_id: str) -> dict[str, Any] | None:
    for alert in load_estate_file()["alerts"]:
        if alert["id"] == alert_id:
            return dict(alert)
    return None


def edr_snapshot(db: Session, tenant_id: str, endpoint_id: str) -> dict[str, Any]:
    ep = db.get(Endpoint, endpoint_id)
    if ep is None or ep.tenant_id != tenant_id:
        raise PermissionError("cross-tenant or unknown endpoint")
    alert = next((a for a in load_estate_file()["alerts"] if a["endpoint_id"] == endpoint_id and a["tenant_id"] == tenant_id), None)
    return {
        "endpoint": {
            "id": ep.id,
            "hostname": ep.hostname,
            "role": ep.role,
            "tags": ep.tags,
            "isolated": ep.isolated,
            "health": ep.health,
        },
        "telemetry": {
            "encryption_rate": (alert or {}).get("encryption_rate"),
            "ransom_note": (alert or {}).get("ransom_note"),
            "process": (alert or {}).get("process"),
            "signal_confidence": (alert or {}).get("signal_confidence"),
            "family": (alert or {}).get("family"),
        },
        "channel": "data",
    }


def backup_catalog(db: Session, tenant_id: str, endpoint_id: str) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(Backup).where(Backup.tenant_id == tenant_id, Backup.endpoint_id == endpoint_id)
    ).all()
    return [
        {
            "id": b.id,
            "taken_at": b.taken_at.isoformat(),
            "integrity_verified": b.integrity_verified,
            "encrypted": b.encrypted,
            "age_hours": b.age_hours,
            "clean": b.integrity_verified and not b.encrypted,
        }
        for b in rows
    ]


def snapshot_endpoint(db: Session, tenant_id: str, endpoint_id: str) -> dict[str, Any]:
    ep = db.get(Endpoint, endpoint_id)
    if ep is None or ep.tenant_id != tenant_id:
        raise PermissionError("cross-tenant")
    return {
        "endpoint_id": ep.id,
        "isolated": ep.isolated,
        "health": ep.health,
        "at": datetime.utcnow().isoformat(),
    }


def isolate(db: Session, tenant_id: str, endpoint_id: str) -> dict[str, Any]:
    ep = db.get(Endpoint, endpoint_id)
    if ep is None or ep.tenant_id != tenant_id:
        raise PermissionError("cross-tenant")
    ep.isolated = True
    db.add(IsolationEvent(tenant_id=tenant_id, endpoint_id=endpoint_id))
    return {"ok": True, "endpoint_id": endpoint_id, "isolated": True}


def restore(db: Session, tenant_id: str, endpoint_id: str, backup_id: str) -> dict[str, Any]:
    ep = db.get(Endpoint, endpoint_id)
    backup = db.get(Backup, backup_id)
    if ep is None or backup is None or ep.tenant_id != tenant_id or backup.tenant_id != tenant_id:
        raise PermissionError("cross-tenant")
    ep.health = "restored"
    return {"ok": True, "endpoint_id": endpoint_id, "backup_id": backup_id}


def rollback_snapshot(db: Session, tenant_id: str, snap: dict[str, Any]) -> dict[str, Any]:
    ep = db.get(Endpoint, snap["endpoint_id"])
    if ep is None or ep.tenant_id != tenant_id:
        raise PermissionError("cross-tenant")
    ep.isolated = bool(snap.get("isolated"))
    ep.health = snap.get("health") or "healthy"
    return {"ok": True, "endpoint_id": ep.id}


def psa_close(ticket: str, note: str) -> dict[str, Any]:
    return {"ok": True, "system": "mock-psa", "ticket": ticket, "note": note}
