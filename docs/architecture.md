# Penny — architecture & data flow

> Markdown mirror of [`architecture.html`](architecture.html) (open the HTML for the visual). One agent brain, two runtimes; a transaction generator feeds the product demo; executed actions land as notifications on the recipient's screen.

## System architecture — planes

```
GENERATION (product/demo only)
  Transaction Generator ── synth payments/registers/invoices/POs + injectable leaks & decoys
        │ writes
        ▼
DATA
  World Store (Postgres, world.*)  ·  MCP Server (run_sql read + submit_* actions)
        │ read tools ▲ action tools
        ▼
AGENT — the only brain (Claude Managed Agent; identical in product & bench)
  Penny Agent: model + system (judgment/abstention/anti-injection) + per-duty skills
  Deterministic sidecar: candidate nets + math (via run_sql)
  Adjudication + action selection (graduated autonomy)
        │ candidate verdicts (before any action)
        ▼
POLICY & GUARDRAIL — integrity layer
  Policy Engine (fin_policy/policy_registry, version+effective-date aware; verdicts cite policy id)
  Guardrails (input anti-injection · action spend-cap/approval · tool read-only · abstain)
  Decision Memory + Feedback (dedup, never re-flag dismissed, learn from human)
  Confidence calibration → autonomy tier
        │ policy-cleared, guardrailed submit_* calls + trace
        ▼
APPLICATION (product only, FastAPI + SQLite)
  Scan Orchestrator · Action Executor (artifacts + guardrail gate) · App DB (audit) · Notification Service
        │ serves
        ▼
PRESENTATION (product only)
  Controller Console (worklist · cleared · actions · ask)
  Recipient screens 🔔 (Regional Manager · Supplier · AP) — where executed actions show up
```

**Bench runtime (parallel, graded):** same agent, data = McContext hidden MCP, no generator/UI. A simulator drives cases → agent calls typed `submit_*` tools → judge scores trace + outcome. **Product work = bench work.**

**Dev-time harness (neither runtime):** Eval harness (generator ground-truth → precision/recall/F1; gate a bench life on offline F1 ≥ target) + Cost governor (candidate-net-first, turn/token cap, model tiering; keep scans inside $50).

## Data flow — product runtime
1. Generator emits txns/events (+ injected leaks/decoys) → World Store.
2. Scan fires (Scan-now / schedule / new-batch) → Orchestrator.
3. Orchestrator invokes Penny; it reads via MCP `run_sql`.
4. Candidate nets (deterministic) surface everything suspicious — high recall.
5. Adjudication (judgment) reasons only on candidates: real vs decoy, root cause, abstain — high precision.
6. Policy & guardrail check → agent calls a typed `submit_*` under graduated autonomy.
7. Action Executor gates (auto / 1-click / approval), produces artifact, writes audit log.
8. Notification Service pushes to recipient screen 🔔 + console toast.
9. Controller triages (confirm/dismiss/approve) → feedback loops to the ledger.

## Data flow — bench runtime
1. Harness starts a session with registered agent id + version (3 lives).
2. Simulator presents hidden cases; agent investigates via McContext MCP `run_sql`.
3. Same funnel: candidate nets → adjudication → verdict/abstain.
4. Agent records outcome via `submit_*` action tools — **this is the graded result**.
5. Judge scores trace + outcome (precision, recall, judgment, security, efficiency, communication).
```
