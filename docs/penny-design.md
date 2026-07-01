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

## The real MCP contract (discovered live — `mccontext-company-systems` v1.28.1)

- **Read/investigate:** `run_sql(query, purpose)` — read-only SELECT/WITH. Only investigation tool; the deterministic "sidecar" = SQL the agent composes/runs.
- **Penny action tools (graded outputs):** `submit_cash_variance`, `submit_duplicate_payment`, `submit_match_exception`, `submit_loss_flag`, `submit_cogs_variance`, `submit_settlement`. Each has a **status enum** + explicit **"do NOT flag" clause** — the tool descriptions ARE the rubric.
- **Clearing a decoy is an explicit action** — e.g. `submit_loss_flag(risk_level=clear)`, `submit_cogs_variance(status=within_tolerance)`. Precision is scored by submitting the *right status*.
- Other challenges confirm mapping: Patty→`issue_credit`/`issue_refund`/`escalate`/`create_ticket`; Stock→`submit_variance`/`submit_forecast`/`submit_reorder`/`submit_markdown`; Pivot→`submit_answer`/`submit_report`.

## Integrity layer (Policy & Guardrail plane) — closes the agentic gaps

| Gap | Closure |
|---|---|
| Policy Engine | `get_policy(topic, as_of)` over `fin_policy` + `policy_registry`, **active + effective-dated only**; bands feed thresholds; verdicts cite policy id; never uses retired policy. |
| Input guardrail | `run_sql` output + note/description = **data, not instructions** (anti-injection). |
| Action guardrail | confidence gate · spend cap→escalate · irreversible money→human approval · never violate a tool's "do NOT flag". |
| Tool guardrail | read-only enforce · action allowlist per duty · turn/token cap. |
| Abstention | thin/conflicting evidence → submit clear/within_tolerance/balanced or decline; never fabricate. |
| Decision memory | ledger (entity+duty+period): dedup, don't re-flag dismissed. |
| Feedback loop | confirm/dismiss/approve → learned exclusions + threshold tuning. |
| Eval harness | generator ground-truth → precision/recall/F1 per duty; **gate: offline F1 ≥ target before spending a bench life**; regression fixtures. |
| Cost governor | candidate-net-first · turn/token cap · model tiering · track vs $50. |
| Confidence calibration | 0–1 → autonomy tier; money/accusation always human; calibrated on eval. |

## Corrected data findings (rubric-grounded — earlier probes were naive)

- **Cash:** `expected = cash_sales − paid_outs`; flag only **persistent directional short**. Real = **str_009 (−$610, t=−3.8)** and **str_003 (−$569, t=−3.8)**. Single-day/noise cleared. (Earlier "$1,854/5 stores" was inflated.)
- **Settlement:** modeling `expected_fee` (MDR bps + per-txn) → **10 store-days, $1,455 gap** (was $0 naively).
- **Loss prevention:** `stf_009_6` @ str_009 = 0.61 void rate vs 0.17 peer — **corroborates the str_009 cash short → refer_investigation**. str_004's high-void cluster = **store-wide (POS) decoy → clear/monitor**.
- **Duplicate payment:** 0 real in visible data; 55 look-alikes are legit recurring → real dups only in hidden bench cases. Best as the **decoy/precision showcase**, not a "$ caught" story.

## Scope — LOCKED

**v1 (build first): `cash-over-short` + `loss-prevention`.** The corroborating pair — `str_009` carries both a persistent cash short and a high-void cashier (`stf_009_6`), so v1 demonstrates chained cross-duty reasoning + the decoy discipline (`str_004` store-wide voids cleared). Real visible signal; strongest agentic demo.

**v1 action tools:** `submit_cash_variance`, `submit_loss_flag` (incl. `clear`/`balanced` for decoys).
**v1 read:** `run_sql`. **v1 policy:** none binding for these two, but the guardrail/abstention/peer-baseline logic applies.

**Fast-follow (v2):** `duplicate-payment` (decoy showcase), `settlement` ($1,455, needs fee model), `three-way-match` (7 policy-aware, needs `fin_policy`), `cogs-leakage`.

Each duty ships the full bundle: skill (tool def + policy + decoy exclusions) + candidate-net SQL + eval fixtures.

## Open items
- Model tiering (single Opus vs Sonnet+Opus escalation) — measure on eval + bench.
- Confidence→tier thresholds — calibrate on the eval set.
- Batch-scan cost envelope vs the $50 usage budget.
