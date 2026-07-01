#!/usr/bin/env python3
"""Render the repo's markdown docs into a single styled, self-contained site/docs.html.
Re-run after editing any doc:  python site/build_docs.py
Compact markdown support: headings, bold/italic/inline-code, fenced code, tables, lists, hr, links, blockquote.
"""
import html, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = [
    ("penny-design.md",   "Design",        "The full design — decisions, integrity layer, corrected findings, scope."),
    ("architecture.md",   "Architecture",  "Planes + data flow. One brain, two runtimes."),
    ("mcp-contract.md",   "MCP Contract",  "The live tools + Penny action schemas + the rubric."),
    ("policies.md",       "Policies",      "fin_policy / policy_registry / fee schedule — the grounding."),
    ("data-findings.md",  "Data Findings", "The world schema map + rubric-grounded leak inventory."),
]

def esc(s): return html.escape(s, quote=False)

def inline(s):
    s = esc(s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    return s

def render(md):
    out, i, lines = [], 0, md.split("\n")
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("```"):
            code=[]; i+=1
            while i < len(lines) and not lines[i].startswith("```"):
                code.append(lines[i]); i+=1
            out.append("<pre><code>"+esc("\n".join(code))+"</code></pre>"); i+=1; continue
        if ln.startswith("|") and i+1 < len(lines) and set(lines[i+1].replace("|","").strip()) <= set("-: "):
            head=[c.strip() for c in ln.strip("|").split("|")]; i+=2; rows=[]
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip("|").split("|")]); i+=1
            t="<table><thead><tr>"+"".join(f"<th>{inline(h)}</th>" for h in head)+"</tr></thead><tbody>"
            for r in rows: t+="<tr>"+"".join(f"<td>{inline(c)}</td>" for c in r)+"</tr>"
            out.append(t+"</tbody></table>"); continue
        m=re.match(r"(#{1,4})\s+(.*)", ln)
        if m: out.append(f"<h{len(m.group(1))}>{inline(m.group(2))}</h{len(m.group(1))}>"); i+=1; continue
        if ln.strip() in ("---","***","___"): out.append("<hr>"); i+=1; continue
        if ln.startswith(">"): out.append(f"<blockquote>{inline(ln.lstrip('> '))}</blockquote>"); i+=1; continue
        if re.match(r"\s*[-*]\s+", ln):
            items=[]
            while i < len(lines) and re.match(r"\s*[-*]\s+", lines[i]):
                items.append(f"<li>{inline(re.sub(r'^\s*[-*]\s+','',lines[i]))}</li>"); i+=1
            out.append("<ul>"+"".join(items)+"</ul>"); continue
        if re.match(r"\s*\d+\.\s+", ln):
            items=[]
            while i < len(lines) and re.match(r"\s*\d+\.\s+", lines[i]):
                items.append(f"<li>{inline(re.sub(r'^\s*\d+\.\s+','',lines[i]))}</li>"); i+=1
            out.append("<ol>"+"".join(items)+"</ol>"); continue
        if ln.strip()=="": i+=1; continue
        out.append(f"<p>{inline(ln)}</p>"); i+=1
    return "\n".join(out)

sections, nav = [], []
for fn, title, blurb in DOCS:
    p = ROOT/"docs"/fn
    if not p.exists(): continue
    slug = fn.replace(".md","")
    nav.append(f'<a href="#{slug}"><b>{esc(title)}</b><span>{esc(blurb)}</span></a>')
    sections.append(f'<article id="{slug}"><div class="doc-h"><span class="kx">{esc(fn)}</span><h1>{esc(title)}</h1></div>{render(p.read_text())}</article>')

HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Penny — Docs</title><style>
:root{--bg:#0a0b10;--panel:#14161f;--line:#242838;--ink:#f2f4fa;--mut:#9aa1b4;--dim:#6b7186;--brand:#7c6cff;--brand2:#a897ff;--cash:#3ddc97;--leak:#ff6b5e;
--serif:"Fraunces",Georgia,serif;--sans:-apple-system,BlinkMacSystemFont,"Inter","Segoe UI",Roboto,sans-serif;--mono:ui-monospace,SFMono-Regular,Menlo,monospace}
*{box-sizing:border-box;margin:0;padding:0}html{scroll-behavior:smooth}
body{background:var(--bg);color:var(--ink);font-family:var(--sans);line-height:1.65;display:grid;grid-template-columns:290px 1fr}
@media(max-width:860px){body{grid-template-columns:1fr}aside{display:none}}
a{color:var(--brand2);text-decoration:none}a:hover{text-decoration:underline}
aside{position:sticky;top:0;height:100vh;overflow:auto;border-right:1px solid var(--line);padding:26px 20px;background:#0c0e15}
.brand{display:flex;align-items:center;gap:10px;font-weight:700;font-size:19px;margin-bottom:8px;color:var(--ink)}
.brand .m{width:28px;height:28px;border-radius:8px;background:linear-gradient(135deg,var(--brand),var(--leak));display:flex;align-items:center;justify-content:center;font-family:var(--serif);color:#fff}
aside .home{font-size:12.5px;color:var(--dim);margin-bottom:22px;display:block}
aside nav{display:flex;flex-direction:column;gap:4px}
aside nav a{display:block;padding:11px 13px;border-radius:10px;color:var(--ink);border:1px solid transparent}
aside nav a:hover{background:var(--panel);border-color:var(--line);text-decoration:none}
aside nav a b{display:block;font-size:14px}aside nav a span{display:block;font-size:11.5px;color:var(--dim);margin-top:3px;line-height:1.4}
main{padding:56px 8vw;max-width:1000px}
article{padding-bottom:60px;margin-bottom:40px;border-bottom:1px solid var(--line);scroll-margin-top:20px}
.doc-h{margin-bottom:22px}.kx{font-family:var(--mono);font-size:12px;color:var(--brand2);letter-spacing:.1em}
h1{font-family:var(--serif);font-weight:600;font-size:40px;letter-spacing:-.02em;margin:4px 0 0}
h2{font-family:var(--serif);font-weight:600;font-size:27px;letter-spacing:-.01em;margin:34px 0 10px;padding-top:10px}
h3{font-size:19px;margin:24px 0 8px}h4{font-size:15px;color:var(--mut);margin:18px 0 6px;font-family:var(--mono);letter-spacing:.04em;text-transform:uppercase}
p{margin:12px 0;color:#d7dbe6}ul,ol{margin:12px 0 12px 24px}li{margin:5px 0;color:#d7dbe6}
code{font-family:var(--mono);font-size:.88em;background:#1c2030;color:var(--brand2);padding:2px 6px;border-radius:5px}
pre{background:#0d1018;border:1px solid var(--line);border-radius:12px;padding:16px 18px;overflow-x:auto;margin:14px 0}
pre code{background:none;color:#cdd6f4;padding:0;font-size:12.5px;line-height:1.6}
blockquote{border-left:3px solid var(--brand);background:rgba(124,108,255,.07);padding:10px 16px;border-radius:0 8px 8px 0;margin:14px 0;color:var(--mut)}
table{width:100%;border-collapse:collapse;margin:16px 0;font-size:13.5px;display:block;overflow-x:auto}
th,td{border:1px solid var(--line);padding:9px 12px;text-align:left}th{background:var(--panel);color:var(--brand2);font-family:var(--mono);font-size:11.5px;letter-spacing:.04em;text-transform:uppercase}
td{color:#d7dbe6}hr{border:0;border-top:1px solid var(--line);margin:24px 0}
strong{color:var(--ink)}
</style></head><body>
<aside>
  <div class="brand"><span class="m">P</span> Penny</div>
  <a class="home" href="index.html">← Back to penny.ai</a>
  <nav>__NAV__
  <a href="../mock/penny-console.html"><b>Live Console ↗</b><span>Clickable flow prototype</span></a>
  <a href="../docs/architecture.html"><b>Architecture (visual) ↗</b><span>The diagrams</span></a>
  </nav>
</aside>
<main>__BODY__
<p style="color:var(--dim);font-family:var(--mono);font-size:12px;margin-top:20px">Generated from repo markdown by site/build_docs.py · Atlan AI Hackathon 2026</p>
</main></body></html>"""

out = HTML.replace("__NAV__", "\n".join(nav)).replace("__BODY__", "\n".join(sections))
(ROOT/"site"/"docs.html").write_text(out)
print(f"wrote site/docs.html — {len(sections)} docs, {len(out)} bytes")
