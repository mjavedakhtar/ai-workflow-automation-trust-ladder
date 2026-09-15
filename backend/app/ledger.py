from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.models import LedgerEntry

GENESIS = "0" * 64


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _sign(entry_hash: str) -> str:
    key = get_settings().ledger_signing_key.encode()
    return hmac.new(key, entry_hash.encode(), hashlib.sha256).hexdigest()


def last_hash(db: Session, tenant_id: str) -> str:
    row = db.scalar(
        select(LedgerEntry)
        .where(LedgerEntry.tenant_id == tenant_id)
        .order_by(LedgerEntry.id.desc())
        .limit(1)
    )
    return row.entry_hash if row else GENESIS


def append(
    db: Session,
    *,
    tenant_id: str,
    event_type: str,
    payload: dict[str, Any],
    run_id: str | None = None,
) -> LedgerEntry:
    prev = last_hash(db, tenant_id)
    body = _canonical({"prev": prev, "event": event_type, "run": run_id, "payload": payload, "tenant": tenant_id})
    entry_hash = hashlib.sha256(body.encode()).hexdigest()
    entry = LedgerEntry(
        tenant_id=tenant_id,
        run_id=run_id,
        event_type=event_type,
        payload=payload,
        prev_hash=prev,
        entry_hash=entry_hash,
        signature=_sign(entry_hash),
    )
    db.add(entry)
    db.flush()
    return entry


def verify_chain(db: Session, tenant_id: str) -> bool:
    rows = db.scalars(
        select(LedgerEntry).where(LedgerEntry.tenant_id == tenant_id).order_by(LedgerEntry.id.asc())
    ).all()
    prev = GENESIS
    for row in rows:
        body = _canonical(
            {"prev": row.prev_hash, "event": row.event_type, "run": row.run_id, "payload": row.payload, "tenant": row.tenant_id}
        )
        expected = hashlib.sha256(body.encode()).hexdigest()
        if row.prev_hash != prev or row.entry_hash != expected or row.signature != _sign(row.entry_hash):
            return False
        prev = row.entry_hash
    return True
