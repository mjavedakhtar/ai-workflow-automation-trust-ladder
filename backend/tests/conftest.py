import os
import tempfile
from pathlib import Path

tmp = Path(tempfile.mkdtemp())
os.environ["DATABASE_URL"] = f"sqlite:///{tmp / 'test.db'}"
os.environ["CHECKPOINT_PATH"] = str(tmp / "ckpt.sqlite")
os.environ["LLM_MODE"] = "mock"
os.environ["API_KEY"] = "dev-change-me"
os.environ["LEDGER_SIGNING_KEY"] = "test-ledger-key"
os.environ["GOOGLE_API_KEY"] = ""

from fastapi.testclient import TestClient  # noqa: E402

from backend.app.main import app  # noqa: E402

HEADERS = {
    "X-API-Key": "dev-change-me",
    "X-Role": "admin",
    "X-Tenant-Id": "northwind",
    "X-User-Id": "arjun",
}


def client() -> TestClient:
    return TestClient(app)
