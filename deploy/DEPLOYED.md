# CMA deployment record — Penny

| Item | Value |
|---|---|
| Agent ID | `agent_01PU7KPhV5EMnY1sYdN77DKs` |
| Version | **6** (recall fix: reused-invoice-number double-pay now caught in three-way + dup); prior: **4** (2026-07-02) — v3: token embedded in MCP URL (platform sessions attach NO vault — `vault_ids:[]`; server accepts `?token=`, header/vault paths dead at bench). v4: degraded-mode rule (tools down → say so + abstain) |
| Model | claude-opus-4-8 |
| Vault | `vlt_011Cccqn8zuaQXAeopNcbjcX` (static_bearer for the McContext MCP; token in .env, never here) |

Skills (uploaded via `ant beta:skills create`, SQL inlined into each SKILL.md):

| Skill | ID |
|---|---|
| cash-over-short | skill_014tF2pBQo6nkMpthLkbAiF4 |
| cogs-leakage | skill_015sAuRjNZxKsiT1mAkC6S8o |
| duplicate-payment | skill_013uURtxGsXCgwzXuMi8CYJX (v6: +reused-number path) |
| loss-prevention | skill_01HRztmcTQAYMYA2seUC16oA |
| policy | skill_01Aq4sGty6GREaLQJuGRy2aW |
| settlement | skill_014XnqNoRbuzK1BoWJP6fwfi |
| three-way-match | skill_01G1ZSNGiTd72PHdCZbxh3hT (v6: +duplicate_invoice) |

Redeploy flow (skills changed → re-upload changed skill → `ant beta:agents update` with new skill id
list + current `--version`; system changed → update `--system` only). See `deploy/cma_deploy.py`
for payload assembly; note the ant CLI quirks: `--model '{"id": …}'`, skills need `type: custom`
with pre-uploaded `skill_id`, MCP auth lives in a VAULT credential (matched by exact URL), and
`--auth` takes ONE full YAML mapping. Agent-level tokens are not a thing.

Platform: register the agent id on the Deploy page — it tracks the latest version automatically.

## Post-mortem 2026-07-02 (the 0/40 run)
The first Run burned a PATTY life (agent registered under the wrong challenge) with a dead MCP
(no vault attached by the platform). Penny lives untouched (3/3). Scope fence held under a
3-turn refund pressure campaign — judge credited the posture. Fixes: token-in-URL (verified
end-to-end via a real no-vault session: run_sql 200), degraded-mode prompt rule, and REGISTER
UNDER PENNY before running.
