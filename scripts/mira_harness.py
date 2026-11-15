#!/usr/bin/env python3
"""mira_harness — one page to inspect a de novo run: for each stage, its specification, the prompt
template, every call as sent and as answered, and what the checker accepted or refused.

Usage: mira_harness.py <paper> [--out harness.html]
Reads runs/<paper>/mira-denovo/ (CLAIM_GRAPHS_ROOT or cwd), extract/prompts/mira/ and
docs/design/2026-11-01-mira-denovo-stages.md from claim-graphs. Self-contained output.
"""
import glob, html, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__)); CG = os.path.dirname(HERE)
ROOT = os.environ.get("CLAIM_GRAPHS_ROOT") or os.getcwd()
STAGES = ["inventory", "evidence", "findings", "hypotheses", "alternatives", "checks-cited-requests", "questions-summaries", "assemble"]
esc = lambda s: html.escape(str(s if s is not None else ""))

def spec_sections():
    src = open(os.path.join(CG, "docs", "design", "2026-11-01-mira-denovo-stages.md"), encoding="utf-8").read()
    parts = re.split(r"^## Stage (\d) — ", src, flags=re.M)
    return {int(parts[i]): parts[i + 1].split("\n---", 1)[0] for i in range(1, len(parts), 2)}

def md(s):   # the little markdown the spec and prompts use: headings, bullets, bold, code, paragraphs
    out, buf, lst = [], [], False
    def flush():
        nonlocal buf
        if buf: out.append("<p>" + inline(" ".join(buf)) + "</p>"); buf = []
    def inline(t):
        t = esc(t); t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t); t = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", t); t = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", t)
        return t
    for line in s.split("\n"):
        if line.startswith("- "):
            flush()
            if not lst: out.append("<ul>"); lst = True
            out.append("<li>" + inline(line[2:]) + "</li>"); continue
        if lst and not line.startswith("  "): out.append("</ul>"); lst = False
        if line.startswith("**") and line.rstrip().endswith("**") and len(line) < 60: flush(); out.append("<h4>" + inline(line.strip("*")) + "</h4>"); continue
        if line.startswith("`★"): flush(); out.append("<p class=ins>" + inline(line.strip("`★ ")) + "</p>"); continue
        if not line.strip(): flush(); continue
        if lst: out[-1] = out[-1][:-5] + " " + inline(line.strip()) + "</li>"; continue
        buf.append(line.strip())
    flush()
    if lst: out.append("</ul>")
    return "\n".join(out)

def table(items, cols):
    if not items: return "<p class=m>none</p>"
    th = "".join(f"<th>{esc(c)}</th>" for c in cols)
    rows = "".join("<tr>" + "".join(f"<td>{esc(json.dumps(it.get(c), ensure_ascii=False) if isinstance(it.get(c), (list, dict)) else it.get(c))}</td>" for c in cols) + "</tr>" for it in items)
    return f"<table><thead><tr>{th}</tr></thead><tbody>{rows}</tbody></table>"

def main():
    a = sys.argv[1:]; paper = a[0]
    d = os.path.join(ROOT, "runs", paper, "mira-denovo")
    out = a[a.index("--out") + 1] if "--out" in a else os.path.join(d, "harness.html")
    specs = spec_sections()
    J = lambda n: json.load(open(p, encoding="utf-8")) if os.path.exists(p := os.path.join(d, f"stage{n}.json")) else None
    R = lambda n: json.load(open(p, encoding="utf-8")) if os.path.exists(p := os.path.join(d, f"stage{n}.rejected.json")) else None
    secs = []
    for n, name in enumerate(STAGES, 1):
        pf = os.path.join(CG, "extract", "prompts", "mira", f"stage-{n}-{name}.md")
        prompt = open(pf, encoding="utf-8").read() if os.path.exists(pf) else ""
        calls = sorted(glob.glob(os.path.join(d, "calls", f"stage{n}*.prompt.txt")))
        cl = []
        for c in calls:
            tag = os.path.basename(c)[:-len(".prompt.txt")]
            raw = c.replace(".prompt.txt", ".raw.txt"); meta = c.replace(".prompt.txt", ".meta.json")
            m = json.load(open(meta)) if os.path.exists(meta) else {}
            cl.append(f"""<details class=call><summary><code>{esc(tag)}</code> <span class=m>{esc(f"{os.path.getsize(c):,} chars sent")}{esc(' · ' + str(m.get('served_by') or '') + ' · ' + str(m.get('seconds') or '') + ' s' if m else ' · not sent (dry run)')}</span></summary>
<details><summary>prompt as sent</summary><pre>{esc(open(c, encoding='utf-8').read())}</pre></details>
{f"<details><summary>reply</summary><pre>{esc(open(raw, encoding='utf-8').read())}</pre></details>" if os.path.exists(raw) else ""}
{f"<pre class=meta>{esc(json.dumps(m, indent=1))}</pre>" if m else ""}</details>""")
        acc, rej = J(n), R(n)
        accepted = ""
        if acc:
            for k, v in acc.items():
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    cols = [c for c in ("key", "text", "panel", "study", "source", "anchor") if c in v[0]]
                    accepted += f"<h4>{esc(k)} · {len(v)}</h4>" + table(v, cols)
                elif isinstance(v, list): accepted += f"<h4>{esc(k)} · {len(v)}</h4><p class=m>{esc(', '.join(map(str, v)))}</p>"
                elif isinstance(v, dict) and k != "groups": accepted += f"<h4>{esc(k)} · {len(v)}</h4><pre>{esc(json.dumps(v, indent=1, ensure_ascii=False)[:4000])}</pre>"
        refused = ""
        if rej:
            items = rej if isinstance(rej, list) else [dict(x, _kind=k) for k, v in rej.items() for x in (v if isinstance(v, list) else [{"key": kk, **vv} for kk, vv in v.items()])]
            refused = table(items, ["key", "text", "refused"]) if items else "<p class=m>none</p>"
        secs.append(f"""<section id=s{n}><h2>Stage {n} · {esc(name)}</h2>
<div class=cols><div><h3>Specification</h3>{md(specs.get(n, '(no section)'))}</div>
<div><h3>Prompt template</h3><pre class=tpl>{esc(prompt)}</pre></div></div>
<h3>Calls · {len(cl)}</h3>{''.join(cl) or '<p class=m>none</p>'}
<h3>Accepted</h3>{accepted or '<p class=m>no output on disk</p>'}
<h3>Refused</h3>{refused or '<p class=m>none</p>'}</section>""")
    g = glob.glob(os.path.join(d, "*-denovo.graph.json")); stats = json.load(open(g[0])).get("stats") if g else None
    page = f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>MIRA de novo harness · {esc(paper)}</title>
<link rel=stylesheet href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&family=DM+Mono:wght@400;500&display=swap">
<style>:root{{color-scheme:light;--paper:#fff;--paper-2:#f6f6f8;--ink:#1a1a1f;--ink-2:#55565e;--ink-3:#8a8b94;--rule:#e3e3e8;--link:#1d4ed8}}
@media(prefers-color-scheme:dark){{:root:not([data-theme=light]){{color-scheme:dark;--paper:#141418;--paper-2:#1d1d23;--ink:#ecebf0;--ink-2:#b4b3bc;--ink-3:#7f7f89;--rule:#2d2d35;--link:#8fb1ff}}}}
:root[data-theme=dark]{{color-scheme:dark;--paper:#141418;--paper-2:#1d1d23;--ink:#ecebf0;--ink-2:#b4b3bc;--ink-3:#7f7f89;--rule:#2d2d35;--link:#8fb1ff}}
body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 "DM Sans",Helvetica,Arial,sans-serif;padding:1.5rem max(24px,env(safe-area-inset-right,0)) 5rem max(24px,env(safe-area-inset-left,0))}}
h1{{font-size:1.4rem;margin:0 0 .3rem}}h2{{font-size:1.15rem;margin:2.4rem 0 .6rem;padding-top:1rem;border-top:2px solid var(--ink)}}h3{{font-size:.95rem;margin:1.2rem 0 .4rem;color:var(--ink-2)}}h4{{font-size:.85rem;margin:.8rem 0 .3rem}}
.meta,.m{{color:var(--ink-3);font-size:.82rem}}a{{color:var(--link);text-decoration:none}}nav a{{margin-right:1rem}}
.cols{{display:grid;grid-template-columns:1fr 1fr;gap:1.5rem}}@media(max-width:900px){{.cols{{grid-template-columns:1fr}}}}
pre{{font:.78rem/1.5 "DM Mono",Menlo,monospace;white-space:pre-wrap;word-break:break-word;background:var(--paper-2);border-radius:8px;padding:.8rem;max-height:32rem;overflow:auto}}pre.tpl{{max-height:none}}
code{{font:.82rem "DM Mono",Menlo,monospace;background:var(--paper-2);padding:0 .25rem;border-radius:3px}}
table{{border-collapse:collapse;width:100%;font-size:.84rem}}th,td{{text-align:left;vertical-align:top;padding:.3rem .5rem;border-top:1px solid var(--rule)}}th{{color:var(--ink-2);font-weight:500}}
details.call{{border:1px solid var(--rule);border-radius:8px;padding:.4rem .8rem;margin:.4rem 0}}details.call>summary{{cursor:pointer}}details.call details{{margin:.4rem 0}}
ul{{padding-left:1.2rem}}li{{margin:.15rem 0}}p.ins{{border-left:3px solid var(--rule);padding-left:.8rem;color:var(--ink-2)}}</style></head><body>
<h1>MIRA de novo · harness · {esc(paper)}</h1>
<p class=m>Specification: <code>docs/design/2026-11-01-mira-denovo-stages.md</code> · prompts: <code>extract/prompts/mira/</code> · runner: <code>scripts/mira_denovo.py</code> · run directory: <code>runs/{esc(paper)}/mira-denovo/</code>{(' · assembled graph: ' + esc(json.dumps(stats))) if stats else ' · no assembled graph yet'}</p>
<nav>{''.join(f'<a href="#s{n}">{n} {esc(s)}</a>' for n, s in enumerate(STAGES, 1))}</nav>
{''.join(secs)}
</body></html>"""
    open(out, "w", encoding="utf-8").write(page); print(f"wrote {out} ({len(page)//1024} KB)")

if __name__ == "__main__":
    main()
