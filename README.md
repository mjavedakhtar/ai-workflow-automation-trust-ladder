# Safe AI Automation for MSP Operations — *The Trust Ladder*

A product concept, PRD, architecture spec, and interactive prototype for introducing AI agents into MSP production environments **safely** — from off to autonomous, one earned rung at a time.

**Author:** Munshi Javed Akhtar

## What's here
| File | What it is |
|---|---|
| `prototype/index.html` | **Interactive prototype** — open in any browser. No install, no build step. |
| `One-Page-Briefing.pdf` | One-page concept briefing. |
| `One-Page-Briefing.html` / `.md` | Same briefing in HTML / Markdown. |
| `PRD_Safe_AI_Automation.pdf` | Full **Product Requirements Document** — the spec behind the concept. |
| `PRD_Safe_AI_Automation.md` | Same PRD in Markdown. |
| `Backend_Architecture_Design.pdf` | **Backend & system architecture** — orchestration, guardrail enforcement, execution/rollback, audit ledger, security. |
| `Backend_Architecture_Design.md` | Same architecture doc in Markdown. |

## The idea in one line
Workflow builders define *what* an agent does. This project designs the layer they usually skip — **how an MSP takes an agent from off → autonomous, one earned rung at a time**, with oversight, accountability, and role-based control throughout.

**Illustrating workflow:** **Ransomware detected → isolate endpoint & restore from a clean backup** — a deliberately high-stakes case that needs both cyber protection (detect + isolate) and backup (find a clean restore point). Two agents: a **Triage Agent** that confirms the threat and finds a clean backup, handing off to a **Remediation Agent** that isolates + restores.

## Try this path (3 minutes)
0. **Activate agent** → read the **"What the agent does / why it beats a human at 3am"** panel at the top.
1. **Role switcher** (top bar, "Viewing as") → flip between **Automation Admin**, **L2 Technician**, and **Auditor**. Watch the €-ROI, the kill switch, and the action buttons change per role — this is RBAC as a product surface.
2. **Activate agent** → step to **Guardrails**, and on the script box click *Inject a forbidden command* → *Re-check* (watch the linter block it). Then run the **Dry-run**.
3. **Oversight inbox** → open the **domain-controller** item (blocked guardrail) and the **Triage Agent** item (it chooses *not* to escalate to a destructive action).
4. **Execution & audit** → full trace incl. the **Triage → Remediation handoff**, accountability record, rollback.
5. **Reliability & evals** → agreement trend, drift alerts, and how the feedback loop closes.

## Built with
Claude (Anthropic) used as a prototyping harness to pressure-test the concept and generate the interactive prototype. See the briefing for how product judgment vs. generation was split.
