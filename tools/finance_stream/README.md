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
