from backend.tests.conftest import HEADERS, client


def test_true_positive_parks_at_hitl():
    c = client()
    r = c.post("/v1/runs", headers=HEADERS, json={"alert_id": "A-8841", "autonomy_rung": "L2"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] in {"awaiting_human", "running"}
    inbox = c.get("/v1/oversight", headers=HEADERS).json()["items"]
    assert any(i["run_id"] == body["id"] for i in inbox)


def test_false_positive_closes():
    c = client()
    h = {**HEADERS, "X-Tenant-Id": "acme"}
    r = c.post("/v1/runs", headers=h, json={"alert_id": "A-9001", "autonomy_rung": "L2"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "closed_false_positive"


def test_dc_case_is_policy_blocked():
    c = client()
    r = c.post("/v1/runs", headers=HEADERS, json={"alert_id": "A-8846", "autonomy_rung": "L2"})
    assert r.status_code == 200, r.text
    run = r.json()
    assert run["policy_eval"] is not None
    assert run["policy_eval"]["passed"] is False
    inbox = c.get("/v1/oversight", headers=HEADERS).json()["items"]
    assert any(i["kind"] == "policy_block" and i["run_id"] == run["id"] for i in inbox)


def test_approve_executes_and_ledger_chains():
    c = client()
    run = c.post("/v1/runs", headers=HEADERS, json={"alert_id": "A-8841"}).json()
    inbox = c.get("/v1/oversight", headers=HEADERS).json()["items"]
    item = next(i for i in inbox if i["run_id"] == run["id"])
    decided = c.post(
        f"/v1/oversight/{item['id']}/decide",
        headers=HEADERS,
        json={"decision": "approve"},
    )
    assert decided.status_code == 200, decided.text
    final = c.get(f"/v1/runs/{run['id']}", headers=HEADERS).json()
    assert final["status"] in {"closed", "executed"}
    chain = c.get("/v1/ledger", headers=HEADERS, params={"run_id": run["id"]})
    assert chain.status_code == 200
    assert chain.json()["intact"] is True
