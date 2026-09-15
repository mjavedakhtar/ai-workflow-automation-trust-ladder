from backend.tests.conftest import HEADERS, client


def test_tech_cannot_activate():
    c = client()
    h = {**HEADERS, "X-Role": "tech", "X-User-Id": "mia"}
    r = c.post("/v1/activation", headers=h, json={"autonomy_rung": "L3"})
    assert r.status_code == 403


def test_auditor_cannot_approve():
    c = client()
    h = {**HEADERS, "X-Role": "auditor", "X-User-Id": "david"}
    r = c.post("/v1/oversight/nope/decide", headers=h, json={"decision": "approve"})
    assert r.status_code == 403


def test_missing_api_key():
    c = client()
    r = c.get("/v1/health")
    assert r.status_code == 200
    r = c.get("/v1/runs")
    assert r.status_code == 401
