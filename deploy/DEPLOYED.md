# CMA deployment record — Penny

| Item | Value |
|---|---|
| Agent ID | `agent_01PU7KPhV5EMnY1sYdN77DKs` |
| Version | **2** (2026-07-02 — v3 conversational system + trap-fixed skills, MCP always_allow) |
| Model | claude-opus-4-8 |
| Vault | `vlt_011Cccqn8zuaQXAeopNcbjcX` (static_bearer for the McContext MCP; token in .env, never here) |

Skills (uploaded via `ant beta:skills create`, SQL inlined into each SKILL.md):

| Skill | ID |
|---|---|
| cash-over-short | skill_014tF2pBQo6nkMpthLkbAiF4 |
| cogs-leakage | skill_015sAuRjNZxKsiT1mAkC6S8o |
| duplicate-payment | skill_01PcPVhtaoKqx61r7eXB5LtF |
| loss-prevention | skill_01HRztmcTQAYMYA2seUC16oA |
| policy | skill_01Aq4sGty6GREaLQJuGRy2aW |
| settlement | skill_014XnqNoRbuzK1BoWJP6fwfi |
| three-way-match | skill_012uxBKHw6pxp3duLGcaFc6T |

Redeploy flow (skills changed → re-upload changed skill → `ant beta:agents update` with new skill id
list + current `--version`; system changed → update `--system` only). See `deploy/cma_deploy.py`
for payload assembly; note the ant CLI quirks: `--model '{"id": …}'`, skills need `type: custom`
with pre-uploaded `skill_id`, MCP auth lives in a VAULT credential (matched by exact URL), and
`--auth` takes ONE full YAML mapping. Agent-level tokens are not a thing.

Platform: register the agent id on the Deploy page — it tracks the latest version automatically.
