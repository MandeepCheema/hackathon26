# hackathon26 · Penny — the Controls Copilot

Team working repo for the **Atlan AI Hackathon 2026** (client: **McContext**, a ~2,000-store US burger chain gone AI-native).

**Challenge:** `Penny · Finance & Controls` — an agent that reads the finance trail across all stores and flags real leaks, while leaving honest activity alone. Detection job; scored on **precision *and* recall**.

**Product:** *Penny — the Controls Copilot*. A controller opens it like an inbox: real leaks ranked by $, each with an evidence trail, plus a **Cleared lane** showing what it deliberately did *not* flag (the engineered decoys) and why.

## Why Penny (data-driven)

We probed the live read-only world DB. Penny had the richest, most *demoable* signal:

| Signal (visible today) | Value |
|---|---|
| Cash over/short | 310 store-days mismatched, **net ~$1,854**; `str_009` tight skim ($610/14d), `str_003` thin persistent bias ($569/92d) |
| Three-way match | 11 invoice lines over received/agreed → **~$402** overcharge exposure |
| Decoy "duplicate payments" | 55 recurring payments that *look* like dups but aren't (distinct invoices, weekly cadence) |

Contrast: **Stock's** explorable variance was exactly $0 (base usage = sales×recipe; difficulty is hidden). **Patty/Pivot** = crowded / less lovable as a product.

**The agentic core:** 269 of 310 cash mismatches are ≤$5 noise; a rules engine fires on all 310 + 55 recurring = 365 false alarms. Penny fires ~3 and *explains the 362 it cleared*. **Precision under engineered ambiguity is the judgment** — that's what justifies an agent over a script.

## Architecture (one brain, two front doors)

```
DETERMINISTIC            AGENTIC                   OUTPUT
candidate gen    ──▶   agent adjudication   ──▶   flag+evidence / cleared+why / abstain
(cheap recall net)     (real? decoy? cause?
                        enough data?)
```

- **One CMA agent** = model + system prompt + per-duty **skills** + tools.
- **Tools:** company **MCP** (read) · deterministic **function tools** (the math — three-way match, cash-bias stats, fee modeling) · **action tool** `record_flag(...)` (the graded output at bench).
- **Bench runtime:** CMA in workspace, MCP = McContext hidden data, `record_flag` calls scored.
- **Product runtime:** our app drives the *same* agent, MCP = our read-only Postgres, renders flags + traces.

Full design: [`docs/penny-design.md`](docs/penny-design.md) *(draft — evolving)*.

## Repo layout (planned)

```
agent/        # the CMA definition — agent.yaml, skills/, mctools/ (function tools)
app/          # Penny Console — FastAPI backend + frontend (worklist, cleared lane, ask)
docs/         # design + decisions
challenges.html  # reference: all 5 hackathon challenges, one page
```

## Getting started (peers)

1. `cp .env.example .env` and fill in — **never commit `.env`** (this repo is public).
   - `WORLD_PG_URI` — read-only Postgres, from the kickoff deck / Slack.
   - `ANTHROPIC_API_KEY` — your participant workspace key (1Password). Never the judge key.
2. Explore the data (read-only, can't break it): point any Postgres client at `WORLD_PG_URI`.
3. Build loop: iterate the agent locally, deploy to your CMA workspace, register id+version, run the bench (3 lives), submit early (bonus).

Help: **#atlan-ai-hackathon-2026** on Slack.
