# Trust Ladder backend

Runnable implementation of the architecture in `Backend_Architecture_Design.md`.

The **model proposes; the platform disposes.** Gemini (or a deterministic mock LLM) only emits structured `Classification` / `ActionPlan` objects. Isolation, restore, and rollback happen only in the execution gateway after a fail-closed policy check.

## Quick start

From the repo root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements-dev.txt
cp .env.example .env   # add GOOGLE_API_KEY when you have it
export PYTHONPATH=.
uvicorn backend.app.main:app --reload --port 8000
```

- API docs: http://127.0.0.1:8000/docs
- Prototype (same origin): http://127.0.0.1:8000/prototype/
- Health: `GET /v1/health`

Without `GOOGLE_API_KEY`, `LLM_MODE=auto` uses the mock LLM. Policy, HITL, ledger, and execution still run — this is the path CI uses.

### Docker

```bash
docker compose up --build
```

## Demo auth (replace before production)

Every mutating/read API except `/v1/health` requires:

| Header | Example | Meaning |
|---|---|---|
| `X-API-Key` | `dev-change-me` | Shared demo secret from `.env` |
| `X-User-Id` | `arjun` | sofia (owner), arjun (admin), mia (tech), david (auditor) |
| `X-Role` | `admin` | owner / admin / tech / auditor |
| `X-Tenant-Id` | `northwind` | Tenant isolation boundary |

This is **not** SSO. Forks should swap `get_principal` for OIDC.

## Walk the ransomware workflow

```bash
KEY="X-API-Key: dev-change-me"
HDR=(-H "$KEY" -H "X-Role: admin" -H "X-Tenant-Id: northwind" -H "X-User-Id: arjun")

# 1. Workstation ransomware — parks at L2 HITL
curl -s "${HDR[@]}" -X POST http://127.0.0.1:8000/v1/runs \
  -H 'Content-Type: application/json' \
  -d '{"alert_id":"A-8841"}'

# 2. Oversight inbox
curl -s "${HDR[@]}" http://127.0.0.1:8000/v1/oversight

# 3. Approve (use the approval id from the inbox)
curl -s "${HDR[@]}" -X POST http://127.0.0.1:8000/v1/oversight/AP_ID/decide \
  -H 'Content-Type: application/json' \
  -d '{"decision":"approve"}'

# Domain controller — policy blocks isolate, never executes
curl -s "${HDR[@]}" -X POST http://127.0.0.1:8000/v1/runs \
  -H 'Content-Type: application/json' \
  -d '{"alert_id":"A-8846"}'

# Prompt-injection ticket text — triage does not obey it
curl -s "${HDR[@]}" -X POST http://127.0.0.1:8000/v1/runs \
  -H 'Content-Type: application/json' \
  -d '{"alert_id":"A-8850"}'
```

Seeded alerts live in `backend/app/data/estate.json` (fictional MSP estate, not production telemetry).

## What is implemented

| Piece | Behaviour |
|---|---|
| LangGraph | ingest → triage → remediate → policy → HITL / shadow / execute → close |
| Gemini | Structured JSON via `google-genai` when `GOOGLE_API_KEY` is set |
| Policy engine | Deterministic: critical-infra, backup age/integrity, reversibility, rate limit, injection flag, script allow-list |
| Execution gateway | snapshot → isolate/restore → verify; policy re-checked; rollback |
| Ledger | Hash-chained + HMAC, tenant-scoped |
| RBAC | Owner / Admin / Tech / Auditor |
| Kill switch | Global (owner/admin) or per-workflow (tech) |
| Evals / dry-run | Golden-set gates that do not need Gemini |
| Adapters | In-process mock EDR / backup / PSA — swap the functions in `adapters/estate.py` |

## Security notes for forks

- Never commit `.env`. Rotate `API_KEY` and `LEDGER_SIGNING_KEY` before sharing a deployment.
- Ticket/alert text is passed to the model in a **data** channel and is not concatenated into the system prompt as instructions.
- Agents cannot call isolate/restore tools. Only `services/execution.py` mutates state.
- Optional ATT&CK ping: `python backend/scripts/fetch_mitre.py` hits a single allow-listed MITRE GitHub URL with a size cap. Runtime classification uses the vendored T1486 excerpt, not live scraping.

## Tests

```bash
export PYTHONPATH=.
pytest -q
```
