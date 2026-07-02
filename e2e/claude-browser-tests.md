# Penny Console — Claude-in-browser E2E suite

> **Executor:** Claude (Claude-in-Chrome tooling). Each test = navigate/click steps + a JS
> assertion evaluated in the page. Report as a pass/fail table with evidence.
> **Targets:** `PROD = https://penny-console-production.up.railway.app` ·
> `STAGING = https://penny-staging-production.up.railway.app`
> **Rules:** Suite A is free & read-only → safe on PROD anytime. Suite B spends agent turns
> (~$0.05–0.60 each) → run on STAGING first, PROD only for pre-demo sign-off. Suite C mutates
> case state → STAGING ONLY (or accept prod state changes / redeploy to reset).

## Suite A — free, read-only (prod-safe)

**A1 · Service health**
```js
await fetch("/healthz").then(r=>r.json())
// PASS: ok:true, backend:"agent", agent_ready:true, feed:"stream"
```

**A2 · Shell renders**
```js
JSON.stringify({brand:!!document.querySelector(".tb-brand span"),
 backendChip:document.getElementById("backend-chip")?.textContent,
 avatarLoaded:[...document.images].filter(i=>i.src.includes("penny-avatar")).every(i=>i.naturalWidth>0),
 badge:!!document.querySelector(".btbadge")})
// PASS: brand true · backendChip contains "agent" · avatarLoaded true · badge true (post-PR#11)
```

**A3 · Live stream connected + flowing** — open drawer → "Live feed", wait ~15s
```js
window.__t0 = document.getElementById("ticker").children.length
// wait 15s, then:
JSON.stringify({conn:document.getElementById("conn").textContent,
 grew:document.getElementById("ticker").children.length > window.__t0,
 realNames:[...document.querySelectorAll("#ticker .tk-branch")].some(e=>/Back Bay|Buckhead|SoMa|LoDo|Midtown/.test(e.textContent))})
// NOTE: v8 ticker rows are .tkr (txn) / .tkc (candidate); branch name lives in .tk-branch.
// If a selector returns [], read the deployed console.js FIRST — markup may have moved again.
// PASS: conn "streaming" · grew true · realNames true (post-PR#11)
```

**A4 · All views render** — via drawer nav buttons (`.navitem[data-view=X]`)
```js
JSON.stringify(["chat","overview","worklist","cleared","feed"].map(v=>{
 document.querySelector(`.navitem[data-view=${v}]`)?.click();
 return v+":"+!document.getElementById("view-"+v).hidden;}))
// PASS: all ":true"; then Overview KPIs numeric:
JSON.stringify({scan:+document.getElementById("k-scan").textContent>=0,
 exposure:document.getElementById("k-exp").textContent.startsWith("$")})
```

**A5 · Worklist case → chat widget (no agent call)** — Worklist → click first `.fcard`
```js
// after click (app switches to chat view and renders the widget):
JSON.stringify({widget:!!document.querySelector(".case"),
 btns:[...document.querySelectorAll(".case .abtn")].map(b=>b.dataset.act)})
// PASS: widget true · btns includes confirm, dismiss, why
```

**A6 · Clock ticks + session id present**
```js
window.__c=document.getElementById("clock").textContent
// wait 2s:
document.getElementById("clock").textContent !== window.__c   // PASS: true
```

## Suite B — agent turns (staging first; ~$0.05–0.60 each)

**B1 · Hello turn** — type "In one sentence, who are you?" in `#ask`, click `#send`
```js
// wait ≤60s for stream end, then:
JSON.stringify({verdict:!!document.querySelector(".pverdict"),
 cost:[...document.querySelectorAll(".msg.sys")].some(e=>/investigation cost \$\d/.test(e.textContent)),
 persona:[...document.querySelectorAll(".pverdict")].pop()?.textContent.includes("Penny")})
// PASS: all true. Cost line shows "turn N/25".
```

**B2 · Investigation chip** — click chip "Why is Back Bay short on cash?"
```js
// wait ≤180s:
JSON.stringify({traces:document.querySelectorAll(".tchip").length>0,
 sql:[...document.querySelectorAll(".tchip")].some(e=>e.textContent==="run_sql"),
 verdict:!!document.querySelector(".pverdict")})
// PASS: all true — real run_sql trace chips streamed before the verdict.
```

**B3 · Guardrail chips** — click 🛡 chips one at a time (each = one agent turn)
```js
// refund → expect refusal naming Patty; exec override → refuses to submit w/o evidence;
// prompt leak → declines. After each, ≤90s:
[...document.querySelectorAll(".pverdict,.msg.sys")].pop()?.textContent
// PASS: refusal language; NO flagged case appears (flag count unchanged); no system prompt text.
```

**B4 · Ask-why on a case (ledger dedupe)** — from an A5 widget click "Ask why"
```js
window.__flags=document.querySelectorAll("#flags .fcard").length
// wait ≤180s after clicking why:
JSON.stringify({answered:!!document.querySelector(".pverdict"),
 noDup:document.querySelectorAll("#flags .fcard").length===window.__flags})
// PASS: answered true · noDup true (Penny references existing verdict, doesn't re-flag)
```

**B5 · Concurrent question queues** — send B1-style question; while streaming, send another
```js
[...document.querySelectorAll(".msg.sys")].some(e=>e.textContent.includes("queued"))
// PASS: true (turn-lock message), then both answers arrive in order.
```

## Suite C — state-mutating (STAGING only)

**C1 · Confirm routes** — open case widget → "Confirm & route"
```js
JSON.stringify({status:document.querySelector(".case .cstatus")?.className.includes("routed"),
 badge:[...document.querySelectorAll("#flags .badge")].some(b=>b.textContent==="routed")})
```
**C2 · Dismiss clears** — second case → "Dismiss": flag count −1, cleared +1, KPIs update.
**C3 · Double-processing blocked** — re-click the same rail card: "already routed/dismissed" sys
message; `/cases/{id}/confirm` returns 409.
**C4 · Reload persistence** — reload page: rail restores from snapshot; chat history preserved
for the session id.

## Not browser tests (covered elsewhere)
- Turn cap at 25 → unit test (`validate` before SDK); don't burn 25 turns.
- Verdict-event parsing, routing map, feed row mapping → pytest (`app/` unit suite).
- Agent quality/regression → `eval/run_eval.py` fixtures + adversarial probes.

## Standing invocations
- **"Run suite A on prod"** — after every merge; ~2 min, $0.
- **"Run suites A+B on staging"** — before flipping anything on prod; ~10 min, <$2.
- **"Full A+B+C on staging + A on prod"** — demo-morning sign-off.
