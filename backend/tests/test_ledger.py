from backend.app import ledger
from backend.app.db import SessionLocal
from backend.app.services.bootstrap import init_db


def test_hash_chain_roundtrip():
    db = SessionLocal()
    try:
        init_db(db)
        ledger.append(db, tenant_id="northwind", event_type="test_a", payload={"n": 1})
        ledger.append(db, tenant_id="northwind", event_type="test_b", payload={"n": 2})
        db.commit()
        assert ledger.verify_chain(db, "northwind") is True
    finally:
        db.close()
