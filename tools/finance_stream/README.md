# finance_stream

Synthetic, **union-compatible** finance data emitted as a **live stream**.

It continues the `world.fin_*` finance model (a retail POS + accounts-payable
world) by generating *new* rows with the same schema, referential integrity, and
source-learned distributions — so synthetic rows drop straight into a
`UNION ALL` with the real tables.

```
  POS side      fin_register_txns ──(end of day)──▶ fin_register_totals
                                                     fin_card_mix
                                                     fin_cash_counts
                                                     fin_paid_outs
                                     ──▶ fin_bank_settlements
                                         fin_settlement_adjustments

  AP side       fin_purchase_orders ─▶ fin_po_lines ─▶ fin_goods_receipts
                    │                                        │
                    └──────────▶ fin_invoices ◀──────────────┘
                                     │  └▶ fin_invoice_lines
                                     ▼
                                 fin_payments_out ─(rare)─▶ fin_credit_memos
```

## Why it unions cleanly

The exact column layout, order, types, and primary keys of every `world.fin_*`
table were captured into [`_schema.json`](_schema.json). Target tables are
generated from that, so a synthetic `fin_invoices` row has *identical* columns to
the real one. Reference keys (stores, staff, suppliers, SKUs, agreed prices, fee
schedule) are loaded live from the read-only source, so joins hold across the
real/synthetic boundary. Generated ids continue the source sequences
(`rtx_002542` picks up after `rtx_002541`, `po_00297` after `po_00296`, …), so
there are no key collisions.

## Install

```bash
pip install -r finance_stream/requirements.txt   # psycopg[binary]
```

The read-only source DSN is read from the **`WORLD_PG_URI`** env var (same as the
repo's `.env.example`) — it is never hardcoded. Set it before running, e.g.:

```bash
export WORLD_PG_URI="postgresql://.../world_dev"   # from Slack / kickoff deck
# or pass explicitly: python -m finance_stream --source-dsn "$WORLD_PG_URI"
```

## Run

Default is a **wall-clock real-time** JSONL stream to stdout:

```bash
python -m finance_stream                 # one JSON event per line, real time
python -m finance_stream | jq -c .        # pretty
python -m finance_stream | grep fin_invoices
```

Each line is `{"table": "<name>", "row": {<exact source columns>}}` — a
CDC-style change stream (AP rows are re-emitted as their status advances
`ordered→received`, `approved→paid`).

### Watch whole days go by (time compression)

`--speed` multiplies sim time. `1.0` = real time (default); larger compresses it
so you can see end-of-day rollups, settlements, and full 30-day payment chains:

```bash
python -m finance_stream --speed 3600     # 1 real second ≈ 1 sim hour
```

### Land it somewhere union-ready

```bash
# SQLite mirror + a snapshot of the real tables in the SAME file,
# so you can UNION ALL real+synthetic with no other infra:
python -m finance_stream --sink sqlite --seed-source --speed 100000

sqlite3 finance_synth.db \
 "SELECT status, count(*) FROM (
     SELECT status FROM world_fin_invoices
     UNION ALL SELECT status FROM synth_fin_invoices) GROUP BY status;"
```

```bash
# Postgres: writes to a `synth` schema mirroring the source DDL.
# Point it at your own writable DB (the source is read-only).
TARGET_DATABASE_URL=postgresql://user:pw@host/db \
  python -m finance_stream --sink postgres --speed 100000
# then, if synth lives on the same server as the source:
#   SELECT * FROM world.fin_invoices UNION ALL SELECT * FROM synth.fin_invoices;
```

```bash
python -m finance_stream --sink both      # stdout JSONL + sqlite at once
```

## Live demo (data consumed by an app / agent)

Wall-clock real time (`--speed 1`, so timestamps are *now* and the feed is live),
a steady cadence an app can react to, and rare leaks so the agent's **precision**
is what's on show. `--rate 120` across the stores is ~1 transaction every ~4s,
plus a purchase order every ~10 min.

```bash
# App/agent reads over SQL: stream into your writable Postgres, load the views once.
export TARGET_DATABASE_URL="postgresql://…"       # your DB, not the read-only source
psql "$TARGET_DATABASE_URL" -f tools/finance_stream/views.postgres.sql   # one time
python -m finance_stream --sink postgres \
    --rate 120 --po-rate 6 \
    --inject-leak all --leak-rate 0.03 --leak-log demo_leaks.jsonl
# the app/agent now queries fin_invoices_all / fin_payments_out_all / … live
```

```bash
# Event-driven agent: consume the JSONL feed directly.
python -m finance_stream --rate 120 --po-rate 6 \
    --inject-leak all --leak-rate 0.03 --leak-log demo_leaks.jsonl \
  | your-agent-ingest
```

Everything stays `--speed 1`; nudge `--rate` for busier/quieter traffic. Daily
rollups + settlements land at close (21:00) or on `Ctrl-C`; add `--speed 12` if
you want a full day of them to roll by within a ~1-hour demo.

## Union it behind one name (`fin_<table>_all`)

Point a consuming app/agent at `fin_<table>_all` and it transparently sees source
rows plus everything the stream generated. Generate the DDL (no DB needed):

```bash
python -m finance_stream --emit-views postgres > views.postgres.sql   # world + synth schemas
python -m finance_stream --emit-views sqlite   > views.sqlite.sql     # world_<t> + synth_<t>
```

Ready-made copies are committed alongside this README
([`views.postgres.sql`](views.postgres.sql), [`views.sqlite.sql`](views.sqlite.sql)).
The 14 generated tables get real+synthetic `UNION ALL` views; the 5 dimension
tables get passthrough views so `_all` works uniformly. Example:

```sql
CREATE OR REPLACE VIEW "fin_invoices_all" AS
  SELECT * FROM world."fin_invoices"
  UNION ALL
  SELECT * FROM synth."fin_invoices";
```

## Inject leaks for detector testing (Penny)

Seed deliberate control failures with a **ground-truth log** to score precision/recall:

```bash
python -m finance_stream --sink sqlite --seed-source \
    --inject-leak all --leak-rate 0.1 --leak-log leaks.jsonl --speed 100000
```

| leak type | how it's woven in | how a detector catches it |
|-----------|-------------------|---------------------------|
| `skim` | cash quietly removed → drawer counts short | cash over/short vs expected |
| `overcharge` | one invoice line billed above agreed price / received qty | three-way match (PO vs receipt vs invoice) |
| `duplicate_payment` | the same invoice paid a second time | invoice paid >1× |

`--inject-leak` is repeatable (`--inject-leak skim --inject-leak overcharge`) or
`all`. Every injected leak is appended to the `--leak-log` JSONL (default
`finance_stream_leaks.jsonl`) as `{leak_type, detect_via, table, ref_id,
amount_cents, note, …}` — the truth set to grade flags against. Verified: injected
counts reconcile exactly with what a detector finds in the data.

## Key options

| flag | default | meaning |
|------|---------|---------|
| `--sink` | `stdout` | `stdout` \| `sqlite` \| `postgres` \| `both` |
| `--speed` | `1.0` | sim-time multiplier (`1.0` = wall-clock real time) |
| `--rate` | `6` | POS transactions per store per sim-hour |
| `--po-rate` | `1.5` | purchase orders created per sim-hour (all stores) |
| `--sim-start` | now (UTC) | ISO datetime to start the sim clock |
| `--seed` | `0` | RNG seed (reproducible streams) |
| `--seed-source` | off | (sqlite) also copy real tables in as `world_<table>` |
| `--sqlite-path` | `finance_synth.db` | sqlite output file |
| `--target-dsn` | env `TARGET_DATABASE_URL` | postgres target DSN |
| `--emit-views` | — | print union-view DDL (`postgres`\|`sqlite`) and exit |
| `--inject-leak` | off | seed leaks: `skim`\|`overcharge`\|`duplicate_payment`\|`all` (repeatable) |
| `--leak-rate` | `0.05` | probability an opportunity becomes an injected leak |
| `--leak-log` | `finance_stream_leaks.jsonl` | ground-truth JSONL of injected leaks |

`Ctrl-C` stops cleanly and flushes any open business day so you always get
complete rollups.

## How it stays consistent

* Store hours 09:00–21:00; POS arrivals are Poisson (exponential inter-arrival).
* Each sale is cash or card (~30% cash); card sales split credit/debit/amex by
  the source mix and roll into `fin_card_mix`.
* End of day emits `fin_register_totals` / `fin_card_mix` / `fin_cash_counts`
  and a `fin_bank_settlements` row (`gross = card_cents`, fee ≈ 226 bps, T+1/T+2).
* AP: a PO orders 1–3 SKUs from a supplier's real catalog at agreed prices →
  goods receipts (occasional short-ships) → invoice (`total = Σ lines`) →
  payment on the supplier's terms (net15/30/45) → occasional credit memo.

Verified on a compressed run: 0 orphaned foreign keys, and
`settlement.gross = totals.card_cents`, `invoice.total = Σ lines`,
`Σ card_mix = totals.card_cents` all hold exactly.
