# Penny Live Console — agent-side handoff

> **For:** Mandeep · **From:** Andrew · **Status:** UI concept approved-pending-layout-pick
> **Mock:** [`mock/penny-live-mockups.html`](../mock/penny-live-mockups.html) (open in a browser — 3 switchable layouts, animated, McContext-branded)
> **Scope of this doc:** exactly what the *agent runtime* must emit so the live UI can render real work instead of canned data. UI/backend (FastAPI + SSE + `finance_stream`) is on me; this is the contract between us.

## The product in one sentence

A live console where transactions stream top→bottom (from `tools/finance_stream`), Penny's investigations light up in real time (`run_sql` → reasoning → `submit_*`), and flagged leaks peel off and route to owners (LP / AP / Supplier Relations) under graduated autonomy — the "prove it's an agent, not a cron job" screen.

Three candidate layouts (same data feed, different metaphor): **Tape + routing** · **Precision funnel** (incoming → investigating → flagged/cleared) · **Ops desk** (tape | live investigation panel | routed queue). All three consume the **same event stream**, so the agent-side work below is identical whichever we pick.

## What the UI needs from the agent: one ordered event stream

Today [`agent/sdk_loop.py`](../agent/sdk_loop.py) `print()`s blocks as they stream. The UI needs those same moments as **structured events**. That's the whole ask — no behavior change, no new agent tools, no prompt edits.

### Event types (NDJSON objects; I'll carry them over SSE)

```jsonc
// 1 · scan lifecycle (from run_scan.py)
{"type":"scan.started",  "scan_id":"scan_0012", "duty":"cash-over-short", "ts":"2026-07-01T09:00:00Z"}
{"type":"scan.completed","scan_id":"scan_0012", "duty":"cash-over-short",
 "counts":{"flagged":2,"cleared":1,"abstained":7}, "ts":"..."}

// 2 · investigation (from ToolUseBlock name == run_sql)
{"type":"agent.sql", "scan_id":"scan_0012", "duty":"cash-over-short",
 "purpose":"candidate net: persistent cash bias per store",
 "query":"WITH daily AS (...)", "ts":"..."}

// 3 · reasoning (from TextBlock — chunks are fine, UI concatenates)
{"type":"agent.reasoning", "scan_id":"scan_0012", "duty":"cash-over-short",
 "text":"str_009 shows a tight one-directional bias...", "ts":"..."}

// 4 · verdict (from ToolUseBlock name == submit_*) — THE row the UI renders
{"type":"verdict", "scan_id":"scan_0012", "duty":"cash-over-short",
 "tool":"submit_cash_variance",
 "payload":{"store_id":"str_009","business_date":"pattern","status":"pattern_short",
            "expected_cash_cents":..., "counted_cash_cents":..., "variance_cents":-61000,
            "note":"t=-3.8 over 14 days ... confidence=0.91"},
 "ts":"..."}
```

Notes on the contract:
- **`payload` is the exact `submit_*` args, untouched.** The UI derives everything else (flag vs cleared, $ exposure, routing) from `status`/`risk_level` — statuses are already the rubric (`pattern_short`, `balanced`, `refer_investigation`, `clear`, …).
- **Correlation:** I derive a case id app-side as `duty + entity` (`store_id`/`staff_id`/`supplier_id` from the payload). You don't need to invent IDs.
- **Confidence:** the `submit_*` schemas have no confidence field, and the UI wants a meter. Smallest change: the duty skills already require the note to state evidence — add one line to each SKILL.md: *"End the note with `confidence=0.NN`."* I'll parse it out of `note`/`evidence_note`. (Alternative: add a `confidence` field to the emitted verdict event only — but then the agent must be asked for it somewhere anyway; the note keeps bench + product identical.)

## Concrete code changes (small — ~30 lines total)

### 1 · `agent/sdk_loop.py` — accept an `emit` callback

```python
def run_agent(system, task, client, emit=None):   # emit: Callable[[dict], None] | None
    ...
async def _run_async(system, task, client, emit=None):
    def _emit(ev):
        if emit: emit({**ev, "ts": datetime.now(timezone.utc).isoformat()})
    ...
    async for msg in sdk_client.receive_response():
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    print(block.text)                                  # keep — bench parity
                    _emit({"type": "agent.reasoning", "text": block.text})
                elif isinstance(block, ToolUseBlock):
                    print(f"[tool] {block.name}({block.input})")       # keep
                    if block.name.endswith("run_sql"):
                        _emit({"type": "agent.sql",
                               "purpose": block.input.get("purpose",""),
                               "query": block.input.get("query","")})
                    elif "submit_" in block.name:
                        _emit({"type": "verdict",
                               "tool": block.name.split("__")[-1],
                               "payload": block.input})
```

### 2 · `agent/run_scan.py` — tag duty + scan lifecycle

```python
def scan_all(client, runner=None, emit=None):
    ...
    for i, duty in enumerate(("cash-over-short", "loss-prevention")):
        scan_id = f"scan_{int(time.time())}_{i}"
        duty_emit = (lambda ev, d=duty, s=scan_id:
                     emit({**ev, "duty": d, "scan_id": s})) if emit else None
        if duty_emit: duty_emit({"type": "scan.started"})
        runner(system, _skill(duty), client, emit=duty_emit)
        if duty_emit: duty_emit({"type": "scan.completed"})
```

### 3 · `agent/skills/*/SKILL.md` — one line each

> In the submitted note, end with `confidence=0.NN` (your calibrated confidence in this verdict).

That's it. **Emission is observational** — same prompts, same tools, same `submit_*` calls, so bench behavior is untouched. If `emit` is `None` (bench / CLI), nothing changes at all.

## What I build against it (so you can see the seam)

```
finance_stream (txns + --inject-leak)──┐
                                       ├──▶ FastAPI app ──SSE /events──▶ live console
scan loop: run_scan.scan_all(client,   │      · merges both streams
           emit=queue.put) ────────────┘      · derives case_id, flag/clear, $, routing
                                              · routing map (below) + autonomy tier
```

Routing/tier map (app-side, from the verdict status — listed so we agree it's *not* agent logic):

| verdict | lane | tier |
|---|---|---|
| `pattern_short` / `refer_investigation` | Loss-Prevention | **approval** (accusation → human) |
| `submit_duplicate_payment` (any) | Accounts Payable | **approval** (money → human) |
| `over_billed`-type match exceptions | Supplier Relations | 1-click (reversible dispute) |
| low-grade `pattern_short` / `over` | Controller review | 1-click |
| `balanced` / `clear` / `within_tolerance` | Cleared lane | auto |

## Demo loop (target)

1. `finance_stream` runs wall-clock with `--inject-leak all --leak-rate 0.03` → transactions flow, ground truth logged.
2. Scan loop fires (interval or on end-of-day rollup events) → Penny investigates via `run_sql` over the union views (`fin_<table>_all`).
3. Console shows the investigation live; verdicts flag/clear; flags route with tier chips.
4. Kicker for the pitch: `leaks.jsonl` ground truth vs Penny's verdicts → live precision/recall on screen.

## Open questions for you

1. **Confidence in the note** — OK with the SKILL.md one-liner, or prefer a different channel?
2. **Scan trigger** — happy for the app to just call `scan_all()` on an interval to start? (Watermark/EOD-trigger can come later.)
3. **`ResultMessage`** carries usage/cost — worth emitting as `scan.completed` metadata for an on-screen "cost of this scan" stat? Nice pitch beat, zero risk.

Ping me in #atlan-ai-hackathon-2026 — once the layout is picked I'll have the FastAPI + SSE shell up the same day.
