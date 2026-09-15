# Safe AI Automation for MSP Operations — *The Trust Ladder*

A product concept, PRD, architecture spec, interactive prototype, and **runnable backend** for introducing AI agents into MSP production environments **safely** — from off to autonomous, one earned rung at a time.

**Author:** Munshi Javed Akhtar

## What's here
| File | What it is |
|---|---|
| `backend/` | **Runnable backend** — FastAPI + LangGraph + Gemini (or mock LLM), policy engine, HITL, hash-chained ledger, mock EDR/backup/PSA. Fork and run. |
| `prototype/index.html` | Interactive UI. Also served at `/prototype/` when the API is up. |
| `One-Page-Briefing.pdf` | One-page concept briefing. |
| `One-Page-Briefing.html` / `.md` | Same briefing in HTML / Markdown. |
| `PRD_Safe_AI_Automation.md` | Product Requirements Document. |
| `Backend_Architecture_Design.md` | Backend & system architecture the code implements. |
| `docker-compose.yml` | One-command API + UI. |

## The idea in one line
Workflow builders define *what* an agent does. This project is the layer they usually skip — **how an MSP takes an agent from off → autonomous, one earned rung at a time**, with oversight, accountability, and role-based control throughout.

**Illustrating workflow:** **Ransomware detected → isolate endpoint & restore from a clean backup.** A **Triage Agent** confirms the threat and finds a clean backup; a **Remediation Agent** proposes isolate + restore. The model never executes — the platform does, after guardrails and (at L2) a human.

## Run the backend (fork this)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements-dev.txt
cp .env.example .env          # paste GOOGLE_API_KEY for live Gemini; omit it to use the mock LLM
export PYTHONPATH=.
uvicorn backend.app.main:app --reload --port 8000
```

Open http://127.0.0.1:8000/docs and http://127.0.0.1:8000/prototype/

```bash
docker compose up --build     # same API on :8000
pytest -q                     # policy, RBAC, ledger, workflow
```

Full API walkthrough, headers, and security notes: [`backend/README.md`](backend/README.md).

Demo identity (replace before production): header `X-API-Key: dev-change-me` plus `X-Role` (`owner` / `admin` / `tech` / `auditor`) and `X-Tenant-Id` (`northwind` / `acme` / `globex`).

## Try the prototype (3 minutes)
0. **Activate agent** → read the **"What the agent does / why it beats a human at 3am"** panel at the top.
1. **Role switcher** (top bar, "Viewing as") → flip between **Automation Admin**, **L2 Technician**, and **Auditor**.
2. **Activate agent** → **Guardrails** → *Inject a forbidden command* → *Re-check*. Then **Dry-run**.
3. **Oversight inbox** → domain-controller (blocked guardrail) and Triage Agent (does *not* escalate).
4. **Execution & audit** → Triage → Remediation handoff, rollback.
5. **Reliability & evals** → agreement trend, drift, closed loop.

With the API running, the prototype at `/prototype/` loads the live oversight inbox.

## Built with
- **Product / prototype:** original Trust Ladder concept and UI.
- **Backend:** FastAPI, LangGraph, Gemini (`google-genai`), deterministic policy engine, SQLite (Postgres-ready URL).
