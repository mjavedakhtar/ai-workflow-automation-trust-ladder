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
| `LICENSE` | MIT. |

## The idea in one line
Workflow builders define *what* an agent does. This project is the layer they usually skip — **how an MSP takes an agent from off → autonomous, one earned rung at a time**, with oversight, accountability, and role-based control throughout.

**Illustrating workflow:** **Ransomware detected → isolate endpoint & restore from a clean backup.** A **Triage Agent** confirms the threat and finds a clean backup; a **Remediation Agent** proposes isolate + restore. The model never executes — the platform does, after guardrails and (at L2) a human.

## 3 minutes — fork, run, prove the safety model

```bash
git clone https://github.com/mjavedakhtar/ai-workflow-automation-trust-ladder.git
cd ai-workflow-automation-trust-ladder
cp .env.example .env          # optional: add GOOGLE_API_KEY for live Gemini
uv sync --all-groups
uv run uvicorn backend.app.main:app --reload --port 8000
```

1. Open http://127.0.0.1:8000/prototype/ (stay **Automation Admin**).
2. On Overview, click **A-8841 workstation ransomware** → Oversight inbox fills from LangGraph.
3. Open the item → **Approve**. Then **Execution & audit** for the hash-chained ledger.
4. Repeat **A-8846** (domain controller is blocked) and **A-8850** (injected ticket text is not obeyed).
5. **Activate agent → Guardrails → Inject a forbidden command → Re-check** (platform linter). **Dry-run** replays labelled history.

Same origin also serves OpenAPI at `/docs`. Architecture write-up: [`backend/README.md`](backend/README.md).

```bash
uv run pytest -q
docker compose up --build
```

Demo identity (replace before production): header `X-API-Key: dev-change-me` plus `X-Role` (`owner` / `admin` / `tech` / `auditor`) and `X-Tenant-Id` (`northwind` / `acme` / `globex`).

## Canned walkthrough (no API)

Open `prototype/index.html` in a browser. The screens still work with scripted incidents:

0. **Activate agent** → read the **"What the agent does / why it beats a human at 3am"** panel.
1. **Role switcher** → **Automation Admin**, **L2 Technician**, **Auditor**.
2. **Guardrails** → *Inject a forbidden command* → *Re-check*. Then **Dry-run**.
3. **Oversight**, **Execution & audit**, **Reliability & evals**.

When the API is running, the same file at `/prototype/` is live: demo alerts, inbox, kill switch, linter, dry-run, activation, ledger, rollback, and evals hit the backend.

## Built with
- **Product / prototype:** original Trust Ladder concept and UI.
- **Backend:** FastAPI, LangGraph, Gemini (`google-genai`), deterministic policy engine, SQLite (Postgres-ready URL).
