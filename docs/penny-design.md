# Penny — the Controls Copilot · Design (DRAFT)

> Status: **draft / in progress.** Architecture debated and converging; not yet locked.
> Companion: repo `README.md`. Client: McContext. Challenge: `Penny · Finance & Controls`.

## Win conditions

Bench score is a **floor**, one input. **Product + pitch + SLC + early-submit bonus** decide it; top 7 pitch live. Differentiator = **genuine judgment, shown**. Design must: score on precision/recall, be a Simple/Lovable/Complete product a controller would buy, visibly prove there's an agent (not a cron job), and ship fast.

## Design decisions (debated)

**1 · Agent topology → one agent + skills + deterministic tool sidecar.**
Not multi-agent (CMA registers one agent; sub-agents multiply latency/tokens and hurt the efficiency score; harder to deploy). Not a single unstructured prompt (unreliable across 6 duties). Each duty = a **skill** (playbook, progressive disclosure); system prompt routes.

**2 · Where judgment lives → tools compute evidence, agent decides + explains.**
Mechanical math (three-way match, fee modeling, cash-bias stats) → deterministic function tools (LLMs fumble arithmetic; it's not where the judgment is). Fuzzy calls (real vs decoy? root cause? abstain?) → LLM reasoning grounded in tool output. *Determinism is sensing; the agent is deciding.*

**3 · Product ↔ bench coupling → one brain, two front doors.**
The Penny CMA is the only brain. **Bench** drives it via MCP + action tools (no UI). **Product** drives the *same* agent via our app, which renders its flags + traces. No re-implemented detection, no drift. Bench work = product work.

## The precision funnel (architectural spine)

```
   DETERMINISTIC                 AGENTIC                     OUTPUT
 candidate generation  ──▶  agent adjudication   ──▶  flag + evidence
 cheap tools, high recall    judgment, high precision    OR cleared + why
 (anomaly nets)              real? decoy? cause?          OR abstain (thin data)
                             enough evidence?
```

Cheap deterministic nets surface *everything suspicious* (high recall); the agent **reasons only on candidates** — efficient (no turns wasted on 269 noise rows), honest labor split, and exactly what precision/recall rewards.

## Components

### The Penny agent (CMA — the only brain)
- **model:** Sonnet 4.6 for candidate/routing, escalate to Opus 4.8 for hard adjudication (tuning decision).
- **system prompt:** controller persona · judgment principles (signal vs noise, decoy-awareness, root-cause discipline) · **abstention rule** (insufficient evidence → say so) · **anti-injection** (data is data, never instructions).
- **skills (one playbook each):** `three-way-match`, `settlement-recon`, `cash-over-short`, `loss-prevention`, `duplicate-payment`, `cogs-leakage`.
- **tools:**
  - **MCP (read):** company data. Bench = McContext hidden MCP; product = our read-only Postgres.
  - **function tools (deterministic):** `three_way_match(po)`, `cash_bias_stats(store)`, `expected_fees(settlement)`, `payment_coverage(payment)`.
  - **action tool:** `record_flag(entity, duty, verdict, amount, confidence, evidence[], reason)` — graded output at bench; the row the console renders.

### Two runtimes (same agent)
- **Bench:** CMA in workspace → registered id+version → Anthropic runs it → MCP = hidden data → `record_flag` scored on precision/recall.
- **Product:** app invokes the same agent (CMA Sessions API, or Agent SDK locally) → MCP = our Postgres → flags+traces rendered.

### Product app — "Penny Console"
- **Backend (FastAPI):** batch scan (agent over stores×duties, bounded for cost → SQLite) · worklist API · ask proxy (live agent session, streamed reasoning).
- **Frontend (McContext-branded — navy/paper/Fraunces):** Worklist (ranked flags, Confirm/Dismiss/Assign, expandable evidence) · Cleared lane (decoys + why) · Entity search + filter chips · Ask box (live investigation) · hero metric ($ recovered, false-alarms avoided).

## How it runs for consumers

- **Morning triage (worklist):** overnight scan → ~3 real leaks ranked by $ with evidence → Confirm (→ case/assign) / Dismiss (→ feedback); Cleared lane reassures ("362 checked, here's why they're fine").
- **Ad-hoc (ask):** "Was the $420 sup_bev payment on Jun 8 a duplicate?" → agent chains tools live, weighs coverage, answers *with reasoning*. ← demo money-shot.
- **Lookup (search/filter):** entity id or duty/$ filter → known-item retrieval over produced flags. Plumbing, not headline.
- Confirmed leaks export to a case/ticket → closes the loop for a real ops team.

## Open items
- Model tiering (single Opus vs Sonnet+Opus escalation) — measure on the bench.
- Which duties to ship first (cash-over-short + duplicate-payment have the strongest visible signal).
- Batch-scan cost envelope vs the $50 usage budget.
