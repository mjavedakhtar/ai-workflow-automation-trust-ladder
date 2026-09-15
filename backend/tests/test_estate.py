from backend.tests.conftest import HEADERS, client


def test_estate_is_tenant_scoped():
    with client() as c:
        r = c.get("/v1/estate", headers=HEADERS)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["tenant"]["id"] == "northwind"
        assert {e["id"] for e in body["endpoints"]} == {"wks-finance-07", "srv-dc-01", "wks-sales-14"}
        assert all(a["tenant_id"] == "northwind" for a in body["alerts"])
        assert body["intel"]["technique_id"] == "T1486"
        acme = {**HEADERS, "X-Tenant-Id": "acme"}
        r2 = c.get("/v1/estate", headers=acme)
        assert {e["id"] for e in r2.json()["endpoints"]} == {"wks-hr-03"}
        assert {a["id"] for a in r2.json()["alerts"]} == {"A-9001"}
