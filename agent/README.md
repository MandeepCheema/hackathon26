# Penny agent (v1)
Duties: cash-over-short, loss-prevention. Read = MCP `run_sql`; actions = `submit_cash_variance`, `submit_loss_flag`.
Deterministic detection = SQL in `duties/`; judgment = `skills/`.

## Eval (offline-safe: reads live data, CAPTURES submits — never records a real bench outcome)
`set -a && . ../.env && set +a && env -u ANTHROPIC_API_KEY ../.venv/bin/python -m eval.run_eval`
Prints the scorecard + F1 gate. Auth uses your Claude subscription (unset ANTHROPIC_API_KEY).
