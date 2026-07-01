"""finance_stream — synthetic, union-compatible finance data as a live stream.

Generates new rows for the ``world.fin_*`` model (POS + accounts payable) with
referential integrity and source-learned distributions, emitted in wall-clock
real time to stdout (JSONL), SQLite, or Postgres.
"""
