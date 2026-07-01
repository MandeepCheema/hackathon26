# Penny v2 — Remaining Four Duties + Policy Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`).

**Goal:** Add the 4 remaining Penny duties — `three-way-match`, `duplicate-payment`, `settlement`, `cogs-leakage` — plus a Policy Engine, on the v1 agent/eval foundation, and extend the eval to cover all 6 duties with data-verified fixtures.

**Architecture:** Same as v1 — one agent, per-duty skill + candidate SQL (Postgres via `run_sql`), typed `submit_*` actions. New: a `policy` skill that reads `fin_policy`/`policy_registry` (active + effective-dated) so three-way-match and cogs cite the governing rule. Eval extends `normalize()`/`REAL_POSITIVE` for the new tools and adds v2 fixtures.

**Tech Stack:** unchanged (Python 3.13, psycopg, claude-agent-sdk, pytest).

## Global Constraints
- Repo PUBLIC — no secrets in tracked files; creds only from gitignored `.env`.
- `run_sql` READ-ONLY. Eval NEVER sends `submit_*` to the real server (CaptureMCP intercepts).
- Subscription auth: `ensure_subscription_auth()` already drops `ANTHROPIC_API_KEY`; keep calling it.
- Fixtures are data-verified (below), NOT massaged. Never edit fixtures to force a pass.
- Ground every three-way / cogs verdict in policy (materiality $5 AND 0.5%; price-tol 0.5%; cogs target 30%, flag >34%, favorable <28%). Use ACTIVE, effective-dated policy only.
- Follow existing v1 files as templates: `agent/duties/*.sql`, `agent/skills/*/SKILL.md`, `eval/run_eval.py`.

## Verified ground truth (from live DB — embed in fixtures)
- **three-way-match** (7): `pol_00039`=over_billed_qty($144), `pol_00092`=price_variance($72), `pol_00150`=over_billed_qty($64.80), `pol_00222`=over_billed_qty($36), `pol_00221`=price_variance($24), `pol_00151`=over_billed_qty($22), `pol_00220`=over_billed_qty($12.80).
- **settlement** (10 store-days, status=shortfall): str_007/2026-04-12, str_010/2026-03-16, str_008/2026-03-02, str_010/2026-03-17, str_004/2026-03-27, str_008/2026-03-05, str_005/2026-05-02, str_007/2026-04-10, str_010/2026-03-19, str_007/2026-04-08.
- **duplicate-payment**: NONE real (0 invoices paid twice, 0 goods double-billed). Precision test: flag nothing; the 55 recurring same-amount payments are decoys.
- **cogs-leakage**: purchasing/receipts data too sparse to compute a trustworthy food-cost ratio → correct verdict is `within_tolerance` (abstain from leakage). Do NOT fabricate leakage.

---

### Task 1: Policy engine skill + query helper

**Files:** Create `agent/duties/policy_lookup.sql`; Create `agent/skills/policy/SKILL.md`; Test `tests/test_policy_sql.py`.

**Interfaces:** Produces `policy_lookup.sql` returning active, effective-dated policies: `select id, topic, title, body from world.fin_policy` UNION the active rows of `world.policy_registry` (`status='active'`).

- [ ] **Step 1: failing test**
```python
# tests/test_policy_sql.py
import os, pathlib, pytest
from agent.mcp_client import MCPClient
SQL = pathlib.Path("agent/duties/policy_lookup.sql").read_text() if pathlib.Path("agent/duties/policy_lookup.sql").exists() else ""
@pytest.mark.integration
def test_returns_active_policies_only():
    c=MCPClient(os.environ["MCCTX_MCP_URL"],os.environ["MCP_AUTH_TOKEN"])
    rows=c.run_sql(SQL,"policies")
    ids={r["id"] for r in rows}
    assert "finpol_materiality" in ids and "pol_refund_v3" in ids   # active
    assert "pol_refund_v2" not in ids                                # retired excluded
```
- [ ] **Step 2:** run `-m integration` → FAIL.
- [ ] **Step 3: write SQL**
```sql
-- agent/duties/policy_lookup.sql
select id, topic, title, body from world.fin_policy
union all
select id, topic, title, body from world.policy_registry where status='active';
```
- [ ] **Step 4:** run → PASS.
- [ ] **Step 5: write `agent/skills/policy/SKILL.md`** — a short shared reference:
```markdown
---
name: policy
description: Look up McContext's active, effective-dated policies before judging a finance exception, and cite the policy id.
---
# Policy grounding
Before a three-way-match or cogs verdict, run `agent/duties/policy_lookup.sql` via `run_sql` and apply:
- **finpol_materiality** — don't raise a 3-way exception under $5.00 AND under 0.5% of the line (both).
- **finpol_pricetol** — a billed price within 0.5% of contract is within tolerance (not an exception).
- **finpol_foodcost** — food cost ~30% of net sales; flag leakage only when materially over 34% AND unexplained; under 28% is favorable.
Always use the ACTIVE row (never a retired policy) and cite its id in your note.
```
- [ ] **Step 6: commit** `git add agent/duties/policy_lookup.sql agent/skills/policy/SKILL.md tests/test_policy_sql.py && git commit -m "feat(policy): active-policy lookup + grounding skill"`

---

### Task 2: three-way-match SQL + test

**Files:** Create `agent/duties/three_way_match.sql`; Test `tests/test_threeway_candidates.py`.

**Interfaces:** SQL returns policy-aware exceptions: `po_id, po_line_id, exception_type, amount_cents` where the variance exceeds BOTH materiality ($5 & 0.5%) and, for price, tolerance (0.5%).

- [ ] **Step 1: failing test**
```python
# tests/test_threeway_candidates.py
import os, pathlib, pytest
from agent.mcp_client import MCPClient
SQL=pathlib.Path("agent/duties/three_way_match.sql").read_text() if pathlib.Path("agent/duties/three_way_match.sql").exists() else ""
@pytest.mark.integration
def test_finds_exactly_the_seven_exceptions():
    c=MCPClient(os.environ["MCCTX_MCP_URL"],os.environ["MCP_AUTH_TOKEN"])
    rows=c.run_sql(SQL,"3way")
    by={r["po_line_id"]:r["exception_type"] for r in rows}
    assert by.get("pol_00039")=="over_billed_qty"
    assert by.get("pol_00092")=="price_variance"
    assert len(rows)==7
```
- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3: write SQL** (cast numerics to `::bigint`/`::int` for JSON, mirror v1 pattern):
```sql
-- agent/duties/three_way_match.sql
with j as (
  select pl.po_id, il.po_line_id,
    il.billed_qty, coalesce(gr.rq,0) rq, il.billed_unit_cost_cents bc, pl.agreed_unit_cost_cents ac,
    (il.billed_qty*il.billed_unit_cost_cents) line_val,
    (il.billed_qty-coalesce(gr.rq,0))*pl.agreed_unit_cost_cents qty_over,
    il.billed_qty*(il.billed_unit_cost_cents-pl.agreed_unit_cost_cents) price_over
  from world.fin_invoice_lines il
  join world.fin_po_lines pl on il.po_line_id=pl.id
  left join (select po_line_id,sum(received_qty) rq from world.fin_goods_receipts group by 1) gr on gr.po_line_id=pl.id)
select po_id, po_line_id,
  case when qty_over>500 and qty_over>0.005*line_val then 'over_billed_qty'
       when (bc-ac)>0 and (bc-ac)>0.005*ac and price_over>500 then 'price_variance' end as exception_type,
  round(greatest(qty_over, price_over))::bigint as amount_cents
from j
where (qty_over>500 and qty_over>0.005*line_val)
   or ((bc-ac)>0 and (bc-ac)>0.005*ac and price_over>500);
```
- [ ] **Step 4:** run → PASS (7 rows). **Step 5: commit** `feat(threeway): policy-aware match-exception SQL`.

---

### Task 3: settlement SQL + test

**Files:** Create `agent/duties/settlement.sql`; Test `tests/test_settlement_candidates.py`.

**Interfaces:** SQL returns `store_id, business_date, register_card_cents, expected_fee_cents, deposit_cents, missing_cents` for store-days where `missing = card − expected_fee − net_deposit` exceeds $2.

- [ ] **Step 1: failing test**
```python
# tests/test_settlement_candidates.py
import os, pathlib, pytest
from agent.mcp_client import MCPClient
SQL=pathlib.Path("agent/duties/settlement.sql").read_text() if pathlib.Path("agent/duties/settlement.sql").exists() else ""
@pytest.mark.integration
def test_finds_the_ten_shortfalls():
    c=MCPClient(os.environ["MCCTX_MCP_URL"],os.environ["MCP_AUTH_TOKEN"])
    rows=c.run_sql(SQL,"settle")
    keys={(r["store_id"],r["business_date"]) for r in rows}
    assert ("str_007","2026-04-12") in keys
    assert len(rows)==10
```
- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3: write SQL**
```sql
-- agent/duties/settlement.sql
with fee as (
  select cm.store_id, cm.business_date,
    sum(cm.gross_cents*fs.mdr_bps/10000.0 + cm.txn_count*fs.per_txn_fee_cents) ef
  from world.fin_card_mix cm join world.fin_fee_schedule fs on fs.card_type=cm.card_type
  group by 1,2)
select rt.store_id, rt.business_date::text as business_date,
  rt.card_cents::bigint as register_card_cents,
  round(f.ef)::bigint as expected_fee_cents,
  s.net_deposit_cents::bigint as deposit_cents,
  round(rt.card_cents - f.ef - s.net_deposit_cents)::bigint as missing_cents
from world.fin_register_totals rt
join world.fin_bank_settlements s on s.store_id=rt.store_id and s.covers_date=rt.business_date
join fee f on f.store_id=rt.store_id and f.business_date=rt.business_date
where abs(rt.card_cents - f.ef - s.net_deposit_cents) > 200;
```
- [ ] **Step 4:** run → PASS (10 rows). **Step 5: commit** `feat(settlement): fee-aware reconciliation SQL`.

---

### Task 4: duplicate-payment SQL + test (decoy separation)

**Files:** Create `agent/duties/duplicate_payment.sql`; Test `tests/test_dup_candidates.py`.

**Interfaces:** SQL returns candidate real duplicates only — an invoice paid more than once, OR a po_line billed on 2+ invoices. Returns `supplier_id, invoice_id, duplicate_of_invoice_id, amount_cents`. On this data it returns ZERO rows (the recurring same-amount payments are NOT duplicates).

- [ ] **Step 1: failing test**
```python
# tests/test_dup_candidates.py
import os, pathlib, pytest
from agent.mcp_client import MCPClient
SQL=pathlib.Path("agent/duties/duplicate_payment.sql").read_text() if pathlib.Path("agent/duties/duplicate_payment.sql").exists() else ""
@pytest.mark.integration
def test_no_real_duplicates_in_data():
    c=MCPClient(os.environ["MCCTX_MCP_URL"],os.environ["MCP_AUTH_TOKEN"])
    rows=c.run_sql(SQL,"dup")
    assert rows==[]   # the 55 recurring same-amount payments are decoys, not dups
```
- [ ] **Step 2:** run → FAIL (SQL empty errors) . **Step 3: write SQL**
```sql
-- agent/duties/duplicate_payment.sql
-- Real duplicate = same invoice paid twice, or the same goods (po_line) covered by two invoices.
-- Recurring same-amount payments with DISTINCT invoices are legitimate and excluded.
with paid_twice as (
  select invoice_id from world.fin_payments_out where invoice_id is not null
  group by invoice_id having count(*)>1),
double_covered as (
  select po_line_id from world.fin_invoice_lines where po_line_id is not null
  group by po_line_id having count(distinct invoice_id)>1)
select p.supplier_id, p.invoice_id, p.invoice_id as duplicate_of_invoice_id, p.amount_cents::bigint
from world.fin_payments_out p
where p.invoice_id in (select invoice_id from paid_twice)
   or p.invoice_id in (select il.invoice_id from world.fin_invoice_lines il
                       where il.po_line_id in (select po_line_id from double_covered));
```
- [ ] **Step 4:** run → PASS (0 rows). **Step 5: commit** `feat(dup): real-duplicate SQL (excludes recurring decoys)`.

---

### Task 5: cogs-leakage SQL + test (insufficient-data → abstain)

**Files:** Create `agent/duties/cogs_leakage.sql`; Test `tests/test_cogs_candidates.py`.

**Interfaces:** SQL returns `store_id, revenue_cents, cogs_cents, cogs_pct, receipt_days` where revenue = register totals and cogs = received_qty×agreed_cost. Includes `receipt_days` (count of distinct receipt dates) so the skill can detect sparse purchasing coverage.

- [ ] **Step 1: failing test**
```python
# tests/test_cogs_candidates.py
import os, pathlib, pytest
from agent.mcp_client import MCPClient
SQL=pathlib.Path("agent/duties/cogs_leakage.sql").read_text() if pathlib.Path("agent/duties/cogs_leakage.sql").exists() else ""
@pytest.mark.integration
def test_purchasing_coverage_is_sparse():
    c=MCPClient(os.environ["MCCTX_MCP_URL"],os.environ["MCP_AUTH_TOKEN"])
    rows={r["store_id"]:r for r in c.run_sql(SQL,"cogs")}
    # cogs% is implausibly low because purchasing/receipts data is too sparse to be a real ratio
    assert all(r["cogs_pct"] < 20 for r in rows.values())
```
- [ ] **Step 2:** run → FAIL. **Step 3: write SQL**
```sql
-- agent/duties/cogs_leakage.sql
with rev as (select store_id, sum(cash_cents+card_cents) rev from world.fin_register_totals group by 1),
spend as (select po.store_id, sum(gr.received_qty*pl.agreed_unit_cost_cents) cogs,
            count(distinct gr.received_at::date) rdays
          from world.fin_goods_receipts gr
          join world.fin_po_lines pl on gr.po_line_id=pl.id
          join world.fin_purchase_orders po on pl.po_id=po.id group by 1)
select r.store_id, r.rev::bigint as revenue_cents,
  coalesce(s.cogs,0)::bigint as cogs_cents,
  round(100.0*coalesce(s.cogs,0)/nullif(r.rev,0),1)::float as cogs_pct,
  coalesce(s.rdays,0)::bigint as receipt_days
from rev r left join spend s on s.store_id=r.store_id;
```
- [ ] **Step 4:** run → PASS. **Step 5: commit** `feat(cogs): revenue-vs-purchasing SQL with coverage signal`.

---

### Task 6: four duty skills

**Files:** Create `agent/skills/three-way-match/SKILL.md`, `agent/skills/duplicate-payment/SKILL.md`, `agent/skills/settlement/SKILL.md`, `agent/skills/cogs-leakage/SKILL.md`.

Write each following the v1 skill template (frontmatter + Rule + Procedure + Guardrails), grounded in the real tool rubric (`docs/mcp-contract.md`) and policy. Key rules per skill:
- **three-way-match** — run `three_way_match.sql`; each row → `submit_match_exception(po_id, po_line_id, exception_type, amount_cents, note)` citing `finpol_materiality`/`finpol_pricetol`. Do not flag within tolerance.
- **duplicate-payment** — run `duplicate_payment.sql`; submit `submit_duplicate_payment` ONLY for returned rows (there are none here). **Explicitly do NOT flag recurring same-amount payments with distinct invoices** — they are legitimate.
- **settlement** — run `settlement.sql`; each row → `submit_settlement(store_id, business_date, status='shortfall', register_card_cents, expected_fee_cents, deposit_cents, missing_cents, note)`. `missing` is already net of expected fee; still exclude any logged `fin_settlement_adjustments`.
- **cogs-leakage** — run `cogs_leakage.sql`; if `receipt_days` is sparse (purchasing doesn't cover the revenue period), the ratio is not trustworthy → submit `submit_cogs_variance(status='within_tolerance', ...)` and note the data is insufficient. **Do NOT report leakage from incomplete purchasing data.**

- [ ] Write all four. Verify each references its real tool + status enum (grep). Commit `feat: v2 duty skills (3-way, dup, settlement, cogs)`.

---

### Task 7: wire agent + scan runner + eval for all 6 duties

**Files:** Modify `agent/agent.yaml` (skills list), `agent/run_scan.py` (duty list), `eval/run_eval.py` (`normalize` + `REAL_POSITIVE`), `eval/fixtures.py` (add v2 fixtures). Test: extend `tests/test_eval_scoring.py`, `tests/test_run_scan.py`.

**Interfaces:** `normalize` maps the new tools: `submit_match_exception`→(threeway, po_line_id, exception_type); `submit_settlement`→(settlement, f"{store_id}:{business_date}", status); `submit_duplicate_payment`→(dup, invoice_id, "duplicate"); `submit_cogs_variance`→(cogs, store_id, status). `REAL_POSITIVE` adds `over_billed_qty, price_variance, short_received, duplicate_invoice, unauthorized_charge, tax_miscalc, shortfall, leakage, duplicate`.

- [ ] **Step 1:** extend `agent.yaml` skills to `[cash-over-short, loss-prevention, policy, three-way-match, duplicate-payment, settlement, cogs-leakage]`.
- [ ] **Step 2:** extend `run_scan.scan_all` duty tuple to include the 4 new duties (policy is a reference skill, not scanned alone).
- [ ] **Step 3:** extend `normalize()` + `REAL_POSITIVE` in `eval/run_eval.py` per Interfaces; add unit tests for the new mappings.
- [ ] **Step 4:** add v2 fixtures to `eval/fixtures.py`:
```python
    # three-way-match (7 real exceptions, verified):
    {"duty":"threeway","entity":"pol_00039","status":"over_billed_qty"},
    {"duty":"threeway","entity":"pol_00092","status":"price_variance"},
    {"duty":"threeway","entity":"pol_00150","status":"over_billed_qty"},
    {"duty":"threeway","entity":"pol_00222","status":"over_billed_qty"},
    {"duty":"threeway","entity":"pol_00221","status":"price_variance"},
    {"duty":"threeway","entity":"pol_00151","status":"over_billed_qty"},
    {"duty":"threeway","entity":"pol_00220","status":"over_billed_qty"},
    # settlement (10 real shortfalls, verified):
    {"duty":"settlement","entity":"str_007:2026-04-12","status":"shortfall"},
    {"duty":"settlement","entity":"str_010:2026-03-16","status":"shortfall"},
    {"duty":"settlement","entity":"str_008:2026-03-02","status":"shortfall"},
    {"duty":"settlement","entity":"str_010:2026-03-17","status":"shortfall"},
    {"duty":"settlement","entity":"str_004:2026-03-27","status":"shortfall"},
    {"duty":"settlement","entity":"str_008:2026-03-05","status":"shortfall"},
    {"duty":"settlement","entity":"str_005:2026-05-02","status":"shortfall"},
    {"duty":"settlement","entity":"str_007:2026-04-10","status":"shortfall"},
    {"duty":"settlement","entity":"str_010:2026-03-19","status":"shortfall"},
    {"duty":"settlement","entity":"str_007:2026-04-08","status":"shortfall"},
    # duplicate-payment: NO positive fixtures — precision test (agent must flag none).
    # cogs-leakage: NO positive fixtures — abstention test (agent must submit within_tolerance).
```
- [ ] **Step 5:** run scoring unit tests → PASS. Commit `feat(eval): wire all 6 duties + v2 fixtures`.

---

### Task 8: full 6-duty eval run + reliability gate

- [ ] **Step 1:** run `set -a && . ./.env && set +a && env -u ANTHROPIC_API_KEY .venv/bin/python -m eval.run_eval` **twice**.
- [ ] **Step 2:** target: both runs `GATE PASS` (F1 ≥ 0.8) with the 17 real positives caught and 0 false alarms (no dup flags, no cogs leakage). If a duty wobbles, tune its SKILL.md wording (crisper decision rules) — never the fixtures.
- [ ] **Step 3:** commit any skill tuning. Push branch, open PR to main.

---

## Self-Review
- All 4 duties: SQL (Tasks 2–5) + skills (Task 6) + fixtures/wiring (Task 7) + eval (Task 8). Policy engine (Task 1) grounds 3-way + cogs. ✅
- Precision duties (dup, cogs) tested via 0-false-alarm, not positives — matches the honest ground truth. ✅
- normalize()/REAL_POSITIVE cover all new tools/statuses. ✅
- No placeholder steps; SQL + tests are complete. Skills (Task 6) are prose playbooks following the v1 template.
